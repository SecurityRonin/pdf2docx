//! Convert a PDF into a DOCX that carries real Word structure.
pub mod extract;
pub mod structure;
pub mod writer;

use std::path::Path;

/// Convert `src` (PDF) to `dst` (DOCX).
pub fn convert(src: &Path, dst: &Path) -> Result<(), String> {
    let lines = extract::extract(src)?;
    let doc = structure::classify(&lines);
    writer::write(&doc, dst)
}
