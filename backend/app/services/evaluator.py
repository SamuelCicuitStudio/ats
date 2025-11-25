# app/services/evaluator.py
"""
Parsing Evaluator
- Compares parsed fields against the original raw_text using semantic similarity
  with Sentence-Transformers (all-MiniLM-L6-v2 by default).
- Returns per-field scores, weights, statuses + a global score/status.
- Never mutates the provided parsed_json.

Spec:
  - Fields (CV): name, title, skills, experience (avg over entries), education, certifications
  - Fields (JD): title, skills, certifications, experience_years
  - Thresholds: excellent ≥ 0.85, good ≥ 0.70, else bad
  - Global score: weighted mean of available fields
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

# ---------------- Config ----------------
ST_MODEL_NAME = os.getenv(
    "SENTENCE_TRANSFORMERS_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

CV_WEIGHTS: Dict[str, float] = {
    "name": 1.0,
    "title": 1.2,
    "skills": 1.5,
    "experience": 1.0,
    "education": 0.6,
    "certifications": 0.7,
}

JD_WEIGHTS: Dict[str, float] = {
    "title": 1.2,
    "skills": 1.5,
    "certifications": 0.7,
    "experience_years": 0.6,
}

EXCELLENT_TH = 0.85
GOOD_TH = 0.70

# --------------- Model (lazy singleton) ---------------
_MODEL: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    """Load the SBERT model once per process."""
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(ST_MODEL_NAME)
    return _MODEL


# --------------- Utils ---------------
def _normspace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _status(score: float) -> str:
    if score >= EXCELLENT_TH:
        return "excellent"
    if score >= GOOD_TH:
        return "good"
    return "bad"


def _embed(text: str) -> Optional[np.ndarray]:
    """
    Returns a normalized embedding for a text string, or None if too short.
    """
    t = _normspace(text)
    if len(t) < 3:
        return None
    m = _get_model()
    vec = m.encode([t], normalize_embeddings=True)[0]
    return vec


def _cos(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    """
    Cosine similarity for already L2-normalized vectors (dot product).
    """
    if a is None or b is None:
        return 0.0
    return float(np.dot(a, b))


def _truncate_context(raw_text: str, max_chars: int = 15_000) -> str:
    raw_text = raw_text or ""
    return raw_text[:max_chars] if len(raw_text) > max_chars else raw_text


# --------------- Field builders ---------------
def _cv_field_strings(parsed: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Build per-field strings for CV evaluation.
    For fields like 'experience' we return a list to average per-entry similarity.
    """
    out: Dict[str, List[str]] = {}
    basics = (parsed.get("profile") or {}).get("basics") or {}

    # name
    fn = _normspace(basics.get("first_name", ""))
    ln = _normspace(basics.get("last_name", ""))
    name = _normspace(f"{fn} {ln}".strip())
    if name:
        out["name"] = [name]

    # title
    title = _normspace(basics.get("current_title", ""))
    if title:
        out["title"] = [title]

    # skills
    skills = parsed.get("skills") or []
    if isinstance(skills, list) and skills:
        # lower, dedupe, alphabetical for stability
        joined = ", ".join(sorted({_normspace(s).lower() for s in skills if _normspace(s)}))
        if joined:
            out["skills"] = [joined]

    # experience (avg across entries)
    exps: List[str] = []
    for e in (parsed.get("experience") or []):
        t = _normspace(e.get("title", ""))
        c = _normspace(e.get("company", ""))
        s = _normspace(f"{t} {c}".strip())
        if len(s) >= 3:
            exps.append(s)
    if exps:
        out["experience"] = exps

    # education (single joined string)
    eds: List[str] = []
    for d in (parsed.get("education") or []):
        deg = _normspace(d.get("degree", ""))
        sch = _normspace(d.get("school", ""))
        s = _normspace(f"{deg} {sch}".strip())
        if len(s) >= 3:
            eds.append(s)
    if eds:
        out["education"] = [", ".join(eds)]

    # certifications
    certs = parsed.get("certifications") or []
    if isinstance(certs, list) and certs:
        joined = ", ".join(sorted({_normspace(c) for c in certs if _normspace(c)}))
        if joined:
            out["certifications"] = [joined]

    return out


def _jd_field_strings(parsed: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Build per-field strings for JD evaluation.
    """
    out: Dict[str, List[str]] = {}
    basics = (parsed.get("job_profile") or {}).get("basics") or {}

    # title
    title = _normspace(basics.get("title", ""))
    if title:
        out["title"] = [title]

    # skills
    skills = parsed.get("skills") or []
    if isinstance(skills, list) and skills:
        joined = ", ".join(sorted({_normspace(s).lower() for s in skills if _normspace(s)}))
        if joined:
            out["skills"] = [joined]

    # certifications
    certs = parsed.get("required_certifications") or []
    if isinstance(certs, list) and certs:
        joined = ", ".join(sorted({_normspace(c) for c in certs if _normspace(c)}))
        if joined:
            out["certifications"] = [joined]

    # experience_years
    yrs = parsed.get("experience_required_years")
    if yrs is not None:
        try:
            yrs_int = int(yrs)
            if yrs_int >= 0:
                out["experience_years"] = [str(yrs_int)]
        except Exception:
            pass

    return out


# --------------- Core evaluation ---------------
def _score_fields(
    field_map: Dict[str, List[str]],
    context_vec: Optional[np.ndarray],
    weights: Dict[str, float],
) -> Tuple[Dict[str, Dict[str, float]], float, str]:
    """
    Compute per-field similarity scores, weighted global score, and global status.
    Missing fields are skipped (no penalty beyond absent weight).
    """
    field_scores: Dict[str, Dict[str, float]] = {}
    total_w = 0.0
    acc = 0.0

    for field, strings in field_map.items():
        if not strings:
            continue

        # Average similarity over list (e.g., multiple experience entries)
        sims: List[float] = []
        for s in strings:
            v = _embed(s)
            sims.append(_cos(v, context_vec))
        score = float(np.mean(sims)) if sims else 0.0

        w = float(weights.get(field, 0.0))
        field_scores[field] = {
            "score": round(score, 4),
            "weight": w,
            "status": _status(score),
        }

        if w > 0.0:
            total_w += w
            acc += w * score

    global_score = (acc / total_w) if total_w > 0 else 0.0
    global_status = _status(global_score)
    return field_scores, round(global_score, 4), global_status


def evaluate_parsing(kind: str, parsed_json: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    """
    Evaluate parsing quality.
    Args:
        kind: "cv" or "jd"
        parsed_json: normalized JSON from the parser
        raw_text: exact extracted text (pre-truncation)
    Returns:
        {
          "field_scores": { "<field>": { "score": float, "weight": float, "status": "excellent|good|bad" }, ... },
          "global_score": float,
          "global_status": "excellent|good|bad"
        }
    """
    ctx = _truncate_context(raw_text or "", 15_000)
    ctx_vec = _embed(ctx)

    if kind.lower() == "cv":
        fmap = _cv_field_strings(parsed_json or {})
        weights = CV_WEIGHTS
    elif kind.lower() == "jd":
        fmap = _jd_field_strings(parsed_json or {})
        weights = JD_WEIGHTS
    else:
        raise ValueError("evaluate_parsing(kind=...) must be 'cv' or 'jd'.")

    field_scores, global_score, global_status = _score_fields(fmap, ctx_vec, weights)
    return {
        "field_scores": field_scores,
        "global_score": round(global_score, 4),
        "global_status": global_status,
    }
