//! Reading a PDF's text lines with the attributes structure depends on.
use pdf2docx_core::extract::extract;
use std::path::PathBuf;

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data/simple.pdf")
}

#[test]
fn extracts_every_line_of_text() {
    let lines = extract(&fixture()).expect("extract failed");
    let texts: Vec<&str> = lines.iter().map(|l| l.text.as_str()).collect();
    assert!(texts.contains(&"Quarterly Security Review"), "{texts:?}");
    assert!(
        texts.iter().any(|t| t.contains("The review covered")),
        "{texts:?}"
    );
    assert!(texts.contains(&"Mail server"), "{texts:?}");
}

#[test]
fn reports_the_font_size_of_each_line() {
    let lines = extract(&fixture()).unwrap();
    let size_of = |needle: &str| lines.iter().find(|l| l.text.contains(needle)).unwrap().size;
    assert!((size_of("Quarterly Security") - 20.0).abs() < 0.6);
    assert!((size_of("The review covered") - 10.0).abs() < 0.6);
}

#[test]
fn reports_the_left_edge_and_top_of_each_line() {
    let lines = extract(&fixture()).unwrap();
    let body = lines
        .iter()
        .find(|l| l.text.starts_with("The review"))
        .unwrap();
    assert!((body.x0 - 60.0).abs() < 2.0, "x0 = {}", body.x0);
    assert!(body.x1 > body.x0);
    let item = lines.iter().find(|l| l.text == "Mail server").unwrap();
    assert!((item.x0 - 78.0).abs() < 2.0, "item x0 = {}", item.x0);
}

#[test]
fn reports_bold_from_the_font_name() {
    let lines = extract(&fixture()).unwrap();
    let title = lines.iter().find(|l| l.text.contains("Quarterly")).unwrap();
    let body = lines
        .iter()
        .find(|l| l.text.starts_with("The review"))
        .unwrap();
    assert!(title.bold, "title should be bold");
    assert!(!body.bold, "oblique body should not be bold");
}

#[test]
fn lines_come_back_in_reading_order() {
    let lines = extract(&fixture()).unwrap();
    let tops: Vec<f32> = lines.iter().map(|l| l.top).collect();
    assert!(tops.windows(2).all(|w| w[0] <= w[1]), "{tops:?}");
}

/// A PDF may break lines inside one `BT`..`ET` block with `T*`, `'` or `"`.
/// Not handling those collapses a whole paragraph into a single line — which
/// silently destroys every line-based decision made downstream.
#[test]
fn a_line_break_inside_one_text_block_still_ends_the_line() {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data/justified.pdf");
    let lines = extract(&p).expect("extract failed");
    assert!(
        lines.len() > 5,
        "collapsed into {} line(s): {:?}",
        lines.len(),
        lines
            .iter()
            .map(|l| l.text.chars().take(20).collect::<String>())
            .collect::<Vec<_>>()
    );
    let tops: std::collections::BTreeSet<i32> =
        lines.iter().map(|l| l.top.round() as i32).collect();
    assert!(tops.len() > 5, "only {} distinct baselines", tops.len());
}

/// Platypus, Word and LaTeX commonly wrap the page in `q cm ... Q` to place
/// the text block. Ignoring that transform leaves every line at x=0, so the
/// measured margins are wrong and the DOCX reflows the document.
#[test]
fn a_translated_text_block_keeps_its_real_position() {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data/justified.pdf");
    let lines = extract(&p).expect("extract failed");
    let left = lines.iter().map(|l| l.x0).fold(f32::INFINITY, f32::min);
    // 76, not 70: Platypus adds 6pt of frame padding inside the 70pt margin,
    // so 76 is where the glyphs actually start. The point of the assertion is
    // that the transform was applied at all — without it the edge is 0.
    assert!(
        (left - 76.0).abs() < 2.0,
        "left edge {left}, expected the text block at 76pt"
    );
}
