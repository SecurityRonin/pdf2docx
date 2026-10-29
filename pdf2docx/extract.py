"""Read a PDF into ordered lines with the attributes structure depends on."""
from __future__ import annotations

import statistics
from dataclasses import dataclass

import pdfplumber


@dataclass
class Line:
    text: str
    size: float
    x0: float
    top: float
    bold: bool
    italic: bool
    page: int


def _is_bold(name: str) -> bool:
    n = (name or "").lower()
    return "bold" in n or "black" in n or "heavy" in n or "semibold" in n


def _is_italic(name: str) -> bool:
    n = (name or "").lower()
    return "italic" in n or "oblique" in n


def lines(pdf_path) -> list[Line]:
    """Every text line in reading order (top-to-bottom, left-to-right)."""
    out: list[Line] = []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages):
            for ln in page.extract_text_lines(return_chars=True):
                chars = ln.get("chars") or []
                if not chars:
                    continue
                text = (ln.get("text") or "").strip()
                if not text:
                    continue
                size = statistics.median(c["size"] for c in chars)
                out.append(
                    Line(
                        text=text,
                        size=round(size, 1),
                        x0=min(c["x0"] for c in chars),
                        top=ln["top"],
                        bold=_is_bold(chars[0].get("fontname", "")),
                        italic=_is_italic(chars[0].get("fontname", "")),
                        page=pno,
                    )
                )
    return out
