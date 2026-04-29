# Experiments Workspace Guide

Use this directory as the working surface for experiment history, status, and analysis.

## Purpose

- `experiments/README.md` is the main index for current bests, active work, analysis links, and status vocabulary.
- `experiments/experiment_log.md` is the cross-run log for wave-level takeaways, decisions, and next steps.
- `experiments/*.md` are per-run reports unless the filename is an index or log file.
- `experiments/analysis/<analysis_name>/README.md` is the entrypoint for a self-contained analysis package.

## Conventions

- Create one report per run at `experiments/{tid}.md`.
- Put cross-run conclusions in `experiments/experiment_log.md`, not in individual run reports.
- Package deeper analysis as `experiments/analysis/<analysis_name>/README.md` with local artifacts in a sibling subdirectory such as `artifacts/`.
- Keep analysis folders named by topic or deliverable, not by issue number alone.

## Status Updates

- Update `experiments/README.md` when a new best, active workstream, or new analysis package should be discoverable quickly.
- Update `experiments/experiment_log.md` when a wave produces a decision, takeaway, or next-step recommendation.
- Use the shared status vocabulary from `experiments/README.md`: `planned`, `running`, `analyzed`, `done`, `superseded`.

## Agent Expectations

- Read `experiments/README.md` before summarizing project experiment status.
- Prefer linking to the package README for analysis work, not directly to raw artifacts.
- If you add a new experiment or analysis package, also update the relevant index so the next model can discover it in one hop.
