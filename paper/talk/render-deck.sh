#!/usr/bin/env bash
# Build talk.html from deck.html, render both PDFs, preflight them.
#
#   ./render-deck.sh          full deck + core-only cut
#
# The core cut is the same source filtered by ?core=1, not a second deck.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8732}"
CHROME="${CHROME:-$(command -v google-chrome || command -v chromium || true)}"
[ -n "$CHROME" ] || { echo "no chrome/chromium on PATH" >&2; exit 1; }

python3 build.py

SERVER=""
cleanup() { [ -n "$SERVER" ] && kill "$SERVER" 2>/dev/null || true; }
trap cleanup EXIT
python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
SERVER=$!
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$PORT/talk.html" && break; sleep 0.1; done

render() {
  echo "rendering $2"
  "$CHROME" --headless=new --disable-gpu --no-sandbox --no-pdf-header-footer \
    --virtual-time-budget=6000 --print-to-pdf="$2" "$1" >/dev/null 2>&1
  local pages size t3
  pages=$(pdfinfo "$2" | sed -n 's/^Pages: *//p')
  size=$(pdfinfo "$2" | sed -n 's/^Page size: *//p')
  t3=$(pdffonts "$2" | grep -c 'Type 3' || true)
  echo "  pages: $pages · $size · $t3 Type 3"
  [ "$t3" -eq 0 ] || { echo "  !! Type 3 font present" >&2; return 1; }
}

render "http://127.0.0.1:$PORT/talk.html"        talk.pdf
render "http://127.0.0.1:$PORT/talk.html?core=1" talk-core.pdf
