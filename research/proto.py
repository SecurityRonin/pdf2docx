"""Prototype: semantic PDF -> DOCX. Structure first, layout never.

Measures the core claim of the research: that heading levels and list nesting can be
recovered from type-size tiers + numbering prefixes, without emitting absolute positions.
"""
import re, sys, json, collections, statistics
import fitz
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

BULLET = "•▪◦‣·∙●■⁃-"
# numbering that is a list prefix: 1. 2) (3) a. b) i. iv) A.
LIST_PREFIX = re.compile(r"^(?:\(?(\d{1,2}|[a-zA-Z]|[ivxlcIVXLC]{1,5})[.)])\s+")
# numbering that is a SECTION number: 1 1.2 3.4.5 (dotted, may lack trailing dot)
SECT_PREFIX = re.compile(r"^(\d+(?:\.\d+)+|\d+\.?)\s+(?=\S)")
SENT_END = (".", ";", ",", "?")


def bold(spans):
    return any("bold" in (s["font"] or "").lower() or (s["flags"] & 2 ** 4) for s in spans)


def gather(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if not txt:
                continue
            sp = [s for s in l["spans"] if s["text"].strip()]
            if not sp:
                continue
            out.append(dict(
                text=txt, x0=min(s["bbox"][0] for s in sp), x1=max(s["bbox"][2] for s in sp),
                y0=min(s["bbox"][1] for s in sp), size=statistics.median(s["size"] for s in sp),
                bold=bold(sp), page=page.number,
            ))
    return out


def drop_furniture(lines, npages):
    """Kill running headers/footers: same slot on many pages, or page-number-only."""
    slots = collections.defaultdict(set)
    for l in lines:
        slots[(round(l["y0"] / 6), round(l["x0"] / 12))].add(l["page"])
    kill = {k for k, v in slots.items() if npages >= 3 and len(v) > max(2, npages * 0.5)}
    keep = []
    for l in lines:
        if (round(l["y0"] / 6), round(l["x0"] / 12)) in kill:
            continue
        if re.fullmatch(r"[-–—\s]*\d{1,3}[-–—\s]*", l["text"]):
            continue
        keep.append(l)
    return keep


def body_size(lines):
    w = collections.Counter()
    for l in lines:
        w[round(l["size"], 1)] += len(l["text"])
    return w.most_common(1)[0][0] if w else 11.0


def is_heading(l, body, nxt):
    t = l["text"]
    if len(t) > 160 or len(t.split()) > 18:
        return False
    if t.endswith(SENT_END):
        return False
    big = l["size"] >= body * 1.04
    sect = bool(SECT_PREFIX.match(t))
    if not (big or (l["bold"] and (sect or len(t.split()) <= 10))):
        return False
    # a heading is followed by a gap or a different size; a body line that merely starts bold is not
    return big or sect or (nxt is not None and (nxt["size"] < l["size"] or nxt["y0"] - l["y0"] > l["size"] * 1.7))


def level_of(l, size_rank, numbering_depth):
    if numbering_depth:
        return min(6, numbering_depth)
    return size_rank


def build(doc, lines):
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    body = body_size(lines)
    heads = [l for i, l in enumerate(lines) if is_heading(l, body, lines[i + 1] if i + 1 < len(lines) else None)]
    # size tiers -> rank, restricted to sizes big enough to be a title
    tiers = sorted({round(l["size"], 1) for l in heads}, reverse=True)
    stats = dict(body=body, tiers=tiers[:8], heads=len(heads), lines=len(lines))
    para, prev = [], None
    used_numbering = set()

    def flush():
        nonlocal para
        if para:
            txt = join_para(para)
            p = doc.add_paragraph(txt)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            para = []

    for i, l in enumerate(lines):
        t = l["text"]
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        depth = 0
        m = SECT_PREFIX.match(t)
        if l in heads:
            flush()
            nd = t[: m.end() - 1].count(".") + 1 if m else 0
            lvl = level_of(l, tiers.index(round(l["size"], 1)) + 1 if round(l["size"], 1) in tiers else 1, nd)
            p = doc.add_paragraph(t, style=f"Heading {min(6, max(1, lvl))}")
            prev = l
            continue
        # list item?
        prefix, kind = None, None
        if t[0] in BULLET:
            prefix, kind = t[0], "bullet"
        elif LIST_PREFIX.match(t) and not SECT_PREFIX.match(t):
            prefix, kind = LIST_PREFIX.match(t).group(0).strip(), "number"
        if kind:
            flush()
            rest = t[len(prefix):].strip() if kind == "bullet" else t[LIST_PREFIX.match(t).end():]
            style = "List Bullet" if kind == "bullet" else "List Number"
            p = doc.add_paragraph(rest)
            p.style = doc.styles[style]
            # nesting by left indent relative to body
            nest = max(0, min(4, int((l["x0"] - min(x["x0"] for x in lines)) / 18)))
            p.paragraph_format.left_indent = Pt(18 * (nest + 1))
            prev = l
            continue
        # body: join wrapped lines, de-hyphenate
        if prev is not None and para and abs(l["x0"] - para[0]["x0"]) < 3 and l["y0"] - prev["y0"] < l["size"] * 1.9:
            para.append(l)
        else:
            flush()
            para = [l]
        prev = l
    flush()
    return stats


def join_para(ls):
    s = ""
    for l in ls:
        t = l["text"]
        if not s:
            s = t
        elif s.endswith("-") and t[:1].islower():
            s = s[:-1] + t
        else:
            s += " " + t
    return s


def main(path, out):
    d = fitz.open(path)
    lines = []
    for p in d:
        lines += gather(p)
    lines = drop_furniture(lines, d.page_count)
    doc = Document()
    st = build(doc, lines)
    doc.save(out)
    st["pages"] = d.page_count
    st["out"] = out
    print(json.dumps(st, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
