import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import supabase
from core.security import current_admin, current_student

router = APIRouter(tags=["academic"])


class UnitIn(BaseModel):
    year_of_study: int = Field(ge=1, le=8)
    unit_code: str = Field("", max_length=30)
    unit_name: str = Field("", max_length=150)
    credit_hours: float | None = Field(None, ge=0, le=100)


class RecordIn(BaseModel):
    academic_year: str = Field("", max_length=20)
    semester: int = Field(ge=1, le=3)
    year_of_study: int = Field(ge=1, le=8)
    unit_code: str = Field("", max_length=30)
    unit_name: str = Field("", max_length=150)
    marks: float | None = Field(None, ge=0, le=100)
    grade: str = Field("", max_length=5)


def _audit(admin_id, action, table, record_id, old, new):
    supabase.table("audit_log").insert({
        "admin_id": admin_id, "action": action, "table_name": table,
        "record_id": record_id, "old_value": old, "new_value": new,
    }).execute()


def _need(table: str, row_id, label: str) -> dict:
    rows = supabase.table(table).select("*").eq("id", str(row_id)).limit(1).execute().data
    if not rows:
        raise HTTPException(404, f"{label} not found")
    return rows[0]


def _session():
    rows = (
        supabase.table("settings").select("current_academic_year,current_semester")
        .eq("id", 1).limit(1).execute().data
    )
    r = rows[0] if rows else {}
    return (r.get("current_academic_year") or ""), r.get("current_semester")


def _need_session():
    ay, sem = _session()
    if not ay or not sem:
        raise HTTPException(400, "Set the academic year and semester in Settings first")
    return ay, sem


def _grade(marks: float) -> str:
    if marks >= 70:
        return "A"
    if marks >= 60:
        return "B"
    if marks >= 50:
        return "C"
    if marks >= 40:
        return "D"
    return "E"


def _clean_unit(body: UnitIn) -> dict:
    if not body.unit_name.strip():
        raise HTTPException(400, "Enter the unit name")
    return {
        "year_of_study": body.year_of_study,
        "unit_code": body.unit_code.strip().upper(),
        "unit_name": body.unit_name.strip(),
        "credit_hours": body.credit_hours,
    }


def _clean_record(body: RecordIn) -> dict:
    if not body.academic_year.strip():
        raise HTTPException(400, "Enter the academic year, e.g. 2025/2026")
    if not body.unit_name.strip():
        raise HTTPException(400, "Enter the unit name")
    grade = body.grade.strip().upper()
    if not grade and body.marks is not None:
        grade = _grade(body.marks)
    return {
        "academic_year": body.academic_year.strip(),
        "semester": body.semester,
        "year_of_study": body.year_of_study,
        "unit_code": body.unit_code.strip().upper(),
        "unit_name": body.unit_name.strip(),
        "marks": body.marks,
        "grade": grade,
    }


def _sort_records(rows: list[dict]) -> list[dict]:
    rows.sort(key=lambda r: (r["academic_year"], r["semester"], r.get("unit_code") or "", r["unit_name"]))
    return rows


# ---------- admin: units ----------

@router.get("/admin/academic")
def admin_academic(_admin: str = Depends(current_admin)):
    ay, sem = _session()
    units = []
    if ay and sem:
        units = (
            supabase.table("academic_units").select("*")
            .eq("academic_year", ay).eq("semester", sem).limit(1000).execute().data
        )
        units.sort(key=lambda u: (u["year_of_study"], u.get("unit_code") or "", u["unit_name"]))
    return {"session": {"academic_year": ay, "semester": sem}, "units": units}


@router.post("/admin/academic/units")
def add_unit(body: UnitIn, admin_id: str = Depends(current_admin)):
    ay, sem = _need_session()
    row = {**_clean_unit(body), "academic_year": ay, "semester": sem}
    created = supabase.table("academic_units").insert(row).execute().data[0]
    _audit(admin_id, "create", "academic_units", created["id"], None, row)
    return {"id": created["id"]}


@router.put("/admin/academic/units/{unit_id}")
def edit_unit(unit_id: uuid.UUID, body: UnitIn, admin_id: str = Depends(current_admin)):
    uid = str(unit_id)
    old = _need("academic_units", uid, "Unit")
    new = _clean_unit(body)
    supabase.table("academic_units").update(new).eq("id", uid).execute()
    _audit(admin_id, "update", "academic_units", uid, old, new)
    return {"ok": True}


@router.delete("/admin/academic/units/{unit_id}")
def delete_unit(unit_id: uuid.UUID, admin_id: str = Depends(current_admin)):
    uid = str(unit_id)
    old = _need("academic_units", uid, "Unit")
    supabase.table("academic_units").delete().eq("id", uid).execute()
    _audit(admin_id, "delete", "academic_units", uid, old, None)
    return {"ok": True}


# ---------- admin: transcript ----------

@router.get("/admin/academic/students")
def admin_student_list(_admin: str = Depends(current_admin)):
    rows = (
        supabase.table("students").select("id,reg_number,name,year_of_study")
        .order("reg_number").limit(5000).execute().data
    )
    return {"students": rows}


@router.get("/admin/academic/transcript/{student_id}")
def admin_transcript(student_id: uuid.UUID, _admin: str = Depends(current_admin)):
    sid = str(student_id)
    student = _need("students", sid, "Student")
    rows = (
        supabase.table("transcript_records").select("*")
        .eq("student_id", sid).limit(2000).execute().data
    )
    return {
        "student": {k: student[k] for k in ("id", "reg_number", "name", "year_of_study")},
        "records": _sort_records(rows),
    }


@router.post("/admin/academic/transcript/{student_id}")
def add_record(student_id: uuid.UUID, body: RecordIn, admin_id: str = Depends(current_admin)):
    sid = str(student_id)
    _need("students", sid, "Student")
    row = {**_clean_record(body), "student_id": sid}
    created = supabase.table("transcript_records").insert(row).execute().data[0]
    _audit(admin_id, "create", "transcript_records", created["id"], None, row)
    return {"id": created["id"]}


@router.put("/admin/academic/records/{record_id}")
def edit_record(record_id: uuid.UUID, body: RecordIn, admin_id: str = Depends(current_admin)):
    rid = str(record_id)
    old = _need("transcript_records", rid, "Result")
    new = _clean_record(body)
    supabase.table("transcript_records").update(new).eq("id", rid).execute()
    _audit(admin_id, "update", "transcript_records", rid, old, new)
    return {"ok": True}


@router.delete("/admin/academic/records/{record_id}")
def delete_record(record_id: uuid.UUID, admin_id: str = Depends(current_admin)):
    rid = str(record_id)
    old = _need("transcript_records", rid, "Result")
    supabase.table("transcript_records").delete().eq("id", rid).execute()
    _audit(admin_id, "delete", "transcript_records", rid, old, None)
    return {"ok": True}


# ---------- student ----------

@router.get("/student/academic")
def student_academic(student_id: str = Depends(current_student)):
    srows = (
        supabase.table("students").select("year_of_study")
        .eq("id", student_id).limit(1).execute().data
    )
    year = srows[0]["year_of_study"] if srows else None
    ay, sem = _session()

    units = []
    if ay and sem and year:
        units = (
            supabase.table("academic_units")
            .select("id,unit_code,unit_name,credit_hours,year_of_study")
            .eq("academic_year", ay).eq("semester", sem).eq("year_of_study", year)
            .limit(500).execute().data
        )
        units.sort(key=lambda u: (u.get("unit_code") or "", u["unit_name"]))

    rows = (
        supabase.table("transcript_records")
        .select("id,academic_year,semester,year_of_study,unit_code,unit_name,marks,grade")
        .eq("student_id", student_id).limit(2000).execute().data
    )
    return {
        "session": {"academic_year": ay, "semester": sem},
        "year_of_study": year,
        "units": units,
        "records": _sort_records(rows),
    }
