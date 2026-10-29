"""Classify extracted lines into document structure.

The governing rule is that a heading is identified by what the document says
about itself — its own section numbering — and only then by typography. Size
alone invents headings in title pages and banners; a section number cannot be
faked by a font.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .extract import Line

# "1.", "2)", "1.2", "3.4.5" — a section number, with or without a trailing dot.
SECTION = re.compile(r"^(?P<num>\d+(?:\.\d+)*)\.?(?P<rest>\s+\S.*)$")
# terminal punctuation of a sentence, which a heading does not carry
TERMINAL = (".", ";", ",", ":", "?", "!")


@dataclass
class Block:
    kind: str          # "heading" | "body"
    text: str
    level: int = 0     # 1-based, only for headings
    size: float = 0.0
    bold: bool = False
    italic: bool = False


def body_size(lines: list[Line]) -> float:
    """The most-used size measured by characters, so one large title cannot win."""
    weight = Counter()
    for ln in lines:
        weight[ln.size] += len(ln.text)
    return weight.most_common(1)[0][0] if weight else 11.0


def section_depth(num: str) -> int:
    """'1' -> 1, '1.2' -> 2, '3.4.5' -> 3. An explicit depth outranks size."""
    return min(6, num.count(".") + 1)


def is_heading(ln: Line, body: float, nxt: Line | None) -> bool:
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
    # a short bold line is a heading only if a size change or a gap follows it
    return nxt is not None and (nxt.size < ln.size or nxt.top - ln.top > ln.size * 1.7)


def classify(lines: list[Line]) -> list[Block]:
    body = body_size(lines)
    blocks: list[Block] = []
    for i, ln in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if not is_heading(ln, body, nxt):
            blocks.append(Block("body", ln.text, 0, ln.size, ln.bold, ln.italic))
            continue
        m = SECTION.match(ln.text)
        if m:
            level = section_depth(m.group("num"))
            text = m.group("rest").strip()
        else:
            text = ln.text.strip()
            level = 1
        blocks.append(Block("heading", text, level, ln.size, ln.bold, ln.italic))
    return blocks
