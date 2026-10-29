"""Justified body text must not be read as a list.

Found on a real court document: paragraphs are set justified, so the first line
of each paragraph starts further right than the continuation lines. Keying a
list on indent alone turned 118 lines of prose into bullet items.
"""
import pytest

from pdf2docx import convert
from pdf2docx.structure import classify
from pdf2docx.extract import Line


def _line(text, x0, x1, size=12.0, top=100.0):
    return Line(text=text, size=size, x0=x0, x1=x1, top=top, bold=False,
                italic=False, page=0, page_height=800.0)


def test_justified_prose_is_not_a_list():
    # Justified text: continuation lines start at varied x0 because Word distributes
    # inter-word space, and they still run to the right measure.
    lines = [
        _line("The claimant engaged a photography agency named Guangzhou Fu", 99, 500, top=100),
        _line("kesi Media Co., Ltd. and three of its affiliates to produce", 71, 500, top=114),
        _line("advertising material for the autumn campaign that appeared", 99, 500, top=128),
        _line("in three magazines.", 71, 500, top=142),
    ]
    doc = classify(lines)
    assert [b.kind for b in doc.blocks].count("list_item") == 0


def test_a_short_indented_line_is_still_a_list_item():
    lines = [
        _line("The following systems were reviewed during the engagement and each", 99, 500, top=100),
        _line("one was examined on site by two analysts over three days.", 99, 500, top=114),
        _line("Mail server", 130, 190, top=132),
        _line("File server", 130, 190, top=146),
    ]
    doc = classify(lines)
    assert [b.kind for b in doc.blocks].count("list_item") == 2
