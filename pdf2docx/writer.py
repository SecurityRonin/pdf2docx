"""Build the DOCX from classified blocks.

Structure comes from styles; fidelity comes from the style definitions plus a
run-level size where the source differs from the template. A heading is never a
bold paragraph, because then Word cannot see it.
"""
from __future__ import annotations

import os
from pathlib import Path

import docx
from docx.shared import Pt

from .structure import Block

# The house template supplies Heading1-9, FootnoteText/FootnoteReference and a
# numbering.xml with bullet and decimal formats. Override with PDF2DOCX_TEMPLATE.
DEFAULT_TEMPLATE = Path("/Users/4n6h4x0r/src/expert-report-kit/templates/house-report.docx")


def template_path() -> Path:
    env = os.environ.get("PDF2DOCX_TEMPLATE")
    return Path(env) if env else DEFAULT_TEMPLATE


def _clear(document):
    """Drop the template's own body content, keeping styles, numbering and sectPr."""
    body = document.element.body
    for child in list(body):
        if child.tag.endswith("}sectPr"):
            continue
        body.remove(child)


def write(blocks: list[Block], dst) -> None:
    tpl = template_path()
    document = docx.Document(str(tpl)) if tpl.exists() else docx.Document()
    _clear(document)

    for b in blocks:
        if b.kind == "heading":
            p = document.add_paragraph(b.text, style=f"Heading {min(6, max(1, b.level))}")
        else:
            p = document.add_paragraph(b.text)
        run = p.runs[0] if p.runs else p.add_run("")
        run.bold = True if b.bold else None
        run.italic = True if b.italic else None

    # Default the body size to the source's own, so the page looks like the PDF.
    body_sizes = [b.size for b in blocks if b.kind == "body"]
    if body_sizes:
        document.styles["Normal"].font.size = Pt(max(body_sizes))

    document.save(str(dst))
