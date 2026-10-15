import io
import os

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

LOGO = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "assets", "logo.jpg")
INK = colors.HexColor("#111111")
GRID = colors.HexColor("#888888")
HEAD = colors.HexColor("#eeeeee")

GRADING = [("75-100", "A"), ("65-74", "B"), ("50-64", "C"), ("0-49", "E")]
OTHER_KEYS = [("#", "Audited Unit"), ("*", "Supplementary"), ("**", "Retake"), ("-", "Missing Marks"),
              ("CT", "Credit Transfer"), ("I", "Incomplete"), ("NA", "Mark Type Not Applicable")]
NOTE = "NB: This result slip is issued without any erasures or alterations. Not Valid without Official Stamp"


def _qr(c, text, x, y, size):
    w = qr.QrCodeWidget(text)
    b = w.getBounds()
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
    d.add(w)
    renderPDF.draw(d, c, x, y)


def make_result_slip(school, location, phone, email, name, programme, department, faculty,
                     reg, admission_year, year_of_study, semester, units, qr_text) -> bytes:
    """units: list of dicts with code, title, hours, grade"""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Result Slip")
    W, H = A4
    L, R = 12 * mm, W - 12 * mm

    def Y(t):
        return H - t * mm

    # QR top right
    q = 26 * mm
    _qr(c, qr_text, R - q, Y(12) - q, q)

    # logo, centred
    y = 14
    if os.path.exists(LOGO):
        iw, ih = ImageReader(LOGO).getSize()
        lh = 38 * mm
        lw = lh * iw / ih
        if lw > 90 * mm:
            lw = 90 * mm
            lh = lw * ih / iw
        c.drawImage(LOGO, (W - lw) / 2, Y(y) - lh, lw, lh, mask="auto")
        y += lh / mm + 7

    # school header
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(W / 2, Y(y), (school or "").upper())
    y += 5.5
    c.setFont("Helvetica-Bold", 8.5)
    for line in (location, ("TEL: " + phone) if phone else "", ("Email: " + email) if email else ""):
        if line:
            c.drawCentredString(W / 2, Y(y), line)
            y += 4.5
    c.setFont("Helvetica", 8)
    c.drawCentredString(W / 2, Y(y), "OFFICE OF THE REGISTRAR \u2013 ACADEMICS")
    y += 4.5
    c.drawCentredString(W / 2, Y(y), "Result Slip")
    y += 5
    c.setStrokeColor(INK)
    c.setLineWidth(0.8)
    c.line(L, Y(y), R, Y(y))
    y += 5

    # student details
    def block(items, x, maxw, y0):
        yy = y0
        for label, value in items:
            c.setFont("Helvetica-Bold", 7.5)
            tag = label + ": "
            tw = c.stringWidth(tag, "Helvetica-Bold", 7.5)
            c.drawString(x, Y(yy), tag)
            c.setFont("Helvetica", 7.5)
            for ln in simpleSplit(str(value or "").upper(), "Helvetica", 7.5, maxw - tw):
                c.drawString(x + tw, Y(yy), ln)
                yy += 3.6
        return yy

    y1 = block([("STUDENT NAME", name), ("PROGRAMME", programme), ("DEPARTMENT", department),
                ("SCHOOL/FACULTY", faculty)], L, 125 * mm, y)
    y2 = block([("REG NO", reg), ("ADMISSION YEAR", admission_year),
                ("YEAR OF STUDY", f"Year {year_of_study} Semester {semester}")], 140 * mm, R - 140 * mm, y)
    y = max(y1, y2) + 4

    # results table
    cols = [30 * mm, 106 * mm, 25 * mm, 25 * mm]
    xs = [L]
    for w_ in cols:
        xs.append(xs[-1] + w_)
    rh = 6.2

    def row(cells, yy, head=False):
        c.setFillColor(HEAD if head else colors.white)
        c.setStrokeColor(GRID)
        c.setLineWidth(0.5)
        c.rect(L, Y(yy + rh), sum(cols), rh * mm, fill=1, stroke=1)
        for x in xs[1:-1]:
            c.line(x, Y(yy), x, Y(yy + rh))
        c.setFillColor(INK)
        size = 7.5
        font = "Helvetica-Bold" if head else "Helvetica"
        for i, t in enumerate(cells):
            t = str(t)
            s = size
            while c.stringWidth(t, font, s) > cols[i] - 4 * mm and s > 5:
                s -= 0.25
            c.setFont(font, s)
            if i < 2:
                c.drawString(xs[i] + 2 * mm, Y(yy + rh / 2 + 1), t)
            else:
                c.drawCentredString((xs[i] + xs[i + 1]) / 2, Y(yy + rh / 2 + 1), t)

    row(["UNIT CODE", "UNIT TITLE", "HOURS", "GRADE"], y, head=True)
    y += rh
    for u in units:
        if y + rh > 297 - 20:
            c.showPage()
            y = 15
        row([u.get("code", ""), (u.get("title") or "").upper(), u.get("hours", ""), u.get("grade", "")], y)
        y += rh
    y += 7

    # keys
    if y + 62 > 297 - 12:
        c.showPage()
        y = 15

    def keys(title, heads, rows, x, widths, y0):
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, Y(y0), title)
        c.setStrokeColor(INK)
        c.setLineWidth(0.5)
        c.line(x, Y(y0) - 1, x + c.stringWidth(title, "Helvetica-Bold", 8), Y(y0) - 1)
        yy = y0 + 5.5
        c.setFont("Helvetica-Bold", 7.5)
        xx = x
        for h_, w_ in zip(heads, widths):
            c.drawString(xx, Y(yy), h_)
            xx += w_
        yy += 4.4
        c.setFont("Helvetica", 7.5)
        for r_ in rows:
            xx = x
            for v, w_ in zip(r_, widths):
                c.drawString(xx, Y(yy), v)
                xx += w_
            yy += 4.4
        return yy

    k1 = keys("Key Grading System", ("Grade", "Points"), GRADING, L, (40 * mm, 20 * mm), y)
    k2 = keys("Other Keys", ("Symbol", "Names"), OTHER_KEYS, 115 * mm, (30 * mm, 50 * mm), y)
    y = max(k1, k2) + 6
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(W / 2, Y(y), NOTE)

    c.showPage()
    c.save()
    return buf.getvalue()
