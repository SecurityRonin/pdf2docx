"""Letter-in-parentheses sub-items are list entries, not prose.

Found in a real expert report whose analysis stages are numbered "(a) ... (e)"
across several paragraphs each. Only the first line of each carries the label.
"""
from pdf2docx.structure import classify
from pdf2docx.extract import Line


def _line(text, x0, x1, size=12.0, top=100.0, bold=False):
    return Line(text=text, size=size, x0=x0, x1=x1, top=top, bold=bold,
                italic=False, page=0, page_height=800.0)


def _paragraph(*texts, x0=99, x1=500, top=100):
    return [_line(t, x0, x1, top=top + i * 14) for i, t in enumerate(texts)]


def test_lettered_items_are_lists():
    lines = (
        _paragraph(
            "6. In my experience, the typical lifecycle of a document processing",
            "environment involves the following stages:",
        )
        + _paragraph("(a) Ingestion. Source documents are collected from the client and", top=160)
        + _paragraph("(b) Processing and review. The ingested documents are placed in a", top=200)
        + _paragraph("(c) Production set creation. Documents approved for production are", top=240)
    )
    doc = classify(lines)
    items = [b for b in doc.blocks if b.kind == "list_item"]
    assert len(items) >= 3
    assert items[0].text.startswith("Ingestion.")


def test_a_parenthetical_reference_mid_text_is_not_a_list_item():
    lines = _paragraph(
        "The claimant relies on the witness statement (a) and the exhibits.",
        "Each of these was served in the usual way under the rules.",
    )
    doc = classify(lines)
    assert [b.kind for b in doc.blocks].count("list_item") == 0
