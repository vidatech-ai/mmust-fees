from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from core.db import supabase
from core.security import current_student

router = APIRouter(prefix="/student", tags=["student"])


@router.get("/me")
def me(student_id: str = Depends(current_student)):
    rows = (
        supabase.table("students")
        .select("name,reg_number,year_of_study,semester,photo_url")
        .eq("id", student_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(404, "Student not found")
    s = rows[0]

    bal = (
        supabase.table("student_balances")
        .select("balance,total_charged,total_paid")
        .eq("student_id", student_id)
        .limit(1)
        .execute()
        .data
    )
    b = bal[0] if bal else {}

    unread = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("student_id", student_id)
        .eq("sender", "admin")
        .is_("read_at", "null")
        .execute()
        .count
        or 0
    )

    cfg_rows = (
        supabase.table("settings")
        .select("school_name,programme,current_academic_year,current_semester,semester_start,semester_end")
        .eq("id", 1)
        .limit(1)
        .execute()
        .data
    )
    cfg = cfg_rows[0] if cfg_rows else {}
    progress = None
    try:
        start = date.fromisoformat(str(cfg["semester_start"])[:10])
        end = date.fromisoformat(str(cfg["semester_end"])[:10])
        span = (end - start).days
        if span > 0:
            progress = max(0, min(100, round((date.today() - start).days / span * 100)))
    except (KeyError, TypeError, ValueError):
        progress = None
    label = ""
    if cfg.get("current_academic_year") and cfg.get("current_semester"):
        label = f"Semester {cfg['current_semester']} {cfg['current_academic_year']}"
    session = {"label": label, "programme": cfg.get("programme") or "", "progress": progress, "school_name": cfg.get("school_name") or ""}

    return {
        **s,
        "session": session,
        "balance": float(b.get("balance") or 0),
        "total_charged": float(b.get("total_charged") or 0),
        "total_paid": float(b.get("total_paid") or 0),
        "unread": unread,
    }
