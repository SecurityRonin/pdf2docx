//! Bullets and sub-items are list entries; a list is a run, and indent alone is
//! not evidence of one. Each rule here was bought with a measurement on a real
//! document in the Python implementation.
use pdf2docx_core::structure::{classify_with, Kind, Line};

fn l(text: &str, size: f32, x0: f32, x1: f32, top: f32) -> Line {
    Line::new(text, size, x0, x1, top)
}

fn kinds(ls: &[Line]) -> Vec<Kind> {
    classify_with(ls, &[]).blocks.iter().map(|b| b.kind).collect()
}

#[test]
fn a_run_of_short_indented_lines_is_a_list() {
    let ls = vec![
        l("The review covered the following systems in scope.", 10.0, 60.0, 400.0, 100.0),
        l("Mail server", 10.0, 78.0, 160.0, 120.0),
        l("File server", 10.0, 78.0, 160.0, 134.0),
        l("Directory service", 10.0, 78.0, 190.0, 148.0),
    ];
    let k = kinds(&ls);
    assert_eq!(k.iter().filter(|x| **x == Kind::ListItem).count(), 3, "{k:?}");
}

#[test]
fn the_list_glyph_is_not_kept_in_the_text() {
    let ls = vec![
        l("Systems reviewed:", 10.0, 60.0, 400.0, 100.0),
        l("• Mail server", 10.0, 78.0, 160.0, 120.0),
        l("• File server", 10.0, 78.0, 160.0, 134.0),
    ];
    let d = classify_with(&ls, &[]);
    let item = d.blocks.iter().find(|b| b.kind == Kind::ListItem).unwrap();
    assert_eq!(item.text, "Mail server");
}

#[test]
fn justified_prose_is_not_a_list() {
    // Continuation lines start at varied x0 under justification and still run to
    // the right measure. Text that reaches the margin is not a list item.
    let ls = vec![
        l("The claimant engaged a photography agency named Guangzhou Fu", 12.0, 99.0, 500.0, 100.0),
        l("kesi Media Co., Ltd. and three of its affiliates to produce", 12.0, 71.0, 500.0, 114.0),
        l("advertising material for the campaign that appeared in three", 12.0, 99.0, 500.0, 128.0),
        l("magazines.", 12.0, 71.0, 500.0, 142.0),
    ];
    assert_eq!(kinds(&ls).iter().filter(|x| **x == Kind::ListItem).count(), 0);
}

#[test]
fn a_lone_indented_line_is_not_a_list() {
    // A list is a run. An indented heading must not lose its identity.
    let ls = vec![
        l("Body paragraph that is long enough to fill the measure completely.", 12.0, 99.0, 500.0, 100.0),
        l("Appendix 1 Software and Limitations", 12.0, 130.0, 330.0, 140.0),
        l("More body text that also fills the measure completely here.", 12.0, 99.0, 500.0, 170.0),
    ];
    assert_eq!(kinds(&ls).iter().filter(|x| **x == Kind::ListItem).count(), 0);
}

#[test]
fn a_lettered_all_caps_line_is_a_heading_not_a_bullet() {
    // "H. REDACTIONS APPLIED FOR" is a section in a court document. The letter
    // is numbering Word cannot generate, so it stays in the heading text.
    let ls = vec![
        l("Body paragraph that is long enough to fill the measure completely.", 12.0, 99.0, 500.0, 100.0),
        l("H. REDACTIONS APPLIED FOR", 12.0, 99.0, 330.0, 140.0),
    ];
    let d = classify_with(&ls, &[]);
    let h = d.blocks.iter().find(|b| b.kind == Kind::Heading).expect("no heading");
    assert_eq!(h.text, "H. REDACTIONS APPLIED FOR");
}

#[test]
fn parenthesised_letter_items_are_list_entries() {
    let ls = vec![
        l("The lifecycle involves the following stages:", 12.0, 99.0, 500.0, 100.0),
        l("(a) Ingestion. Source documents are collected from the client.", 12.0, 99.0, 480.0, 120.0),
        l("(b) Processing and review. The documents are placed in a system.", 12.0, 99.0, 480.0, 134.0),
    ];
    let d = classify_with(&ls, &[]);
    let items: Vec<_> = d.blocks.iter().filter(|b| b.kind == Kind::ListItem).collect();
    assert_eq!(items.len(), 2, "{:?}", d.blocks);
    assert!(items[0].text.starts_with("Ingestion."));
}
