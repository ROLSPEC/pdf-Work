"""Super-admin master control: stats, settings (maintenance / gateways / feature toggles / limits),
user management (list + grant/revoke lifetime)."""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel


UNIT_PRICE_USD = 1.0  # $1 lifetime unlock


class PlanIn(BaseModel):
    plan: str  # "lifetime" | "free"


def build_admin_router(db, get_current_user, get_settings, save_settings):
    router = APIRouter(prefix="/admin")

    async def require_admin(user=Depends(get_current_user)):
        if not user.get("is_admin"):
            raise HTTPException(403, "Admin only")
        return user

    # ---------- Stats ----------
    @router.get("/stats")
    async def stats(admin=Depends(require_admin)):
        total_users = await db.users.count_documents({})
        lifetime_users = await db.users.count_documents({"plan": "lifetime"})
        free_users = max(0, total_users - lifetime_users)
        conversion = round(100.0 * lifetime_users / total_users, 1) if total_users else 0.0

        total_jobs = await db.user_jobs.count_documents({})
        agg = await db.users.aggregate(
            [{"$group": {"_id": None, "ops": {"$sum": "$ops_today"}}}]
        ).to_list(1)
        ops_today = int(agg[0]["ops"]) if agg else 0

        # Revenue: every lifetime user = $1. Attribute to a gateway when a paid
        # transaction exists; the remainder is counted as mock/dev unlocks.
        paid = await db.payment_transactions.find({"payment_status": "paid"}).to_list(20000)
        by_gateway: Dict[str, Dict[str, float]] = {}
        real_paid = 0
        for tx in paid:
            gw = (tx.get("gateway") or "stripe").lower()
            entry = by_gateway.setdefault(gw, {"count": 0, "revenue": 0.0})
            entry["count"] += 1
            entry["revenue"] += float(tx.get("amount") or UNIT_PRICE_USD)
            real_paid += 1
        mock_count = max(0, lifetime_users - real_paid)
        if mock_count:
            entry = by_gateway.setdefault("mock", {"count": 0, "revenue": 0.0})
            entry["count"] += mock_count
            entry["revenue"] += mock_count * UNIT_PRICE_USD

        total_revenue = round(lifetime_users * UNIT_PRICE_USD, 2)

        recent_users_raw = await db.users.find(
            {}, {"password_hash": 0}
        ).sort("created_at", -1).limit(8).to_list(8)
        recent_users = [
            {
                "id": u["_id"],
                "email": u.get("email"),
                "name": u.get("name"),
                "plan": u.get("plan", "free"),
                "is_admin": bool(u.get("is_admin")),
                "created_at": u.get("created_at"),
            }
            for u in recent_users_raw
        ]

        recent_purchases_raw = await db.users.find(
            {"plan": "lifetime"}, {"password_hash": 0}
        ).sort("created_at", -1).limit(8).to_list(8)
        recent_purchases = [
            {"email": u.get("email"), "name": u.get("name"), "created_at": u.get("created_at")}
            for u in recent_purchases_raw
        ]

        return {
            "users": {
                "total": total_users,
                "lifetime": lifetime_users,
                "free": free_users,
                "conversion_pct": conversion,
            },
            "usage": {"ops_today": ops_today, "total_jobs": total_jobs},
            "revenue": {
                "currency": "USD",
                "symbol": "$",
                "unit_price": UNIT_PRICE_USD,
                "total": total_revenue,
                "by_gateway": [
                    {"gateway": k, "count": v["count"], "revenue": round(v["revenue"], 2)}
                    for k, v in sorted(by_gateway.items())
                ],
            },
            "recent_users": recent_users,
            "recent_purchases": recent_purchases,
        }

    # ---------- Settings ----------
    @router.get("/settings")
    async def get_admin_settings(admin=Depends(require_admin)):
        s = await get_settings(force=True)
        s.pop("_id", None)
        return s

    @router.put("/settings")
    async def update_admin_settings(payload: Dict[str, Any] = Body(...), admin=Depends(require_admin)):
        current = await get_settings(force=True)
        allowed = {"maintenance_mode", "gateways", "disabled_tools", "disabled_categories", "limits"}
        updates: Dict[str, Any] = {}

        if "maintenance_mode" in payload:
            updates["maintenance_mode"] = bool(payload["maintenance_mode"])

        if "gateways" in payload and isinstance(payload["gateways"], dict):
            gw = dict(current.get("gateways", {}))
            for gid, cfg in payload["gateways"].items():
                if gid not in ("stripe", "razorpay", "paypal") or not isinstance(cfg, dict):
                    continue
                existing = dict(gw.get(gid, {"enabled": True, "mock": True}))
                if "enabled" in cfg:
                    existing["enabled"] = bool(cfg["enabled"])
                if "mock" in cfg:
                    existing["mock"] = bool(cfg["mock"])
                gw[gid] = existing
            updates["gateways"] = gw

        if "disabled_tools" in payload and isinstance(payload["disabled_tools"], list):
            updates["disabled_tools"] = [str(x) for x in payload["disabled_tools"]]

        if "disabled_categories" in payload and isinstance(payload["disabled_categories"], list):
            updates["disabled_categories"] = [str(x) for x in payload["disabled_categories"]]

        if "limits" in payload and isinstance(payload["limits"], dict):
            lim = dict(current.get("limits", {}))
            if "free_daily_ops" in payload["limits"]:
                lim["free_daily_ops"] = max(0, int(payload["limits"]["free_daily_ops"]))
            if "max_file_mb_free" in payload["limits"]:
                lim["max_file_mb_free"] = max(1, int(payload["limits"]["max_file_mb_free"]))
            updates["limits"] = lim

        if not updates:
            raise HTTPException(400, "No valid settings provided")

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await save_settings(updates)
        s = await get_settings(force=True)
        s.pop("_id", None)
        return s

    # ---------- Users ----------
    @router.get("/users")
    async def list_users(q: Optional[str] = None, limit: int = 200, admin=Depends(require_admin)):
        query: Dict[str, Any] = {}
        if q:
            query = {"$or": [
                {"email": {"$regex": q, "$options": "i"}},
                {"name": {"$regex": q, "$options": "i"}},
            ]}
        cursor = db.users.find(query, {"password_hash": 0}).sort("created_at", -1).limit(min(500, max(1, limit)))
        out: List[dict] = []
        async for u in cursor:
            out.append({
                "id": u["_id"],
                "email": u.get("email"),
                "name": u.get("name"),
                "plan": u.get("plan", "free"),
                "is_admin": bool(u.get("is_admin")),
                "ops_today": u.get("ops_today", 0),
                "created_at": u.get("created_at"),
            })
        return {"users": out, "count": len(out)}

    @router.post("/users/{uid}/plan")
    async def set_user_plan(uid: str, body: PlanIn, admin=Depends(require_admin)):
        if body.plan not in ("lifetime", "free"):
            raise HTTPException(400, "plan must be 'lifetime' or 'free'")
        target = await db.users.find_one({"_id": uid})
        if not target:
            raise HTTPException(404, "User not found")
        if target.get("is_admin") and body.plan == "free":
            raise HTTPException(400, "Cannot downgrade an admin account")
        await db.users.update_one({"_id": uid}, {"$set": {"plan": body.plan}})
        return {"ok": True, "id": uid, "plan": body.plan}

    return router
