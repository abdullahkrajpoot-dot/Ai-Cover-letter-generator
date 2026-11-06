"""Approved letters ki library + similar letters retrieve karna (TF-IDF, koi training nahi)."""
import json
import hashlib
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

LIB = Path(__file__).resolve().parent.parent / "data" / "letters"


def redact(text: str) -> str:
    """Basic personal-data redaction. Staff ko phir bhi manually check karna chahiye."""
    text = re.sub(r"\b\d{5}-?\d{7}-?\d\b", "[CNIC]", text)
    text = re.sub(r"\b[A-Z]{2}\d{7}\b", "[PASSPORT_NO]", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[EMAIL]", text)
    text = re.sub(r"\+?\d[\d\s-]{8,}\d", "[PHONE]", text)
    return text


def feedback_key(text: str, country: str, visa_type: str) -> str:
    payload = f"{country.casefold()}|{visa_type.casefold()}|{redact(text).strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def record_feedback(key: str, rating: int, learned: bool) -> None:
    path = LIB.parent / "feedback.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"key": key, "rating": rating, "learned": learned}) + "\n")


def add_letter(text: str, visa_type: str, country: str = "Canada", source: str = "sample", rating: int | None = None) -> str:
    LIB.mkdir(parents=True, exist_ok=True)
    lid = feedback_key(text, country, visa_type)
    target = LIB / f"{lid}.json"
    if target.exists():
        return ""
    rec = {"id": lid, "country": country, "visa_type": visa_type, "source": source, "rating": rating, "text": redact(text)}
    target.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    if rating is not None:
        record_feedback(lid, rating, learned=rating >= 4)
    return lid


def all_letters(country="Canada", visa_type=None):
    out = []
    for p in LIB.glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("country", "").casefold() == country.casefold() and (visa_type is None or r.get("visa_type") == visa_type):
            out.append(r)
    return out


def retrieve(query: str, country="Canada", visa_type=None, k=4):
    letters = all_letters(country, visa_type) or all_letters(country)
    if not letters:
        return []
    vec = TfidfVectorizer(stop_words="english")
    mat = vec.fit_transform([l["text"] for l in letters] + [query])
    sims = cosine_similarity(mat[-1], mat[:-1]).ravel()
    order = sims.argsort()[::-1][:k]
    return [letters[i] for i in order]
