#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <tid> [split]"
    echo "  split defaults to blindset_A; pass e.g. blindset_B to package another blind split."
    echo "Example: $0 state_ranker_v10_lgbm_blindset_A"
    echo "Example: $0 <tid> blindset_B"
    exit 1
fi

TID="$1"
SPLIT="${2:-blindset_A}"
DATE=$(date +%Y%m%d)
BLINDSET_DIR="$(dirname "$0")/exp/inference/${SPLIT}"
SUBMISSION_DIR="$(dirname "$0")/submission"
SRC="$BLINDSET_DIR/${TID}.json"
ZIP_NAME="submission_${TID}_${DATE}.zip"

if [[ ! -f "$SRC" ]]; then
    echo "Error: $SRC not found"
    exit 1
fi

mkdir -p "$SUBMISSION_DIR"

cp "$SRC" "$SUBMISSION_DIR/prediction.json"

(cd "$SUBMISSION_DIR" && zip "$ZIP_NAME" prediction.json && rm prediction.json)

echo "Created: $SUBMISSION_DIR/$ZIP_NAME"
