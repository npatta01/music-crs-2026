#!/usr/bin/env bash
#
# Fresh Modal LanceDB catalog build.
#
# Rebuilds the `music_track_catalog` table from scratch (drop_existing) with
# metadata + FTS fields + the shipped 0.6B Qwen columns + generated 4B/8B Qwen
# embedding columns, then copies it into the `music-crs-models` volume.
# Per-item embeddings are served from the LiteLLM file cache where present; only
# cache misses hit the self-hosted vLLM endpoints.
#
# ALWAYS detached. The build is long-running (188k per-item embedding lookups)
# while the local client only streams logs. `modal run --detach` keeps the run
# alive on Modal even when the local client drops its heartbeat, disconnects, or
# the terminal closes — which a plain `modal run` does not. Do not remove
# `--detach`; that is the entire point of this wrapper.
#
# Track / re-attach after launch:
#   modal app logs <app-id>          # app-id is printed at launch
#   modal app list | grep ephemeral  # find a running build
#
# Pass-through args go to the entrypoint, e.g.:
#   scripts/build_db_modal.sh --max-in-flight 48
#   scripts/build_db_modal.sh --model-sizes 8b --document-kinds metadata
#
set -euo pipefail

cd "$(dirname "$0")/.."

exec uv run modal run --detach \
  modal/app.py::build_lancedb_with_vllm_qwen_embeddings "$@"
