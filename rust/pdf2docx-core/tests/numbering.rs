//! Section numbers are stripped from the text so Word can supply them — which
//! only works if Word is actually told to. Otherwise the number is simply lost.
use pdf2docx_core::structure::{classify_with, Line};
use std::io::Read;

fn line(text: &str, size: f32, x0: f32, x1: f32, top: f32) -> Line {
    Line::new(text, size, x0, x1, top)
}

fn doc_lines() -> Vec<Line> {
    vec![
        line("Quarterly Security Review", 20.0, 60.0, 340.0, 60.0),
        line("1. Scope of the Review", 15.0, 60.0, 230.0, 110.0),
        line("1.1 Systems Covered", 12.0, 60.0, 190.0, 140.0),
        line("H. REDACTIONS APPLIED FOR", 12.0, 60.0, 260.0, 170.0),
        line(
            "The review covered the following systems in scope.",
            10.0,
            60.0,
            300.0,
            200.0,
        ),
    ]
}

fn converted() -> (String, String) {
    let doc = classify_with(&doc_lines(), &[]);
    let mut out = std::env::temp_dir();
    out.push("pdf2docx-rs-numbering.docx");
    pdf2docx_core::writer::write(&doc, &out).unwrap();
    let read = |name: &str| {
        let f = std::fs::File::open(&out).unwrap();
        let mut zip = zip::ZipArchive::new(f).unwrap();
        let mut s = String::new();
        zip.by_name(name).unwrap().read_to_string(&mut s).unwrap();
        s
    };
    (read("word/document.xml"), read("word/numbering.xml"))
}

#[test]
fn a_numbered_section_gets_a_word_number() {
    let (doc, _) = converted();
    assert!(doc.contains(r#"<w:numPr>"#), "no numbering on any heading");
    assert!(
        doc.contains(r#"<w:numId w:val="2"/>"#),
        "heading list not applied"
    );
}

#[test]
fn the_numbering_definition_is_a_decimal_multilevel_list() {
    let (_, numbering) = converted();
    assert!(
        numbering.contains(r#"<w:lvlText w:val="%1."/>"#),
        "{numbering}"
    );
    assert!(
        numbering.contains(r#"<w:lvlText w:val="%1.%2"/>"#),
        "{numbering}"
    );
}

#[test]
fn a_subsection_uses_the_second_level() {
    let (doc, _) = converted();
    assert!(
        doc.contains(r#"<w:ilvl w:val="1"/>"#),
        "no level-2 numbering"
    );
}

#[test]
fn the_title_is_not_numbered() {
    let (doc, _) = converted();
    let title_at = doc
        .find("Quarterly Security Review")
        .expect("title missing");
    let window_start = doc[..title_at]
        .rfind("<w:p>")
        .or_else(|| doc[..title_at].rfind("<w:p "))
        .unwrap();
    assert!(
        !doc[window_start..title_at].contains("numPr"),
        "title was numbered"
    );
}

#[test]
fn a_lettered_heading_keeps_its_own_label() {
    let (doc, _) = converted();
    assert!(
        doc.contains("H. REDACTIONS APPLIED FOR"),
        "lettered heading lost its label"
    );
    let at = doc.find("H. REDACTIONS").unwrap();
    let start = doc[..at]
        .rfind("<w:p>")
        .or_else(|| doc[..at].rfind("<w:p "))
        .unwrap();
    assert!(
        !doc[start..at].contains("numPr"),
        "lettered heading was given a decimal number"
    );
}
