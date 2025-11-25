# app/services/matcher.py
"""
Matching Engine
- Computes component scores (title, skills, certifications, experience, location)
  and a global score for CV vs JD using SBERT embeddings (same model as evaluator).
- Deterministic: no randomness, same inputs → same outputs.

Weights default (can be overridden per request):
  { "title":0.25, "skills":0.25, "certifications":0.15, "experience":0.20, "location":0.05 }
"""

from __future__ import annotations
import math
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import numpy as np
from dateutil import parser as dateparse

# Reuse the same model loader used by the evaluator
from app.services.evaluator import _get_model  # uses SENTENCE_TRANSFORMERS_MODEL

DEFAULT_WEIGHTS = {
    "title": 0.25,
    "skills": 0.25,
    "certifications": 0.15,
    "experience": 0.20,
    "location": 0.05,
}

# ---------- small utils ----------
def _normspace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _lower_dedup(items: Optional[List[str]]) -> List[str]:
    if not items:
        return []
    seen = set()
    out = []
    for x in items:
        v = _normspace(x).lower()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out

def _embed(texts: List[str]) -> np.ndarray:
    """
    Encode 1 or many strings with normalized embeddings.
    Returns array shape (n, d). If n == 1, still (1, d).
    """
    m = _get_model()
    return m.encode(texts, normalize_embeddings=True)

def _cos(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    # both should already be L2-normalized
    return float(np.dot(vec_a, vec_b))

def _mean_pool(vectors: np.ndarray) -> np.ndarray:
    """
    vectors: (n, d) of unit vectors → mean + renormalize to unit length
    """
    if vectors.size == 0:
        raise ValueError("Empty vectors array.")
    mean = vectors.mean(axis=0)
    nrm = np.linalg.norm(mean)
    if nrm == 0:
        return mean
    return mean / nrm

# ---------- component scorers ----------
def _title_similarity(cv_json: Dict[str, Any], jd_json: Dict[str, Any]) -> float:
    cv_title = _normspace(((cv_json.get("profile") or {}).get("basics") or {}).get("current_title", ""))
    jd_title = _normspace(((jd_json.get("job_profile") or {}).get("basics") or {}).get("title", ""))
    if not cv_title or not jd_title:
        return 0.0
    em = _embed([cv_title, jd_title])
    return _cos(em[0], em[1])

def _skills_similarity(cv_json: Dict[str, Any], jd_json: Dict[str, Any]) -> float:
    cv_sk = _lower_dedup(cv_json.get("skills"))
    jd_sk = _lower_dedup(jd_json.get("skills"))
    if not cv_sk or not jd_sk:
        return 0.0
    em_cv = _embed(cv_sk)
    em_jd = _embed(jd_sk)
    cv_mean = _mean_pool(em_cv)
    jd_mean = _mean_pool(em_jd)
    return _cos(cv_mean, jd_mean)

def _certs_similarity(cv_json: Dict[str, Any], jd_json: Dict[str, Any]) -> float:
    cv_c = _lower_dedup(cv_json.get("certifications"))
    jd_c = _lower_dedup(jd_json.get("required_certifications"))
    if not cv_c or not jd_c:
        return 0.0
    em_cv = _embed(cv_c)
    em_jd = _embed(jd_c)
    cv_mean = _mean_pool(em_cv)
    jd_mean = _mean_pool(em_jd)
    return _cos(cv_mean, jd_mean)

def _to_date_or_none(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return dateparse.parse(s)
    except Exception:
        return None

def _cv_experience_years(cv_json: Dict[str, Any]) -> float:
    total_months = 0
    today = datetime.utcnow()
    for e in (cv_json.get("experience") or []):
        # prefer pre-computed duration_months if present
        dm = e.get("duration_months")
        if isinstance(dm, int) and dm >= 0:
            total_months += dm
            continue
        # else compute from dates
        s = _to_date_or_none(e.get("start_date"))
        e_ = _to_date_or_none(e.get("end_date")) or today
        if s:
            months = (e_.year - s.year) * 12 + (e_.month - s.month)
            if months > 0:
                total_months += months
    yrs = total_months / 12.0
    # clamp sane range
    return max(0.0, min(40.0, yrs))

def _experience_score(cv_json: Dict[str, Any], jd_json: Dict[str, Any]) -> float:
    cv_years = _cv_experience_years(cv_json)
    jd_req = jd_json.get("experience_required_years")
    try:
        jd_years = float(jd_req) if jd_req is not None else 0.0
    except Exception:
        jd_years = 0.0

    if jd_years <= 0.0:
        return 1.0
    return float(min(cv_years / jd_years, 1.0))

def _location_score(cv_json: Dict[str, Any], jd_json: Dict[str, Any]) -> float:
    """
    1.0 if the CV location is a substring of JD text (very simple heuristic).
    Else 0.0. If either missing, 0.0.
    """
    loc = _normspace(((cv_json.get("profile") or {}).get("basics") or {}).get("location", "")).lower()
    jd_text = _normspace(jd_json.get("jd_text", "")).lower()
    if not loc or not jd_text:
        return 0.0
    # Require at least 3 chars to avoid matching "LA" etc.
    if len(loc) < 3:
        return 0.0
    return 1.0 if loc in jd_text else 0.0

# ---------- public API ----------
def compute_match(
    cv_json: Dict[str, Any],
    jd_json: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    scores = {
        "title": _title_similarity(cv_json, jd_json),
        "skills": _skills_similarity(cv_json, jd_json),
        "certifications": _certs_similarity(cv_json, jd_json),
        "experience": _experience_score(cv_json, jd_json),
        "location": _location_score(cv_json, jd_json),
    }

    # Weighted sum
    global_score = (
        w["title"] * scores["title"]
        + w["skills"] * scores["skills"]
        + w["certifications"] * scores["certifications"]
        + w["experience"] * scores["experience"]
        + w["location"] * scores["location"]
    )

    # Presentation rounding (keep raw too if you need)
    result = {
        "candidate_name": _normspace(
            f"{((cv_json.get('profile') or {}).get('basics') or {}).get('first_name', '')} "
            f"{((cv_json.get('profile') or {}).get('basics') or {}).get('last_name', '')}"
        ),
        "cv_title": _normspace(((cv_json.get("profile") or {}).get("basics") or {}).get("current_title", "")),
        "jd_title": _normspace(((jd_json.get("job_profile") or {}).get("basics") or {}).get("title", "")),
        "scores": {k: round(v, 4) for k, v in scores.items()},
        "global_score": round(float(global_score), 4),
    }
    return result
