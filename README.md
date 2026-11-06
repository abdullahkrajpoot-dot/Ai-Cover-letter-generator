# Visa Cover Letter Generator

Streamlit application for generating evidence-led visitor visa cover letters for Canada, the United Kingdom, Australia and New Zealand.

## Setup
```
pip install -r requirements.txt
# .env file auto-loads automatically when the app starts
streamlit run streamlit_app.py
```

`.env` example:
```
GEMINI_API_KEY=your_key
# Optional low-cost default override:
GEMINI_MODEL=gemini-2.5-flash
```

If Gemini returns a 429/quota error, short-term rate limits normally clear after
a brief wait. A daily quota needs its reset; exhausted paid credits/spend caps
must be handled in Google AI Studio billing. Changing API keys in the same
Google project does not create a new quota because quota is project-based.

## Istemal
1. **Letter library** tab: 20+ approved Canadian letters upload karein (visit/business/study alag).
2. **Generate** tab: visa type chunein, passport/ID/FRC/bank/job/invitation upload karein, scan karein.
3. Nikla hua data check karein, notes likhein, letter generate karein.
4. Letter edit karein, DOCX download karein, achha ho to **Approve** karein. Ye anonymized letter library mein add ho jata hai aur agli letters behtar hoti hain.

## Structure
- `config/canada_rules.yaml` : Canada ke rules aur har visa type ki zaroorat. Naya country = nayi rules file.
- `app/extract.py` : documents se fields (Claude vision)
- `app/library.py` : letters ki library + retrieval
- `app/generate.py` : prompt + generation + checks
- `app/export.py` : DOCX

## Privacy (zaroori)
- Passport/ID images library mein save nahi hotin, sirf redacted approved letters.
- Production se pehle: login, encryption, auto-delete policy, aur client ki ijazat add karein.
- Redaction basic hai, approve karne se pehle letter mein naam/address check karein.
