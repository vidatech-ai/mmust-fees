from fastapi import APIRouter

from core.db import supabase

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/school")
def school():
    rows = supabase.table("settings").select("school_name").eq("id", 1).limit(1).execute().data
    return {"school_name": (rows[0]["school_name"] if rows else "") or ""}
