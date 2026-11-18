import pymupdf

from app.generate import _document_checklist, _extract_closing_balance, _apply_verified_bank_balance


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
