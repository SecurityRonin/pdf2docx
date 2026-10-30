//! Convert a PDF into a DOCX that carries real Word structure.
pub mod extract;
pub mod layout;
pub mod structure;
pub mod table;
pub mod writer;

use std::path::Path;

/// Convert `src` (PDF) to `dst` (DOCX).
pub fn convert(src: &Path, dst: &Path) -> Result<(), String> {
    let lines = extract::extract(src)?;
    let segments = extract::segments(src)?;
    let doc = structure::classify_with(&lines, &segments);
    writer::write(&doc, dst)
}
