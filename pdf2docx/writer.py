"""Build the DOCX from classified blocks.

Structure comes from styles; fidelity comes from the style definitions plus a
run-level size where the source differs from the template. A heading is never a
bold paragraph, because then Word cannot see it.

Footnotes are written as OOXML by hand: python-docx has no footnote API, and a
note appended as prose is not a footnote to any tool that reads the document.
"""
from __future__ import annotations

import os
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


def _para(text: str, style: str | None = None, size: float | None = None,
          bold: bool = False, italic: bool = False):
    p = docx.text.paragraph.Paragraph(_empty_p(), None)
    return p


def _empty_p():
    return OxmlElement("w:p")


BULLET_NUM_ID = "12"   # the house template's bullet abstractNum (w:num w:numId=12)


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


def write(doc: Doc, dst) -> None:
    tpl = template_path()
    document = docx.Document(str(tpl)) if tpl.exists() else docx.Document()
    _clear(document)
    notes_part = _ensure_footnotes_part(document) if doc.notes else None

    for b in doc.blocks:
        if b.kind == "heading":
            p = _add(document, b.text, f"Heading {min(6, max(1, b.level))}", b)
        elif b.kind == "list_item":
            p = _add(document, b.text, "List Bullet", b)
            _apply_numbering(p, BULLET_NUM_ID, max(0, (b.level or 1) - 1))
        else:
            p = _add(document, b.text, None, b)
        if b.marker and notes_part is not None and b.marker in doc.notes:
            _attach_mark(p, _add_note(notes_part, doc.notes[b.marker]))

    if notes_part is not None:
        from lxml import etree
        notes_part._blob = notes_part.blob  # keep lxml bytes, not a tree

    _set_body_font(document)
    body_sizes = [b.size for b in doc.blocks if b.kind == "body" and b.size]
    if body_sizes:
        document.styles["Normal"].font.size = Pt(max(body_sizes))

    document.save(str(dst))
