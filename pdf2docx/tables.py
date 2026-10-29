"""Detect ruled tables and recover their grid, including merged cells.

A table flattened to paragraphs is the single largest remaining source of page
drift: a table occupying a third of a page becomes flowing text and the
document grows. Recovering the grid is what makes page-identical output
possible at all.

Geometry drives everything here. `page.find_tables()` gives cell bounding
boxes; column and row boundaries are the clustered edges of those boxes, so a
cell spanning two columns is recognised by its width rather than guessed from
its text.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field

import pdfplumber

EDGE_TOL = 3.0   # points within which two edges are the same grid line


def _cluster(values: list[float], tol: float = EDGE_TOL) -> list[float]:
    """Collapse near-identical coordinates into one grid line."""
    out: list[float] = []
    for v in sorted(values):
        if not out or v - out[-1] > tol:
            out.append(v)
        else:
            out[-1] = (out[-1] + v) / 2
    return out


@dataclass
class Cell:
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    text: str = ""


@dataclass
class Table:
    page: int
    top: float
    bbox: tuple
    nrows: int
    ncols: int
    col_widths: list[float] = field(default_factory=list)
    cells: list[Cell] = field(default_factory=list)
    header_row: bool = True


def _cell_text(page, bbox) -> str:
    try:
        t = page.within_bbox(bbox).extract_text() or ""
    except Exception:
        return ""
    return " ".join(t.split())


def _outermost(tables):
    """Drop tables nested inside another (a header block inside the real table)."""
    def contains(a, b):
        ax0, ay0, ax1, ay1 = a.bbox
        bx0, by0, bx1, by1 = b.bbox
        return ax0 - 1 <= bx0 and ay0 - 1 <= by0 and ax1 + 1 >= bx1 and ay1 + 1 >= by1

    keep = []
    for t in tables:
        if any(o is not t and contains(o, t) and o.bbox != t.bbox for o in tables):
            continue
        keep.append(t)
    return keep


def table_from_pdfplumber(page, raw, page_no: int) -> Table | None:
    boxes = [tuple(float(v) for v in b) for b in raw.cells]
    if len(boxes) < 2:
        return None

    col_edges = _cluster([b[0] for b in boxes] + [b[2] for b in boxes])
    row_edges = _cluster([b[1] for b in boxes] + [b[3] for b in boxes])
    if len(col_edges) < 2 or len(row_edges) < 2:
        return None
    ncols, nrows = len(col_edges) - 1, len(row_edges) - 1

    def span(edges, a, b):
        start = min(range(len(edges)), key=lambda i: abs(edges[i] - a))
        end = min(range(len(edges)), key=lambda i: abs(edges[i] - b))
        return start, max(1, end - start)

    cells: list[Cell] = []
    occupied: set[tuple[int, int]] = set()
    for b in boxes:
        c0, cspan = span(col_edges, b[0], b[2])
        r0, rspan = span(row_edges, b[1], b[3])
        if (r0, c0) in occupied:
            continue
        occupied.add((r0, c0))
        cells.append(Cell(r0, c0, rspan, cspan, _cell_text(page, b)))

    if not cells:
        return None
    widths = [round(col_edges[i + 1] - col_edges[i], 2) for i in range(ncols)]
    return Table(page_no, float(raw.bbox[1]), tuple(raw.bbox), nrows, ncols, widths, cells)


def page_tables(pdf_path) -> list[Table]:
    """Every outermost ruled table, in reading order."""
    out: list[Table] = []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages):
            try:
                raw = page.find_tables()
            except Exception:
                continue
            for t in _outermost(list(raw)):
                tbl = table_from_pdfplumber(page, t, pno)
                if tbl is not None:
                    out.append(tbl)
    return out


def table_bboxes(pdf_path) -> dict[int, list[tuple]]:
    """Table bounding boxes per page, so their text can be excluded from lines."""
    boxes: dict[int, list[tuple]] = collections.defaultdict(list)
    for t in page_tables(pdf_path):
        boxes[t.page].append(t.bbox)
    return dict(boxes)
