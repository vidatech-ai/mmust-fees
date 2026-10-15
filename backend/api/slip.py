import hashlib
import io
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from core.db import supabase
from core.security import current_student

router = APIRouter(prefix="/payments", tags=["payment-slip"])

LOGO = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "assets", "logo.jpg")
POWERED_BY = "Jiunge"          # change this text, or set to "" to hide the line
SERVICE_TYPE = "Tuition Fees"
INK = colors.HexColor("#222222")
MUTED = colors.HexColor("#555555")
LINE = colors.HexColor("#9a9a9a")
QR_BG = colors.HexColor("#eeeeee")


def _slip_no(ref: str) -> str:
    n = int(hashlib.sha256(ref.encode()).hexdigest(), 16) % 9_000_000 + 1_000_000
    return f"SLP{n}"


def _when(p: dict) -> str:
    raw = str(p.get("paid_at") or p.get("created_at") or "")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[:10]
    if len(raw) <= 10:
        return dt.strftime("%d %B %Y")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=3))).strftime("%d %B %Y %I:%M %p")


def _amount(a: float) -> str:
    return f"KES {a:,.0f}" if a == int(a) else f"KES {a:,.2f}"


def _draw_qr(c, text, x, y, size):
    w = qr.QrCodeWidget(text)
    b = w.getBounds()
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
    d.add(w)
    renderPDF.draw(d, c, x, y)


def make_slip(school, name, reg, amount, when, mode, invoice, receipt, slip_no, qr_text) -> bytes:
    buf = io.BytesIO()
    W, H = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle("Payment Slip")
    x0, w, h = 15 * mm, W - 30 * mm, 140 * mm
    top = H - 20 * mm
    right = x0 + w - 8 * mm

    def Y(t):
        return top - t * mm

    # outer frame
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.rect(x0, top - h, w, h)

    # title
    c.setFillColor(INK)
    c.setFont("Helvetica", 12)
    c.drawString(x0 + 8 * mm, Y(11), "PAYMENT SLIP")

    # logo + school name
    lx = x0 + 8 * mm
    if os.path.exists(LOGO):
        iw, ih = ImageReader(LOGO).getSize()
        lh = 16 * mm
        lw = min(lh * iw / ih, 40 * mm)
        c.drawImage(LOGO, lx, Y(32), width=lw, height=lh, preserveAspectRatio=True, mask="auto")
        lx += lw + 4 * mm
    c.setFont("Helvetica", 12)
    c.drawString(lx, Y(27), school or "")

    # received from
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawString(x0 + 8 * mm, Y(38), "Received from")
    c.setFillColor(INK)
    c.setFont("Helvetica", 10)
    c.drawString(x0 + 8 * mm, Y(44), f"{name.upper()} ({reg.upper()})")

    # QR + slip number
    q = 30 * mm
    qx = x0 + w - 8 * mm - q
    c.setFillColor(QR_BG)
    c.setStrokeColor(LINE)
    c.rect(qx, Y(6 + 30), q, q, fill=1, stroke=1)
    _draw_qr(c, qr_text, qx + 2 * mm, Y(6 + 30) + 2 * mm, q - 4 * mm)
    c.setFillColor(INK)
    c.setFont("Helvetica", 8)
    c.drawRightString(right, Y(46), slip_no)

    # separator + heading
    c.setStrokeColor(LINE)
    c.line(x0, Y(50), x0 + w, Y(50))
    c.setFont("Helvetica", 11)
    c.drawString(x0 + 6 * mm, Y(57), "Payment Details")

    # details box
    c.rect(x0 + 6 * mm, Y(62 + 60), w - 12 * mm, 60 * mm)
    rows = [
        ("Amount Paid:", _amount(amount)),
        ("Service Type:", SERVICE_TYPE),
        ("Payment Date:", when),
        ("Payment Mode:", mode),
        ("Invoice Number:", invoice),
        ("ERP Receipt Number:", receipt),
        ("Paid To:", school or ""),
    ]
    c.setFont("Helvetica", 10)
    for i, (label, value) in enumerate(rows):
        yy = Y(70 + i * 8)
        c.setFillColor(MUTED)
        c.drawString(x0 + 14 * mm, yy, label)
        c.setFillColor(INK)
        c.drawString(x0 + 105 * mm, yy, value)

    # footer
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 6 * mm, Y(128), "This is a computer-generated slip no signature required.")
    if POWERED_BY:
        c.drawString(x0 + 6 * mm, Y(135), f"Powered by {POWERED_BY}")

    c.showPage()
    c.save()
    return buf.getvalue()


PUBLIC_API = os.getenv("PUBLIC_API_URL", "https://mmust-fees-backend.onrender.com").rstrip("/")


def _ensure_slip_no(p: dict) -> str:
    if p.get("slip_no"):
        return p["slip_no"]
    for _ in range(10):
        no = "SLP" + str(secrets.randbelow(9_000_000) + 1_000_000)
        try:
            supabase.table("payments").update({"slip_no": no}) \
                .eq("id", p["id"]).is_("slip_no", "null").execute()
        except Exception:
            continue  # number already used by another slip, try again
        row = supabase.table("payments").select("slip_no").eq("id", p["id"]).limit(1).execute().data
        if row and row[0].get("slip_no"):
            return row[0]["slip_no"]
    raise HTTPException(500, "Could not create a slip number")


def _ensure_invoice_no(p: dict) -> str:
    if p.get("invoice_no"):
        return p["invoice_no"]
    for _ in range(10):
        no = "SFI" + str(secrets.randbelow(900_000) + 100_000)
        try:
            supabase.table("payments").update({"invoice_no": no}) \
                .eq("id", p["id"]).is_("invoice_no", "null").execute()
        except Exception:
            continue  # number already used, try again
        row = supabase.table("payments").select("invoice_no").eq("id", p["id"]).limit(1).execute().data
        if row and row[0].get("invoice_no"):
            return row[0]["invoice_no"]
    raise HTTPException(500, "Could not create an invoice number")


def _build(p: dict) -> bytes:
    sid = p["student_id"]
    st = supabase.table("students").select("name,reg_number").eq("id", sid).limit(1).execute().data[0]
    cfg = supabase.table("settings").select("school_name").eq("id", 1).limit(1).execute().data
    school = ((cfg[0].get("school_name") if cfg else "") or "").strip()

    invoice = _ensure_invoice_no(p)

    no = _ensure_slip_no(p)
    return make_slip(
        school=school, name=st["name"], reg=st["reg_number"], amount=float(p["amount"]), when=_when(p),
        mode="M-Pesa", invoice=invoice, receipt="", slip_no=no,
        qr_text=f"{PUBLIC_API}/payments/slip/view/{no}",
    )


@router.get("/slip/view/{slip_no}")
def view_slip(slip_no: str):
    """Public: opened when someone scans the QR code. Shows the slip as it is."""
    rows = supabase.table("payments").select("*").eq("slip_no", slip_no.strip().upper()).limit(1).execute().data
    if not rows or rows[0]["status"] != "success":
        raise HTTPException(404, "Slip not found")
    return Response(_build(rows[0]), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{slip_no}.pdf"'})


@router.get("/slip/{reference}")
def slip(reference: str, sid: str = Depends(current_student)):
    rows = (supabase.table("payments").select("*").eq("paystack_reference", reference)
            .eq("student_id", sid).limit(1).execute().data)
    if not rows:
        raise HTTPException(404, "Payment not found")
    if rows[0]["status"] != "success":
        raise HTTPException(400, "A slip is only available for completed payments")
    return Response(_build(rows[0]), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="payment-slip-{reference}.pdf"'})
