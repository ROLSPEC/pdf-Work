"""Ugh!PDF backend — auth, tools, jobs, billing (no AI, 24h ephemeral job history)."""
import os
import io
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Annotated

from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, BeforeValidator
from bson import ObjectId
import bcrypt
import jwt
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

from tools_registry import TOOLS, CATEGORIES, TOOL_MAP
import pdf_ops

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")
FREE_DAILY = int(os.environ.get("FREE_DAILY_OPS", "10"))
PAID_DAILY = int(os.environ.get("PAID_DAILY_OPS", "200"))
MAX_MB_FREE = int(os.environ.get("MAX_FILE_MB_FREE", "25"))
MAX_MB_PAID = int(os.environ.get("MAX_FILE_MB_PAID", "100"))
FILE_TTL_HOURS = int(os.environ.get("FILE_TTL_HOURS", "24"))

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="Ugh!PDF API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ughpdf")


# ============ Global settings (admin master control) ============
import time as _time

ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or ""

DEFAULT_SETTINGS = {
    "_id": "global",
    "maintenance_mode": False,
    "gateways": {
        "stripe": {"enabled": True, "mock": True},
        "razorpay": {"enabled": True, "mock": True},
        "paypal": {"enabled": True, "mock": True},
    },
    "disabled_tools": [],
    "disabled_categories": [],
    "limits": {"free_daily_ops": FREE_DAILY, "max_file_mb_free": MAX_MB_FREE},
}

# Effective free-plan limits, refreshed whenever settings are read.
CURRENT_FREE_DAILY = FREE_DAILY
CURRENT_MAX_MB_FREE = MAX_MB_FREE

_settings_cache = {"data": None, "ts": 0.0}


def _merge_settings(doc: dict) -> dict:
    """Fill any missing keys with defaults so old docs stay valid."""
    s = dict(DEFAULT_SETTINGS)
    s.update(doc or {})
    gw = dict(DEFAULT_SETTINGS["gateways"])
    for k, v in (doc or {}).get("gateways", {}).items():
        gw[k] = {**gw.get(k, {}), **(v or {})}
    s["gateways"] = gw
    lim = dict(DEFAULT_SETTINGS["limits"])
    lim.update((doc or {}).get("limits", {}) or {})
    s["limits"] = lim
    return s


async def get_settings(force: bool = False) -> dict:
    global CURRENT_FREE_DAILY, CURRENT_MAX_MB_FREE
    now = _time.time()
    if not force and _settings_cache["data"] and (now - _settings_cache["ts"] < 5):
        return _settings_cache["data"]
    doc = await db.settings.find_one({"_id": "global"})
    if not doc:
        doc = dict(DEFAULT_SETTINGS)
        await db.settings.insert_one(doc)
    s = _merge_settings(doc)
    _settings_cache["data"] = s
    _settings_cache["ts"] = now
    CURRENT_FREE_DAILY = int(s["limits"].get("free_daily_ops", FREE_DAILY))
    CURRENT_MAX_MB_FREE = int(s["limits"].get("max_file_mb_free", MAX_MB_FREE))
    return s


async def save_settings(updates: dict):
    await db.settings.update_one({"_id": "global"}, {"$set": updates}, upsert=True)
    _settings_cache["ts"] = 0.0  # invalidate cache
    await get_settings(force=True)


def _tool_blocked(settings: dict, tool_id: str) -> bool:
    if tool_id in (settings.get("disabled_tools") or []):
        return True
    cat = (TOOL_MAP.get(tool_id) or {}).get("cat")
    if cat and cat in (settings.get("disabled_categories") or []):
        return True
    return False


async def _ensure_tool_enabled(tool_id: str):
    s = await get_settings()
    if _tool_blocked(s, tool_id):
        raise HTTPException(403, "This tool is currently disabled by the administrator.")



# ============ Models ============
def _oid(v):
    if isinstance(v, ObjectId):
        return str(v)
    return v


PyObjectId = Annotated[str, BeforeValidator(_oid)]


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


def _daily_reset(dt: datetime) -> datetime:
    return dt + timedelta(days=1)


async def _ensure_reset(u: dict) -> dict:
    now = _now()
    changed = False
    reset_ops = datetime.fromisoformat(u.get("ops_reset_at", now.isoformat()))
    if now >= reset_ops:
        u["ops_today"] = 0
        u["ops_reset_at"] = _daily_reset(now).isoformat()
        changed = True
    if changed:
        await db.users.update_one({"_id": u["_id"]}, {"$set": {
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
    is_life = u.get("plan") == "lifetime"
    return {
        "id": u["_id"],
        "email": u["email"],
        "name": u.get("name") or u["email"].split("@")[0],
        "plan": u.get("plan", "free"),
        "is_admin": bool(u.get("is_admin")),
        "ops_today": u.get("ops_today", 0),
        "ops_reset_at": u.get("ops_reset_at", _now().isoformat()),
        "max_file_mb": MAX_MB_PAID if is_life else CURRENT_MAX_MB_FREE,
        "daily_ops_limit": PAID_DAILY if is_life else CURRENT_FREE_DAILY,
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


# ============ Tools registry ============
@api.get("/tools")
async def list_tools():
    s = await get_settings()
    return {
        "categories": CATEGORIES,
        "tools": TOOLS,
        "disabled_tools": s.get("disabled_tools", []),
        "disabled_categories": s.get("disabled_categories", []),
    }


@api.get("/config")
async def public_config():
    """Public runtime config for the frontend (maintenance banner + feature toggles)."""
    s = await get_settings()
    return {
        "maintenance_mode": bool(s.get("maintenance_mode")),
        "disabled_tools": s.get("disabled_tools", []),
        "disabled_categories": s.get("disabled_categories", []),
    }


@api.get("/tools/{tool_id}")
async def get_tool(tool_id: str):
    t = TOOL_MAP.get(tool_id)
    if not t:
        raise HTTPException(404, "Tool not found")
    return t


# ============ Usage + Job history (24h auto-expiry) ============
async def _log_job(user: dict, tool_id: str, file: UploadFile, size: int, status: str = "completed", error: Optional[str] = None):
    now = _now()
    engine = (TOOL_MAP.get(tool_id) or {}).get("engine", "server")
    await db.user_jobs.insert_one({
        "_id": str(uuid.uuid4()),
        "user_id": user["_id"],
        "tool_id": tool_id,
        "tool_name": (TOOL_MAP.get(tool_id) or {}).get("name", tool_id),
        "filename": (file.filename or "unknown"),
        "size_bytes": size,
        "engine": engine,
        "status": status,
        "error": error,
        "created_at": now,
        "expires_at": now + timedelta(hours=FILE_TTL_HOURS),
    })


async def _consume_op(user: dict):
    if user.get("plan") == "lifetime":
        daily_cap = PAID_DAILY
    else:
        await get_settings()
        daily_cap = CURRENT_FREE_DAILY
    if user.get("ops_today", 0) >= daily_cap:
        raise HTTPException(429, f"Daily limit reached ({daily_cap}). Upgrade for more.")
    await db.users.update_one({"_id": user["_id"]}, {"$inc": {"ops_today": 1}})


async def _read_upload(f: UploadFile, user: dict) -> bytes:
    data = await f.read()
    if user.get("plan") == "lifetime":
        limit_mb = MAX_MB_PAID
    else:
        await get_settings()
        limit_mb = CURRENT_MAX_MB_FREE
    if len(data) > limit_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large. Max {limit_mb}MB on your plan.")
    return data


@api.get("/user/jobs")
async def list_jobs(user=Depends(get_current_user)):
    """List the current user's recent (< 24h) job history. Metadata only — no file bytes are stored."""
    cursor = db.user_jobs.find({"user_id": user["_id"]}).sort("created_at", -1).limit(200)
    out = []
    async for j in cursor:
        out.append({
            "id": j["_id"],
            "tool_id": j["tool_id"],
            "tool_name": j.get("tool_name"),
            "filename": j.get("filename"),
            "size_bytes": j.get("size_bytes", 0),
            "engine": j.get("engine"),
            "status": j.get("status"),
            "created_at": (j["created_at"].isoformat() if isinstance(j["created_at"], datetime) else j["created_at"]),
            "expires_at": (j["expires_at"].isoformat() if isinstance(j["expires_at"], datetime) else j["expires_at"]),
        })
    return {"jobs": out, "ttl_hours": FILE_TTL_HOURS}


@api.delete("/user/jobs/{job_id}")
async def delete_job(job_id: str, user=Depends(get_current_user)):
    """Let a user delete their own job record."""
    r = await db.user_jobs.delete_one({"_id": job_id, "user_id": user["_id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "Job not found")
    return {"deleted": True}


@api.delete("/user/jobs")
async def delete_all_jobs(user=Depends(get_current_user)):
    """Nuke the user's entire history."""
    r = await db.user_jobs.delete_many({"user_id": user["_id"]})
    return {"deleted": r.deleted_count}


# ============ Server tools ============
def _pdf_response(data: bytes, name: str = "output.pdf"):
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@api.post("/tools/protect/run")
async def run_protect(file: UploadFile = File(...), password: str = Form(...), user=Depends(get_current_user)):
    await _ensure_tool_enabled("protect")
    data = await _read_upload(file, user)
    await _consume_op(user)
    out = pdf_ops.protect(data, password)
    await _log_job(user, "protect", file, len(data))
    return _pdf_response(out, f"protected-{file.filename}")


@api.post("/tools/unlock/run")
async def run_unlock(file: UploadFile = File(...), password: str = Form(...), user=Depends(get_current_user)):
    await _ensure_tool_enabled("unlock")
    data = await _read_upload(file, user)
    await _consume_op(user)
    try:
        out = pdf_ops.unlock(data, password)
    except Exception:
        await _log_job(user, "unlock", file, len(data), status="failed", error="wrong password")
        raise HTTPException(400, "Wrong password or file cannot be unlocked")
    await _log_job(user, "unlock", file, len(data))
    return _pdf_response(out, f"unlocked-{file.filename}")


@api.post("/tools/flatten/run")
async def run_flatten(file: UploadFile = File(...), user=Depends(get_current_user)):
    await _ensure_tool_enabled("flatten")
    data = await _read_upload(file, user)
    await _consume_op(user)
    out = pdf_ops.flatten(data)
    await _log_job(user, "flatten", file, len(data))
    return _pdf_response(out, f"flat-{file.filename}")


@api.post("/tools/repair/run")
async def run_repair(file: UploadFile = File(...), user=Depends(get_current_user)):
    await _ensure_tool_enabled("repair")
    data = await _read_upload(file, user)
    await _consume_op(user)
    try:
        out = pdf_ops.repair(data)
    except Exception as e:
        await _log_job(user, "repair", file, len(data), status="failed", error=str(e)[:100])
        raise HTTPException(400, f"Could not repair: {e}")
    await _log_job(user, "repair", file, len(data))
    return _pdf_response(out, f"repaired-{file.filename}")


@api.post("/tools/pdf-to-text/run")
async def run_pdf_to_text(file: UploadFile = File(...), user=Depends(get_current_user)):
    await _ensure_tool_enabled("pdf-to-text")
    data = await _read_upload(file, user)
    await _consume_op(user)
    txt = pdf_ops.to_text_file(data)
    await _log_job(user, "pdf-to-text", file, len(data))
    return StreamingResponse(io.BytesIO(txt), media_type="text/plain",
                             headers={"Content-Disposition": f'attachment; filename="{file.filename}.txt"'})


@api.post("/tools/pdf-to-markdown/run")
async def run_pdf_to_md(file: UploadFile = File(...), user=Depends(get_current_user)):
    await _ensure_tool_enabled("pdf-to-markdown")
    data = await _read_upload(file, user)
    await _consume_op(user)
    text = pdf_ops.extract_text(data)
    md = "# " + (file.filename or "Document") + "\n\n" + text.replace("[page ", "\n\n## Page ").replace("]\n", "\n\n")
    await _log_job(user, "pdf-to-markdown", file, len(data))
    return StreamingResponse(io.BytesIO(md.encode("utf-8")), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="{file.filename}.md"'})


@api.post("/tools/bates/run")
async def run_bates(file: UploadFile = File(...), prefix: str = Form("BATES"), start: int = Form(1),
                    user=Depends(get_current_user)):
    await _ensure_tool_enabled("bates")
    data = await _read_upload(file, user)
    await _consume_op(user)
    out = pdf_ops.bates_stamp(data, prefix, start)
    await _log_job(user, "bates", file, len(data))
    return _pdf_response(out, f"bates-{file.filename}")


@api.post("/tools/exif-strip-server/run")
async def run_strip_meta(file: UploadFile = File(...), user=Depends(get_current_user)):
    await _ensure_tool_enabled("exif-strip")
    data = await _read_upload(file, user)
    await _consume_op(user)
    await _log_job(user, "exif-strip", file, len(data))
    return _pdf_response(pdf_ops.strip_metadata(data), f"clean-{file.filename}")


@api.post("/tools/pdf-search/run")
async def run_search(file: UploadFile = File(...), query: str = Form(...),
                     k: int = Form(8), user=Depends(get_current_user)):
    """Semantic search over a PDF — no LLM. Returns top-K chunks with page + score."""
    if not query.strip():
        raise HTTPException(400, "Query cannot be empty")
    await _ensure_tool_enabled("pdf-search")
    data = await _read_upload(file, user)
    await _consume_op(user)
    import rag
    fh, chunks, matrix = await rag.get_or_build_index(db, data)
    results = await rag.search(chunks, matrix, query, k=max(1, min(20, int(k))))
    await _log_job(user, "pdf-search", file, len(data))
    return {
        "query": query,
        "file_hash": fh,
        "n_chunks_total": len(chunks),
        "n_results": len(results),
        "results": [{"page": r["page"], "score": round(r["score"], 3), "text": r["text"][:600]} for r in results],
        "embedding_model": rag.EMBED_MODEL,
    }


# ============ Generic server-tool fallback ============
@api.post("/tools/{tool_id}/run-generic")
async def generic_stub(tool_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    """Fallback: for server tools not yet fully implemented — echoes file back or extracts text."""
    t = TOOL_MAP.get(tool_id)
    if not t:
        raise HTTPException(404, "Unknown tool")
    await _ensure_tool_enabled(tool_id)
    data = await _read_upload(file, user)
    await _consume_op(user)
    await _log_job(user, tool_id, file, len(data))
    if tool_id in ("pdf-to-html",):
        txt = pdf_ops.extract_text(data)
        html = f"<html><body><pre>{txt}</pre></body></html>"
        return StreamingResponse(io.BytesIO(html.encode()), media_type="text/html",
                                 headers={"Content-Disposition": f'attachment; filename="{file.filename}.html"'})
    return _pdf_response(data, f"{tool_id}-{file.filename}")


# ============ Billing (Stripe + Razorpay + PayPal) ============
from billing import build_router as _billing_router
from razorpay_gw import build_router as _razorpay_router, rzp_available
from paypal_gw import build_router as _paypal_router, paypal_available
from admin import build_admin_router as _admin_router
api.include_router(_billing_router(db, get_current_user, get_settings))
api.include_router(_razorpay_router(db, get_current_user))
api.include_router(_paypal_router(db, get_current_user))
api.include_router(_admin_router(db, get_current_user, get_settings, save_settings))


@api.get("/billing/methods")
async def billing_methods(request: Request):
    """Report which payment gateways are enabled + the recommended one for the caller's country."""
    from billing import _geo_country, resolve_currency
    s = await get_settings()
    gw_cfg = s.get("gateways", {})
    country = await _geo_country(request)
    currency, symbol = resolve_currency(country)

    def _avail(gid: str, real_on: bool) -> bool:
        cfg = gw_cfg.get(gid, {"enabled": True, "mock": True})
        if not cfg.get("enabled", True):
            return False
        return bool(real_on or cfg.get("mock", True))

    stripe_real = bool(os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY"))
    stripe_on = _avail("stripe", stripe_real)
    razorpay_on = _avail("razorpay", rzp_available())
    paypal_on = _avail("paypal", paypal_available())
    if country == "IN" and razorpay_on:
        recommended = "razorpay"
    elif stripe_on:
        recommended = "stripe"
    elif paypal_on:
        recommended = "paypal"
    else:
        recommended = None
    return {
        "country": country,
        "currency": currency.upper(),
        "symbol": symbol,
        "display": f"{symbol}1",
        "recommended": recommended,
        "gateways": [
            {"id": "stripe", "name": "Stripe", "available": stripe_on,
             "methods": ["card", "apple_pay", "google_pay", "link", "klarna", "afterpay"],
             "currencies": ["USD", "CAD", "GBP", "EUR", "AUD", "NZD", "INR"]},
            {"id": "razorpay", "name": "Razorpay", "available": razorpay_on,
             "methods": ["card", "upi", "netbanking", "wallets"],
             "currencies": ["INR"]},
            {"id": "paypal", "name": "PayPal", "available": paypal_on,
             "methods": ["paypal", "wallet", "venmo"],
             "currencies": ["USD", "GBP", "EUR", "CAD", "AUD"]},
        ],
    }


# ============ Health ============
@api.get("/")
async def root():
    return {"app": "Ugh!PDF", "tools": len(TOOLS), "categories": len(CATEGORIES)}


# ============ Maintenance kill-switch middleware ============
async def _is_admin_request(request: Request) -> bool:
    auth = request.headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        return False
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALG])
        uid = payload["sub"]
    except Exception:
        return False
    u = await db.users.find_one({"_id": uid})
    return bool(u and u.get("is_admin"))


_MAINT_ALLOW_EXACT = {"/api", "/api/", "/api/config", "/api/auth/login", "/api/auth/me"}
_MAINT_ALLOW_PREFIX = ("/api/admin",)


@app.middleware("http")
async def maintenance_gate(request: Request, call_next):
    path = request.url.path
    if request.method != "OPTIONS" and path.startswith("/api"):
        try:
            s = await get_settings()
        except Exception:
            s = {}
        if s.get("maintenance_mode"):
            allowed = path in _MAINT_ALLOW_EXACT or any(path.startswith(p) for p in _MAINT_ALLOW_PREFIX)
            if not allowed and not await _is_admin_request(request):
                from starlette.responses import JSONResponse
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Ugh!PDF is down for maintenance. Please check back soon.",
                             "maintenance": True},
                )
    return await call_next(request)


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _init_indexes():
    """Ensure MongoDB TTL index so job records auto-expire after 24h.
    Also warm the fastembed model for the semantic-search tool."""
    try:
        await db.user_jobs.create_index("expires_at", expireAfterSeconds=0)
        await db.user_jobs.create_index([("user_id", 1), ("created_at", -1)])
        await db.rag_indexes.create_index("expires_at", expireAfterSeconds=0)
        log.info("user_jobs + rag_indexes TTL indexes ensured")
    except Exception as e:
        log.warning(f"index init warn: {e}")
    # Ensure global settings doc exists
    try:
        await get_settings(force=True)
        log.info("global settings ensured")
    except Exception as e:
        log.warning(f"settings init warn: {e}")
    # Seed the super-admin (idempotent)
    try:
        if ADMIN_EMAIL and ADMIN_PASSWORD:
            existing = await db.users.find_one({"email": ADMIN_EMAIL})
            if not existing:
                u = await _create_user(ADMIN_EMAIL, "Super Admin", _hash_pw(ADMIN_PASSWORD))
                await db.users.update_one({"_id": u["_id"]}, {"$set": {"is_admin": True, "plan": "lifetime"}})
                log.info(f"super-admin created: {ADMIN_EMAIL}")
            else:
                set_fields = {"is_admin": True}
                if existing.get("plan") != "lifetime":
                    set_fields["plan"] = "lifetime"
                # keep admin password in sync with env
                if not existing.get("password_hash") or not _verify_pw(ADMIN_PASSWORD, existing["password_hash"]):
                    set_fields["password_hash"] = _hash_pw(ADMIN_PASSWORD)
                await db.users.update_one({"_id": existing["_id"]}, {"$set": set_fields})
                log.info(f"super-admin ensured: {ADMIN_EMAIL}")
        else:
            log.warning("ADMIN_EMAIL/ADMIN_PASSWORD not set — no super-admin seeded")
    except Exception as e:
        log.warning(f"admin seed warn: {e}")
    # Warm embedder
    try:
        import asyncio, rag as _rag
        await asyncio.to_thread(_rag.get_embedder)
        log.info("Semantic search embedder warmed up")
    except Exception as e:
        log.warning(f"embedder warm-up failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
