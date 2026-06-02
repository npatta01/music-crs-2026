# Experiments Workspace Guide

This workspace is pruned on purpose. Historical reports, archived configs, and
raw artifacts were removed because they confused agents about the current
system. Git history is the archive.

## Source Of Truth

- `experiments/README.md` is the current experiment index.
- `experiments/experiment_log.md` is the short current-state log.
- `leaderboard.md` is the compact devset score table.
- `changelog.md` links experiment outcomes to PRs.
- `configs/` contains only runnable current configs.

## Current Config Policy

- Keep current runnable configs directly under `configs/`.
- Do not recreate `configs/archive/`.
- If a config is superseded, delete it from the working tree after preserving
  the rationale in Git history or in a concise current-state note.
- Prefer `v0plus_compiler_all_retrievers_devset` for the latest coverage
  experiment and `v0plus_compiler_image_devset` for the current score anchor.

## Report Policy

- Do not add one report per exploratory run by default.
- Add a checked-in report only when it is the new current reference or the user
  explicitly asks for a durable artifact.
- Keep reports short and self-contained; avoid raw JSONL, traces, screenshots,
  slide decks, or labeling files in `experiments/`.
- Downloaded Modal artifacts belong under `exp/` or `evaluator/exp/`, not under
  this directory.

## Runtime Prompt Policy

Runtime ConversationState schema and extractor prompts do not live under
`experiments/`. Keep this directory for one-off reports and concise experiment
status only.

Use `mcrs/conversation_state/schema.py` for the Pydantic contract,
`mcrs/conversation_state/prompts/current.py` for the production extractor
prompt, and `mcrs/conversation_state/prompts/previous.py` for the single
reference prompt kept for comparison or rollback.

## Maintenance Checklist

When a new run becomes important enough to keep:

1. Update `experiments/README.md` with the current config/report status.
2. Update `experiments/experiment_log.md` with one concise decision entry.
3. Update `leaderboard.md` if the run changes the compact devset table.
4. Update `changelog.md` with the PR-linked outcome.
5. Keep old details in Git history instead of adding archive folders.
