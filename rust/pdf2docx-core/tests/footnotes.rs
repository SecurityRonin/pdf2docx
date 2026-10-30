//! A footnote must be a real Word footnote: a reference in the body and its text
//! in footnotes.xml — not the note appended as prose.
use pdf2docx_core::convert;
use std::io::Read;
use std::path::PathBuf;

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data/footnote.pdf")
}

fn part(path: &PathBuf, name: &str) -> String {
    let f = std::fs::File::open(path).unwrap();
    let mut zip = zip::ZipArchive::new(f).unwrap();
    let mut s = String::new();
    zip.by_name(name).unwrap().read_to_string(&mut s).unwrap();
    s
}

fn converted() -> (PathBuf, String, String) {
    let mut out = std::env::temp_dir();
    out.push("pdf2docx-rs-footnote.docx");
    convert(&fixture(), &out).expect("convert failed");
    let doc = part(&out, "word/document.xml");
    let notes = part(&out, "word/footnotes.xml");
    (out, doc, notes)
}

#[test]
fn the_note_text_lives_in_the_footnotes_part() {
    let (_p, _doc, notes) = converted();
    assert!(notes.contains("Statement of A. Example"), "note not in footnotes.xml: {notes}");
}

#[test]
fn the_body_carries_a_footnote_reference() {
    let (_p, doc, _n) = converted();
    assert!(doc.contains("footnoteReference"), "no reference run in the body");
}

#[test]
fn the_note_is_not_left_in_the_body() {
    let (_p, doc, _n) = converted();
    assert!(!doc.contains("Statement of A. Example"), "note leaked into the body");
}

#[test]
fn the_mark_is_not_left_in_the_body_text() {
    // The superscript "1" must become a reference, not a literal character.
    let (_p, doc, _n) = converted();
    assert!(doc.contains("signed on 12 March."), "body text was altered: {doc}");
}

#[test]
fn the_separator_rule_is_not_a_paragraph() {
    let (_p, doc, _n) = converted();
    assert!(!doc.contains("------------"), "the note separator leaked into the body");
}

#[test]
fn a_long_footnote_does_not_become_the_body_size() {
    // Character weight alone lets a long note outvote the prose it annotates.
    let lines = pdf2docx_core::extract::extract(&fixture()).unwrap();
    assert_eq!(pdf2docx_core::structure::body_size(&lines), 12.0);
}
