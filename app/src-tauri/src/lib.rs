//! App backend: read a PDF for preview, and run the conversion engine.

use serde::Serialize;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::ipc::Response;

/// What the engine reported, surfaced to the UI.
#[derive(Serialize, Clone)]
pub struct ConversionReport {
    pub ok: bool,
    pub out_path: String,
    pub engine: String,
    pub detail: String,
}

/// Bytes of the chosen PDF, for pdf.js to render.
#[tauri::command]
fn read_pdf(path: String) -> Result<Response, String> {
    let bytes = std::fs::read(&path).map_err(|e| format!("cannot read {path}: {e}"))?;
    Ok(Response::new(bytes))
}

/// Where the conversion engine lives.
///
/// In a packaged build it is a Tauri sidecar named `pdf2docx-engine-<target>`
/// shipped next to the app binary. In development it is the Python module, so
/// the tested converter is exercised directly rather than a stale copy.
fn engine_command() -> (String, Vec<String>, &'static str) {
    if let Ok(explicit) = std::env::var("PDF2DOCX_ENGINE") {
        return (explicit, vec![], "sidecar(PDF2DOCX_ENGINE)");
    }
    let exe = std::env::current_exe().ok();
    if let Some(dir) = exe.as_ref().and_then(|p| p.parent()) {
        let name = if cfg!(windows) {
            "pdf2docx-engine.exe"
        } else {
            "pdf2docx-engine"
        };
        let candidate = dir.join(name);
        if candidate.exists() {
            return (candidate.to_string_lossy().into(), vec![], "sidecar");
        }
    }
    (
        "python3".into(),
        vec!["-m".into(), "pdf2docx".into()],
        "python-module",
    )
}

#[tauri::command]
fn convert(
    src: String,
    dst: Option<String>,
    layout: Option<String>,
) -> Result<ConversionReport, String> {
    let src_path = PathBuf::from(&src);
    if !src_path.exists() {
        return Err(format!("no such file: {src}"));
    }
    let dst_path = dst
        .map(PathBuf::from)
        .unwrap_or_else(|| src_path.with_extension("docx"));

    let (program, prefix, kind) = engine_command();
    let mut cmd = Command::new(&program);
    cmd.args(&prefix);
    cmd.arg(&src_path).arg(&dst_path);
    cmd.args(["--layout", layout.as_deref().unwrap_or("semantic")]);
    cmd.env("PDF2DOCX_QUIET", "1");

    let output = cmd
        .output()
        .map_err(|e| format!("cannot start engine ({program}): {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!(
            "engine failed ({}): {}",
            output.status,
            stderr.trim()
        ));
    }
    if !dst_path.exists() {
        return Err(format!(
            "engine reported success but wrote nothing to {}",
            dst_path.display()
        ));
    }
    Ok(ConversionReport {
        ok: true,
        out_path: dst_path.to_string_lossy().into(),
        engine: kind.to_string(),
        detail: summarize(&dst_path),
    })
}

/// A short human-readable fact about the result, so the UI shows evidence
/// rather than a bare "done".
fn summarize(path: &Path) -> String {
    match std::fs::metadata(path) {
        Ok(m) => format!("{} KB written", m.len() / 1024),
        Err(_) => "written".into(),
    }
}

/// Reveal the produced file in the OS file manager.
#[tauri::command]
fn reveal(path: String) -> Result<(), String> {
    let p = PathBuf::from(&path);
    let mut cmd;
    if cfg!(target_os = "macos") {
        cmd = Command::new("open");
        cmd.args(["-R", path.as_str()]);
    } else if cfg!(windows) {
        // explorer's /select, switch takes the path in the same argument.
        cmd = Command::new("explorer");
        cmd.arg(format!("/select,{path}"));
    } else {
        cmd = Command::new("xdg-open");
        cmd.arg(p.parent().unwrap_or(p.as_path()));
    }
    cmd.spawn()
        .map(|_| ())
        .map_err(|e| format!("cannot reveal: {e}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![read_pdf, convert, reveal])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
