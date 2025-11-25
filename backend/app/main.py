# backend/app/main.py
from __future__ import annotations

import os
import uuid
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jsonschema.exceptions import ValidationError

# storage tree bootstrap
from app.utils.storage_utils import ensure_storage_tree, persist_cv_artifacts, persist_jd_artifacts

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
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
SUPPORTED_EXT = {".pdf", ".docx", ".txt"}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# make sure /storage tree exists at startup
ensure_storage_tree()


def _ext_ok(filename: str) -> bool:
    _, ext = os.path.splitext((filename or "").lower())
    return ext in SUPPORTED_EXT


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
        cv_json, raw_text = cv_parser.parse_cv(file.filename, raw, req_id=req_id)
        eval_json = evaluator.evaluate(parsed_json=cv_json, raw_text=raw_text, kind="cv")
        storage_paths = persist_cv_artifacts(req_id, file.filename, raw, cv_json)
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
        jd_json, raw_text = jd_parser.parse_jd(file.filename, raw, req_id=req_id)
        eval_json = evaluator.evaluate(parsed_json=jd_json, raw_text=raw_text, kind="jd")
        storage_paths = persist_jd_artifacts(req_id, file.filename, raw, jd_json)
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
        return {"result": result, "request_id": req_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching failed: {e}")


# ---------- TEST GENERATOR ----------
class TestBody(BaseModel):
    jd: dict


@app.post("/tests/generate")
def tests_generate(body: TestBody):
    req_id = str(uuid.uuid4())
    try:
        res = test_generator.generate_questions(body.jd)
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
