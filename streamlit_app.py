"""Modern Streamlit UI for document-led visa cover letter generation."""
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

from app.export import package_docx
from app.generate import check_package, generate_from_documents, package_text
from app import library

load_dotenv(Path(__file__).resolve().parent / ".env")

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
    header[data-testid="stHeader"] { background:rgba(248,251,255,.96) !important; color:#18324f !important; }
    .block-container { max-width:900px; padding-top:1.4rem; padding-bottom:3rem; }
    h1, h2, h3, p, label, .stMarkdown, [data-testid="stWidgetLabel"] { color:#18324f !important; }
    input, textarea, [data-baseweb="select"] > div { color:#18324f !important; background:#ffffff !important; }
    input::placeholder, textarea::placeholder { color:#8393a7 !important; }
    .simple-head { position:relative; overflow:hidden; background:linear-gradient(120deg,#135f9f,#167fb3 68%,#26a6ad); padding:22px 26px;
        margin-bottom:18px; border:1px solid #3ca4c5; border-radius:18px; box-shadow:0 15px 34px rgba(25,94,143,.24); }
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
        background:#f2f8fe !important; color:#18324f !important; }
    [data-testid="stFileUploaderDropzone"] * { color:#18324f !important; }
    [data-testid="stFileUploaderDropzone"] button { background:#ffffff !important; color:#1769c2 !important;
        border:1px solid #5f9ed4 !important; }
    [data-testid="stFileUploaderDropzone"] button * { color:#1769c2 !important; }
    [data-testid="stFileUploaderDropzone"]::after { content:"CNIC, Passport, Bank Statement, FRC/MRC, Job/Business Docs, Letterhead etc.";
        color:#385774; font-size:.84rem; line-height:1.35; margin-left:14px; }
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
    .result-card { background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:18px 20px;
        box-shadow:0 10px 28px rgba(0,0,0,.22); height:100%; }
    .result-label { color:var(--muted); font-size:.73rem; text-transform:uppercase; letter-spacing:.1em; font-weight:700; }
    .result-value { color:var(--navy); font-size:1rem; font-weight:750; margin-top:6px; line-height:1.4; }
    .result-detail { color:var(--muted); font-size:.82rem; margin-top:6px; line-height:1.5; }
    [data-testid="stTabs"] button { color:#536b84 !important; }
    [data-testid="stTabs"] button[aria-selected="true"] { color:#18324f !important; }
    [data-testid="stAlert"] { border-width:1px !important; }
    hr { border-color:#2b3a50 !important; }
    div[data-testid="stTextArea"] textarea { font-family:Georgia,'Times New Roman',serif; line-height:1.55; }
    @media(max-width:760px) { .block-container { padding:1rem; } }
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
    label_visibility="collapsed",
)

c1, c2 = st.columns(2)
destination_country = c1.selectbox("Destination country", ["Canada", "United Kingdom", "Australia", "New Zealand"])
destination_city = c2.text_input("City / cities", placeholder="e.g. Toronto, London, Sydney or Auckland")
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

travel_start = travel_dates[0] if isinstance(travel_dates, (tuple, list)) and len(travel_dates) > 0 else None
travel_end = travel_dates[1] if isinstance(travel_dates, (tuple, list)) and len(travel_dates) > 1 else None

st.write("")
generate = st.button(
    "Generate Cover Letter",
    type="primary",
    use_container_width=True,
    disabled=not documents,
)

if generate:
    try:
        uploaded = [(f.name, f.getvalue()) for f in documents]
        progress = st.progress(10, text="Preparing uploaded documents...")
        progress.progress(35, text="Analysing applicant profile and supporting evidence...")
        with st.spinner("Creating the cover letter package..."):
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
            progress.progress(85, text="Formatting the final document...")
            st.session_state.generated_package = package
            detected_name = package.get("letterhead_document", "")
            uploaded_map = dict(uploaded)
            st.session_state.output_settings = {
                "letterhead": uploaded_map.get(detected_name),
                "letterhead_filename": detected_name if detected_name in uploaded_map else "",
            }
            st.session_state.generated_visa_type = visa_type
            progress.progress(100, text="Cover letter ready")
        progress.empty()
    except Exception as exc:
        st.error(f"Cover letter generate nahi ho saka: {exc}")

package = st.session_state.get("generated_package")
if package:
    settings = st.session_state.get("output_settings", {})
    active_visa_type = st.session_state.get("generated_visa_type", visa_type)
    st.divider()
    st.subheader("Generated package")
    missing_count = len(package.get("missing", []))
    if not missing_count:
        st.success("Ready for review and download.")

    if package.get("generation_mode") == "local_fallback":
        st.info("Safe local document analysis was used. Review missing details before submission.")
    for issue in check_package(package, active_visa_type):
        st.error(issue)

    download_tab, preview_tab = st.tabs(["Download", "Document preview"])
    with download_tab:
        st.markdown("#### Your document is ready")
        st.caption("Open it in Microsoft Word to review, update or finalise the letter.")
        st.download_button(
            "Download Word Document",
            data=package_docx(package, **settings),
            file_name="visa_cover_letter_package.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    with preview_tab:
        st.text_area("Generated text", package_text(package), height=560, label_visibility="collapsed")

    st.divider()
    st.markdown("### Help the software improve")
    st.caption("Only ratings of 4 or 5 are saved as future style examples. Lower-rated letters are never learned.")
    rating = st.select_slider(
        "Rate this generated letter",
        options=[1, 2, 3, 4, 5],
        value=3,
        format_func=lambda value: f"{value} star{'s' if value != 1 else ''}",
    )
    if st.button("Submit rating", use_container_width=True):
        feedback_key = library.feedback_key(package_text(package), destination_country, active_visa_type)
        if rating >= 4:
            saved = library.add_letter(
                package_text(package),
                active_visa_type,
                country=destination_country,
                source="self_learning",
                rating=rating,
            )
            if saved:
                st.success("High-rated letter learned. Future letters can use its approved structure and style.")
            else:
                st.info("This approved letter was already learned earlier.")
        else:
            library.record_feedback(feedback_key, rating, learned=False)
            st.info("Rating saved, but this letter was not added to learning examples.")
