# Unified Experiment Command Design

## Goal

Add one operator-facing experiment command that can run either locally or via Modal while producing the same local artifact layout.

## Problem

The repo already has local-friendly inference scripts, but the higher-level experiment workflow is Modal-centric. That forces users to remember different commands, different artifact locations, and a manual copy/evaluation path.

## Decision

Add a new repo-root wrapper, `run_experiment.py`, as the primary entrypoint for experiment orchestration.

The wrapper will:

- validate that `config/{tid}.yaml` exists
- resolve whether the run targets `devset` or a `blindset_*` split
- dispatch either a local or Modal backend
- standardize local artifacts under one `exp/`-style output tree
- run local evaluation automatically for devset runs

## Scope

### In scope

- new unified wrapper command
- local backend orchestration
- Modal backend orchestration
- evaluator support for configurable artifact roots
- docs refresh so the wrapper becomes the default workflow
- skill refresh so local repo guidance stops assuming Modal-only execution

### Out of scope

- changing the underlying retrieval or generation implementation
- hidden device overrides for local runs
- refactoring inference scripts into a package CLI
- changing blindset packaging format

## Interface

Primary command examples:

```bash
uv run python run_experiment.py --backend local --tid llama1b_bm25_devset
uv run python run_experiment.py --backend modal --tid llama1b_bm25_devset
uv run python run_experiment.py --backend local --tid llama1b_bm25_blindset_A --eval_dataset blindset_A
```

Key arguments:

- `--backend {local,modal}`
- `--tid`
- `--eval_dataset` for explicit blindset selection when needed
- `--batch_size`
- `--num_sessions` for devset smoke runs
- `--session_ids_file` for local devset subset runs
- `--clear_cache`
- `--exp_dir`

## Backend Behavior

### Local

- devset: run `run_inference_devset.py`, ensure ground truth exists, then run `evaluator/evaluate_devset.py`
- blindset: run `run_inference_blindset.py`

### Modal

- devset: run `modal/app.py::run_inference`, download artifacts into the local `exp` tree, ensure ground truth exists, then run `evaluator/evaluate_devset.py`
- blindset: run `modal/app.py::run_inference_blindset`, then download artifacts into the local `exp` tree

## Artifact Layout

Use repo-root `exp/` by default for both backends:

- `exp/inference/devset/{tid}.json`
- `exp/inference/blindset_A/{tid}.json`
- `exp/ground_truth/devset.json`
- `exp/scores/devset/{tid}.json`

This keeps `prepare_submission.sh` working unchanged for default runs.

## Error Handling

- missing config: fail before running anything
- ambiguous split detection: require explicit `--eval_dataset`
- missing devset ground truth: auto-generate it in the selected `exp_dir`
- local hardware mismatch: surface the real runtime error rather than rewriting config values
- Modal failures: surface the underlying command failure directly

## File Changes

- add `run_experiment.py`
- update `evaluator/evaluate_devset.py` to accept `--exp_dir`
- update `evaluator/make_ground_truth.py` to accept `--exp_dir`
- refresh docs in `readme.md`, `docs/mac_dev.md`, `docs/modal_setup.md`, and `CLAUDE.md`
- refresh `.claude/skills/run-experiment/SKILL.md`
