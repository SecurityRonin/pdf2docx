"""Tag-aware path: read the PDF's own structure tree via pdfplumber MCIDs.

This is the high-fidelity branch of the design. It emits Heading 1..6 and real list
paragraphs, never absolute positioning. Verify it reproduces the tree exactly.
"""
import sys, json, collections
import pdfplumber
from docx import Document

HEAD = {"H1": 1, "H2": 2, "H3": 3, "H4": 4, "H5": 5, "H6": 6}
LISTY = ("List Paragraph", "LBody", "LI", "L")


def page_groups(pg):
    """MCID -> text, in reading order, using the tag carried on each char."""
    groups = collections.defaultdict(list)
    for c in pg.chars:
        if c.get("mcid") is None:
            continue
        groups[c["mcid"]].append(c)
    out = []
    for mcid, cs in groups.items():
        cs.sort(key=lambda c: (round(c["doctop"], 1), c["x0"]))
        txt = "".join(c["text"] for c in cs).strip()
        if txt:
            out.append((mcid, cs[0].get("tag"), min(c["x0"] for c in cs), txt))
    return out


def convert(src, dst):
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    seen = 0
    stats = collections.Counter()
    with pdfplumber.open(src) as pdf:
        for pg in pdf.pages:
            for mcid, tag, x0, txt in page_groups(pg):
                tag = str(tag or "Standard").strip("/")
                if tag in HEAD:
                    doc.add_paragraph(txt, style=f"Heading {HEAD[tag]}")
                    stats[f"heading_{HEAD[tag]}"] += 1
                elif tag in LISTY:
                    doc.add_paragraph(txt, style="List Bullet")
                    stats["list"] += 1
                else:
                    doc.add_paragraph(txt)
                    stats["para"] += 1
                seen += 1
    doc.save(dst)
    print(json.dumps(dict(groups=seen, **stats), ensure_ascii=False))


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
