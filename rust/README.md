# pdf2docx-core (Rust)

A Rust implementation of the converter, so the desktop app can ship **one binary**
instead of a Tauri shell plus a 32 MB frozen Python engine.

Built TDD: every module below began as a failing test.

```bash
cargo test          # 31 tests
```

## What is ported

| Module | What it does | Tests |
|---|---|---|
| `structure` | section numbering → heading levels, digits stripped; lists by indent/bullet/label; lettered sections; body/text discrimination; footnote zone and superscript-marker pairing | 13 |
| `extract` | PDF text lines via `lopdf`: `Tf`/`Tm`/`Td`/`Tj`/`TJ`, `/Widths` advances, `/ToUnicode` CMaps, bold from the font name | 5 |
| `writer` | OOXML package: `Heading 1..6`, `Title`, native bullet numbering, correct size ladder, `footnotes.xml` with real reference runs | 7 |
| `convert` | PDF → lines → blocks → DOCX | 2 |

Verified end to end by rendering the produced DOCX through LibreOffice and reading
it back: the title is 28pt, Heading 1 20pt, Heading 2 16pt, body 11pt, and list
items carry a real bullet glyph. A render is the only check that catches malformed
OOXML — the string-level tests passed while the size ladder was inverted.

## What is NOT ported yet

The Python implementation does substantially more. This is a working vertical
slice, not parity:

- **tables** — no detection; table text flows as paragraphs
- **layout profile** — page size, margins, leading and justification are fixed,
  not read from the source
- **font matching and tracking** — no installed-font scan, no metrics fitting
- **the two modes** — no `semantic` / `faithful` split; output is single-mode
- **numbering restarts**, multilevel lists, lettered numbering (`H.`) in Word

`docx-rs` was the intended writer and is not available offline here, so OOXML is
emitted directly — which is what the Python does anyway.

## Known limitations, measured rather than assumed

- **Base-14 fonts carry no `/Widths`.** A PDF set in non-embedded Helvetica,
  Times or Courier gives no advance table, so every glyph falls back to a
  500-unit default and a line's computed `x1` over-reports. `x0` comes from the
  text matrix and is exact, so geometry rules are written against `x0`.
- **`x1` includes a trailing space.** The advance is accumulated for every code
  in the string, including trailing whitespace that is then trimmed from the
  text, so `x1` can be one space wider than the visible line.
- **One `BT`..`ET` block is one line.** Text drawn with an unusual matrix is
  approximated rather than rejected.
