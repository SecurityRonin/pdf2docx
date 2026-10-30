//! Ruled tables, recovered from the PDF's own line work.
//!
//! A table in a PDF is geometry, not structure: there is no table object, only
//! rules drawn at coordinates and text placed between them. Detection rebuilds
//! the grid from the rules and then reads each cell by position.
//!
//! Only *ruled* tables are recognised. A table whose cells are separated by
//! whitespace alone has no line work to find and comes through as paragraphs.
/// A straight segment of drawn line work, in PDF coordinates (y up).
#[derive(Debug, Clone, Copy)]
pub struct Segment {
    pub x0: f32,
    pub y0: f32,
    pub x1: f32,
    pub y1: f32,
    pub page: usize,
    pub page_height: f32,
}

#[derive(Debug, Clone)]
pub struct Table {
    pub rows: usize,
    pub cols: usize,
    pub grid: Vec<Vec<String>>,
}

impl Table {
    fn new(rows: usize, cols: usize) -> Self {
        Self {
            rows,
            cols,
            grid: vec![vec![String::new(); cols]; rows],
        }
    }
}

/// Tolerance for two coordinates to be the same rule, and for two rules to meet.
const SAME: f32 = 3.0;
const JOIN: f32 = 3.0;

fn is_horizontal(s: &Segment) -> bool {
    (s.y1 - s.y0).abs() <= 0.5 && (s.x1 - s.x0).abs() > 1.0
}

fn is_vertical(s: &Segment) -> bool {
    (s.x1 - s.x0).abs() <= 0.5 && (s.y1 - s.y0).abs() > 1.0
}

fn bbox(s: &Segment) -> (f32, f32, f32, f32) {
    (
        s.x0.min(s.x1),
        s.y0.min(s.y1),
        s.x0.max(s.x1),
        s.y0.max(s.y1),
    )
}

fn touches(a: &Segment, b: &Segment) -> bool {
    let (ax0, ay0, ax1, ay1) = bbox(a);
    let (bx0, by0, bx1, by1) = bbox(b);
    ax0 - JOIN <= bx1 && bx0 - JOIN <= ax1 && ay0 - JOIN <= by1 && by0 - JOIN <= ay1
}

/// Merge coordinates that are the same rule drawn in pieces.
fn cluster(mut v: Vec<f32>) -> Vec<f32> {
    v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let mut out: Vec<f32> = Vec::new();
    for x in v {
        match out.last_mut() {
            Some(last) if (x - *last).abs() <= SAME => *last = (*last + x) / 2.0,
            _ => out.push(x),
        }
    }
    out
}

/// Connected groups of line work: one group is one table.
fn components(segments: &[Segment]) -> Vec<Vec<usize>> {
    let n = segments.len();
    let mut parent: Vec<usize> = (0..n).collect();
    fn find(p: &mut Vec<usize>, i: usize) -> usize {
        if p[i] != i {
            let r = find(p, p[i]);
            p[i] = r;
        }
        p[i]
    }
    for i in 0..n {
        for j in (i + 1)..n {
            if segments[i].page == segments[j].page && touches(&segments[i], &segments[j]) {
                let (a, b) = (find(&mut parent, i), find(&mut parent, j));
                parent[a] = b;
            }
        }
    }
    let mut groups: std::collections::HashMap<usize, Vec<usize>> = std::collections::HashMap::new();
    for i in 0..n {
        let r = find(&mut parent, i);
        groups.entry(r).or_default().push(i);
    }
    groups.into_values().collect()
}

/// Rebuild a grid from one component, or nothing if it does not enclose cells.
fn grid_of(group: &[&Segment]) -> Option<(Vec<f32>, Vec<f32>)> {
    let xs = cluster(
        group
            .iter()
            .filter(|s| is_vertical(s))
            .map(|s| s.x0)
            .collect(),
    );
    let ys = cluster(
        group
            .iter()
            .filter(|s| is_horizontal(s))
            .map(|s| s.y0)
            .collect(),
    );
    if xs.len() < 2 || ys.len() < 2 {
        return None;
    }
    Some((xs, ys))
}

/// Detect every ruled table and fill it with the text that falls inside.
///
/// Returns the tables and the indices of the lines they consumed, so the caller
/// can place a table where its first line was instead of appending it.
pub fn detect(lines: &[crate::structure::Line], segments: &[Segment]) -> (Vec<Table>, Vec<bool>) {
    let mut tables = Vec::new();
    let mut consumed = vec![false; lines.len()];
    if segments.is_empty() {
        return (tables, consumed);
    }

    for group in components(segments) {
        let group: Vec<&Segment> = group.iter().map(|i| &segments[*i]).collect();
        let Some((xs, ys)) = grid_of(&group) else {
            continue;
        };
        let page = group[0].page;
        let height = group[0].page_height;
        let rows = ys.len() - 1;
        let cols = xs.len() - 1;
        let mut table = Table::new(rows, cols);
        let (bx0, by0, bx1, by1) = group.iter().fold(
            (
                f32::INFINITY,
                f32::INFINITY,
                f32::NEG_INFINITY,
                f32::NEG_INFINITY,
            ),
            |acc, s| {
                let (a, b, c, d) = bbox(s);
                (acc.0.min(a), acc.1.min(b), acc.2.max(c), acc.3.max(d))
            },
        );

        for (i, l) in lines.iter().enumerate() {
            if l.page != page {
                continue;
            }
            let cx = (l.x0 + l.x1) / 2.0;
            let cy = height - l.top - l.size / 2.0;
            if cx < bx0 || cx > bx1 || cy < by0 || cy > by1 {
                continue;
            }
            // ys ascend in PDF space, so the topmost row is the last interval.
            let col = xs.iter().position(|x| cx < *x).map(|i| i.saturating_sub(1));
            let rowi = ys.iter().position(|y| cy < *y).map(|i| i.saturating_sub(1));
            if let (Some(c), Some(r)) = (col, rowi) {
                if r < rows && c < cols {
                    let cell = &mut table.grid[rows - 1 - r][c];
                    if !cell.is_empty() {
                        cell.push(' ');
                    }
                    cell.push_str(l.text.trim());
                    consumed[i] = true;
                }
            }
        }
        // A grid whose rules enclose no text is a border or a chart, not a table.
        if table.grid.iter().flatten().any(|c| !c.is_empty()) {
            tables.push(table);
        }
    }
    (tables, consumed)
}
