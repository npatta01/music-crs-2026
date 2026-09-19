# Reproduction Setup Progress Design

## Goal

Make `bash scripts/repro_setup.sh` easy to scan in an interactive terminal by
showing the total number of phases and the current phase, without obscuring the
existing Hugging Face download progress.

## Output design

The script will print a compact title followed by five numbered phases:

1. Check prerequisites.
2. Install the Python environment.
3. Download the offline reproduction bundle.
4. Extract cache components.
5. Verify bundle integrity.

Each heading will use the form `[N/5] Description`. Successful prerequisite
checks will use a check mark, informational messages will use a bullet, and the
final message will clearly separate setup completion from the next commands.

## Terminal behavior

Color and stronger separators will be enabled only when standard output is an
interactive terminal and `NO_COLOR` is not set. Redirected output and CI logs
will remain plain text. The script will not attempt to control the terminal's
font, and it will not wrap or replace progress bars emitted by `hf download`.

## Error behavior

Existing fail-fast behavior remains unchanged. Missing prerequisites will be
reported beneath the relevant phase with installation guidance. Phase 1 checks
for `uv`; phase 2 runs `uv sync`, activates `.venv`, and then confirms that the
synced environment provides `hf`. Commands that fail in later phases retain
their native error output so diagnostic details are not hidden.

## Verification

Shell-level tests will exercise interactive/color and non-interactive/plain
rendering without installing dependencies or downloading the reproduction
bundle. The script will also be checked with `bash -n` and `shellcheck` when
available.

## Scope

The environment phase uses the repository's locked `uv sync` workflow instead
of manually creating a virtual environment and running `uv pip install -e .`.
The change does not alter download sources, extracted files, verification, or
reproduction commands.
