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
# "1." "a)" "(3)" "(b)" — a list label, with or without a closing bracket.
LIST_NUMBER = re.compile(r"^(?:\(?(\d{1,2}|[a-zA-Z]{1,2})[.)])\s+")


@dataclass
class Block:
    kind: str          # "heading" | "body" | "list_item"
    text: str
    level: int = 0     # 1-based, headings only
    size: float = 0.0
    bold: bool = False
    italic: bool = False
    marker: str = ""   # footnote mark that follows this block's text
    page: int = 0
    page_break_before: bool = False
    top: float = 0.0
    table: object = None   # set when kind == "table"


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
    m = SECTION.match(ln.text)
    numbered = bool(m) and (bigger or (ln.bold and _is_short_title(ln, m)))
    if not (bigger or numbered):
        return False
    return True


def _is_short_title(ln: Line, m) -> bool:
    """A numbered title carries its section number and does not run on as prose."""
    rest = m.group("rest").strip()
    return len(rest) <= 90 and len(rest.split()) <= 12


def list_body(text: str) -> str | None:
    """The item text if `text` reads as a list entry, else None."""
    t = text.strip()
    if t[:1] and t[0] in BULLETS:
        return t[1:].strip()
    m = LIST_NUMBER.match(t)
    if m:
        return t[m.end():].strip()
    return None


LETTERED_SECTION = re.compile(r"^[A-Z][.)]\s+\S")


def _is_lettered_section(ln: Line) -> bool:
    """'H. REDACTIONS APPLIED FOR' — a lettered heading, not a bullet."""
    t = ln.text.strip()
    if not LETTERED_SECTION.match(t) or len(t) > 90:
        return False
    body = t[2:].strip()
    letters = [c for c in body if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _lettered_label(text: str) -> bool:
    """True for "(a) ..." / "a) ..." — a sub-item label, which is unambiguous.

    Bare "1. Scope" is left alone: in reports that is the section numbering, and
    reading it as a list would turn every section into a bullet.
    """
    t = text.strip()
    m = LIST_NUMBER.match(t)
    if not m:
        return False
    label = m.group(1)
    return not label.isdigit()


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


def classify(lines: list[Line], join: bool = True, tables=None) -> Doc:
    """Classify lines into blocks.

    `join=True` merges wrapped lines into paragraphs so the text reflows in
    Word (semantic mode). `join=False` keeps one block per visual line, which
    is what faithful mode needs to pin the layout.
    """
    body = body_size(lines)
    notes = _collect_notes(lines)
    lists_ok = _intro_marks_lists(lines)
    margin = _margin(lines)
    right = _right_edge(lines)
    doc = Doc(notes=notes)
    content = [ln for ln in lines if not ln.in_note_zone
               and not re.fullmatch(r"[-–—_ ]{4,}", ln.text.strip())]

    seen_numbered = False
    prev_page = None
    for i, ln in enumerate(content):
        nxt = content[i + 1] if i + 1 < len(content) else None
        marker = ln.marker if ln.marker in notes else ""
        new_page = prev_page is not None and ln.page != prev_page
        prev_page = ln.page

        if is_heading(ln, body, nxt):
            m = SECTION.match(ln.text)
            if m:
                seen_numbered = True
                level, text = section_depth(m.group("num")), m.group("rest").strip()
            else:
                text = ln.text.strip()
                # An unnumbered heading before the first numbered section is the
                # document's title. Giving it Heading 1 would make Word number it
                # "1" and push every real section down by one.
                level = 0 if not seen_numbered and not doc.blocks else 1
            doc.blocks.append(Block("heading", text, level, ln.size, ln.bold, ln.italic,
                                    marker, ln.page, new_page, ln.top))
            continue
        # A lettered ALL-CAPS line ("H. REDACTIONS APPLIED FOR") is a section
        # heading in a court document, not a list item. The letter is section
        # numbering Word cannot generate, so it stays in the heading text.
        if _is_lettered_section(ln):
            doc.blocks.append(Block("heading", ln.text.strip(), 1, ln.size, ln.bold, ln.italic,
                                    marker, ln.page, new_page, ln.top))
            continue

        item = list_body(ln.text)
        bulleted = bool(ln.text.strip()[:1]) and ln.text.strip()[0] in BULLETS
        numbered = item is not None and not bulleted and (lists_ok or _lettered_label(ln.text))
        # An indented line below the body margin is a list item in its own right:
        # Word's own list styles indent the item and leave the glyph to numbering.
        # A lone indented line is not a list: a list is a run. Requiring a
        # neighbour keeps an indented heading ("Appendix 1 ...") out of the
        # bullets, where it would lose its identity as a heading.
        neighbour_indented = (
            (nxt is not None and _is_indented(nxt, margin, right))
            or (i > 0 and _is_indented(content[i - 1], margin, right))
        )
        indented = (_is_indented(ln, margin, right) and neighbour_indented
                    and not is_heading(ln, body, nxt))
        if indented:
            doc.blocks.append(Block("list_item", (item if item is not None else ln.text.strip()),
                                    1, ln.size, ln.bold, ln.italic, marker, ln.page, new_page,
                                    ln.top))
            continue
        if item is not None and (bulleted or numbered):
            doc.blocks.append(Block("list_item", item, 1, ln.size, ln.bold, ln.italic,
                                    marker, ln.page, new_page, ln.top))
            continue
        doc.blocks.append(Block("body", ln.text, 0, ln.size, ln.bold, ln.italic,
                                marker, ln.page, new_page, ln.top))

    if join:
        doc.blocks = _join_paragraphs(doc.blocks, right, margin)

    if tables:
        doc.blocks = _interleave_tables(doc.blocks, list(tables))
    return doc


def _interleave_tables(blocks: list[Block], tables: list) -> list[Block]:
    """Put each table where its position falls in the text flow.

    Ordering by (page, top) rather than appending at the end is what keeps the
    reading order right: a table mid-document must not jump to the end.
    """
    out: list[Block] = []
    pending = sorted(tables, key=lambda t: (t.page, t.top))
    for b in blocks:
        while pending and (pending[0].page, pending[0].top) <= (b.page, b.top):
            t = pending.pop(0)
            out.append(Block("table", "", 0, 0, False, False, "", t.page, False, t.top, t))
        out.append(b)
    for t in pending:
        out.append(Block("table", "", 0, 0, False, False, "", t.page, False, t.top, t))
    return out


def _continued(prev: Block, cur: Block, right: float, margin: float) -> bool:
    """Does `cur` continue the paragraph started by `prev`?

    A wrapped line differs from a new paragraph in one reliable way: the line
    above it ran on to the right measure. A paragraph's last line is short.
    """
    if prev.kind != "body" or cur.kind != "body":
        return False
    if prev.page != cur.page:
        return False
    if abs((prev.size or 0) - (cur.size or 0)) > 0.6:
        return False
    if right and margin and (right - margin) > 0:
        measure = right - margin
        filled = (len(prev.text) * (prev.size or 10) * 0.5)
        if filled < measure * 0.75:
            return False
    # a sentence that ended is a paragraph that ended
    return not prev.text.rstrip().endswith((".", "!", "?", ":", ";"))


def _join_paragraphs(blocks: list[Block], right: float, margin: float) -> list[Block]:
    """Merge wrapped body lines so Word reflows the text as paragraphs."""
    out: list[Block] = []
    for b in blocks:
        if out and _continued(out[-1], b, right, margin):
            prev = out[-1]
            joined = prev.text.rstrip()
            nxt = b.text.lstrip()
            if joined.endswith("-") and nxt[:1].islower():
                prev.text = joined[:-1] + nxt      # de-hyphenate a wrapped word
            else:
                prev.text = joined + " " + nxt
            if b.marker:
                prev.marker = b.marker
        else:
            out.append(b)
    return out
