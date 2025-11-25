# app/services/kpi_chat.py
"""
KPI Chat Assistant — single-PDF, session-scoped Q&A via OpenRouter.
- Accepts a PDF (<= 20 MB), extracts text with PyMuPDF.
- Caches trimmed context (first 12k chars) and last 3 Q↔A pairs per session.
- Answers strictly from the report content using an OpenRouter chat completion.

ENV:
  OPENROUTER_API_KEY       (required)
  OPENROUTER_MODEL_KPI     (default: 'deepseek/deepseek-chat:free')

Constraints:
  - PDF only for this module.
  - Temperature 0.0 (deterministic).
  - No external retrieval; single-document only.
"""

from __future__ import annotations
import os
import json
import uuid
from typing import Dict, Any, List, Tuple

import fitz  # PyMuPDF
import requests

from app.utils.storage_utils import persist_kpi_pdf

MAX_BYTES = 20 * 1024 * 1024  # 20 MB
TRIM_CHARS = 12_000

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL_KPI = os.getenv("OPENROUTER_MODEL_KPI", "deepseek/deepseek-chat:free")
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# In-memory session store:
# { session_id: {"text": str, "history": [(q,a),...], "pages": int, "path": str, "bytes": int} }
_SESSIONS: Dict[str, Dict[str, Any]] = {}


# -------- PDF helpers --------
def _extract_pdf_text(pdf_bytes: bytes) -> Tuple[str, int]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = doc.page_count
    parts: List[str] = []
    for i in range(pages):
        page = doc.load_page(i)
        # plain text extraction
        parts.append(page.get_text())
        if i < pages - 1:
            parts.append(f"\n\n--- PAGE {i+1} ---\n\n")
    text = "".join(parts)
    return text, pages


# -------- Public API --------
def load_pdf_and_create_session(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    # Basic checks
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Unsupported file type. Only .pdf accepted for KPI Chat.")
    if len(file_bytes) > MAX_BYTES:
        raise ValueError("File too large. Max 20 MB.")

    # New session id
    sid = str(uuid.uuid4())

    # Persist the PDF via centralized storage utils
    # -> writes /kpi/<sid>.pdf and returns {"path": "..."}
    persisted = persist_kpi_pdf(session_id=sid, filename=filename, raw_bytes=file_bytes)
    out_path = persisted["path"]

    # Extract & trim
    full_text, pages = _extract_pdf_text(file_bytes)
    trimmed = (full_text[:TRIM_CHARS]).strip()

    # Cache session context
    _SESSIONS[sid] = {
        "text": trimmed,
        "history": [],          # list[(q, a)]
        "pages": pages,
        "path": out_path,
        "bytes": len(file_bytes),
    }

    # Let the caller (FastAPI route) shape the final response
    return {
        "session_id": sid,
        "pages": pages,
        "bytes": len(file_bytes),
        "storage_path": out_path,
    }


def _build_messages(context_text: str, history: List[Tuple[str, str]], user_q: str) -> List[Dict[str, str]]:
    system_prompt = (
        "You are an HR analytics assistant. Answer strictly and only from the provided report text. "
        'If the answer is not present, say "I can\'t find that in the report."'
    )

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    # Include last up to 3 Q↔A pairs to keep short memory
    for q, a in history[-3:]:
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})

    # Provide the report content + the current question together
    user_blob = (
        "REPORT CONTEXT (use this only):\n"
        f"{context_text}\n\n"
        "USER QUESTION:\n"
        f"{user_q}\n\n"
        "Answer only from the report context above."
    )
    messages.append({"role": "user", "content": user_blob})
    return messages


def _openrouter_chat(messages: List[Dict[str, str]]) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("Missing OPENROUTER_API_KEY env var.")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL_KPI,
        "messages": messages,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 800,
    }
    r = requests.post(_OPENROUTER_URL, headers=headers, json=payload, timeout=60)

    # Raise HTTP errors with full body to help debugging
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"OpenRouter error {r.status_code}: {r.text}") from e

    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(f"Unexpected OpenRouter response: {json.dumps(data)[:500]}")


def ask_question(session_id: str, question: str) -> str:
    sess = _SESSIONS.get(session_id)
    if not sess:
        raise KeyError("Unknown session_id.")

    context_text: str = sess["text"]
    history: List[Tuple[str, str]] = sess["history"]

    messages = _build_messages(context_text, history, question)
    answer = _openrouter_chat(messages).strip()

    # Update history (limit to last 3 pairs)
    history.append((question.strip(), answer))
    if len(history) > 3:
        del history[:-3]
    sess["history"] = history

    return answer
