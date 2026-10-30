//! Read a PDF's text lines with the attributes structure depends on.
//!
//! `lopdf` is an object layer, not a text extractor: it gives content streams and
//! font dictionaries, and this module walks the text operators (`Tf`, `Tm`, `Td`,
//! `Tj`, `TJ`) to recover lines with a size, an x-range and a vertical position.
//!
//! Scope, stated rather than implied: each `BT`..`ET` block becomes one line, and
//! a glyph's advance comes from the font's `/Widths` (or `/W` for CID fonts).
//! Text drawn with an unusual matrix, or a font with neither widths nor a
//! ToUnicode map, is approximated rather than rejected.
use std::collections::HashMap;
use std::path::Path;

use lopdf::content::Content;
use lopdf::{Document, Object, ObjectId};

use crate::structure::Line;

#[derive(Debug, Default, Clone)]
struct FontInfo {
    name: String,
    /// Advance width per glyph code, in 1/1000 em, indexed from `first_char`.
    widths: Vec<f32>,
    first_char: u32,
    to_unicode: HashMap<u32, String>,
    /// CID fonts address glyphs directly; the code is not a byte.
    two_byte: bool,
}

impl FontInfo {
    fn width_of(&self, code: u32) -> f32 {
        let i = code.saturating_sub(self.first_char) as usize;
        self.widths
            .get(i)
            .copied()
            .filter(|w| *w > 0.0)
            .unwrap_or(500.0)
    }

    fn char_of(&self, code: u32) -> Option<String> {
        if let Some(s) = self.to_unicode.get(&code) {
            return Some(s.clone());
        }
        char::from_u32(code).map(|c| c.to_string())
    }
}

fn as_dict<'a>(doc: &'a Document, o: &'a Object) -> Option<&'a lopdf::Dictionary> {
    match o {
        Object::Dictionary(d) => Some(d),
        Object::Reference(id) => match doc.get_object(*id) {
            Ok(Object::Dictionary(d)) => Some(d),
            _ => None,
        },
        _ => None,
    }
}

fn parse_hex(s: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    let mut hi: Option<u8> = None;
    for &b in s {
        let v = match b {
            b'0'..=b'9' => b - b'0',
            b'a'..=b'f' => b - b'a' + 10,
            b'A'..=b'F' => b - b'A' + 10,
            _ => continue,
        };
        match hi.take() {
            None => hi = Some(v),
            Some(h) => out.push((h << 4) | v),
        }
    }
    out
}

/// Parse the subset of a ToUnicode CMap that matters: bfchar and bfrange.
fn parse_cmap(data: &[u8], two_byte: bool) -> HashMap<u32, String> {
    let text = String::from_utf8_lossy(data);
    let mut map = HashMap::new();
    let mut push = |code: u32, s: &str| {
        map.insert(code, s.to_string());
    };

    for block in text.split("beginbfchar").skip(1) {
        for line in block.split("endbfchar").next().unwrap_or("").lines() {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 2 && parts[0].starts_with('<') {
                let src = parse_hex(parts[0].trim_matches(|c| c == '<' || c == '>').as_bytes());
                let dst = parse_hex(parts[1].trim_matches(|c| c == '<' || c == '>').as_bytes());
                let code = if two_byte {
                    src.iter().fold(0u32, |a, b| (a << 8) | *b as u32)
                } else {
                    src.first().copied().unwrap_or(0) as u32
                };
                let s: String = dst
                    .chunks(2)
                    .filter(|c| c.len() == 2)
                    .filter_map(|c| char::from_u32(((c[0] as u32) << 8) | c[1] as u32))
                    .collect();
                push(code, &s);
            }
        }
    }

    for block in text.split("beginbfrange").skip(1) {
        for line in block.split("endbfrange").next().unwrap_or("").lines() {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 3 && parts[0].starts_with('<') {
                let lo = parse_hex(parts[0].trim_matches(|c| c == '<' || c == '>').as_bytes());
                let hi = parse_hex(parts[1].trim_matches(|c| c == '<' || c == '>').as_bytes());
                let lo = lo.iter().fold(0u32, |a, b| (a << 8) | *b as u32);
                let hi = hi.iter().fold(0u32, |a, b| (a << 8) | *b as u32);
                let dst = parse_hex(parts[2].trim_matches(|c| c == '<' || c == '>').as_bytes());
                let base = dst.iter().fold(0u32, |a, b| (a << 8) | *b as u32);
                for i in 0..=(hi.saturating_sub(lo)).min(65_535) {
                    if let Some(c) = char::from_u32(base + i) {
                        push(lo + i, &c.to_string());
                    }
                }
            }
        }
    }
    map
}

fn font_info(doc: &Document, resources: &lopdf::Dictionary, name: &str) -> FontInfo {
    let mut info = FontInfo {
        name: name.to_string(),
        ..Default::default()
    };
    let fonts = resources.get(b"Font").ok().and_then(|o| as_dict(doc, o));
    let Some(fonts) = fonts else { return info };
    let Some(font) = fonts
        .get(name.as_bytes())
        .ok()
        .and_then(|o| as_dict(doc, o))
    else {
        return info;
    };

    info.name = font
        .get(b"BaseFont")
        .ok()
        .and_then(|o| o.as_name_str().ok())
        .unwrap_or("")
        .to_string();

    let subtype = font
        .get(b"Subtype")
        .ok()
        .and_then(|o| o.as_name_str().ok())
        .unwrap_or("");
    info.two_byte = subtype == "Type0";

    if let Ok(w) = font.get(b"Widths") {
        if let Ok(arr) = w.as_array() {
            info.widths = arr
                .iter()
                .map(|o| {
                    o.as_float()
                        .or_else(|_| o.as_i64().map(|i| i as f32))
                        .unwrap_or(500.0)
                })
                .collect();
        }
    }
    info.first_char = font
        .get(b"FirstChar")
        .ok()
        .and_then(|o| o.as_i64().ok())
        .unwrap_or(0) as u32;

    if let Ok(o) = font.get(b"ToUnicode") {
        let obj = match o {
            Object::Reference(id) => doc.get_object(*id).ok(),
            other => Some(other),
        };
        if let Some(Object::Stream(s)) = obj {
            if let Ok(data) = s.decompressed_content() {
                info.to_unicode = parse_cmap(&data, info.two_byte);
            }
        }
    }
    info
}

fn media_size(doc: &Document, page_id: ObjectId) -> (f32, f32) {
    let dict = doc.get_dictionary(page_id).ok();
    let mb = dict.and_then(|d| d.get(b"MediaBox").ok());
    if let Some(mb) = mb {
        let arr = match mb {
            Object::Array(a) => Some(a),
            Object::Reference(id) => match doc.get_object(*id) {
                Ok(Object::Array(a)) => Some(a),
                _ => None,
            },
            _ => None,
        };
        if let Some(arr) = arr {
            let num = |i: usize| arr.get(i).and_then(|o| o.as_float().ok());
            if let (Some(x0), Some(y0), Some(x1), Some(y1)) = (num(0), num(1), num(2), num(3)) {
                // A MediaBox is not required to start at the origin.
                return ((x1 - x0).abs(), (y1 - y0).abs());
            }
        }
    }
    (595.28, 841.89)
}

/// Extract every text line, in reading order.
pub fn extract(path: &Path) -> Result<Vec<Line>, String> {
    let doc = Document::load(path).map_err(|e| format!("cannot open {}: {e}", path.display()))?;
    let mut out: Vec<Line> = Vec::new();

    for (pno, page_id) in doc.get_pages() {
        let (width, height) = media_size(&doc, page_id);
        let content = match doc.get_page_content(page_id) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let ops = match Content::decode(&content) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let resources = doc
            .get_dictionary(page_id)
            .ok()
            .and_then(|d| d.get(b"Resources").ok())
            .and_then(|o| as_dict(&doc, o))
            .cloned()
            .unwrap_or_default();

        let mut fonts: HashMap<String, FontInfo> = HashMap::new();
        let mut font = FontInfo::default();
        let mut size = 0.0f32;
        let mut leading = 0.0f32;
        // The current transformation matrix [a b c d e f]. A page is routinely
        // wrapped in `q cm ... Q` to place its text block, so raw Tm values are
        // in that transformed space, not page space.
        let mut ctm: [f32; 6] = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0];
        let mut ctm_stack: Vec<[f32; 6]> = Vec::new();
        let mut word_spacing = 0.0f32;
        // A Cell so the flush closure can read and reset it while the loop
        // also updates it; a plain binding would be a borrow conflict.
        let line_stretch = std::cell::Cell::new(0.0f32);
        let mut x = 0.0f32;
        let mut y = 0.0f32;
        let mut text = String::new();
        let mut x_start = 0.0f32;
        let mut started = false;

        let flush = |text: &mut String,
                     started: &mut bool,
                     out: &mut Vec<Line>,
                     x0: f32,
                     x1: f32,
                     y: f32,
                     size: f32,
                     font_name: &str| {
            let t = text.trim();
            let stretch = line_stretch.get();
            line_stretch.set(0.0);
            if *started && !t.is_empty() {
                out.push(Line {
                    text: t.to_string(),
                    size,
                    x0,
                    x1,
                    top: height - y,
                    bold: font_name.to_lowercase().contains("bold"),
                    page: (pno - 1) as usize,
                    page_height: height,
                    page_width: width,
                    word_spacing: stretch,
                });
            }
            text.clear();
            // `started` means "inside a text block", not "has pending text":
            // clearing it here dropped every line after the first `T*`, because
            // only `BT` ever set it again.
        };

        for op in ops.operations {
            match op.operator.as_str() {
                "q" => ctm_stack.push(ctm),
                "Q" => {
                    if let Some(prev) = ctm_stack.pop() {
                        ctm = prev;
                    }
                }
                "cm" => {
                    if op.operands.len() >= 6 {
                        let m: Vec<f32> = op
                            .operands
                            .iter()
                            .map(|o| o.as_float().unwrap_or(0.0))
                            .collect();
                        if m.len() == 6 {
                            ctm = [
                                m[0] * ctm[0] + m[1] * ctm[2],
                                m[0] * ctm[1] + m[1] * ctm[3],
                                m[2] * ctm[0] + m[3] * ctm[2],
                                m[2] * ctm[1] + m[3] * ctm[3],
                                m[4] * ctm[0] + m[5] * ctm[2] + ctm[4],
                                m[4] * ctm[1] + m[5] * ctm[3] + ctm[5],
                            ];
                        }
                    }
                }
                "BT" => {
                    started = true;
                    text.clear();
                }
                "ET" => {
                    flush(
                        &mut text,
                        &mut started,
                        &mut out,
                        x_start,
                        x,
                        y,
                        size,
                        &font.name,
                    );
                }
                "Tf" => {
                    if let (Some(Object::Name(n)), Some(sz)) =
                        (op.operands.first(), op.operands.get(1))
                    {
                        let name = String::from_utf8_lossy(n).to_string();
                        size = sz.as_float().unwrap_or(0.0);
                        let info = fonts
                            .entry(name.clone())
                            .or_insert_with(|| font_info(&doc, &resources, &name))
                            .clone();
                        font = info;
                    }
                }
                "Tm" => {
                    if op.operands.len() >= 6 {
                        let (tx, ty) = (
                            op.operands[4].as_float().unwrap_or(0.0),
                            op.operands[5].as_float().unwrap_or(0.0),
                        );
                        // Only the translation is applied. A rotated or skewed
                        // text matrix is left approximated, as documented.
                        x = tx * ctm[0] + ty * ctm[2] + ctm[4];
                        y = tx * ctm[1] + ty * ctm[3] + ctm[5];
                        x_start = x;
                    }
                }
                // A vertical move starts a new line even inside one BT..ET
                // block. Flushing on it is what keeps a paragraph from being
                // read as a single line of several hundred words.
                "Td" | "TD" => {
                    if op.operands.len() >= 2 {
                        let dx = op.operands[0].as_float().unwrap_or(0.0);
                        let dy = op.operands[1].as_float().unwrap_or(0.0);
                        if dy != 0.0 {
                            flush(
                                &mut text,
                                &mut started,
                                &mut out,
                                x_start,
                                x,
                                y,
                                size,
                                &font.name,
                            );
                        }
                        if op.operator == "TD" {
                            leading = -dy;
                        }
                        x += dx;
                        y += dy;
                        if dy != 0.0 {
                            x_start = x;
                        }
                    }
                }
                "Tw" => {
                    if let Some(v) = op.operands.first().and_then(|o| o.as_float().ok()) {
                        word_spacing = v;
                    }
                }
                "TL" => {
                    if let Some(v) = op.operands.first().and_then(|o| o.as_float().ok()) {
                        leading = v;
                    }
                }
                // T* = "next line": the leading move, with no text of its own.
                "T*" => {
                    flush(
                        &mut text,
                        &mut started,
                        &mut out,
                        x_start,
                        x,
                        y,
                        size,
                        &font.name,
                    );
                    y -= leading;
                    x = x_start;
                }
                // `'` and `"` move to the next line *and* show text; treating
                // them as plain Tj joins consecutive lines into one.
                "'" | "\"" => {
                    flush(
                        &mut text,
                        &mut started,
                        &mut out,
                        x_start,
                        x,
                        y,
                        size,
                        &font.name,
                    );
                    y -= leading;
                    x = x_start;
                    if let Some(Object::String(s, _)) = op.operands.last() {
                        append(s, &font, size, &mut text, &mut x);
                    }
                }
                "Tj" => {
                    if let Some(Object::String(s, _)) = op.operands.last() {
                        line_stretch.set(line_stretch.get().max(word_spacing.abs()));
                        append(s, &font, size, &mut text, &mut x);
                    }
                }
                "TJ" => {
                    if let Some(Object::Array(items)) = op.operands.first() {
                        for it in items {
                            match it {
                                Object::String(s, _) => {
                                    line_stretch.set(line_stretch.get().max(word_spacing.abs()));
                                    append(s, &font, size, &mut text, &mut x)
                                }
                                Object::Integer(n) => {
                                    // A negative adjustment moves the pen forward.
                                    x -= *n as f32 / 1000.0 * size;
                                }
                                Object::Real(r) => x -= *r / 1000.0 * size,
                                _ => {}
                            }
                        }
                    }
                }
                _ => {}
            }
        }
        flush(
            &mut text,
            &mut started,
            &mut out,
            x_start,
            x,
            y,
            size,
            &font.name,
        );
    }

    out.sort_by(|a, b| {
        a.page
            .cmp(&b.page)
            .then(
                a.top
                    .partial_cmp(&b.top)
                    .unwrap_or(std::cmp::Ordering::Equal),
            )
            .then(a.x0.partial_cmp(&b.x0).unwrap_or(std::cmp::Ordering::Equal))
    });
    Ok(out)
}

fn append(s: &[u8], font: &FontInfo, size: f32, text: &mut String, x: &mut f32) {
    if font.two_byte {
        for c in s.chunks(2) {
            let code = if c.len() == 2 {
                ((c[0] as u32) << 8) | c[1] as u32
            } else {
                c[0] as u32
            };
            if let Some(ch) = font.char_of(code) {
                text.push_str(&ch);
            }
            *x += font.width_of(code) / 1000.0 * size;
        }
    } else {
        for &b in s {
            let code = b as u32;
            if let Some(ch) = font.char_of(code) {
                text.push_str(&ch);
            }
            *x += font.width_of(code) / 1000.0 * size;
        }
    }
}

/// Every straight line the page draws, in PDF coordinates.
///
/// Tables are ruled, and the rules are path operators rather than text. Only
/// axis-aligned segments survive: curves and rotated rules are ignored rather
/// than approximated, because a misplaced cell boundary is worse than none.
pub fn segments(path: &Path) -> Result<Vec<crate::table::Segment>, String> {
    let doc = Document::load(path).map_err(|e| format!("cannot open {}: {e}", path.display()))?;
    let mut out: Vec<crate::table::Segment> = Vec::new();

    for (pno, page_id) in doc.get_pages() {
        let (_, height) = media_size(&doc, page_id);
        let content = match doc.get_page_content(page_id) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let ops = match Content::decode(&content) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let mut pending: Vec<crate::table::Segment> = Vec::new();
        let mut cur = (0.0f32, 0.0f32);
        let mut start = (0.0f32, 0.0f32);
        let commit = |pending: &mut Vec<crate::table::Segment>,
                      out: &mut Vec<crate::table::Segment>| {
            out.append(pending);
        };
        let seg = |a: (f32, f32), b: (f32, f32)| crate::table::Segment {
            x0: a.0,
            y0: a.1,
            x1: b.0,
            y1: b.1,
            page: (pno - 1) as usize,
            page_height: height,
        };

        for op in &ops.operations {
            match op.operator.as_str() {
                "m" => {
                    if op.operands.len() >= 2 {
                        cur = (
                            op.operands[0].as_float().unwrap_or(0.0),
                            op.operands[1].as_float().unwrap_or(0.0),
                        );
                        start = cur;
                    }
                }
                "l" => {
                    if op.operands.len() >= 2 {
                        let p = (
                            op.operands[0].as_float().unwrap_or(0.0),
                            op.operands[1].as_float().unwrap_or(0.0),
                        );
                        pending.push(seg(cur, p));
                        cur = p;
                    }
                }
                "re" => {
                    if op.operands.len() >= 4 {
                        let x = op.operands[0].as_float().unwrap_or(0.0);
                        let y = op.operands[1].as_float().unwrap_or(0.0);
                        let w = op.operands[2].as_float().unwrap_or(0.0);
                        let h = op.operands[3].as_float().unwrap_or(0.0);
                        let (a, b, c, d) = (x, y, x + w, y + h);
                        pending.push(seg((a, b), (c, b)));
                        pending.push(seg((c, b), (c, d)));
                        pending.push(seg((c, d), (a, d)));
                        pending.push(seg((a, d), (a, b)));
                        cur = (x, y);
                        start = cur;
                    }
                }
                "h" => {
                    pending.push(seg(cur, start));
                    cur = start;
                }
                "S" | "s" | "f" | "F" | "f*" | "B" | "B*" | "b" | "b*" => {
                    commit(&mut pending, &mut out);
                    pending.clear();
                }
                "n" => pending.clear(),
                _ => {}
            }
        }
    }
    Ok(out)
}
