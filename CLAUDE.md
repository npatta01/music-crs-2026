# Music-CRS

RecSys Challenge 2026 baseline — conversational music recommendation system. Given a multi-turn conversation, retrieve 20 tracks from a 47k-track catalog and generate a natural language response.

Challenge: https://nlp4musa.github.io/music-crs-challenge/

## Docs

- [Data](docs/data.md) — dataset schemas, splits, sample rows, inference output format
- [Baseline Architecture](docs/architectures/baseline.md) — pipeline, retrieval modules, LLM module, config
- [v0+ Retrieval Pipeline](docs/architectures/v0plus_retrieval.md) — **retrievers, flow & fusion rankers** for the canonical `v0plus_compiler_*` path
- [Session State](docs/architectures/session_state.md) — the `ConversationStateV0Plus` schema, extract→resolve pipeline, and how each field drives retrieval
- [Explanation / Response Generation](docs/architectures/explanation_generation.md) — how the natural-language response is generated, what the code was vs. is now doing (dummy), and per-track explanation scaffolding
- [Evaluation](docs/evaluation.md) — metrics, devset leaderboard
- [Mac / Local Dev](docs/mac_dev.md) — local testing on Apple Silicon
- [Modal Setup](docs/modal_setup.md) — cloud GPU authentication and smoke test
- [Codebase Map](docs/codebase/README.md) — **start here to understand the code**: per-module internals (`docs/codebase/modules/`), [end-to-end code paths](docs/codebase/code-paths.md), and the [verified-bugs audit](docs/codebase/bugs.md)

## Setup

```bash
uv venv .venv --python=3.10
source .venv/bin/activate
uv pip install -e .
uvx hf auth login   # HF access required for datasets + Llama
```

## Run

```bash
# Preferred: unified experiment command (local)
python run_experiment.py --backend local --tid v0plus_compiler_image_devset --batch_size 16

# Preferred: unified experiment command (Modal)
python run_experiment.py --backend modal --tid v0plus_compiler_all_retrievers_devset --batch_size 64

# Low-level inference scripts still work
python run_inference_devset.py --tid v0plus_compiler_image_devset --batch_size 16
python run_inference_blindset.py --tid v0plus_compiler_blindset_A --eval_dataset blindset_A --batch_size 16

# Package submission
bash prepare_submission.sh
```

Results saved to `exp/inference/{split}/{tid}.json`.

## Architecture notes

- v0+ catalog source of truth is LanceDB (`mcrs/qu_modules/v0plus_catalog_lance.py`). The HF-backed `HFTalkPlayCatalog` is retained only for unit tests.

## Extend

See `tips/` for directions: better item representations, reranker modules, generative retrieval.

## Skills

- `download-artifacts` — sync Modal prediction artifacts, rewrite traces, scores, and ground-truth files into `evaluator/exp` using `python modal/download_results.py`
- `run-experiment` — run a local or Modal experiment end-to-end with the unified `run_experiment.py` wrapper

## Experiments Workspace

- The experiment workspace is intentionally pruned. Do not treat deleted historical reports or `configs/archive/` as missing current context.
- Use [`experiments/README.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/README.md) for the current config/report surface.
- Use [`experiments/experiment_log.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/experiment_log.md) for the concise current-state decision log.
- [`leaderboard.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/leaderboard.md) is the compact devset table; [`changelog.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/changelog.md) links current outcomes to PRs.
- Keep only current configs under `configs/`: `v0plus_compiler_image_devset`, `v0plus_compiler_all_retrievers_devset`, and `v0plus_compiler_blindset_A`.
- If working inside `experiments/`, read the local [`experiments/CLAUDE.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/CLAUDE.md) and follow its prune-first conventions.
