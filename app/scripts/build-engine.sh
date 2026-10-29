#!/usr/bin/env bash
# Freeze the converter into the Tauri sidecar for the current target.
#
# Tauri resolves `externalBin: ["binaries/pdf2docx-engine"]` to a file suffixed
# with the target triple, so the name here must carry that triple or the bundle
# step fails with "binary not found".
#
# Onefile is deliberate: `externalBin` ships a single file. It extracts to a
# temp dir at run time, which on macOS needs the `disable-library-validation`
# entitlement already set in entitlements.plist.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app="$(cd "$here/.." && pwd)"
repo="$(cd "$app/.." && pwd)"

triple="${TAURI_ENV_TARGET_TRIPLE:-$(rustc -vV | sed -n 's/^host: //p')}"
out="$app/src-tauri/binaries"
mkdir -p "$out"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

export PYTHONPATH="$repo${PYTHONPATH:+:$PYTHONPATH}"
python="${PYTHON:-python3}"

echo "building engine for $triple"
"$python" -m PyInstaller \
  --noconfirm --clean --onefile \
  --name pdf2docx-engine \
  --distpath "$work/dist" \
  --workpath "$work/build" \
  --specpath "$work" \
  --hidden-import pdfplumber \
  --hidden-import pdfminer \
  --collect-submodules pdfminer \
  --collect-submodules pdfplumber \
  --exclude-module tkinter \
  --exclude-module pytest \
  "$here/engine_entry.py"

bin="$work/dist/pdf2docx-engine"
[ -x "$bin" ] || { echo "PyInstaller produced no executable at $bin" >&2; exit 1; }

ext=""
case "$triple" in *windows*) ext=".exe" ;; esac
install -m 755 "$bin" "$out/pdf2docx-engine-$triple$ext"
echo "wrote $out/pdf2docx-engine-$triple$ext"
"$out/pdf2docx-engine-$triple$ext" --help >/dev/null 2>&1 || true
