"""Convert a PDF into a DOCX that carries real Word structure, not positioned text.

Two layout modes, because layout and structure conflict in exactly one place —
whether the text reflows:

  semantic  (default) typography matches the source; Word reflows the text
  faithful            typography matches AND line and page breaks are pinned
"""
from __future__ import annotations

from .extract import lines as _lines
from .layout import profile as _profile
from .structure import classify as _classify
from .writer import write as _write

MODES = ("semantic", "faithful")


def convert(src, dst, layout: str = "semantic"):
    """Convert PDF `src` to DOCX `dst`, preserving structure and typography."""
    if layout not in MODES:
        raise ValueError(f"layout must be one of {MODES}, not {layout!r}")
    prof = _profile(src)
    doc = _classify(_lines(src), join=(layout == "semantic"))
    _write(doc, dst, prof=prof, layout=layout)
    return dst
