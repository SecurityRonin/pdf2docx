# Privacy Policy

Last updated: 30 October 2026

## The short version

pdf2docx operates entirely on your machine. It does not collect telemetry, does not
open a network connection to convert a document, and does not transmit your files
anywhere.

## What is processed, and where

Conversion runs locally. The PDF you open, the text extracted from it and the DOCX
produced from it stay on your computer. Nothing is uploaded.

## Network access

There is exactly one network feature, and it is manual: fetching a metric-compatible
font substitution (for example Carlito in place of Calibri). It runs only when you ask
for it, downloads from a fixed allowlist, verifies a pinned SHA-256 before use, and
writes to a per-user directory (`~/.local/share/pdf2docx/fonts`). No document content
is ever part of that request.

## Crash reporting and analytics

None. The application writes logs to its own local directory only.

## Desktop application

The Tauri application reads PDFs through a local file dialog and writes DOCX to the
location you choose. It has no update check, no licence check and no remote
configuration, so it makes no outbound connection while converting.

## Third-party components

The converter uses `pdfplumber`/`pdfminer.six` to read PDF and `python-docx` to write
DOCX. The desktop application uses Tauri, and pdf.js for preview. Each is executed
locally.

## Contact

Questions about this policy: **privacy@securityronin.com**

Security Ronin Ltd
