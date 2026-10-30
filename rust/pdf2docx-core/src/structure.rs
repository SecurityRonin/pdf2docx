//! Classify extracted lines into document structure.
//!
//! The governing rule is that a heading is identified by what the document says
//! about itself — its own section numbering — and only then by typography. Size
//! alone invents headings in title pages and banners; a section number cannot be
//! faked by a font.
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Heading,
    Body,
    ListItem,
    Table,
}

/// One text line as read from the PDF.
#[derive(Debug, Clone)]
pub struct Line {
    pub text: String,
    pub size: f32,
    pub x0: f32,
    pub x1: f32,
    pub top: f32,
    pub bold: bool,
    pub page: usize,
    /// The page the line sits on. The note zone is defined from the bottom of
    /// the page, and the page size is measured from these, so a line cannot be
    /// placed or classified without them.
    pub page_height: f32,
    pub page_width: f32,
}

impl Line {
    pub fn new(text: &str, size: f32, x0: f32, x1: f32, top: f32) -> Self {
        Self {
            text: text.to_string(),
            size,
            x0,
            x1,
            top,
            bold: false,
            page: 0,
            page_height: 0.0,
            page_width: 0.0,
        }
    }
}

#[derive(Debug, Clone)]
pub struct Block {
    pub kind: Kind,
    pub text: String,
    /// 1-based heading depth; 0 means "document title".
    pub level: u8,
    /// Footnote marker this block carries ("1"), if any.
    pub marker: Option<String>,
    /// Cell contents, for a table block.
    pub table: Option<crate::table::Table>,
    /// True when the source carried a section number, which was stripped from
    /// the text so Word could supply it. A lettered heading keeps its own label
    /// and must not also be given a decimal one.
    pub numbered: bool,
}

#[derive(Debug, Default)]
pub struct Doc {
    pub blocks: Vec<Block>,
    /// Numbered notes (`"1" -> "Statement of ..."`), paired by number.
    pub notes: Vec<(String, String)>,
    /// Page geometry measured from the source.
    pub layout: crate::layout::Profile,
}

const TERMINAL: [char; 6] = ['.', ';', ',', ':', '?', '!'];

/// Split a leading section number from the rest: "1.2 Scope" -> (2, "Scope").
///
/// The prefix is the longest run of digits and dots that contains a digit and is
/// followed by whitespace. Depth counts the dots *inside* the number, so "1."
/// is depth 1 and "1.2" is depth 2.
pub fn split_section(text: &str) -> Option<(u8, String)> {
    let mut end = 0usize;
    let mut has_digit = false;
    for (i, c) in text.char_indices() {
        match c {
            '0'..='9' => {
                has_digit = true;
                end = i + c.len_utf8();
            }
            '.' => end = i + 1,
            _ => break,
        }
    }
    if !has_digit {
        return None;
    }
    let rest = text[end..].trim_start();
    if rest.len() == text[end..].len() {
        return None; // no whitespace after the number
    }
    if rest.is_empty() {
        return None;
    }
    let num = text[..end].trim_end_matches('.');
    let depth = (num.matches('.').count() + 1) as u8;
    Some((depth, rest.trim().to_string()))
}

/// The document's body size: the size carrying the most characters, measured
/// over the body region of the page.
///
/// Measuring over the whole page lets a long footnote out-vote the prose it
/// annotates — 55 characters of note against 44 of text — and taking the note's
/// size as the body then hides every note from the note zone, because nothing
/// is smaller than itself. The bottom quarter of the page is excluded from the
/// vote; text there is still kept, it just does not define the prose.
pub fn body_size(lines: &[Line]) -> f32 {
    let region: Vec<&Line> = lines
        .iter()
        .filter(|l| !l.text.trim().is_empty())
        .filter(|l| l.page_height <= 0.0 || l.top <= l.page_height * NOTE_ZONE)
        .collect();
    let subset: Vec<&Line> = if region.is_empty() {
        lines.iter().filter(|l| !l.text.trim().is_empty()).collect()
    } else {
        region
    };
    let mut weight: HashMap<u32, usize> = HashMap::new();
    for l in subset {
        *weight.entry((l.size * 10.0).round() as u32).or_default() += l.text.chars().count();
    }
    weight
        .into_iter()
        .max_by_key(|(_, w)| *w)
        .map(|(s, _)| s as f32 / 10.0)
        .unwrap_or(11.0)
}

fn is_short_title(rest: &str) -> bool {
    rest.chars().count() <= 90 && rest.split_whitespace().count() <= 12
}

fn is_heading(l: &Line, body: f32) -> bool {
    let t = l.text.trim();
    if t.chars().count() > 160 || t.split_whitespace().count() > 18 {
        return false;
    }
    if t.ends_with(TERMINAL) {
        return false;
    }
    let bigger = l.size >= body * 1.04;
    match split_section(t) {
        Some((_, rest)) => bigger || (l.bold && is_short_title(&rest)),
        None => bigger,
    }
}

const BULLETS: [char; 10] = [
    '\u{2022}', '\u{25aa}', '\u{25e6}', '\u{2023}', '\u{b7}', '\u{2219}', '\u{25cf}', '\u{25a0}',
    '\u{2043}', '\u{2014}',
];
const INDENT_PT: f32 = 8.0;
const SHORT_LINE: f32 = 0.62;

/// Left edge of the body text block: the leftmost line start.
///
/// Not the modal x0: a page of short list items outnumbers its prose lines, so
/// the mode reports the list indent as the margin and then nothing looks
/// indented — which is how bullets stop rendering.
pub fn margin(lines: &[Line]) -> f32 {
    lines
        .iter()
        .filter(|l| !l.text.trim().is_empty())
        .map(|l| l.x0)
        .fold(f32::INFINITY, f32::min)
}

/// The 90th percentile of line ends: the measure the text is set to.
pub fn right_edge(lines: &[Line]) -> f32 {
    let mut v: Vec<f32> = lines.iter().filter(|l| l.x1 > 0.0).map(|l| l.x1).collect();
    if v.is_empty() {
        return 0.0;
    }
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    v[(v.len() as f32 * 0.9) as usize]
}

/// Indented *and* shorter than the measure. Indent alone is not evidence of a
/// list under justification, where continuation lines start at varied x0.
fn is_indented(l: &Line, margin: f32, right: f32) -> bool {
    if l.x1 > 0.0 && right > 0.0 {
        let width = l.x1 - margin;
        if width >= (right - margin) * SHORT_LINE {
            return false;
        }
    }
    l.x0 - margin >= INDENT_PT
}

/// Strip a list label, returning the item text: bullet glyph, "1.", "(a)", "b)".
pub fn list_body(text: &str) -> Option<String> {
    let t = text.trim();
    let mut cs = t.chars();
    if let Some(first) = cs.next() {
        if BULLETS.contains(&first) {
            return Some(cs.as_str().trim().to_string());
        }
    }
    // An optional opening paren, one or two alphanumerics, then '.' or ')'.
    let rest = t.strip_prefix('(').unwrap_or(t);
    let label_len: usize = rest.chars().take_while(|c| c.is_alphanumeric()).count();
    if label_len == 0 || label_len > 2 {
        return None;
    }
    let after = &rest[rest
        .char_indices()
        .nth(label_len)
        .map(|(i, _)| i)
        .unwrap_or(rest.len())..];
    let close = if t.starts_with('(') {
        ")"
    } else {
        after
            .chars()
            .next()
            .map(|c| if c == '.' { "." } else { ")" })
            .unwrap_or("")
    };
    let tail = after.strip_prefix(close)?;
    if !tail.starts_with(char::is_whitespace) {
        return None;
    }
    let item = tail.trim();
    if item.is_empty() {
        None
    } else {
        Some(item.to_string())
    }
}

/// "H. REDACTIONS APPLIED FOR" — a lettered heading, not a bullet.
fn is_lettered_section(text: &str) -> bool {
    let t = text.trim();
    let mut cs = t.chars();
    let first = match cs.next() {
        Some(c) => c,
        None => return false,
    };
    if !first.is_ascii_uppercase() {
        return false;
    }
    let rest = match cs.next() {
        Some(c) if c == '.' || c == ')' => cs.as_str(),
        _ => return false,
    };
    if !rest.starts_with(char::is_whitespace) {
        return false;
    }
    let body = rest.trim();
    if body.chars().count() > 90 || body.is_empty() {
        return false;
    }
    body.chars()
        .filter(|c| c.is_alphabetic())
        .all(|c| c.is_uppercase())
}

/// True for "(a) ..." / "a) ..." — a sub-item label, unambiguous on its own.
/// Bare "1. Scope" is left alone: that is section numbering in a report.
fn is_lettered_label(text: &str) -> bool {
    let t = text.trim();
    let rest = t.strip_prefix('(').unwrap_or(t);
    let label: String = rest.chars().take_while(|c| c.is_alphanumeric()).collect();
    !label.is_empty() && !label.chars().all(|c| c.is_ascii_digit())
}

const NOTE_ZONE: f32 = 0.75;

/// A horizontal rule: only dashes, em dashes or underscores. Never prose, and
/// never worth carrying into the output as a paragraph.
fn is_rule(text: &str) -> bool {
    let t = text.trim();
    t.chars().count() >= 3
        && t.chars()
            .all(|c| c == '-' || c == '_' || c == '\u{2014}' || c == '\u{2013}')
}

/// "1  Statement of ..." -> ("1", "Statement of ...").
fn split_note(text: &str) -> Option<(String, String)> {
    let t = text.trim();
    let digits: String = t.chars().take_while(|c| c.is_ascii_digit()).collect();
    if digits.is_empty() || digits.len() > 3 {
        return None;
    }
    let rest = &t[digits.len()..];
    if !rest.starts_with(char::is_whitespace) {
        return None;
    }
    let body = rest.trim();
    if body.is_empty() {
        return None;
    }
    Some((digits, body.to_string()))
}

/// Footnotes sit below the body measure *and* are set smaller than it.
///
/// Position alone is not enough: a document whose prose runs to the foot of the
/// page put 20.5% of its text there, and an earlier build discarded all of it.
fn in_note_zone(l: &Line, body: f32) -> bool {
    l.page_height > 0.0 && l.top > l.page_height * NOTE_ZONE && l.size < body * 0.9
}

/// Position test alone, without the size test: used where a line must be kept
/// but must not define the page geometry.
pub fn note_zone(l: &Line) -> bool {
    l.page_height > 0.0 && l.top > l.page_height * NOTE_ZONE
}

/// Re-attach superscript marks to the line they belong to.
///
/// A PDF has no link between a mark and its paragraph — the mark is a separate
/// text object drawn a few points above the baseline. The link is geometric:
/// same page, vertically overlapping, and starting where the host line ends.
///
/// The mark sorts *before* its host in reading order, because it sits higher on
/// the page, so the search runs in both directions.
fn attach_markers(lines: Vec<Line>, body: f32) -> Vec<(Line, Option<String>)> {
    let mut mark = vec![None::<String>; lines.len()];
    let mut consumed = vec![false; lines.len()];
    for i in 0..lines.len() {
        let m = &lines[i];
        let t = m.text.trim();
        let candidate = !t.is_empty()
            && t.len() <= 3
            && t.chars().all(|c| c.is_ascii_digit())
            && m.size < body * 0.85;
        if !candidate {
            continue;
        }
        let host = (0..lines.len())
            .filter(|&j| j != i && !consumed[j])
            .filter(|&j| {
                let h = &lines[j];
                h.page == m.page
                    && h.size >= body * 0.9
                    && (h.top - m.top).abs() <= body * 0.9
                    // Measured from the host's *start*: a base-14 font carries
                    // no /Widths, so x1 can over-report by a glyph, while x0
                    // comes straight from the text matrix and is exact.
                    && m.x0 >= h.x0 + (h.x1 - h.x0) * 0.5
                    && m.x0 <= h.x1 + body
            })
            .min_by(|&a, &b| {
                let da = (lines[a].top - m.top).abs();
                let db = (lines[b].top - m.top).abs();
                da.partial_cmp(&db).unwrap_or(std::cmp::Ordering::Equal)
            });
        if let Some(j) = host {
            mark[j] = Some(t.to_string());
            consumed[i] = true;
        }
    }
    lines
        .into_iter()
        .enumerate()
        .filter(|(i, _)| !consumed[*i])
        .map(|(i, l)| (l, mark[i].clone()))
        .collect()
}

pub fn classify_with(lines: &[Line], segments: &[crate::table::Segment]) -> Doc {
    let body = body_size(lines);

    let mut notes: Vec<(String, String)> = Vec::new();
    let mut kept: Vec<Line> = Vec::new();
    for l in lines {
        let t = l.text.trim();
        if t.is_empty() || is_rule(t) {
            continue;
        }
        if in_note_zone(l, body) {
            if let Some((n, txt)) = split_note(t) {
                notes.push((n, txt));
                continue;
            }
        }
        kept.push(l.clone());
    }

    let content = attach_markers(kept, body);

    // Tables are found from the page's line work and take their text with them,
    // so the text is not also emitted as paragraphs.
    let flat: Vec<Line> = content.iter().map(|(l, _)| l.clone()).collect();
    let (tables, consumed) = crate::table::detect(&flat, segments);
    let mut table_at: Vec<Option<usize>> = vec![None; flat.len()];
    for ti in 0..tables.len() {
        let _ = ti;
    }
    // Map each table to the first line it consumed, so it lands in place.
    {
        let mut seen = 0usize;
        let mut ti = 0usize;
        while ti < tables.len() && seen < consumed.len() {
            if consumed[seen] {
                table_at[seen] = Some(ti);
                ti += 1;
                // advance past this table's own lines
                while seen < consumed.len() && consumed[seen] {
                    seen += 1;
                }
            } else {
                seen += 1;
            }
        }
    }

    let margin = margin(lines);
    let right = right_edge(lines);
    let lists_ok = content.iter().any(|(l, _)| {
        l.text
            .trim()
            .chars()
            .next()
            .map(|c| BULLETS.contains(&c))
            .unwrap_or(false)
    });
    let mut blocks: Vec<Block> = Vec::new();
    let mut seen_numbered = false;

    for (i, (l, mk)) in content.iter().enumerate() {
        if consumed[i] {
            if let Some(ti) = table_at[i] {
                blocks.push(Block {
                    kind: Kind::Table,
                    text: String::new(),
                    level: 0,
                    marker: None,
                    table: Some(tables[ti].clone()),
                    numbered: false,
                });
            }
            continue;
        }
        let t = l.text.trim();
        let nxt = content.get(i + 1).map(|(l, _)| l);
        let prior = if i > 0 { Some(&content[i - 1].0) } else { None };

        if is_heading(l, body) {
            match split_section(t) {
                Some((depth, rest)) => {
                    seen_numbered = true;
                    blocks.push(Block {
                        kind: Kind::Heading,
                        text: rest,
                        level: depth,
                        marker: mk.clone(),
                        table: None,
                        numbered: true,
                    });
                }
                None => {
                    let level = if !seen_numbered && blocks.is_empty() {
                        0
                    } else {
                        1
                    };
                    blocks.push(Block {
                        kind: Kind::Heading,
                        text: t.to_string(),
                        level,
                        marker: mk.clone(),
                        table: None,
                        numbered: false,
                    });
                }
            }
            continue;
        }

        if is_lettered_section(t) {
            blocks.push(Block {
                kind: Kind::Heading,
                text: t.to_string(),
                level: 1,
                marker: mk.clone(),
                table: None,
                numbered: false,
            });
            continue;
        }

        let item = list_body(t);
        let bulleted = t
            .chars()
            .next()
            .map(|c| BULLETS.contains(&c))
            .unwrap_or(false);
        let numbered = item.is_some() && !bulleted && (lists_ok || is_lettered_label(t));
        let neighbour_indented = nxt.map(|n| is_indented(n, margin, right)).unwrap_or(false)
            || prior
                .map(|p| is_indented(p, margin, right))
                .unwrap_or(false);
        if is_indented(l, margin, right) && neighbour_indented {
            let text = item.unwrap_or_else(|| t.to_string());
            blocks.push(Block {
                kind: Kind::ListItem,
                text,
                level: 0,
                marker: mk.clone(),
                table: None,
                numbered: false,
            });
            continue;
        }
        if let Some(text) = item {
            if bulleted || numbered {
                blocks.push(Block {
                    kind: Kind::ListItem,
                    text,
                    level: 0,
                    marker: mk.clone(),
                    table: None,
                    numbered: false,
                });
                continue;
            }
        }
        blocks.push(Block {
            kind: Kind::Body,
            text: t.to_string(),
            level: 0,
            marker: mk.clone(),
            table: None,
            numbered: false,
        });
    }
    Doc {
        blocks,
        notes,
        layout: crate::layout::profile(lines),
    }
}
