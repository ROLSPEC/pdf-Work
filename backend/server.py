"""Ugh!PDF backend — auth, tools, AI, billing."""
import os
import io
import uuid
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Annotated

from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, BeforeValidator, ConfigDict
from bson import ObjectId
import bcrypt
import jwt
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

from tools_registry import TOOLS, CATEGORIES, TOOL_MAP
import pdf_ops
import ai_service

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")
FREE_CREDITS = int(os.environ.get("FREE_AI_CREDITS_MONTHLY", "5"))
PAID_CREDITS = int(os.environ.get("PAID_AI_CREDITS_MONTHLY", "50"))
FREE_DAILY = int(os.environ.get("FREE_DAILY_OPS", "10"))
PAID_DAILY = int(os.environ.get("PAID_DAILY_OPS", "200"))
MAX_MB_FREE = int(os.environ.get("MAX_FILE_MB_FREE", "25"))
MAX_MB_PAID = int(os.environ.get("MAX_FILE_MB_PAID", "100"))

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="Ugh!PDF API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ughpdf")


# ============ Models ============
def _oid(v):
    if isinstance(v, ObjectId):
        return str(v)
    return v


PyObjectId = Annotated[str, BeforeValidator(_oid)]


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    plan: str  # "free" | "lifetime"
    ai_credits: int
    ai_credits_reset_at: str
    ops_today: int
    ops_reset_at: str
    byok_openai: bool = False
    byok_gemini: bool = False


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthIn(BaseModel):
    session_id: str


# ============ Auth helpers ============
def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def _token(uid: str) -> str:
    payload = {
        "sub": uid,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _monthly_reset(dt: datetime) -> datetime:
    return (dt + timedelta(days=30))


def _daily_reset(dt: datetime) -> datetime:
    return dt + timedelta(days=1)


async def _ensure_reset(u: dict) -> dict:
    now = _now()
    changed = False
    reset_ai = datetime.fromisoformat(u.get("ai_credits_reset_at", now.isoformat()))
    if now >= reset_ai:
        u["ai_credits"] = PAID_CREDITS if u.get("plan") == "lifetime" else FREE_CREDITS
        u["ai_credits_reset_at"] = _monthly_reset(now).isoformat()
        changed = True
    reset_ops = datetime.fromisoformat(u.get("ops_reset_at", now.isoformat()))
    if now >= reset_ops:
        u["ops_today"] = 0
        u["ops_reset_at"] = _daily_reset(now).isoformat()
        changed = True
    if changed:
        await db.users.update_one({"_id": u["_id"]}, {"$set": {
            "ai_credits": u["ai_credits"],
            "ai_credits_reset_at": u["ai_credits_reset_at"],
            "ops_today": u["ops_today"],
            "ops_reset_at": u["ops_reset_at"],
        }})
    return u


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALG])
        uid = payload["sub"]
    except Exception:
        raise HTTPException(401, "Invalid token")
    u = await db.users.find_one({"_id": uid})
    if not u:
        raise HTTPException(401, "User not found")
    return await _ensure_reset(u)


def user_public(u: dict) -> dict:
    return {
        "id": u["_id"],
        "email": u["email"],
        "name": u.get("name") or u["email"].split("@")[0],
        "plan": u.get("plan", "free"),
        "ai_credits": u.get("ai_credits", 0),
        "ai_credits_reset_at": u.get("ai_credits_reset_at", _now().isoformat()),
        "ops_today": u.get("ops_today", 0),
        "ops_reset_at": u.get("ops_reset_at", _now().isoformat()),
        "byok_openai": bool(u.get("byok_openai_key")),
        "byok_gemini": bool(u.get("byok_gemini_key")),
    }


async def _create_user(email: str, name: Optional[str], pw_hash: Optional[str], google_sub: Optional[str] = None) -> dict:
    uid = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": uid,
        "email": email.lower(),
        "name": name or email.split("@")[0],
        "password_hash": pw_hash,
        "google_sub": google_sub,
        "plan": "free",
        "ai_credits": FREE_CREDITS,
        "ai_credits_reset_at": _monthly_reset(now).isoformat(),
        "ops_today": 0,
        "ops_reset_at": _daily_reset(now).isoformat(),
        "created_at": now.isoformat(),
    }
    await db.users.insert_one(doc)
    return doc


# ============ Routes: Auth ============
@api.post("/auth/signup")
async def signup(body: SignupIn):
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")
    u = await _create_user(body.email, body.name, _hash_pw(body.password))
    return {"token": _token(u["_id"]), "user": user_public(u)}


@api.post("/auth/login")
async def login(body: LoginIn):
    u = await db.users.find_one({"email": body.email.lower()})
    if not u or not u.get("password_hash") or not _verify_pw(body.password, u["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    u = await _ensure_reset(u)
    return {"token": _token(u["_id"]), "user": user_public(u)}


@api.post("/auth/google")
async def google_auth(body: GoogleAuthIn):
    """Emergent-managed Google OAuth session handshake."""
    import httpx
    url = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
    async with httpx.AsyncClient(timeout=10.0) as hc:
        r = await hc.get(url, headers={"X-Session-ID": body.session_id})
        if r.status_code != 200:
            raise HTTPException(401, "Google session invalid")
        data = r.json()
    email = data.get("email", "").lower()
    if not email:
        raise HTTPException(401, "No email in session")
    u = await db.users.find_one({"email": email})
    if not u:
        u = await _create_user(email, data.get("name"), None, data.get("id"))
    return {"token": _token(u["_id"]), "user": user_public(u)}


@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user_public(user)


@api.post("/auth/byok")
async def set_byok(body: dict, user=Depends(get_current_user)):
    update = {}
    if "openai_key" in body:
        update["byok_openai_key"] = body["openai_key"] or None
    if "gemini_key" in body:
        update["byok_gemini_key"] = body["gemini_key"] or None
    if update:
        await db.users.update_one({"_id": user["_id"]}, {"$set": update})
    u = await db.users.find_one({"_id": user["_id"]})
    return user_public(u)


# ============ Tools registry ============
@api.get("/tools")
async def list_tools():
    return {"categories": CATEGORIES, "tools": TOOLS}


@api.get("/tools/{tool_id}")
async def get_tool(tool_id: str):
    t = TOOL_MAP.get(tool_id)
    if not t:
        raise HTTPException(404, "Tool not found")
    return t


# ============ Usage enforcement ============
async def _consume_op(user: dict, credits: int = 0):
    daily_cap = PAID_DAILY if user.get("plan") == "lifetime" else FREE_DAILY
    if user.get("ops_today", 0) >= daily_cap:
        raise HTTPException(429, f"Daily limit reached ({daily_cap}). Upgrade for more.")
    if credits > 0 and user.get("ai_credits", 0) < credits:
        raise HTTPException(402, "Out of AI credits")
    inc = {"ops_today": 1}
    if credits > 0:
        inc["ai_credits"] = -credits
    await db.users.update_one({"_id": user["_id"]}, {"$inc": inc})


async def _read_upload(f: UploadFile, user: dict) -> bytes:
    data = await f.read()
    limit_mb = MAX_MB_PAID if user.get("plan") == "lifetime" else MAX_MB_FREE
    if len(data) > limit_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large. Max {limit_mb}MB on your plan.")
    return data


# ============ Server tools ============
def _pdf_response(data: bytes, name: str = "output.pdf"):
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@api.post("/tools/protect/run")
async def run_protect(file: UploadFile = File(...), password: str = Form(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user)
    out = pdf_ops.protect(data, password)
    return _pdf_response(out, f"protected-{file.filename}")


@api.post("/tools/unlock/run")
async def run_unlock(file: UploadFile = File(...), password: str = Form(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user)
    try:
        out = pdf_ops.unlock(data, password)
    except Exception:
        raise HTTPException(400, "Wrong password or file cannot be unlocked")
    return _pdf_response(out, f"unlocked-{file.filename}")


@api.post("/tools/flatten/run")
async def run_flatten(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user)
    return _pdf_response(pdf_ops.flatten(data), f"flat-{file.filename}")


@api.post("/tools/repair/run")
async def run_repair(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user)
    try:
        out = pdf_ops.repair(data)
    except Exception as e:
        raise HTTPException(400, f"Could not repair: {e}")
    return _pdf_response(out, f"repaired-{file.filename}")


@api.post("/tools/pdf-to-text/run")
async def run_pdf_to_text(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user)
    txt = pdf_ops.to_text_file(data)
    return StreamingResponse(io.BytesIO(txt), media_type="text/plain",
                             headers={"Content-Disposition": f'attachment; filename="{file.filename}.txt"'})


@api.post("/tools/pdf-to-markdown/run")
async def run_pdf_to_md(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user)
    text = pdf_ops.extract_text(data)
    md = "# " + (file.filename or "Document") + "\n\n" + text.replace("[page ", "\n\n## Page ").replace("]\n", "\n\n")
    return StreamingResponse(io.BytesIO(md.encode("utf-8")), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="{file.filename}.md"'})


@api.post("/tools/bates/run")
async def run_bates(file: UploadFile = File(...), prefix: str = Form("BATES"), start: int = Form(1),
                    user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user)
    out = pdf_ops.bates_stamp(data, prefix, start)
    return _pdf_response(out, f"bates-{file.filename}")


@api.post("/tools/exif-strip-server/run")
async def run_strip_meta(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user)
    return _pdf_response(pdf_ops.strip_metadata(data), f"clean-{file.filename}")


# ============ AI Tools ============
class ChatBody(BaseModel):
    question: str


@api.post("/tools/ai-chat/run")
async def ai_chat(file: UploadFile = File(...), question: str = Form(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user, credits=1)
    text = pdf_ops.extract_text(data)
    answer = await ai_service.chat_with_pdf(text, question)
    return {"answer": answer}


@api.post("/tools/ai-summarize/run")
async def ai_summarize(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user, credits=2)
    text = pdf_ops.extract_text(data)
    summary = await ai_service.summarize(text)
    return {"summary": summary}


@api.post("/tools/ai-extract/run")
async def ai_extract(file: UploadFile = File(...), hint: str = Form(""),
                     user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user, credits=3)
    text = pdf_ops.extract_text(data)
    result = await ai_service.extract_structured(text, hint)
    return {"data": result}


@api.post("/tools/ai-redact/run")
async def ai_redact(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user, credits=3)
    text = pdf_ops.extract_text(data)
    findings = await ai_service.ai_pii_verify(text)
    return {"findings": findings, "count": len(findings)}


@api.post("/tools/ai-math/run")
async def ai_math(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user, credits=2)
    text = pdf_ops.extract_text(data)
    solution = await ai_service.solve_math(text)
    return {"solution": solution}


@api.post("/tools/ai-ocr/run")
async def ai_ocr(file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await _read_upload(file, user)
    await _consume_op(user, credits=2)
    pages = pdf_ops.extract_text_by_page(data)
    scanned = [p["page"] for p in pages if len((p.get("text") or "").strip()) < 100]
    already = [p["page"] for p in pages if len((p.get("text") or "").strip()) >= 100]
    return {
        "total_pages": len(pages),
        "scanned_pages": scanned,
        "already_searchable_pages": already,
        "message": f"{len(scanned)} pages need OCR, {len(already)} already searchable (saved credits).",
        "text_by_page": pages,
    }


@api.post("/tools/ai-visual-diff/run")
async def ai_diff(file_a: UploadFile = File(...), file_b: UploadFile = File(...),
                  user=Depends(get_current_user)):
    a = await _read_upload(file_a, user)
    b = await _read_upload(file_b, user)
    await _consume_op(user, credits=3)
    ta = pdf_ops.extract_text(a)
    tb = pdf_ops.extract_text(b)
    result = await ai_service.visual_diff(ta, tb)
    return {"diff": result}


@api.post("/tools/ai-audiobook/run")
async def ai_audiobook(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Stub: real TTS pipeline requires OpenAI audio via emergentintegrations.
    Returns extracted chapters as text with a message."""
    data = await _read_upload(file, user)
    await _consume_op(user, credits=5)
    pages = pdf_ops.extract_text_by_page(data)
    chapters = []
    for i, p in enumerate(pages):
        chapters.append({"chapter": i + 1, "title": f"Page {p['page']}", "text": p["text"][:2000]})
    return {
        "chapters": chapters,
        "note": "MP3 generation coming soon. Chapters extracted and ready for narration.",
    }


# ============ Generic server-tool fallback ============
@api.post("/tools/{tool_id}/run-generic")
async def generic_stub(tool_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    """Fallback: for server tools not yet fully implemented — echoes file back or extracts text."""
    t = TOOL_MAP.get(tool_id)
    if not t:
        raise HTTPException(404, "Unknown tool")
    data = await _read_upload(file, user)
    await _consume_op(user)
    # For text-based conversions, return extracted text as the file
    if tool_id in ("pdf-to-html",):
        txt = pdf_ops.extract_text(data)
        html = f"<html><body><pre>{txt}</pre></body></html>"
        return StreamingResponse(io.BytesIO(html.encode()), media_type="text/html",
                                 headers={"Content-Disposition": f'attachment; filename="{file.filename}.html"'})
    # Default: echo file back
    return _pdf_response(data, f"{tool_id}-{file.filename}")


# ============ Billing (Stripe geo-priced) ============
from billing import build_router as _billing_router
api.include_router(_billing_router(db, get_current_user, PAID_CREDITS))


# ============ Health ============
@api.get("/")
async def root():
    return {"app": "Ugh!PDF", "tools": len(TOOLS)}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
