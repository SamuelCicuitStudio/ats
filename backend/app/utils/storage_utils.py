from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any

# Resolve /storage at repo root (…/backend/storage)
BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_ROOT = BASE_DIR / "storage"

def ensure_storage_tree() -> None:
    (STORAGE_ROOT / "cv_raw").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "cv_json").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "jd_raw").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "jd_json").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "questions").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "kpi").mkdir(parents=True, exist_ok=True)

def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def persist_cv_artifacts(
    req_id: str,
    original_filename: str,
    raw_bytes: bytes,
    cv_json: Dict[str, Any],
) -> Dict[str, str]:
    ensure_storage_tree()
    ext = os.path.splitext((original_filename or "").lower())[1] or ".bin"
    raw_path = STORAGE_ROOT / "cv_raw" / f"{req_id}{ext}"
    json_path = STORAGE_ROOT / "cv_json" / f"{req_id}.json"
    _atomic_write_bytes(raw_path, raw_bytes)
    _atomic_write_json(json_path, cv_json)
    return {"raw_path": str(raw_path), "json_path": str(json_path)}

def persist_jd_artifacts(
    req_id: str,
    original_filename: str,
    raw_bytes: bytes,
    jd_json: Dict[str, Any],
) -> Dict[str, str]:
    ensure_storage_tree()
    ext = os.path.splitext((original_filename or "").lower())[1] or ".bin"
    raw_path = STORAGE_ROOT / "jd_raw" / f"{req_id}{ext}"
    json_path = STORAGE_ROOT / "jd_json" / f"{req_id}.json"
    _atomic_write_bytes(raw_path, raw_bytes)
    _atomic_write_json(json_path, jd_json)
    return {"raw_path": str(raw_path), "json_path": str(json_path)}

def persist_questions(req_id: str, questions: Any) -> str:
    ensure_storage_tree()
    out_path = STORAGE_ROOT / "questions" / f"{req_id}.json"
    _atomic_write_json(out_path, {"id": req_id, "questions": questions})
    return str(out_path)
# ADD this near your other helpers
def persist_kpi_pdf(session_id: str, filename: str, file_bytes: bytes) -> dict:
    """
    Persist the uploaded KPI PDF to /storage/kpi/<session_id>.pdf (atomic write).
    Returns {"path": "<absolute or project-relative path>"}.
    """
    ensure_storage_tree()  # make sure storage tree exists

    # we force .pdf name based on session_id per spec
    out_dir = os.path.join(STORAGE_ROOT, "kpi")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{session_id}.pdf")

    _atomic_write_bytes(out_path, file_bytes)  # reuse your existing atomic writer
    return {"path": out_path.replace("\\", "/")}
