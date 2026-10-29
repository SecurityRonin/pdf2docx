"""Read a PDF into ordered lines with the attributes structure depends on.

Two things are split out here because they are decided by glyph geometry, not by
text: a trailing superscript digit (a footnote mark) and whether a line sits in
the footnote zone at the foot of the page.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import pdfplumber

SUPERSCRIPT_RATIO = 0.8   # a mark is smaller than its own line's median size


@dataclass
class Line:
    text: str
    size: float
    x0: float
    top: float
    bold: bool
    italic: bool
    page: int
    page_height: float = 0.0
    marker: str = ""       # trailing footnote digit, removed from `text`
    in_note_zone: bool = False


def _is_bold(name: str) -> bool:
    n = (name or "").lower()
    return "bold" in n or "black" in n or "heavy" in n or "semibold" in n


def _is_italic(name: str) -> bool:
    n = (name or "").lower()
    return "italic" in n or "oblique" in n


def _split_marker(text: str, chars: list) -> tuple[str, str]:
    """Separate a trailing superscript digit run from the line's text."""
    if not chars or not text:
        return text, ""
    # Compare against the line's most common size, not its median: one small
    # mark on a 20-character line shifts the median, so a median test misses
    # exactly the case it is meant to catch.
    counts = {}
    for c in chars:
        counts[c["size"]] = counts.get(c["size"], 0) + 1
    common = max(counts, key=counts.get)
    small = [c for c in chars if c["size"] < common * SUPERSCRIPT_RATIO
             and (c.get("text") or "").strip().isdigit()]
    if not small:
        return text, ""
    tail = "".join((c.get("text") or "") for c in chars[-len(small):])
    if not tail.strip().isdigit():
        return text, ""
    marker = tail.strip()
    return text[: len(text) - len(tail)].rstrip(), marker


def lines(pdf_path, note_zone: float = 0.75) -> list[Line]:
    """Every text line in reading order (top-to-bottom, left-to-right)."""
    out: list[Line] = []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages):
            height = float(page.height)
            for ln in page.extract_text_lines(return_chars=True):
                chars = ln.get("chars") or []
                if not chars:
                    continue
                text = (ln.get("text") or "").strip()
                if not text:
                    continue
                median = statistics.median(c["size"] for c in chars)
                body_text, marker = _split_marker(text, chars)
                out.append(
                    Line(
                        text=body_text,
                        size=round(median, 1),
                        x0=min(c["x0"] for c in chars),
                        top=ln["top"],
                        bold=_is_bold(chars[0].get("fontname", "")),
                        italic=_is_italic(chars[0].get("fontname", "")),
                        page=pno,
                        page_height=height,
                        marker=marker,
                        in_note_zone=bool(height) and ln["top"] > height * note_zone,
                    )
                )
    return out
