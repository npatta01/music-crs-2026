# Worktree Resource Sharing

Tracked in [#2](https://github.com/nlp4musa/music-crs-baselines/issues/2).
Implemented in f57fddc on `main`.

## Problem

Claude Code worktrees at `.claude/worktrees/{name}/` only contain git-tracked files.
Gitignored resources (`.venv`, `data/`, `.env`) are absent, so inference cannot run
without manual setup after each worktree creation.

HuggingFace credentials and model cache (`~/.cache/huggingface/`) are system-wide
and unaffected.

## Solution

Use Claude Code's built-in `.worktreeinclude` to auto-copy small gitignored files
into new worktrees. Three file changes:

### `.worktreeinclude` (new)

```
# Copied from main repo into new worktrees on creation.
data/
.env
```

- `data/` — propagates `local_eval_split.json` so local eval works immediately
- `.env` — propagates credentials/overrides when the file exists
- `.venv` excluded — copying 1-2 GB is worse than rebuilding (`uv venv .venv && uv pip install -e .`)

### `.gitignore` additions

```
data/
exp/
```

- `data/` — makes the directory eligible for `.worktreeinclude`; also prevents
  accidental commits of local data files beyond `local_eval_split.json`
- `exp/` — inference outputs are per-worktree; only `evaluator/exp/*` was excluded before

### `.env.example` (new)

Documents env vars relevant to this project so contributors know what to set:

```bash
# HuggingFace auth — recommended: uvx hf auth login (system-wide, no .env needed)
# For CI / Modal: set HF_TOKEN here
# HF_TOKEN=hf_...

# Override HF cache (default: ~/.cache/huggingface/)
# HF_HOME=/path/to/larger/disk/.cache/huggingface
```

## Worktree Workflow After This Change

```bash
# New worktree is created by Claude Code — .worktreeinclude auto-copies data/ and .env
# Then set up Python env (fast with uv):
uv venv .venv
uv pip install -e .

# Run inference as normal
python run_inference_devset.py --tid llama1b_bm25_devset --batch_size 16
```

## What Stays Per-Worktree

| Resource | Strategy | Reason |
|----------|----------|--------|
| `.venv/` | Rebuild | 1-2 GB copy is wasteful; `uv` install is fast |
| `cache/` | Rebuild | BM25/BERT indexes rebuild on first run; per-branch isolation is fine |
| `exp/` | Per-worktree | Inference outputs should be isolated per branch |
| `submission/` | Per-worktree | Each branch packages its own submission |
| `data/` | Copied | Small JSON; needed for local eval |
| `.env` | Copied | Small config; should match main repo |
