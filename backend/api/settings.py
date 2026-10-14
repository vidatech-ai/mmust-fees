import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import supabase
from core.security import current_admin

router = APIRouter(prefix="/admin", tags=["settings"])

FIELDS = [
    "school_name", "location", "phone", "email",
    "programme", "department", "school", "programme_type",
    "current_academic_year", "current_semester", "semester_start", "semester_end",
    "bank_name",
]


class SettingsIn(BaseModel):
    school_name: str = Field("", max_length=150)
    location: str = Field("", max_length=200)
    phone: str = Field("", max_length=100)
    email: str = Field("", max_length=120)
    programme: str = Field("", max_length=200)
    department: str = Field("", max_length=200)
    school: str = Field("", max_length=250)
    programme_type: str = Field("", max_length=60)
    current_academic_year: str = Field("", max_length=9)
    current_semester: int = Field(1, ge=1, le=2)
    semester_start: date | None = None
    semester_end: date | None = None
    bank_name: str = Field("", max_length=120)


def _read() -> dict:
    rows = supabase.table("settings").select(",".join(FIELDS)).eq("id", 1).limit(1).execute().data
    return rows[0] if rows else {}


@router.get("/settings")
def get_settings(_admin: str = Depends(current_admin)):
    return _read()


@router.put("/settings")
def save_settings(body: SettingsIn, admin_id: str = Depends(current_admin)):
    new = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump(mode="json").items()}

    year = new["current_academic_year"]
    if year:
        m = re.fullmatch(r"(\d{4})/(\d{4})", year)
        if not m or int(m.group(2)) != int(m.group(1)) + 1:
            raise HTTPException(400, "Academic year must look like 2026/2027")
    if new["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", new["email"]):
        raise HTTPException(400, "That email address does not look right")
    if new["semester_start"] and new["semester_end"] and new["semester_end"] <= new["semester_start"]:
        raise HTTPException(400, "Semester end date must be after the start date")

    old = _read()
    supabase.table("settings").update(new).eq("id", 1).execute()
    supabase.table("audit_log").insert({
        "admin_id": admin_id,
        "action": "update",
        "table_name": "settings",
        "old_value": old,
        "new_value": new,
    }).execute()
    return new
