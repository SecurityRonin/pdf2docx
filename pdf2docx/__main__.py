"""Command line: python -m pdf2docx INPUT.pdf [OUTPUT.docx]"""
from __future__ import annotations

import sys
from pathlib import Path

from . import convert


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print("usage: python -m pdf2docx INPUT.pdf [OUTPUT.docx]", file=sys.stderr)
        return 2
    src = Path(argv[1])
    if not src.exists():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    dst = Path(argv[2]) if len(argv) == 3 else src.with_suffix(".docx")
    convert(src, dst)
    print(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
