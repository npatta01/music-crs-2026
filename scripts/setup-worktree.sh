#!/usr/bin/env bash
# Shared worktree initialisation — called by Claude Code, Codex, and manually.
# Run from inside the worktree directory. Idempotent.
set -euo pipefail

WORKTREE="$(pwd -P)"
MAIN="$(git worktree list --porcelain | awk '/^worktree /{print $2; exit}')"
MAIN="$(cd "$MAIN" && pwd -P)"

if [ "$WORKTREE" = "$MAIN" ]; then
    echo "Already in main repo — skipping."
    exit 0
fi

echo "Worktree : $WORKTREE"
echo "Main repo: $MAIN"

# --- Symlinks from .worktreeinclude ---
INC="$MAIN/.worktreeinclude"
if [ -f "$INC" ]; then
    while IFS= read -r p; do
        [[ -z "$p" || "$p" == \#* ]] && continue
        src="$MAIN/$p"
        dst="$WORKTREE/$p"
        if [ ! -e "$src" ]; then
            echo "  [SKIP]  $p (not in main repo)"
        elif [ -L "$dst" ]; then
            echo "  [OK]    $p already linked"
        elif [ -e "$dst" ]; then
            echo "  [WARN]  $p exists as real file — remove to enable sharing"
        else
            ln -s "$src" "$dst" && echo "  [LINK]  $p"
        fi
    done < "$INC"
fi

# --- Submodules ---
echo "Initialising submodules..."
git submodule update --init --recursive

# --- Python env ---
echo "Running uv sync..."
uv sync

echo "Done."
