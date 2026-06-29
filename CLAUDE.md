# Music-CRS

RecSys Challenge 2026 baseline — conversational music recommendation system. Given a multi-turn conversation, retrieve 20 tracks from a 47k-track catalog and generate a natural language response.

Challenge: https://nlp4musa.github.io/music-crs-challenge/

## Docs

- [Data](docs/data.md) — dataset schemas, splits, sample rows, inference output format
- [Baseline Architecture](docs/architectures/baseline.md) — pipeline, retrieval modules, LLM module, config
- [v10 State-Ranker Pipeline](docs/architectures/v0plus_retrieval.md) — retrievers, compiled state, explicit ranking stages, and final recommendation handoff for the `state_ranker_v10_*` path
- [Staged Experiment Pipeline](docs/architectures/staged_pipeline.md) — config-driven retrieval → rerank replay → explanation → evaluation runs for faster local iteration
- [Session State](docs/architectures/session_state.md) — the `ConversationStateV0Plus` schema, extract→resolve pipeline, and how each field drives retrieval
- [b1 Bi-Encoder](docs/architectures/biencoder.md) — the fine-tuned Qwen3-Embedding-4B two-tower conv→track retriever: input/output spec, training (MNRL/MOVES-only), and the `b1_cos` reranker feature + cache-first serving
- [Explanation / Response Generation](docs/architectures/explanation_generation.md) — how the natural-language response is generated, what the code was vs. is now doing (dummy), and per-track explanation scaffolding
- [State Extraction Cache](docs/state_extraction_cache.md) — file-per-turn cache layout, override precedence, GitHub Release packaging, and install/verify commands
- [Evaluation](docs/evaluation.md) — metrics, devset leaderboard
- [Reproduce the reranker](docs/reproduce_reranker.md) — **LambdaMART v10**: committed model bundle, required vs optional artifacts, FAST (use model) + FULL (retrain) paths
- [Mac / Local Dev](docs/mac_dev.md) — local testing on Apple Silicon
- [Modal Setup](docs/modal_setup.md) — cloud GPU authentication and smoke test
- [Codebase Map](docs/codebase/README.md) — **start here to understand the code**: per-module internals (`docs/codebase/modules/`) and the [verified-bugs audit](docs/codebase/bugs.md)
- [Anchoring-fix labels v1](data/anchor_labels_v1/README.md) — clean LLM-judged relevance labels (train + dev) for retraining the retriever against the anchoring bug; data files ship on the `anchor-labels-v1` GitHub release. Build pipeline: `scripts/rerank/anchor_labels/`

## Setup

```bash
uv venv .venv --python=3.10
source .venv/bin/activate
uv pip install -e .
uvx hf auth login   # HF access required for datasets + Llama
```

## Shared local caches

Local worktrees should share the large ignored artifacts instead of rebuilding
or redownloading them. Configure the shared cache-owner root once:

```bash
git config --global mcrs.sharedRoot /path/to/music-crs-cache-owner
```

In Codex worktrees on this machine, the standard cache-owner checkout is:

```bash
git config --global mcrs.sharedRoot /home/nidhin/projects/music-conversational-music-recomender-2026
```

Then, in any new worktree, run:

```bash
uv run python scripts/setup_worktree_cache.py
```

The script links `cache`, `exp/analysis/rerank`, and `.env` from the shared
root. It also accepts `--source /path/to/root` or `MCRS_SHARED_ROOT=/path/to/root`
instead of git config. If a local run is requested and these paths are missing,
run the setup script before trying to recompute artifacts. If a worktree already
has throwaway local cache artifacts from a failed run, use `--force` to replace
them with the shared links.

For state-cache materialization and release packaging, follow
[`docs/state_extraction_cache.md`](docs/state_extraction_cache.md). Blind sets
only need the final turn per session; devset and trainset use all turns. Use
`--skip-existing` so backfills do not redo existing files:

```bash
uv run python scripts/extract_state.py --tid state_ranker_v10_lgbm_blindset_A --turn-scope final --output-dir cache/state_extraction/blindset_A --skip-existing
uv run python scripts/extract_state.py --tid state_ranker_v10_lgbm_blindset_B --turn-scope final --output-dir cache/state_extraction/blindset_B --skip-existing
uv run python scripts/extract_state.py --tid state_ranker_v10_lgbm_devset --turn-scope all --output-dir cache/state_extraction/devset --skip-existing
```

Trainset has an existing extracted-state artifact at
`exp/state_extraction/deepseek_train_all.jsonl`; materialize it into
`cache/state_extraction/trainset` without making LiteLLM calls.

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

- The experiment workspace is intentionally pruned. Do not treat deleted historical reports or configs as missing current context.
- Use [`experiments/README.md`](experiments/README.md) for the current config/report surface.
- Use [`experiments/experiment_log.md`](experiments/experiment_log.md) for the concise current-state decision log.
- [`leaderboard.md`](leaderboard.md) is the compact devset table; [`changelog.md`](changelog.md) links current outcomes to PRs.
- Active configs under `configs/`: `state_ranker_v10_rrf_devset` (devset explicit RRF/candidate-fusion baseline), `state_ranker_v10_lgbm_devset` (devset LambdaMART v10; single canonical devset config — for fast local iteration export `MCRS_MAX_IN_FLIGHT=24` / `MCRS_COMPILE_MAX_IN_FLIGHT=8`), `state_ranker_v10_lgbm_blindset_A` / `state_ranker_v10_lgbm_blindset_B` (blindset LambdaMART v10; B uses the goal-free `reranker_v12_goalfree` bundle). Pipeline configs live under `configs/pipelines/`. Note the three version axes: pipeline lineage `state_ranker_v10`, feature-schema `lgbm_v10` (`model_version`), and the trained-bundle directory (`reranker_v10`, `reranker_v12_goalfree`) are independent counters.
- If working inside `experiments/`, read the local [`experiments/CLAUDE.md`](experiments/CLAUDE.md) and follow its prune-first conventions.
