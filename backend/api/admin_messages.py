import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import supabase
from core.security import current_admin

router = APIRouter(prefix="/admin/messages", tags=["admin-messages"])


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.get("/conversations")
def conversations(_admin: str = Depends(current_admin)):
    students = supabase.table("students").select("id,name,reg_number,active").order("name").limit(1000).execute().data
    msgs = (
        supabase.table("messages").select("student_id,sender,body,read_at,created_at")
        .order("created_at", desc=True).limit(3000).execute().data
    )
    last, unread = {}, {}
    for m in msgs:
        sid = m["student_id"]
        if sid not in last:
            last[sid] = m
        if m["sender"] == "student" and m["read_at"] is None:
            unread[sid] = unread.get(sid, 0) + 1

    out = []
    for s in students:
        l = last.get(s["id"])
        out.append({
            "student_id": s["id"], "name": s["name"], "reg_number": s["reg_number"], "active": s["active"],
            "last_body": l["body"][:80] if l else "", "last_at": l["created_at"] if l else None,
            "unread": unread.get(s["id"], 0),
        })
    out.sort(key=lambda c: c["name"].lower())
    out.sort(key=lambda c: c["last_at"] or "", reverse=True)  # newest chats first
    return out


@router.get("/thread/{student_id}")
def thread(student_id: uuid.UUID, _admin: str = Depends(current_admin)):
    sid = str(student_id)
    msgs = (
        supabase.table("messages").select("id,sender,body,created_at")
        .eq("student_id", sid).order("created_at", desc=True).limit(300).execute().data
    )
    msgs.reverse()
    supabase.table("messages").update({"read_at": datetime.now(timezone.utc).isoformat()}) \
        .eq("student_id", sid).eq("sender", "student").is_("read_at", "null").execute()
    return msgs


@router.post("/thread/{student_id}")
def send(student_id: uuid.UUID, body: MessageIn, _admin: str = Depends(current_admin)):
    sid = str(student_id)
    text = body.body.strip()
    if not text:
        raise HTTPException(400, "Message is empty")
    if not supabase.table("students").select("id").eq("id", sid).limit(1).execute().data:
        raise HTTPException(404, "Student not found")
    row = supabase.table("messages").insert({"student_id": sid, "sender": "admin", "body": text}).execute().data[0]
    return {"id": row["id"]}
