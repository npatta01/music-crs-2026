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

TOTAL_STEPS=5
if [[ -t 1 && -z "${NO_COLOR+x}" ]]; then
  STYLE_BOLD=$'\033[1m'
  STYLE_CYAN=$'\033[36m'
  STYLE_GREEN=$'\033[32m'
  STYLE_DIM=$'\033[2m'
  STYLE_RESET=$'\033[0m'
else
  STYLE_BOLD=""
  STYLE_CYAN=""
  STYLE_GREEN=""
  STYLE_DIM=""
  STYLE_RESET=""
fi

step() {
  local number="$1"
  local description="$2"
  printf '\n%s%s[%s/%s] %s%s\n' \
    "$STYLE_BOLD" "$STYLE_CYAN" "$number" "$TOTAL_STEPS" "$description" "$STYLE_RESET"
}

success() {
  printf '      %s✓%s %s\n' "$STYLE_GREEN" "$STYLE_RESET" "$1"
}

info() {
  printf '      %s•%s %s\n' "$STYLE_DIM" "$STYLE_RESET" "$1"
}

error() {
  printf '      ERROR: %s\n' "$1" >&2
}

if [[ -n "$STYLE_BOLD" ]]; then
  printf '%s%s━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s\n' "$STYLE_BOLD" "$STYLE_CYAN" "$STYLE_RESET"
  printf '%sMusic CRS offline reproduction setup%s\n' "$STYLE_BOLD" "$STYLE_RESET"
  printf '%s%s steps%s\n' "$STYLE_DIM" "$TOTAL_STEPS" "$STYLE_RESET"
  printf '%s%s━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s\n' "$STYLE_BOLD" "$STYLE_CYAN" "$STYLE_RESET"
else
  printf '== Music CRS offline reproduction setup (%s steps) ==\n' "$TOTAL_STEPS"
fi

step 1 "Checking prerequisites"
if ! command -v uv >/dev/null 2>&1; then
  error "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi
success "$(uv --version)"

if [ -z "${MODAL_TOKEN_ID:-}" ] || [ -z "${MODAL_TOKEN_SECRET:-}" ]; then
  info "Modal credentials are not required for the pre-cached bundle."
fi

step 2 "Installing Python environment"
uv sync
source .venv/bin/activate

if ! command -v hf >/dev/null 2>&1; then
  error "hf CLI is unavailable after uv sync. Check the huggingface_hub installation."
  exit 1
fi
success "$(hf --version)"

step 3 "Downloading the offline reproduction bundle"
info "Source: Hugging Face dataset Npatta01/music-crs-repro-2026"
hf download Npatta01/music-crs-repro-2026 --repo-type dataset --local-dir .

step 4 "Extracting cache components"
tar --use-compress-program=unzstd -xf cache/embedding.tar.zst
tar --use-compress-program=unzstd -xf cache/state_extraction.tar.zst
chmod +x .repro/scripts/*.sh

step 5 "Verifying bundle integrity"
.repro/scripts/verify_bundle.sh

cat <<'MSG'

✓ Setup complete

Next:
  scripts/repro_run.sh                          # Blind-B (default)
  scripts/repro_run.sh --eval_dataset blindset_A
  scripts/repro_run.sh --eval_dataset devset
MSG
