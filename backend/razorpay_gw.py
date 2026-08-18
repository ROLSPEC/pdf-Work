"""Razorpay integration — one-time ₹1 lifetime unlock for India users.
Requires env: RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET (optional RAZORPAY_WEBHOOK_SECRET).
When keys are missing, endpoints report Razorpay as unavailable so the frontend
gracefully falls back to Stripe.
"""

import os
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

try:
    import razorpay as _razorpay
except Exception:
    _razorpay = None


def rzp_available() -> bool:
    return bool(_razorpay and os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"))


def _client():
    if not rzp_available():
        return None
    return _razorpay.Client(auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]))


class OrderIn(BaseModel):
    amount: int = 100  # paise; ₹1 = 100 paise
    currency: str = "INR"


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def build_router(db, get_current_user) -> APIRouter:
    router = APIRouter()

    @router.get("/billing/razorpay/available")
    async def available():
        return {"available": rzp_available(), "key_id": os.environ.get("RAZORPAY_KEY_ID", "")}

    @router.post("/billing/razorpay/order")
    async def create_order(body: OrderIn, user=Depends(get_current_user)):
        if user.get("plan") == "lifetime":
            raise HTTPException(409, "You're already on lifetime — no purchase needed 🎉")
        if not rzp_available():
            raise HTTPException(503, "Razorpay is not configured on this server")
        client = _client()
        order = client.order.create({
            "amount": max(100, int(body.amount)),
            "currency": body.currency,
            "receipt": f"ughpdf-{user['_id'][:8]}-{int(datetime.now(timezone.utc).timestamp())}",
            "payment_capture": 1,
            "notes": {"user_id": user["_id"], "sku": "lifetime"},
        })
        await db.payment_transactions.insert_one({
            "session_id": order["id"],
            "gateway": "razorpay",
            "user_id": user["_id"],
            "amount": order["amount"] / 100.0,
            "currency": order["currency"].lower(),
            "status": "initiated",
            "payment_status": "pending",
            "sku": "lifetime",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": os.environ["RAZORPAY_KEY_ID"],
            "display": "₹1",
        }

    @router.post("/billing/razorpay/verify")
    async def verify_payment(body: VerifyIn, user=Depends(get_current_user)):
        if not rzp_available():
            raise HTTPException(503, "Razorpay is not configured on this server")
        secret = os.environ["RAZORPAY_KEY_SECRET"].encode()
        payload = f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode()
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, body.razorpay_signature):
            raise HTTPException(400, "Invalid signature")
        # Grant lifetime (idempotent)
        tx = await db.payment_transactions.find_one({"session_id": body.razorpay_order_id})
        if not tx:
            raise HTTPException(404, "Order not found")
        if tx.get("payment_status") != "paid":
            await db.payment_transactions.update_one(
                {"session_id": body.razorpay_order_id, "payment_status": {"$ne": "paid"}},
                {"$set": {"status": "completed", "payment_status": "paid",
                          "payment_id": body.razorpay_payment_id,
                          "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"plan": "lifetime"}})
        return {"ok": True, "plan": "lifetime"}

    @router.post("/webhook/razorpay")
    async def webhook(request: Request):
        if not rzp_available():
            return {"status": "ignored"}
        secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
        if not secret:
            return {"status": "no webhook secret configured"}
        raw = await request.body()
        sig = request.headers.get("x-razorpay-signature", "")
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(400, "Invalid webhook signature")
        payload = await request.json()
        event = payload.get("event", "")
        if event.startswith("payment."):
            entity = (payload.get("payload", {}).get("payment", {}) or {}).get("entity", {})
            order_id = entity.get("order_id")
            payment_id = entity.get("id")
            status = entity.get("status")  # 'captured' means paid
            if order_id and status == "captured":
                tx = await db.payment_transactions.find_one({"session_id": order_id})
                if tx and tx.get("payment_status") != "paid":
                    await db.payment_transactions.update_one(
                        {"session_id": order_id},
                        {"$set": {"status": "completed", "payment_status": "paid",
                                  "payment_id": payment_id,
                                  "updated_at": datetime.now(timezone.utc).isoformat()}},
                    )
                    await db.users.update_one({"_id": tx["user_id"]}, {"$set": {"plan": "lifetime"}})
        return {"status": "ok"}

    return router
