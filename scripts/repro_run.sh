#!/usr/bin/env bash
# Run offline reproduction inference — no credentials, no Modal — against the
# bundle scripts/repro_setup.sh downloaded. Defaults to Blind-B.
#
# Usage:
#   scripts/repro_run.sh                                 # Blind-B
#   scripts/repro_run.sh --eval_dataset blindset_A
#   scripts/repro_run.sh --eval_dataset devset
#   scripts/repro_run.sh --eval_dataset blindset_B --tid some_other_config
#   scripts/repro_run.sh --batch_size 4
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

EVAL_DATASET="blindset_B"
TID=""
BATCH_SIZE=8

while [ $# -gt 0 ]; do
  case "$1" in
    --eval_dataset) EVAL_DATASET="$2"; shift 2 ;;
    --tid) TID="$2"; shift 2 ;;
    --batch_size) BATCH_SIZE="$2"; shift 2 ;;
    -h|--help) tail -n +2 "$0" | sed -n '/^#/{p};/^[^#]/q' | cut -c3-; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done
if [ -z "$TID" ]; then
  TID="state_ranker_v10_lgbm_$EVAL_DATASET"
fi

if [ ! -f .repro/scripts/activate_repro_env.sh ]; then
  echo "ERROR: .repro/scripts/activate_repro_env.sh not found — run scripts/repro_setup.sh first." >&2
  exit 1
fi
source .repro/scripts/activate_repro_env.sh

PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python"
fi

if [ "$EVAL_DATASET" = "devset" ]; then
  echo "== Running devset ($TID) =="
  "$PYTHON" run_inference_devset.py --tid "$TID" --batch_size "$BATCH_SIZE" \
    --require_litellm_cache
  OUT="exp/inference/devset/$TID.json"
else
  echo "== Running $EVAL_DATASET ($TID) =="
  "$PYTHON" run_inference_blindset.py --tid "$TID" --eval_dataset "$EVAL_DATASET" \
    --batch_size "$BATCH_SIZE" --require_litellm_cache
  OUT="exp/inference/$EVAL_DATASET/$TID.json"
fi

echo
echo "Done: $OUT"

if command -v jq >/dev/null 2>&1; then
  BLANK=$(jq '[.[] | select((.predicted_response // "") == "")] | length' "$OUT")
  if [ "$BLANK" != "0" ]; then
    cat <<MSG

NOTE: $BLANK/$(jq 'length' "$OUT") session(s) came back with an empty
predicted_response. This is expected, occasional behavior for live reruns,
not a bug: retrieval isn't byte-reproducible run to run (see "Why frozen
replay, not live rerun, is canonical" in docs/reproduce_offline_bundle.md),
so a different track can end up ranked #1 than in the canonical run — and
this bundle's cached explanations only cover the tracks that were actually
#1 in that canonical run. The recommended track IDs are unaffected either
way; only the natural-language explanation for the affected turn(s) is
blank. Re-running may or may not reproduce the same gap.
MSG
  fi
fi
