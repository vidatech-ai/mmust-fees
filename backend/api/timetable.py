import uuid
from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import supabase
from core.security import current_admin, current_student

router = APIRouter(tags=["timetable"])

CLASS_TYPES = ["lecture", "practical", "tutorial", "clinical", "cat", "exam"]
EVENT_KINDS = ["semester", "cat", "exam", "holiday", "event"]


class ClassIn(BaseModel):
    day_of_week: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    unit_code: str = Field("", max_length=30)
    unit_name: str = Field("", max_length=150)
    lecturer: str = Field("", max_length=120)
    venue: str = Field("", max_length=120)
    class_type: str = "lecture"
    year_of_study: int | None = Field(None, ge=1, le=8)


class CheckIn(ClassIn):
    exclude_id: uuid.UUID | None = None


class EventIn(BaseModel):
    title: str = Field("", max_length=150)
    kind: str = "event"
    event_date: date
    end_date: date | None = None
    details: str = Field("", max_length=500)
    year_of_study: int | None = Field(None, ge=1, le=8)


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


def _clean_class(body: ClassIn) -> dict:
    if not body.unit_name.strip():
        raise HTTPException(400, "Enter the unit name")
    if body.end_time <= body.start_time:
        raise HTTPException(400, "The end time must be after the start time")
    if body.class_type not in CLASS_TYPES:
        raise HTTPException(400, "Choose a class type from the list")
    return {
        "day_of_week": body.day_of_week,
        "start_time": body.start_time.strftime("%H:%M:%S"),
        "end_time": body.end_time.strftime("%H:%M:%S"),
        "unit_code": body.unit_code.strip().upper(),
        "unit_name": body.unit_name.strip(),
        "lecturer": body.lecturer.strip(),
        "venue": body.venue.strip(),
        "class_type": body.class_type,
        "year_of_study": body.year_of_study,
    }


def _clean_event(body: EventIn) -> dict:
    if not body.title.strip():
        raise HTTPException(400, "Enter a title")
    if body.kind not in EVENT_KINDS:
        raise HTTPException(400, "Choose a type from the list")
    if body.end_date and body.end_date < body.event_date:
        raise HTTPException(400, "The end date cannot be before the start date")
    return {
        "title": body.title.strip(),
        "kind": body.kind,
        "event_date": body.event_date.isoformat(),
        "end_date": body.end_date.isoformat() if body.end_date else None,
        "details": body.details.strip(),
        "year_of_study": body.year_of_study,
    }


def _out(r: dict) -> dict:
    return {**r, "start_time": str(r["start_time"])[:5], "end_time": str(r["end_time"])[:5]}


# ---------- admin ----------

@router.get("/admin/timetable")
def admin_timetable(_admin: str = Depends(current_admin)):
    ay, sem = _session()
    classes = []
    if ay and sem:
        classes = (
            supabase.table("timetable_classes").select("*")
            .eq("academic_year", ay).eq("semester", sem).limit(1000).execute().data
        )
    classes = [_out(c) for c in classes]
    classes.sort(key=lambda r: (r["day_of_week"], r["start_time"]))
    events = (
        supabase.table("timetable_entries")
        .select("id,title,kind,event_date,end_date,details,year_of_study")
        .limit(1000).execute().data
    )
    events = [e for e in events if e.get("event_date")]
    events.sort(key=lambda e: e["event_date"])
    return {"session": {"academic_year": ay, "semester": sem}, "classes": classes, "events": events}


@router.post("/admin/timetable/classes/check")
def check_class(body: CheckIn, _admin: str = Depends(current_admin)):
    ay, sem = _need_session()
    c = _clean_class(body)
    rows = (
        supabase.table("timetable_classes")
        .select("id,unit_code,unit_name,lecturer,venue,start_time,end_time,year_of_study")
        .eq("academic_year", ay).eq("semester", sem).eq("day_of_week", c["day_of_week"])
        .limit(1000).execute().data
    )
    out = []
    for r in rows:
        if body.exclude_id and r["id"] == str(body.exclude_id):
            continue
        rs, re_ = str(r["start_time"])[:5], str(r["end_time"])[:5]
        if not (c["start_time"][:5] < re_ and rs < c["end_time"][:5]):
            continue
        label = f"{r['unit_code'] or r['unit_name']} ({rs}-{re_})"
        if c["venue"] and (r.get("venue") or "").lower() == c["venue"].lower():
            out.append(f"Venue {c['venue']} is already used by {label}")
        if c["lecturer"] and (r.get("lecturer") or "").lower() == c["lecturer"].lower():
            out.append(f"{c['lecturer']} already teaches {label}")
        ry = r.get("year_of_study")
        if c["year_of_study"] is None or ry is None or ry == c["year_of_study"]:
            out.append(f"The same students already have {label}")
    return {"clashes": out}


@router.post("/admin/timetable/classes")
def add_class(body: ClassIn, admin_id: str = Depends(current_admin)):
    ay, sem = _need_session()
    row = {**_clean_class(body), "academic_year": ay, "semester": sem}
    created = supabase.table("timetable_classes").insert(row).execute().data[0]
    _audit(admin_id, "create", "timetable_classes", created["id"], None, row)
    return {"id": created["id"]}


@router.put("/admin/timetable/classes/{class_id}")
def edit_class(class_id: uuid.UUID, body: ClassIn, admin_id: str = Depends(current_admin)):
    cid = str(class_id)
    old = _need("timetable_classes", cid, "Class")
    new = _clean_class(body)
    supabase.table("timetable_classes").update(new).eq("id", cid).execute()
    _audit(admin_id, "update", "timetable_classes", cid, old, new)
    return {"ok": True}


@router.delete("/admin/timetable/classes/{class_id}")
def delete_class(class_id: uuid.UUID, admin_id: str = Depends(current_admin)):
    cid = str(class_id)
    old = _need("timetable_classes", cid, "Class")
    supabase.table("timetable_classes").delete().eq("id", cid).execute()
    _audit(admin_id, "delete", "timetable_classes", cid, old, None)
    return {"ok": True}


@router.post("/admin/timetable/events")
def add_event(body: EventIn, admin_id: str = Depends(current_admin)):
    row = _clean_event(body)
    created = supabase.table("timetable_entries").insert(row).execute().data[0]
    _audit(admin_id, "create", "timetable_entries", created["id"], None, row)
    return {"id": created["id"]}


@router.put("/admin/timetable/events/{event_id}")
def edit_event(event_id: uuid.UUID, body: EventIn, admin_id: str = Depends(current_admin)):
    eid = str(event_id)
    old = _need("timetable_entries", eid, "Key date")
    new = _clean_event(body)
    supabase.table("timetable_entries").update(new).eq("id", eid).execute()
    _audit(admin_id, "update", "timetable_entries", eid, old, new)
    return {"ok": True}


@router.delete("/admin/timetable/events/{event_id}")
def delete_event(event_id: uuid.UUID, admin_id: str = Depends(current_admin)):
    eid = str(event_id)
    old = _need("timetable_entries", eid, "Key date")
    supabase.table("timetable_entries").delete().eq("id", eid).execute()
    _audit(admin_id, "delete", "timetable_entries", eid, old, None)
    return {"ok": True}


# ---------- student ----------

@router.get("/student/timetable")
def student_timetable(student_id: str = Depends(current_student)):
    srows = supabase.table("students").select("year_of_study").eq("id", student_id).limit(1).execute().data
    year = srows[0]["year_of_study"] if srows else None
    ay, sem = _session()

    classes = []
    if ay and sem:
        rows = (
            supabase.table("timetable_classes")
            .select("id,day_of_week,start_time,end_time,unit_code,unit_name,lecturer,venue,class_type,year_of_study")
            .eq("academic_year", ay).eq("semester", sem).limit(1000).execute().data
        )
        classes = [_out(c) for c in rows if c.get("year_of_study") in (None, year)]
        classes.sort(key=lambda r: (r["day_of_week"], r["start_time"]))

    cutoff = (date.today() - timedelta(days=14)).isoformat()
    ev = (
        supabase.table("timetable_entries")
        .select("id,title,kind,event_date,end_date,details,year_of_study")
        .limit(1000).execute().data
    )
    events = [
        e for e in ev
        if e.get("event_date")
        and (e.get("end_date") or e["event_date"]) >= cutoff
        and e.get("year_of_study") in (None, year)
    ]
    events.sort(key=lambda e: e["event_date"])
    return {"session": {"academic_year": ay, "semester": sem}, "classes": classes, "events": events}
