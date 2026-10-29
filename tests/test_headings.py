"""Headings must be real Word heading styles, with levels recovered from the
document's own numbering, and nothing else may be styled as a heading.

These are the properties a reader's Word relies on: the navigation pane, a
generated table of contents, and any tool that walks the outline.
"""
import pathlib
import zipfile

import docx
import pytest

from pdf2docx import convert

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _headings(path):
    d = docx.Document(str(path))
    return [(p.style.name, p.text) for p in d.paragraphs if p.style.name.startswith("Heading")]


def test_numbered_sections_become_heading_styles(numbered_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    heads = _headings(out)
    texts = [t for _, t in heads]
    # RED: the converter does not exist yet.
    assert "Scope of the Review" in texts
    assert "Findings" in texts


def test_heading_level_follows_the_section_number(numbered_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    by_text = {t: s for s, t in _headings(out)}
    assert by_text["Scope of the Review"] == "Heading 1"      # "1."
    assert by_text["Systems Covered"] == "Heading 2"          # "1.1"


def test_section_digits_are_not_baked_into_heading_text(numbered_pdf, tmp_path):
    """Word supplies the numbers; a literal '1.1 ' in the text would double them."""
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    for _, text in _headings(out):
        assert not text.startswith("1."), text
        assert not text.startswith("1.1"), text


def test_body_text_is_not_styled_as_a_heading(numbered_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    texts = [t for _, t in _headings(out)]
    assert not any(t.startswith("The review covered") for t in texts)
    assert not any(t in ("Mail server", "File server") for t in texts)


def test_headings_carry_outline_level_so_navigation_works(numbered_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(numbered_pdf, out)
    with zipfile.ZipFile(out) as z:
        xml = z.read("word/document.xml").decode("utf8")
    assert "Heading1" in xml or "Heading 1" in xml
