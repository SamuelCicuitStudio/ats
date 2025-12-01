# app/services/cv_parser.py
"""
Backend CV parser aligned with the reference parser_cv (1).py:
- same model, same JSON schema, same prompt, same response shape
- bytes-based file extraction (pdf/docx/txt)
- language detection
- robust JSON extraction (no PCRE recursion issues)
- keeps the same public API used by the frontend: parse_cv_file / parse_cv / persist_outputs
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import ollama
import pdfplumber
from docx import Document
from langdetect import detect

from app.utils.storage_utils import persist_cv_artifacts

# ------------------------------- Config ---------------------------------------
# Match reference: use the same environment var name for model; default to phi3:latest
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:latest")
# Keep a simple word-budget like the reference (not true tokens)
MAX_TOKENS = int(os.getenv("CV_PROMPT_CHAR_LIMIT", os.getenv("OLLAMA_MAX_TOKENS", "3000")))

# --- JSON schema (identical structure to parser_cv (1).py) ---
JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "profile": {
            "type": "object",
            "properties": {
                "basics": {
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                    },
                    "required": ["first_name", "last_name"],
                },
            },
            "required": ["basics"],
        },
        "cv_language": {"type": "string"},
    },
    "required": ["profile"],
}

# --- Prompt (copied from parser_cv (1).py) ---
PROMPT_TEMPLATE = """
[SYSTEM] You are an expert system for extracting information following strict JSON format:
- First name and last name (required)
- Email, phone
- Location (city, country)
- Technical skills (simple list)
- Professional experience (position, company, duration)
- Education
- Languages (with level)
- Projects github(name, link, description)
- Certifications(name, organization, date)
- Publications(title, link, date)
- References(name, contact)
- CV language (French, English, etc.)
- Raw CV text (for reference)
- Do not include empty or irrelevant sections

### Details to extract
- Job title
- Companies
- Dates (start and end: month and year)
- Duration (calculated in years and months)
- Indicate if it's an internship
- Identify current company and position if possible
- Calculate total years of experience **excluding internships**
- Diplomas (title, institution, year)
- Languages and level

[CV]
{text}
""".strip()


# ------------------------- File text extraction --------------------------------
def extract_text(filename: str, file_bytes: bytes) -> str:
    ext = os.path.splitext((filename or "").lower())[1]
    if ext == ".pdf":
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if ext == ".docx":
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(para.text for para in doc.paragraphs)
    if ext == ".txt":
        return file_bytes.decode("utf-8", errors="replace")
    raise ValueError(f"Format non supporte: {ext}")


# ------------------------------ Prompt sizing ---------------------------------
def truncate_text(text: str, max_tokens: Optional[int] = None) -> str:
    if max_tokens is None:
        max_tokens = MAX_TOKENS
    words = text.split()
    return " ".join(words[:max_tokens])


# --------------------------- Robust JSON handling ------------------------------
def _extract_first_json_object(s: str) -> str:
    """
    Extract the first balanced JSON object substring from a string (manual scan).
    """
    start = s.find("{")
    if start == -1:
        raise ValueError("JSON start brace not found in model response")
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    raise ValueError("Unbalanced braces in model response; JSON not closed")


def _load_json_lenient(raw: str) -> Dict[str, Any]:
    """
    Decode model response even if it contains surrounding text or minor JSON issues.
    Priority given to structures that contain top keys (profile/basics).
    """
    payload = (raw or "").strip()
    if not payload:
        raise ValueError("Reponse modele vide")

    # 1) Direct attempt
    try:
        return json.loads(payload)
    except Exception:
        pass

    # 2) Balanced braces slice
    try:
        return json.loads(_extract_first_json_object(payload))
    except Exception:
        pass

    # 3) Minimal recovery when the opening brace is missing
    if ('"profile"' in payload) or ("'profile'" in payload):
        inner = payload.lstrip(", \n\r\t")
        if not inner.startswith("{"):
            inner = "{" + inner
        if inner.count("{") > inner.count("}"):
            inner = inner + "}"
        try:
            return json.loads(inner)
        except Exception:
            pass

    raise ValueError("Impossible d'extraire un JSON valide de la reponse modele")


# ------------------------------- LLM call --------------------------------------
def parse_with_model(text: str) -> Dict[str, Any]:
    truncated = truncate_text(text)
    # Use replace instead of .format to avoid conflicts with JSON braces
    prompt = PROMPT_TEMPLATE.replace("{text}", truncated)

    try:
        response = ollama.generate(
            model=OLLAMA_MODEL,
            prompt=prompt,
            format="json",
            options={"temperature": 0.1},  # match reference behavior
        )
    except Exception as exc:
        raise RuntimeError(f"Echec appel LLM (CV): {exc}") from exc

    raw = response.get("response") or response.get("message", {}).get("content") or ""
    return _load_json_lenient(raw)


# ------------------------------ Public API ------------------------------------
@dataclass
class CVParseResult:
    parsed: Dict[str, Any]
    detected_language: str
    raw_text: str


def parse_cv_file(filename: str, file_bytes: bytes) -> CVParseResult:
    raw_text = extract_text(filename, file_bytes)
    if not raw_text.strip():
        raise ValueError("Fichier vide ou illisible")

    try:
        lang = detect(raw_text) if len(raw_text) > 20 else "fr"
    except Exception:
        lang = "fr"

    data = parse_with_model(raw_text)
    # Ensure fields the frontend relies on are always present
    data["cv_language"] = lang
    data["cv_text"] = raw_text

    return CVParseResult(parsed=data, detected_language=lang, raw_text=raw_text)


def parse_cv(filename: str, file_bytes: bytes, req_id: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
    res = parse_cv_file(filename, file_bytes)
    return res.parsed, res.raw_text


def persist_outputs(req_id: str, filename: str, raw: bytes, cv_json: Dict[str, Any]) -> Dict[str, str]:
    return persist_cv_artifacts(
        req_id=req_id,
        original_filename=filename,
        raw_bytes=raw,
        cv_json=cv_json,
    )
