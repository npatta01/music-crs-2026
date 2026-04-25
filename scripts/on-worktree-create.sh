#!/usr/bin/env bash
# Claude Code WorktreeCreate hook — reads worktree path from stdin JSON,
# then delegates to the shared setup script.
set -euo pipefail

WT=$(python3 -c "import sys, json; print(json.load(sys.stdin)['worktree_path'])")
cd "$WT" && bash scripts/setup-worktree.sh
