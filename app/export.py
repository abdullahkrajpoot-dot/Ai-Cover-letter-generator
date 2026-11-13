"""Polished direct-PDF export with automatic company-letterhead support."""
import hashlib
import json
import re
from copy import deepcopy
from io import BytesIO

import pymupdf
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from .generate import load_rules

A4 = pymupdf.paper_rect("a4")
BLACK = (0.08, 0.08, 0.08)
ACCENT = (0.20, 0.25, 0.32)


def _plain(value) -> str:
    text = re.sub(r"\*\*", "", str(value or "")).strip()
    return re.sub(r"(?i)^suggested tourism visit:\s*", "", text)


def _document_style(pkg: dict) -> dict:
    """Choose a stable professional style variant for each generated package."""
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
    if letterhead:
        if letterhead_filename.lower().endswith(".pdf") or letterhead[:4] == b"%PDF":
            stationery_pdf = pymupdf.open(stream=letterhead, filetype="pdf")
        else:
            stationery_image = letterhead

    # Dedicated stationery reserves the same physical print area on every page.
    top = 184 if letterhead else 64
    bottom = 86 if letterhead else 55
    left, right = 58.0, A4.width - 58.0
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
            page.insert_image(pymupdf.Rect(42, 10, A4.width - 42, 150), stream=stationery_image, keep_proportion=True, overlay=False)
        y = float(top)

    def ensure(height: float):
        if y + height > A4.height - bottom:
            new_page()

    def heading(text: str, force_page: bool = False):
        nonlocal y
        if force_page and y > top + 8:
            new_page()
        ensure(38)
        title = _plain(text).upper()
        title_width = min(pymupdf.get_text_length(title, fontname="Times-Bold", fontsize=15), content_width)
        line_left = (A4.width - title_width) / 2
        page.insert_text((line_left, y + 16), title, fontname="Times-Bold", fontsize=15, color=ACCENT)
        page.draw_line((line_left, y + 20), (line_left + title_width, y + 20), color=ACCENT, width=0.8)
        y += 34

    def paragraph(text: str, after: float = 10, size: float = 10.5):
        nonlocal y
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
        ensure(17 + after)
        page.insert_text((left, y + 11), _plain(text), fontname=font, fontsize=10.5, color=BLACK)
        y += 17 + after

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
    for line in (pkg.get("addressee") or rules["addressee"]):
        short_line(line, after=0)
    y += 8
    short_line(f"Subject: {pkg.get('subject', '')}", bold=True, after=9)
    short_line("Dear Visa Officer,", after=8)
    for text in pkg.get("cover_letter", []):
        paragraph(text)

    if pkg.get("purpose_of_visit"):
        heading("Purpose of visit", force_page=True)
        for text in pkg["purpose_of_visit"]:
            paragraph(text)

    if pkg.get("itinerary"):
        heading("Travel itinerary", force_page=True)
        itinerary_table(pkg["itinerary"])

    for index, section in enumerate(pkg.get("sections", [])):
        # Start major supporting material cleanly, then allow related short sections to share a page.
        heading(section.get("heading", "Supporting information"), force_page=index == 0 or y > A4.height * 0.62)
        for text in section.get("paragraphs", []):
            paragraph(text)

    if pkg.get("attached_documents"):
        heading("Attached documents supporting this application", force_page=True)
        for item in pkg["attached_documents"]:
            paragraph(f"- {_plain(item)}", after=3, size=10)
    for text in pkg.get("closing", []):
        paragraph(text, after=6)

    # A subtle page number differentiates the layout from the reference while improving navigation.
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


def _word_heading(doc: Document, title: str, style: dict, page_break: bool = False) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.page_break_before = page_break
    paragraph.alignment = style["align"]
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(10)
    run = paragraph.add_run(_plain(title).upper())
    run.bold = True
    run.underline = True
    run.font.name = style["font"]
    run.font.size = Pt(15)
    run.font.color.rgb = RGBColor.from_string(style["heading"])
    paragraph.paragraph_format.keep_with_next = True


def _word_body(doc: Document, paragraphs: list, line_spacing: float = 1.08) -> None:
    for value in paragraphs:
        if not _plain(value):
            continue
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.space_after = Pt(5)
        paragraph.paragraph_format.line_spacing = line_spacing
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


def _place_picture_behind_text(inline_shape, section) -> None:
    """Convert an inline picture to a full-page floating image behind document text."""
    inline = inline_shape._inline
    anchor = OxmlElement("wp:anchor")
    for name, value in (
        ("distT", "0"), ("distB", "0"), ("distL", "0"), ("distR", "0"),
        ("simplePos", "0"), ("relativeHeight", "0"), ("behindDoc", "1"),
        ("locked", "0"), ("layoutInCell", "1"), ("allowOverlap", "1"),
    ):
        anchor.set(name, value)

    simple_pos = OxmlElement("wp:simplePos")
    simple_pos.set("x", "0")
    simple_pos.set("y", "0")
    anchor.append(simple_pos)

    position_h = OxmlElement("wp:positionH")
    position_h.set("relativeFrom", "page")
    offset_h = OxmlElement("wp:posOffset")
    offset_h.text = "0"
    position_h.append(offset_h)
    anchor.append(position_h)

    position_v = OxmlElement("wp:positionV")
    position_v.set("relativeFrom", "page")
    offset_v = OxmlElement("wp:posOffset")
    offset_v.text = "0"
    position_v.append(offset_v)
    anchor.append(position_v)

    extent = OxmlElement("wp:extent")
    extent.set("cx", str(section.page_width))
    extent.set("cy", str(section.page_height))
    anchor.append(extent)
    effect = OxmlElement("wp:effectExtent")
    for edge in ("l", "t", "r", "b"):
        effect.set(edge, "0")
    anchor.append(effect)
    anchor.append(OxmlElement("wp:wrapNone"))

    for tag in ("wp:docPr", "wp:cNvGraphicFramePr", "a:graphic"):
        child = inline.find(qn(tag))
        if child is not None:
            anchor.append(deepcopy(child))
    inline.getparent().replace(inline, anchor)


def package_docx(pkg: dict, letterhead: bytes | None = None, letterhead_filename: str = "") -> bytes:
    """Create an editable Word version using the same professional section hierarchy."""
    rules = load_rules()
    style = _document_style(pkg)
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = section.right_margin = Inches(0.82)
    # Keep body copy inside the clear writing area of a full-page letterhead.
    # The stationery itself remains behind the text and is repeated on every page.
    section.top_margin = Inches(2.5) if letterhead else Inches(0.8)
    section.bottom_margin = Inches(1.25) if letterhead else Inches(0.75)

    normal = doc.styles["Normal"]
    normal.font.name = style["font"]
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.space_after = Pt(8)

    if letterhead:
        stationery = _letterhead_page_image(letterhead, letterhead_filename)
        header = section.header
        header.is_linked_to_previous = False
        header.distance = Inches(0)
        paragraph = header.paragraphs[0]
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        shape = paragraph.add_run().add_picture(
            BytesIO(stationery), width=section.page_width, height=section.page_height
        )
        _place_picture_behind_text(shape, section)
    doc.add_paragraph("To")
    for line in (pkg.get("addressee") or rules["addressee"]):
        paragraph = doc.add_paragraph(line)
        paragraph.paragraph_format.space_after = Pt(0)
    subject = doc.add_paragraph()
    subject.add_run("Subject: ").bold = True
    _word_runs(subject, pkg.get("subject", ""))
    doc.add_paragraph("Dear Visa Officer,")
    edited_preview = str(pkg.get("_edited_preview_text", "")).strip()
    if edited_preview:
        editable_paragraphs = [part.strip() for part in re.split(r"\n\s*\n", edited_preview) if part.strip()]
        _word_body(doc, editable_paragraphs, style["line"])
    else:
        _word_body(doc, pkg.get("cover_letter", []), style["line"])

    if not edited_preview and pkg.get("purpose_of_visit"):
        _word_heading(doc, "Purpose of visit", style, page_break=False)
        _word_body(doc, pkg["purpose_of_visit"], style["line"])

    if not edited_preview and pkg.get("itinerary"):
        _word_heading(doc, "Travel itinerary", style, page_break=False)
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
        _word_heading(doc, supporting.get("heading", "Supporting information"), style, page_break=False)
        _word_body(doc, supporting.get("paragraphs", []), style["line"])

    if not edited_preview and pkg.get("attached_documents"):
        _word_heading(doc, "Attached documents supporting this application", style, page_break=False)
        for item in pkg["attached_documents"]:
            paragraph = doc.add_paragraph(style="List Bullet")
            _word_runs(paragraph, item)
    if not edited_preview:
        _word_body(doc, pkg.get("closing", []), style["line"])

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
