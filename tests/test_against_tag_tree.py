"""Score heading detection against a document's OWN structure tree.

Most PDFs carry no tree, so this is skipped unless one is present. Where it is
present it is ground truth the converter did not write, which makes it the
strongest oracle available without hand-labelling.

Set PDF2DOCX_TAGGED_FIXTURE to a tagged PDF to enable it.
"""
import collections
import os

import pdfplumber
import pytest

from pdf2docx.extract import lines
from pdf2docx.structure import classify

FIXTURE = os.environ.get("PDF2DOCX_TAGGED_FIXTURE")

pytestmark = pytest.mark.skipif(not FIXTURE, reason="PDF2DOCX_TAGGED_FIXTURE not set")


def _truth(path):
    counts = collections.Counter()
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            groups = collections.defaultdict(list)
            for c in pg.chars:
                if c.get("mcid") is not None:
                    groups[c["mcid"]].append(c)
            for _mcid, cs in groups.items():
                tag = str(cs[0].get("tag") or "").strip("/")
                if tag in ("H1", "H2", "H3"):
                    counts[tag] += 1
    return counts


def _emitted(path):
    doc = classify(lines(path))
    return collections.Counter(f"H{b.level}" for b in doc.blocks if b.kind == "heading")


def test_heading_count_is_within_a_quarter_of_the_documents_own_tree():
    truth, got = _truth(FIXTURE), _emitted(FIXTURE)
    total_t, total_g = sum(truth.values()), sum(got.values())
    assert total_t, "fixture has no H* tags"
    assert total_g <= total_t * 1.25, f"emitted {total_g} headings, tree has {total_t}"


def test_headings_are_not_inflated_at_the_top_level():
    truth, got = _truth(FIXTURE), _emitted(FIXTURE)
    assert got["H1"] <= truth["H1"] * 1.25, f"H1 emitted {got['H1']}, tree has {truth['H1']}"
