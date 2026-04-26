#!/usr/bin/env bash
# Claude Code WorktreeCreate hook — replaces default git behavior.
# Creates the worktree under .claude/worktrees/<name>, runs shared setup,
# then prints the worktree path on stdout (required by Claude Code).
set -euo pipefail

read -r CWD NAME < <(python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d['cwd'], d['name'])
")

WT="$CWD/.claude/worktrees/$NAME"
BRANCH="claude/$NAME"

cd "$CWD"
git worktree add -b "$BRANCH" "$WT" >&2
cd "$WT" && bash scripts/setup-worktree.sh >&2

echo "$WT"
