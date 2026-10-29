# Building a Semantic PDF→DOCX Converter

**Research report — 29 October 2026**
Scope: a converter that reconstructs *semantic* structure (headings and their levels, numbered sections, bullets, tables) rather than reproducing literal positioned glyphs.

---

## Executive summary

**Recommendation: build it, but build it as a structure-first pipeline that reads the PDF's own tag tree, and treat every ML model as a fallback for untagged pages — not as the engine.**

Three measured facts drive this:

1. **The structure often already exists and we can read it in Python.** Of 176 readable PDFs on this machine, **52 (29.5%) carry a real structure tree** with more than 50 structure elements; one handbook has 6,113. `pdfplumber` exposes the per-character `mcid` and `tag`, so a tagged PDF's `H1`/`H2`/`List Paragraph` elements bind straight to text. [OBSERVED — `research/tags.py`, `research/tagpath.py`, 2026-10-29]

2. **Reading tags beats every heuristic and every ML model on level assignment.** On the same 26-page handbook: geometric heuristic → **47% heading recall**; Docling (ML) → **110 headings, all emitted at one level**; tag path → **88% recall with 45/45 correct levels** and 44 list items recovered. [OBSERVED — `research/proto.py`, `research/eval.py`, `research/docling_hb.md`]

3. **The "not literal" requirement is mostly a DOCX writer problem, not a parsing problem.** Real Word numbering is a list *definition*, not typed digits. Verified through a LibreOffice render: a second list built with python-docx's `List Number` style continues **3, 4**, while pandoc's per-list abstract numbering restarts **1, 2**. [OBSERVED — `research/lists_pandoc.docx`, `research/py_numtest.docx`, rendered 2026-10-29]

The residual risk is concentrated in one place: **70% of PDFs have no usable tag tree**, and for those you are back to inference. That is where the engineering effort belongs, and where an off-the-shelf tool will beat a naive build.

---

## 1. Why "literal" fails and what replaces it

A PDF has no paragraphs. It has a content stream of glyphs at coordinates; word spaces and line breaks are not in it, they are inferred from positions. Any converter that carries those coordinates into DOCX produces text boxes and hard returns — editable in bytes, not in Word.

The replacement principle is **classification, not transcription**:

| PDF evidence | Reconstructed DOCX concept |
|---|---|
| `H1`–`H6` structure element | paragraph style `Heading 1`–`Heading 6` |
| `List Paragraph` / `LBody` element | paragraph with `numPr` → real list |
| numbering glyph `1.2.3` in text | heading text with auto-numbering, dotted digits stripped |
| font size tier | heading level (fallback only) |
| glyph positions | **discarded** |

The output must be *reflowable*: page count and line breaks will not match the original, and that is the correct outcome, not a defect.

---

## 2. What the corpus actually looks like

Census of PDFs under `~/Downloads` (n = 181 opened, 176 parsed):
[OBSERVED — `research/census.py`, `research/tags.py`, 2026-10-29]

| Property | Count | Reading |
|---|---|---|
| Usable structure tree (>50 elements) | **52 / 176 (29.5%)** | tag-first path applies |
| Any outline / bookmark TOC | 15 / 79 | outline titles are *unreliable* — books list chapters only |
| Median distinct font sizes | 5 | geometric tiering is viable as fallback |
| ≤3 distinct sizes | 12 / 79 | heuristic will struggle badly |
| Lines matching a numbering prefix | 57 / 79 | usually the strongest single signal |

The tag tree is uneven by producer in a predictable way: LaTeX and Adobe/Word exports are tagged; older scanner and print-driver output is not. A production tool should **branch on this per document, and per page.**

---

## 3. Results, on one document, three ways

Same input (`CLLMSP Handbook.pdf`, 26 pages; its own tree reports 13 `H1`, 45 `H2`, 28 tables, 44 list paragraphs).

| Approach | Headings emitted | Recall (vs numbered-title key) | Correct level | Lists |
|---|---|---|---|---|
| Geometric heuristic (size ≥ body×1.04 + numbering regex) | 50 | 47.1% | 24/24 | 1 |
| Docling 2.110 (ML, CPU) | 110 | not scored | **0** — all `##` | 59 `list_item` |
| **Tag path (pdfplumber MCID → tag)** | 58 | **88.2%** | **45/45** | **44** |

**Read the numbers with their denominators.** My independent key is *numbered section titles only*, which is why the tag path scores 0.776 precision there: the 13 "extra" headings are genuinely unnumbered headings (`About This Handbook`, `Table of Contents`, the module titles) that the key cannot see. Against the document's own structure tree, recovery is exact by construction. The honest statement: **88% recall against a partially-blind key, 100% level agreement on everything recovered.**

The heuristic's 47% is the more instructive number. It emits a title page as Heading 1, then a banner, and it assigns `Heading 5` and `Heading 6` to body text because six size tiers exist and the mapping is naive. That is not a tuning problem; it is what happens when you infer a semantic layer that is not in the data.

`★ Insight ─────────────────────────────────────`
The 26→46 page regression in the first tag run, and the 1067 MCID groups for 965 body paragraphs, both came from the same cause: **one MCID is a text run, not a paragraph.** A line split mid-sentence by an inline bold word produces two groups. Detecting structure from tags is easy; reconstructing paragraph boundaries on top of it is the real work, and it is the same merge logic you need for untagged PDFs.
`─────────────────────────────────────────────────`

---

## 4. The architecture

```
PDF
 ├─ page-level probe ─── has /StructTreeRoot with H*/L* elements?
 │
 ├─ YES → TAG PATH  (high fidelity, ~30% of corpus)
 │    pdfplumber chars → group by (page, mcid) → tag each group
 │    → merge same-tag neighbours into paragraphs
 │    → Heading 1..6 / list / body
 │
 └─ NO  → INFERENCE PATH  (~70% of corpus)
      body-size detection (char-weighted mode)
      → type-size tier clustering
      → numbering-prefix regex  ─┐
      → bold + short + no terminal punctuation ─┤→ heading score
      → vertical gap above ──────┘
      → list detection (glyph or prefix, indent → nesting level)

      optional: Docling for reading order, tables, scans (never for levels)
                │
      ──────────┴──────────→ STRUCTURED IR (JSON: blocks with kind+level)
                              → DOCX writer (styles + numbering.xml)
```

**Keep an explicit intermediate representation.** Text → IR → DOCX, never stream-to-DOCX. It lets you diff converters, re-render after fixing the writer, and expose the structure as JSON for verification.

### Writer rules that make it "not literal"

1. **Numbering is a list definition.** Use a `w:abstractNum` per list *pattern*, and a fresh `w:num` instance per list *occurrence* so every new list restarts at 1. Pandoc already does this correctly; python-docx's built-in `List Number` style does not.
2. **Strip section digits from heading text.** `2.3 Data Poisoning` → `Data Poisoning` + `Heading 2`, with the document's own `multilevel list` supplying `2.3`. This is what makes the section numbering *editable*; leaving the digits baked in reproduces the PDF's worst property.
3. **Styles, not direct formatting.** Emit `Heading 1..6`, `List Bullet`, `List Number` and a rebuilt `Normal`. Never set font size or indent per paragraph to imitate the page.
4. **Tables as real tables.** Tagged PDFs carry `Table/TR/TD`; untagged ones need table *structure* recognition — Docling is genuinely good here and is worth using for this alone.

---

## 5. Where a from-scratch build will hurt

| Problem | Difficulty | Evidence / note |
|---|---|---|
| Untagged PDFs (70%) | **High** — the main risk | heuristic hits 47% on a clean document |
| Multi-column and sidebars | High | reading order is a layout problem, not a text problem |
| Tables without tags | High | merged cells, spanning headers, financial sign conventions |
| Inline emphasis (bold runs mid-sentence) | Medium | causes the MCID fragmentation above |
| Footnotes | Medium | not in the body stream; `MinerU` reportedly deletes them [QUOTED, benchmark] |
| Math / equations | High | needs OMML; Docling drops rather than fakes them [QUOTED] |
| Scanned pages | Separate problem | requires OCR first (Vision + Tesseract/PaddleOCR) |
| Ligatures, soft hyphens, smart quotes | Low but fatal if skipped | normalise at extraction, never post-hoc |

---

## 6. Build vs buy — and the licence trap

| Tool | What it is good at | Why it is not the answer here |
|---|---|---|
| **pdf2docx** (Artifex) | real DOCX, tables, text PDFs | threshold-based **layout** reconstruction; earlier reports that lists/headings come out as styled body text |
| **Docling** | tables, reading order, `list_item`/`section_header` labels | **no `export_to_docx`** in 2.110 (verified: dict, doclang, doctags, element_tree, html, markdown, text, vtt only); **no heading levels** |
| **Marker** | accuracy on hard documents | same flat-heading defect (upstream issue #730, maintainer confirmed unsupported); **weights restricted** above a revenue/funding threshold |
| **Pandoc** | DOCX *writing* — correct numbering model | has no PDF reader |

`★ Insight ─────────────────────────────────────`
The licence finding matters more than the quality finding for a forensic or client deliverable. Marker 2 moved its *code* to Apache-2.0 (2026-07-20) but its Surya *weights* carry a separate restriction; two secondary sources put the commercial threshold at $5M revenue/funding. That is quoted, not verified against the licence text — check `datalab.to/terms` before shipping anything commercial. Docling is MIT throughout and is the safer dependency.
`─────────────────────────────────────────────────`

**Recommended split:** own the *structure decision* (tag read + IR + writer), reuse the *perception* (Docling for tables/reading-order on untagged pages). That is a small, honest seam rather than a reimplementation of table structure recognition.

---

## 7. Build plan

| Phase | Deliverable | Acceptance test |
|---|---|---|
| 0 | Corpus + scorer (already built: `eval.py`) | scorer reproduces today's numbers |
| 1 | Tag path + writer | ≥95% level agreement on 20 tagged PDFs |
| 2 | IR + heuristic fallback | ≥80% heading recall on numbered-section documents |
| 3 | Lists: nesting + restart | render-oracle: two lists render 1,2 / 1,2 |
| 4 | Tables (Docling on untagged) | cell-level precision on a table-heavy set |
| 5 | Rendered-page QA | LibreOffice render → font-size tiers match the original's tier count |

**The test that must exist from day one** is the one used here: convert → render to PDF → read back the *visible* numbering and heading sizes. Asserting on the DOCX XML alone is not enough, because the XML can be structurally valid and still render `3, 4` where the source said `1, 2`.

---

## 8. What I did not establish

- **No benchmark against `pdf2docx` itself** — it is not installed here, and its list/heading behaviour is reported from issue threads, not measured. [NOT ESTABLISHED]
- **One document scored end-to-end.** The 29.5% tagged figure is from 176 files; the quality comparison is n=1.
- **Benchmark figures quoted in §5** come from a public 9-tool benchmark that is **published by one of the tools it scores** (pdfmarkdown.app). Treat its rankings as a contestant's ledger, not an independent measurement.
- **CJK, RTL, multi-column and scanned inputs** were not exercised at all.
- Marker's exact licence threshold is secondary-sourced.

## 9. Recommendation

Build the tag-first pipeline with a DOCX writer of your own and Docling as the untagged-page fallback. It is a few hundred lines to a working prototype — the prototype in `research/` already produces correct hierarchy on tagged input — and the hard, valuable work is the untagged path and the table handling, which no existing tool solves in a way that preserves Word semantics.

---

### Reproducing this

```bash
cd /Users/4n6h4x0r/src/pdf2docx/research
python3 census.py      # corpus shape
python3 tags.py        # structure-tree coverage
python3 tagpath.py  <in.pdf> <out.docx>   # tag path
python3 proto.py    <in.pdf> <out.docx>   # heuristic path
python3 eval.py     <in.pdf> <out.docx>   # score either against ground truth
soffice --headless --convert-to pdf <out.docx>   # render oracle
```
