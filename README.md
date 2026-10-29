[![CI](https://github.com/SecurityRonin/pdf2docx/actions/workflows/ci.yml/badge.svg)](https://github.com/SecurityRonin/pdf2docx/actions/workflows/ci.yml)
[![Release](https://github.com/SecurityRonin/pdf2docx/actions/workflows/release.yml/badge.svg)](https://github.com/SecurityRonin/pdf2docx/releases)
[![Docs](https://img.shields.io/badge/docs-securityronin.github.io-blue)](https://securityronin.github.io/pdf2docx/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Sponsor](https://img.shields.io/badge/sponsor-h4x0r-ea4aaa?logo=github-sponsors)](https://github.com/sponsors/h4x0r)

**A DOCX you can edit, not a page made of text boxes.**

Most PDF→Word converters reproduce the page: every line a floating box, every section a bold paragraph. This one reproduces the *document* — real `Heading 2` styles, numbering Word generates itself, footnotes that live in `footnotes.xml` — and then matches the source's typography so the result still looks like the PDF it came from.

```bash
python -m pdf2docx contract.pdf contract.docx --layout faithful
```

**[Documentation →](https://securityronin.github.io/pdf2docx/)**

---

## Two modes, because layout and structure conflict in one place

Both keep real heading styles, native list numbering and true footnotes. They differ in whether the text reflows — the only thing that can conflict.

| | typography | text | pages |
|---|---|---|---|
| `semantic` (default) | matches the source | reflows; better to edit | differs |
| `faithful` | matches the source | line and page breaks pinned | matches |

Rendered back to PDF through **WordCraft 0.12.0** and compared with the original:

| Document | Pages | Text similarity | Pixels differing* |
|---|---|---|---|
| Two-page contract | **2 → 2** ✅ | **99.2% / 99.4%** | 13.6% / 19.3% |

\* At 150 dpi, differing by more than 32/255. That residual is glyph shape, not position: the source embeds Calibri, which is proprietary, so the renderer substitutes. Positions match; letterforms do not.

---

## What it does

| PDF evidence | DOCX result |
|---|---|
| `1.`, `1.2` numbering | `Heading 1`/`Heading 2`, digits stripped, Word supplies the number |
| larger type, short line | heading, level from numbering depth |
| bullet glyph, or indent + short line | `List Bullet` with an explicit `w:numPr` |
| `(a)`, `(b)` labels | list entries |
| trailing superscript + note zone | real footnote in `footnotes.xml` |
| ruled table | real `w:tbl` with `gridSpan`/`vMerge` and a repeating header row |
| page geometry, fonts, leading | page box, margins, type size, tracking |

**Fonts.** A PDF names its fonts, so the question is "do I have it, or its metrics". The ladder is: the exact face if installed → a **metric-compatible open clone** (Carlito for Calibri, Liberation for Arial) fetched with a pinned SHA-256 → the closest installed face, fitted by size and then by per-character tracking to the width the source measured. Proprietary faces are never downloaded: they cannot be redistributed, and their clones carry the same advance widths, which is what fidelity needs.

---

## Install

**From source**

```bash
git clone https://github.com/SecurityRonin/pdf2docx
cd pdf2docx
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pdf2docx in.pdf out.docx
```

**Desktop app** (macOS, Windows) — opens a PDF, previews it, converts in either mode:

```bash
cd app
npm install
./scripts/build-engine.sh
npm run tauri build
```

---

## What's different

| | real heading styles | numbering Word generates | true footnotes | real tables | page-faithful | edits cleanly |
|---|---|---|---|---|---|---|
| **pdf2docx** (Artifex) | partial | — | — | ✅ | ✅ | partial |
| **Docling** | partial · flat levels | — | — | ✅ | — | ✅ |
| **Marker** | partial · flat levels | — | — | ✅ | — | ✅ |
| **WordCraft** (DOCX→PDF) | n/a · consumer | n/a | n/a | ✅ | ✅ | n/a |
| **this** | ✅ | ✅ | ✅ | ✅ | ✅ (`faithful`) | ✅ (`semantic`) |

The ML converters detect headings well and never reconstruct their hierarchy; the layout converters match the page and hand you boxes.

---

## Trust, and its limits

- **Measured against independent renderers, not our own fixtures.** WordCraft and LibreOffice are separate DOCX implementations. Where they agree on a page count, that is evidence about the file; where they disagree, it is reported.
- **Not fuzzed.** The parser takes untrusted input and there is no fuzz story behind it, so no badge claims one.
- **Page-identical is demonstrated on two documents, not guaranteed.** Multi-column, rotated pages and floating objects are untested.
- **The failures are in the log.** A converter that silently dropped 20% of a contract, and a heading rule that ate lettered sections, were found by measurement and fixed; the commits say so.

---

## Known limits

- Untagged PDFs are inferred from geometry; there is no structure to read.
- 29.5% of PDFs carry a usable structure tree and the converter does not read it yet — measured at 88% heading recall versus 57% for the geometry path. It is the largest known win available.
- Scanned pages need OCR first.
- Pixels will not match without the original font.

---

[Privacy Policy](https://securityronin.github.io/pdf2docx/privacy/) · [Terms of Service](https://securityronin.github.io/pdf2docx/terms/) · © 2026 Security Ronin Ltd
