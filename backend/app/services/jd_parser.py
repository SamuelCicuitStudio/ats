# app/services/jd_parser.py
"""
Implementation calquee sur refjob.py pour l'API:
- extraction texte (pdf/docx/txt) a partir de bytes
- detection de langue
- prompt Ollama strict JSON
- extraction robuste du JSON (regex)
- validation jsonschema
"""

from __future__ import annotations

import io
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import ollama
import pdfplumber
from docx import Document
from jsonschema import validate
from langdetect import detect

from app.utils.storage_utils import persist_jd_artifacts

# Configuration
OLLAMA_MODEL_JD = os.getenv("OLLAMA_MODEL_JD", "phi3:latest")
MAX_TOKENS = 3000  # comme refjob

JSON_SCHEMA = {
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

# Prompt identique au ref
PROMPT = '''[SYSTEM] Tu es un assistant d'extraction d'informations pour des offres d'emploi.
Lis le texte fourni et retourne STRICTEMENT un objet JSON avec la structure suivante (aucun champ en plus, aucun champ en moins) 
pour chaque fichier JD. Extrait-moi proprement les sections : profil, missions, competences, prerequis et formate en JSON standardise :
{
    "job_profile": {
        "basics": {
            "title": "",
            "company": ""
        }
    },
    "jd_language": "",
    "jd_text": ""
}

REGLES :
1. Remplis tous les champs, meme vides ("" ou []).
2. Si une information n'est pas presente dans le texte, laisse le champ vide.
3. Ne retourne rien d'autre que l'objet JSON ci-dessus.
4. Ne jamais inventer d'information.

[JOB]
{text}
'''

# --- Extraction du texte a partir d'un fichier ---
def extract_text(filename: str, file_bytes: bytes) -> str:
    ext = os.path.splitext((filename or "").lower())[1]
    if ext == '.pdf':
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or '' for page in pdf.pages)
    elif ext == '.docx':
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(para.text for para in doc.paragraphs)
    elif ext == '.txt':
        return file_bytes.decode('utf-8', errors='replace')
    else:
        raise ValueError(f"Format non supporte: {ext}")


# --- Troncature du texte pour ne pas depasser une limite de tokens ---
def truncate_text(text: str, max_tokens: int = MAX_TOKENS) -> str:
    words = text.split()
    return " ".join(words[:max_tokens])


def parse_with_ollama(text: str) -> Dict[str, Any]:
    truncated = truncate_text(text, MAX_TOKENS)

    response = ollama.generate(
        model=OLLAMA_MODEL_JD,
        prompt=PROMPT.format(text=truncated),
        options={"temperature": 0.1}
    )

    raw = response["response"] if "response" in response else response.get("message", {}).get("content", "")

    # Extraction robuste
    match = re.search(r'\{(?:[^{}]|(?R))*\}', raw, re.DOTALL)
    if not match:
        raise ValueError("Impossible d'extraire du JSON depuis Ollama")

    json_str = match.group()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON mal forme : {e}\nJSON recu : {json_str}")

    return data


# ---- Public API ----
@dataclass
class JDParseResult:
    parsed: Dict[str, Any]
    detected_language: str
    raw_text: str


def parse_jd_file(filename: str, file_bytes: bytes) -> JDParseResult:
    text = extract_text(filename, file_bytes)
    if not text.strip():
        raise ValueError("Fichier vide ou illisible")

    # Detection automatique de la langue
    lang = detect(text) if len(text) > 20 else "fr"

    data = parse_with_ollama(text)
    data["jd_language"] = lang  # post-traitement
    data["jd_text"] = text      # texte complet

    validate(instance=data, schema=JSON_SCHEMA)
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
