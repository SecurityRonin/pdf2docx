//! A ruled table must become a Word table, not paragraphs that happen to line up.
use pdf2docx_core::structure::{classify_with, Kind};
use std::io::Read;
use std::path::PathBuf;

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data/table.pdf")
}

fn part(path: &PathBuf, name: &str) -> String {
    let f = std::fs::File::open(path).unwrap();
    let mut zip = zip::ZipArchive::new(f).unwrap();
    let mut s = String::new();
    zip.by_name(name).unwrap().read_to_string(&mut s).unwrap();
    s
}

#[test]
fn a_ruled_grid_is_detected_as_a_table() {
    let lines = pdf2docx_core::extract::extract(&fixture()).unwrap();
    let segs = pdf2docx_core::extract::segments(&fixture()).unwrap();
    let doc = classify_with(&lines, &segs);
    let tables: Vec<_> = doc.blocks.iter().filter(|b| b.kind == Kind::Table).collect();
    assert_eq!(tables.len(), 1, "blocks: {:?}", doc.blocks.iter().map(|b| (&b.kind, &b.text)).collect::<Vec<_>>());
    let t = tables[0].table.as_ref().expect("table payload missing");
    assert_eq!((t.rows, t.cols), (2, 2), "grid {}x{}", t.rows, t.cols);
}

#[test]
fn cell_text_lands_in_its_own_cell() {
    let lines = pdf2docx_core::extract::extract(&fixture()).unwrap();
    let segs = pdf2docx_core::extract::segments(&fixture()).unwrap();
    let doc = classify_with(&lines, &segs);
    let t = doc.blocks.iter().find(|b| b.kind == Kind::Table).unwrap()
        .table.as_ref().unwrap();
    let at = |r: usize, c: usize| t.grid[r][c].clone();
    assert_eq!(at(0, 0), "Alpha");
    assert_eq!(at(0, 1), "Beta");
    assert_eq!(at(1, 0), "Gamma");
    assert_eq!(at(1, 1), "Delta");
}

#[test]
fn prose_beside_the_table_is_not_swallowed() {
    let lines = pdf2docx_core::extract::extract(&fixture()).unwrap();
    let segs = pdf2docx_core::extract::segments(&fixture()).unwrap();
    let doc = classify_with(&lines, &segs);
    let text: Vec<&str> = doc.blocks.iter().map(|b| b.text.as_str()).collect();
    assert!(text.iter().any(|t| t.contains("summarises the results")), "{text:?}");
    assert!(text.iter().any(|t| t.contains("no exceptions")), "{text:?}");
}

#[test]
fn the_docx_carries_a_word_table() {
    let mut out = std::env::temp_dir();
    out.push("pdf2docx-rs-table.docx");
    pdf2docx_core::convert(&fixture(), &out).unwrap();
    let doc = part(&out, "word/document.xml");
    assert!(doc.contains("<w:tbl>"), "no table element");
    assert_eq!(doc.matches("<w:tc>").count(), 4, "cell count");
    for want in ["Alpha", "Beta", "Gamma", "Delta"] {
        assert!(doc.contains(want), "{want} missing from the table");
    }
}
