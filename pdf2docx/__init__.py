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
from .tables import page_tables as _page_tables
from .writer import write as _write

MODES = ("semantic", "faithful")


def convert(src, dst, layout: str = "semantic"):
    """Convert PDF `src` to DOCX `dst`, preserving structure and typography."""
    if layout not in MODES:
        raise ValueError(f"layout must be one of {MODES}, not {layout!r}")
    prof = _profile(src)
    tables = _page_tables(src)   # detection is the expensive step; reuse it
    boxes: dict[int, list] = {}
    for t in tables:
        boxes.setdefault(t.page, []).append(t.bbox)
    # Table text is emitted as a table; leaving it in the line stream would
    # also emit it as paragraphs.
    doc = _classify(_lines(src, exclude=boxes),
                    join=(layout == "semantic"), tables=tables)
    _write(doc, dst, prof=prof, layout=layout)
    return dst
