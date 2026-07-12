#!/usr/bin/env bash
# One-command bootstrap for the offline reproduction bundle: checks
# prerequisites, installs the Python env, downloads the bundle from Hugging
# Face, and verifies it. See docs/reproduce_offline_bundle.md for details.
#
# Usage: scripts/repro_setup.sh
# Then:  scripts/repro_run.sh              # Blind-B, no credentials, no Modal
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Checking prerequisites =="
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi
echo "  uv: $(uv --version)"

if ! command -v hf >/dev/null 2>&1; then
  echo "ERROR: hf (huggingface_hub CLI) not found. Install: uv pip install -U 'huggingface_hub[cli]'"
  exit 1
fi
echo "  hf: $(hf --version)"

if [ -z "${MODAL_TOKEN_ID:-}" ] || [ -z "${MODAL_TOKEN_SECRET:-}" ]; then
  echo "  modal: no credentials set — fine for this bundle. Every devset /"
  echo "         Blind-A / Blind-B session is pre-cached, so reproduction"
  echo "         never calls Modal. Only needed for data outside those"
  echo "         cached sessions."
fi

echo "== Installing Python environment (.venv) =="
if [ ! -d .venv ]; then
  uv venv .venv --python=3.12
fi
source .venv/bin/activate
uv pip install -e .

echo "== Downloading the offline reproduction bundle from Hugging Face =="
hf download Npatta01/music-crs-repro-2026 --repo-type dataset --local-dir .

echo "== Extracting tarballed cache components =="
tar --use-compress-program=unzstd -xf cache/embedding.tar.zst
tar --use-compress-program=unzstd -xf cache/state_extraction.tar.zst
chmod +x .repro/scripts/*.sh

echo "== Verifying bundle integrity =="
.repro/scripts/verify_bundle.sh

cat <<'MSG'

Setup complete. Next:
  scripts/repro_run.sh                          # Blind-B (default)
  scripts/repro_run.sh --eval_dataset blindset_A
  scripts/repro_run.sh --eval_dataset devset
MSG
