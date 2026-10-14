from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.db import supabase
from core.security import current_student

router = APIRouter(prefix="/student/messages", tags=["student messages"])


class NewMessage(BaseModel):
    body: str


@router.get("")
def list_messages(student_id: str = Depends(current_student)):
    rows = (
        supabase.table("messages")
        .select("id,sender,body,created_at,read_at")
        .eq("student_id", student_id)
        .order("created_at")
        .limit(500)
        .execute()
        .data
    )
    # opening the chat marks admin messages as read
    supabase.table("messages").update(
        {"read_at": datetime.now(timezone.utc).isoformat()}
    ).eq("student_id", student_id).eq("sender", "admin").is_("read_at", "null").execute()
    return rows


@router.post("")
def send_message(body: NewMessage, student_id: str = Depends(current_student)):
    text = body.body.strip()
    if not text:
        raise HTTPException(400, "Message is empty")
    if len(text) > 2000:
        raise HTTPException(400, "Message is too long (max 2000 characters)")
    row = (
        supabase.table("messages")
        .insert({"student_id": student_id, "sender": "student", "body": text})
        .execute()
        .data[0]
    )
    return row
