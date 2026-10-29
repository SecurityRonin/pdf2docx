"""Layout fidelity: the DOCX must reproduce the source page's typography.

"Visually close" is measured here rather than asserted: page size, body font,
body size and margins are read from the PDF and compared with the rendered
DOCX. Two modes are covered, because layout and structure conflict in exactly
one place — whether text reflows.

  semantic  typography matches, text reflows (pages differ)
  faithful  typography matches AND line/page breaks are pinned (pages match)
"""
import shutil
import subprocess

import pdfplumber
import pytest

from pdf2docx import convert
from pdf2docx.layout import profile


def _render(docx_path, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    exe = shutil.which("soffice")
    if exe is None:
        pytest.skip("LibreOffice not available")
    subprocess.run(
        [exe, "--headless", "--convert-to", "pdf", str(docx_path), "--outdir", str(outdir)],
        check=True, capture_output=True, timeout=180,
    )
    return outdir / (docx_path.stem + ".pdf")


def _facts(pdf_path):
    """Document-level facts.

    Body size is measured by character weight across ALL pages: a title page
    that holds only the heading would otherwise report the heading's size as
    the body size, which measures the wrong thing.
    """
    with pdfplumber.open(pdf_path) as pdf:
        sizes = {}
        left = None
        for pg in pdf.pages:
            for c in pg.chars:
                sizes[round(c["size"], 1)] = sizes.get(round(c["size"], 1), 0) + 1
            if pg.chars:
                pg_left = min(c["x0"] for c in pg.chars)
                left = pg_left if left is None else min(left, pg_left)
        first = pdf.pages[0]
        body = max(sizes, key=sizes.get) if sizes else 0
        return {
            "count": len(pdf.pages),
            "width": round(first.width),
            "height": round(first.height),
            "body_size": body,
            "left": round(left or 0, 1),
        }


def test_page_size_matches_the_source(numbered_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    src, got = _facts(numbered_pdf), _facts(_render(out, tmp_path / "r"))
    assert abs(got["width"] - src["width"]) <= 2
    assert abs(got["height"] - src["height"]) <= 2


def test_body_font_size_matches_the_source(numbered_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    src, got = _facts(numbered_pdf), _facts(_render(out, tmp_path / "r"))
    assert abs(got["body_size"] - src["body_size"]) <= 0.5


def test_left_margin_matches_the_source(numbered_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    src, got = _facts(numbered_pdf), _facts(_render(out, tmp_path / "r"))
    assert abs(got["left"] - src["left"]) <= 6


def test_profile_reads_the_documents_own_typography(numbered_pdf):
    p = profile(numbered_pdf)
    assert p.page_width == pytest.approx(595, abs=2)
    assert p.page_height == pytest.approx(842, abs=2)
    assert p.body_size == pytest.approx(10.0, abs=0.5)
    assert p.left_margin == pytest.approx(60, abs=3)


def test_profile_maps_subset_prefixed_fonts_to_families():
    from pdf2docx.layout import family_of

    assert family_of("CAAAAA+ArialMT") == "Arial"
    assert family_of("TimesNewRomanPS-BoldMT") == "Times New Roman"
    assert family_of("BAAAAA+DejaVuSansMono") == "DejaVu Sans Mono"
    assert family_of("Helvetica-Oblique") == "Arial"


@pytest.mark.parametrize("mode", ["semantic", "faithful"])
def test_faithful_mode_keeps_the_page_count(numbered_pdf, tmp_path, mode):
    out = tmp_path / f"{mode}.docx"
    convert(numbered_pdf, out, layout=mode)
    src, got = _facts(numbered_pdf), _facts(_render(out, tmp_path / "r"))
    if mode == "faithful":
        assert got["count"] == src["count"]
    else:
        assert got["count"] >= 1
