# app/services/evaluator.py
"""
Parsing Evaluator base sur refcv/refjob generalises.
- Compare les champs extraits au texte brut via similarite semantique
  (Sentence-Transformers all-MiniLM-L6-v2 par defaut).
- Retourne des scores par champ et un score global, sans muter parsed_json.
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
    "company": 0.8,
    "skills": 1.0,
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
    Build per-field strings for CV evaluation (refcv schema).
    """
    out: Dict[str, List[str]] = {}

    fn = _normspace(parsed.get("prenom", ""))
    ln = _normspace(parsed.get("nom", ""))
    name = _normspace(f"{fn} {ln}".strip())
    if name:
        out["name"] = [name]

    title = _normspace(parsed.get("poste_actuel", "") or parsed.get("profil", ""))
    if title:
        out["title"] = [title]

    skills = parsed.get("competences") or []
    if isinstance(skills, list) and skills:
        joined = ", ".join(sorted({_normspace(s).lower() for s in skills if _normspace(s)}))
        if joined:
            out["skills"] = [joined]

    try:
        exp_val = float(parsed.get("annees_experience", 0))
        if exp_val > 0:
            out["experience"] = [str(exp_val)]
    except Exception:
        pass

    eds: List[str] = []
    for d in (parsed.get("diplomes") or []):
        s = _normspace(d)
        if len(s) >= 3:
            eds.append(s)
    for e in (parsed.get("ecoles") or []):
        s = _normspace(e)
        if len(s) >= 3:
            eds.append(s)
    if eds:
        out["education"] = [", ".join(eds)]

    certs = parsed.get("certifications") or []
    if isinstance(certs, list) and certs:
        joined = ", ".join(sorted({_normspace(c) for c in certs if _normspace(c)}))
        if joined:
            out["certifications"] = [joined]

    return out


def _jd_field_strings(parsed: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Build per-field strings for JD evaluation (refjob schema).
    """
    out: Dict[str, List[str]] = {}
    basics = (parsed.get("job_profile") or {}).get("basics") or {}

    title = _normspace(basics.get("title", ""))
    if title:
        out["title"] = [title]

    company = _normspace(basics.get("company", ""))
    if company:
        out["company"] = [company]

    skills = parsed.get("skills") or parsed.get("competences") or []
    if isinstance(skills, list) and skills:
        joined = ", ".join(sorted({_normspace(s).lower() for s in skills if _normspace(s)}))
        if joined:
            out["skills"] = [joined]

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
    Evaluate parsing quality for CV or JD.
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


def evaluate(parsed_json: Dict[str, Any], raw_text: str, kind: str) -> Dict[str, Any]:
    """
    Alias attendu par le reste de l'application.
    """
    return evaluate_parsing(kind=kind, parsed_json=parsed_json, raw_text=raw_text)
