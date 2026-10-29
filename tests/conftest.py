"""Shared fixtures: synthetic PDFs built with reportlab, so a test states the
document it means instead of depending on a file that may move."""
import pathlib

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

W, H = A4


@pytest.fixture
def numbered_pdf(tmp_path):
    """A page with a title, two numbered sections, body text and a bullet list."""
    out = tmp_path / "numbered.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)
    y = H - 80

    c.setFont("Helvetica-Bold", 20)
    c.drawString(60, y, "Quarterly Security Review")
    y -= 44

    c.setFont("Helvetica-Bold", 15)
    c.drawString(60, y, "1. Scope of the Review")
    y -= 26
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y, "1.1 Systems Covered")
    y -= 20
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(60, y, "The review covered the following systems in scope.")
    y -= 16
    for item in ("Mail server", "File server", "Directory service"):
        c.setFont("Helvetica", 10)
        c.drawString(78, y, item)
        y -= 14

    y -= 12
    c.setFont("Helvetica-Bold", 15)
    c.drawString(60, y, "2. Findings")
    y -= 26
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(60, y, "Two findings were recorded during the review.")
    c.showPage()
    c.save()
    return out


@pytest.fixture
def footnote_pdf(tmp_path):
    """A paragraph carrying one superscript footnote mark and its note text."""
    out = tmp_path / "footnote.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)
    y = H - 80
    c.setFont("Helvetica", 12)
    c.drawString(60, y, "The witness statement was signed on 12 March.")
    from reportlab.pdfbase.pdfmetrics import stringWidth
    x = 60 + stringWidth("The witness statement was signed on 12 March.", "Helvetica", 12)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.setFont("Helvetica", 7)
    c.drawString(x + 1, y + 4, "1")          # raised: the footnote mark
    c.setFillColorRGB(0, 0, 0)
    # the note itself, below a separator, smaller than body text
    c.setFont("Helvetica", 14)
    c.drawString(60, 120, "—" * 12)
    c.setFont("Helvetica", 8)
    c.drawString(60, 106, "1  Statement of A. Example, 12 March 2026, paragraph 4.")
    c.showPage()
    c.save()
    return out


@pytest.fixture
def tabled_pdf(tmp_path):
    """A ruled table with a spanning header cell, drawn with reportlab."""
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    out = tmp_path / "tabled.pdf"
    doc = SimpleDocTemplate(str(out), pagesize=A4)
    rows = [
        ["Evidence overview", "", ""],
        ["Name", "Role", "Exhibit"],
        ["Alice", "Analyst", "KTH-1"],
        ["Bob", "Reviewer", "KTH-2"],
        ["Carol", "Analyst", "KTH-3"],
    ]
    t = Table(rows, colWidths=[120, 120, 100])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.grey),
        ("SPAN", (0, 0), (2, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
    ]))
    doc.build([t])
    return out
