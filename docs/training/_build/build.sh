#!/bin/bash
# Build docs/training/**/*.pdf from the markdown files.
# Step 1 (this script): pandoc -> HTML -> headless Chrome -> raw PDFs in _build/out/raw
# Step 2: python3 _build/links.py   (rewrites links, writes final PDFs next to the .md files)
# Usage: _build/build.sh [file.md ...]   (paths relative to docs/training; default: all)
# Needs: pandoc, Google Chrome, internet (mermaid is loaded from a CDN).
B="$(cd "$(dirname "$0")" && pwd)"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT="$B/out"
cd "$B/.." || exit 1
if [ $# -gt 0 ]; then FILES=("$@"); else FILES=(README.md 00-architecture-overview.md 0[1-6]*/*.md); fi
for f in "${FILES[@]}"; do
  h="$OUT/html/${f%.md}.html"; mkdir -p "$(dirname "$h")" "$(dirname "$OUT/raw/${f%.md}.pdf")"
  pandoc -f gfm -t html5 -s --lua-filter="$B/mermaid.lua" -H "$B/mermaid-head.html" --metadata pagetitle="$(head -1 "$f" | sed 's/^# //')" --css "$B/style.css" --embed-resources "$f" -o "$h" 2>/dev/null || { echo "PANDOC FAIL $f"; continue; }
  "$CH" --headless=new --disable-gpu --no-pdf-header-footer --virtual-time-budget=15000 --print-to-pdf="$OUT/raw/${f%.md}.pdf" "file://$h" >/dev/null 2>&1 || echo "CHROME FAIL $f"
done
