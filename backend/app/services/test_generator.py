# app/services/test_generator.py
"""
Technical Test / Questionnaire Generator (frontend-compatible)

This service now mirrors the reference "questionnaire_generator (1).py":
- Same model source (OLLAMA_MODEL), same French prompt, same JSON output format
- Generates ~20 short, technical interview questions and includes both QCM and open questions
- Returns a JSON array of {"question": "..."} objects

Frontend contract preserved:
- Public API: generate_questions(jd: dict) -> {"questions": [...], "storage_path": "...", "id": "..."}
- Persists payload via app.utils.storage_utils.persist_questions when available, else local atomic write
"""

from __future__ import annotations

import os
import re
import json
import uuid
import tempfile
from typing import List, Dict, Any

import ollama  # switched to match reference impl (ollama.chat)
# Try storage utils (preferred); we also ship a safe local fallback if import fails.
try:
    from app.utils.storage_utils import persist_questions  # type: ignore
    _HAS_STORAGE_UTILS = True
except Exception:
    persist_questions = None  # type: ignore
    _HAS_STORAGE_UTILS = False

# ------------------------------- Config ---------------------------------------
# Match the reference: use OLLAMA_MODEL (from config if available), not a TEST-specific model.
try:
    # If your project defines OLLAMA_MODEL in config.config (like the reference)
    from config.config import OLLAMA_MODEL  # type: ignore
except Exception:
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:latest")

# Minimal EN/FR stopword set (for JD keyword fallback)
_STOPWORDS = {
    # english
    "a","an","and","the","or","of","for","with","in","to","on","by","at","from","as","is","are","be","being","been",
    "this","that","these","those","it","its","we","you","they","their","our","your",
    "i","he","she","them","his","her","ours","yours",
    "will","can","should","may","must","might",
    "not","no","yes","but","if","else","than","then","so","such","per",
    "job","role","position","requirements","responsibilities","skills","experience","years","year",
    # french
    "le","la","les","un","une","des","du","de","d","et","ou","dans","au","aux","par","pour","avec","sur","en","à",
    "est","sont","être","été","ayant","avoir","ou","sans","plus","moins","ainsi","dont","que","qui","quoi","où",
    "poste","rôle","exigences","responsabilités","compétences","expérience","ans","année","années"
}
_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", re.UNICODE)


# ------------------------------- Prompt ---------------------------------------
# Copied (semantics preserved) from questionnaire_generator (1).py
PROMPT_TEMPLATE = """
Tu es un expert en recrutement technique.
Génère entre 20 questions d’entretien (courtes et techniques) dois inclure des qcm et des questions ouvertes
à partir des compétences suivantes : {skills}.
Le résultat doit être un tableau JSON, avec le format suivant :

[
  {{ "question": "..." }},
  {{ "question": "..." }}
]
""".strip()


# ---------------------------- tiny helpers ------------------------------------
def _normspace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _atomic_write_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def _dedup_lower_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        v = _normspace(it).lower()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _extract_seed_skills(jd: Dict[str, Any], k: int = 20) -> List[str]:
    """
    Primary: jd['skills'] / jd['competences'] if provided by the JD parser.
    Fallback: simple term-frequency on jd['jd_text'] with stopwords removed.
    Behavior mirrors the reference's intent to derive skills when not provided.
    """
    skills = jd.get("skills") or jd.get("competences") or []
    if isinstance(skills, list) and skills:
        return _dedup_lower_keep_order(skills)[:k]

    text = _normspace(jd.get("jd_text", ""))
    if not text:
        return []

    freqs: Dict[str, int] = {}
    for tok in _TOKEN_RE.findall(text):
        t = tok.lower()
        if len(t) < 3 or t in _STOPWORDS:
            continue
        freqs[t] = freqs.get(t, 0) + 1

    if not freqs:
        return []
    ranked = sorted(freqs.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for (w, _) in ranked[:k]]


# ---------------------- LLM call (matches reference) --------------------------
def _ollama_generate_questions(skills: List[str]) -> List[Dict[str, str]]:
    if not skills:
        return []

    prompt = PROMPT_TEMPLATE.format(skills=", ".join(skills))

    try:
        # Use ollama.chat like the reference; temp ~0.8
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.8},
        )
        raw_output = (
            (response.get("message") or {}).get("content")
            if isinstance(response, dict) else ""
        ) or ""
    except Exception as e:
        # Mirror reference behavior: fail softly
        print(f"[!] Erreur Ollama : {e}")
        return []

    # Try to parse as JSON first
    try:
        data = json.loads(raw_output)
        if isinstance(data, list):
            # Normalize shape: keep only {"question": "<str>"}
            normalized: List[Dict[str, str]] = []
            for item in data:
                if isinstance(item, dict) and "question" in item and isinstance(item["question"], str):
                    normalized.append({"question": _normspace(item["question"])})
            if normalized:
                return normalized
    except Exception:
        pass

    # Fallback compatible with reference (split lines)
    questions = [
        {"question": _normspace(q)}
        for q in raw_output.split("\n")
        if _normspace(q)
    ]
    return questions


def _post_normalize(questions: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Light cleanup + dedupe. Keep up to 20 items (reference says 'entre 20').
    Do NOT enforce the old 5..10 constraint to stay aligned with the reference.
    """
    seen = set()
    cleaned: List[Dict[str, str]] = []
    for q in questions:
        s = _normspace(q.get("question", ""))
        if 5 <= len(s) <= 250 and s.lower() not in seen:
            seen.add(s.lower())
            cleaned.append({"question": s})

    # Aim for up to 20 questions as per the reference prompt
    if len(cleaned) > 20:
        cleaned = cleaned[:20]
    return cleaned


# --------------------------- public API (unchanged) ----------------------------
def generate_questions(jd: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate ~20 concise questions from a JD JSON and persist them.
    Returns:
      {
        "questions": [...],
        "storage_path": "<abs path to saved json>",
        "id": "<uuid>"
      }
    """
    basics = (jd.get("job_profile") or {}).get("basics") or {}
    # Role/company kept for possible future extensions; prompt currently uses skills only (like the reference).
    _ = _normspace(basics.get("title", ""))
    _ = _normspace(basics.get("company", ""))

    seed_skills = _extract_seed_skills(jd, k=20)
    questions = _ollama_generate_questions(seed_skills)
    questions = _post_normalize(questions)

    qid = str(uuid.uuid4())
    payload = {
        "id": qid,
        "seed_skills": seed_skills,
        "questions": questions,
    }

    # Persist via project utility if available; else local atomic write
    if _HAS_STORAGE_UTILS and callable(persist_questions):  # type: ignore
        try:
            info = persist_questions(qid, payload)  # expected to return {"path": "..."} (or similar)
            storage_path = info.get("path") or info.get("json_path") or info.get("storage_path")  # type: ignore
            if not storage_path:
                raise RuntimeError("persist_questions returned no path.")
        except Exception:
            out_dir = os.path.abspath(os.path.join(os.getcwd(), "storage", "questions"))
            storage_path = os.path.join(out_dir, f"{qid}.json")
            _atomic_write_json(storage_path, payload)
    else:
        out_dir = os.path.abspath(os.path.join(os.getcwd(), "storage", "questions"))
        storage_path = os.path.join(out_dir, f"{qid}.json")
        _atomic_write_json(storage_path, payload)

    return {"questions": questions, "storage_path": storage_path, "id": qid}
