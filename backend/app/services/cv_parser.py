# app/services/cv_parser.py
"""
CV Parsing Service:
- Extract text (pdf/docx/txt)
- Detect language
- Truncate (25k cap: first 15k + last 5k)
- Call Ollama (phi3:latest) with strict JSON prompt + format=json
- Validate JSON with jsonschema
- Normalize fields (names, skills, experience months, etc.)
- Persist artifacts via storage_utils

Relies on env:
  OLLAMA_BASE_URL (default http://localhost:11434)
  OLLAMA_MODEL_CV (default phi3:latest)
"""

from __future__ import annotations

import io
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import docx
import pdfplumber
import requests
from dateutil import parser as dateparser
from jsonschema import Draft7Validator
from langdetect import detect

# Storage helpers (centralized, atomic writes, normalized paths)
from app.utils.storage_utils import persist_cv_artifacts

# ---- Env & constants ----
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL_CV = os.getenv("OLLAMA_MODEL_CV", "phi3:latest")
MAX_CHARS_FOR_LLM = 25_000

# ---- Errors ----
class SchemaError(Exception):
    """Raised when the extracted JSON fails the required schema."""
    pass


# ---- JSON schema (as per spec) ----
CV_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "profile",
        "skills",
        "experience",
        "education",
        "languages",
        "certifications",
        "cv_language",
        "cv_text",
    ],
    "properties": {
        "profile": {
            "type": "object",
            "required": ["basics"],
            "properties": {
                "basics": {
                    "type": "object",
                    "required": ["first_name", "last_name"],
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "full_name_raw": {"type": "string"},
                        "current_title": {"type": "string"},
                        "email": {"type": "string"},
                        "phone": {"type": "string"},
                        "location": {"type": "string"},
                    },
                }
            },
        },
        "skills": {"type": "array", "items": {"type": "string"}},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "duration_months": {"type": "integer"},
                    "is_internship": {"type": "boolean"},
                    "highlights": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "degree": {"type": "string"},
                    "school": {"type": "string"},
                    "year": {"type": "integer"},
                },
            },
        },
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "level": {"type": "string"}},
            },
        },
        "certifications": {"type": "array", "items": {"type": "string"}},
        "cv_language": {"type": "string"},
        "cv_text": {"type": "string"},
    },
}


# ---- Text I/O helpers ----
def _collapse_newlines(s: str) -> str:
    s = s.replace("\x00", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _read_pdf(file_bytes: bytes) -> str:
    parts: List[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            if t.strip():
                parts.append(t)
    return _collapse_newlines("\n\n".join(parts))


def _read_docx(file_bytes: bytes) -> str:
    f = io.BytesIO(file_bytes)
    doc = docx.Document(f)
    paras = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    return _collapse_newlines("\n".join(paras))


def _read_txt(file_bytes: bytes) -> str:
    s = file_bytes.decode("utf-8", errors="replace")
    return _collapse_newlines(s)


def extract_text(filename: str, file_bytes: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _read_pdf(file_bytes)
    if name.endswith(".docx"):
        return _read_docx(file_bytes)
    if name.endswith(".txt"):
        return _read_txt(file_bytes)
    raise ValueError("Unsupported file type. Use .pdf, .docx, or .txt")


# ---- Language & truncation ----
def detect_language(text: str) -> str:
    try:
        snippet = text[:3000] if len(text) > 3000 else text
        lang = detect(snippet)
        return lang or "und"
    except Exception:
        return "und"


def truncate_for_llm(text: str) -> str:
    if len(text) <= MAX_CHARS_FOR_LLM:
        return text
    head = text[:15_000]
    tail = text[-5_000:]
    return f"{head}\n...\n{tail}"


# ---- LLM (Ollama) call ----
def call_ollama_extract(detected_lang: str, truncated_text: str) -> Dict[str, Any]:
    """
    Calls Ollama /api/generate with format=json to enforce JSON-only output.
    Retries up to 2 times on JSON parse failure (total 3 attempts).
    """
    system = (
        "You are a precise information extractor. Return ONLY strict JSON that validates the given schema. "
        "If a field is missing in the CV, return an empty string (\"\") or empty list [] as appropriate. Never invent data."
    )
    user = f"""Extract the candidate profile from the following CV text. Follow exactly this JSON schema:

{json.dumps(CV_SCHEMA, ensure_ascii=False, indent=2)}

CV_LANGUAGE_HINT: {detected_lang}
CV_TEXT:
{truncated_text}
"""

    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL_CV,
        "system": system,
        "prompt": user,
        "format": "json",
        "options": {"temperature": 0.0, "top_p": 1.0},
        "stream": False,
    }

    attempts = 0
    last_exc: Optional[Exception] = None
    while attempts < 3:
        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            content = (data.get("response") or "").strip()
            return json.loads(content)
        except Exception as e:
            last_exc = e
            # reinforce JSON-only instruction and retry
            payload["prompt"] = user + "\n\nReturn strictly valid JSON only. No extra text."
            attempts += 1

    # if still failing after retries
    raise RuntimeError(f"Ollama JSON extraction failed after retries: {last_exc}")


# ---- Normalization helpers ----
def _normalize_spaces(s: str) -> str:
    return re.sub(r"[ \t]+", " ", (s or "").strip())


def _titlecase_name(s: str) -> str:
    return " ".join(w.capitalize() for w in s.split()) if s else s


def _to_iso(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    s = date_str.strip()
    if not s:
        return None
    try:
        dt = dateparser.parse(s, default=datetime(1900, 1, 1))
        return dt.date().isoformat()
    except Exception:
        return None


def _months_between_if_both(start_iso: Optional[str], end_iso: Optional[str]) -> int:
    """Compute months only when BOTH dates exist (per spec)."""
    if not start_iso or not end_iso:
        return 0
    try:
        sd = dateparser.parse(start_iso).date()
        ed = dateparser.parse(end_iso).date()
        months = (ed.year - sd.year) * 12 + (ed.month - sd.month)
        return months if months >= 0 else 0
    except Exception:
        return 0


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def normalize_cv(parsed: Dict[str, Any], detected_lang: str, raw_text: str) -> Dict[str, Any]:
    # Ensure cv_language & cv_text
    parsed["cv_language"] = detected_lang or parsed.get("cv_language") or "und"
    parsed["cv_text"] = raw_text

    # Basics
    basics = parsed.get("profile", {}).get("basics", {})
    basics["first_name"] = _titlecase_name(_normalize_spaces(basics.get("first_name", "")))
    basics["last_name"] = _titlecase_name(_normalize_spaces(basics.get("last_name", "")))
    if basics.get("full_name_raw"):
        basics["full_name_raw"] = _normalize_spaces(basics["full_name_raw"])
    if basics.get("current_title"):
        basics["current_title"] = _normalize_spaces(basics["current_title"])
    if basics.get("location"):
        basics["location"] = _normalize_spaces(basics["location"])

    # Email (first valid, lowercase)
    email = _normalize_spaces(basics.get("email", ""))
    if email:
        m = EMAIL_RE.search(email)
        basics["email"] = m.group(0).lower() if m else ""
    else:
        m = EMAIL_RE.search(raw_text or "")
        basics["email"] = m.group(0).lower() if m else ""

    # Phone: digits and plus only
    phone = basics.get("phone", "") or ""
    basics["phone"] = re.sub(r"[^0-9+]", "", phone)

    # Skills: lowercase, dedupe, sort (alphabetical)
    skills = parsed.get("skills", []) or []
    skills_norm = []
    for s in skills:
        ss = _normalize_spaces(str(s)).lower()
        if ss:
            skills_norm.append(ss)
    parsed["skills"] = sorted(list({s for s in skills_norm}))

    # Experience
    exps = parsed.get("experience", []) or []
    for e in exps:
        e["title"] = _normalize_spaces(e.get("title", ""))
        e["company"] = _normalize_spaces(e.get("company", ""))
        s_iso = _to_iso(e.get("start_date"))
        e_iso = _to_iso(e.get("end_date"))
        e["start_date"] = s_iso or ""
        e["end_date"] = e_iso or ""
        e["duration_months"] = _months_between_if_both(s_iso, e_iso)
        label = f"{e.get('title','')} {e.get('company','')}".lower()
        e["is_internship"] = bool(re.search(r"\b(intern|stagiaire|internship|apprentice)\b", label))
        if isinstance(e.get("highlights"), list):
            e["highlights"] = [
                _normalize_spaces(h) for h in e["highlights"] if _normalize_spaces(h)
            ]
    parsed["experience"] = exps

    # Education
    edus = parsed.get("education", []) or []
    for ed in edus:
        ed["degree"] = _normalize_spaces(ed.get("degree", ""))
        ed["school"] = _normalize_spaces(ed.get("school", ""))
        y = ed.get("year")
        if isinstance(y, str) and y.isdigit():
            ed["year"] = int(y)
        elif not isinstance(y, int):
            ed["year"] = None
    parsed["education"] = edus

    # Languages
    allowed_levels = {"native", "fluent", "advanced", "intermediate", "basic"}
    langs = parsed.get("languages", []) or []
    for l in langs:
        l["name"] = _normalize_spaces(l.get("name", "")).lower()
        lvl = _normalize_spaces(l.get("level", "")).lower()
        l["level"] = lvl if lvl in allowed_levels else (None if lvl else None)
    parsed["languages"] = langs

    # Certifications
    certs = parsed.get("certifications", []) or []
    parsed["certifications"] = [_normalize_spaces(c) for c in certs if _normalize_spaces(c)]

    return parsed


# ---- Persistence (delegates to storage_utils) ----
def persist_outputs(req_id: str, filename: str, raw: bytes, cv_json: Dict[str, Any]) -> Dict[str, str]:
    from app.utils.storage_utils import persist_cv_artifacts
    return persist_cv_artifacts(
        req_id=req_id,
        original_filename=filename,
        raw_bytes=raw,
        cv_json=cv_json,
    )



# ---- Public API ----
@dataclass
class CVParseResult:
    parsed: Dict[str, Any]
    detected_language: str
    raw_text: str


def parse_cv_file(filename: str, file_bytes: bytes) -> CVParseResult:
    # 1) Extract
    raw = extract_text(filename, file_bytes)
    if not raw.strip():
        raise ValueError("File contains no readable text.")

    # 2) Language
    lang = detect_language(raw)

    # 3) Truncate for LLM
    truncated = truncate_for_llm(raw)

    # 4) LLM extraction (Ollama, deterministic, JSON-only)
    parsed = call_ollama_extract(lang, truncated)

    # 5) Schema validation
    validator = Draft7Validator(CV_SCHEMA)
    errors = sorted(validator.iter_errors(parsed), key=lambda e: e.path)
    if errors:
        err = errors[0]
        # Raise our SchemaError so FastAPI can return 422
        raise SchemaError(f"JSON schema validation failed at {list(err.path)}: {err.message}")

    # 6) Normalization (names, skills, dates → ISO, duration_months, etc.)
    normalized = normalize_cv(parsed, lang, raw)

    return CVParseResult(parsed=normalized, detected_language=lang, raw_text=raw)


def parse_cv(filename: str, file_bytes: bytes, req_id: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
    """
    Thin wrapper expected by main.py: returns (cv_json, raw_text).
    Persistence is handled by main.py via persist_outputs().
    """
    res = parse_cv_file(filename, file_bytes)
    return res.parsed, res.raw_text
