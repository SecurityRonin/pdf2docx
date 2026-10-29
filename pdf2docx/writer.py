"""Build the DOCX from classified blocks.

Structure comes from styles; fidelity comes from the style definitions plus a
run-level size where the source differs from the template. A heading is never a
bold paragraph, because then Word cannot see it.

Footnotes are written as OOXML by hand: python-docx has no footnote API, and a
note appended as prose is not a footnote to any tool that reads the document.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from .structure import Block, Doc

DEFAULT_TEMPLATE = Path("/Users/4n6h4x0r/src/expert-report-kit/templates/house-report.docx")
# The house font (Equity B) may be absent where the file is opened, and Word's
# substitution for it mangles glyphs. Fidelity to the source wins: body text is
# set in a font that actually resolves, unless a template asks for another.
FALLBACK_FONT = "Calibri"

REL_FOOTNOTES = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
CT_FOOTNOTES = ("application/vnd.openxmlformats-officedocument."
                "wordprocessingml.footnotes+xml")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def template_path() -> Path:
    env = os.environ.get("PDF2DOCX_TEMPLATE")
    return Path(env) if env else DEFAULT_TEMPLATE


def _set_body_font(document, name: str = FALLBACK_FONT) -> None:
    """Point Normal (and the theme's minor latin) at a font that resolves."""
    normal = document.styles["Normal"]
    normal.font.name = name
    rpr = normal.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), name)
    # A theme font wins over a style font; strip the references so the name holds.
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if fonts.get(qn(attr)) is not None:
            del fonts.attrib[qn(attr)]


def _clear(document) -> None:
    """Keep the template's styles and numbering; drop its content and furniture.

    The template is a style library, not stationery: its cover page, running
    headers and footers would add material the source PDF never contained, so a
    converted page would not look like the document it came from.
    """
    body = document.element.body
    for child in list(body):
        if child.tag == qn("w:sectPr"):
            continue
        body.remove(child)
    for sect in body.iter(qn("w:sectPr")):
        for tag in ("w:headerReference", "w:footerReference", "w:titlePg"):
            for el in list(sect.iter(qn(tag))):
                el.getparent().remove(el)

    # The template's Heading 1 starts a new page (report chapters do). A
    # conversion is one continuous document, so that behaviour would split the
    # output into extra pages the source never had.
    styles = document.styles.element
    for style in styles.iter(qn("w:style")):
        ppr = style.find(qn("w:pPr"))
        if ppr is None:
            continue
        brk = ppr.find(qn("w:pageBreakBefore"))
        if brk is not None:
            ppr.remove(brk)


def _para(text: str, style: str | None = None, size: float | None = None,
          bold: bool = False, italic: bool = False):
    p = docx.text.paragraph.Paragraph(_empty_p(), None)
    return p


def _empty_p():
    return OxmlElement("w:p")


BULLET_NUM_ID = "12"   # the house template's bullet abstractNum (w:num w:numId=12)
LETTERED_HEADING = re.compile(r"^[A-Z][.)]\s+\S")


def _suppress_numbering(p) -> None:
    """numId 0 is Word's way of saying 'this paragraph is not numbered'."""
    ppr = p._p.get_or_add_pPr()
    numpr = OxmlElement("w:numPr")
    nid = OxmlElement("w:numId")
    nid.set(qn("w:val"), "0")
    numpr.append(nid)
    # numPr must precede rPr/prChange in pPr; append before any existing rPr.
    rpr = ppr.find(qn("w:rPr"))
    if rpr is not None:
        rpr.addprevious(numpr)
    else:
        ppr.append(numpr)


def _apply_numbering(p, num_id: str, level: int = 0) -> None:
    """A List style alone prints no glyph; the paragraph needs its own w:numPr."""
    ppr = p._p.get_or_add_pPr()
    numpr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), str(level))
    nid = OxmlElement("w:numId")
    nid.set(qn("w:val"), num_id)
    numpr.append(ilvl)
    numpr.append(nid)
    ppr.append(numpr)


def _add(document, text, style, b: Block):
    p = document.add_paragraph(text, style=style) if style else document.add_paragraph(text)
    if b.bold and p.runs:
        p.runs[0].bold = True
    if b.italic and p.runs:
        p.runs[0].italic = True
    if b.size:
        for r in p.runs:
            r.font.size = Pt(b.size)
    return p


def _ensure_footnotes_part(document):
    """Create word/footnotes.xml and register it, if the template lacks one."""
    try:
        return document.part.part_related_by(REL_FOOTNOTES)
    except KeyError:
        pass
    from docx.opc.package import Part
    from docx.opc.packuri import PackURI
    xml = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:footnotes xmlns:w="{W_NS}">'
        f'<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0" '
        f'w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:separator/></w:r></w:p></w:footnote>'
        f'<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:spacing '
        f'w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:continuationSeparator/>'
        f'</w:r></w:p></w:footnote></w:footnotes>'
    ).encode("utf8")
    part = Part(PackURI("/word/footnotes.xml"), "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml", xml, document.part.package)
    document.part.relate_to(part, REL_FOOTNOTES)
    return part


def _next_note_id(part) -> int:
    from lxml import etree
    root = etree.fromstring(part.blob)
    ids = [int(e.get(qn("w:id"))) for e in root.iter(qn("w:footnote"))]
    return max(ids + [0]) + 1


def _add_note(part, text: str) -> int:
    from lxml import etree
    root = etree.fromstring(part.blob)
    nid = _next_note_id(part)
    note = etree.SubElement(root, qn("w:footnote"))
    note.set(qn("w:id"), str(nid))
    p = etree.SubElement(note, qn("w:p"))
    ppr = etree.SubElement(p, qn("w:pPr"))
    ps = etree.SubElement(ppr, qn("w:pStyle"))
    ps.set(qn("w:val"), "FootnoteText")
    r1 = etree.SubElement(p, qn("w:r"))
    rpr = etree.SubElement(r1, qn("w:rPr"))
    rs = etree.SubElement(rpr, qn("w:rStyle"))
    rs.set(qn("w:val"), "FootnoteReference")
    etree.SubElement(r1, qn("w:footnoteRef"))
    r2 = etree.SubElement(p, qn("w:r"))
    t = etree.SubElement(r2, qn("w:t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = " " + text
    part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return nid


TWIPS = 20  # 1 point = 20 twentieths of a point


def _el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(k), str(v))
    return e


def _cell_paragraphs(tc, text: str):
    """One w:p per line: a cell's text must live in paragraphs, never bare."""
    for line in (text.split("\n") if text else [""]):
        p = _el("w:p")
        r = _el("w:r")
        t = _el("w:t")
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = line
        r.append(t)
        p.append(r)
        tc.append(p)


def _add_table(document, tbl) -> None:
    """Emit the recovered grid as a real Word table.

    Grid spans and vertical merges are written directly rather than by merging
    cells after the fact: python-docx's merge cannot express a table whose
    cells were never created in the final shape, and it silently rewrites the
    grid when spans overlap.
    """
    total = sum(tbl.col_widths) or 1.0
    widths = [max(1, int(w / total * 9000)) for w in tbl.col_widths]  # twips

    t = _el("w:tbl")
    pr = _el("w:tblPr")
    pr.append(_el("w:tblW", **{"w:w": sum(widths), "w:type": "dxa"}))
    pr.append(_el("w:tblLayout", **{"w:type": "fixed"}))
    borders = _el("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        borders.append(_el(f"w:{side}", **{"w:val": "single", "w:sz": "4",
                                           "w:space": "0", "w:color": "999999"}))
    pr.append(borders)
    t.append(pr)

    grid = _el("w:tblGrid")
    for w in widths:
        grid.append(_el("w:gridCol", **{"w:w": w}))
    t.append(grid)

    starts = {(c.row, c.col): c for c in tbl.cells}
    owner = {}
    for c in tbl.cells:
        for dr in range(c.rowspan):
            for dc in range(c.colspan):
                owner[(c.row + dr, c.col + dc)] = c

    for r in range(tbl.nrows):
        tr = _el("w:tr")
        if r == 0 and tbl.header_row:
            trpr = _el("w:trPr")
            trpr.append(_el("w:tblHeader"))
            tr.append(trpr)
        c = 0
        while c < tbl.ncols:
            cell = starts.get((r, c))
            if cell is None:
                # covered: horizontal continuations are absorbed by gridSpan,
                # vertical ones still need a cell carrying vMerge.
                own = owner.get((r, c))
                if own is not None and own.row < r and own.col == c:
                    tc = _el("w:tc")
                    tcpr = _el("w:tcPr")
                    tcpr.append(_el("w:vMerge"))
                    tc.append(tcpr)
                    _cell_paragraphs(tc, "")
                    tr.append(tc)
                    c += 1
                    continue
                c += 1
                continue
            tc = _el("w:tc")
            tcpr = _el("w:tcPr")
            tcpr.append(_el("w:tcW", **{"w:w": sum(widths[c:c + cell.colspan]), "w:type": "dxa"}))
            if cell.colspan > 1:
                tcpr.append(_el("w:gridSpan", **{"w:val": cell.colspan}))
            if cell.rowspan > 1:
                tcpr.append(_el("w:vMerge", **{"w:val": "restart"}))
            tc.append(tcpr)
            _cell_paragraphs(tc, cell.text)
            tr.append(tc)
            c += cell.colspan
        t.append(tr)

    body = document.element.body
    sect = body.find(qn("w:sectPr"))
    if sect is not None:
        sect.addprevious(t)
    else:
        body.append(t)


def _attach_mark(paragraph, nid: int) -> None:
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "FootnoteReference")
    rpr.append(style)
    run.append(rpr)
    ref = OxmlElement("w:footnoteReference")
    ref.set(qn("w:id"), str(nid))
    run.append(ref)
    paragraph._p.append(run)


def _apply_page(document, prof) -> None:
    """Match the source page box and margins, so the page looks like the PDF."""
    from docx.shared import Mm  # noqa: F401  (kept for callers passing units)

    for section in document.sections:
        section.page_width = Pt(prof.page_width)
        section.page_height = Pt(prof.page_height)
        section.left_margin = Pt(max(0, prof.left_margin))
        section.right_margin = Pt(max(0, prof.right_margin))
        section.top_margin = Pt(max(0, prof.top_margin))
        section.bottom_margin = Pt(max(0, prof.bottom_margin))


def _apply_typography(document, prof) -> None:
    """Font, size, leading and justification, taken from the source itself."""
    normal = document.styles["Normal"]
    _set_body_font(document, prof.font_family)
    normal.font.size = Pt(prof.body_size)
    pf = normal.paragraph_format
    pf.line_spacing = prof.line_spacing
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if prof.justified:
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def write(doc: Doc, dst, prof=None, layout: str = "semantic") -> None:
    tpl = template_path()
    document = docx.Document(str(tpl)) if tpl.exists() else docx.Document()
    _clear(document)
    notes_part = _ensure_footnotes_part(document) if doc.notes else None

    prev_top = None      # last text line's top on the current page, for spacing
    prev_page = None
    prev_height = 0.0    # that line's own height, for the gap calculation
    for b in doc.blocks:
        if b.kind == "table" and b.table is not None:
            _add_table(document, b.table)
            prev_top = None
            continue
        if b.kind == "heading":
            style = "Title" if b.level == 0 else f"Heading {min(6, max(1, b.level))}"
            p = _add(document, b.text, style, b)
            # A lettered section ("H. REDACTIONS APPLIED FOR") carries its own
            # number in the text. The template's heading style also auto-numbers,
            # which would print "8 H. ..." — numId 0 turns that numbering off.
            if LETTERED_HEADING.match(b.text):
                _suppress_numbering(p)
        elif b.kind == "list_item":
            p = _add(document, b.text, "List Bullet", b)
            _apply_numbering(p, BULLET_NUM_ID, max(0, (b.level or 1) - 1))
        else:
            p = _add(document, b.text, None, b)
        if b.marker and notes_part is not None and b.marker in doc.notes:
            _attach_mark(p, _add_note(notes_part, doc.notes[b.marker]))
        if layout == "faithful":
            # The source's own line and page breaks carry the vertical rhythm,
            # so the template's style spacing would double-count it. Instead the
            # gap actually measured above this line supplies the extra space —
            # which is how a document whose paragraphs are separated by 9pt, 23pt
            # or 46pt keeps those gaps instead of being flattened to one pitch.
            pf = p.paragraph_format
            pf.space_after = Pt(0)
            # A line's height is the pitch, except where the line itself is
            # bigger than the pitch (a display heading): exact spacing at the
            # pitch would clip it.
            height = max(prof.line_pitch if prof else 0,
                         (b.size or (prof.body_size if prof else 12)) * 1.15)
            pf.line_spacing = Pt(height)
            if prev_top is not None and prev_page == b.page and b.top > 0:
                extra = (b.top - prev_top) - prev_height
                pf.space_before = Pt(max(0.0, min(extra, 200)))
            else:
                pf.space_before = Pt(0)
            if getattr(b, "page_break_before", False):
                pf.page_break_before = True
            prev_height = height
        prev_top = b.top if b.kind in ("body", "heading", "list_item") else None
        prev_page = b.page

    if notes_part is not None:
        notes_part._blob = notes_part.blob  # keep lxml bytes, not a tree

    if prof is not None:
        _apply_typography(document, prof)
        _apply_page(document, prof)
    else:
        _set_body_font(document)
        body_sizes = [b.size for b in doc.blocks if b.kind == "body" and b.size]
        if body_sizes:
            document.styles["Normal"].font.size = Pt(max(body_sizes))

    document.save(str(dst))
