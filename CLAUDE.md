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
python run_experiment.py --backend local --tid llama1b_bm25_devset --batch_size 16

# Preferred: unified experiment command (Modal)
python run_experiment.py --backend modal --tid llama1b_bm25_devset --batch_size 16

# Low-level inference scripts still work
python run_inference_devset.py --tid llama1b_bm25_devset --batch_size 16
python run_inference_blindset.py --tid llama1b_bm25_blindset_A --eval_dataset blindset_A --batch_size 16

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

- Use [`experiments/README.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/README.md) as the main index for experiment reports, analysis packages, current bests, and status.
- Use [`experiments/experiment_log.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/experiment_log.md) for cross-run takeaways, decisions, and next steps.
- [`leaderboard.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/leaderboard.md) is the ranked devset table (by NDCG@20); [`changelog.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/changelog.md) is the hybrid code+experiment log with PR links.
- When a run lands, follow the **Maintenance Checklist** in [`experiments/CLAUDE.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/CLAUDE.md) to keep report, log, index, leaderboard, and changelog in sync.
- If working inside `experiments/`, read the local [`experiments/CLAUDE.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/CLAUDE.md) and follow its conventions for report naming, analysis packaging, and status updates.
