"""Polished direct-PDF export with automatic company-letterhead support."""
import hashlib
import json
import re
from io import BytesIO

import pymupdf
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

from .generate import load_rules

A4 = pymupdf.paper_rect("a4")
BLACK = (0.08, 0.08, 0.08)
ACCENT = (0.20, 0.25, 0.32)
LETTERHEAD_TOP = 190.0
LETTERHEAD_BOTTOM = 100.0
LETTERHEAD_SIDE = 60.0


def _plain(value) -> str:
    text = re.sub(r"\*\*", "", str(value or "")).strip()
    return re.sub(r"(?i)^suggested tourism visit:\s*", "", text)


def _addressee_lines(pkg: dict, defaults: list) -> list[str]:
    lines = []
    for value in (pkg.get("addressee") or defaults):
        line = re.sub(r"\s*,\s*", ", ", _plain(value)).strip()
        if not line or line.casefold() in {"to", "to the visa officer"}:
            continue
        if re.fullmatch(r"(?i)(?:the\s+)?visa\s+officer", line):
            line = "The Visa Officer"
        lines.append(line)
    if not lines or lines[0] != "The Visa Officer":
        lines.insert(0, "The Visa Officer")
    return list(dict.fromkeys(lines))


def _document_style(pkg: dict) -> dict:
    """Choose a stable professional style variant for each generated package."""
    country = str(pkg.get("destination_country", "")).strip().casefold()
    if country in {
        "canada", "united states", "united states of america", "usa", "us",
        "new zealand", "australia",
    }:
        return {
            "font": "Times New Roman", "heading": "1F4E79", "table": "D9EAF7",
            "align": WD_ALIGN_PARAGRAPH.LEFT, "line": 1.15,
        }
    variants = (
        {"font": "Cambria", "heading": "1F4E79", "table": "D9EAF7", "align": WD_ALIGN_PARAGRAPH.LEFT, "line": 1.08},
        {"font": "Garamond", "heading": "6B4F3A", "table": "EFE4D5", "align": WD_ALIGN_PARAGRAPH.CENTER, "line": 1.12},
        {"font": "Aptos", "heading": "176B70", "table": "DDEEEE", "align": WD_ALIGN_PARAGRAPH.LEFT, "line": 1.10},
        {"font": "Georgia", "heading": "514A7E", "table": "E7E2F3", "align": WD_ALIGN_PARAGRAPH.CENTER, "line": 1.08},
    )
    payload = str(pkg.get("document_style_seed") or json.dumps(
        pkg, sort_keys=True, ensure_ascii=True, default=str
    )).encode("utf-8")
    return variants[hashlib.sha256(payload).digest()[0] % len(variants)]


def _wrapped_lines(text: str, width: float, font: str, size: float) -> list[str]:
    lines = []
    for source in _plain(text).splitlines() or [""]:
        current = ""
        for word in source.split():
            candidate = f"{current} {word}".strip()
            if current and pymupdf.get_text_length(candidate, fontname=font, fontsize=size) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines or [""]


def package_pdf(pkg: dict, letterhead: bytes | None = None, letterhead_filename: str = "") -> bytes:
    """Create an A4 embassy-style package inspired by, but not copied from, reference letters."""
    output = pymupdf.open()
    stationery_pdf = None
    stationery_image = None
    full_page_stationery_image = False
    one_page = bool(pkg.get("force_one_page"))
    if letterhead:
        if letterhead_filename.lower().endswith(".pdf") or letterhead[:4] == b"%PDF":
            stationery_pdf = pymupdf.open(stream=letterhead, filetype="pdf")
        else:
            stationery_image = letterhead
            try:
                image_info = pymupdf.Pixmap(letterhead)
                full_page_stationery_image = image_info.height >= image_info.width * 1.1
            except Exception:
                # Most uploaded stationery images are portrait pages. Falling back
                # to full-page placement avoids shrinking them into a header strip.
                full_page_stationery_image = True

    # Keep body text inside the clear writing area of full-page stationery.
    # The larger footer reserve prevents contact details and decorative artwork
    # from being covered on multi-page letters.
    top = LETTERHEAD_TOP if letterhead else 64
    bottom = LETTERHEAD_BOTTOM if letterhead else 55
    left = LETTERHEAD_SIDE if letterhead else 58.0
    right = A4.width - left
    content_width = right - left
    page = None
    y = 0.0
    page_number = 0

    def new_page():
        nonlocal page, y, page_number
        page = output.new_page(width=A4.width, height=A4.height)
        page_number += 1
        if stationery_pdf:
            page.show_pdf_page(page.rect, stationery_pdf, 0, overlay=False)
        elif stationery_image:
            if full_page_stationery_image:
                page.insert_image(page.rect, stream=stationery_image, keep_proportion=False, overlay=False)
            else:
                page.insert_image(
                    pymupdf.Rect(42, 12, A4.width - 42, 160),
                    stream=stationery_image,
                    keep_proportion=True,
                    overlay=False,
                )
        y = float(top)

    def ensure(height: float):
        if y + height > A4.height - bottom:
            new_page()

    def heading(text: str, force_page: bool = False):
        nonlocal y
        if force_page and not one_page and y > top + 8:
            new_page()
        y += 8 if one_page else 13
        heading_size = 11.5 if one_page else 15
        ensure(25 if one_page else 38)
        title = _plain(text).upper()
        title_width = min(pymupdf.get_text_length(title, fontname="Times-Bold", fontsize=heading_size), content_width)
        line_left = (A4.width - title_width) / 2
        page.insert_text((line_left, y + heading_size), title, fontname="Times-Bold", fontsize=heading_size, color=ACCENT)
        page.draw_line((line_left, y + heading_size + 3), (line_left + title_width, y + heading_size + 3), color=ACCENT, width=0.8)
        y += 22 if one_page else 34

    def paragraph(text: str, after: float = 10, size: float = 10.5):
        nonlocal y
        if one_page and size >= 10:
            size, after = 8.6, min(after, 4)
        clean = _plain(text)
        if not clean:
            y += after
            return
        line_height = size * 1.38
        estimated = len(_wrapped_lines(clean, content_width, "Times-Roman", size)) * line_height + 2
        ensure(estimated + after)
        rect = pymupdf.Rect(left, y, right, y + estimated + 4)
        page.insert_textbox(
            rect, clean, fontname="Times-Roman", fontsize=size,
            lineheight=1.38, color=BLACK, align=pymupdf.TEXT_ALIGN_JUSTIFY,
        )
        y += estimated + after

    def short_line(text: str, bold: bool = False, after: float = 3):
        nonlocal y
        font = "Times-Bold" if bold else "Times-Roman"
        line_size = 9 if one_page else 10.5
        line_height = 13 if one_page else 17
        ensure(line_height + after)
        page.insert_text((left, y + line_size + 1), _plain(text), fontname=font, fontsize=line_size, color=BLACK)
        y += line_height + after

    def itinerary_table(rows: list[dict]):
        nonlocal y
        widths = [72.0, 88.0, content_width - 160.0]
        headers = ["Date", "Location", "Planned activities"]

        def draw_row(values, is_header=False):
            nonlocal y
            font = "Times-Bold" if is_header else "Times-Roman"
            size = 9.0 if is_header else 8.8
            wrapped = [_wrapped_lines(value, width - 10, font, size) for value, width in zip(values, widths)]
            row_height = max(24, max(len(lines) for lines in wrapped) * 12 + 8)
            if y + row_height > A4.height - bottom:
                new_page()
                heading("Travel itinerary")
                draw_row(headers, True)
            x = left
            fill = (0.90, 0.92, 0.95) if is_header else None
            for lines, width in zip(wrapped, widths):
                cell = pymupdf.Rect(x, y, x + width, y + row_height)
                page.draw_rect(cell, color=(0.45, 0.45, 0.45), fill=fill, width=0.6)
                line_y = cell.y0 + 5 + size
                for line in lines:
                    page.insert_text((cell.x0 + 5, line_y), line, fontname=font, fontsize=size, color=BLACK)
                    line_y += 12
                x += width
            y += row_height

        draw_row(headers, True)
        for row in rows:
            draw_row([_plain(row.get("date")), _plain(row.get("location")), _plain(row.get("activity"))])
        y += 10

    new_page()
    rules = load_rules()
    short_line("To")
    for line in _addressee_lines(pkg, rules["addressee"]):
        short_line(line, after=0)
    y += 8
    short_line(f"Subject: {pkg.get('subject', '')}", bold=True, after=9)
    short_line("Dear Visa Officer,", after=8)
    edited_preview = str(pkg.get("_edited_preview_text", "")).strip()
    if edited_preview:
        for block in (part.strip() for part in re.split(r"\n\s*\n", edited_preview)):
            if not block:
                continue
            if re.fullmatch(r"\*\*[^*]+\*\*", block):
                heading(block)
            else:
                paragraph(block)
    else:
        for text in pkg.get("cover_letter", []):
            paragraph(text)

    if not edited_preview and pkg.get("purpose_of_visit"):
        heading("Purpose of visit", force_page=not one_page)
        for text in pkg["purpose_of_visit"]:
            paragraph(text)

    if not edited_preview and pkg.get("itinerary"):
        heading("Travel itinerary", force_page=not one_page)
        itinerary_table(pkg["itinerary"])

    for index, section in enumerate(pkg.get("sections", []) if not edited_preview else []):
        # Start major supporting material cleanly, then allow related short sections to share a page.
        heading(section.get("heading", "Supporting information"), force_page=not one_page and (index == 0 or y > A4.height * 0.62))
        for text in section.get("paragraphs", []):
            paragraph(text)

    if not edited_preview and pkg.get("attached_documents"):
        heading("Attached documents supporting this application", force_page=not one_page)
        if one_page:
            paragraph("; ".join(_plain(item) for item in pkg["attached_documents"]), after=3, size=8.3)
        else:
            for item in pkg["attached_documents"]:
                paragraph(f"- {_plain(item)}", after=3, size=10)
    if not edited_preview:
        for text in pkg.get("closing", []):
            paragraph(text, after=6)

    # Page numbers are omitted on company stationery so they never cover its
    # footer artwork or contact details.
    if not letterhead:
        for number, pdf_page in enumerate(output, 1):
            pdf_page.insert_textbox(
                pymupdf.Rect(A4.width - 95, A4.height - 34, A4.width - 48, A4.height - 18),
                f"Page {number}", fontname="Helvetica", fontsize=8, color=(0.4, 0.4, 0.4),
                align=pymupdf.TEXT_ALIGN_RIGHT,
            )

    if stationery_pdf:
        stationery_pdf.close()
    result = output.tobytes(garbage=4, deflate=True)
    output.close()
    return result


def _word_runs(paragraph, value) -> None:
    clean_value = re.sub(r"(?i)^suggested tourism visit:\s*", "", str(value or "")).strip()
    for index, chunk in enumerate(clean_value.split("**")):
        if chunk:
            run = paragraph.add_run(chunk)
            run.bold = index % 2 == 1


def _word_heading(doc: Document, title: str, style: dict, page_break: bool = False, compact: bool = False) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.page_break_before = page_break
    paragraph.alignment = style["align"]
    paragraph.paragraph_format.space_before = Pt(7 if compact else 14)
    paragraph.paragraph_format.space_after = Pt(5 if compact else 9)
    run = paragraph.add_run(_plain(title).upper())
    run.bold = True
    run.underline = True
    run.font.name = style["font"]
    run.font.size = Pt(11.5 if compact else 15)
    run.font.color.rgb = RGBColor.from_string(style["heading"])
    paragraph.paragraph_format.keep_with_next = True


def _word_body(doc: Document, paragraphs: list, line_spacing: float = 1.08, compact: bool = False) -> None:
    for value in paragraphs:
        if not _plain(value):
            continue
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.space_after = Pt(2 if compact else 5)
        paragraph.paragraph_format.line_spacing = 1.05 if compact else max(1.15, line_spacing)
        _word_runs(paragraph, value)


def _set_cell_shading(cell, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    properties.append(shading)


def _letterhead_page_image(letterhead: bytes, filename: str) -> bytes:
    """Return the full stationery page as an image suitable for a Word background."""
    if filename.lower().endswith(".pdf") or letterhead[:4] == b"%PDF":
        source = pymupdf.open(stream=letterhead, filetype="pdf")
        try:
            page = source[0]
            return page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).tobytes("png")
        finally:
            source.close()
    return letterhead


def _letterhead_bands(letterhead: bytes, filename: str) -> tuple[bytes, bytes]:
    """Crop printable header/footer bands for stable repetition in Microsoft Word."""
    page_image = _letterhead_page_image(letterhead, filename)
    source = Image.open(BytesIO(page_image)).convert("RGB")
    top_px = max(1, round(source.height * LETTERHEAD_TOP / A4.height))
    bottom_px = max(1, round(source.height * LETTERHEAD_BOTTOM / A4.height))
    top = source.crop((0, 0, source.width, top_px))
    bottom = source.crop((0, source.height - bottom_px, source.width, source.height))
    top_buffer, bottom_buffer = BytesIO(), BytesIO()
    top.save(top_buffer, format="PNG")
    bottom.save(bottom_buffer, format="PNG")
    return top_buffer.getvalue(), bottom_buffer.getvalue()


def package_docx(pkg: dict, letterhead: bytes | None = None, letterhead_filename: str = "") -> bytes:
    """Create an editable Word version using the same professional section hierarchy."""
    rules = load_rules()
    style = _document_style(pkg)
    one_page = bool(pkg.get("force_one_page"))
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = section.right_margin = Inches(LETTERHEAD_SIDE / 72 if letterhead else 0.82)
    # Keep body copy inside the clear writing area of a full-page letterhead.
    # The stationery itself remains behind the text and is repeated on every page.
    section.top_margin = Inches(LETTERHEAD_TOP / 72) if letterhead else Inches(0.8)
    section.bottom_margin = Inches(LETTERHEAD_BOTTOM / 72) if letterhead else Inches(0.75)

    normal = doc.styles["Normal"]
    normal.font.name = style["font"]
    normal.font.size = Pt(8.6 if one_page else 10.5)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.space_after = Pt(3 if one_page else 8)

    if letterhead:
        top_band, bottom_band = _letterhead_bands(letterhead, letterhead_filename)
        section.header_distance = Inches(0)
        section.footer_distance = Inches(0)
        header = section.header
        header.is_linked_to_previous = False
        header_paragraph = header.paragraphs[0]
        header_paragraph.paragraph_format.left_indent = -section.left_margin
        header_paragraph.paragraph_format.space_before = Pt(0)
        header_paragraph.paragraph_format.space_after = Pt(0)
        header_paragraph.add_run().add_picture(
            BytesIO(top_band), width=section.page_width, height=Inches(LETTERHEAD_TOP / 72)
        )
        footer = section.footer
        footer.is_linked_to_previous = False
        footer_paragraph = footer.paragraphs[0]
        footer_paragraph.paragraph_format.left_indent = -section.left_margin
        footer_paragraph.paragraph_format.space_before = Pt(0)
        footer_paragraph.paragraph_format.space_after = Pt(0)
        footer_paragraph.add_run().add_picture(
            BytesIO(bottom_band), width=section.page_width, height=Inches(LETTERHEAD_BOTTOM / 72)
        )
    to_paragraph = doc.add_paragraph("To")
    to_paragraph.paragraph_format.space_after = Pt(0)
    for line in _addressee_lines(pkg, rules["addressee"]):
        paragraph = doc.add_paragraph(line)
        paragraph.paragraph_format.space_after = Pt(0)
    subject = doc.add_paragraph()
    subject.paragraph_format.space_before = Pt(5)
    subject.paragraph_format.space_after = Pt(5)
    subject.add_run("Subject: ").bold = True
    _word_runs(subject, pkg.get("subject", ""))
    salutation = doc.add_paragraph("Dear Visa Officer,")
    salutation.paragraph_format.space_after = Pt(5 if not one_page else 3)
    edited_preview = str(pkg.get("_edited_preview_text", "")).strip()
    if edited_preview:
        editable_paragraphs = [part.strip() for part in re.split(r"\n\s*\n", edited_preview) if part.strip()]
        _word_body(doc, editable_paragraphs, style["line"], one_page)
    else:
        _word_body(doc, pkg.get("cover_letter", []), style["line"], one_page)

    if not edited_preview and pkg.get("purpose_of_visit"):
        _word_heading(doc, "Purpose of visit", style, page_break=False, compact=one_page)
        _word_body(doc, pkg["purpose_of_visit"], style["line"], one_page)

    if not edited_preview and pkg.get("itinerary"):
        _word_heading(doc, "Travel itinerary", style, page_break=False, compact=one_page)
        table = doc.add_table(rows=1, cols=3)
        table.autofit = False
        table.style = "Table Grid"
        widths = (Inches(1.1), Inches(1.25), Inches(4.25))
        for cell, label, width in zip(table.rows[0].cells, ("Date", "Location", "Planned activities"), widths):
            cell.width = width
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            _set_cell_shading(cell, style["table"])
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.add_run(label).bold = True
        table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
        for row_data in pkg["itinerary"]:
            cells = table.add_row().cells
            values = (row_data.get("date", ""), row_data.get("location", ""), row_data.get("activity", ""))
            for cell, value, width in zip(cells, values, widths):
                cell.width = width
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if cell is not cells[2] else WD_ALIGN_PARAGRAPH.LEFT
                _word_runs(paragraph, value)

    for index, supporting in enumerate(pkg.get("sections", []) if not edited_preview else []):
        _word_heading(doc, supporting.get("heading", "Supporting information"), style, page_break=False, compact=one_page)
        _word_body(doc, supporting.get("paragraphs", []), style["line"], one_page)

    if not edited_preview and pkg.get("attached_documents"):
        _word_heading(doc, "Attached documents supporting this application", style, page_break=False, compact=one_page)
        if one_page:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(3)
            paragraph.paragraph_format.line_spacing = 1.05
            _word_runs(paragraph, "; ".join(str(item) for item in pkg["attached_documents"]))
        else:
            for item in pkg["attached_documents"]:
                paragraph = doc.add_paragraph(style="List Bullet")
                _word_runs(paragraph, item)
    if not edited_preview:
        _word_body(doc, pkg.get("closing", []), style["line"], one_page)

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
