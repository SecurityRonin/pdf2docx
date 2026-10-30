//! The page must come from the source, not from a constant.
//!
//! A DOCX whose page size and margins are hard-coded reflows every document
//! that was not set to that page: a Letter PDF opens as A4 and its line breaks
//! move. These tests fail against any fixed profile.
use pdf2docx_core::convert;
use std::io::Read;
use std::path::PathBuf;

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data/layout.pdf")
}

fn part(path: &PathBuf, name: &str) -> String {
    let f = std::fs::File::open(path).unwrap();
    let mut zip = zip::ZipArchive::new(f).unwrap();
    let mut s = String::new();
    zip.by_name(name).unwrap().read_to_string(&mut s).unwrap();
    s
}

#[test]
fn page_size_matches_the_source_letter_page() {
    let lines = pdf2docx_core::extract::extract(&fixture()).unwrap();
    let p = pdf2docx_core::layout::profile(&lines);
    assert!((p.page_width - 612.0).abs() < 1.0, "width {}", p.page_width);
    assert!((p.page_height - 792.0).abs() < 1.0, "height {}", p.page_height);
}

#[test]
fn margins_are_measured_not_assumed() {
    let lines = pdf2docx_core::extract::extract(&fixture()).unwrap();
    let p = pdf2docx_core::layout::profile(&lines);
    assert!((p.margin_left - 90.0).abs() < 2.0, "left {}", p.margin_left);
    // 1134 twips = 56.7pt is the old constant; 90pt is 1800 twips.
    assert!((p.margin_left - 56.7).abs() > 20.0, "margin looks hard-coded");
}

#[test]
fn the_docx_page_matches_the_source() {
    let mut out = std::env::temp_dir();
    out.push("pdf2docx-rs-layout.docx");
    convert(&fixture(), &out).unwrap();
    let doc = part(&out, "word/document.xml");
    // 612pt x 792pt at 20 twips/pt.
    assert!(doc.contains(r#"<w:pgSz w:w="12240" w:h="15840""#), "page size not applied: {doc}");
    assert!(doc.contains(r#"<w:pgMar w:top="#), "no margin block");
    assert!(!doc.contains(r#"w:left="1134""#), "margins are still the old constant");
}

#[test]
fn text_that_stops_mid_page_does_not_define_the_bottom_margin() {
    // The whitespace below the last line is not a margin: taking it as one
    // shrinks the text area to a few lines and pushes the document onto a
    // second page. Measured on this fixture as 575pt against a real margin.
    let lines = pdf2docx_core::extract::extract(&fixture()).unwrap();
    let p = pdf2docx_core::layout::profile(&lines);
    assert!(p.margin_bottom < 100.0, "bottom margin {}", p.margin_bottom);
}
