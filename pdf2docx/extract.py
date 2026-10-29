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
    x1: float
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


def _modal_size(sizes: list[float]) -> float:
    counts = {}
    for s in sizes:
        k = round(s, 1)
        counts[k] = counts.get(k, 0) + 1
    return max(counts, key=counts.get) if counts else 0.0


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


def _inside(c, boxes) -> bool:
    cx = (c["x0"] + c["x1"]) / 2
    cy = (c["top"] + c["bottom"]) / 2
    for x0, y0, x1, y1 in boxes:
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return True
    return False


def lines(pdf_path, note_zone: float = 0.75, exclude=None) -> list[Line]:
    """Every text line in reading order (top-to-bottom, left-to-right).

    `exclude` maps page number to bounding boxes whose text belongs to a table;
    that text is emitted as a table instead, so keeping it here would duplicate
    it as flowing paragraphs.
    """
    with pdfplumber.open(pdf_path) as pdf:
        # Pass 1: gather every page's raw lines, and the document's body size.
        gathered: list[tuple[int, float, list]] = []
        weight: dict[float, int] = {}
        for pno, page in enumerate(pdf.pages):
            height = float(page.height)
            boxes = (exclude or {}).get(pno, [])
            source = page
            if boxes:
                # Filter the page's objects rather than joining the surviving
                # characters: a bare join loses every space pdfplumber derives
                # from glyph positions, turning "member of the" into
                # "memberofthe". filter() keeps the real layout of the text.
                def keep(obj, _b=boxes):
                    if obj.get("object_type") != "char":
                        return True
                    return not _inside(obj, _b)

                source = page.filter(keep)
            raw = [ln for ln in source.extract_text_lines(return_chars=True)
                   if ln.get("chars")]
            if raw:
                gathered.append((pno, height, raw))
            for ln in raw:
                text = (ln.get("text") or "").strip()
                if text:
                    size = round(statistics.median(c["size"] for c in ln["chars"]), 1)
                    weight[size] = weight.get(size, 0) + len(text)

    # Body size for the whole DOCUMENT: the LARGEST size with a substantial
    # share of the characters. Not the mode — a cover page's most common size is
    # its small print; and not the maximum — a title page would win. A size
    # below 20% of the text is a heading, a note or furniture, not the body.
    total = sum(weight.values()) if weight else 0
    doc_body = max((s for s, w in weight.items() if total and w >= total * 0.2),
                   default=max(weight, key=weight.get) if weight else 0.0)

    out: list[Line] = []
    for pno, height, raw in gathered:
        for ln in raw:
            chars = ln["chars"]
            text = (ln.get("text") or "").strip()
            if not text:
                continue
            median = statistics.median(c["size"] for c in chars)
            body_text, marker = _split_marker(text, chars)
            # Footnote text is smaller than body text. A dense page whose
            # paragraphs simply run to the bottom is not a footnote: treating
            # everything below a fixed fraction of the page as notes silently
            # discarded about a fifth of a two-page contract.
            small = bool(doc_body) and median < doc_body * 0.9
            out.append(
                Line(
                    text=body_text,
                    size=round(median, 1),
                    x0=min(c["x0"] for c in chars),
                    x1=max(c["x1"] for c in chars),
                    top=ln["top"],
                    bold=_is_bold(chars[0].get("fontname", "")),
                    italic=_is_italic(chars[0].get("fontname", "")),
                    page=pno,
                    page_height=height,
                    marker=marker,
                    in_note_zone=(bool(height) and ln["top"] > height * note_zone
                                  and small),
                )
            )
    return out
