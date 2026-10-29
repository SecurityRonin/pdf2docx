"""Command line: python -m pdf2docx INPUT.pdf [OUTPUT.docx] [--layout MODE]"""
from __future__ import annotations

import sys
from pathlib import Path

from . import MODES, convert


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    layout = "semantic"
    if "--layout" in args:
        i = args.index("--layout")
        if i + 1 >= len(args):
            print("--layout needs a value", file=sys.stderr)
            return 2
        layout = args[i + 1]
        del args[i : i + 2]
    if layout not in MODES:
        print(f"--layout must be one of {MODES}", file=sys.stderr)
        return 2
    if len(args) not in (1, 2):
        print("usage: python -m pdf2docx INPUT.pdf [OUTPUT.docx] [--layout semantic|faithful]",
              file=sys.stderr)
        return 2
    src = Path(args[0])
    if not src.exists():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    dst = Path(args[1]) if len(args) == 2 else src.with_suffix(".docx")
    convert(src, dst, layout=layout)
    print(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
