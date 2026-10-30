//! The DOCX must carry real Word structure: heading styles and native numbering,
//! not text that merely looks like a heading.
use pdf2docx_core::structure::{Block, Doc, Kind};
use pdf2docx_core::writer::write;
use std::io::Read;
use std::path::PathBuf;

fn out_path(name: &str) -> PathBuf {
    let mut p = std::env::temp_dir();
    p.push(format!("pdf2docx-rs-{name}.docx"));
    p
}

fn read_part(path: &PathBuf, part: &str) -> String {
    let f = std::fs::File::open(path).unwrap();
    let mut zip = zip::ZipArchive::new(f).unwrap();
    let mut s = String::new();
    zip.by_name(part).unwrap().read_to_string(&mut s).unwrap();
    s
}

fn sample() -> Doc {
    Doc {
        notes: Vec::new(),
        blocks: vec![
            Block { kind: Kind::Heading, text: "Quarterly Security Review".into(), level: 0, marker: None },
            Block { kind: Kind::Heading, text: "Scope of the Review".into(), level: 1, marker: None },
            Block { kind: Kind::Heading, text: "Systems Covered".into(), level: 2, marker: None },
            Block { kind: Kind::Body, text: "The review covered three systems.".into(), level: 0, marker: None },
            Block { kind: Kind::ListItem, text: "Mail server".into(), level: 0, marker: None },
            Block { kind: Kind::ListItem, text: "File server".into(), level: 0, marker: None },
        ],
    }
}

#[test]
fn writes_a_package_with_the_parts_word_requires() {
    let p = out_path("parts");
    write(&sample(), &p).unwrap();
    for part in ["[Content_Types].xml", "_rels/.rels", "word/document.xml",
                 "word/styles.xml", "word/numbering.xml"] {
        let body = read_part(&p, part);
        assert!(!body.is_empty(), "{part} is empty");
    }
}

#[test]
fn headings_use_heading_styles() {
    let p = out_path("headings");
    write(&sample(), &p).unwrap();
    let doc = read_part(&p, "word/document.xml");
    assert!(doc.contains("Heading1"), "no Heading1 in document.xml");
    assert!(doc.contains("Heading2"), "no Heading2 in document.xml");
}

#[test]
fn a_document_title_is_not_a_numbered_heading() {
    let p = out_path("title");
    write(&sample(), &p).unwrap();
    let doc = read_part(&p, "word/document.xml");
    // The title must not consume Heading 1, or every section shifts by one.
    assert!(doc.contains("Title"), "title should use the Title style");
}

#[test]
fn list_items_carry_native_numbering() {
    let p = out_path("lists");
    write(&sample(), &p).unwrap();
    let doc = read_part(&p, "word/document.xml");
    assert!(doc.contains("<w:numPr>"), "list paragraphs must carry numPr");
    assert!(doc.contains("<w:numId"), "numPr must reference a numId");
    let numbering = read_part(&p, "word/numbering.xml");
    assert!(numbering.contains("bullet"), "numbering.xml must define a bullet level");
}

#[test]
fn list_glyphs_are_not_baked_into_the_text() {
    let p = out_path("glyphs");
    let mut d = sample();
    d.blocks[4].text = "Mail server".into();
    write(&d, &p).unwrap();
    let doc = read_part(&p, "word/document.xml");
    assert!(!doc.contains("\u{2022} Mail server"), "glyph leaked into the text");
}

#[test]
fn body_text_survives_unchanged() {
    let p = out_path("body");
    write(&sample(), &p).unwrap();
    let doc = read_part(&p, "word/document.xml");
    assert!(doc.contains("The review covered three systems."));
}

#[test]
fn the_heading_size_ladder_descends_and_starts_below_the_title() {
    // A heading larger than the document title reads as more important than the
    // document itself.
    let p = out_path("ladder");
    write(&sample(), &p).unwrap();
    let styles = read_part(&p, "word/styles.xml");
    let size_of = |id: &str| -> u32 {
        let at = styles.find(&format!(r#"w:styleId="{id}""#)).unwrap();
        let seg = &styles[at..];
        let end = seg.find("</w:style>").unwrap();
        let seg = &seg[..end];
        let sz = seg.find(r#"<w:sz w:val=""#).unwrap();
        let rest = &seg[sz + 13..];
        rest[..rest.find('"').unwrap()].parse().unwrap()
    };
    assert!(size_of("Title") > size_of("Heading1"), "title must be largest");
    assert!(size_of("Heading1") > size_of("Heading2"), "H1 must exceed H2");
    assert!(size_of("Heading2") > size_of("Heading3"), "H2 must exceed H3");
}
