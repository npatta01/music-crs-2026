# Reproduction Setup Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/repro_setup.sh` show five clear, numbered phases with terminal-aware color and readable plain-text fallback.

**Architecture:** Keep presentation helpers inside the existing Bash entrypoint so setup gains no dependency. Exercise the real script from Python subprocess tests inside a temporary fake repository whose command stubs prevent installation, extraction, verification, or network access.

**Tech Stack:** Bash, Python standard library, pytest

## Global Constraints

- Show exactly five phases as `[N/5] Description`.
- Enable color only for an interactive stdout when `NO_COLOR` is unset.
- Preserve native `hf download` output without wrapping its progress bars.
- Use `uv sync` before checking for the environment-provided `hf` command.
- Do not change download sources, artifacts, or reproduction commands.

---

### Task 1: Numbered and terminal-aware setup output

**Files:**
- Create: `tests/test_repro_setup_script.py`
- Modify: `scripts/repro_setup.sh`

**Interfaces:**
- Consumes: Bash stdout TTY detection and the conventional `NO_COLOR` environment variable.
- Produces: `step NUMBER DESCRIPTION`, `success MESSAGE`, and `info MESSAGE` presentation helpers used by the setup phases.

- [ ] **Step 1: Write failing subprocess tests**

Create a temporary repository containing the real setup script and local stubs for `uv`, `hf`, `tar`, and `chmod`. Assert that ordinary captured output contains every heading from `[1/5]` through `[5/5]`, contains no ANSI escape sequences, and still shows the final reproduction commands. Run the same fixture through a Python pseudo-terminal and assert that ANSI styling is present. Run the pseudo-terminal fixture with `NO_COLOR=1` and assert styling is absent.

- [ ] **Step 2: Verify the tests fail for the missing presentation**

Run: `python -m pytest tests/test_repro_setup_script.py -q`

Expected: failures because current headings do not contain `[1/5]` and interactive output has no ANSI styling.

- [ ] **Step 3: Implement the minimal Bash presentation helpers**

Add constants initialized from `[[ -t 1 && -z "${NO_COLOR+x}" ]]`, a title banner, and helpers that render the agreed headings and status prefixes. Replace the five existing `== ... ==` headings with `step` calls. In phase 2, run `uv sync`, activate `.venv`, and then verify the synced `hf` command before downloading.

- [ ] **Step 4: Verify focused behavior and syntax**

Run: `python -m pytest tests/test_repro_setup_script.py -q`

Expected: all focused tests pass.

Run: `bash -n scripts/repro_setup.sh`

Expected: exit code 0 with no output.

- [ ] **Step 5: Review scope and commit**

Run: `git diff --check && git diff -- scripts/repro_setup.sh tests/test_repro_setup_script.py`

Expected: no whitespace errors; diff contains presentation and focused test changes only.

Commit the script, tests, spec, and plan with `feat: clarify reproduction setup progress`.
