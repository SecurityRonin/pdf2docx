# pdf2docx

Convert a PDF into a DOCX that carries **real Word structure** — heading styles,
native list numbering and true footnotes — instead of positioned text that happens
to look like the original.

```bash
python -m pdf2docx input.pdf output.docx                  # semantic (default)
python -m pdf2docx input.pdf output.docx --layout faithful
```

## Two modes, because layout and structure conflict in one place

Both keep real Heading styles, native numbering and true footnotes. They differ
only in whether the text reflows:

| | typography | text | pages |
|---|---|---|---|
| `semantic` | matches the source | reflows; better to edit | differs |
| `faithful` | matches the source | line and page breaks pinned | near-identical |

Measured against the source, rendered through LibreOffice:

| Document | Pages | semantic | faithful | page openings that match |
|---|---|---|---|---|
| CLLMSP Handbook | 26 | 0.73× | **1.00×** | 26/26 |
| Expert Report | 14 | 0.64× | **1.00×** | 12/14 |

Page count is exact on both. Page size, body size, font and margins match in
both modes. The two remaining opening mismatches are classification, not
layout: a table header cell whose text reorders, and a lettered sub-item
`(c)` emitted as a bullet.

## What it produces

| PDF evidence | DOCX result |
|---|---|
| section numbering (`1.`, `1.2`) | `Heading N`, digits stripped, Word supplies the number |
| larger type, short line | heading (level from numbering depth) |
| bullet glyph / indent + short line | `List Bullet` with explicit `w:numPr` |
| `(a)`, `b)` labels | list entry |
| trailing superscript digit + note zone | real footnote in `footnotes.xml` |

## Design notes

**Structure beats fidelity where they conflict** — a heading is `Heading 2`, never a
bold paragraph, because a bold paragraph is invisible to the navigation pane, to a
generated table of contents, and to any tool that walks the outline.

**Styles come from the expert-report-kit `house-report.docx`**, used as a style
library (Heading1-9, `FootnoteText`, a `numbering.xml` with six formats). Its body
content and running headers/footers are stripped: that stationery is not the source
document's content.

**Two rules were bought with measurements**, and both are pinned by tests:

- *Justified text is not a list.* Indent alone turned 118 lines of prose into bullets
  in a real court document. A list item must also fall short of the right measure.
- *A bold line at body size is not a heading.* It produced 36 H1s where the document's
  own structure tree carried 13. Type size and numbering decide, not weight.

## Testing

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

Some tests render through LibreOffice and read the result back, because a DOCX can be
structurally valid and still print wrong — the render oracle caught a leaked cover
page and a font that corrupted every `e` into `(cid:2)`.

To score heading detection against a real document's own tag tree:

```bash
PDF2DOCX_TAGGED_FIXTURE=/path/to/tagged.pdf .venv/bin/python -m pytest tests/test_against_tag_tree.py
```

## Known limits

- Untagged PDFs are inferred from geometry only; there is no structure to read.
- Multi-column layouts, tables and scanned pages are not handled.
- Rich labelled PDFs (which carry `H1`/`H2`/`List Paragraph` tags bound to MCIDs) are
  detected by the research in `RESEARCH.md` but the converter does not yet use the tag
  path — that is the highest-value next step, measured at 88% heading recall.
