import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import supabase
from core.security import current_admin, hash_password

router = APIRouter(prefix="/admin/students", tags=["admin-students"])

REG_RE = re.compile(r"[A-Z0-9][A-Z0-9/_.\-]{2,39}")
PUBLIC = "id,reg_number,name,year_of_study,semester,admission_year,active,photo_url"  # never the hash


class StudentIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    reg_number: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=64)
    year_of_study: int = Field(1, ge=1, le=7)
    semester: int = Field(1, ge=1, le=2)
    admission_year: int | None = Field(None, ge=2000, le=2100)


class StudentEdit(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    year_of_study: int = Field(ge=1, le=7)
    semester: int = Field(ge=1, le=2)
    admission_year: int | None = Field(None, ge=2000, le=2100)
    active: bool


class PasswordIn(BaseModel):
    password: str = Field(min_length=6, max_length=64)


def _audit(admin_id, action, record_id, old, new):
    supabase.table("audit_log").insert({
        "admin_id": admin_id, "action": action, "table_name": "students",
        "record_id": record_id, "old_value": old, "new_value": new,
    }).execute()


def _get(student_id: str) -> dict:
    rows = supabase.table("students").select(PUBLIC).eq("id", student_id).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "Student not found")
    return rows[0]


def _hash(password: str) -> str:
    try:
        return hash_password(password)
    except ValueError:
        raise HTTPException(400, "Password is too long")


@router.get("")
def list_students(_admin: str = Depends(current_admin)):
    rows = supabase.table("students").select(PUBLIC).order("name").limit(1000).execute().data
    bal = supabase.table("student_balances").select("student_id,balance").limit(1000).execute().data
    by_id = {b["student_id"]: float(b["balance"] or 0) for b in bal}
    for r in rows:
        r["balance"] = by_id.get(r["id"], 0.0)
    return rows


@router.post("")
def create_student(body: StudentIn, admin_id: str = Depends(current_admin)):
    reg = body.reg_number.strip().upper()
    if not REG_RE.fullmatch(reg):
        raise HTTPException(400, "Registration number can only use letters, numbers and / - _ .")
    if supabase.table("students").select("id").eq("reg_number", reg).limit(1).execute().data:
        raise HTTPException(409, "That registration number already exists")

    row = {
        "reg_number": reg,
        "name": " ".join(body.name.split()),
        "password_hash": _hash(body.password),
        "year_of_study": body.year_of_study,
        "semester": body.semester,
        "admission_year": body.admission_year,
        "active": True,
    }
    created = supabase.table("students").insert(row).execute().data[0]
    safe = {k: v for k, v in row.items() if k != "password_hash"}
    _audit(admin_id, "create", created["id"], None, safe)
    return _get(created["id"])


@router.put("/{student_id}")
def edit_student(student_id: uuid.UUID, body: StudentEdit, admin_id: str = Depends(current_admin)):
    sid = str(student_id)
    old = _get(sid)
    new = {
        "name": " ".join(body.name.split()),
        "year_of_study": body.year_of_study,
        "semester": body.semester,
        "admission_year": body.admission_year,
        "active": body.active,
    }
    supabase.table("students").update(new).eq("id", sid).execute()
    _audit(admin_id, "update", sid, old, new)
    return _get(sid)


@router.post("/{student_id}/password")
def reset_password(student_id: uuid.UUID, body: PasswordIn, admin_id: str = Depends(current_admin)):
    sid = str(student_id)
    _get(sid)
    supabase.table("students").update({"password_hash": _hash(body.password)}).eq("id", sid).execute()
    _audit(admin_id, "password_reset", sid, None, {"password_reset": True})  # never log the password
    return {"ok": True}
