# app/services/test_generator.py
"""
Technical Test Generator
- Input: JD JSON (normalized by your JD Parser)
- Seeds: use jd["skills"]; if empty, fall back to top terms from jd["jd_text"]
- LLM: Ollama /api/generate with model from OLLAMA_MODEL_TEST (default 'mistral')
- Output: list of 5..10 questions (each: {"question": "<string>"})
- Persist: /storage/questions/<uuid>.json (atomic write)
- Deterministic: temperature 0.0, top_p 1.0

Env:
  OLLAMA_BASE_URL (default http://localhost:11434)
  OLLAMA_MODEL_TEST (default mistral)
"""

from __future__ import annotations

import os
import re
import json
import uuid
import tempfile
from typing import List, Dict, Any, Tuple

import requests

# Try storage utils (preferred); we also ship a safe local fallback if import fails.
try:
    from app.utils.storage_utils import persist_questions  # type: ignore
    _HAS_STORAGE_UTILS = True
except Exception:
    persist_questions = None  # type: ignore
    _HAS_STORAGE_UTILS = False

# --------- Config / constants ----------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL_TEST = os.getenv("OLLAMA_MODEL_TEST", "mistral")
OLLAMA_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "3000"))

# Minimal EN/FR stopword set (enough for JD keyword fallback, no extra deps)
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


# -------------------- small helpers --------------------
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


def _extract_seed_skills(jd: Dict[str, Any], k: int = 10) -> List[str]:
    """
    Primary: jd['skills'] (already normalized by JD parser).
    Fallback: simple term-frequency on jd['jd_text'] with stopwords removed (no sklearn dependency).
    """
    skills = jd.get("skills") or jd.get("competences") or []
    if isinstance(skills, list) and skills:
        return _dedup_lower_keep_order(skills)[:k]

    text = _normspace(jd.get("jd_text", ""))
    if not text:
        return []

    # crude token freq (single-document "tf-idf" ~ tf)
    freqs: Dict[str, int] = {}
    for tok in _TOKEN_RE.findall(text):
        t = tok.lower()
        if len(t) < 3 or t in _STOPWORDS:
            continue
        freqs[t] = freqs.get(t, 0) + 1

    if not freqs:
        return []

    # pick top-k by frequency, stable by token name as tie-breaker
    ranked = sorted(freqs.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for (w, _) in ranked[:k]]


def _ollama_generate_questions(role_title: str, company: str, seed_skills: List[str]) -> List[Dict[str, str]]:
    system = (
        "You generate concise technical interview questions. "
        'Return ONLY valid JSON: an array of 5 to 10 objects, each with a single key "question" (string). '
        "No explanations, no commentary."
    )
    user = (
        "Create targeted technical questions based on these skills and the role title.\n\n"
        f"ROLE_TITLE: {role_title}\n"
        f"COMPANY: {company}\n"
        f'SKILLS_CANDIDATE_SHOULD_HAVE: {", ".join(seed_skills)}\n\n'
        "Return JSON only, like:\n[\n  {\"question\": \"Your single question here.\"}\n]\n"
    )

    payload = {
        "model": OLLAMA_MODEL_TEST,
        "system": system,
        "prompt": user,
        "format": "json",
        "options": {"temperature": 0.0, "top_p": 1.0, "num_predict": OLLAMA_MAX_TOKENS},
        "stream": False,
    }

    url = f"{OLLAMA_BASE_URL}/api/generate"
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    text = (r.json().get("response") or "").strip()

    def _parse_questions(s: str) -> List[Dict[str, str]]:
        parsed = json.loads(s)
        if not isinstance(parsed, list):
            raise ValueError("LLM did not return a JSON array.")
        out: List[Dict[str, str]] = []
        for item in parsed:
            if isinstance(item, dict) and "question" in item and isinstance(item["question"], str):
                out.append({"question": item["question"]})
        return out

    try:
        return _parse_questions(text)
    except Exception:
        # Retry once with stricter reminder
        payload["prompt"] = user + '\n\nReturn a VALID JSON array of objects with only the key "question".'
        r2 = requests.post(url, json=payload, timeout=60)
        r2.raise_for_status()
        text2 = (r2.json().get("response") or "").strip()
        return _parse_questions(text2)


def _post_normalize(questions: List[Dict[str, str]]) -> List[Dict[str, str]]:
    # Trim, drop too short/long, dedupe
    seen = set()
    cleaned: List[Dict[str, str]] = []
    for q in questions:
        s = _normspace(q.get("question", ""))
        if 5 <= len(s) <= 200 and s.lower() not in seen:
            seen.add(s.lower())
            cleaned.append({"question": s})
    # Enforce 5..10 items
    if len(cleaned) > 10:
        cleaned = cleaned[:10]
    return cleaned


# -------------------- public API --------------------
def generate_questions(jd: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate 5..10 concise questions from a JD JSON and persist to /storage/questions/<uuid>.json.
    Returns:
      {
        "questions": [...],
        "storage_path": "<abs path to saved json>",
        "id": "<uuid>"
      }
    """
    basics = (jd.get("job_profile") or {}).get("basics") or {}
    role_title = _normspace(basics.get("title", ""))
    company = _normspace(basics.get("company", ""))

    seeds = _extract_seed_skills(jd, k=10)
    questions = _ollama_generate_questions(role_title, company, seeds)
    questions = _post_normalize(questions)

    if len(questions) < 5:
        raise ValueError("Generated fewer than 5 questions after normalization.")

    qid = str(uuid.uuid4())
    payload = {
        "id": qid,
        "role_title": role_title,
        "company": company,
        "seed_skills": seeds,
        "questions": questions,
    }

    # Preferred: use storage utils; Fallback: local atomic write
    storage_path: str
    if _HAS_STORAGE_UTILS and callable(persist_questions):  # type: ignore
        try:
            info = persist_questions(qid, payload)  # expected to return {"path": "..."} (or similar)
            # Support both {"path": "..."} and {"json_path": "..."} shapes
            storage_path = info.get("path") or info.get("json_path") or info.get("storage_path")  # type: ignore
            if not storage_path:
                raise RuntimeError("persist_questions returned no path.")
        except Exception:
            # fallback to local atomic write
            out_dir = os.path.abspath(os.path.join(os.getcwd(), "storage", "questions"))
            storage_path = os.path.join(out_dir, f"{qid}.json")
            _atomic_write_json(storage_path, payload)
    else:
        out_dir = os.path.abspath(os.path.join(os.getcwd(), "storage", "questions"))
        storage_path = os.path.join(out_dir, f"{qid}.json")
        _atomic_write_json(storage_path, payload)

    return {"questions": questions, "storage_path": storage_path, "id": qid}
