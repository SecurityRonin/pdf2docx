"""The output must contain the source's content and nothing else, and must
open in a renderer without corrupting its glyphs.

Both tests here encode defects the render oracle found that the structural
tests could not: the template's cover page and running footer leaked into the
output, and the house font did not resolve, breaking every 'e' into (cid:2).
"""
import pathlib
import re
import shutil
import subprocess
import zipfile

import docx
import pdfplumber
import pytest

from pdf2docx import convert


def _render(docx_path, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    exe = shutil.which("soffice")
    if exe is None:
        pytest.skip("LibreOffice not available")
    subprocess.run([exe, "--headless", "--convert-to", "pdf", str(docx_path),
                    "--outdir", str(outdir)], check=True, capture_output=True, timeout=120)
    return outdir / (docx_path.stem + ".pdf")


def test_output_adds_no_text_the_source_did_not_contain(numbered_pdf, tmp_path):
    """Nothing from the template may leak: no cover line, no running footer.

    Checked by comparing vocabularies rather than by naming one template's
    strings: a list of literals only proves those literals are absent, and any
    other stationery would pass. Every word in the DOCX must exist in the PDF.
    """
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)

    with pdfplumber.open(numbered_pdf) as pdf:
        source_words = set()
        for pg in pdf.pages:
            source_words |= set(re.findall(r"[A-Za-z0-9]+",
                                           (pg.extract_text() or "").lower()))

    doc_words = set()
    for para in docx.Document(str(out)).paragraphs:
        doc_words |= set(re.findall(r"[A-Za-z0-9]+", para.text.lower()))

    invented = doc_words - source_words
    assert not invented, f"DOCX contains words absent from the source: {invented}"


def test_blanks_before_bullets_are_not_paragraphs(numbered_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    blanks = [p for p in docx.Document(str(out)).paragraphs if not p.text.strip()]
    assert not blanks


def test_rendered_text_is_not_glyph_corrupted(numbered_pdf, tmp_path):
    """A font that does not resolve turns text into (cid:N) on render."""
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    pdf = _render(out, tmp_path / "render")
    with pdfplumber.open(pdf) as p:
        text = "\n".join((pg.extract_text() or "") for pg in p.pages)
    assert "(cid:" not in text
    assert "review covered" in text.lower()


def test_bullets_actually_render(numbered_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    pdf = _render(out, tmp_path / "render")
    with pdfplumber.open(pdf) as p:
        text = "\n".join((pg.extract_text() or "") for pg in p.pages)
    assert "Mail server" in text
    assert any(g in text for g in ("•", "▪", "◦", "‣", "·")), text
