//! Emit a DOCX that carries real Word structure.
//!
//! Structure comes from styles and numbering definitions, never from a run that
//! merely looks bold: a heading is `Heading N`, so Word's navigation pane, a
//! generated table of contents and anything that walks the outline can see it.
use std::io::Write;
use std::path::Path;

use crate::structure::{Block, Doc, Kind};

fn esc(s: &str) -> String {
    let mut o = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => o.push_str("&amp;"),
            '<' => o.push_str("&lt;"),
            '>' => o.push_str("&gt;"),
            '"' => o.push_str("&quot;"),
            '\'' => o.push_str("&apos;"),
            _ => o.push(c),
        }
    }
    o
}

fn run(text: &str) -> String {
    format!(r#"<w:r><w:t xml:space="preserve">{}</w:t></w:r>"#, esc(text))
}

fn paragraph(b: &Block, note: Option<usize>) -> String {
    let mut body = run(&b.text);
    if let Some(id) = note {
        // A reference run, not the literal digit: Word numbers the mark and
        // renumbers it when notes are added, which a typed character cannot do.
        body.push_str(&format!(
            r#"<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="{id}"/></w:r>"#
        ));
    }
    match b.kind {
        Kind::Heading if b.level == 0 => {
            format!(r#"<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>{body}</w:p>"#)
        }
        Kind::Heading => {
            let n = b.level.clamp(1, 6);
            format!(r#"<w:p><w:pPr><w:pStyle w:val="Heading{n}"/></w:pPr>{body}</w:p>"#)
        }
        Kind::ListItem => format!(
            r#"<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>{body}</w:p>"#
        ),
        Kind::Body => format!("<w:p>{body}</w:p>"),
    }
}

const CONTENT_TYPES: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
</Types>"#;

const ROOT_RELS: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"#;

const DOC_RELS: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>
</Relationships>"#;

fn styles_xml() -> String {
    let mut s = String::from(
        r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/></w:pPr></w:style>"#,
    );
    // Title: deliberately not numbered, so the first real section is "1".
    s.push_str(r#"<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="56"/></w:rPr></w:style>"#);
    // Half-points, descending, all below the Title's 56 (28pt). An earlier
    // formula produced 72 for Heading 1, so a section rendered larger than the
    // document title — which the renderer showed and the XML could not.
    const SIZES: [u32; 6] = [40, 32, 28, 24, 22, 22];
    for n in 1..=6u32 {
        s.push_str(&format!(
            r#"<w:style w:type="paragraph" w:styleId="Heading{n}"><w:name w:val="heading {n}"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="{}"/></w:pPr><w:rPr><w:b/><w:sz w:val="{}"/></w:rPr></w:style>"#,
            n - 1,
            SIZES[(n - 1) as usize]
        ));
    }
    s.push_str(r#"<w:style w:type="paragraph" w:styleId="FootnoteText"><w:name w:val="footnote text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="18"/></w:rPr></w:style>"#);
    s.push_str(r#"<w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>"#);
    s.push_str("</w:styles>");
    s
}

fn numbering_xml() -> &'static str {
    r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="&#8226;"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>"#
}

/// Footnote ids per block, and the notes in the order Word must show them.
///
/// Ids 0 and 1 are reserved for the separator rules, so real notes start at 2.
fn footnote_ids(doc: &Doc) -> (Vec<Option<usize>>, Vec<(usize, String)>) {
    let mut per_block = vec![None; doc.blocks.len()];
    let mut notes: Vec<(usize, String)> = Vec::new();
    let mut next = 2usize;
    for (i, b) in doc.blocks.iter().enumerate() {
        if let Some(mk) = &b.marker {
            if let Some((_, text)) = doc.notes.iter().find(|(n, _)| n == mk) {
                per_block[i] = Some(next);
                notes.push((next, text.clone()));
                next += 1;
            }
        }
    }
    (per_block, notes)
}

fn footnotes_xml(notes: &[(usize, String)]) -> String {
    let mut s = String::from(
        r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:footnote w:type="separator" w:id="0"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:separator/></w:r></w:p></w:footnote>
<w:footnote w:type="continuationSeparator" w:id="1"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>"#,
    );
    for (id, text) in notes {
        s.push_str(&format!(
            r#"<w:footnote w:id="{id}"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr><w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r><w:r><w:t xml:space="preserve"> {}</w:t></w:r></w:p></w:footnote>"#,
            esc(text)
        ));
    }
    s.push_str("</w:footnotes>");
    s
}

fn document_xml(doc: &Doc, ids: &[Option<usize>]) -> String {
    let mut s = String::from(
        r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>"#,
    );
    for (i, b) in doc.blocks.iter().enumerate() {
        s.push_str(&paragraph(b, ids.get(i).copied().flatten()));
    }
    s.push_str(
        r#"<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>"#,
    );
    s
}

/// Write `doc` to `path` as a DOCX package.
pub fn write(doc: &Doc, path: &Path) -> Result<(), String> {
    let f = std::fs::File::create(path).map_err(|e| format!("cannot create {}: {e}", path.display()))?;
    let mut zip = zip::ZipWriter::new(f);
    let opts = zip::write::SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated);

    let mut put = |zip: &mut zip::ZipWriter<std::fs::File>, name: &str, body: String| -> Result<(), String> {
        zip.start_file(name, opts).map_err(|e| e.to_string())?;
        zip.write_all(body.as_bytes()).map_err(|e| e.to_string())
    };

    put(&mut zip, "[Content_Types].xml", CONTENT_TYPES.to_string())?;
    put(&mut zip, "_rels/.rels", ROOT_RELS.to_string())?;
    put(&mut zip, "word/_rels/document.xml.rels", DOC_RELS.to_string())?;
    let (ids, notes) = footnote_ids(doc);
    put(&mut zip, "word/document.xml", document_xml(doc, &ids))?;
    put(&mut zip, "word/footnotes.xml", footnotes_xml(&notes))?;
    put(&mut zip, "word/styles.xml", styles_xml())?;
    put(&mut zip, "word/numbering.xml", numbering_xml().to_string())?;
    zip.finish().map_err(|e| e.to_string())?;
    Ok(())
}
