# Music-CRS

RecSys Challenge 2026 baseline — conversational music recommendation system. Given a multi-turn conversation, retrieve 20 tracks from a 47k-track catalog and generate a natural language response.

Challenge: https://nlp4musa.github.io/music-crs-challenge/

## Docs

- [Data](docs/data.md) — dataset schemas, splits, sample rows, inference output format
- [Baseline Architecture](docs/architectures/baseline.md) — pipeline, retrieval modules, LLM module, config
- [v10 State-Ranker Pipeline](docs/architectures/v0plus_retrieval.md) — retrievers, compiled state, explicit ranking stages, and final recommendation handoff for the `state_ranker_v10_*` path
- [Staged Experiment Pipeline](docs/architectures/staged_pipeline.md) — config-driven retrieval → rerank replay → explanation → evaluation runs for faster local iteration
- [Session State](docs/architectures/session_state.md) — the `ConversationStateV0Plus` schema, extract→resolve pipeline, and how each field drives retrieval
- [Explanation / Response Generation](docs/architectures/explanation_generation.md) — how the natural-language response is generated, what the code was vs. is now doing (dummy), and per-track explanation scaffolding
- [Evaluation](docs/evaluation.md) — metrics, devset leaderboard
- [Reproduce the reranker](docs/reproduce_reranker.md) — **LambdaMART v10**: committed model bundle, required vs optional artifacts, FAST (use model) + FULL (retrain) paths
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
# Devset — explicit RRF candidate-fusion baseline (local)
python run_experiment.py --backend local --tid state_ranker_v10_rrf_devset --batch_size 16

# Devset — explicit RRF candidate-fusion baseline (Modal, 50 shards default)
python run_experiment.py --backend modal --tid state_ranker_v10_rrf_devset --batch_size 64

# Devset — LambdaMART v10 reranker (Modal)
python run_experiment.py --backend modal --tid state_ranker_v10_lgbm_devset --batch_size 8

# Devset — staged local iteration: RRF retrieval, LambdaMART replay, dummy explanation, eval
python run_pipeline.py --config configs/pipelines/state_ranker_v10_lgbm_devset.yaml

# Reuse an existing staged retrieval run and replay rerank/eval only
python run_pipeline.py --config configs/pipelines/state_ranker_v10_lgbm_devset.yaml --from rerank --retrieval-run exp/pipeline/runs/<run_id> --run-id <rerank_run_id>

# Blindset — LambdaMART v10 reranker (Modal)
python run_experiment.py --backend modal --tid state_ranker_v10_lgbm_blindset_A --eval_dataset blindset_A --batch_size 8

# Low-level inference scripts still work
python run_inference_devset.py --tid state_ranker_v10_rrf_devset --batch_size 16
python run_inference_blindset.py --tid state_ranker_v10_lgbm_blindset_A --eval_dataset blindset_A --batch_size 16

# Package submission
bash prepare_submission.sh state_ranker_v10_lgbm_blindset_A
```

`--num_shards` defaults to 50 for `--backend modal`, 1 for local. Local devset runs may set `--num_shards > 1` with `--num_workers` to run session shards in parallel.

Results saved to `exp/inference/{split}/{tid}.json`.

## Architecture notes

- v10 catalog source of truth is LanceDB (`mcrs/qu_modules/v0plus_catalog_lance.py`). The HF-backed `HFTalkPlayCatalog` is retained only for unit tests.
- State extraction uses `prompt_version: v1` (ConversationStateV1 → projected to V0Plus) in all active configs. Use `prompt_version: v0plus` to switch to the old generous V0Plus extraction.
- LambdaMART v10 reranker (`mcrs/qu_modules/lgbm_reranker.py`) is config-driven via `qu_kwargs.ranking.mode: lgbm`. Set `ranking.mode: rrf` for the explicit candidate-fusion baseline.
- `run_pipeline.py` is the faster iteration path: retrieval/state extraction can be saved once, then local LambdaMART replay/evaluation can be rerun from the saved trace. Model training stays outside the pipeline config.

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
- Active configs under `configs/`: `state_ranker_v10_rrf_devset` (devset explicit RRF/candidate-fusion baseline), `state_ranker_v10_lgbm_devset` (devset LambdaMART v10), `state_ranker_v10_lgbm_devset_fastlocal` (higher-concurrency local devset variant), `state_ranker_v10_lgbm_blindset_A` (blindset LambdaMART v10). Pipeline configs live under `configs/pipelines/`.
- If working inside `experiments/`, read the local [`experiments/CLAUDE.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/CLAUDE.md) and follow its prune-first conventions.
