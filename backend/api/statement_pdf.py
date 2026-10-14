import io
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

LOGO = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "assets", "logo.jpg")
NAVY = colors.HexColor("#0b3a7e")
GRID = colors.HexColor("#c9cfdb")
HEAD_BG = colors.HexColor("#f1f3f9")
BAND_BG = colors.HexColor("#e8f1fd")
RED = colors.HexColor("#b42318")


def _money(n) -> str:
    return f"{float(n or 0):,.2f}"


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(RED)
    pass
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def make_pdf(d: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=18 * mm, title="Fee Statement",
    )

    base = ParagraphStyle("base", fontName="Helvetica", fontSize=8.5, leading=11)
    center = ParagraphStyle("center", parent=base, alignment=1)
    name_st = ParagraphStyle("name", parent=center, fontName="Helvetica-Bold", fontSize=13, leading=16)
    title_st = ParagraphStyle("title", parent=center, fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=6)
    demo_st = ParagraphStyle("demo", parent=center, textColor=RED, fontSize=8)
    bold = ParagraphStyle("bold", parent=base, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3)

    h, s = d["header"], d["student"]
    story = []

    # --- header ---
    if os.path.exists(LOGO):
        iw, ih = ImageReader(LOGO).getSize()
        height = 20 * mm
        img = Image(LOGO, width=height * iw / ih, height=height)
        img.hAlign = "CENTER"
        story += [img, Spacer(1, 3)]
    if h["school_name"]:
        story.append(Paragraph(escape(h["school_name"]), name_st))
    if h["location"]:
        story.append(Paragraph(escape(h["location"]), center))
    if h["phone"]:
        story.append(Paragraph("TEL: " + escape(h["phone"]), center))
    if h["email"]:
        story.append(Paragraph("Email: " + escape(h["email"]), center))
    story += [
        Paragraph("Fee Statement", title_st),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=1.5, color=NAVY),
        Spacer(1, 6),
    ]

    # --- student details box ---
    def lines(pairs):
        out = []
        for label, value in pairs:
            if value in ("", None):
                continue
            out.append(f"<b>{escape(label)}:</b> {escape(str(value).upper())}")
        return Paragraph("<br/>".join(out), base)

    left = lines([
        ("STUDENT NAME", s["name"]), ("PROGRAMME", s["programme"]), ("DEPARTMENT", s["department"]),
        ("SCHOOL/FACULTY", s["school"]), ("STUDENT TYPE", s["student_type"]),
    ])
    right = lines([
        ("REGNO", s["reg_number"]), ("ADMISSION YEAR", s["admission_year"]),
        ("YEAR OF STUDY", f"Year {s['year_of_study']}"), ("TERM", f"Semester {s['term']}"),
    ])
    info = Table([[left, right]], colWidths=[115 * mm, 65 * mm])
    info.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, GRID),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafbfe")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [info, Paragraph("HOUSEHOLD BREAKDOWN", bold)]

    # --- one table per semester ---
    widths = [w * mm for w in (10, 22, 26, 50, 24, 24, 24)]
    cell = ParagraphStyle("cell", parent=base, fontSize=8)
    for sem in d["semesters"]:
        data = [
            [sem["label"].upper(), "", "", "", "", "", ""],
            ["No", "Date", "Ref", "Description", "Debit (KES)", "Credit (KES)", "Balance (KES)"],
        ]
        for r in sem["rows"]:
            data.append([
                str(r["no"]), r["date"], Paragraph(escape(r["ref"]), cell), Paragraph(escape(r["description"]), cell),
                _money(r["debit"]), _money(r["credit"]), _money(r["balance"]),
            ])
        t = Table(data, colWidths=widths, repeatRows=2)
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, GRID),
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), BAND_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
            ("BACKGROUND", (0, 1), (-1, 1), HEAD_BG),
            ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story += [t, Spacer(1, 8)]

    # --- grand totals ---
    story.append(Paragraph("HOUSEHOLD", bold))
    tot = d["totals"]
    tt = Table(
        [["Debit (KES)", "Credit (KES)", "Balance (KES)"],
         [_money(tot["debit"]), _money(tot["credit"]), _money(tot["balance"])]],
        colWidths=[60 * mm] * 3,
    )
    tt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("BACKGROUND", (0, 0), (-1, -1), HEAD_BG),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tt)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
