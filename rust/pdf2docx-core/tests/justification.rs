//! A justified document must reflow justified. Setting every paragraph to the
//! left changes the line breaks of the whole page.
use pdf2docx_core::layout::profile;
use pdf2docx_core::structure::{classify_with, Line};

fn line(text: &str, x1: f32, top: f32) -> Line {
    let mut l = Line::new(text, 11.0, 60.0, x1, top);
    l.page_width = 595.0;
    l.page_height = 842.0;
    l
}

fn flush_right() -> Vec<Line> {
    // Every line but the last of each paragraph ends on the same measure.
    vec![
        line(
            "The first paragraph runs across the full measure of the page here",
            535.0,
            100.0,
        ),
        line(
            "and continues onto a second line which also reaches the right edge",
            535.0,
            113.0,
        ),
        line("before ending.", 180.0, 126.0),
        line(
            "The second paragraph likewise fills the measure of the text block",
            535.0,
            150.0,
        ),
        line("and then stops at the paragraph end.", 260.0, 163.0),
    ]
}

fn ragged() -> Vec<Line> {
    vec![
        line("A short first line", 180.0, 100.0),
        line("a rather longer second line ending elsewhere", 420.0, 113.0),
        line("and a third that stops sooner", 300.0, 126.0),
        line("A fourth line of different length", 350.0, 150.0),
    ]
}

#[test]
fn flush_right_lines_are_recognised_as_justified() {
    assert!(
        profile(&flush_right()).justified,
        "not detected as justified"
    );
}

#[test]
fn ragged_lines_are_not_justified() {
    assert!(
        !profile(&ragged()).justified,
        "ragged text called justified"
    );
}

#[test]
fn a_justified_document_is_written_justified() {
    let doc = classify_with(&flush_right(), &[]);
    let mut out = std::env::temp_dir();
    out.push("pdf2docx-rs-justified.docx");
    pdf2docx_core::writer::write(&doc, &out).unwrap();
    let f = std::fs::File::open(&out).unwrap();
    let mut zip = zip::ZipArchive::new(f).unwrap();
    let mut styles = String::new();
    std::io::Read::read_to_string(&mut zip.by_name("word/styles.xml").unwrap(), &mut styles)
        .unwrap();
    assert!(
        styles.contains(r#"<w:jc w:val="both"/>"#),
        "no justification in styles.xml: {styles}"
    );
}

#[test]
fn a_ragged_document_is_not_forced_justified() {
    let doc = classify_with(&ragged(), &[]);
    let mut out = std::env::temp_dir();
    out.push("pdf2docx-rs-ragged.docx");
    pdf2docx_core::writer::write(&doc, &out).unwrap();
    let f = std::fs::File::open(&out).unwrap();
    let mut zip = zip::ZipArchive::new(f).unwrap();
    let mut styles = String::new();
    std::io::Read::read_to_string(&mut zip.by_name("word/styles.xml").unwrap(), &mut styles)
        .unwrap();
    assert!(
        !styles.contains(r#"<w:jc w:val="both"/>"#),
        "ragged text was justified"
    );
}
