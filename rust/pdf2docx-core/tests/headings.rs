//! Numbered sections become headings, the level comes from the number, and the
//! digits are stripped so Word can supply them.
use pdf2docx_core::structure::{classify, Kind, Line};

fn line(text: &str, size: f32, x0: f32, x1: f32, top: f32) -> Line {
    Line::new(text, size, x0, x1, top)
}

fn doc() -> Vec<Line> {
    vec![
        line("Quarterly Security Review", 20.0, 60.0, 340.0, 60.0),
        line("1. Scope of the Review", 15.0, 60.0, 230.0, 110.0),
        line("1.1 Systems Covered", 12.0, 60.0, 190.0, 140.0),
        line("The review covered the following systems in scope.", 10.0, 60.0, 300.0, 170.0),
    ]
}

#[test]
fn numbered_section_becomes_a_heading() {
    let d = classify(&doc());
    let h = d.blocks.iter().find(|b| b.text.contains("Scope")).expect("no heading");
    assert_eq!(h.kind, Kind::Heading);
}

#[test]
fn heading_level_follows_the_section_number() {
    let d = classify(&doc());
    let by = |s: &str| d.blocks.iter().find(|b| b.text == s).unwrap().clone();
    assert_eq!(by("Scope of the Review").level, 1);
    assert_eq!(by("Systems Covered").level, 2);
}

#[test]
fn section_digits_are_not_baked_into_the_text() {
    let d = classify(&doc());
    // Guard against a vacuous pass: `all()` on an empty set is true.
    assert!(!d.blocks.is_empty(), "classifier produced no blocks");
    assert!(d.blocks.iter().all(|b| !b.text.starts_with("1.")), "{:?}",
            d.blocks.iter().map(|b| &b.text).collect::<Vec<_>>());
    assert!(d.blocks.iter().all(|b| !b.text.starts_with("1.1")));
}

#[test]
fn body_text_is_not_a_heading() {
    let d = classify(&doc());
    let b = d.blocks.iter().find(|b| b.text.starts_with("The review")).unwrap();
    assert_eq!(b.kind, Kind::Body);
}

#[test]
fn the_first_unnumbered_heading_is_the_title() {
    // A document title must not consume numbering: giving it Heading 1 makes
    // Word number it 1 and pushes every real section down by one.
    let d = classify(&doc());
    let t = d.blocks.iter().find(|b| b.text == "Quarterly Security Review").unwrap();
    assert_eq!(t.level, 0, "title should have level 0");
}
