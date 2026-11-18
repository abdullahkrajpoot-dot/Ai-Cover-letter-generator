import pymupdf
from copy import deepcopy

from app.export import package_pdf
from app.generate import (
    _apply_country_output_rules, _apply_verified_bank_balance,
    _document_checklist, _extract_closing_balance,
)


def _statement_pdf() -> bytes:
    doc = pymupdf.open()
    first = doc.new_page()
    first.insert_text((72, 72), "ABC Bank Account Statement")
    first.insert_text((72, 100), "Opening Balance PKR 150,000.00")
    first.insert_text((72, 130), "Current Balance PKR 175,000.00")
    second = doc.new_page()
    second.insert_text((72, 72), "Account Number 123456 Transactions Debit Credit")
    second.insert_text((72, 110), "Closing Balance as of 31 December 2026: PKR 987,654.32 CR")
    data = doc.tobytes()
    doc.close()
    return data


def test_closing_balance_prefers_explicit_final_balance():
    result = _extract_closing_balance([("bank_statement.pdf", _statement_pdf())])
    assert result is not None
    assert result["amount"] == 987654.32
    assert result["currency"] == "PKR"
    assert result["source_filename"] == "bank_statement.pdf"


def test_dual_currency_sentence_preserves_pkr(monkeypatch):
    monkeypatch.setattr("app.generate._exchange_rate", lambda currency: 0.005)
    package = {"sections": [{"heading": "BANK STATEMENT AND FINANCIAL CAPACITY", "paragraphs": []}]}
    _apply_verified_bank_balance(package, [("bank_statement.pdf", _statement_pdf())], "Canada")
    paragraph = package["sections"][0]["paragraphs"][0]
    assert "PKR 987,654.32" in paragraph
    assert "CAD 4,938.27" in paragraph


def test_checklist_uses_actual_files_and_excludes_letterhead():
    files = [
        ("passport.pdf", b""), ("client_bank_statement.pdf", b""),
        ("business_invitation.pdf", b""), ("company_letterhead.png", b""),
    ]
    assert _document_checklist(files) == [
        "Passport - passport.pdf",
        "Bank statement - client_bank_statement.pdf",
        "Business invitation - business_invitation.pdf",
    ]


def _long_package():
    return {
        "subject": "Application for a Visitor Visa to Turkey",
        "addressee": ["The Visa Officer", "Embassy of Turkey"],
        "cover_letter": [("This paragraph explains the verified application evidence in detail. " * 20)] * 4,
        "purpose_of_visit": [("The purpose is a temporary tourism visit supported by the documents. " * 15)],
        "itinerary": [{"date": "1 January 2027", "location": "Istanbul", "activity": "Sightseeing"}],
        "sections": [
            {"heading": heading, "paragraphs": [("Verified supporting evidence is enclosed for review. " * 15)]}
            for heading in (
                "BUSINESS / PROFESSIONAL PROFILE", "BANK STATEMENT AND FINANCIAL CAPACITY",
                "TRAVEL AND ACCOMMODATION", "FAMILY AND HOME-COUNTRY TIES",
                "INTERNATIONAL TRAVEL HISTORY",
            )
        ],
        "attached_documents": [f"Supporting document - file-{index}.pdf" for index in range(15)],
        "closing": ["Thank you for your consideration.", "Yours faithfully,", "Applicant Name"],
    }


def test_turkey_is_compacted_to_one_pdf_page_only():
    package = _long_package()
    _apply_country_output_rules(package, "Turkey")
    assert package["force_one_page"] is True
    assert package["itinerary"] == []
    assert len(package["attached_documents"]) == 10
    rendered = pymupdf.open(stream=package_pdf(package), filetype="pdf")
    try:
        assert len(rendered) == 1
    finally:
        rendered.close()


def test_non_turkey_package_is_not_changed():
    package = _long_package()
    original = deepcopy(package)
    _apply_country_output_rules(package, "Canada")
    assert package == original
