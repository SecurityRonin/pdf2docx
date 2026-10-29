"""Entry point frozen by PyInstaller into the Tauri sidecar.

Kept deliberately thin: the conversion logic lives in the `pdf2docx` package so
the CLI, the tests and the app all exercise one implementation.
"""
import sys

from pdf2docx.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
