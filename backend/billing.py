"""Stripe billing (Flow B — BYOK using STRIPE_API_KEY env).
Geo-priced $1 lifetime unlock in 7 currencies."""
import os
import httpx
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends, Header
from pydantic import BaseModel
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse,
)

# Country → (currency_code, symbol)
COUNTRY_CURRENCY = {
    "US": ("usd", "$"),
    "CA": ("cad", "$"),
    "GB": ("gbp", "£"),
    "AU": ("aud", "$"),
    "NZ": ("nzd", "$"),
    "IN": ("inr", "₹"),
    # Eurozone
    "AT": ("eur", "€"), "BE": ("eur", "€"), "CY": ("eur", "€"), "EE": ("eur", "€"),
    "FI": ("eur", "€"), "FR": ("eur", "€"), "DE": ("eur", "€"), "GR": ("eur", "€"),
    "IE": ("eur", "€"), "IT": ("eur", "€"), "LV": ("eur", "€"), "LT": ("eur", "€"),
    "LU": ("eur", "€"), "MT": ("eur", "€"), "NL": ("eur", "€"), "PT": ("eur", "€"),
    "SK": ("eur", "€"), "SI": ("eur", "€"), "ES": ("eur", "€"), "HR": ("eur", "€"),
}

DEFAULT_CURRENCY = ("usd", "$")

# The amount is "1 unit" of local currency. Stripe expects the amount in the
# smallest currency unit (cents/paise). $1 = 100 cents. ₹1 = 100 paise. £1 = 100p.
# INR minimum is ₹1 but Stripe treats INR as 100 paise per rupee.
CURRENCY_AMOUNT_UNITS = {
    "usd": 1.0, "cad": 1.0, "gbp": 1.0, "eur": 1.0, "aud": 1.0, "nzd": 1.0, "inr": 1.0,
}


def _client_ip(request: Request) -> str:
    """Extract the actual client IP from headers (Cloudflare / proxies)."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.headers.get("cf-connecting-ip") or request.client.host or ""


async def _geo_country(request: Request) -> str:
    """Detect country from Cloudflare header first, then IP-based lookup."""
    # 1. Cloudflare header (deployed environment)
    cf = request.headers.get("cf-ipcountry", "").upper()
    if cf and cf != "XX":
        return cf
    # 2. IP-based fallback
    ip = _client_ip(request)
    if not ip:
        return "US"
    try:
        async with httpx.AsyncClient(timeout=3.0) as hc:
            r = await hc.get(f"https://ipapi.co/{ip}/country/")
            if r.status_code == 200 and r.text.strip():
                return r.text.strip().upper()
    except Exception:
        pass
    return "US"


def resolve_currency(country: str) -> tuple[str, str]:
    return COUNTRY_CURRENCY.get(country.upper(), DEFAULT_CURRENCY)


class CheckoutIn(BaseModel):
    origin_url: str


def build_router(db, get_current_user, PAID_CREDITS: int) -> APIRouter:
    router = APIRouter()

    STRIPE_KEY = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY") or ""
    PUBLIC_BASE_URL = (os.environ.get("APP_URL") or os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")

    def _get_checkout(host_url: str) -> StripeCheckout:
        base = PUBLIC_BASE_URL or host_url.rstrip("/")
        webhook_url = base + "/api/webhook/stripe"
        return StripeCheckout(api_key=STRIPE_KEY, webhook_url=webhook_url)

    @router.get("/billing/geo")
    async def geo(request: Request):
        country = await _geo_country(request)
        currency, symbol = resolve_currency(country)
        return {
            "country": country,
            "currency": currency.upper(),
            "symbol": symbol,
            "amount": CURRENCY_AMOUNT_UNITS[currency],
            "display": f"{symbol}1",
        }

    @router.post("/billing/checkout")
    async def checkout(body: CheckoutIn, request: Request, user=Depends(get_current_user)):
        if not STRIPE_KEY:
            # Dev-mode fallback: mock unlock
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"plan": "lifetime", "ai_credits": PAID_CREDITS}})
            return {"url": f"{body.origin_url}/unlocked?mock=1", "mock": True}
        country = await _geo_country(request)
        currency, symbol = resolve_currency(country)
        amount = float(CURRENCY_AMOUNT_UNITS[currency])
        host_url = str(request.base_url)
        checkout_lib = _get_checkout(host_url)
        req = CheckoutSessionRequest(
            amount=amount,
            currency=currency,
            success_url=f"{body.origin_url}/unlocked?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{body.origin_url}/pricing",
            metadata={"user_id": user["_id"], "sku": "lifetime", "country": country},
        )
        try:
            session: CheckoutSessionResponse = await checkout_lib.create_checkout_session(req)
        except Exception as e:
            raise HTTPException(500, f"Stripe error: {e}")
        # Log tx before returning
        await db.payment_transactions.insert_one({
            "session_id": session.session_id,
            "user_id": user["_id"],
            "amount": amount,
            "currency": currency,
            "country": country,
            "status": "initiated",
            "payment_status": "pending",
            "sku": "lifetime",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"url": session.url, "session_id": session.session_id, "currency": currency.upper(), "amount": amount, "display": f"{symbol}1"}

    @router.get("/payments/status/{session_id}")
    async def payment_status(session_id: str, request: Request):
        rec = await db.payment_transactions.find_one({"session_id": session_id})
        if not rec:
            raise HTTPException(404, "Transaction not found")
        # Fallback: poll Stripe directly if still pending
        if rec.get("payment_status") != "paid" and STRIPE_KEY:
            try:
                host_url = str(request.base_url)
                checkout_lib = _get_checkout(host_url)
                status = await checkout_lib.get_checkout_status(session_id)
                if status.payment_status == "paid":
                    await _grant_lifetime(db, rec["user_id"], session_id, status.payment_status, PAID_CREDITS)
                    rec = await db.payment_transactions.find_one({"session_id": session_id})
            except Exception:
                pass
        return {
            "session_id": rec["session_id"],
            "status": rec["status"],
            "payment_status": rec["payment_status"],
            "currency": rec.get("currency", "usd"),
            "amount": rec.get("amount", 1.0),
        }

    @router.post("/webhook/stripe")
    async def stripe_webhook(request: Request):
        if not STRIPE_KEY:
            return {"status": "ignored", "reason": "stripe not configured"}
        try:
            host_url = str(request.base_url)
            checkout_lib = _get_checkout(host_url)
            payload = await request.body()
            sig = request.headers.get("stripe-signature", "")
            wr = await checkout_lib.handle_webhook(payload, sig)
        except Exception as e:
            raise HTTPException(400, f"Invalid webhook: {e}")
        if wr.payment_status == "paid":
            uid = (wr.metadata or {}).get("user_id")
            if uid:
                await _grant_lifetime(db, uid, wr.session_id, "paid", PAID_CREDITS)
        return {"status": "ok"}

    @router.post("/billing/mock-unlock")
    async def mock_unlock(user=Depends(get_current_user)):
        """Dev helper: instantly unlock lifetime."""
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"plan": "lifetime", "ai_credits": PAID_CREDITS}})
        return {"ok": True, "plan": "lifetime"}

    return router


async def _grant_lifetime(db, user_id: str, session_id: str, payment_status: str, credits: int):
    """Idempotent: only grants once."""
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx or tx.get("payment_status") == "paid":
        # Update tx status but don't double-grant
        await db.payment_transactions.update_one(
            {"session_id": session_id, "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": "paid",
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        return
    await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid",
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.users.update_one({"_id": user_id}, {"$set": {"plan": "lifetime", "ai_credits": credits}})
