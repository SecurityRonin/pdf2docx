//! The page the document was set on.
//!
//! A converter that hard-codes A4 and 2 cm margins silently reflows every
//! Letter document it is given: the page is a different size, so every line
//! breaks somewhere else. The profile is measured from the source instead.
use crate::structure::{body_size, note_zone};

/// Page geometry in PDF points (1/72 inch).
#[derive(Debug, Clone, Copy)]
pub struct Profile {
    pub page_width: f32,
    pub page_height: f32,
    pub margin_left: f32,
    pub margin_right: f32,
    pub margin_top: f32,
    pub margin_bottom: f32,
    pub body_size: f32,
    /// Baseline-to-baseline distance of body text.
    pub line_pitch: f32,
    /// True when the source sets lines flush to the right measure.
    pub justified: bool,
}

impl Default for Profile {
    fn default() -> Self {
        Self {
            page_width: 595.28,
            page_height: 841.89,
            margin_left: 56.7,
            margin_right: 56.7,
            margin_top: 56.7,
            margin_bottom: 56.7,
            body_size: 11.0,
            line_pitch: 13.2,
            justified: false,
        }
    }
}

/// No margin is inferred below this: a heading overhanging into the margin
/// would otherwise collapse the page geometry to nothing.
const FLOOR: f32 = 18.0;
/// How close a line end must be to the measure to count as flush.
const JUSTIFY_TOL: f32 = 2.0;

fn percentile(mut v: Vec<f32>, p: f32) -> f32 {
    if v.is_empty() {
        return 0.0;
    }
    v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    v[((v.len() as f32 * p) as usize).min(v.len() - 1)]
}

/// Measure the page from the lines the extractor produced.
pub fn profile(lines: &[Line]) -> Profile {
    let mut p = Profile::default();
    // The most common page size wins: a stray cover page should not set the
    // geometry for the document.
    let mut sizes: std::collections::HashMap<(u32, u32), usize> = std::collections::HashMap::new();
    for l in lines
        .iter()
        .filter(|l| l.page_width > 0.0 && l.page_height > 0.0)
    {
        *sizes
            .entry(((l.page_width * 10.0) as u32, (l.page_height * 10.0) as u32))
            .or_default() += 1;
    }
    if let Some(((w, h), _)) = sizes.into_iter().max_by_key(|(_, n)| *n) {
        p.page_width = w as f32 / 10.0;
        p.page_height = h as f32 / 10.0;
    }

    // Margins are measured from body text only. Footnote text sits inside the
    // bottom margin by definition and would otherwise be taken as the edge.
    let body: Vec<&Line> = lines
        .iter()
        .filter(|l| !l.text.trim().is_empty())
        .filter(|l| l.page_height <= 0.0 || !note_zone(l))
        .collect();
    let usable: Vec<&Line> = if body.is_empty() {
        lines.iter().collect()
    } else {
        body
    };
    if usable.is_empty() {
        return p;
    }

    p.body_size = body_size(lines);
    p.margin_left = usable
        .iter()
        .map(|l| l.x0)
        .fold(f32::INFINITY, f32::min)
        .max(FLOOR);
    let edge = percentile(
        usable.iter().filter(|l| l.x1 > 0.0).map(|l| l.x1).collect(),
        0.9,
    );
    let right_gap = p.page_width - edge;
    // Likewise on the right: only trust the gap if the text reaches past the
    // middle of the page. A page of short lines is ragged, not narrow-margined,
    // and mirroring the left margin is the better guess when the measure is
    // unknown.
    p.margin_right = if edge > p.page_width * 0.5 && right_gap >= FLOOR {
        right_gap
    } else {
        p.margin_left
    };
    let top = usable.iter().map(|l| l.top).fold(f32::INFINITY, f32::min);
    if top.is_finite() {
        p.margin_top = top.max(FLOOR);
    }
    // A margin is a gap the text is not allowed into, so it can only be
    // measured where text actually runs to the edge. Text that stops halfway
    // down the page leaves whitespace, not a margin; reading that gap as one
    // shrinks the text area and pushes the document onto extra pages.
    let bottom = usable.iter().map(|l| l.top + l.size).fold(0.0f32, f32::max);
    let bottom_gap = p.page_height - bottom;
    if bottom > p.page_height * 0.6 && bottom_gap >= FLOOR {
        p.margin_bottom = bottom_gap;
    } else {
        p.margin_bottom = FLOOR;
    }

    // Leading: the median step between consecutive baselines on one page.
    let mut steps: Vec<f32> = Vec::new();
    for pair in usable.windows(2) {
        if pair[0].page == pair[1].page {
            let d = pair[1].top - pair[0].top;
            if d > pair[1].size * 0.8 && d < pair[1].size * 4.0 {
                steps.push(d);
            }
        }
    }
    let step = percentile(steps, 0.5);
    if step > 0.0 {
        p.line_pitch = step;
    }

    // Justification is a property of the *set* of lines: a justified block ends
    // every line but the last of each paragraph on the same measure, so most
    // lines share a right edge. A ragged block has no shared edge to find.
    if usable.len() >= 3 {
        // Direct evidence first: justified text is stretched with `Tw`, so a
        // run of non-zero word spacing on most lines is the fact itself rather
        // than an inference from positions. These are also the only documents
        // where geometry is trustworthy — a base-14 font carries no /Widths,
        // so `x1` is an estimate there and cannot decide flushness.
        let stretched = usable
            .iter()
            .filter(|l| l.word_spacing.abs() > 0.01)
            .count();
        p.justified = if stretched > 0 {
            stretched * 2 >= usable.len()
        } else {
            let flush = usable
                .iter()
                .filter(|l| (l.x1 - edge).abs() <= JUSTIFY_TOL)
                .count();
            flush * 5 >= usable.len() * 3
        };
    }
    p
}

use crate::structure::Line;
