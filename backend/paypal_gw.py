"""PayPal Orders v2 API integration (REST, no SDK) — one-time $1 lifetime unlock.
Requires env: PAYPAL_CLIENT_ID + PAYPAL_CLIENT_SECRET (optional PAYPAL_MODE=sandbox|live).
When keys are missing, endpoints report PayPal as unavailable so the frontend
gracefully falls back to Stripe.
"""
import os
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel


def _base_url() -> str:
    mode = (os.environ.get("PAYPAL_MODE") or "sandbox").lower()
    return "https://api-m.paypal.com" if mode == "live" else "https://api-m.sandbox.paypal.com"


def paypal_available() -> bool:
    return bool(os.environ.get("PAYPAL_CLIENT_ID") and os.environ.get("PAYPAL_CLIENT_SECRET"))


async def _access_token() -> str:
    async with httpx.AsyncClient(timeout=15.0) as hc:
        r = await hc.post(
            f"{_base_url()}/v1/oauth2/token",
            auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"]),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        return r.json()["access_token"]


class OrderIn(BaseModel):
    amount: float = 1.0
    currency: str = "USD"


class CaptureIn(BaseModel):
    order_id: str


def build_router(db, get_current_user) -> APIRouter:
    router = APIRouter()

    @router.get("/billing/paypal/available")
    async def available():
        return {
            "available": paypal_available(),
            "mode": (os.environ.get("PAYPAL_MODE") or "sandbox").lower(),
            "client_id": os.environ.get("PAYPAL_CLIENT_ID", ""),
        }

    @router.post("/billing/paypal/order")
    async def create_order(body: OrderIn, user=Depends(get_current_user)):
        if not paypal_available():
            raise HTTPException(503, "PayPal is not configured on this server")
        token = await _access_token()
        amount_str = f"{max(1.0, float(body.amount)):.2f}"
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": user["_id"],
                "description": "Ugh!PDF Lifetime Unlock",
                "amount": {"currency_code": body.currency.upper(), "value": amount_str},
            }],
            "application_context": {
                "brand_name": "Ugh!PDF",
                "shipping_preference": "NO_SHIPPING",
                "user_action": "PAY_NOW",
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as hc:
            r = await hc.post(
                f"{_base_url()}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": f"ughpdf-{user['_id']}-{int(datetime.now(timezone.utc).timestamp())}",
                },
                json=payload,
            )
        if r.status_code >= 400:
            raise HTTPException(502, f"PayPal error: {r.text[:200]}")
        j = r.json()
        await db.payment_transactions.insert_one({
            "session_id": j["id"],
            "gateway": "paypal",
            "user_id": user["_id"],
            "amount": float(amount_str),
            "currency": body.currency.lower(),
            "status": "initiated",
            "payment_status": "pending",
            "sku": "lifetime",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"order_id": j["id"], "status": j.get("status"), "amount": amount_str, "currency": body.currency.upper()}

    @router.post("/billing/paypal/capture")
    async def capture_order(body: CaptureIn, user=Depends(get_current_user)):
        if not paypal_available():
            raise HTTPException(503, "PayPal is not configured on this server")
        token = await _access_token()
        async with httpx.AsyncClient(timeout=15.0) as hc:
            r = await hc.post(
                f"{_base_url()}/v2/checkout/orders/{body.order_id}/capture",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        if r.status_code >= 400:
            raise HTTPException(400, f"Capture failed: {r.text[:200]}")
        j = r.json()
        status = (j.get("status") or "").upper()
        if status == "COMPLETED":
            # Idempotent grant
            tx = await db.payment_transactions.find_one({"session_id": body.order_id})
            if tx and tx.get("payment_status") != "paid":
                capture_id = ""
                try:
                    capture_id = j["purchase_units"][0]["payments"]["captures"][0]["id"]
                except Exception:
                    pass
                await db.payment_transactions.update_one(
                    {"session_id": body.order_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "payment_id": capture_id,
                              "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                await db.users.update_one({"_id": user["_id"]}, {"$set": {"plan": "lifetime"}})
            return {"ok": True, "plan": "lifetime", "capture": j}
        return {"ok": False, "status": status, "raw": j}

    @router.post("/webhook/paypal")
    async def webhook(request: Request):
        """PayPal webhook — verifies with PayPal's verify-webhook-signature endpoint.
        Requires PAYPAL_WEBHOOK_ID env to be set (created in developer dashboard)."""
        if not paypal_available():
            return {"status": "ignored"}
        webhook_id = os.environ.get("PAYPAL_WEBHOOK_ID", "")
        headers = request.headers
        body = await request.json()
        if webhook_id:
            token = await _access_token()
            verify_payload = {
                "auth_algo": headers.get("paypal-auth-algo", ""),
                "cert_url": headers.get("paypal-cert-url", ""),
                "transmission_id": headers.get("paypal-transmission-id", ""),
                "transmission_sig": headers.get("paypal-transmission-sig", ""),
                "transmission_time": headers.get("paypal-transmission-time", ""),
                "webhook_id": webhook_id,
                "webhook_event": body,
            }
            async with httpx.AsyncClient(timeout=10.0) as hc:
                r = await hc.post(
                    f"{_base_url()}/v1/notifications/verify-webhook-signature",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=verify_payload,
                )
            if r.status_code >= 400 or r.json().get("verification_status") != "SUCCESS":
                raise HTTPException(400, "Webhook signature invalid")
        event = body.get("event_type", "")
        if event == "CHECKOUT.ORDER.APPROVED" or event == "PAYMENT.CAPTURE.COMPLETED":
            resource = body.get("resource", {}) or {}
            order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id") or resource.get("id")
            if order_id:
                tx = await db.payment_transactions.find_one({"session_id": order_id})
                if tx and tx.get("payment_status") != "paid":
                    await db.payment_transactions.update_one(
                        {"session_id": order_id},
                        {"$set": {"status": "completed", "payment_status": "paid",
                                  "updated_at": datetime.now(timezone.utc).isoformat()}},
                    )
                    await db.users.update_one({"_id": tx["user_id"]}, {"$set": {"plan": "lifetime"}})
        return {"status": "ok"}

    return router
