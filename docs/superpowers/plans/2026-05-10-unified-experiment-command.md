# Unified Experiment Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one repo-native experiment command that can run local or Modal backends and produce the same local artifact layout.

**Architecture:** Keep the existing inference scripts as the execution engines and add a thin orchestration wrapper at the repo root. Make the evaluator and ground-truth generator aware of `exp_dir` so both backends converge on the same local artifacts.

**Tech Stack:** Python, argparse, subprocess, pytest, Modal CLI, existing repo inference/evaluator scripts

---

### Task 1: Add regression tests for the new orchestration surface

**Files:**
- Create: `tests/test_run_experiment.py`
- Modify: `tests/test_inference_scripts.py`
- Test: `tests/test_run_experiment.py`

- [ ] **Step 1: Write the failing test**

```python
def test_local_devset_runs_inference_then_ground_truth_then_eval(...):
    ...


def test_modal_blindset_downloads_into_exp_dir(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_experiment.py -v`
Expected: FAIL because `run_experiment.py` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def main(args):
    raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it still fails for the right reason**

Run: `pytest tests/test_run_experiment.py -v`
Expected: FAIL with behavior mismatches instead of import errors.

- [ ] **Step 5: Commit**

```bash
git add tests/test_run_experiment.py
git commit -m "test: cover unified experiment wrapper"
```

### Task 2: Implement the wrapper and shared split logic

**Files:**
- Create: `run_experiment.py`
- Test: `tests/test_run_experiment.py`

- [ ] **Step 1: Write the failing test for split detection and command dispatch**

```python
def test_detect_split_requires_explicit_eval_dataset_for_unknown_tid():
    with pytest.raises(ValueError):
        run_experiment.resolve_split("custom_run", None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_experiment.py::test_detect_split_requires_explicit_eval_dataset_for_unknown_tid -v`
Expected: FAIL because the helper is missing.

- [ ] **Step 3: Write minimal implementation**

```python
def resolve_split(tid: str, eval_dataset: str | None) -> str:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_run_experiment.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add run_experiment.py tests/test_run_experiment.py
git commit -m "feat: add unified experiment wrapper"
```

### Task 3: Make evaluator artifacts configurable

**Files:**
- Modify: `evaluator/evaluate_devset.py`
- Modify: `evaluator/make_ground_truth.py`
- Test: `tests/test_run_experiment.py`

- [ ] **Step 1: Write the failing test**

```python
def test_evaluate_main_uses_custom_exp_dir(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_experiment.py::test_evaluate_main_uses_custom_exp_dir -v`
Expected: FAIL because the evaluator still hardcodes `exp/`.

- [ ] **Step 3: Write minimal implementation**

```python
parser.add_argument("--exp_dir", ...)
```

- [ ] **Step 4: Run targeted tests to verify they pass**

Run: `pytest tests/test_run_experiment.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add evaluator/evaluate_devset.py evaluator/make_ground_truth.py tests/test_run_experiment.py
git commit -m "feat: make experiment artifacts configurable"
```

### Task 4: Refresh docs and repo guidance

**Files:**
- Modify: `readme.md`
- Modify: `docs/mac_dev.md`
- Modify: `docs/modal_setup.md`
- Modify: `CLAUDE.md`
- Modify: `.claude/skills/run-experiment/SKILL.md`

- [ ] **Step 1: Write the failing doc expectation mentally**

```text
The primary workflow should no longer read as Modal-only.
```

- [ ] **Step 2: Update the docs**

```text
Document `run_experiment.py` as the default operator command and keep local and Modal examples side by side.
```

- [ ] **Step 3: Verify wording is consistent**

Run: `rg -n "Modal experiment|Modal-only|run_experiment.py|--backend" readme.md docs CLAUDE.md .claude/skills/run-experiment/SKILL.md`
Expected: wrapper documentation present; stale Modal-only instructions removed or reframed.

- [ ] **Step 4: Commit**

```bash
git add readme.md docs/mac_dev.md docs/modal_setup.md CLAUDE.md .claude/skills/run-experiment/SKILL.md
git commit -m "docs: document unified experiment command"
```
