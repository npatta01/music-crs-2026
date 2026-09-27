#!/usr/bin/env bash
# Render poster.html to PDF, then preflight the result.
#
# Chrome has to fetch the page over HTTP: printing a file:// URL resolves
# relative assets inconsistently and silently drops them, so we serve the
# directory for the duration of the run and tear it down on exit.
#
#   ./render.sh
set -euo pipefail

cd "$(dirname "$0")"
PORT="${PORT:-8731}"
CHROME="${CHROME:-$(command -v google-chrome || command -v chromium || true)}"
[ -n "$CHROME" ] || { echo "no chrome/chromium on PATH; set CHROME=..." >&2; exit 1; }

SERVER=""
cleanup() { [ -n "$SERVER" ] && kill "$SERVER" 2>/dev/null || true; }
trap cleanup EXIT

python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
SERVER=$!
for _ in $(seq 1 40); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/poster.html" && break
  sleep 0.1
done

render() {  # render <name>
  local n="$1"
  echo "rendering $n.pdf"
  "$CHROME" --headless=new --disable-gpu --no-sandbox --no-pdf-header-footer \
    --virtual-time-budget=6000 --print-to-pdf="$n.pdf" \
    "http://127.0.0.1:$PORT/$n.html" >/dev/null 2>&1
}

preflight() {  # preflight <name> <expected page size fragment>
  local n="$1" want="$2" size fonts t3 raster
  size=$(pdfinfo "$n.pdf" | sed -n 's/^Page size: *//p')
  fonts=$(pdffonts "$n.pdf" | tail -n +3 | grep -c . || true)
  t3=$(pdffonts "$n.pdf" | grep -c 'Type 3' || true)
  raster=$(pdfimages -list "$n.pdf" 2>/dev/null | tail -n +3 | grep -c . || true)
  echo "  size    : $size"
  echo "  fonts   : $fonts embedded, $t3 Type 3"
  echo "  rasters : $raster"
  case "$size" in *"$want"*) ;; *) echo "  !! expected $want" >&2 ;; esac
  # Type 3 comes from variable fonts and some print RIPs mishandle it, so it
  # is a hard failure rather than a warning.
  [ "$t3" -eq 0 ] || { echo "  !! Type 3 font present" >&2; return 1; }
  # Any embedded font must also be subset-embedded, or the shop substitutes.
  pdffonts "$n.pdf" | tail -n +3 | awk '$(NF-3)!="yes"{print "  !! not embedded: "$1; bad=1} END{exit bad+0}'
}

# US shops (FedEx Office etc.) stock 24x36in, not A1. The layout is sized in
# cqw, so the US version is the same source with the page size swapped; the
# extra height goes into the column gaps.
sed -e 's/--w:594mm; --h:841mm;/--w:609.6mm; --h:914.4mm;/' \
    -e 's#96vw / 594, 92vh / 841#96vw / 609.6, 92vh / 914.4#' \
    -e 's/size:594mm 841mm;/size:609.6mm 914.4mm;/' \
    -e 's/width:594mm;height:841mm/width:609.6mm;height:914.4mm/' \
    poster.html > poster-24x36.html

render poster
preflight poster "A1"
render poster-24x36
preflight poster-24x36 "1728 x 2592"
rm -f poster-24x36.html
