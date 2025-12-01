# backend/app/main.py
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from jsonschema.exceptions import ValidationError

# storage tree bootstrap
from app.utils.storage_utils import ensure_storage_tree, persist_cv_artifacts, persist_jd_artifacts, STORAGE_ROOT
from app.utils import history_store

# service modules
from app.services import cv_parser, jd_parser, evaluator, matcher, test_generator, kpi_chat

# ---- .env loading made robust across encodings (fixes UnicodeDecodeError) ----
_env_path = find_dotenv(usecwd=True)
if _env_path:
    try:
        load_dotenv(_env_path, override=False, encoding="utf-8")
    except UnicodeDecodeError:
        try:
            load_dotenv(_env_path, override=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            load_dotenv(_env_path, override=False, encoding="utf-16")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
# hard timeout (seconds) for long-running parser threads
PARSER_TIMEOUT = float(os.getenv("PARSER_TIMEOUT_SECONDS", "60"))
# admin bootstrap from env so creds live in .env
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_DISPLAY_NAME = os.getenv("ADMIN_DISPLAY_NAME", "Administrator")
ADMIN_ROLES = [
    r.strip()
    for r in (os.getenv("ADMIN_ROLES", "admin,user") or "admin,user").split(",")
    if r.strip()
]
# also allow the 127.0.0.1 alias to avoid CORS surprises in CRA dev
_frontend_origins = {FRONTEND_ORIGIN}
if "localhost" in FRONTEND_ORIGIN:
    _frontend_origins.add(FRONTEND_ORIGIN.replace("localhost", "127.0.0.1"))
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
SUPPORTED_EXT = {".pdf", ".docx", ".txt"}
# simple in-memory user/session store
USERS = {
    ADMIN_USERNAME: {
        "password": ADMIN_PASSWORD,
        "roles": ADMIN_ROLES,
        "display_name": ADMIN_DISPLAY_NAME,
    }
}
SESSIONS = {}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# make sure /storage tree exists at startup
ensure_storage_tree()


def _ext_ok(filename: str) -> bool:
    _, ext = os.path.splitext((filename or "").lower())
    return ext in SUPPORTED_EXT


def _auth_from_header(req: Request) -> str:
    auth = req.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def _serialize_user(username: str, rec: dict) -> dict:
    return {
        "username": username,
        "roles": rec.get("roles") or [],
        "display_name": rec.get("display_name") or "",
    }


def _require_auth(req: Request) -> tuple[str, dict]:
    token = _auth_from_header(req)
    if not token or token not in SESSIONS:
        raise HTTPException(status_code=401, detail="Unauthorized")
    username = SESSIONS[token]
    rec = USERS.get(username)
    if not rec:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return username, rec


def _require_admin(req: Request) -> tuple[str, dict]:
    username, rec = _require_auth(req)
    if "admin" not in (rec.get("roles") or []):
        raise HTTPException(status_code=403, detail="Admin required")
    return username, rec


def _admin_count(exclude: str | None = None) -> int:
    return sum(
        1
        for u, r in USERS.items()
        if u != exclude and "admin" in (r.get("roles") or [])
    )


def _update_session_usernames(old_username: str, new_username: str):
    if old_username == new_username:
        return
    for tok, uname in list(SESSIONS.items()):
        if uname == old_username:
            SESSIONS[tok] = new_username


@app.get("/health")
def health():
    def present(k: str) -> bool:
        v = os.getenv(k)
        return bool(v and v.strip())

    return {
        "status": "ok",
        "env": {
            "OLLAMA_BASE_URL": present("OLLAMA_BASE_URL"),
            "OLLAMA_MODEL_CV": present("OLLAMA_MODEL_CV"),
            "OLLAMA_MODEL_TEST": present("OLLAMA_MODEL_TEST"),
            "SENTENCE_TRANSFORMERS_MODEL": present("SENTENCE_TRANSFORMERS_MODEL"),
            "OPENROUTER_API_KEY": present("OPENROUTER_API_KEY"),
            "OPENROUTER_MODEL_KPI": present("OPENROUTER_MODEL_KPI"),
        },
        "routes": sorted({r.path for r in app.routes}),
    }

# ---------- HISTORY & SUMMARY ----------
@app.get("/history")
def get_history(limit: int = 50, kind: str | None = None):
    try:
        limit = max(1, min(int(limit), 500))
    except Exception:
        limit = 50
    return {"items": history_store.list_events(limit=limit, kind=kind)}


@app.get("/dashboard/summary")
def dashboard_summary():
    return history_store.summary()


# ---------- STORAGE FILE SERVING ----------
@app.get("/storage/file")
def get_storage_file(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    base = STORAGE_ROOT.resolve()
    p = Path(path)
    if not p.is_absolute():
        p = base / p
    try:
        rp = p.resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    if base not in rp.parents and rp != base:
        raise HTTPException(status_code=403, detail="Access denied")
    if not rp.exists() or not rp.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(rp), filename=rp.name)


# ---------- CV PARSER ----------
@app.post("/cv/parse")
async def cv_parse(file: UploadFile = File(...)):
    if not _ext_ok(file.filename):
        raise HTTPException(status_code=415, detail="Unsupported file type")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20MB)")
    req_id = str(uuid.uuid4())

    try:
        # Pas de timeout explicite : on attend la reponse du parser
        cv_json, raw_text = await asyncio.to_thread(cv_parser.parse_cv, file.filename, raw, req_id)
        eval_json = evaluator.evaluate(parsed_json=cv_json, raw_text=raw_text, kind="cv")
        storage_paths = persist_cv_artifacts(req_id, file.filename, raw, cv_json)
        history_store.append_event(
            "cv_parse",
            {
                "request_id": req_id,
                "filename": file.filename,
                "storage": storage_paths,
                "evaluation": eval_json,
            },
        )
        return {
            "cv": cv_json,
            "evaluation": eval_json,
            "request_id": req_id,
            "storage": storage_paths,
        }
    except cv_parser.SchemaError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Schema validation failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV parse failed: {e}")


# ---------- JD PARSER ----------
@app.post("/jd/parse")
async def jd_parse(file: UploadFile = File(...)):
    if not _ext_ok(file.filename):
        raise HTTPException(status_code=415, detail="Unsupported file type")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20MB)")
    req_id = str(uuid.uuid4())

    try:
        # Pas de timeout explicite : on attend la reponse du parser
        jd_json, raw_text = await asyncio.to_thread(jd_parser.parse_jd, file.filename, raw, req_id)
        eval_json = evaluator.evaluate(parsed_json=jd_json, raw_text=raw_text, kind="jd")
        storage_paths = persist_jd_artifacts(req_id, file.filename, raw, jd_json)
        history_store.append_event(
            "jd_parse",
            {
                "request_id": req_id,
                "filename": file.filename,
                "storage": storage_paths,
                "evaluation": eval_json,
            },
        )
        return {
            "jd": jd_json,
            "evaluation": eval_json,
            "request_id": req_id,
            "storage": storage_paths,
        }
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Schema validation failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD parse failed: {e}")


# ---------- MATCHING ----------
class MatchBody(BaseModel):
    cv: dict
    jd: dict
    weights: dict | None = None


@app.post("/match")
def post_match(body: MatchBody):
    req_id = str(uuid.uuid4())
    try:
        result = matcher.match(body.cv, body.jd, weights=body.weights)
        history_store.append_event(
            "match",
            {"request_id": req_id, "result": result, "weights": body.weights},
        )
        return {"result": result, "request_id": req_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching failed: {e}")


class BulkMatchBody(BaseModel):
    cvs: list[dict]
    jd: dict
    weights: dict | None = None


@app.post("/match/bulk")
def post_match_bulk(body: BulkMatchBody):
    """
    Match a single JD against multiple CVs in one call (hard-capped to 100 CVs).
    """
    cvs = body.cvs or []
    if not cvs:
        raise HTTPException(status_code=400, detail="At least one CV is required")
    if len(cvs) > 100:
        raise HTTPException(status_code=400, detail="Too many CVs; max allowed is 100")

    req_id = str(uuid.uuid4())
    results = []
    for idx, cv in enumerate(cvs):
        try:
            match_res = matcher.match(cv, body.jd, weights=body.weights)
            results.append({"index": idx, "result": match_res})
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Matching failed for CV #{idx + 1}: {e}"
            )

    history_store.append_event(
        "match_bulk",
        {"request_id": req_id, "count": len(results), "results": results},
    )

    return {"results": results, "count": len(results), "request_id": req_id}


# ---------- TEST GENERATOR ----------
class TestBody(BaseModel):
    jd: dict


@app.post("/tests/generate")
def tests_generate(body: TestBody):
    req_id = str(uuid.uuid4())
    try:
        res = test_generator.generate_questions(body.jd)
        history_store.append_event(
            "test_generate",
            {
                "request_id": req_id,
                "storage": {"path": res.get("storage_path")},
                "count": len(res.get("questions") or []),
            },
        )
        return {
            "questions": res["questions"],
            "request_id": req_id,
            "storage": {"path": res["storage_path"]},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test generation failed: {e}")


# ---------- KPI CHAT ----------
@app.post("/kpi/load")
async def kpi_load(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF supported for KPI chat")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20MB)")
    req_id = str(uuid.uuid4())
    try:
        meta = kpi_chat.load_pdf_and_create_session(filename=file.filename, file_bytes=raw)
        meta["request_id"] = req_id
        return meta
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KPI load failed: {e}")


class AskBody(BaseModel):
    session_id: str
    question: str


@app.post("/kpi/ask")
def kpi_ask(body: AskBody):
    req_id = str(uuid.uuid4())
    try:
        ans = kpi_chat.ask_question(body.session_id, body.question)
        return {"answer": ans, "request_id": req_id}
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KPI question failed: {e}")


# ---------- optional root ----------
@app.get("/")
def root():
    return {"ok": True}


# ---------- AUTH & USER MANAGEMENT ----------
class LoginBody(BaseModel):
    username: str
    password: str


class CreateUserBody(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    roles: list[str] | None = None


class UpdateUserBody(BaseModel):
    new_username: str | None = None
    password: str | None = None
    display_name: str | None = None
    roles: list[str] | None = None


class UpdateSelfBody(BaseModel):
    password: str | None = None
    display_name: str | None = None


@app.post("/login")
def login(body: LoginBody):
    rec = USERS.get(body.username)
    if not rec or rec.get("password") != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = str(uuid.uuid4())
    SESSIONS[token] = body.username
    return {"token": token, "user": _serialize_user(body.username, rec)}


@app.get("/users")
def list_users(req: Request):
    _require_admin(req)
    return [
        _serialize_user(u, r)
        for u, r in sorted(USERS.items(), key=lambda x: x[0].lower())
    ]


@app.post("/users")
def create_user(body: CreateUserBody, req: Request):
    _require_admin(req)
    if body.username in USERS:
        raise HTTPException(status_code=409, detail="User already exists")
    roles = body.roles or ["user"]
    USERS[body.username] = {
        "password": body.password,
        "roles": roles,
        "display_name": body.display_name or "",
    }
    return _serialize_user(body.username, USERS[body.username])


@app.patch("/users/{username}")
def update_user(username: str, body: UpdateUserBody, req: Request):
    _require_admin(req)
    rec = USERS.get(username)
    if not rec:
        raise HTTPException(status_code=404, detail="User not found")

    # handle username change
    new_username = body.new_username or username
    if new_username != username and new_username in USERS:
        raise HTTPException(status_code=409, detail="Username already taken")

    # roles update with admin safety
    new_roles = body.roles if body.roles is not None else rec.get("roles") or []
    if "admin" not in new_roles and "admin" in (rec.get("roles") or []):
        # ensure at least one admin remains
        if _admin_count(exclude=username) == 0:
            raise HTTPException(status_code=400, detail="Cannot remove last admin")

    updated = {
        "password": body.password if body.password is not None else rec.get("password"),
        "roles": new_roles,
        "display_name": body.display_name if body.display_name is not None else rec.get("display_name", ""),
    }

    # apply rename if needed
    if new_username != username:
        del USERS[username]
        USERS[new_username] = updated
        _update_session_usernames(username, new_username)
        username = new_username
    else:
        USERS[username] = updated

    return _serialize_user(username, USERS[username])


@app.delete("/users/{username}")
def delete_user(username: str, req: Request):
    _require_admin(req)
    rec = USERS.get(username)
    if not rec:
        raise HTTPException(status_code=404, detail="User not found")
    if "admin" in (rec.get("roles") or []) and _admin_count(exclude=username) == 0:
        raise HTTPException(status_code=400, detail="Cannot delete last admin")
    del USERS[username]
    # remove sessions for this user
    for tok, uname in list(SESSIONS.items()):
        if uname == username:
            del SESSIONS[tok]
    return {"ok": True}


@app.patch("/users/me")
def update_self(body: UpdateSelfBody, req: Request):
    username, rec = _require_auth(req)
    if body.password is not None:
        rec["password"] = body.password
    if body.display_name is not None:
        rec["display_name"] = body.display_name
    USERS[username] = rec
    return _serialize_user(username, rec)
