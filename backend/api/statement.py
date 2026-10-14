from fastapi.responses import Response
from api.statement_pdf import make_pdf
from fastapi import APIRouter, Depends, HTTPException
from core.db import supabase
from core.security import current_student

router = APIRouter(prefix="/student", tags=["statement"])


def _fmt(d) -> str:
    """'2026-03-18...' -> '18/03/2026'"""
    if not d:
        return ""
    y, m, day = str(d)[:10].split("-")
    return f"{day}/{m}/{y}"


def build_statement(student_id: str) -> dict:
    cfg_rows = supabase.table("settings").select("*").eq("id", 1).limit(1).execute().data
    cfg = cfg_rows[0] if cfg_rows else {}

    srows = (
        supabase.table("students")
        .select("name,reg_number,year_of_study,semester,admission_year")
        .eq("id", student_id)
        .limit(1)
        .execute()
        .data
    )
    if not srows:
        raise HTTPException(404, "Student not found")
    s = srows[0]

    terms = supabase.table("fee_terms").select("id,academic_year,semester").execute().data
    terms.sort(key=lambda t: (t["academic_year"], t["semester"]))

    charges = (
        supabase.table("fee_charges")
        .select("term_id,amount,description,ref,charge_date,created_at")
        .eq("student_id", student_id)
        .execute()
        .data
    )
    pays = (
        supabase.table("payments")
        .select("term_id,amount,description,ref,paystack_reference,paid_at,created_at")
        .eq("student_id", student_id)
        .eq("status", "success")
        .execute()
        .data
    )

    by_term = {t["id"]: [] for t in terms}
    last_term = terms[-1]["id"] if terms else None

    for c in charges:
        tid = c["term_id"] or last_term
        if tid in by_term:
            by_term[tid].append({
                "date": str(c.get("charge_date") or c["created_at"])[:10],
                "kind": 0,  # debits sort before credits on the same day
                "ref": c.get("ref") or "",
                "description": c.get("description") or "INVOICE",
                "debit": float(c["amount"]),
                "credit": 0.0,
            })
    for p in pays:
        tid = p["term_id"] or last_term
        if tid in by_term:
            by_term[tid].append({
                "date": str(p.get("paid_at") or p["created_at"])[:10],
                "kind": 1,
                "ref": p.get("ref") or p.get("paystack_reference") or "",
                "description": p.get("description") or "PAYMENT",
                "debit": 0.0,
                "credit": float(p["amount"]),
            })

    semesters = []
    running = total_debit = total_credit = 0.0
    for t in terms:
        entries = sorted(by_term.get(t["id"], []), key=lambda e: (e["date"], e["kind"]))
        if not entries:
            continue
        rows = []
        for i, e in enumerate(entries, 1):
            running += e["debit"] - e["credit"]
            total_debit += e["debit"]
            total_credit += e["credit"]
            rows.append({
                "no": i,
                "date": _fmt(e["date"]),
                "ref": e["ref"],
                "description": e["description"],
                "debit": e["debit"],
                "credit": e["credit"],
                "balance": round(running, 2),
            })
        semesters.append({"label": f"Semester {t['semester']} {t['academic_year']}", "rows": rows})

    return {
        "header": {
            "school_name": cfg.get("school_name") or "",
            "location": cfg.get("location") or "",
            "phone": cfg.get("phone") or "",
            "email": cfg.get("email") or "",
        },
        "student": {
            "name": s["name"],
            "reg_number": s["reg_number"],
            "programme": cfg.get("programme") or "",
            "department": cfg.get("department") or "",
            "school": cfg.get("school") or "",
            "student_type": cfg.get("programme_type") or "",
            "admission_year": s.get("admission_year"),
            "year_of_study": s["year_of_study"],
            "term": s["semester"],
        },
        "semesters": semesters,
        "totals": {
            "debit": round(total_debit, 2),
            "credit": round(total_credit, 2),
            "balance": round(running, 2),
        },
    }


@router.get("/statement")
def statement(student_id: str = Depends(current_student)):
    return build_statement(student_id)


@router.get("/statement/pdf")
def statement_pdf(student_id: str = Depends(current_student)):
    pdf = make_pdf(build_statement(student_id))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="fee-statement.pdf"'},
    )
