"""Score a converted DOCX against free ground truth: the PDF's own numbered section titles.

Ground truth is only what the document states about itself (1.1 Title, 2.3.4 Title).
Precision = emitted headings that appear in GT (by text). Recall = GT titles emitted as a heading.
A heading emitted as plain body text counts as a miss, which is the defect this design targets.
"""
import sys, re, json
import fitz
from docx import Document

SECT = re.compile(r"^(\d+(?:\.\d+)+)\s+(\S.{0,120})$")


def truth(pdf):
    d = fitz.open(pdf)
    gt = {}
    for p in d:
        for b in p.get_text("dict")["blocks"]:
            if b["type"]:
                continue
            for l in b["lines"]:
                t = "".join(s["text"] for s in l["spans"]).strip()
                m = SECT.match(t)
                if m and len(t) < 140:
                    gt.setdefault(t, m.group(1))
    return gt


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def main(pdf, docx_path):
    gt = {norm(k): v for k, v in truth(pdf).items()}
    doc = Document(docx_path)
    got = {}
    for p in doc.paragraphs:
        if p.style.name.startswith("Heading"):
            got[norm(p.text)] = p.style.name
    tp = [g for g in got if g in gt]
    # recall: GT title present anywhere (as heading or as body), to separate "wrong style" from "lost"
    alltext = norm(" ".join(p.text for p in doc.paragraphs))
    present = [g for g in gt if g in alltext]
    print(json.dumps(dict(
        gt=len(gt), emitted_headings=len(got), tp=len(tp),
        precision=round(len(tp) / len(got), 3) if got else 0,
        recall_as_heading=round(len(tp) / len(gt), 3) if gt else 0,
        recall_text_present=round(len(present) / len(gt), 3) if gt else 0,
        level_match=sum(1 for g in tp if got[g].endswith(str(min(6, gt[g].count(".") + 1)))),
        sample_missed=[k for k in got if k not in gt][:6],
    ), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
