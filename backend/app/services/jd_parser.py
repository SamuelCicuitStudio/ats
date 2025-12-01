# app/services/jd_parser.py
"""
Backend JD parser aligned with the reference parse_jd script:
- same JSON schema, same prompt, same response shape
- bytes-based file extraction (pdf/docx/txt)
- language detection
- robust JSON extraction (no PCRE recursion)
- schema validation (graceful fallback so the frontend never breaks)
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
from jsonschema import validate, ValidationError

from app.utils.storage_utils import persist_jd_artifacts

# ---------------------------------- Config -----------------------------------
OLLAMA_MODEL_JD = os.getenv("OLLAMA_MODEL_JD", "phi3:latest")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "45"))
PROMPT_CHAR_LIMIT = int(os.getenv("JD_PROMPT_CHAR_LIMIT", "3000"))

# --- JSON schema (identical to parser_jd) ---
JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "job_profile": {
            "type": "object",
            "properties": {
                "basics": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "company": {"type": "string"}
                    },
                    "required": ["title", "company"]
                }
            },
            "required": ["basics"]
        },
        "jd_language": {"type": "string"},
        "jd_text": {"type": "string"}
    },
    "required": ["job_profile", "jd_language", "jd_text"]
}

# --- Prompt (same wording as parser_jd; injected text placeholder preserved) ---
JD_PROMPT_TEMPLATE = (
    "[SYSTEM] Tu es un assistant d'extraction d'informations pour des offres d'emploi.\n"
    "Lis le texte fourni et retourne STRICTEMENT un objet JSON avec la structure suivante (aucun champ en plus, aucun champ en moins) \n"
    "pour chaque fichier JD. Extrait-moi proprement les sections : profil, missions, compétences, prérequis et formate en JSON standardisé :\n"
    "{\n"
    '    "job_profile": {\n'
    '        "basics": {\n'
    '            "title": "",\n'
    '            "company": ""\n'
    "        }\n"
    "    },\n"
    '    "jd_language": "",\n'
    '    "jd_text": ""\n'
    "}\n\n"
    "RÈGLES :\n"
    '1. Remplis tous les champs, même vides ("" ou []).\n'
    "2. Si une information n'est pas présente dans le texte, laisse le champ vide.\n"
    "3. Ne retourne rien d'autre que l'objet JSON ci-dessus.\n"
    "4. Ne jamais inventer d'information.\n\n"
    "[JOB]\n"
    "{jd_text}\n"
)

# --- Extraction du texte a partir d'un fichier ---
def extract_text(filename: str, file_bytes: bytes) -> str:
    ext = os.path.splitext((filename or "").lower())[1]
    if ext == ".pdf":
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    elif ext == ".docx":
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(para.text for para in doc.paragraphs)
    elif ext == ".txt":
        return file_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Format non supporte: {ext}")

# --- Normalisation / limite de prompt ---
def _normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split())

def _build_prompt_payload(text: str, max_chars: int = PROMPT_CHAR_LIMIT) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars]

# --- Extraction robuste du premier objet JSON equilibre ---
def _extract_first_json_object(s: str) -> str:
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
    payload = (raw or "").strip()
    if not payload:
        raise ValueError("Reponse modele vide")
    # 1) tentative directe
    try:
        return json.loads(payload)
    except Exception:
        pass
    # 2) bloc JSON equilibre
    try:
        return json.loads(_extract_first_json_object(payload))
    except Exception:
        pass
    # 3) rattrapage minimal si la cle racine est visible
    if ('"job_profile"' in payload) or ("'job_profile'" in payload):
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

def parse_with_model(text: str) -> Dict[str, Any]:
    payload = _build_prompt_payload(text)
    # IMPORTANT: avoid .format on the JSON braces; only replace our placeholder
    prompt = JD_PROMPT_TEMPLATE.replace("{jd_text}", payload)
    try:
        response = ollama.generate(
            model=OLLAMA_MODEL_JD,
            prompt=prompt,
            options={
                "temperature": 0.1,   # matches parser_jd behavior
            },
        )
    except Exception as exc:
        raise RuntimeError(f"Echec appel LLM (JD): {exc}") from exc

    raw = response.get("response") or response.get("message", {}).get("content") or ""
    try:
        data = _load_json_lenient(raw)
        # validate against the shared schema; if it fails we fall back below
        validate(instance=data, schema=JSON_SCHEMA)
        return data
    except (ValidationError, Exception):
        # Fallback: ensure the frontend still gets a valid shape
        return {
            "job_profile": {"basics": {"title": "", "company": ""}},
            "jd_language": "",
            "jd_text": text,
        }

# ---- Public API (unchanged; used by the frontend) ----
@dataclass
class JDParseResult:
    parsed: Dict[str, Any]
    detected_language: str
    raw_text: str

def parse_jd_file(filename: str, file_bytes: bytes) -> JDParseResult:
    text = extract_text(filename, file_bytes)
    if not text.strip():
        raise ValueError("Fichier vide ou illisible")
    # auto language detection
    lang = detect(text) if len(text) > 20 else "fr"
    data = parse_with_model(text)
    data["jd_language"] = lang  # post-process to match schema
    data["jd_text"] = text
    return JDParseResult(parsed=data, detected_language=lang, raw_text=text)

def parse_jd(filename: str, file_bytes: bytes, req_id: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
    res = parse_jd_file(filename, file_bytes)
    return res.parsed, res.raw_text

def persist_outputs(req_id: str, filename: str, raw: bytes, jd_json: Dict[str, Any]) -> Dict[str, str]:
    return persist_jd_artifacts(
        req_id=req_id,
        original_filename=filename,
        raw_bytes=raw,
        jd_json=jd_json,
    )
