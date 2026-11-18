"""Modern Streamlit UI for document-led visa cover letter generation."""
from pathlib import Path
import html
import re
import streamlit as st
import pycountry
from dotenv import load_dotenv

from app.export import package_docx, package_pdf
from app.editable_preview import word_preview_editor
from app.generate import generate_from_documents, package_text
from app.llm import complete
from app import library

load_dotenv(Path(__file__).resolve().parent / ".env")

COUNTRY_NAMES = sorted({country.name for country in pycountry.countries})


def package_preview_markdown(pkg: dict) -> str:
    """Build a readable Markdown preview with clearly bold section headings."""
    parts = [str(text).strip() for text in pkg.get("cover_letter", []) if str(text).strip()]

    purpose = [str(text).strip() for text in pkg.get("purpose_of_visit", []) if str(text).strip()]
    if purpose:
        parts.extend(["**PURPOSE OF VISIT**", *purpose])

    itinerary = pkg.get("itinerary", [])
    if itinerary:
        parts.append("**TRAVEL ITINERARY**")
        parts.extend(
            f"- **{row.get('date', '')}** — {row.get('location', '')}: {row.get('activity', '')}"
            for row in itinerary
        )

    for section in pkg.get("sections", []):
        heading = str(section.get("heading", "")).strip()
        if heading:
            parts.append(f"**{heading}**")
        parts.extend(
            str(text).strip()
            for text in section.get("paragraphs", [])
            if str(text).strip()
        )

    documents = pkg.get("attached_documents", [])
    if documents:
        parts.append("**ATTACHED DOCUMENTS**")
        parts.extend(f"- {item}" for item in documents)

    parts.extend(str(text).strip() for text in pkg.get("closing", []) if str(text).strip())
    return "\n\n".join(parts)


def _preview_inline(value: str) -> str:
    """Escape user/document text while retaining the app's **bold** markers."""
    chunks = str(value or "").split("**")
    return "".join(
        f"<strong>{html.escape(chunk)}</strong>" if index % 2 else html.escape(chunk)
        for index, chunk in enumerate(chunks)
    )


def package_preview_html(pkg: dict, body_text: str) -> str:
    """Render a selectable Word-like page preview from the current editable body."""
    lines = []
    for line in pkg.get("addressee", []) or ["The Visa Officer"]:
        clean = re.sub(r"\s*,\s*", ", ", str(line).strip())
        if clean and clean.casefold() not in {"to", "to the visa officer"}:
            lines.append(clean)
    if not lines or lines[0].casefold() != "the visa officer":
        lines.insert(0, "The Visa Officer")
    address = "<br>".join(html.escape(line) for line in dict.fromkeys(lines))

    body_parts = []
    list_items = []
    for block in (part.strip() for part in re.split(r"\n\s*\n", body_text or "")):
        if not block:
            continue
        if block.startswith("- "):
            list_items.append(f"<li>{_preview_inline(block[2:])}</li>")
            continue
        if list_items:
            body_parts.append("<ul>" + "".join(list_items) + "</ul>")
            list_items = []
        heading = re.fullmatch(r"\*\*([^*]+)\*\*", block)
        if heading:
            body_parts.append(f"<h3>{html.escape(heading.group(1))}</h3>")
        else:
            body_parts.append(f"<p>{_preview_inline(block).replace(chr(10), '<br>')}</p>")
    if list_items:
        body_parts.append("<ul>" + "".join(list_items) + "</ul>")

    return (
        '<div class="word-preview">'
        f'<p class="word-address">To<br>{address}</p>'
        f'<p class="word-subject"><strong>Subject: {_preview_inline(pkg.get("subject", ""))}</strong></p>'
        '<p>Dear Visa Officer,</p>'
        + '<div class="editable-body">'
        + "".join(body_parts)
        + "</div></div>"
    )


def apply_prompt_revision() -> None:
    """Revise the editable letter from a plain-language user instruction."""
    instruction = st.session_state.get("revision_prompt", "").strip()
    current_letter = st.session_state.get("editable_preview", "").strip()
    if not instruction:
        st.session_state.revision_error = "Please describe the change you want."
        return
    prompt = f"""You are editing a professional visa cover letter.
Apply only the requested changes while preserving all verified facts, section order, and professional tone.
Do not invent dates, finances, employment, travel history, bookings, or personal details.
Keep existing Markdown bold headings written as **HEADING**.
Return the complete revised cover letter only, with no commentary or code fence.

REQUESTED CHANGE:
{instruction}

CURRENT COVER LETTER:
{current_letter}
"""
    try:
        revised = complete(prompt, max_tokens=6000).strip()
        revised = re.sub(r"^```(?:markdown|text)?\s*|\s*```$", "", revised, flags=re.I | re.S).strip()
        if not revised:
            raise ValueError("Provider returned an empty revision.")
        st.session_state.editable_preview = revised
        st.session_state.revision_prompt = ""
        st.session_state.revision_error = ""
    except Exception as exc:
        st.session_state.revision_error = f"Changes apply nahi ho sake: {exc}"

st.set_page_config(
    page_title="Visa Cover Letter Generator",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root { --navy:#18324f; --blue:#2478c7; --line:#c9d8e8; --panel:#ffffff; --muted:#61758d; }
    .stApp { background:
        radial-gradient(circle at 8% 12%,rgba(65,166,223,.18),transparent 28%),
        radial-gradient(circle at 92% 8%,rgba(80,102,210,.12),transparent 24%),
        linear-gradient(145deg,#edf6ff 0%,#fbfdff 48%,#eef7fb 100%); color:#18324f; }
    header[data-testid="stHeader"] { height:0 !important; min-height:0 !important; background:transparent !important; }
    [data-testid="stToolbar"], [data-testid="stHeaderActionElements"], [data-testid="stStatusWidget"],
    #MainMenu { display:none !important; visibility:hidden !important; }
    .block-container { width:80vw; max-width:80vw; margin-left:auto; margin-right:auto;
        padding-top:1.4rem; padding-bottom:3rem; }
    @media (max-width:900px) { .block-container { width:94vw; max-width:94vw; } }
    h1, h2, h3, p, label, .stMarkdown, [data-testid="stWidgetLabel"] { color:#18324f !important; }
    input, textarea, [data-baseweb="select"] > div { color:#18324f !important; background:#ffffff !important; }
    input::placeholder, textarea::placeholder { color:#8393a7 !important; }
    [data-testid="stTextInput"] [data-baseweb="input"] { border:1px solid #a9c8e2 !important;
        box-shadow:none !important; overflow:hidden; }
    [data-testid="stTextInput"] > div > div { border-color:#a9c8e2 !important;
        box-shadow:none !important; }
    [data-testid="stTextInput"] [data-baseweb="input"] > div,
    [data-testid="stTextInput"] [data-baseweb="base-input"],
    [data-testid="stTextInput"] input { border:0 !important; outline:0 !important; box-shadow:none !important; }
    [data-testid="stTextInput"] [data-baseweb="input"]:hover,
    [data-testid="stTextInput"] [data-baseweb="input"]:focus-within { border-color:#75a9d1 !important;
        box-shadow:0 0 0 1px rgba(36,120,199,.12) !important; }
    [data-testid="stTextInput"] div { border-top-color:#a9c8e2 !important;
        border-bottom-color:#a9c8e2 !important; }
    div[data-testid="stTextInput"] div[data-baseweb="input"] { border:none !important;
        box-shadow:0 0 0 1px #a9c8e2 !important; }
    [data-testid="stTextInputRootElement"] { background:#ffffff !important;
        border:1px solid #a9c8e2 !important; box-shadow:none !important; }
    [data-testid="stTextInputField"] { background:#ffffff !important; color:#18324f !important;
        -webkit-text-fill-color:#18324f !important; opacity:1 !important; }
    [data-testid="stTextInput"] input::placeholder,
    [data-testid="stTextInputField"]::placeholder {
        color:#8393a7 !important; -webkit-text-fill-color:#8393a7 !important;
        opacity:1 !important; font-family:Georgia,'Times New Roman',serif !important; }
    [data-testid="stTextInputField"]:-webkit-autofill,
    [data-testid="stTextInputField"]:-webkit-autofill:hover,
    [data-testid="stTextInputField"]:-webkit-autofill:focus { -webkit-text-fill-color:#18324f !important;
        -webkit-box-shadow:0 0 0 1000px #ffffff inset !important; box-shadow:0 0 0 1000px #ffffff inset !important; }
    [data-testid="stTextInputRootElement"]:hover,
    [data-testid="stTextInputRootElement"]:focus-within { background:#ffffff !important;
        border-color:#75a9d1 !important; box-shadow:0 0 0 1px rgba(36,120,199,.12) !important; }
    .simple-head { position:relative; overflow:hidden; display:flex; align-items:center; min-height:150px;
        background:linear-gradient(120deg,#135f9f,#167fb3 68%,#26a6ad); padding:30px 34px;
        margin-bottom:22px; border:1px solid #3ca4c5; border-radius:18px; box-shadow:0 15px 34px rgba(25,94,143,.24); }
    .simple-head::after { content:""; position:absolute; width:180px; height:180px; right:-45px; top:-95px;
        border-radius:50%; background:rgba(255,255,255,.12); }
    .simple-head h1 { position:relative; z-index:1; margin:0; color:#ffffff !important; font-size:1.8rem; }
    .country-row { display:flex; flex-wrap:wrap; gap:7px; margin-top:15px; }
    .country-chip { background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25); color:#ffffff !important;
        padding:5px 10px; border-radius:999px; font-size:.76rem; font-weight:650; }
    .section-label { display:inline-block; color:#145381; background:#dcefff; border:1px solid #aed3ef;
        border-left:5px solid #1687b6; border-radius:9px; padding:7px 12px; font-size:.94rem; font-weight:800; margin:4px 0 10px; }
    .section-copy { color:var(--muted); font-size:.88rem; margin-bottom:13px; }
    div[data-testid="stFileUploader"] { background:linear-gradient(180deg,#ffffff,#f5faff); border:1px solid #bcd7eb; border-radius:14px;
        padding:8px 12px 4px; box-shadow:0 10px 24px rgba(40,88,132,.11); }
    [data-testid="stFileUploaderDropzone"] { border:1.5px dashed #8caed2 !important; border-radius:14px;
        background:#f2f8fe !important; color:#18324f !important; align-items:center !important; }
    [data-testid="stFileUploaderDropzone"] * { color:#18324f !important; }
    [data-testid="stFileUploaderDropzone"] button { background:#ffffff !important; color:#1769c2 !important;
        border:1px solid #5f9ed4 !important; }
    [data-testid="stFileUploaderDropzone"] button * { color:#1769c2 !important; }
    [data-testid="stFileUploaderFile"] { background:#ffffff !important; border:1px solid #b9d2e6 !important;
        border-radius:10px !important; box-shadow:0 3px 10px rgba(40,88,132,.08) !important; }
    [data-testid="stFileUploaderFile"] * { color:#18324f !important; }
    [data-testid="stFileUploaderFileName"] { color:#18324f !important; font-weight:650 !important; }
    [data-testid="stFileUploaderFileSize"] { color:#58728b !important; }
    [data-testid="stFileUploaderFile"] svg { color:#1769c2 !important; fill:currentColor !important; }
    [data-testid="stFileChip"] { background:#ffffff !important; border:1px solid #b9d2e6 !important;
        border-radius:10px !important; box-shadow:0 3px 10px rgba(40,88,132,.08) !important; }
    [data-testid="stFileChip"] * { color:#18324f !important; }
    [data-testid="stFileChipName"] { color:#18324f !important; font-weight:650 !important; }
    [data-testid="stFileChip"] > div:nth-child(2) > div:last-child { color:#58728b !important; }
    [data-testid="stFileChip"] > div:first-child { background:#e8f3fd !important; color:#1769c2 !important; }
    .st-key-applicant_documents [data-testid="stFileUploaderDropzone"]::after {
        content:"CNIC, Passport, Bank Statement, FRC/MRC, Job/Business documents etc.";
        color:#385774; font-size:.84rem; line-height:1.35; margin-left:18px;
        align-self:center; display:flex; align-items:center; }
    [data-testid="stFileUploaderDropzoneInstructions"] { display:none !important; }
    [data-testid="stFileUploaderDropzone"] small { display:none !important; }
    [data-testid="stDateInput"] { color-scheme:light !important; }
    [data-testid="stDateInput"] div[data-baseweb="input"],
    [data-testid="stDateInput"] div[data-baseweb="input"] > div,
    [data-testid="stDateInput"] [role="group"] { background:#e8f3fd !important; border-color:#9cc5e8 !important; }
    [data-testid="stDateInput"] [data-baseweb="base-input"],
    [data-testid="stDateInput"] [data-baseweb="base-input"] > div,
    [data-testid="stDateInput"] [data-baseweb="input"] { background-color:#e8f3fd !important; color:#18324f !important; }
    [data-testid="stDateInput"] > div,
    [data-testid="stDateInput"] > div > div,
    [data-testid="stDateInput"] > div > div > div { background-color:#e8f3fd !important; color:#18324f !important; }
    [data-testid="stDateInput"] [role="group"] *,
    [data-testid="stDateInput"] [data-placeholder],
    [data-testid="stDateInput"] [aria-placeholder] { color:#365f82 !important; -webkit-text-fill-color:#365f82 !important;
        opacity:1 !important; }
    [data-testid="stDateInput"] input { color:#274f72 !important; -webkit-text-fill-color:#274f72 !important;
        background:#e8f3fd !important; text-transform:uppercase; opacity:1 !important; }
    [data-testid="stDateInput"] input::placeholder { color:#55738f !important; -webkit-text-fill-color:#55738f !important;
        text-transform:uppercase; opacity:1 !important; }
    [data-testid="stDateInput"] input::-webkit-datetime-edit,
    [data-testid="stDateInput"] input::-webkit-datetime-edit-fields-wrapper,
    [data-testid="stDateInput"] input::-webkit-datetime-edit-text,
    [data-testid="stDateInput"] input::-webkit-datetime-edit-year-field,
    [data-testid="stDateInput"] input::-webkit-datetime-edit-month-field,
    [data-testid="stDateInput"] input::-webkit-datetime-edit-day-field { color:#55738f !important; -webkit-text-fill-color:#55738f !important; }
    [data-testid="stDateInput"] svg { fill:#526a82 !important; }
    .st-key-destination_country [data-baseweb="select"] { position:relative; }
    .st-key-destination_country [data-baseweb="select"]::before {
        content:"\\1F50D"; position:absolute; left:13px; top:50%; transform:translateY(-50%);
        z-index:3; font-size:15px; line-height:1; pointer-events:none; }
    .st-key-destination_country [data-baseweb="select"] > div { padding-left:34px !important; }
    .section-label, [data-testid="stWidgetLabel"] p { text-transform:uppercase; letter-spacing:.025em; }
    div[data-testid="stExpander"] { background:linear-gradient(180deg,#ffffff,#f7fbff); border:1px solid #bdd7eb; border-radius:12px;
        box-shadow:0 6px 16px rgba(40,88,132,.07); }
    div[data-testid="stExpander"] details, div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] button { background:#ffffff !important; color:#18324f !important; }
    div[data-testid="stExpander"] summary *, div[data-testid="stExpander"] button * { color:#18324f !important; }
    .stButton > button, .stDownloadButton > button { border-radius:12px; min-height:48px; font-weight:700;
        background:linear-gradient(90deg,#1769c2,#168bb8) !important; color:#ffffff !important; border:1px solid #1777b8 !important;
        box-shadow:0 9px 20px rgba(23,105,194,.20); }
    .stButton > button *, .stDownloadButton > button * { color:#ffffff !important; }
    .stButton > button:disabled { background:#8b98a7 !important; border-color:#8b98a7 !important; color:#ffffff !important; }
    .stButton > button[kind="primary"] { background:#1769c2; color:#ffffff !important; border:0;
        box-shadow:0 9px 22px rgba(29,99,213,.22); }
    .stButton > button[kind="primary"] p { color:#ffffff !important; }
    div[data-testid="stExpander"] .stButton > button { background:linear-gradient(90deg,#1769c2,#168bb8) !important;
        color:#ffffff !important; border:1px solid #1777b8 !important; min-height:44px; }
    div[data-testid="stExpander"] .stButton > button *,
    div[data-testid="stExpander"] .stButton > button p { color:#ffffff !important;
        -webkit-text-fill-color:#ffffff !important; }
    .result-card { background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:18px 20px;
        box-shadow:0 10px 28px rgba(0,0,0,.22); height:100%; }
    .result-label { color:var(--muted); font-size:.73rem; text-transform:uppercase; letter-spacing:.1em; font-weight:700; }
    .result-value { color:var(--navy); font-size:1rem; font-weight:750; margin-top:6px; line-height:1.4; }
    .result-detail { color:var(--muted); font-size:.82rem; margin-top:6px; line-height:1.5; }
    [data-testid="stTabs"] button { color:#536b84 !important; }
    [data-testid="stTabs"] button[aria-selected="true"] { color:#18324f !important; }
    [data-testid="stAlert"] { background:#f7fbff !important; border:1px solid #9fc4e2 !important;
        border-left:5px solid #2478c7 !important; border-radius:12px !important;
        box-shadow:0 6px 16px rgba(40,88,132,.08); }
    [data-testid="stAlert"] > div { background:transparent !important; }
    [data-testid="stAlert"] p, [data-testid="stAlert"] span,
    [data-testid="stAlert"] div { color:#173653 !important; -webkit-text-fill-color:#173653 !important; }
    [data-testid="stFeedback"] { gap:7px !important; }
    [data-testid="stFeedback"] button { background:transparent !important; border:0 !important;
        box-shadow:none !important; min-height:38px !important; padding:3px !important; }
    [data-testid="stFeedbackButton"] svg { color:#cbd5e1 !important; fill:#cbd5e1 !important; width:27px !important; height:27px !important; }
    [data-testid="stFeedbackButtonActive"] svg { color:#f5b914 !important; fill:#f5b914 !important; width:27px !important; height:27px !important; }
    .rating-title { color:#6f86a0; font-size:1rem; margin-bottom:7px; }
    .rating-thanks { color:#6f86a0; font-size:1rem; margin-top:7px; }
    hr { border-color:#2b3a50 !important; }
    div[data-testid="stTextArea"] textarea { font-family:Georgia,'Times New Roman',serif; line-height:1.55; }
    .word-preview { width:100%; min-height:900px; box-sizing:border-box; background:#ffffff;
        border:1px solid #c8d0d9; box-shadow:0 8px 24px rgba(24,50,79,.12); padding:64px 74px;
        color:#111827 !important; font-family:'Times New Roman',Times,serif; font-size:16px;
        line-height:1.48; }
    .word-preview p { color:#111827 !important; margin:0 0 15px; text-align:justify; }
    .word-preview .word-address { text-align:left; margin-bottom:18px; }
    .word-preview .word-subject { text-align:left; margin-bottom:18px; }
    .word-preview h3 { color:#111827 !important; font-family:'Times New Roman',Times,serif;
        font-size:20px; line-height:1.25; text-align:center; text-transform:uppercase;
        text-decoration:underline; margin:27px 0 14px; }
    .word-preview ul { color:#111827; margin:0 0 16px 24px; padding:0; }
    .word-preview li { margin:4px 0; }
    @media(max-width:760px) {
        .block-container { padding:1rem; }
    }
    @media(max-width:520px) {
        [data-testid="stFileUploaderDropzone"] { flex-wrap:wrap; gap:10px; }
        [data-testid="stFileUploaderDropzone"]::after { width:100%; margin:0; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="simple-head">
      <h1>Visa Cover Letter Generator</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-label">Cover letter details</div>', unsafe_allow_html=True)
documents = st.file_uploader(
    "Upload applicant documents",
    type=["pdf", "png", "jpg", "jpeg", "txt"],
    accept_multiple_files=True,
    key="applicant_documents",
    label_visibility="collapsed",
)

c1, c2 = st.columns(2)
destination_city = c1.text_input("City / cities", placeholder="e.g. Toronto, London, Sydney or Auckland")
destination_country = c2.selectbox(
    "Destination country",
    COUNTRY_NAMES,
    index=None,
    placeholder="Type to search any country",
    key="destination_country",
)
visa_type = "visit"
travel_dates = st.date_input(
    "Travel dates",
    value=(),
    help="Start date aur end date isi field mein select karein.",
)
with st.expander("Additional details", expanded=False):
    contact_c1, contact_c2 = st.columns(2)
    email_address = contact_c1.text_input("Email", placeholder="applicant@example.com")
    phone_number = contact_c2.text_input("Phone", placeholder="+92 300 1234567")
    trip_notes = st.text_area(
        "Other verified details",
        placeholder="Accommodation, bookings, employment/business details aur previous travel",
        height=72,
    )
    letterhead_file = st.file_uploader(
        "Optional letterhead",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=False,
        key="optional_letterhead",
        help="Upload a blank letterhead. The Word and PDF cover letter will be placed on it.",
    )

travel_start = travel_dates[0] if isinstance(travel_dates, (tuple, list)) and len(travel_dates) > 0 else None
travel_end = travel_dates[1] if isinstance(travel_dates, (tuple, list)) and len(travel_dates) > 1 else None
required_details_ready = bool(
    documents
    and destination_country
    and destination_city.strip()
    and travel_start
    and travel_end
)

progress_placeholder = st.empty()
st.write("")
generate_left, generate_col, generate_right = st.columns([1, 3, 1])
with generate_col:
    generate = st.button(
        "Generate Cover Letter",
        type="primary",
        use_container_width=True,
        disabled=not required_details_ready,
    )

if generate:
    try:
        uploaded = [(f.name, f.getvalue()) for f in documents]
        progress = progress_placeholder.progress(20, text="Creating the cover letter...")
        package = generate_from_documents(
            visa_type=visa_type,
            files=uploaded,
            notes=trip_notes,
            destination_country=destination_country,
            destination_city=destination_city,
            travel_start=travel_start.isoformat() if travel_start else "",
            travel_end=travel_end.isoformat() if travel_end else "",
            email_address=email_address,
            phone_number=phone_number,
        )
        progress.progress(85, text="Creating the cover letter...")
        st.session_state.generated_package = package
        st.session_state.editable_preview = package_preview_markdown(package)
        st.session_state.generated_destination_country = destination_country
        st.session_state.pop("letter_rating", None)
        st.session_state.pop("last_saved_rating_token", None)
        if letterhead_file is not None:
            package["letterhead_document"] = letterhead_file.name
            letterhead_bytes = letterhead_file.getvalue()
            letterhead_name = letterhead_file.name
        else:
            package["letterhead_document"] = ""
            letterhead_bytes = None
            letterhead_name = ""
        st.session_state.output_settings = {
            "letterhead": letterhead_bytes,
            "letterhead_filename": letterhead_name,
        }
        st.session_state.generated_visa_type = visa_type
        progress.progress(100, text="Creating the cover letter...")
        progress_placeholder.empty()
    except Exception as exc:
        progress_placeholder.empty()
        st.error(f"Cover letter generate nahi ho saka: {exc}")

package = st.session_state.get("generated_package")
if package:
    settings = st.session_state.get("output_settings", {})
    active_visa_type = st.session_state.get("generated_visa_type", visa_type)
    st.divider()
    st.subheader("Your Cover Letter is Ready")
    missing_count = len(package.get("missing", []))
    if not missing_count:
        st.success("Ready for review and download.")

    if "editable_preview" not in st.session_state:
        st.session_state.editable_preview = package_preview_markdown(package)
    package_for_download = dict(package)
    original_preview = package_preview_markdown(package)
    if st.session_state.editable_preview.strip() != original_preview.strip():
        package_for_download["_edited_preview_text"] = st.session_state.editable_preview

    with st.expander("AI Cover Letter Editor", expanded=False):
        st.text_area(
            "What would you like to change?",
            key="revision_prompt",
            placeholder=(
                "Example: First paragraph ki heading change kar do, purpose of visit short karo, "
                "ya financial section ko more professional bana do."
            ),
            height=95,
        )
        ai_button_col, ai_button_space = st.columns([1, 3])
        with ai_button_col:
            st.button(
                "Apply AI Changes",
                on_click=apply_prompt_revision,
                use_container_width=True,
                type="primary",
            )
        if st.session_state.get("revision_error"):
            st.error(st.session_state.revision_error)

    download_tab, preview_tab = st.tabs(["Download", "Document preview"])
    with download_tab:
        st.markdown("#### Your document is ready")
        word_col, pdf_col = st.columns(2)
        with word_col:
            st.download_button(
                "Download Word Document",
                data=package_docx(package_for_download, **settings),
                file_name="visa_cover_letter_package.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        with pdf_col:
            st.download_button(
                "Download PDF Document",
                data=package_pdf(package_for_download, **settings),
                file_name="visa_cover_letter_package.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
    with preview_tab:
        editor_value = word_preview_editor(
            package_preview_html(package, st.session_state.editable_preview),
            key=f"document_preview_editor_{package.get('document_style_seed', 'current')}",
        )
        if isinstance(editor_value, dict):
            edited_markdown = str(editor_value.get("markdown", "")).strip()
            edited_subject = str(editor_value.get("subject", "")).strip()
            edited_addressee = [str(line).strip() for line in editor_value.get("addressee", []) if str(line).strip()]
            if edited_markdown:
                st.session_state.editable_preview = edited_markdown
            if edited_subject:
                package["subject"] = edited_subject
            if edited_addressee:
                package["addressee"] = edited_addressee
            st.session_state.generated_package = package

    st.divider()
    rating_left, rating_col, rating_right = st.columns([1.3, 1, 1.3])
    with rating_col:
        st.markdown('<div class="rating-title">Rate this cover letter</div>', unsafe_allow_html=True)
        rating_index = st.feedback("stars", key="letter_rating")
        if rating_index is not None:
            rating = rating_index + 1
            rating_country = st.session_state.get("generated_destination_country", destination_country)
            feedback_key = library.feedback_key(package_text(package), rating_country, active_visa_type)
            rating_token = f"{feedback_key}:{rating}"
            if st.session_state.get("last_saved_rating_token") != rating_token:
                if rating >= 4:
                    library.add_letter(
                        package_text(package),
                        active_visa_type,
                        country=rating_country,
                        source="self_learning",
                        rating=rating,
                    )
                else:
                    library.record_feedback(feedback_key, rating, learned=False)
                st.session_state.last_saved_rating_token = rating_token
            st.markdown(f'<div class="rating-thanks">Thank you — {rating}/5</div>', unsafe_allow_html=True)
