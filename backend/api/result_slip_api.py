import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response

from api.result_slip import make_result_slip
from api.slip import PUBLIC_API
from core.db import supabase
from core.security import current_student

router = APIRouter(tags=["result-slip"])


def grade_for(marks) -> str:
    """Grading key printed on the slip."""
    if marks is None:
        return "-"
    m = float(marks)
    if m >= 75:
        return "A"
    if m >= 65:
        return "B"
    if m >= 50:
        return "C"
    return "E"


def _hours(v):
    if v is None:
        return ""
    v = float(v)
    return int(v) if v == int(v) else v


def _rows(sid: str, ay: str, sem: int):
    """Results for one student, year and semester. Returns (year_of_study, units)."""
    recs = (supabase.table("transcript_records").select("*")
            .eq("student_id", sid).eq("academic_year", ay).eq("semester", sem)
            .limit(500).execute().data)
    if not recs:
        raise HTTPException(404, "No results posted for that year and semester")
    yos = recs[0]["year_of_study"]

    catalog = (supabase.table("academic_units").select("unit_code,credit_hours")
               .eq("academic_year", ay).eq("semester", sem).eq("year_of_study", yos)
               .limit(500).execute().data)
    hours = {(u.get("unit_code") or "").upper(): u.get("credit_hours") for u in catalog}

    recs.sort(key=lambda r: (r.get("unit_code") or "", r["unit_name"]))
    seen = set()
    units = []
    for r in recs:
        code = (r.get("unit_code") or "").strip().upper()
        if code:
            if code in seen:      # duplicate row in the database: show the unit once
                continue
            seen.add(code)
        units.append({
            "code": r.get("unit_code") or "",
            "title": r["unit_name"],
            "hours": _hours(hours.get(code)),
            "marks": r.get("marks"),
            "grade": grade_for(r.get("marks")),
        })
    return yos, units


def _build(sid: str, ay: str, sem: int) -> bytes:
    st = supabase.table("students").select("name,reg_number,admission_year").eq("id", sid).limit(1).execute().data
    if not st:
        raise HTTPException(404, "Student not found")
    st = st[0]
    yos, units = _rows(sid, ay, sem)

    cfg = supabase.table("settings").select("*").eq("id", 1).limit(1).execute().data
    cfg = cfg[0] if cfg else {}

    qr_text = f"{PUBLIC_API}/result-slip/view/{sid}?academic_year={quote(ay)}&semester={sem}"
    return make_result_slip(
        school=cfg.get("school_name") or "", location=cfg.get("location") or "",
        phone=cfg.get("phone") or "", email="",
        name=st["name"], programme=cfg.get("programme") or "",
        department=cfg.get("department") or "", faculty=cfg.get("school") or "",
        reg=st["reg_number"], admission_year=st.get("admission_year") or "",
        year_of_study=yos, semester=sem, units=units, qr_text=qr_text,
    )


# ---------- results transcript ----------

@router.get("/student/result-slip/options")
def options(student_id: str = Depends(current_student)):
    rows = (supabase.table("transcript_records").select("academic_year,semester")
            .eq("student_id", student_id).limit(2000).execute().data)
    pairs = sorted({(r["academic_year"], r["semester"]) for r in rows}, reverse=True)
    return {"options": [{"academic_year": a, "semester": s} for a, s in pairs]}


@router.get("/student/result-slip/data")
def data(academic_year: str, semester: int, student_id: str = Depends(current_student)):
    ay = academic_year.strip()
    yos, units = _rows(student_id, ay, semester)
    return {"academic_year": ay, "semester": semester, "year_of_study": yos, "units": units}


@router.get("/student/result-slip")
def download(academic_year: str, semester: int, student_id: str = Depends(current_student)):
    pdf = _build(student_id, academic_year.strip(), semester)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="result-slip.pdf"'})


@router.get("/result-slip/view/{student_id}")
def view(student_id: str, academic_year: str, semester: int):
    """Public: opened when someone scans the QR code."""
    try:
        sid = str(uuid.UUID(student_id))
    except ValueError:
        raise HTTPException(404, "Slip not found")
    pdf = _build(sid, academic_year.strip(), semester)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="result-slip.pdf"'})


# ---------- curriculum units ----------

@router.get("/student/curriculum/options")
def curriculum_options(student_id: str = Depends(current_student)):
    rows = supabase.table("academic_units").select("academic_year,semester").limit(2000).execute().data
    pairs = sorted({(r["academic_year"], r["semester"]) for r in rows}, reverse=True)
    return {"options": [{"academic_year": a, "semester": s} for a, s in pairs]}


@router.get("/student/curriculum")
def curriculum(academic_year: str, semester: int, student_id: str = Depends(current_student)):
    rows = (supabase.table("academic_units")
            .select("year_of_study,unit_code,unit_name,credit_hours")
            .eq("academic_year", academic_year.strip()).eq("semester", semester)
            .limit(500).execute().data)
    rows.sort(key=lambda u: (u["year_of_study"], u.get("unit_code") or "", u["unit_name"]))
    return {"units": rows}


# ---------- on-page slip ----------

@router.get("/student/result-slip/page")
def slip_page(academic_year: str, semester: int, student_id: str = Depends(current_student)):
    import base64
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing

    ay = academic_year.strip()
    st = supabase.table("students").select("name,reg_number,admission_year").eq("id", student_id).limit(1).execute().data
    if not st:
        raise HTTPException(404, "Student not found")
    st = st[0]
    yos, units = _rows(student_id, ay, semester)
    cfg = supabase.table("settings").select("*").eq("id", 1).limit(1).execute().data
    cfg = cfg[0] if cfg else {}

    qr_text = f"{PUBLIC_API}/result-slip/view/{student_id}?academic_year={quote(ay)}&semester={semester}"
    w = qr.QrCodeWidget(qr_text)
    b = w.getBounds()
    size = 120
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
    d.add(w)
    svg = d.asString("svg")
    if isinstance(svg, str):
        svg = svg.encode()
    qr_uri = "data:image/svg+xml;base64," + base64.b64encode(svg).decode()

    return {
        "school": cfg.get("school_name") or "", "location": cfg.get("location") or "",
        "phone": cfg.get("phone") or "",
        "name": st["name"], "programme": cfg.get("programme") or "",
        "department": cfg.get("department") or "", "faculty": cfg.get("school") or "",
        "reg": st["reg_number"], "admission_year": st.get("admission_year") or "",
        "year_of_study": yos, "semester": semester, "academic_year": ay,
        "units": units, "qr": qr_uri,
    }
