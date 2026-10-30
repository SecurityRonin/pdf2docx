//! PDF in, DOCX out, with real structure at the far end.
use pdf2docx_core::convert;
use std::io::Read;
use std::path::PathBuf;

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data/simple.pdf")
}

fn read(path: &PathBuf, part: &str) -> String {
    let f = std::fs::File::open(path).unwrap();
    let mut zip = zip::ZipArchive::new(f).unwrap();
    let mut s = String::new();
    zip.by_name(part).unwrap().read_to_string(&mut s).unwrap();
    s
}

#[test]
fn converting_the_fixture_produces_a_structured_docx() {
    let mut out = std::env::temp_dir();
    out.push("pdf2docx-e2e.docx");
    convert(&fixture(), &out).expect("convert failed");

    let doc = read(&out, "word/document.xml");
    assert!(doc.contains("Heading1"), "no Heading 1 in output");
    assert!(doc.contains("Heading2"), "no Heading 2 in output");
    assert!(doc.contains("<w:numPr>"), "no native numbering in output");

    // Every source line must be present, and the section digits stripped.
    assert!(doc.contains("Scope of the Review"));
    assert!(
        !doc.contains("1. Scope of the Review"),
        "section digits not stripped"
    );
    assert!(doc.contains("Mail server"));
    assert!(!doc.contains("\u{2022}"));
}

#[test]
fn the_title_is_a_title_not_a_numbered_heading() {
    let mut out = std::env::temp_dir();
    out.push("pdf2docx-e2e-title.docx");
    convert(&fixture(), &out).unwrap();
    let doc = read(&out, "word/document.xml");
    let title_at = doc
        .find("Quarterly Security Review")
        .expect("title missing");
    let before = &doc[..title_at];
    let pstart = before.rfind("<w:p>").unwrap();
    let pprops = &doc[pstart..title_at];
    assert!(
        pprops.contains("Title"),
        "title paragraph has no Title style: {pprops}"
    );
}
