#!/usr/bin/env bash
# Run the full train_v9 OOF-CV pipeline (build -> 5 folds -> finalize) for one
# feature set. One process per fold (memory recipe). Binary labels (no --grades)
# to match the binary control framing. Usage:
#   _run_train_msgstore.sh <features_dir> <sidecar_parquet> <out_dir> <log>
set -euo pipefail
FEATURES="$1"; SIDECAR="$2"; OUT="$3"; LOG="$4"
cd "$(dirname "$0")/../.."
source .venv/bin/activate 2>/dev/null || true

echo "=== [$(date +%H:%M:%S)] BUILD  features=$FEATURES sidecar=$SIDECAR out=$OUT ===" | tee "$LOG"
python scripts/rerank/train_v9.py --stage build \
  --features-dir "$FEATURES" --sidecar "$SIDECAR" --out-dir "$OUT" >>"$LOG" 2>&1

for f in 0 1 2 3 4; do
  echo "=== [$(date +%H:%M:%S)] FOLD $f ===" | tee -a "$LOG"
  python scripts/rerank/train_v9.py --stage fold --fold "$f" \
    --features-dir "$FEATURES" --sidecar "$SIDECAR" --out-dir "$OUT" >>"$LOG" 2>&1
done

echo "=== [$(date +%H:%M:%S)] FINALIZE ===" | tee -a "$LOG"
python scripts/rerank/train_v9.py --stage finalize \
  --features-dir "$FEATURES" --sidecar "$SIDECAR" --out-dir "$OUT" >>"$LOG" 2>&1
echo "=== [$(date +%H:%M:%S)] DONE -> $OUT/metrics.json ===" | tee -a "$LOG"
