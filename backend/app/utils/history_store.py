from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.utils.storage_utils import STORAGE_ROOT, ensure_storage_tree

HISTORY_DIR = STORAGE_ROOT / "history"
HISTORY_FILE = HISTORY_DIR / "history.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_history_file():
    ensure_storage_tree()
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("", encoding="utf-8")


def append_event(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Append a history event to history.jsonl.
    """
    _ensure_history_file()
    event = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "created_at": _now_iso(),
        "payload": payload,
    }
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def list_events(limit: int = 50, kind: str | None = None) -> List[Dict[str, Any]]:
    _ensure_history_file()
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if kind and ev.get("kind") != kind:
            continue
        out.append(ev)
        if len(out) >= limit:
            break
    return out


def summary() -> Dict[str, Any]:
    """
    Simple aggregation: counts per kind and recents.
    """
    events = list_events(limit=200)
    counts: Dict[str, int] = {}
    recents: Dict[str, List[Dict[str, Any]]] = {}
    for ev in events:
        k = ev.get("kind", "unknown")
        counts[k] = counts.get(k, 0) + 1
        recents.setdefault(k, [])
        if len(recents[k]) < 5:
            recents[k].append(ev)
    return {"counts": counts, "recents": recents}
