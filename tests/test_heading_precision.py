"""A numbered paragraph at body size is not a heading.

Measured on a real handbook: it produced 36 Heading 1s where its own tree
carried 13, because any line beginning "3." was promoted. A heading is short;
a numbered paragraph runs to the right measure like the prose around it.
"""
from pdf2docx.structure import classify
from pdf2docx.extract import Line


def _line(text, x0, x1, size=10.5, top=100.0, bold=False):
    return Line(text=text, size=size, x0=x0, x1=x1, top=top, bold=bold,
                italic=False, page=0, page_height=800.0)


def test_numbered_paragraph_at_body_size_is_not_a_heading():
    lines = [
        _line("3. The platform was configured to retain audit entries for the period", 99, 500, top=100),
        _line("of ninety days, after which entries were rotated to cold storage.", 99, 470, top=114),
    ]
    doc = classify(lines)
    assert [b.kind for b in doc.blocks].count("heading") == 0


def test_bold_text_at_body_size_is_not_a_heading():
    """Bold emphasis inside a body-sized line does not make a heading.

    Measured on a real handbook: eleven module titles at body size were emitted
    as Heading 1 because they were bold and short, giving 36 H1s where the
    document's own tree carried 13.
    """
    lines = [
        _line("Module 01 — LLM Fundamentals & Architecture", 99, 300, size=10.5, top=100, bold=True),
        _line("This module introduces the architecture of large language models", 99, 500, size=10.5, top=114),
        _line("and the serving stack that surrounds them in production.", 99, 480, size=10.5, top=128),
    ]
    doc = classify(lines)
    assert [b.kind for b in doc.blocks].count("heading") == 0


def test_short_numbered_title_is_still_a_heading():
    lines = [
        _line("3. Findings", 99, 180, size=18.0, top=100, bold=True),
        _line("The review recorded three findings across the estate, each of which", 99, 500, top=130),
    ]
    doc = classify(lines)
    heads = [b for b in doc.blocks if b.kind == "heading"]
    assert len(heads) == 1
    assert heads[0].level == 1


def test_a_larger_heading_may_still_be_long():
    """Size is decisive on its own: a big line is a title however wide it sets."""
    lines = [
        _line("Certified LLM Security Professional — Official Study Guide", 99, 500, size=18.0, top=100, bold=True),
        _line("The programme covers ten domains of practice in depth over a year.", 99, 500, top=140),
    ]
    doc = classify(lines)
    assert [b.kind for b in doc.blocks].count("heading") == 1
