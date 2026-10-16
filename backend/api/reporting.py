from fastapi import APIRouter, Depends, HTTPException

from api.academic import _need_session
from core.db import supabase
from core.security import current_student

router = APIRouter(tags=["reporting"])


@router.get("/student/reporting")
def my_reports(student_id: str = Depends(current_student)):
    rows = (
        supabase.table("semester_reports")
        .select("id,academic_year,semester,report_type,reported_at")
        .eq("student_id", student_id).limit(200).execute().data
    )
    rows.sort(key=lambda r: r["reported_at"], reverse=True)
    return {"reports": rows}


@router.post("/student/reporting")
def report_now(student_id: str = Depends(current_student)):
    ay, sem = _need_session()
    existing = (
        supabase.table("semester_reports").select("id")
        .eq("student_id", student_id).eq("academic_year", ay).eq("semester", sem)
        .limit(1).execute().data
    )
    if existing:
        raise HTTPException(400, "You have already reported for this semester")
    supabase.table("semester_reports").insert({
        "student_id": student_id, "academic_year": ay, "semester": sem,
        "report_type": "Reported Online",
    }).execute()
    return {"ok": True}
