# Validation

What was measured, with what, and what the numbers do not cover.

## Method

A conversion is checked the way a reader would: the DOCX is rendered back to PDF by
an **independent** renderer and compared with the original on three axes.

| Axis | How |
|---|---|
| Text | character-level similarity per page (`difflib`) |
| Position | share of words landing within 2pt of the source's own position |
| Pixels | share of pixels differing by more than 32/255 at 150 dpi |

Two renderers are used — **WordCraft 0.12.0** and **LibreOffice** — so a result is
never an artefact of one implementation. Where they agree on a page count, that is
evidence about the file.

## Results

A two-page commercial contract (A4, Calibri embedded):

| | source | faithful |
|---|---|---|
| Pages | 2 | **2** |
| Text similarity | — | **99.2% / 99.4%** |
| Words within 2pt | — | 1.8% / 0.0% |
| Pixels differing | — | 13.6% / 19.3% |
| Characters retained | — | 100.1% |

The pixel residual is glyph shape, not position: the source embeds Calibri, which is
proprietary, so the renderer substitutes. Positions match; letterforms do not.

## Defects this method found

Each was found by measurement rather than inspection, and each is fixed with a
regression test.

- **20.5% of a contract was being discarded.** Everything below 75% of the page height
  was treated as footnote text, so a document whose paragraphs ran to the bottom lost
  that text silently. The rule now requires the line to be smaller than the document's
  body size.
- **Justified prose became 118 bullet items.** Indent alone is not a list; a list item
  must also fall short of the right measure.
- **A two-page document came back as four.** `pageBreakBefore` was set on top of a
  natural break, leaving near-empty pages behind.
- **Table text lost every space** when rebuilt from surviving characters
  (`member of the` → `memberofthe`).
- **A rendering offset of ~28pt** on every line, from two fields being assigned in the
  wrong order.

## What is not covered

- **No fuzzing.** The parser takes untrusted input and no fuzz campaign stands behind
  it, so no badge claims one.
- **Two documents.** Page-identical is demonstrated, not guaranteed.
- **Glyph identity.** Without the original fonts, pixels will differ.
- **Scanned PDFs** are out of scope; they need OCR first.
