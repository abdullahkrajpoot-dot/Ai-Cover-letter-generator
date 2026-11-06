import base64
import io
import os
import re
import tempfile
import time

import google.generativeai as genai
import httpx
import pdfplumber
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.omniroute", override=True)

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Flash-Lite is sufficient for document extraction and structured letter output,
# while costing substantially less than a Pro model. Override it in .env when
# higher quality is required: GEMINI_MODEL=gemini-3.8-flash
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def _omniroute_key() -> str:
    key = os.getenv("OMNIROUTE_API_KEY", "").strip()
    key_file = os.getenv("OMNIROUTE_API_KEY_FILE", "").strip()
    if not key and key_file:
        try:
            with open(key_file, "r", encoding="utf-8") as handle:
                key = handle.read().strip()
        except OSError as exc:
            raise RuntimeError(f"OmniRoute API key file read nahi ho saki: {exc}") from exc
    return key


def _omniroute_content(prompt, files):
    content = [{"type": "text", "text": prompt}]
    for name, data in files or []:
        raw = data
        if isinstance(data, str) and os.path.exists(data):
            with open(data, "rb") as handle:
                raw = handle.read()
        if not isinstance(raw, bytes):
            raw = str(raw).encode("utf-8")

        lower_name = name.lower()
        if lower_name.endswith(".pdf"):
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
            content.append({
                "type": "text",
                "text": f"\nDocument: {name}\n{text or '[PDF has no extractable text]'}",
            })
        elif lower_name.endswith((".png", ".jpg", ".jpeg")):
            mime = "image/png" if lower_name.endswith(".png") else "image/jpeg"
            encoded = base64.b64encode(raw).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            })
        else:
            content.append({
                "type": "text",
                "text": f"\nDocument: {name}\n{raw.decode('utf-8', errors='ignore')}",
            })
    return content


def _complete_omniroute(prompt, files, max_tokens):
    base_url = os.getenv("OMNIROUTE_BASE_URL", "").strip().rstrip("/")
    key = _omniroute_key()
    if not key:
        raise RuntimeError("OmniRoute API key missing hai.")

    model = os.getenv("OMNIROUTE_MODEL", "pol/openai").strip() or "pol/openai"
    request_body = {
        "model": model,
        "messages": [{"role": "user", "content": _omniroute_content(prompt, files)}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    response = None
    for attempt in range(5):
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=request_body,
            timeout=180,
        )
        retry_match = re.search(r"retry after\s+(\d+)s", response.text, re.IGNORECASE)
        should_retry = response.status_code in (402, 429, 503)
        if not should_retry or attempt == 4:
            break

        retry_seconds = int(retry_match.group(1)) if retry_match else 15
        time.sleep(min(retry_seconds + 1, 35))

    if response is None:
        raise RuntimeError("OmniRoute request send nahi ho saki.")
    if response.status_code >= 400:
        detail = response.text[:500]
        raise RuntimeError(f"OmniRoute request fail hui ({response.status_code}): {detail}")

    payload = response.json()
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("OmniRoute ne unexpected response diya.") from exc


def _friendly_api_error(exc: Exception) -> RuntimeError:
    message = str(exc)
    normalized = message.lower()
    if any(term in normalized for term in (
        "resource_exhausted", "quota", "rate limit", "429", "credit",
    )):
        return RuntimeError(
            "Gemini API quota/credits khatam ya rate limit exceed ho gayi hai. "
            "Agar requests bohat tez hui hain to 1-2 minutes baad retry karein. "
            "Daily quota khatam hai to quota reset ka wait karein; paid project "
            "ke liye Google AI Studio mein billing/spend limit check karein."
        )
    if any(term in normalized for term in ("api key", "api_key", "permission_denied", "401", "403")):
        return RuntimeError(
            "Gemini API key invalid hai ya is project ko Gemini API access nahi. "
            "GEMINI_API_KEY aur Google AI Studio project permissions check karein."
        )
    return RuntimeError(f"Gemini API request fail hui: {message}")

def complete(prompt, files=None, max_tokens=1500):
    if os.getenv("OMNIROUTE_BASE_URL", "").strip():
        return _complete_omniroute(prompt, files, max_tokens)

    if not api_key:
        raise RuntimeError(
            "Gemini API key missing hai. .env mein GEMINI_API_KEY set karein."
        )

    contents = [prompt]
    temp_files = []
    try:
        if files:
            for name, data in files:
                mime_type = "application/pdf"
                if name.lower().endswith((".png", ".jpg", ".jpeg")):
                    mime_type = "image/jpeg"
                elif name.lower().endswith(".txt"):
                    mime_type = "text/plain"

                if isinstance(data, str) and os.path.exists(data):
                    upload_path = data
                else:
                    suffix = os.path.splitext(name)[1]
                    tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    tf.write(data if isinstance(data, bytes) else str(data).encode("utf-8"))
                    tf.close()
                    temp_files.append(tf.name)
                    upload_path = tf.name

                contents.append(genai.upload_file(upload_path, mime_type=mime_type))

        model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            contents,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.2,
            ),
        )
        return response.text
    except Exception as exc:
        raise _friendly_api_error(exc) from exc
    finally:
        for tf_path in temp_files:
            try:
                os.unlink(tf_path)
            except OSError:
                pass
