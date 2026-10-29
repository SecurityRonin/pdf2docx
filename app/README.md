# PDF to DOCX — desktop app

A Tauri v2 desktop app (macOS and Windows) that opens a PDF, previews it, and
converts it with the tested `pdf2docx` engine.

## Run it

```bash
cd app
npm install
npm run tauri dev
```

In development the backend uses the in-repo Python module through
`scripts/engine-dev`. To point it somewhere else:

```bash
PDF2DOCX_ENGINE=/path/to/engine npm run tauri dev
```

## Build a distributable

```bash
# 1. freeze the converter into a sidecar for THIS host triple
./scripts/build-engine.sh          # writes src-tauri/binaries/pdf2docx-engine-<triple>

# 2. build the app
npm run tauri build
```

PyInstaller cannot cross-compile, so each architecture is built on a runner of
that architecture (see `.github/workflows/release.yml`).

## How the pieces fit

```
┌─────────────── Tauri window ───────────────┐
│ frontend (pdf.js)  ── invoke ──►  Rust     │
│   renders pages                   │        │
│                                   ├─ read_pdf   → bytes for preview
│                                   ├─ convert    → spawn engine
│                                   └─ reveal     → open in Finder/Explorer
└───────────────────────────────────┼────────┘
                                    ▼
                        pdf2docx-engine (frozen Python)
```

The engine is resolved in this order, so a packaged app never depends on a
system Python:

1. `$PDF2DOCX_ENGINE` (development override)
2. `pdf2docx-engine` next to the app executable (packaged sidecar)
3. `python3 -m pdf2docx` (fallback; dev machines only)

## Why the sidecar is a single file

Tauri's `externalBin` ships one file. PyInstaller `--onefile` satisfies that, at
the cost of extracting to a temp directory at run time. On macOS the extraction
`dlopen`s unsigned libraries, which the hardened runtime blocks — hence
`com.apple.security.cs.disable-library-validation` in `entitlements.plist`.
The alternative (one directory of files) needs `resources` wiring and loses the
single-binary sidecar contract.

## Signing

See [`../docs/SIGNING.md`](../docs/SIGNING.md). macOS gets Developer ID signing
plus notarization; Windows gets Authenticode via Azure Trusted Signing. Windows
has no notarization service.
