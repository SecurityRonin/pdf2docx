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
}

impl Line {
    pub fn new(text: &str, size: f32, x0: f32, x1: f32, top: f32) -> Self {
        Self { text: text.to_string(), size, x0, x1, top, bold: false, page: 0 }
    }
}

#[derive(Debug, Clone)]
pub struct Block {
    pub kind: Kind,
    pub text: String,
    /// 1-based heading depth; 0 means "document title".
    pub level: u8,
}

#[derive(Debug, Default)]
pub struct Doc {
    pub blocks: Vec<Block>,
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

/// The document's body size: the most-used size, measured by characters so one
/// large title cannot win.
pub fn body_size(lines: &[Line]) -> f32 {
    let mut weight: HashMap<u32, usize> = HashMap::new();
    for l in lines {
        *weight.entry((l.size * 10.0).round() as u32).or_default() += l.text.len();
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


const BULLETS: [char; 10] = ['\u{2022}', '\u{25aa}', '\u{25e6}', '\u{2023}', '\u{b7}',
                             '\u{2219}', '\u{25cf}', '\u{25a0}', '\u{2043}', '\u{2014}'];
const INDENT_PT: f32 = 8.0;
const SHORT_LINE: f32 = 0.62;

/// Left edge of the body text block: the leftmost line start.
///
/// Not the modal x0: a page of short list items outnumbers its prose lines, so
/// the mode reports the list indent as the margin and then nothing looks
/// indented — which is how bullets stop rendering.
pub fn margin(lines: &[Line]) -> f32 {
    lines.iter().filter(|l| !l.text.trim().is_empty()).map(|l| l.x0)
        .fold(f32::INFINITY, f32::min)
}

/// The 90th percentile of line ends: the measure the text is set to.
pub fn right_edge(lines: &[Line]) -> f32 {
    let mut v: Vec<f32> = lines.iter().filter(|l| l.x1 > 0.0).map(|l| l.x1).collect();
    if v.is_empty() { return 0.0; }
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
    let after = &rest[rest.char_indices().nth(label_len).map(|(i, _)| i).unwrap_or(rest.len())..];
    let close = if t.starts_with('(') { ")" } else { after.chars().next().map(|c| if c == '.' { "." } else { ")" }).unwrap_or("") };
    let tail = after.strip_prefix(close)?;
    if !tail.starts_with(char::is_whitespace) {
        return None;
    }
    let item = tail.trim();
    if item.is_empty() { None } else { Some(item.to_string()) }
}

/// "H. REDACTIONS APPLIED FOR" — a lettered heading, not a bullet.
fn is_lettered_section(text: &str) -> bool {
    let t = text.trim();
    let mut cs = t.chars();
    let first = match cs.next() { Some(c) => c, None => return false };
    if !first.is_ascii_uppercase() { return false; }
    let rest = match cs.next() {
        Some(c) if c == '.' || c == ')' => cs.as_str(),
        _ => return false,
    };
    if !rest.starts_with(char::is_whitespace) { return false; }
    let body = rest.trim();
    if body.chars().count() > 90 || body.is_empty() { return false; }
    body.chars().filter(|c| c.is_alphabetic()).all(|c| c.is_uppercase())
}

/// True for "(a) ..." / "a) ..." — a sub-item label, unambiguous on its own.
/// Bare "1. Scope" is left alone: that is section numbering in a report.
fn is_lettered_label(text: &str) -> bool {
    let t = text.trim();
    let rest = t.strip_prefix('(').unwrap_or(t);
    let label: String = rest.chars().take_while(|c| c.is_alphanumeric()).collect();
    !label.is_empty() && !label.chars().all(|c| c.is_ascii_digit())
}

pub fn classify(lines: &[Line]) -> Doc {
    let body = body_size(lines);
    let margin = margin(lines);
    let right = right_edge(lines);
    let lists_ok = lines.iter().any(|l| l.text.trim().chars().next()
        .map(|c| BULLETS.contains(&c)).unwrap_or(false));
    let mut blocks: Vec<Block> = Vec::new();
    let mut seen_numbered = false;
    let content: Vec<&Line> = lines.iter().filter(|l| !l.text.trim().is_empty()).collect();

    for (i, l) in content.iter().enumerate() {
        let t = l.text.trim();
        let nxt = content.get(i + 1).copied();

        if is_heading(l, body) {
            match split_section(t) {
                Some((depth, rest)) => {
                    seen_numbered = true;
                    blocks.push(Block { kind: Kind::Heading, text: rest, level: depth });
                }
                None => {
                    let level = if !seen_numbered && blocks.is_empty() { 0 } else { 1 };
                    blocks.push(Block { kind: Kind::Heading, text: t.to_string(), level });
                }
            }
            continue;
        }

        if is_lettered_section(t) {
            blocks.push(Block { kind: Kind::Heading, text: t.to_string(), level: 1 });
            continue;
        }

        let item = list_body(t);
        let bulleted = t.chars().next().map(|c| BULLETS.contains(&c)).unwrap_or(false);
        let numbered = item.is_some() && !bulleted && (lists_ok || is_lettered_label(t));
        let neighbour_indented = nxt.map(|n| is_indented(n, margin, right)).unwrap_or(false)
            || (i > 0 && is_indented(content[i - 1], margin, right));
        if is_indented(l, margin, right) && neighbour_indented {
            let text = item.unwrap_or_else(|| t.to_string());
            blocks.push(Block { kind: Kind::ListItem, text, level: 0 });
            continue;
        }
        if let Some(text) = item {
            if bulleted || numbered {
                blocks.push(Block { kind: Kind::ListItem, text, level: 0 });
                continue;
            }
        }
        blocks.push(Block { kind: Kind::Body, text: t.to_string(), level: 0 });
    }
    Doc { blocks }
}
