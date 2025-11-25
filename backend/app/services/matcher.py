# app/services/matcher.py
"""
Matching Engine adapte au schema refcv/refjob generalise.
- Compare titre, competences, certifications, experience et localisation.
- Utilise les embeddings Sentence-Transformers (meme loader que l'evaluator).
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional

import numpy as np

from app.services.evaluator import _get_model  # reuse the shared SBERT loader

DEFAULT_WEIGHTS = {
    "title": 0.25,
    "skills": 0.30,
    "certifications": 0.10,
    "experience": 0.25,
    "location": 0.10,
}

_STOPWORDS = {
    # english
    "a", "an", "and", "the", "or", "of", "for", "with", "in", "to", "on", "by", "at", "from", "as", "is", "are",
    "be", "being", "been", "this", "that", "these", "those", "it", "its", "we", "you", "they", "their", "our", "your",
    "i", "he", "she", "them", "his", "her", "ours", "yours", "will", "can", "should", "may", "must", "might", "not",
    "no", "yes", "but", "if", "else", "than", "then", "so", "such", "per", "job", "role", "position", "requirements",
    "responsibilities", "skills", "experience", "years", "year",
    # french (basic subset)
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "et", "ou", "dans", "au", "aux", "par", "pour", "avec",
    "sur", "en", "est", "sont", "etre", "ayant", "avoir", "sans", "plus", "moins", "ainsi", "dont", "que", "qui",
    "quoi", "poste", "role", "exigences", "responsabilites", "competences", "experience", "ans", "annee", "annees",
}
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _normspace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _lower_dedup(items: Optional[List[str]]) -> List[str]:
    if not items:
        return []
    seen = set()
    out: List[str] = []
    for x in items:
        v = _normspace(x).lower()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _extract_keywords(text: str, k: int = 12) -> List[str]:
    freqs: Dict[str, int] = {}
    for tok in _TOKEN_RE.findall(_normspace(text)):
        t = tok.lower()
        if len(t) < 3 or t in _STOPWORDS:
            continue
        freqs[t] = freqs.get(t, 0) + 1
    ranked = sorted(freqs.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:k]]


def _embed(texts: List[str]) -> np.ndarray:
    m = _get_model()
    return m.encode(texts, normalize_embeddings=True)


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def _mean_pool(vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        raise ValueError("Empty vectors array.")
    mean = vectors.mean(axis=0)
    nrm = np.linalg.norm(mean)
    return mean if nrm == 0 else mean / nrm


def _title_similarity(cv_json: Dict[str, Any], jd_json: Dict[str, Any]) -> float:
    cv_title = _normspace(cv_json.get("poste_actuel", "") or cv_json.get("profil", ""))
    jd_title = _normspace(((jd_json.get("job_profile") or {}).get("basics") or {}).get("title", ""))
    if not cv_title or not jd_title:
        return 0.0
    em = _embed([cv_title, jd_title])
    return _cos(em[0], em[1])


def _skills_similarity(cv_json: Dict[str, Any], jd_json: Dict[str, Any]) -> float:
    cv_sk = _lower_dedup(cv_json.get("competences"))
    jd_sk = _lower_dedup(jd_json.get("competences") or jd_json.get("skills"))
    if not jd_sk:
        jd_sk = _extract_keywords(jd_json.get("jd_text", ""), k=12)
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
    if not jd_c:
        jd_c = _extract_keywords(jd_json.get("jd_text", ""), k=6)
    if not cv_c or not jd_c:
        return 0.0
    em_cv = _embed(cv_c)
    em_jd = _embed(jd_c)
    cv_mean = _mean_pool(em_cv)
    jd_mean = _mean_pool(em_jd)
    return _cos(cv_mean, jd_mean)


def _experience_score(cv_json: Dict[str, Any], jd_json: Dict[str, Any]) -> float:
    try:
        cv_years = float(cv_json.get("annees_experience", 0))
    except Exception:
        cv_years = 0.0
    try:
        jd_req = float(jd_json.get("experience_required_years", 0))
    except Exception:
        jd_req = 0.0
    if jd_req <= 0:
        return 1.0 if cv_years > 0 else 0.0
    return float(min(cv_years / jd_req, 1.0))


def _location_score(cv_json: Dict[str, Any], jd_json: Dict[str, Any]) -> float:
    loc = _normspace(cv_json.get("localisation", "")).lower()
    jd_text = _normspace(jd_json.get("jd_text", "")).lower()
    if not loc or not jd_text or len(loc) < 3:
        return 0.0
    return 1.0 if loc in jd_text else 0.0


def compute_match(
    cv_json: Dict[str, Any],
    jd_json: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    scores = {
        "title": _title_similarity(cv_json, jd_json),
        "skills": _skills_similarity(cv_json, jd_json),
        "certifications": _certs_similarity(cv_json, jd_json),
        "experience": _experience_score(cv_json, jd_json),
        "location": _location_score(cv_json, jd_json),
    }

    global_score = sum(w[k] * scores[k] for k in scores)

    return {
        "candidate_name": _normspace(f"{cv_json.get('prenom', '')} {cv_json.get('nom', '')}"),
        "cv_title": _normspace(cv_json.get("poste_actuel", "") or cv_json.get("profil", "")),
        "jd_title": _normspace(((jd_json.get("job_profile") or {}).get("basics") or {}).get("title", "")),
        "scores": {k: round(v, 4) for k, v in scores.items()},
        "global_score": round(float(global_score), 4),
    }


def match(cv_json: Dict[str, Any], jd_json: Dict[str, Any], weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Alias attendu par main.py.
    """
    return compute_match(cv_json=cv_json, jd_json=jd_json, weights=weights)
