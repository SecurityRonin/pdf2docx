# pdf2docx

A converter that produces a DOCX you can edit, rather than a page recreated out of
positioned text.

```bash
python -m pdf2docx input.pdf output.docx --layout faithful
```

## The two modes

Both keep real heading styles, native list numbering and true footnotes. They differ
only in whether the text reflows, which is the one place layout and structure
actually conflict.

| | typography | text | pages |
|---|---|---|---|
| `semantic` (default) | matches the source | reflows; better to edit | differs |
| `faithful` | matches the source | line and page breaks pinned | matches |

`faithful` is still fully tagged — it is not a picture of a page. Every heading is a
`Heading N` style, every list is numbered by Word, every note is a real footnote.

## What comes across

| PDF evidence | DOCX result |
|---|---|
| `1.`, `1.2` numbering | `Heading N`, digits stripped, Word numbers it |
| larger type, short line | heading, level from numbering depth |
| bullet glyph, or indent + short line | `List Bullet` with an explicit `w:numPr` |
| `(a)`, `(b)` labels | list entries |
| trailing superscript + note zone | footnote in `footnotes.xml` |
| ruled table | `w:tbl` with `gridSpan`/`vMerge`, repeating header |
| page geometry and type | page box, margins, size, leading, tracking |

## Honest status

Page-identical output is demonstrated on two documents — a two-page contract and a
26-page handbook — not proven in general. Multi-column layouts, rotated pages and
floating objects are untested. See [Validation](validation.md) for the measurements
and the failures found on the way.

The largest known improvement is not yet built: 29.5% of PDFs carry a structure tree
this converter does not read, measured at 88% heading recall against 57% for the
geometry path.
