from fastapi import APIRouter, Depends
from core.db import supabase
from core.security import current_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
def overview(_admin: str = Depends(current_admin)):
    total = supabase.table("students").select("id", count="exact").execute().count or 0
    active = (
        supabase.table("students").select("id", count="exact").eq("active", True).execute().count or 0
    )
    unread = (
        supabase.table("messages")
        .select("id", count="exact")
        .eq("sender", "student")
        .is_("read_at", "null")
        .execute()
        .count
        or 0
    )
    rows = supabase.table("student_balances").select("balance,total_charged,total_paid").execute().data

    return {
        "students_total": total,
        "students_active": active,
        "unread_messages": unread,
        "total_charged": sum(float(r.get("total_charged") or 0) for r in rows),
        "total_paid": sum(float(r.get("total_paid") or 0) for r in rows),
        "total_outstanding": sum(float(r.get("balance") or 0) for r in rows),
    }
