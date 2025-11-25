# app/services/cv_parser.py
"""
Generalisation de refcv.py pour l'API :
- extraction texte (pdf/docx/txt) a partir de bytes
- detection de langue
- prompt Ollama strict JSON inspire du ref
- validation schema minimale + normalisation legere
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import ollama
import pdfplumber
from docx import Document
from jsonschema import Draft7Validator
from langdetect import DetectorFactory, detect

from app.utils.storage_utils import persist_cv_artifacts

# reproductibilite de langdetect
DetectorFactory.seed = 0

OLLAMA_MODEL_CV = os.getenv("OLLAMA_MODEL_CV", "nous-hermes")
MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "5000"))

CV_PROMPT_TEMPLATE = """
[SYSTEM] Tu es un expert RH. Extrait STRICTEMENT ces champs au format JSON :
{
  "nom": "",
  "prenom": "",
  "profil": "",
  "annees_experience": 0,
  "localisation": "",
  "telephone": "",
  "email": "",
  "entreprise_actuelle": "",
  "poste_actuel": "",
  "competences": [],
  "certifications": [],
  "diplomes": [],
  "ecoles": []
}

[REGLES]
- "annees_experience" : uniquement des annees completes hors stages
- "competences" : liste de competences techniques brutes
- Ne pas inventer de donnees manquantes
- Formater les numeros de telephone internationalement (+33...)
- Reponds en JSON uniquement.

[CV]
{text}
"""

CV_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "nom",
        "prenom",
        "profil",
        "annees_experience",
        "localisation",
        "telephone",
        "email",
        "entreprise_actuelle",
        "poste_actuel",
        "competences",
        "certifications",
        "diplomes",
        "ecoles",
        "cv_language",
        "cv_text",
    ],
    "properties": {
        "nom": {"type": "string"},
        "prenom": {"type": "string"},
        "profil": {"type": "string"},
        "annees_experience": {"type": ["integer", "number", "string"]},
        "localisation": {"type": "string"},
        "telephone": {"type": "string"},
        "email": {"type": "string"},
        "entreprise_actuelle": {"type": "string"},
        "poste_actuel": {"type": "string"},
        "competences": {"type": "array", "items": {"type": "string"}},
        "certifications": {"type": "array", "items": {"type": "string"}},
        "diplomes": {"type": "array", "items": {"type": "string"}},
        "ecoles": {"type": "array", "items": {"type": "string"}},
        "cv_language": {"type": "string"},
        "cv_text": {"type": "string"},
    },
}


class SchemaError(Exception):
    """Raised when the extracted JSON fails the required schema."""


# ---- Text extraction ----
def extract_text(filename: str, file_bytes: bytes) -> str:
    ext = os.path.splitext((filename or "").lower())[1]
    try:
        if ext == ".pdf":
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
        if ext == ".docx":
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(para.text for para in doc.paragraphs).strip()
        if ext == ".txt":
            return file_bytes.decode("utf-8", errors="replace").strip()
    except Exception as e:
        raise ValueError(f"Erreur extraction: {e}")
    raise ValueError(f"Format non supporte: {ext}")


def detect_language(text: str) -> str:
    try:
        return detect(text) if len(text) > 20 else "fr"
    except Exception:
        return "und"


def truncate_text(text: str, limit: int = MAX_TOKENS) -> str:
    return text[:limit] if len(text) > limit else text


def _extract_first_json_object(s: str) -> str:
    """
    Extract the first balanced JSON object substring from a string.
    The model may prepend/append text; we isolate the JSON block.
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


# ---- LLM call ----
def parse_with_ollama(text: str) -> Dict[str, Any]:
    prompt = CV_PROMPT_TEMPLATE.format(text=truncate_text(text))
    response = ollama.generate(
        model=OLLAMA_MODEL_CV,
        prompt=prompt,
        format="json",
        options={"temperature": 0.0},
    )

    if "response" in response:
        raw_json = response["response"]
    elif "message" in response and "content" in response["message"]:
        raw_json = response["message"]["content"]
    else:
        raise ValueError("Format de reponse inattendu d'Ollama")

    try:
        json_block = _extract_first_json_object(raw_json)
        data = json.loads(json_block)
    except Exception as e:
        raise ValueError(f"Impossible d'extraire/decoder le JSON: {e}")
    required_fields = ["nom", "prenom", "email"]
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValueError(f"Champ obligatoire manquant: {field}")
    try:
        data["annees_experience"] = int(data.get("annees_experience", 0))
    except Exception:
        data["annees_experience"] = 0
    return data


def _normalize_list(values: Optional[List[Any]]) -> List[str]:
    out: List[str] = []
    for v in values or []:
        if isinstance(v, str):
            s = v.strip()
            if s:
                out.append(s)
    return out


# ---- Public API ----
@dataclass
class CVParseResult:
    parsed: Dict[str, Any]
    detected_language: str
    raw_text: str


def parse_cv_file(filename: str, file_bytes: bytes) -> CVParseResult:
    raw_text = extract_text(filename, file_bytes)
    if not raw_text:
        raise ValueError("Fichier vide ou illisible")

    lang = detect_language(raw_text)
    parsed = parse_with_ollama(raw_text)
    parsed["cv_language"] = lang
    parsed["cv_text"] = raw_text
    parsed["competences"] = _normalize_list(parsed.get("competences"))
    parsed["certifications"] = _normalize_list(parsed.get("certifications"))
    parsed["diplomes"] = _normalize_list(parsed.get("diplomes"))
    parsed["ecoles"] = _normalize_list(parsed.get("ecoles"))

    validator = Draft7Validator(CV_SCHEMA)
    errors = sorted(validator.iter_errors(parsed), key=lambda e: e.path)
    if errors:
        err = errors[0]
        raise SchemaError(f"JSON schema validation failed at {list(err.path)}: {err.message}")

    return CVParseResult(parsed=parsed, detected_language=lang, raw_text=raw_text)


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
