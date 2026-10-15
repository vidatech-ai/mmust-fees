import os
import re
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.config import PAYSTACK_SECRET_KEY
from core.db import supabase
from core.security import current_student
from api.admin_fees import _bank_name, _bank_ref, _fresh_refs

router = APIRouter(prefix="/payments", tags=["payments"])

PAYSTACK = "https://api.paystack.co"
CURRENCY = os.getenv("PAYSTACK_CURRENCY", "KES")
EMAIL_DOMAIN = os.getenv("PAYSTACK_EMAIL_DOMAIN", "vidatech-wifi.com")
MIN_AMOUNT = 10
MAX_AMOUNT = 10_000_000


class MpesaIn(BaseModel):
    amount: float = Field(gt=0, le=MAX_AMOUNT)
    phone: str = Field(min_length=9, max_length=20)


def _phone(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    if d.startswith("254") and len(d) == 12:
        pass
    elif d.startswith("0") and len(d) == 10:
        d = "254" + d[1:]
    elif len(d) == 9 and d[0] in "17":
        d = "254" + d
    else:
        raise HTTPException(400, "Enter a valid M-Pesa number, e.g. 0712345678")
    return "+" + d


def _paystack(method: str, path: str, payload: dict | None = None):
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(503, "Online payment is not configured")
    try:
        r = httpx.request(
            method, PAYSTACK + path, json=payload, timeout=30.0,
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
        )
        return r.status_code, r.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Could not reach the payment provider. Try again.")


def _balance(sid: str) -> float:
    charged = sum(float(c["amount"]) for c in
                  supabase.table("fee_charges").select("amount").eq("student_id", sid).execute().data)
    paid = sum(float(p["amount"]) for p in
               supabase.table("payments").select("amount").eq("student_id", sid).eq("status", "success").execute().data)
    return round(charged - paid, 2)


def _current_term(sid: str):
    ids = {c["term_id"] for c in
           supabase.table("fee_charges").select("term_id").eq("student_id", sid).execute().data if c.get("term_id")}
    if not ids:
        return None
    terms = supabase.table("fee_terms").select("id,academic_year,semester").in_("id", list(ids)).execute().data
    terms.sort(key=lambda t: (t["academic_year"], t["semester"]), reverse=True)
    return terms[0]["id"] if terms else None


def _settle(row: dict) -> str:
    """Ask Paystack about a pending payment and update our row. Returns the resulting status."""
    if row["status"] != "pending":
        return row["status"]
    code, body = _paystack("GET", f"/transaction/verify/{row['paystack_reference']}")
    if code != 200 or not body.get("status"):
        return "pending"
    d = body["data"]
    ps = d.get("status")
    if ps == "success":
        expected = int(round(float(row["amount"]) * 100))
        if d.get("amount") != expected or d.get("currency") != CURRENCY:
            supabase.table("payments").update({"status": "failed"}) \
                .eq("id", row["id"]).eq("status", "pending").execute()
            return "failed"
        supabase.table("payments").update({
            "status": "success",
            "paid_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", row["id"]).eq("status", "pending").execute()
        return "success"
    if ps == "failed":
        supabase.table("payments").update({"status": "failed"}) \
            .eq("id", row["id"]).eq("status", "pending").execute()
        return "failed"
    return "pending"


@router.get("/summary")
def summary(sid: str = Depends(current_student)):
    pend = (supabase.table("payments").select("*").eq("student_id", sid)
            .eq("source", "paystack").eq("status", "pending").limit(5).execute().data)
    for row in pend:
        _settle(row)
    rows = (supabase.table("payments")
            .select("id,amount,status,ref,paystack_reference,source,paid_at,created_at")
            .eq("student_id", sid)
            .order("created_at", desc=True).limit(50).execute().data)
    return {
        "balance": _balance(sid),
        "currency": CURRENCY,
        "min_amount": MIN_AMOUNT,
        "online_payments": [{
            "id": r["id"], "reference": r.get("ref") or r.get("paystack_reference") or "",
            "amount": float(r["amount"]),
            "status": r["status"], "date": str(r.get("paid_at") or r["created_at"])[:10],
        } for r in rows],
    }


@router.post("/mpesa")
def mpesa(body: MpesaIn, sid: str = Depends(current_student)):
    amount = round(body.amount, 2)
    phone = _phone(body.phone)
    bal = _balance(sid)
    if bal <= 0:
        raise HTTPException(400, "You have no outstanding balance")
    if amount < MIN_AMOUNT:
        raise HTTPException(400, f"Minimum payment is {MIN_AMOUNT}")
    if amount > bal:
        raise HTTPException(400, f"Amount is more than your balance of {bal:,.2f}")

    st = supabase.table("students").select("reg_number").eq("id", sid).limit(1).execute().data[0]
    reference = "FEE-" + uuid.uuid4().hex[:16].upper()
    row = {
        "student_id": sid, "term_id": _current_term(sid), "amount": amount,
        "source": "paystack", "status": "pending", "paystack_reference": reference,
        "description": _bank_name() or "PAYMENT",
        "ref": _fresh_refs("payments", _bank_ref, 1)[0],
    }
    created = supabase.table("payments").insert(row).execute().data[0]

    # Paystack requires an email; students have none on file, so one is built from the reg number
    reg_clean = re.sub(r"[^a-z0-9]", "", st["reg_number"].lower())
    email = f"mmustfees+{reg_clean}+{phone.lstrip('+')}@{EMAIL_DOMAIN}"
    code, res = _paystack("POST", "/charge", {
        "email": email,
        "amount": int(round(amount * 100)),
        "currency": CURRENCY,
        "reference": reference,
        "mobile_money": {"phone": phone, "provider": "mpesa"},
        "metadata": {
            "app": "mmust-fees", "student_id": sid, "reg_number": st["reg_number"],
            "custom_fields": [
                {"display_name": "App", "variable_name": "app", "value": "MMUST Fee Portal"},
                {"display_name": "Reg number", "variable_name": "reg_number", "value": st["reg_number"]},
                {"display_name": "Phone", "variable_name": "phone", "value": phone},
            ],
        },
    })
    data = res.get("data") or {}
    if code != 200 or not res.get("status") or data.get("status") == "failed":
        supabase.table("payments").update({"status": "failed"}).eq("id", created["id"]).execute()
        raise HTTPException(502, data.get("message") or res.get("message") or "Could not start the payment")
    return {
        "reference": reference,
        "message": data.get("display_text") or "Check your phone and enter your M-Pesa PIN",
    }


@router.get("/verify/{reference}")
def verify(reference: str, sid: str = Depends(current_student)):
    rows = (supabase.table("payments").select("*").eq("paystack_reference", reference)
            .eq("student_id", sid).limit(1).execute().data)
    if not rows:
        raise HTTPException(404, "Payment not found")
    return {"status": _settle(rows[0]), "reference": reference}
