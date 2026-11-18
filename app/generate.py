"""Rules + format example + similar approved letters + verified facts se 3-hisson ka cover letter package banana."""
import io
import json
import re
import secrets
import urllib.request
import pycountry
from babel.numbers import get_territory_currencies
from datetime import date, datetime, timedelta
from pathlib import Path

import pdfplumber
import yaml

from .library import retrieve
from .llm import complete

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "config" / "canada_rules.yaml"
FORMAT_EX = ROOT / "config" / "format_example_visit.txt"

COVER_LETTER_CATEGORIES = {
    "Master Category (Detailed: 7-8 Pages)": {
        "pages": "7-8",
        "detail": "maximum",
        "instructions": (
            "Create a comprehensive submission for a strong or complex profile. Include a full "
            "document index, day-by-day itinerary, detailed financial audit, asset and source-of-funds "
            "analysis, extensive travel history, strong home ties, and fully developed supporting sections."
        ),
    },
    "Pro Category (Medium: 3-4 Pages)": {
        "pages": "3-4",
        "detail": "medium",
        "instructions": (
            "Create a focused professional submission. Cover employment or business evidence, moderate "
            "assets and finances, essential itinerary details, home ties, travel history, and a standard "
            "supporting-document checklist without unnecessary repetition."
        ),
    },
    "Standard Category (Short: 1-2 Pages)": {
        "pages": "1-2",
        "detail": "concise",
        "instructions": (
            "Create a concise and direct submission. State the request, standard salary or business proof, "
            "financial capacity, brief trip details, home ties, and only the essential supporting documents."
        ),
    },
}

DEFAULT_CATEGORY = "Pro Category (Medium: 3-4 Pages)"


def category_config(category: str) -> dict:
    return COVER_LETTER_CATEGORIES.get(category, COVER_LETTER_CATEGORIES[DEFAULT_CATEGORY])


def load_rules():
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))


def build_prompt(
    visa_type: str,
    facts: dict,
    notes: str,
    examples: list,
    destination_country: str = "Canada",
    destination_city: str = "Toronto",
    embassy_name_location: str = "The Visa Officer, Embassy of Canada, Islamabad, Pakistan",
) -> str:
    r = load_rules()
    vt = r["visa_types"][visa_type]
    has_itinerary = visa_type != "study"
    country = (destination_country or r.get("country") or "Destination country").strip() or "Destination country"
    city = (destination_city or "Destination city").strip() or "Destination city"
    embassy = (embassy_name_location or f"The Visa Officer, Embassy of {country}, Islamabad, Pakistan").strip() or f"The Visa Officer, Embassy of {country}, Islamabad, Pakistan"
    ex = "\n\n".join(f"--- APPROVED EXAMPLE {i+1} ---\n{e['text']}" for i, e in enumerate(examples)) or "(none yet)"
    format_template = FORMAT_EX.read_text(encoding="utf-8")
    format_template = format_template.replace("Canada", country).replace("Toronto", city).replace("The Visa Officer", embassy)
    itinerary_example = f'[{{"date": "21 Jan 2027", "location": "{city}", "activity": "..."}}] one row per day' if has_itinerary else "[] (study permits have no itinerary)"
    return f"""Write a visa cover letter package for {country} - {vt['label']}.

DESTINATION COUNTRY: {country}
DESTINATION CITY / CITIES: {city}
EMBASSY / VISA OFFICE: {embassy}
LANGUAGE: {r['spelling']}
COVER LETTER LENGTH: {r['word_count']['min']}-{r['word_count']['max']} words in total
TONE: {r['tone']}

FORMAT TEMPLATE (follow this structure, style and level of detail exactly; bracketed parts are placeholders):
{format_template}

THE PACKAGE MUST COVER (only where facts are provided):
{chr(10).join('- ' + c for c in vt['must_cover'])}

STRICT RULES:
{chr(10).join('- ' + m for m in r['must_not'])}
- Put names, places and dates in **double asterisks** so they print in bold.
- Use {country} and {city} as the trip destination throughout the letter.
- Never copy facts from the examples, only their structure and tone.
- Do not mention or assume a fixed country, city, or embassy unless it is supplied in the inputs.

OTHER APPROVED LETTERS FOR STYLE:
{ex}

VERIFIED FACTS ABOUT THE APPLICANT (the only facts you may use):
{json.dumps(facts, ensure_ascii=False, indent=2)}

STAFF TRIP DETAILS / NOTES:
{notes or 'none'}

Return ONLY a JSON object, no other text:
{{
  "subject": "Application for ...",
  "cover_letter": ["paragraph 1", "paragraph 2", "paragraph 3"],
  "purpose_of_visit": ["paragraph 1", "paragraph 2"],
  "itinerary": {itinerary_example},
  "missing": ["every important fact that was not provided, e.g. 'travel dates'"]
}}"""


def generate_package(
    visa_type: str,
    facts: dict,
    notes: str = "",
    destination_country: str = "Canada",
    destination_city: str = "Toronto",
    embassy_name_location: str = "The Visa Officer, Embassy of Canada, Islamabad, Pakistan",
) -> dict:
    query = f"{visa_type} {destination_country} {destination_city} {notes} {json.dumps(facts, ensure_ascii=False)}"
    examples = retrieve(query, country=destination_country, visa_type=visa_type, k=3)
    prompt = build_prompt(
        visa_type,
        facts,
        notes,
        examples,
        destination_country=destination_country,
        destination_city=destination_city,
        embassy_name_location=embassy_name_location,
    )
    pkg = None
    for attempt in range(2):
        current_prompt = prompt
        if attempt:
            current_prompt += (
                "\n\nIMPORTANT RETRY: The previous response was invalid. Return one complete, "
                "valid JSON object only. Do not use markdown fences or add commentary."
            )
        text = complete(current_prompt, max_tokens=3000)
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            continue
        try:
            pkg = json.loads(match.group(0))
            break
        except json.JSONDecodeError:
            continue

    if pkg is None:
        raise ValueError("Model ne valid JSON nahi diya. Please dobara try karein.")
    pkg.setdefault("itinerary", [])
    pkg.setdefault("missing", [])
    return pkg


def generate_from_documents(
    visa_type: str,
    files: list,
    notes: str = "",
    destination_country: str = "Canada",
    destination_city: str = "Toronto",
    travel_start: str = "",
    travel_end: str = "",
    email_address: str = "",
    phone_number: str = "",
) -> dict:
    """Scan all documents and generate the package in one model request."""
    country_style = {
        "Canada": "Canadian English; address the responsible Canadian visa office",
        "United Kingdom": "British English; address UK Visas and Immigration / the Entry Clearance Officer",
        "Australia": "Australian English; address the Australian visa decision maker",
        "New Zealand": "New Zealand English; address Immigration New Zealand / the Visa Officer",
        "Turkey": "concise formal English; address the responsible Turkish embassy or consulate and keep the complete letter to one page",
    }.get(
        destination_country,
        f"professional international English appropriate for {destination_country}; address the relevant visa officer, embassy, consulate, or immigration authority",
    )
    learned = retrieve(
        f"{visa_type} {destination_country} {destination_city} {notes}",
        country=destination_country,
        visa_type=visa_type,
        k=2,
    )
    learned_examples = "\n\n".join(
        f"--- HIGH-RATED STYLE EXAMPLE {index + 1} ---\n{item['text']}"
        for index, item in enumerate(learned)
        if item.get("source") == "self_learning" and (item.get("rating") or 0) >= 4
    ) or "(No high-rated examples saved yet.)"
    prompt = f"""You are an expert visa application writer and document analyst.
Read every attached applicant document, cross-check the facts, and create a professional
{visa_type} visa application package for {destination_country} ({destination_city}).

COUNTRY-SPECIFIC WRITING:
- Use {country_style}.
- Preserve the same professional evidence-led structure for every destination while using
  the selected country's correct visa authority, terminology, spelling conventions, and currency.

HIGH-RATED APPROVED EXAMPLES FOR STYLE ONLY:
{learned_examples}
Never copy applicant facts from these examples. Use only their structure, clarity and tone.

AUTOMATIC PROFILE CLASSIFICATION (required before writing):
- Master Category (Detailed: 7-8 Pages): high net-worth, substantial bank funds, multiple/heavy
  assets, complex business interests, or an otherwise exceptionally strong profile.
- Pro Category (Medium: 3-4 Pages): established professional or business owner with solid
  employment/business evidence and moderate assets or bank funds.
- Standard Category (Short: 1-2 Pages): normal salaried employment or small business with
  basic financial/assets evidence and a straightforward profile.
Choose the category only from evidence in the uploaded documents. Then match its target page
length, section depth, financial analysis, document index, and itinerary detail.

CATEGORY OUTPUT DEPTH (do not return a thin or skeletal letter):
- Master: approximately 2,200-3,200 words, 8-12 developed sections, detailed financial/asset
  analysis, full document index, and day-by-day itinerary where dates are documented.
- Pro: approximately 1,200-1,800 words, 6-9 developed sections, clear professional and financial
  analysis, essential itinerary, home ties, compliance, and supporting-document discussion.
- Standard: approximately 650-950 words, 4-7 useful sections with a direct but adequately
  explained purpose, finances, identity, home ties, compliance, and document checklist.
Each substantive section should normally contain 2-4 complete paragraphs. Expand by explaining
the relevance of verified evidence; never pad with repetition and never invent missing facts.

AUTOMATIC LETTERHEAD DETECTION:
Inspect every uploaded image and PDF. If one is clearly a blank company letterhead/template
with a company logo/header/footer and is suitable as stationery, return its exact uploaded
filename in letterhead_document. Do not treat ordinary invoices, employment letters, bank
statements, or business documents printed on their issuer's stationery as the applicant's
cover-letter template. Return an empty string when no dedicated template is provided.

BUSINESS INVITATION HANDLING:
- Inspect all files for a genuine business invitation, conference invitation, meeting invitation,
  host-company letter, or event invitation.
- When one is present, add a dedicated developed paragraph directly inside cover_letter explaining
  the verified inviter/host organisation, business purpose, meeting or event, location and dates.
- Use only details explicitly printed in the invitation. If a detail is absent, omit it rather than
  guessing. Explain that the visit is temporary and does not constitute local employment.
- Align purpose_of_visit and the subject with a business visitor purpose when supported by the
  invitation; do not describe a documented business trip as tourism.
- In PURPOSE OF VISIT, explicitly identify the verified inviter/host person or organisation and
  the documented meeting, event, location and dates. Omit only the invitation details that are
  genuinely absent from the uploaded invitation.
- When no business invitation is attached, do not mention an invitation or business host.

STAFF NOTES (use only if supplied):
{notes or '(none)'}
CONFIRMED TRAVEL DATES: {travel_start or '(not supplied)'} to {travel_end or '(not supplied)'}
CONTACT DETAILS FOR THE CLOSING:
- Email: {email_address or '(not supplied)'}
- Phone: {phone_number or '(not supplied)'}

STRICT RULES:
- Use only facts explicitly visible in the attached documents or staff notes.
- Never invent a name, date, amount, address, business, asset, booking, family member, or travel history.
- Omit a section when no reliable supporting fact exists; record it in the missing list instead.
- Resolve minor spelling differences conservatively and keep names/numbers exactly as documented.
- Write in the selected country's professional English style, first person, with short readable paragraphs.
- Before PURPOSE OF VISIT, write exactly two developed introductory paragraphs. Combine all opening
  evidence into those two paragraphs; do not create three or four separate opening paragraphs.
- Match the automatically selected category's length, section depth, table complexity, and level of analysis.
- TURKEY ONLY: regardless of the automatic category, summarise all verified evidence into a
  concise single-page cover letter. Keep the essential purpose, dates, finances, professional
  profile, home ties and attached-document checklist, but do not create extra pages.
- Structure and detail should resemble an embassy submission: cover letter, purpose,
  itinerary, professional profile, finances, accommodation, family/home ties, compliance,
  travel history, supporting documents, and closing.
- Put important names, places, dates, balances, organisations and document numbers between
  **double asterisks** for bold formatting.
- Use the statement's explicitly labelled final closing/ending balance, not an opening balance or
  an earlier running transaction balance. Show it in its original statement currency (normally
  PKR) AND as an approximate destination-country currency equivalent.
- BUSINESS / PROFESSIONAL PROFILE is mandatory when supported. For a business owner discuss
  Chamber of Commerce and NTN evidence; for an employed applicant discuss the employment letter,
  NOC and salary slips. Never claim a document that was not uploaded.
- When an FBR/NTN registration document is uploaded, add a separate FBR NTN REGISTRATION section.
  Read and state the verified taxpayer name, NTN/registration number, registration date and status
  only when printed in that document. Do not claim tax returns or filing history unless attached.
- Use the heading TRAVEL AND ACCOMMODATION instead of IDENTITY AND PERSONAL DOCUMENTATION.
- Use the heading INTERNATIONAL TRAVEL HISTORY instead of IMMIGRATION COMPLIANCE.
- When confirmed start/end dates are supplied, create one itinerary row per day using recognised
  attractions in the supplied city. Do not present suggested attractions as confirmed bookings.
- End the closing with the supplied email address and phone number when present.
- Return one COMPLETE valid JSON object only. No Markdown fence and no commentary.

JSON SCHEMA:
{{
  "profile_category": "exactly one category name listed above",
  "category_reason": "brief evidence-based reason for the classification",
  "letterhead_document": "exact uploaded filename or empty string",
  "subject": "Application for ...",
  "addressee": ["The Visa Officer", "Embassy or visa office if known"],
  "cover_letter": ["paragraphs"],
  "purpose_of_visit": ["paragraphs"],
  "itinerary": [{{"date":"...", "location":"...", "activity":"..."}}],
  "sections": [
    {{"heading":"BUSINESS / PROFESSIONAL PROFILE", "paragraphs":["..."]}},
    {{"heading":"FBR NTN REGISTRATION", "paragraphs":["..."]}},
    {{"heading":"BANK STATEMENT AND FINANCIAL CAPACITY", "paragraphs":["..."]}},
    {{"heading":"TRAVEL AND ACCOMMODATION", "paragraphs":["..."]}},
    {{"heading":"FAMILY AND HOME-COUNTRY TIES", "paragraphs":["..."]}},
    {{"heading":"INTERNATIONAL TRAVEL HISTORY", "paragraphs":["..."]}}
  ],
  "attached_documents": ["only documents actually attached"],
  "closing": ["final request and thanks", "Yours faithfully", "contact details if documented"],
  "missing": ["important information not found"]
}}
"""
    try:
        text = complete(prompt, files=files, max_tokens=10000)
    except Exception:
        pkg = _offline_package(files, notes, destination_country, destination_city, travel_start, travel_end, email_address, phone_number)
        return pkg
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        pkg = _offline_package(files, notes, destination_country, destination_city, travel_start, travel_end, email_address, phone_number)
        return pkg
    try:
        pkg = json.loads(match.group(0))
    except json.JSONDecodeError:
        pkg = _offline_package(files, notes, destination_country, destination_city, travel_start, travel_end, email_address, phone_number)
        return pkg
    for key, default in (
        ("cover_letter", []), ("purpose_of_visit", []), ("itinerary", []),
        ("sections", []), ("attached_documents", []), ("closing", []), ("missing", []),
    ):
        pkg.setdefault(key, default)
    pkg["profile_category"] = _normalise_category(pkg.get("profile_category"))
    pkg["destination_country"] = destination_country
    uploaded_names = {name for name, _ in files}
    if pkg.get("letterhead_document") not in uploaded_names:
        pkg["letterhead_document"] = _detect_letterhead_filename(files)
    _normalise_requested_sections(pkg)
    _normalise_cover_opening(pkg)
    if travel_start and travel_end:
        pkg["itinerary"] = _build_itinerary(destination_city, travel_start, travel_end)
    _append_contact_details(pkg, email_address, phone_number)
    pkg["attached_documents"] = _document_checklist(files)
    _apply_verified_bank_balance(pkg, files, destination_country)
    _apply_ntn_section(pkg, files)
    _apply_country_output_rules(pkg, destination_country)
    for row in pkg.get("itinerary", []):
        row["activity"] = re.sub(
            r"(?i)^suggested tourism visit:\s*", "", str(row.get("activity", ""))
        )
    pkg["document_style_seed"] = secrets.token_hex(8)
    return pkg


def _normalise_category(value: str | None) -> str:
    value = (value or "").lower()
    if "master" in value:
        return "Master Category (Detailed: 7-8 Pages)"
    if "standard" in value:
        return "Standard Category (Short: 1-2 Pages)"
    return DEFAULT_CATEGORY


def _detect_letterhead_filename(files: list) -> str:
    """Conservative fallback; visual detection is performed by the document model."""
    keywords = ("letterhead", "letter-head", "letter_head", "company header", "stationery", "stationary")
    for name, _ in files:
        if any(keyword in name.lower() for keyword in keywords):
            return name
    # A single uploaded image is normally the applicant's stationery. This also
    # covers camera/scanner filenames that do not contain the word letterhead.
    image_files = [
        name for name, _ in files
        if Path(name).suffix.lower() in {".jpg", ".jpeg", ".png"}
    ]
    if len(image_files) == 1:
        return image_files[0]
    return ""


def _offline_category(files: list) -> tuple[str, str]:
    text = _document_text(files).lower()
    names = " ".join(name.lower() for name, _ in files)
    combined = text + " " + names
    asset_terms = sum(combined.count(term) for term in (
        "property", "properties", "asset", "land", "vehicle", "investment", "shareholding",
    ))
    professional = any(term in combined for term in (
        "employment", "salary", "business", "company", "tax return", "partnership", "director",
    ))
    financial = any(term in combined for term in ("bank", "statement", "account", "balance"))
    if asset_terms >= 4 and professional and financial:
        return "Master Category (Detailed: 7-8 Pages)", "Multiple assets plus strong professional and financial evidence were detected."
    if professional and financial:
        return DEFAULT_CATEGORY, "Solid professional/business and bank evidence were detected."
    return "Standard Category (Short: 1-2 Pages)", "The uploaded evidence indicates a straightforward profile with basic supporting documents."


def _document_text(files: list) -> str:
    """Extract embedded text locally without spending an API request."""
    chunks = []
    for name, raw in files:
        if name.lower().endswith(".pdf"):
            try:
                with pdfplumber.open(io.BytesIO(raw)) as pdf:
                    chunks.append("\n".join(page.extract_text() or "" for page in pdf.pages))
            except Exception:
                continue
        elif name.lower().endswith(".txt"):
            chunks.append(raw.decode("utf-8", errors="ignore"))
    return "\n".join(chunks)


def _extract_pdf_text(raw: bytes) -> str:
    """Extract page text while preserving statement row order as far as possible."""
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n\f\n".join(
                page.extract_text(x_tolerance=2, y_tolerance=3, layout=False) or ""
                for page in pdf.pages
            )
    except Exception:
        return ""


def _parse_amount(value: str) -> float | None:
    cleaned = re.sub(r"[^0-9.\-]", "", value.replace(",", ""))
    try:
        amount = float(cleaned)
    except (TypeError, ValueError):
        return None
    return amount if abs(amount) >= 1 else None


def _extract_closing_balance(files: list) -> dict | None:
    """Return the best explicitly labelled statement balance, favouring the final page."""
    label_scores = {
        "closing balance": 120, "closing bal": 115, "balance carried forward": 110,
        "balance c/f": 108, "ending balance": 105, "available balance": 90,
        "current balance": 80, "ledger balance": 70,
    }
    currency_pattern = r"(?:PKR|Rs\.?|USD|CAD|GBP|AUD|NZD|EUR|AED|SAR)"
    amount_pattern = r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|[-+]?\d{4,}(?:\.\d{1,2})?|[-+]?\d+\.\d{2}"
    candidates = []
    letterhead_name = _detect_letterhead_filename(files)
    for filename, raw in files:
        if filename == letterhead_name or not filename.lower().endswith((".pdf", ".txt")):
            continue
        text = _extract_pdf_text(raw) if filename.lower().endswith(".pdf") else raw.decode("utf-8", errors="ignore")
        if not text:
            continue
        lower = text.lower()
        bank_likelihood = sum(term in (filename + " " + lower[:5000]).lower() for term in (
            "bank", "statement", "account number", "iban", "transactions", "debit", "credit"
        ))
        if bank_likelihood < 2:
            continue
        for label, base_score in label_scores.items():
            escaped = re.escape(label)
            for label_match in re.finditer(rf"(?i){escaped}", text):
                line_end = min(
                    [position for position in (text.find("\n", label_match.end()), text.find("\r", label_match.end())) if position >= 0]
                    or [min(len(text), label_match.end() + 140)]
                )
                segment = text[label_match.start():line_end]
                amount_matches = list(re.finditer(
                    rf"(?i)(?P<currency>{currency_pattern})?\s*(?P<amount>{amount_pattern})\s*(?P<currency_after>{currency_pattern})?\s*(?P<suffix>CR|DR)?",
                    segment,
                ))
                if not amount_matches:
                    continue
                # The final numeric value on a labelled summary row is the balance;
                # earlier values on the same row are commonly an "as of" date.
                match = amount_matches[-1]
                amount = _parse_amount(match.group("amount"))
                if amount is None:
                    continue
                if (match.group("suffix") or "").upper() == "DR":
                    amount = -abs(amount)
                raw_currency = (match.group("currency") or match.group("currency_after") or "PKR").upper().replace(".", "")
                currency = "PKR" if raw_currency in {"RS", "PKR"} else raw_currency
                candidates.append({
                    "amount": amount, "currency": currency, "label": label.title(),
                    "source_filename": filename, "raw": " ".join(segment.split()),
                    "score": base_score + int(30 * label_match.start() / max(len(text), 1)) + bank_likelihood,
                    "position": label_match.start(),
                })
    if not candidates:
        return None
    best = max(candidates, key=lambda item: (item["score"], item["position"]))
    best.pop("score", None)
    best.pop("position", None)
    return best


def _document_checklist(files: list) -> list[str]:
    """Build a complete, non-hallucinated checklist from the actual uploads."""
    letterhead_name = _detect_letterhead_filename(files)
    rules = (
        (("passport",), "Passport"), (("cnic", "nicop", "identity card", "national id"), "Identity document"),
        (("bank", "statement", "account"), "Bank statement"), (("frc", "family registration"), "Family Registration Certificate"),
        (("mrc", "marriage registration", "marriage certificate"), "Marriage Registration Certificate"),
        (("invitation", "invite"), "Business invitation"),
        (("employment", "job letter", "noc", "salary", "payslip"), "Employment evidence"),
        (("ntn", "chamber", "business", "company", "tax"), "Business evidence"),
        (("hotel", "accommodation", "booking"), "Accommodation booking"),
        (("flight", "ticket", "itinerary"), "Travel booking"),
    )
    checklist = []
    for filename, _ in files:
        if filename == letterhead_name:
            continue
        label = next((title for terms, title in rules if any(term in filename.lower() for term in terms)), "Supporting document")
        checklist.append(f"{label} - {filename}")
    return list(dict.fromkeys(checklist))


def _label_value(text: str, labels: list[str]) -> str:
    for label in labels:
        match = re.search(
            rf"(?im)^\s*{label}\s*[:\-]?\s*([A-Z][A-Z .'-]{{2,60}})\s*$",
            text,
        )
        if match:
            value = " ".join(match.group(1).split()).title()
            if value.lower() not in {"pakistan", "male", "female"}:
                return value
    return ""


def _inviter_name(text: str) -> str:
    """Extract a conservative inviter/host label from a documented invitation."""
    patterns = (
        r"(?im)^\s*(?:invited by|inviter|host company|host organisation|host organization)\s*[:\-]\s*([^\n\r]{3,100})",
        r"(?im)^\s*(?:company|organisation|organization)\s*(?:name)?\s*[:\-]\s*([^\n\r]{3,100})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = " ".join(match.group(1).split()).strip(" .,:;-")
            if value:
                return value
    return ""


def _offline_package(files, notes, country, city, travel_start="", travel_end="", email_address="", phone_number=""):
    """Safe fallback for free providers that truncate long structured replies."""
    text = _document_text(files)
    name = _label_value(text, ["name", "full name", "given names?", "applicant name"])
    if not name:
        candidates = []
        for filename, _ in files:
            stem = Path(filename).stem
            first = re.split(r"[_\-.]", stem)[0].strip()
            first = re.sub(
                r"(?i)\s+(?:bank\s+statement|passport|cnic|nic|frc|mrc|family\s+registration|marriage\s+registration|statement|document).*$",
                "",
                first,
            ).strip()
            if first and first.lower() not in {"frc", "cnic", "passport", "bank", "statement"}:
                candidates.append(first)
        name = candidates[0].title() if candidates else "the applicant"

    verified_balance = _extract_closing_balance(files)

    filenames = [name for name, _ in files]
    has_bank = any("bank" in n.lower() or "account" in n.lower() for n in filenames)
    has_frc = any("frc" in n.lower() or "family" in n.lower() for n in filenames)
    has_passport = any("passport" in n.lower() for n in filenames)
    has_cnic = any("cnic" in n.lower() or "identity" in n.lower() for n in filenames)
    combined_lower = (text + " " + " ".join(filenames)).lower()
    business_evidence = [label for term, label in (
        ("chamber", "Chamber of Commerce documentation"), ("ntn", "NTN / tax registration"),
        ("business", "business documentation"), ("company", "company documentation"),
    ) if term in combined_lower]
    employment_evidence = [label for term, label in (
        ("employment letter", "employment letter"), ("noc", "NOC letter"),
        ("salary slip", "salary slips"), ("payslip", "salary slips"),
    ) if term in combined_lower]
    invitation_terms = (
        "business invitation", "invitation letter", "letter of invitation",
        "conference invitation", "meeting invitation", "invited by", "host company",
    )
    business_context_terms = ("business", "company", "meeting", "conference", "exhibition", "trade fair", "event")
    has_business_invitation = any(term in combined_lower for term in invitation_terms) or (
        "invitation" in combined_lower and any(term in combined_lower for term in business_context_terms)
    )
    inviter = _inviter_name(text) if has_business_invitation else ""

    trip = f"**{city}, {country}**"
    visit_description = "a short and temporary business visit" if has_business_invitation else "a short and temporary visit"
    stated_purpose = "the documented business meetings or event" if has_business_invitation else "tourism"
    cover = [
        f"I, **{name}**, respectfully submit my application for a temporary visitor visa to **{country}**. "
        f"I intend to make {visit_description} to **{city}** for {stated_purpose}. My passport, identity, family and financial records enclosed with this application are provided so that my circumstances can be assessed from the available documentary evidence.",
        f"This application is presented as a genuine temporary-resident request. The proposed journey is limited to {stated_purpose}, and it does not involve local employment, study or any activity outside the conditions of visitor status.",
        "The enclosed records should be read together as a consistent set of supporting evidence. Identity documents establish the applicant's particulars, family registration records explain the documented family structure, and the available banking material demonstrates the financial evidence submitted for review.",
        f"I understand that permission to enter **{country}** is temporary and subject to immigration conditions. I undertake to respect the authorised period of stay, maintain lawful visitor status and leave **{country}** at the end of the approved visit.",
        "I respectfully request an assessment based on the documents actually supplied. Where travel dates, accommodation, bookings or other trip details are not shown in the uploaded records, those details should be completed and verified before final submission rather than assumed in this letter.",
    ]
    if has_business_invitation:
        cover.insert(2,
            "I have enclosed the uploaded **business invitation** as evidence of the stated purpose of this temporary visit. "
            "The reviewing officer may verify the host organisation, proposed meeting or event, location and any stated dates directly from that document. "
            "I will restrict my activities to the authorised business-visitor purpose and will not undertake local employment."
        )
    purpose = [
        (f"The purpose of my proposed visit to {trip} is the temporary business activity documented in the enclosed invitation"
         f"{' from **' + inviter + '**' if inviter else ''}. My attendance will remain limited to the verified meeting, event or host-company engagement described in that document."
         if has_business_invitation else
         f"The purpose of my proposed visit to {trip} is tourism and leisure. I wish to experience the destination's recognised public attractions, local culture and landmarks during a temporary and carefully limited stay."),
        "My activities will remain consistent with visitor status. I will not undertake unauthorised employment, enrol in a course of study, or engage in any activity that would require a different immigration authorisation.",
        "The final travel programme should be aligned with confirmed dates, accommodation and transport bookings. A day-by-day itinerary should only be included once those details are supported by the applicant's records or staff notes.",
        f"At the conclusion of the authorised visit, I will depart **{country}** in accordance with the conditions attached to any visa granted. This undertaking forms an essential part of my temporary travel request.",
    ]
    sections = []
    if business_evidence or employment_evidence:
        evidence = list(dict.fromkeys(business_evidence + employment_evidence))
        profile_type = "business and self-employment" if business_evidence else "salaried employment"
        sections.append({"heading": "BUSINESS / PROFESSIONAL PROFILE", "paragraphs": [
            f"My uploaded records provide evidence of my **{profile_type}** profile, including **{', '.join(evidence)}**.",
            "These documents are submitted so the reviewing officer can assess my established professional circumstances and continuing economic ties from the source evidence itself.",
        ]})
    if has_bank:
        financial = "I have enclosed my bank/account statement as the financial evidence available for this application. It allows the reviewing officer to examine the recorded account activity and the funds presented in support of the proposed visit."
        if verified_balance:
            financial += (
                f" The verified {verified_balance['label'].lower()} in "
                f"**{verified_balance['source_filename']}** is "
                f"**{verified_balance['currency']} {verified_balance['amount']:,.2f}**."
            )
        sections.append({"heading": "BANK STATEMENT AND FINANCIAL CAPACITY", "paragraphs": [
            financial,
            "The financial assessment should be based on the statement itself, including its covered period, transaction history and any balance expressly shown. No income, asset value or source of funds has been added where it is not supported by the uploaded evidence.",
            "Before submission, the proposed trip budget should be checked against the documented available funds and confirmed travel arrangements. This ensures that the financial explanation remains proportionate, transparent and fully supported.",
        ]})
    if has_frc:
        sections.append({
            "heading": "FAMILY AND HOME-COUNTRY TIES",
            "paragraphs": [
                "I have enclosed my Family Registration Certificate as documentary evidence of my recorded family composition and established family connections in Pakistan.",
                "This certificate is relevant because it provides official supporting context for the family relationships declared with the application. The reviewing officer may assess the exact names and relationships directly from the enclosed record.",
                "These documented connections form part of the applicant's wider circumstances in Pakistan. The letter does not add occupations, dependency claims or other family facts that are not expressly supported by the submitted documents.",
            ],
        })
    sections.append({
        "heading": "TRAVEL AND ACCOMMODATION",
        "paragraphs": [
            f"My proposed journey to **{city}, {country}** is temporary and limited to the confirmed travel period stated in this application.",
            "Accommodation and transport arrangements should be assessed from the uploaded bookings and additional details. No unconfirmed hotel or booking is claimed in this letter.",
        ],
    })
    sections.append({"heading": "INTERNATIONAL TRAVEL HISTORY", "paragraphs": [
        "My passport is submitted so that my international travel history, visas and entry or exit records can be assessed directly from the official document.",
        "This letter does not claim any previous journey that is not evidenced by the uploaded passport or other supporting records.",
    ]})

    missing = ["confirmed travel dates", "accommodation details", "day-by-day itinerary"]
    if not has_bank:
        missing.append("financial evidence")
    if not (has_passport and has_cnic):
        missing.append("complete identity evidence")
    if notes:
        missing = [item for item in missing if item not in notes.lower()]

    category, category_reason = _offline_category(files)
    pkg = {
        "profile_category": category,
        "category_reason": category_reason,
        "destination_country": country,
        "letterhead_document": _detect_letterhead_filename(files),
        "subject": (
            f"Application for Temporary Business Visitor Visa - {country}"
            if has_business_invitation else
            f"Application for Temporary Resident Visa - Tourism in {country}"
        ),
        "addressee": ["The Visa Officer", f"Embassy / Visa Office of {country}"],
        "cover_letter": cover,
        "purpose_of_visit": purpose,
        "itinerary": _build_itinerary(city, travel_start, travel_end) if travel_start and travel_end else [],
        "sections": sections,
        "attached_documents": _document_checklist(files),
        "closing": [
            "Thank you for your time and consideration. I respectfully request favourable consideration of my application.",
            "Yours faithfully,",
            f"**{name}**",
        ],
        "missing": missing,
        "generation_mode": "local_fallback",
        "document_style_seed": secrets.token_hex(8),
    }
    _normalise_cover_opening(pkg)
    _append_contact_details(pkg, email_address, phone_number)
    _apply_verified_bank_balance(pkg, files, country)
    _apply_ntn_section(pkg, files)
    _apply_country_output_rules(pkg, country)
    return pkg


DESTINATION_CURRENCY = {
    "Canada": "CAD", "United Kingdom": "GBP", "Australia": "AUD", "New Zealand": "NZD",
}


def _destination_currency(country: str) -> str | None:
    """Return the active legal-tender currency for an ISO destination country."""
    if country in DESTINATION_CURRENCY:
        return DESTINATION_CURRENCY[country]
    try:
        territory = pycountry.countries.lookup(country)
        currencies = get_territory_currencies(territory.alpha_2, tender=True)
        return currencies[0] if currencies else None
    except (LookupError, AttributeError, TypeError):
        return None

# Used only when the live exchange service is unavailable. The output is explicitly
# labelled approximate, so a temporary network failure never falls back to displaying PKR.
FALLBACK_PKR_RATES = {"CAD": 0.0050, "GBP": 0.0027, "AUD": 0.0055, "NZD": 0.0061}

CITY_ATTRACTIONS = {
    "toronto": ["CN Tower and Harbourfront", "Royal Ontario Museum", "Toronto Islands", "Distillery Historic District", "Casa Loma", "St Lawrence Market"],
    "london": ["Westminster and Big Ben", "British Museum", "Tower of London and Tower Bridge", "Buckingham Palace and St James's Park", "National Gallery", "Hyde Park"],
    "sydney": ["Sydney Opera House and Circular Quay", "Sydney Harbour Bridge", "The Rocks", "Bondi Beach", "Royal Botanic Garden", "Darling Harbour"],
    "auckland": ["Auckland War Memorial Museum", "Sky Tower", "Viaduct Harbour", "Waiheke Island", "Mount Eden", "Auckland Art Gallery"],
}


def _build_itinerary(city: str, start: str, end: str) -> list[dict]:
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except (TypeError, ValueError):
        return []
    if last < first or (last - first).days > 30:
        return []
    primary_city = (city or "Destination city").split(",")[0].strip()
    attractions = CITY_ATTRACTIONS.get(primary_city.lower(), [
        f"city centre and recognised public landmarks in {primary_city}",
        f"local museum and cultural district in {primary_city}",
        f"public park and waterfront sightseeing in {primary_city}",
    ])
    rows = []
    current = first
    index = 0
    while current <= last:
        if current == first:
            activity = f"Arrival, hotel check-in and local orientation in {primary_city}"
        elif current == last:
            activity = f"Hotel check-out and departure from {primary_city}"
        else:
            activity = attractions[(index - 1) % len(attractions)]
        rows.append({"date": current.strftime("%d %B %Y"), "location": primary_city, "activity": activity})
        current += timedelta(days=1)
        index += 1
    return rows


def _append_contact_details(pkg: dict, email: str, phone: str) -> None:
    closing = pkg.setdefault("closing", [])
    closing[:] = [line for line in closing if not re.search(r"(?i)\b(?:email|phone|tel)\b", str(line))]
    contacts = [value.strip() for value in (email, phone) if value and value.strip()]
    if contacts:
        closing.append(" | ".join(f"**{value}**" for value in contacts))


def _normalise_requested_sections(pkg: dict) -> None:
    replacements = {
        "IDENTITY AND PERSONAL DOCUMENTATION": "TRAVEL AND ACCOMMODATION",
        "ACCOMMODATION AND INTENDED STAY": "TRAVEL AND ACCOMMODATION",
        "IMMIGRATION COMPLIANCE": "INTERNATIONAL TRAVEL HISTORY",
        "PREVIOUS TRAVEL HISTORY": "INTERNATIONAL TRAVEL HISTORY",
    }
    seen = set()
    normalised = []
    for section in pkg.get("sections", []):
        heading = replacements.get(str(section.get("heading", "")).upper(), str(section.get("heading", "")).upper())
        section["heading"] = heading
        if heading in seen:
            existing = next(item for item in normalised if item.get("heading") == heading)
            existing.setdefault("paragraphs", []).extend(section.get("paragraphs", []))
        else:
            normalised.append(section)
            seen.add(heading)
    pkg["sections"] = normalised


def _normalise_cover_opening(pkg: dict) -> None:
    """Keep the pre-purpose introduction detailed but limited to two paragraphs."""
    paragraphs = [" ".join(str(value).split()) for value in pkg.get("cover_letter", []) if str(value).strip()]
    if len(paragraphs) > 2:
        split_at = (len(paragraphs) + 1) // 2
        paragraphs = [" ".join(paragraphs[:split_at]), " ".join(paragraphs[split_at:])]
    pkg["cover_letter"] = paragraphs

    addressee = []
    for value in pkg.get("addressee", []):
        line = re.sub(r"\s*,\s*", ", ", " ".join(str(value).split())).strip()
        if not line or line.casefold() in {"to", "to the visa officer"}:
            continue
        if re.fullmatch(r"(?i)(?:the\s+)?visa\s+officer", line):
            line = "The Visa Officer"
        addressee.append(line)
    if not addressee or addressee[0] != "The Visa Officer":
        addressee.insert(0, "The Visa Officer")
    pkg["addressee"] = list(dict.fromkeys(addressee))


def _exchange_rate(currency: str) -> float | None:
    try:
        with urllib.request.urlopen("https://open.er-api.com/v6/latest/PKR", timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
        return float(data.get("rates", {}).get(currency) or 0) or None
    except Exception:
        return FALLBACK_PKR_RATES.get(currency)


def _apply_verified_bank_balance(pkg: dict, files: list, country: str) -> None:
    """Insert one deterministic dual-currency balance sentence into the finance section."""
    balance = _extract_closing_balance(files)
    if not balance:
        return
    destination_currency = _destination_currency(country)
    destination_text = ""
    if balance["currency"] == "PKR" and destination_currency:
        rate = _exchange_rate(destination_currency)
        if rate:
            destination_text = (
                f"; approximately **{destination_currency} {balance['amount'] * rate:,.2f}** "
                f"for the **{country}** application (reference conversion)"
            )
    sentence = (
        f"The verified **{balance['label']}** shown in **{balance['source_filename']}** is "
        f"**{balance['currency']} {balance['amount']:,.2f}**{destination_text}."
    )
    sections = pkg.setdefault("sections", [])
    finance = next((section for section in sections if "BANK" in str(section.get("heading", "")).upper()), None)
    if finance is None:
        finance = {"heading": "BANK STATEMENT AND FINANCIAL CAPACITY", "paragraphs": []}
        sections.insert(0, finance)
    paragraphs = [
        paragraph for paragraph in finance.get("paragraphs", [])
        if not re.search(r"(?i)\b(?:closing|ending|available|current|ledger)\s+(?:account\s+)?balance\b", str(paragraph))
    ]
    paragraphs.insert(0, sentence)
    finance["paragraphs"] = paragraphs
    pkg["verified_bank_balance"] = balance


def _apply_ntn_section(pkg: dict, files: list) -> None:
    """Add a standalone verified FBR/NTN section when NTN evidence is uploaded."""
    ntn_files = []
    text_parts = []
    for filename, raw in files:
        file_text = ""
        if filename.lower().endswith(".pdf"):
            file_text = _extract_pdf_text(raw)
        elif filename.lower().endswith(".txt"):
            file_text = raw.decode("utf-8", errors="ignore")
        evidence = f"{filename}\n{file_text}"
        if re.search(r"(?i)\b(?:ntn|national\s+tax\s+number|federal\s+board\s+of\s+revenue|fbr)\b", evidence):
            ntn_files.append(filename)
            text_parts.append(file_text)
    if not ntn_files:
        return

    text = "\n".join(text_parts)
    number_match = re.search(
        r"(?i)(?:national\s+tax\s+number|registration\s*(?:no\.?|number)|\bntn\b)\s*[:#\-]?\s*([0-9]{7}(?:-[0-9])?|[0-9]{8,10})",
        text,
    )
    taxpayer = _label_value(text, ["taxpayer name", "business name", "name"])
    verified = []
    if taxpayer:
        verified.append(f"registered taxpayer name **{taxpayer}**")
    if number_match:
        verified.append(f"National Tax Number **{number_match.group(1)}**")
    sources = ", ".join(f"**{name}**" for name in ntn_files)
    if verified:
        first = f"The uploaded FBR/NTN evidence ({sources}) records the " + " and ".join(verified) + "."
    else:
        first = f"I have enclosed the uploaded FBR/NTN registration evidence ({sources}) for verification of my documented tax registration."
    paragraphs = [
        first,
        "This registration supports my documented professional and economic circumstances in Pakistan. Any tax-return or filing-history assessment should rely only on tax records separately attached to this application.",
    ]
    sections = pkg.setdefault("sections", [])
    existing = next((item for item in sections if str(item.get("heading", "")).upper() == "FBR NTN REGISTRATION"), None)
    if existing:
        existing["paragraphs"] = paragraphs
    else:
        profile_index = next((index for index, item in enumerate(sections) if "PROFESSIONAL PROFILE" in str(item.get("heading", "")).upper()), -1)
        sections.insert(profile_index + 1, {"heading": "FBR NTN REGISTRATION", "paragraphs": paragraphs})


def _shorten_text(value: str, limit: int) -> str:
    """Keep complete opening sentences within a compact evidence-led limit."""
    clean = " ".join(str(value or "").split())
    if len(clean) <= limit:
        return clean
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    chosen = ""
    for sentence in sentences:
        candidate = f"{chosen} {sentence}".strip()
        if chosen and len(candidate) > limit:
            break
        chosen = candidate
    if chosen and len(chosen) <= limit:
        return chosen
    return clean[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "."


def _apply_country_output_rules(pkg: dict, country: str) -> None:
    """Turkey applications are always condensed to a single-page package."""
    if (country or "").strip().casefold() not in {"turkey", "türkiye", "turkiye"}:
        return
    pkg["force_one_page"] = True
    pkg["profile_category"] = "Standard Category (Short: 1-2 Pages)"
    pkg["category_reason"] = "Turkey-specific single-page cover-letter format."
    pkg["cover_letter"] = [
        _shorten_text(value, 330) for value in pkg.get("cover_letter", [])[:2] if str(value).strip()
    ]
    pkg["purpose_of_visit"] = [
        _shorten_text(pkg.get("purpose_of_visit", [""])[0], 280)
    ] if pkg.get("purpose_of_visit") else []
    compact_sections = []
    preferred = (
        "BUSINESS / PROFESSIONAL PROFILE", "FBR NTN REGISTRATION", "BANK STATEMENT AND FINANCIAL CAPACITY",
        "TRAVEL AND ACCOMMODATION", "FAMILY AND HOME-COUNTRY TIES",
        "INTERNATIONAL TRAVEL HISTORY",
    )
    section_map = {str(item.get("heading", "")).upper(): item for item in pkg.get("sections", [])}
    for heading in preferred:
        section = section_map.get(heading)
        if not section or not section.get("paragraphs"):
            continue
        compact_sections.append({
            "heading": heading,
            "paragraphs": [_shorten_text(section["paragraphs"][0], 260)],
        })
    pkg["sections"] = compact_sections
    pkg["itinerary"] = []
    pkg["attached_documents"] = pkg.get("attached_documents", [])[:10]
    pkg["closing"] = [
        _shorten_text(value, 180) for value in pkg.get("closing", []) if str(value).strip()
    ][:3]


def package_text(pkg: dict) -> str:
    """Library mein save karne ke liye flat text."""
    parts = ["\n\n".join(pkg.get("cover_letter", [])), "PURPOSE OF VISIT\n" + "\n\n".join(pkg.get("purpose_of_visit", []))]
    if pkg.get("itinerary"):
        parts.append("TRAVEL ITINERARY\n" + "\n".join(f"{r['date']} | {r['location']} | {r['activity']}" for r in pkg["itinerary"]))
    for section in pkg.get("sections", []):
        parts.append(section.get("heading", "") + "\n" + "\n\n".join(section.get("paragraphs", [])))
    if pkg.get("attached_documents"):
        parts.append("ATTACHED DOCUMENTS\n" + "\n".join("• " + item for item in pkg["attached_documents"]))
    if pkg.get("closing"):
        parts.append("\n\n".join(pkg["closing"]))
    return "\n\n".join(parts)


def check_package(pkg: dict, visa_type: str) -> list:
    r = load_rules()
    issues = []
    n = len(" ".join(pkg.get("cover_letter", [])).split())
    if not r["word_count"]["min"] <= n <= r["word_count"]["max"]:
        issues.append(f"Cover letter {n} words (target {r['word_count']['min']}-{r['word_count']['max']})")
    if pkg.get("missing"):
        issues.append("Missing info, pehle ye details dein: " + ", ".join(pkg["missing"]))
    if "[MISSING" in package_text(pkg):
        issues.append("Letter mein [MISSING: ...] marker hai")
    if visa_type != "study" and not pkg.get("itinerary"):
        issues.append("Itinerary khali hai (travel dates/cities chahiye)")
    return issues
