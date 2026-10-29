"""Match the source document's fonts, and fit an inexact one by measurement.

A PDF names its fonts exactly, so the first question is not "what does this
look like" but "do I have it, or something with the same metrics". Substituting
a face with different advance widths moves every word after the first, which is
what pushes a page over.

Order of preference, cheapest and best first:

  1. the exact family, installed                 -> use it as-is
  2. a metric-compatible open clone, if known    -> fetch it, then as-is
  3. the closest installed face                  -> tune size, then tracking

Only allowlisted clones are ever downloaded. Proprietary faces (Calibri, Arial,
Times New Roman) are never fetched: they cannot be redistributed, and their open
clones carry the same metrics by design, which is what fidelity actually needs.
"""
from __future__ import annotations

import os
import platform
import re
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont

# Fidelity needs the metrics, not the glyphs. Each entry is a face whose
# advance widths are designed to match the proprietary original.
SUBSTITUTES = {
    "calibri": "Carlito",
    "cambria": "Caladea",
    "arial": "Liberation Sans",
    "times new roman": "Liberation Serif",
    "courier new": "Liberation Mono",
    "georgia": "Gelasio",
    "verdana": "DejaVu Sans",
    "tahoma": "DejaVu Sans",
    "segoe ui": "Selawik",
    "helvetica": "Liberation Sans",
    "helvetica neue": "Liberation Sans",
}

# Where clones may be fetched from. Pinned URL and SHA-256 per file; anything not
# listed here is refused, so a caller cannot turn this into an arbitrary download.
CLONE_SOURCES = {
    "Carlito": {
        "url": "https://github.com/google/fonts/raw/main/ofl/carlito/Carlito-Regular.ttf",
        # Verified 2026-10-30 against the upstream file (SIL OFL 1.1).
        "sha256": "f6418f708baede9789daef5d458c0f53d2a888af9820e8062934e504fedc6595",
    },
}

MAX_TRACKING_PT = 0.6      # per character; beyond this the face is simply wrong
SIZE_RANGE = (0.7, 1.4)


@dataclass
class Metrics:
    units_per_em: int
    average_width: float     # in em units
    family: str = ""


@dataclass
class Fit:
    size_scale: float
    tracking_pt: float       # added between characters
    source: str              # "exact" | "substitute" | "tuned"


_FONT_DIRS = {
    "Darwin": ["/System/Library/Fonts", "/Library/Fonts", "~/Library/Fonts",
               "/System/Library/Fonts/Supplemental"],
    "Windows": [r"C:\Windows\Fonts", "~/AppData/Local/Microsoft/Windows/Fonts"],
    "Linux": ["/usr/share/fonts", "/usr/local/share/fonts", "~/.local/share/fonts",
              "~/.fonts"],
}

_cache: dict[Path, TTFont] = {}


def _dirs() -> list[Path]:
    """System font directories, plus the clones this tool fetched.

    The clones come last so a real system face of the same name wins; but they
    must be visible, or a fetched Carlito would never be used and the download
    would be pointless.
    """
    out = []
    for d in _FONT_DIRS.get(platform.system(), []):
        p = Path(d).expanduser()
        if p.is_dir():
            out.append(p)
    # Opt-in only. A clone's metrics are the right ones only when the RENDERER
    # will also use that clone. Measured with Carlito fetched and used for
    # fitting but not visible to the renderer, text similarity fell from 99.2%
    # to 83.1% — tracking computed for one face, applied to another.
    if os.environ.get("PDF2DOCX_USE_FETCHED_FONTS"):
        clones = Path.home() / ".local" / "share" / "pdf2docx" / "fonts"
        if clones.is_dir():
            out.append(clones)
    return out


def _load(path) -> TTFont | None:
    p = Path(path)
    if p in _cache:
        return _cache[p]
    try:
        f = TTFont(str(p), lazy=True, fontNumber=0)
    except Exception:
        return None
    _cache[p] = f
    return f


def _family_name(font: TTFont) -> str:
    name = font.get("name")
    if name is None:
        return ""
    for nid in (16, 1):          # typographic family, then family
        rec = name.getDebugName(nid)
        if rec:
            return rec
    return ""


def installed() -> dict[str, Path]:
    """Regular-weight faces available on this machine, keyed by lower-case family."""
    found: dict[str, Path] = {}
    for d in _dirs():
        for p in sorted(d.rglob("*")):
            if p.suffix.lower() not in (".ttf", ".otf", ".ttc", ".otc"):
                continue
            font = _load(p)
            if font is None:
                continue
            fam = _family_name(font)
            if not fam:
                continue
            key = fam.strip().lower()
            # Prefer the regular face for a family.
            if key in found and re.search(r"bold|italic|oblique|black|light",
                                          p.stem, re.I):
                continue
            found.setdefault(key, p)
    return found


def metrics(path) -> Metrics:
    font = _load(path)
    if font is None:
        raise ValueError(f"cannot read font: {path}")
    upem = font["head"].unitsPerEm or 1000
    widths = [m[0] for m in font["hmtx"].metrics.values()] if hasattr(
        font["hmtx"].metrics, "values") else [v[0] for v in font["hmtx"].metrics.values()]
    avg = (sum(widths) / len(widths)) / upem if widths else 0.5
    return Metrics(upem, avg, _family_name(font))


def _advance(font: TTFont, ch: str, upem: int) -> int:
    cmap = font.getBestCmap() or {}
    gname = cmap.get(ord(ch))
    if gname is None:
        return upem // 2            # a notdef-ish advance rather than zero
    try:
        return font["hmtx"].metrics[gname][0]
    except KeyError:
        return upem // 2


def text_width(path, text: str, size: float) -> float:
    """Width of `text` at `size` points, from the font's own advance widths."""
    font = _load(path)
    if font is None:
        raise ValueError(f"cannot read font: {path}")
    upem = font["head"].unitsPerEm or 1000
    total = sum(_advance(font, ch, upem) for ch in text)
    return total / upem * size


def substitute_for(family: str) -> str | None:
    """The metric-compatible open clone of `family`, if one is known."""
    return SUBSTITUTES.get((family or "").strip().lower())


def closest(target: str, available: list[str]) -> str:
    """Nearest available family by name, preferring a shared word or script."""
    t = (target or "").strip().lower()
    if not available:
        return ""
    exact = next((a for a in available if a.strip().lower() == t), None)
    if exact:
        return exact
    sub = substitute_for(t)
    if sub:
        hit = next((a for a in available if a.strip().lower() == sub.lower()), None)
        if hit:
            return hit
    def score(a: str) -> int:
        al = a.strip().lower()
        words = set(re.split(r"[^a-z]+", t)) & set(re.split(r"[^a-z]+", al))
        return len(words) * 10 + (3 if "sans" in al or "arial" in al else 0)
    return max(available, key=score)


def clone_dir() -> Path:
    """Where fetched clones live: per-user, not the system font folder.

    Installing into the system folder would change every other application's
    rendering; a per-user directory is ours to add and remove.
    """
    root = Path.home() / ".local" / "share" / "pdf2docx" / "fonts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def fetch_substitute(family: str, dest: Path | None = None) -> Path:
    """Fetch the metric-compatible clone of `family`, verified.

    Only names in CLONE_SOURCES are fetched, and only when their SHA-256
    matches the pin. A download that cannot be verified is deleted rather than
    used: an unchecked font binary is arbitrary code the renderer will load.
    """
    import hashlib
    import shutil
    import tempfile
    import urllib.request

    name = substitute_for(family)
    if not name:
        raise ValueError(f"no known substitute for {family!r}")
    entry = CLONE_SOURCES.get(name)
    if not entry:
        raise ValueError(f"{name} is not in the download allowlist")

    dest = Path(dest) if dest else clone_dir()
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"{name}.ttf"
    if target.exists():
        return target

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as tmp:
        tmp_path = Path(tmp.name)
    try:
        with urllib.request.urlopen(entry["url"], timeout=60) as r, open(tmp_path, "wb") as f:
            shutil.copyfileobj(r, f)
        digest = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
        if entry.get("sha256") and digest != entry["sha256"]:
            raise ValueError(
                f"{name} failed verification: expected {entry['sha256']}, got {digest}")
        shutil.move(str(tmp_path), target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return target


def plan(path, text: str, size: float, target_width: float,
         exact: bool = False) -> Fit:
    """How to make `text` occupy `target_width` in this face.

    Tracking closes small differences without distorting glyphs; a large
    difference means the face itself is wrong, and the size scale takes it.
    """
    natural = text_width(path, text, size)
    if natural <= 0 or not text:
        return Fit(1.0, 0.0, "exact" if exact else "tuned")

    scale = 1.0
    tracking = (target_width - natural) / max(1, len(text) - 1)
    if abs(tracking) > MAX_TRACKING_PT:
        # Too far to fix by spacing alone: scale the size, then re-fit.
        scale = max(SIZE_RANGE[0], min(SIZE_RANGE[1], target_width / natural))
        scaled = natural * scale
        tracking = (target_width - scaled) / max(1, len(text) - 1)
        tracking = max(-MAX_TRACKING_PT, min(MAX_TRACKING_PT, tracking))
    if exact and abs(tracking) < 0.01:
        return Fit(1.0, 0.0, "exact")
    return Fit(round(scale, 4), round(tracking, 4), "tuned" if not exact else "exact")
