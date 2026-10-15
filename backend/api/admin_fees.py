import re
import secrets
import uuid
import random
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import supabase
from core.security import current_admin

router = APIRouter(prefix="/admin/fees", tags=["admin-fees"])

STANDARD = "STANDARD INVOICE"
MAX_AMOUNT = 10_000_000


class TermApply(BaseModel):
    academic_year: str = Field(min_length=9, max_length=9)
    semester: int = Field(ge=1, le=2)
    amount: float = Field(gt=0, le=MAX_AMOUNT)
    invoice_date: date


class EntryIn(BaseModel):
    student_id: uuid.UUID
    term_id: uuid.UUID
    amount: float = Field(gt=0, le=MAX_AMOUNT)
    description: str = Field("", max_length=200)
    ref: str = Field("", max_length=60)
    entry_date: date


class EntryEdit(BaseModel):
    term_id: uuid.UUID
    amount: float = Field(gt=0, le=MAX_AMOUNT)
    description: str = Field("", max_length=200)
    ref: str = Field("", max_length=60)
    entry_date: date


def _audit(admin_id, action, table, record_id, old, new):
    supabase.table("audit_log").insert({
        "admin_id": admin_id, "action": action, "table_name": table,
        "record_id": record_id, "old_value": old, "new_value": new,
    }).execute()


def _ref(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:7].upper()


def _sfi() -> str:
    # standard invoice ref: SFI + 6 digits, e.g. SFI591884
    return "SFI" + str(secrets.randbelow(900_000) + 100_000)


def _bank_ref() -> str:
    # payment ref: 7 digits, e.g. 1295949
    return str(secrets.randbelow(9_000_000) + 1_000_000)


def _fresh_refs(table: str, make, n: int) -> list:
    # n new refs that are not already used in `table`
    out, seen = [], set()
    while len(out) < n:
        batch = []
        while len(batch) < min(100, n - len(out)):
            r = make()
            if r not in seen:
                seen.add(r)
                batch.append(r)
        used = {u["ref"] for u in supabase.table(table).select("ref").in_("ref", batch).execute().data}
        out += [r for r in batch if r not in used]
    return out


def _bank_name() -> str:
    rows = supabase.table("settings").select("bank_name").eq("id", 1).limit(1).execute().data
    return ((rows[0].get("bank_name") if rows else "") or "").strip()


def _need(table: str, row_id, label: str, cols: str = "*") -> dict:
    rows = supabase.table(table).select(cols).eq("id", str(row_id)).limit(1).execute().data
    if not rows:
        raise HTTPException(404, f"{label} not found")
    return rows[0]


def _terms() -> list:
    rows = supabase.table("fee_terms").select("id,academic_year,semester,fee_amount").execute().data
    rows.sort(key=lambda t: (t["academic_year"], t["semester"]), reverse=True)
    for r in rows:
        r["fee_amount"] = float(r["fee_amount"])
    return rows


def _clean(body, default_desc: str, prefix: str):
    desc = body.description.strip()
    ref = body.ref.strip()
    if prefix == "PAY":
        if not desc:
            desc = _bank_name() or default_desc
        if not ref:
            ref = _fresh_refs("payments", _bank_ref, 1)[0]
        return desc, ref
    return (desc or default_desc), (ref or _ref(prefix))


def _manual_only(old: dict):
    if old.get("source") != "manual":
        raise HTTPException(400, "Online payments cannot be changed here")


_EAT = timezone(timedelta(hours=3))


def _manual_time(d: date) -> str:
    # random time between 10:00 and 16:00 East Africa Time, stored as UTC
    start = datetime(d.year, d.month, d.day, tzinfo=_EAT)
    return (start + timedelta(minutes=random.randint(600, 960))).astimezone(timezone.utc).isoformat()


def _paid_at(old: dict, d: date) -> str:
    # keep the existing time if the date did not change, otherwise pick a new random time
    raw = str(old.get("paid_at") or "")
    try:
        if raw and datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(_EAT).date() == d:
            return raw
    except ValueError:
        pass
    return _manual_time(d)


# ---------- semester fee ----------

@router.get("/terms")
def list_terms(_admin: str = Depends(current_admin)):
    return _terms()


@router.post("/terms/apply")
def apply_term(body: TermApply, admin_id: str = Depends(current_admin)):
    m = re.fullmatch(r"(\d{4})/(\d{4})", body.academic_year)
    if not m or int(m.group(2)) != int(m.group(1)) + 1:
        raise HTTPException(400, "Academic year must look like 2026/2027")
    amount = round(body.amount, 2)

    existing = (
        supabase.table("fee_terms").select("id,fee_amount")
        .eq("academic_year", body.academic_year).eq("semester", body.semester).limit(1).execute().data
    )
    if existing:
        term_id = existing[0]["id"]
        old_amount = float(existing[0]["fee_amount"])
        if old_amount != amount:
            supabase.table("fee_terms").update({"fee_amount": amount}).eq("id", term_id).execute()
            _audit(admin_id, "update", "fee_terms", term_id, {"fee_amount": old_amount}, {"fee_amount": amount})
    else:
        row = {"academic_year": body.academic_year, "semester": body.semester, "fee_amount": amount}
        term_id = supabase.table("fee_terms").insert(row).execute().data[0]["id"]
        _audit(admin_id, "create", "fee_terms", term_id, None, row)

    students = supabase.table("students").select("id").eq("active", True).limit(1000).execute().data
    have = (
        supabase.table("fee_charges").select("student_id")
        .eq("term_id", term_id).eq("description", STANDARD).limit(1000).execute().data
    )
    done = {h["student_id"] for h in have}
    todo = [s for s in students if s["id"] not in done]
    refs = _fresh_refs("fee_charges", _sfi, len(todo))
    rows = [
        {"student_id": s["id"], "term_id": term_id, "amount": amount, "description": STANDARD,
         "ref": ref, "charge_date": body.invoice_date.isoformat()}
        for s, ref in zip(todo, refs)
    ]
    for i in range(0, len(rows), 200):
        supabase.table("fee_charges").insert(rows[i:i + 200]).execute()

    skipped = len(students) - len(rows)
    _audit(admin_id, "apply_term", "fee_terms", term_id, None,
           {"amount": amount, "invoiced": len(rows), "skipped": skipped})
    return {"term_id": term_id, "created": len(rows), "skipped": skipped}


# ---------- one student's ledger ----------

@router.get("/student/{student_id}")
def ledger(student_id: uuid.UUID, _admin: str = Depends(current_admin)):
    sid = str(student_id)
    student = _need("students", sid, "Student", "id,name,reg_number,active")
    terms = _terms()
    labels = {t["id"]: f"Semester {t['semester']} {t['academic_year']}" for t in terms}

    charges = (
        supabase.table("fee_charges")
        .select("id,term_id,amount,description,ref,charge_date,created_at")
        .eq("student_id", sid).execute().data
    )
    pays = (
        supabase.table("payments")
        .select("id,term_id,amount,description,ref,paystack_reference,source,status,paid_at,created_at")
        .eq("student_id", sid).execute().data
    )
    out_c = [{
        "id": c["id"], "term_id": c["term_id"], "term": labels.get(c["term_id"], "-"),
        "amount": float(c["amount"]), "description": c.get("description") or "",
        "ref": c.get("ref") or "", "date": str(c.get("charge_date") or c["created_at"])[:10],
    } for c in charges]
    out_p = [{
        "id": p["id"], "term_id": p["term_id"], "term": labels.get(p["term_id"], "-"),
        "amount": float(p["amount"]), "description": p.get("description") or "",
        "ref": p.get("ref") or p.get("paystack_reference") or "",
        "date": str(p.get("paid_at") or p["created_at"])[:10],
        "source": p["source"], "status": p["status"],
    } for p in pays]
    out_c.sort(key=lambda r: r["date"])
    out_p.sort(key=lambda r: r["date"])

    charged = sum(c["amount"] for c in out_c)
    paid = sum(p["amount"] for p in out_p if p["status"] == "success")
    return {
        "student": student, "terms": terms, "charges": out_c, "payments": out_p,
        "total_charged": round(charged, 2), "total_paid": round(paid, 2), "balance": round(charged - paid, 2),
    }


# ---------- invoices / adjustments ----------

@router.post("/charges")
def add_charge(body: EntryIn, admin_id: str = Depends(current_admin)):
    _need("students", body.student_id, "Student", "id")
    _need("fee_terms", body.term_id, "Semester", "id")
    desc, ref = _clean(body, "INVOICE ADJUSTMENT", "ADJ")
    row = {"student_id": str(body.student_id), "term_id": str(body.term_id), "amount": round(body.amount, 2),
           "description": desc, "ref": ref, "charge_date": body.entry_date.isoformat()}
    created = supabase.table("fee_charges").insert(row).execute().data[0]
    _audit(admin_id, "create", "fee_charges", created["id"], None, row)
    return {"id": created["id"]}


@router.put("/charges/{charge_id}")
def edit_charge(charge_id: uuid.UUID, body: EntryEdit, admin_id: str = Depends(current_admin)):
    cid = str(charge_id)
    old = _need("fee_charges", cid, "Invoice")
    _need("fee_terms", body.term_id, "Semester", "id")
    desc, ref = _clean(body, "INVOICE ADJUSTMENT", "ADJ")
    new = {"term_id": str(body.term_id), "amount": round(body.amount, 2), "description": desc,
           "ref": ref, "charge_date": body.entry_date.isoformat()}
    supabase.table("fee_charges").update(new).eq("id", cid).execute()
    _audit(admin_id, "update", "fee_charges", cid, old, new)
    return {"ok": True}


@router.delete("/charges/{charge_id}")
def delete_charge(charge_id: uuid.UUID, admin_id: str = Depends(current_admin)):
    cid = str(charge_id)
    old = _need("fee_charges", cid, "Invoice")
    supabase.table("fee_charges").delete().eq("id", cid).execute()
    _audit(admin_id, "delete", "fee_charges", cid, old, None)
    return {"ok": True}


# ---------- payments ----------

@router.post("/payments")
def add_payment(body: EntryIn, admin_id: str = Depends(current_admin)):
    _need("students", body.student_id, "Student", "id")
    _need("fee_terms", body.term_id, "Semester", "id")
    desc, ref = _clean(body, "PAYMENT", "PAY")
    row = {"student_id": str(body.student_id), "term_id": str(body.term_id), "amount": round(body.amount, 2),
           "source": "manual", "status": "success", "paid_at": _manual_time(body.entry_date),
           "description": desc, "ref": ref}
    created = supabase.table("payments").insert(row).execute().data[0]
    _audit(admin_id, "create", "payments", created["id"], None, row)
    return {"id": created["id"]}


@router.put("/payments/{payment_id}")
def edit_payment(payment_id: uuid.UUID, body: EntryEdit, admin_id: str = Depends(current_admin)):
    pid = str(payment_id)
    old = _need("payments", pid, "Payment")
    _need("fee_terms", body.term_id, "Semester", "id")
    desc, ref = _clean(body, "PAYMENT", "PAY")
    new = {"term_id": str(body.term_id), "amount": round(body.amount, 2), "description": desc,
           "ref": ref, "paid_at": _paid_at(old, body.entry_date)}
    supabase.table("payments").update(new).eq("id", pid).execute()
    _audit(admin_id, "update", "payments", pid, old, new)
    return {"ok": True}


@router.delete("/payments/{payment_id}")
def delete_payment(payment_id: uuid.UUID, admin_id: str = Depends(current_admin)):
    pid = str(payment_id)
    old = _need("payments", pid, "Payment")
    supabase.table("payments").delete().eq("id", pid).execute()
    _audit(admin_id, "delete", "payments", pid, old, None)
    return {"ok": True}


@router.delete("/payments")
def delete_all_payments(confirm: str = "", admin_id: str = Depends(current_admin)):
    if confirm != "DELETE":
        raise HTTPException(400, "Type DELETE to confirm")
    rows = supabase.table("payments").select("amount").execute().data
    count = len(rows)
    total = round(sum(float(r["amount"]) for r in rows), 2)
    if count:
        supabase.table("payments").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    _audit(admin_id, "delete_all", "payments", None, {"count": count, "total": total}, None)
    return {"deleted": count}
