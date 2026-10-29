"""Convert a PDF into a DOCX that carries real Word structure, not positioned text."""
from __future__ import annotations

from .extract import lines as _lines
from .structure import classify as _classify
from .writer import write as _write


def convert(src, dst):
    """Convert PDF `src` to DOCX `dst`, preserving headings, lists and footnotes."""
    _write(_classify(_lines(src)), dst)
    return dst
