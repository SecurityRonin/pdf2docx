"""Classify extracted lines into document structure.

The governing rule is that a heading is identified by what the document says
about itself — its own section numbering — and only then by typography. Size
alone invents headings in title pages and banners; a section number cannot be
faked by a font.

Footnotes are decided by geometry: a trailing superscript mark in the body, and
its text in the note zone at the foot of the page.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .extract import Line

SECTION = re.compile(r"^(?P<num>\d+(?:\.\d+)*)\.?(?P<rest>\s+\S.*)$")
TERMINAL = (".", ";", ",", ":", "?", "!")
BULLETS = "•▪◦‣·∙●■⁃–—"
LIST_NUMBER = re.compile(r"^(?:\(?(\d{1,2}|[a-zA-Z])[.)])\s+")


@dataclass
class Block:
    kind: str          # "heading" | "body" | "list_item"
    text: str
    level: int = 0     # 1-based, headings only
    size: float = 0.0
    bold: bool = False
    italic: bool = False
    marker: str = ""   # footnote mark that follows this block's text


@dataclass
class Doc:
    blocks: list[Block] = field(default_factory=list)
    notes: dict[str, str] = field(default_factory=dict)   # marker -> note text


def body_size(lines: list[Line]) -> float:
    weight = Counter()
    for ln in lines:
        if not ln.in_note_zone:
            weight[ln.size] += len(ln.text)
    return weight.most_common(1)[0][0] if weight else 11.0


def section_depth(num: str) -> int:
    return min(6, num.count(".") + 1)


def is_heading(ln: Line, body: float, nxt: Line | None) -> bool:
    if ln.in_note_zone:
        return False
    if len(ln.text) > 160 or len(ln.text.split()) > 18:
        return False
    if ln.text.endswith(TERMINAL):
        return False
    bigger = ln.size >= body * 1.04
    numbered = bool(SECTION.match(ln.text))
    if not (bigger or (ln.bold and (numbered or len(ln.text.split()) <= 10))):
        return False
    if bigger or numbered:
        return True
    return nxt is not None and (nxt.size < ln.size or nxt.top - ln.top > ln.size * 1.7)


def list_body(text: str) -> str | None:
    """The item text if `text` reads as a list entry, else None."""
    t = text.strip()
    if t[:1] and t[0] in BULLETS:
        return t[1:].strip()
    m = LIST_NUMBER.match(t)
    if m:
        return t[m.end():].strip()
    return None


def _margin(lines: list[Line]) -> float:
    """Left edge of unindented body text.

    Measured by characters, not by line count: a page of short list items
    outnumbers its prose lines, so a modal x0 reports the list indent as the
    margin and then every list item looks flush.
    """
    weight = Counter()
    for ln in lines:
        if not ln.in_note_zone:
            weight[round(ln.x0)] += len(ln.text)
    return float(weight.most_common(1)[0][0]) if weight else 0.0


def _intro_marks_lists(lines: list[Line]) -> bool:
    """Only treat numbered lines as lists when the document uses bullets too.

    Section numbering ("1. Scope") is the dominant numbered-line form in reports;
    treating it as a list would turn every section into a list item.
    """
    return any(ln.text.strip()[:1] in BULLETS for ln in lines if ln.text.strip())


INDENT_PT = 8.0   # a list item is set in from the body margin by at least this
SHORT_LINE = 0.62  # ...and does not run on to the right margin like prose


def _right_edge(lines: list[Line]) -> float:
    """Typical right edge of a full line, i.e. the measure the text is set to."""
    edges = [ln.x1 for ln in lines if not ln.in_note_zone and ln.x1]
    if not edges:
        return 0.0
    edges.sort()
    return edges[int(len(edges) * 0.9)]


def _is_indented(ln: Line, margin: float, right: float) -> bool:
    """Indented, and shorter than a full measure.

    Indent alone is not enough: justified body text starts its continuation
    lines at the margin while the first line of each paragraph varies, so an
    offset from the modal x0 is mostly inter-word spacing, not a list.
    """
    if ln.x1 and right:
        width = ln.x1 - margin
        if width >= (right - margin) * SHORT_LINE:
            return False
    return ln.x0 - margin >= INDENT_PT


def _collect_notes(lines: list[Line]) -> dict[str, str]:
    notes: dict[str, str] = {}
    for ln in lines:
        if not ln.in_note_zone:
            continue
        t = ln.text.strip()
        m = re.match(r"^(\d{1,3})\s+(.+)$", t)
        if m and m.group(1) not in notes:
            notes[m.group(1)] = m.group(2).strip()
    return notes


def classify(lines: list[Line]) -> Doc:
    body = body_size(lines)
    notes = _collect_notes(lines)
    lists_ok = _intro_marks_lists(lines)
    margin = _margin(lines)
    right = _right_edge(lines)
    doc = Doc(notes=notes)
    content = [ln for ln in lines if not ln.in_note_zone
               and not re.fullmatch(r"[-–—_ ]{4,}", ln.text.strip())]

    for i, ln in enumerate(content):
        nxt = content[i + 1] if i + 1 < len(content) else None
        marker = ln.marker if ln.marker in notes else ""
        if is_heading(ln, body, nxt):
            m = SECTION.match(ln.text)
            if m:
                level, text = section_depth(m.group("num")), m.group("rest").strip()
            else:
                level, text = 1, ln.text.strip()
            doc.blocks.append(Block("heading", text, level, ln.size, ln.bold, ln.italic, marker))
            continue
        item = list_body(ln.text)
        bulleted = bool(ln.text.strip()[:1]) and ln.text.strip()[0] in BULLETS
        numbered = item is not None and not bulleted and lists_ok
        # An indented line below the body margin is a list item in its own right:
        # Word's own list styles indent the item and leave the glyph to numbering.
        indented = _is_indented(ln, margin, right) and not is_heading(ln, body, nxt)
        if indented:
            doc.blocks.append(Block("list_item", (item if item is not None else ln.text.strip()),
                                    1, ln.size, ln.bold, ln.italic, marker))
            continue
        if item is not None and (bulleted or numbered):
            doc.blocks.append(Block("list_item", item, 1, ln.size, ln.bold, ln.italic, marker))
            continue
        doc.blocks.append(Block("body", ln.text, 0, ln.size, ln.bold, ln.italic, marker))
    return doc
