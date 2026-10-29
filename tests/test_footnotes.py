"""A footnote must be a real Word footnote: a reference run in the body, and its
text in footnotes.xml — not the note appended as prose at the end.
"""
import pathlib
import zipfile

import docx

from pdf2docx import convert

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def test_footnote_text_moves_into_footnotes_part(footnote_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(footnote_pdf, out)
    with zipfile.ZipFile(out) as z:
        assert "word/footnotes.xml" in z.namelist()
        notes = z.read("word/footnotes.xml").decode("utf8")
    assert "Statement of A. Example" in notes


def test_body_carries_a_footnote_reference(footnote_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(footnote_pdf, out)
    with zipfile.ZipFile(out) as z:
        body = z.read("word/document.xml").decode("utf8")
    assert "footnoteReference" in body


def test_note_text_is_not_left_in_the_body(footnote_pdf, tmp_path):
    out = tmp_path / "out.docx"
    convert(footnote_pdf, out)
    d = docx.Document(str(out))
    body_text = " ".join(p.text for p in d.paragraphs)
    assert "Statement of A. Example" not in body_text


def test_the_note_marker_is_not_left_in_body_text(footnote_pdf, tmp_path):
    """The superscript '1' must become a reference, not literal characters."""
    out = tmp_path / "out.docx"
    convert(footnote_pdf, out)
    d = docx.Document(str(out))
    body_text = " ".join(p.text for p in d.paragraphs)
    assert body_text.rstrip().endswith("12 March.")


def test_footnotes_work_without_the_house_template(footnote_pdf, tmp_path, monkeypatch):
    """The converter must not depend on a template on one machine.

    The house template lives outside this repo; CI has never seen it. Passing a
    path that does not exist forces the base-document path, which is the one a
    user of this tool actually gets. That path crashed with an ImportError and,
    before that, would have silently dropped the footnote styles.
    """
    monkeypatch.setenv("PDF2DOCX_TEMPLATE", str(tmp_path / "does-not-exist.docx"))
    out = tmp_path / "out.docx"
    convert(footnote_pdf, out)

    with zipfile.ZipFile(out) as z:
        assert "word/footnotes.xml" in z.namelist()
        notes = z.read("word/footnotes.xml").decode("utf8")
        body = z.read("word/document.xml").decode("utf8")
        styles = z.read("word/styles.xml").decode("utf8")
    assert "A. Example" in notes
    assert "footnoteReference" in body
    assert "FootnoteText" in styles
