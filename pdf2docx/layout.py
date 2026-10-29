"""Read a PDF's page geometry and typography so the DOCX can reproduce it.

Layout and semantic structure conflict in exactly one place: whether text
reflows. Everything measured here — page size, margins, font, size, leading,
alignment — is typography, which can match while the text still reflows.
"""
from __future__ import annotations

import collections
import re
import statistics
from dataclasses import dataclass, field

import pdfplumber

# A PDF font name carries a 6-letter subset prefix ("CAAAAA+ArialMT") and a
# PostScript style suffix ("TimesNewRomanPS-BoldMT"). Neither belongs in a
# DOCX font name, and leaving them in guarantees a substitution.
_SUBSET = re.compile(r"^[A-Z]{6}\+")

# PostScript families to the names a word processor actually resolves. Several
# spellings map to one family because the metrics are the same.
_FAMILIES = {
    "arial": "Arial",
    "arialmt": "Arial",
    "helvetica": "Arial",
    "helveticaneue": "Helvetica Neue",
    "timesnewromanps": "Times New Roman",
    "timesnewroman": "Times New Roman",
    "times": "Times New Roman",
    "courier": "Courier New",
    "couriernewps": "Courier New",
    "dejavusans": "DejaVu Sans",
    "dejavusansmono": "DejaVu Sans Mono",
    "dejavuserif": "DejaVu Serif",
    "calibri": "Calibri",
    "cambria": "Cambria",
    "georgia": "Georgia",
}

_STYLE_SUFFIX = re.compile(
    r"[-,_]?(bold|italic|oblique|regular|medium|light|semibold|black|mt|ps)+$", re.I
)


def family_of(fontname: str) -> str:
    """'CAAAAA+ArialMT' -> 'Arial'; 'TimesNewRomanPS-BoldMT' -> 'Times New Roman'."""
    n = _SUBSET.sub("", fontname or "")
    key = n.split("-")[0].split(",")[0]
    base = _STYLE_SUFFIX.sub("", key).lower()
    if base in _FAMILIES:
        return _FAMILIES[base]
    # strip a trailing "mt"/"ps" that survived, then try again
    for suffix in ("mt", "ps"):
        if base.endswith(suffix) and base[: -len(suffix)] in _FAMILIES:
            return _FAMILIES[base[: -len(suffix)]]
    # unknown family: return the cleaned name rather than inventing one
    return key or "Arial"


@dataclass
class LayoutProfile:
    page_width: float
    page_height: float
    left_margin: float
    right_margin: float
    top_margin: float
    bottom_margin: float
    body_size: float
    font_family: str
    line_pitch: float          # baseline-to-baseline, body text only
    justified: bool
    page_count: int
    # per-page text spans, for faithful mode
    page_breaks: list = field(default_factory=list)

    @property
    def line_spacing(self) -> float:
        """Multiple line spacing, so the leading survives a font-size change."""
        return round(self.line_pitch / self.body_size, 3) if self.body_size else 1.15


def _modal(values) -> float:
    counts = collections.Counter(values)
    return counts.most_common(1)[0][0] if counts else 0.0


def profile(pdf_path) -> LayoutProfile:
    fonts: collections.Counter = collections.Counter()
    sizes: collections.Counter = collections.Counter()
    lefts, rights, tops, bottoms = [], [], [], []
    pitches: list[float] = []
    right_edges = 0
    total_lines = 0

    with pdfplumber.open(pdf_path) as pdf:
        first = pdf.pages[0]
        page_w, page_h = float(first.width), float(first.height)
        for pg in pdf.pages:
            chars = pg.chars
            if not chars:
                continue
            for c in chars:
                fonts[c["fontname"]] += len(c["text"])
                sizes[round(c["size"], 1)] += len(c["text"])
            lefts.append(min(c["x0"] for c in chars))
            rights.append(max(c["x1"] for c in chars))
            tops.append(min(c["top"] for c in chars))
            bottoms.append(max(c["bottom"] for c in chars))

    body_size = sizes.most_common(1)[0][0] if sizes else 11.0

    # Leading: measure gaps between consecutive body-sized lines only. Headings
    # and paragraph gaps inflate a naive median badly (a handbook read 34.8pt
    # for 10.5pt text because every title gap counted).
    body_rights: list[float] = []
    with pdfplumber.open(pdf_path) as pdf:
        body_tops: list[float] = []
        for pg in pdf.pages:
            for ln in pg.extract_text_lines(return_chars=True):
                ch = ln.get("chars") or []
                if not ch:
                    continue
                if abs(statistics.median(c["size"] for c in ch) - body_size) > 0.6:
                    continue
                body_tops.append(ln["top"])
                # The measure is where BODY text ends. A running rule, a table
                # border or a watermark that touches the page edge is not the
                # text column and must not define the margin.
                body_rights.append(max(c["x1"] for c in ch))
        for a, b in zip(body_tops, body_tops[1:]):
            gap = b - a
            # Only genuine line-to-line gaps. A larger gap is a paragraph break
            # or a heading, which is spacing between lines, not line spacing —
            # folding those in loosens every line in the document.
            if 0 < gap <= body_size * 1.6:
                pitches.append(gap)
        # Justification: many lines ending within a hair of the right edge.
        for pg in pdf.pages:
            text_right = max((c["x1"] for c in pg.chars), default=0)
            if not text_right:
                continue
            for ln in pg.extract_text_lines(return_chars=True):
                ch = ln.get("chars") or []
                if not ch:
                    continue
                total_lines += 1
                if text_right - max(c["x1"] for c in ch) < 2:
                    right_edges += 1

    # The MODE, not the median: the line pitch is the gap that repeats. A median
    # over a document whose paragraphs are separated by extra space drifts
    # upward and inflates every line.
    if pitches:
        rounded = collections.Counter(round(p, 1) for p in pitches)
        pitch = rounded.most_common(1)[0][0]
    else:
        pitch = body_size * 1.15
    justified = total_lines > 3 and right_edges / total_lines > 0.5

    # The dominant font of body-sized text is the body font.
    family = family_of(fonts.most_common(1)[0][0]) if fonts else "Arial"

    left = min(lefts) if lefts else 72.0
    top = min(tops) if tops else 72.0

    # Take a high percentile, not the maximum: one stray element (a rule, a
    # watermark, a wide table cell) that reaches the page edge otherwise reports
    # a 1pt margin and destroys the text column for every other page.
    def p95(values):
        if not values:
            return 0.0
        values = sorted(values)
        return values[min(len(values) - 1, int(len(values) * 0.95))]

    right_edge = p95(body_rights) if body_rights else p95(rights)
    bottom_edge = p95(bottoms)

    # A margin can only be read off an edge the content actually reaches.
    # Inferring it from the content box otherwise is self-defeating: a page whose
    # text fills only the top quarter yields a 600pt bottom margin, a near-zero
    # text area, and the document spills onto extra pages. Where the text does
    # not reach an edge, the opposite margin is the honest estimate.
    REACH = 0.70
    right = page_w - right_edge if right_edge >= page_w * REACH else left
    bottom = page_h - bottom_edge if bottom_edge >= page_h * REACH else top

    # A page margin below a quarter-inch is not a margin, it is a misread.
    FLOOR = 18.0
    return LayoutProfile(
        page_width=page_w,
        page_height=page_h,
        left_margin=max(FLOOR, left),
        right_margin=max(FLOOR, right),
        top_margin=max(FLOOR, top),
        bottom_margin=max(FLOOR, bottom),
        body_size=body_size,
        font_family=family,
        line_pitch=pitch,
        justified=justified,
        page_count=len(pdfplumber.open(pdf_path).pages),
    )
