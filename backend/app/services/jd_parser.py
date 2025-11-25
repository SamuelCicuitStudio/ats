# app/services/jd_parser.py
"""
JD Parsing Service:
- Extract text (pdf/docx/txt)    [reuses extract_text from CV module]
- Detect language                [langdetect on first 3k chars]
- Truncate (25k cap: first 15k + last 5k)
- Call Ollama (phi3:latest or OLLAMA_MODEL_JD) with strict JSON prompt + format=json
- Validate JSON with jsonschema
- Normalize (title/company required; skills/certs deduped; years coerced; jd_* set)
- Persist artifacts via storage_utils (exposed through persist_outputs)

Env:
  OLLAMA_BASE_URL   (default http://localhost:11434)
  OLLAMA_MODEL_JD   (falls back to OLLAMA_MODEL_CV or phi3:latest)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from jsonschema import Draft7Validator
from langdetect import detect

# Centralized storage (atomic writes)
from app.utils.storage_utils import persist_jd_artifacts

# Reuse extraction + truncation helpers to keep behavior identical to CV parsing
from app.services.cv_parser import extract_text, truncate_for_llm

# ---- Env & constants ----
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL_JD = (
    os.getenv("OLLAMA_MODEL_JD")
    or os.getenv("OLLAMA_MODEL_CV", "phi3:latest")
)
MAX_CHARS_FOR_LLM = 25_000  # (shared policy; not directly used here since we reuse truncate_for_llm)

# ---- Errors ----
class SchemaError(Exception):
    """Raised when the extracted JSON fails schema or required post-normalization checks."""
    pass


# ---------- JSON schema (per spec) ----------
JD_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["job_profile", "jd_language", "jd_text"],
    "properties": {
        "job_profile": {
            "type": "object",
            "required": ["basics"],
            "properties": {
                "basics": {
                    "type": "object",
                    "required": ["title", "company"],
                    "properties": {
                        "title": {"type": "string"},
                        "company": {"type": "string"},
                    },
                }
            },
        },
        "skills": {"type": "array", "items": {"type": "string"}},
        "required_certifications": {"type": "array", "items": {"type": "string"}},
        "experience_required_years": {"type": "integer"},
        "jd_language": {"type": "string"},
        "jd_text": {"type": "string"},
    },
}


# ---------- helpers ----------
def detect_language(text: str) -> str:
    try:
        snippet = text[:3000] if len(text) > 3000 else text
        return detect(snippet) or "und"
    except Exception:
        return "und"


def _norm_list_str(values: Optional[List[str]]) -> List[str]:
    values = values or []
    dedup = {(v or "").strip().lower() for v in values if (v or "").strip()}
    return sorted(list(dedup))


# ---- LLM (Ollama) call with retry on JSON failure ----
def call_ollama_extract_jd(detected_lang: str, truncated_text: str) -> Dict[str, Any]:
    """
    Calls Ollama /api/generate with format=json to enforce JSON-only output.
    Retries up to 2 additional times on JSON parse failure.
    """
    system = (
        "You extract structured job requirements. "
        "Return ONLY strict JSON validating the schema. "
        "Use empty strings or [] when information is missing. "
        "Do not add fields not defined by the schema."
    )
    user = f"""Extract the job profile from the following JD text. JSON schema:

{json.dumps(JD_SCHEMA, ensure_ascii=False, indent=2)}

JD_LANGUAGE_HINT: {detected_lang}
JD_TEXT:
{truncated_text}
"""

    payload = {
        "model": OLLAMA_MODEL_JD,
        "system": system,
        "prompt": user,
        "format": "json",
        "options": {"temperature": 0.0, "top_p": 1.0},
        "stream": False,
    }
    url = f"{OLLAMA_BASE_URL}/api/generate"

    last_exc: Optional[Exception] = None
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            content = (resp.json().get("response") or "").strip()
            return json.loads(content)
        except Exception as e:
            last_exc = e
            payload["prompt"] = user + "\n\nReturn strictly valid JSON only. No extra text."

    raise RuntimeError(f"Ollama JSON extraction failed after retries: {last_exc}")


def normalize_jd(parsed: Dict[str, Any], detected_lang: str, raw_text: str) -> Dict[str, Any]:
    # Ensure language + raw text
    parsed["jd_language"] = detected_lang or parsed.get("jd_language") or "und"
    parsed["jd_text"] = raw_text

    # Basics: title & company required non-empty
    job_profile = parsed.get("job_profile") or {}
    basics = (job_profile.get("basics") or {})
    basics["title"] = (basics.get("title") or "").strip()
    basics["company"] = (basics.get("company") or "").strip()
    if not basics["title"] or not basics["company"]:
        raise SchemaError("JD basics.title and basics.company must be non-empty strings.")
    job_profile["basics"] = basics
    parsed["job_profile"] = job_profile

    # Skills & certifications: lowercase, dedupe, sort
    parsed["skills"] = _norm_list_str(parsed.get("skills"))
    parsed["required_certifications"] = _norm_list_str(parsed.get("required_certifications"))

    # experience_required_years: coerce to non-negative int if present
    if "experience_required_years" in parsed:
        yrs = parsed.get("experience_required_years")
        if isinstance(yrs, str) and yrs.isdigit():
            yrs = int(yrs)
        if isinstance(yrs, int):
            parsed["experience_required_years"] = max(0, yrs)
        else:
            # remove invalid to satisfy schema if it rejects non-integers
            parsed.pop("experience_required_years", None)

    return parsed


# ---------- Public API ----------
@dataclass
class JDParseResult:
    parsed: Dict[str, Any]
    detected_language: str
    raw_text: str


def parse_jd_file(filename: str, file_bytes: bytes) -> JDParseResult:
    # 1) extract text
    raw = extract_text(filename, file_bytes)
    if not raw.strip():
        raise ValueError("File contains no readable text.")

    # 2) detect language
    lang = detect_language(raw)

    # 3) truncate for LLM
    truncated = truncate_for_llm(raw)

    # 4) LLM extraction (deterministic, JSON-only)
    parsed = call_ollama_extract_jd(lang, truncated)

    # 5) schema validate
    validator = Draft7Validator(JD_SCHEMA)
    errors = sorted(validator.iter_errors(parsed), key=lambda e: e.path)
    if errors:
        err = errors[0]
        raise SchemaError(f"JSON schema validation failed at {list(err.path)}: {err.message}")

    # 6) normalization (+ required title/company)
    normalized = normalize_jd(parsed, lang, raw)

    return JDParseResult(parsed=normalized, detected_language=lang, raw_text=raw)


def parse_jd(filename: str, file_bytes: bytes, req_id: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
    """
    Thin wrapper expected by main.py: returns (jd_json, raw_text).
    Persistence is handled by main.py via persist_outputs().
    """
    res = parse_jd_file(filename, file_bytes)
    return res.parsed, res.raw_text


# ---- Persistence (delegates to storage_utils) ----
def persist_outputs(req_id: str, filename: str, raw: bytes, jd_json: Dict[str, Any]) -> Dict[str, str]:
    from app.utils.storage_utils import persist_jd_artifacts
    return persist_jd_artifacts(
        req_id=req_id,
        original_filename=filename,
        raw_bytes=raw,
        jd_json=jd_json,
    )
