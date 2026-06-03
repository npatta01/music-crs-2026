# CLI Entrypoints

## Purpose

The CLI entrypoints are the outermost shell of the Music-CRS pipeline. They sit above every `mcrs.*` module: they parse user arguments, load YAML configs, instantiate the pipeline via `mcrs.load_crs_baseline`, drive batch inference over the HuggingFace test dataset, and persist results to `exp/inference/{split}/{tid}.json`.

Two levels of abstraction exist:

- **Unified wrapper** (`run_experiment.py`) — preferred entry point. Knows whether to call a local or Modal inference command, wires optional smoke-test subset generation, downloads Modal artifacts, and triggers the evaluator. Callers only need to know the task ID and backend.
- **Low-level inference scripts** (`run_inference_devset.py`, `run_inference_blindset.py`) — invoked directly or as sub-processes by the wrapper. They own the actual model load → dataset load → batch loop → JSON write sequence.
- **Streamlit explorer** (`streamlit_app.py`) — read-only browser UI for exploring saved prediction JSON files alongside ground truth. Does not run inference.
- **Submission packager** (`prepare_submission.sh`) — wraps a blindset prediction file into the ZIP format expected by the challenge server.

---

## Files

| File | Responsibility |
|---|---|
| `run_experiment.py` | Unified local/Modal orchestrator: resolves split, validates args, calls the right low-level script or Modal function, downloads results, and invokes the evaluator. |
| `run_inference_devset.py` | Low-level devset batch inference: loads config + model + all 8 turns per session, writes `exp/inference/devset/{tid}[{suffix}].json` and a `_trace.jsonl` sidecar. |
| `run_inference_blindset.py` | Low-level blindset batch inference: identical pipeline but uses only the last turn per session (no ground truth) and writes to `exp/inference/{eval_dataset}/{tid}.json`. |
| `streamlit_app.py` | Interactive prediction explorer: browses saved JSON predictions, displays per-turn and aggregate metrics (NDCG, Recall, MRR, Diversity, Distinct-N), and renders track cards alongside the conversation. |
| `prepare_submission.sh` | Packages a blindset prediction file as `submission/submission_{tid}_{date}.zip` for challenge upload. |

---

## Public API

These are the symbols called directly from the command line or imported by other modules (e.g. Modal app, tests).

### `run_experiment.py`

| Symbol | Signature | Description |
|---|---|---|
| `build_parser` | `() -> argparse.ArgumentParser` | Constructs the CLI argument parser for `run_experiment.py`. `run_experiment.py:21` |
| `resolve_split` | `(tid: str, eval_dataset: str | None) -> str` | Infers the evaluation split (`"devset"` or `"blindset_X"`) from the task ID or explicit override. `run_experiment.py:71` |
| `resolve_exp_dir` | `(exp_dir: str) -> Path` | Makes `exp_dir` absolute relative to `PROJECT_ROOT` if given as a relative path. `run_experiment.py:85` |
| `require_config` | `(tid: str) -> Path` | Asserts that `configs/{tid}.yaml` exists and returns its path; raises `FileNotFoundError` otherwise. `run_experiment.py:92` |
| `materialize_num_sessions_file` | `(tid: str, exp_dir: Path, num_sessions: int) -> str` | Samples `num_sessions` session IDs from the HF dataset and writes them to `exp/subsets/{tid}_num_sessions_{n}.json`. Returns the file path. `run_experiment.py:104` |
| `run_command` | `(cmd: list[str], cwd: Path | None) -> None` | Thin wrapper over `subprocess.run(..., check=True)`. `run_experiment.py:115` |
| `ensure_ground_truth` | `(exp_dir: Path) -> None` | Runs `evaluator/make_ground_truth.py` if `exp/ground_truth/devset.json` does not yet exist. `run_experiment.py:119` |
| `run_evaluation` | `(tid, exp_dir, split, session_ids_file) -> None` | Invokes `evaluator/evaluate_devset.py` as a subprocess. `run_experiment.py:134` |
| `validate_args` | `(args: argparse.Namespace, split: str) -> None` | Guards against invalid flag combinations (e.g. `--num_sessions` on blindset, mixing subset flags, Modal + `--session_ids_file`). `run_experiment.py:155` |
| `run_local` | `(args, split, exp_dir) -> None` | Executes a devset or blindset inference run locally, then evaluates for devset. `run_experiment.py:172` |
| `run_modal` | `(args, split, exp_dir) -> None` | Dispatches a Modal inference run, downloads artifacts, then evaluates for devset. `run_experiment.py:213` |
| `main` | `(argv: list[str] | None) -> int` | Top-level entry point. Returns exit code 0. `run_experiment.py:284` |

### `run_inference_devset.py`

| Symbol | Signature | Description |
|---|---|---|
| `main` | `(args: argparse.Namespace) -> None` | Core devset inference loop. Accepts a `Namespace` with `tid`, `batch_size`, `exp_dir`, `session_ids_file`, `num_sessions`, `num_shards`, `shard_id`, `output_suffix`, `clear_cache`. `run_inference_devset.py:65` |

The `main` function is also called directly by Modal workers and test harnesses that pass a `SimpleNamespace` — sharding fields (`num_shards`, `shard_id`, `output_suffix`) are read with `getattr(..., default)` for backward compatibility (`run_inference_devset.py:133–205`).

### `run_inference_blindset.py`

| Symbol | Signature | Description |
|---|---|---|
| `main` | `(args: argparse.Namespace) -> None` | Core blindset inference loop. Accepts `tid`, `eval_dataset`, `batch_size`, `exp_dir`, `clear_cache`, `num_shards`, `shard_id`, `output_suffix`. Sharding fields are read with `getattr(..., default)` for backward compatibility with programmatic callers (tests, Modal) that pass a `SimpleNamespace`. Each blindset row is one session; shards are contiguous index slices. No trace sidecar. `run_inference_blindset.py:23` |

### `streamlit_app.py`

These are module-level functions (not imported elsewhere, but documented for maintainability):

| Symbol | Signature | Description |
|---|---|---|
| `load_track_catalog` | `() -> dict` | Loads and caches `talkpl-ai/TalkPlayData-Challenge-Track-Metadata` keyed by `track_id`. `streamlit_app.py:46` |
| `load_ground_truth` | `() -> tuple[dict, dict]` | Loads devset sessions and builds a `(session_id, turn_number) -> track_id` ground-truth map. `streamlit_app.py:51` |
| `load_blind_sessions` | `() -> dict` | Loads blindset_A conversation sessions. `streamlit_app.py:64` |
| `load_predictions` | `(filepath: str) -> dict` | Loads a prediction JSON and keys it by `(session_id, turn_number)`. `streamlit_app.py:70` |
| `compute_aggregate_metrics` | `(predictions, ground_truth, track_meta) -> dict` | Full metric sweep: NDCG@k, Recall@k, MRR, MRR@k, Mean/Median rank, Catalog Diversity, Distinct-1/2, per-turn breakdown. `streamlit_app.py:224` |
| `validate_prediction_depths` | `(predictions) -> None` | Raises `ValueError` if any prediction has fewer than 1000 candidates (required for deep-cutoff diagnostics). `streamlit_app.py:136` |

---

## Key Data Structures / Config

### YAML Config (`configs/{tid}.yaml`)

Every inference run is governed by a YAML file. Required and commonly used keys (read at `run_inference_devset.py:86` and `run_inference_blindset.py:41`):

| Key | Type | Used by |
|---|---|---|
| `lm_type` | `str` | `load_crs_baseline` — LM model name/path |
| `retrieval_type` | `str` | `load_crs_baseline` — retrieval backend identifier |
| `qu_type` | `str` (default `"passthrough"`) | `load_crs_baseline` — query understanding module |
| `qu_kwargs` | `dict` | passed through `resolve_qu_kwargs_placeholders` |
| `item_db_name` | `str` | HF dataset name for track metadata |
| `user_db_name` | `str` | HF dataset name for user metadata |
| `track_split_types` | `list[str]` | dataset splits for track catalog |
| `user_split_types` | `list[str]` | dataset splits for user catalog |
| `corpus_types` | `list[str]` | text fields used to build the retrieval corpus |
| `cache_dir` | `str` | local path for retrieval index cache |
| `device` | `str` | `"cuda"` / `"cpu"` / `"mps"` |
| `attn_implementation` | `str` | passed to `transformers` (e.g. `"eager"`, `"flash_attention_2"`) |
| `dtype` | `str` (default `"bfloat16"`) | torch dtype string |
| `retrieval_topk` | `int` (default `20`) | number of candidates returned by the retriever |
| `retrieval_config` | `dict` | backend-specific retrieval parameters |
| `lm_kwargs` | `dict` | extra kwargs forwarded to the LM module |
| `test_dataset_name` | `str` (default `talkpl-ai/TalkPlayData-Challenge-Dataset`) | HF dataset for the test split |

### Session subset file (`exp/subsets/{tid}_num_sessions_{n}.json`)

```json
{
  "session_ids": ["<uuid>", "..."]
}
```

Written by `materialize_num_sessions_file` (`run_experiment.py:104`) and accepted by `run_inference_devset.py` via `--session_ids_file`.

### Inference output (`exp/inference/{split}/{tid}.json`)

List of records, one per `(session, turn)`:

```json
[
  {
    "session_id": "<uuid>",
    "user_id": "<uuid>",
    "turn_number": 3,
    "predicted_track_ids": ["<id>", ...],
    "predicted_response": "<text>"
  }
]
```

### Trace sidecar (`exp/inference/devset/{tid}_trace.jsonl`)

Written only by `run_inference_devset.py` (`run_inference_devset.py:209`). JSONL — one record per line, parallel to the main output (one line per predictions row, same order). The `trace` field is populated only when `V0PlusCompilerQU` is active; otherwise `null`.

```jsonl
{"session_id": "<uuid>", "user_id": "<uuid>", "turn_number": 3, "trace": { ... }}
{"session_id": "<uuid>", "user_id": "<uuid>", "turn_number": 4, "trace": { ... }}
```

---

## Internal Flow

### Unified local devset run (`python run_experiment.py --backend local --tid v0plus_compiler_image_devset`)

1. `main` (`run_experiment.py:284`) parses args, calls `require_config` to validate the config exists, `resolve_split` to determine `"devset"`, `validate_args` to check flag combinations.
2. `run_local` (`run_experiment.py:172`) is invoked. If `--num_sessions > 0`, `materialize_num_sessions_file` samples session IDs and writes a subset JSON.
3. `run_command` (`run_experiment.py:115`) spawns `python run_inference_devset.py --tid ... --batch_size ... [--session_ids_file ...]`.
4. Inside `run_inference_devset.main` (`run_inference_devset.py:65`): config is loaded, `load_crs_baseline` constructs the CRS pipeline, the HF dataset is loaded and optionally filtered, all sessions × 8 turns are materialized into flat `batch_data` + `metadata` lists, then processed in `batch_size` chunks via `music_crs.batch_chat`.
5. Results are written to `exp/inference/devset/{tid}.json`; trace sidecar to `exp/inference/devset/{tid}_trace.jsonl`.
6. Back in `run_local`: `ensure_ground_truth` runs `evaluator/make_ground_truth.py` if needed, then `run_evaluation` invokes `evaluator/evaluate_devset.py`.

### Unified Modal devset run (`python run_experiment.py --backend modal --tid ...`)

1. Steps 1–2 same as local.
2. `run_modal` (`run_experiment.py:213`) calls `modal run modal/app.py::run_inference` via subprocess (passes `--session-ids-json` if a subset was materialized).
3. After Modal completes, `modal/download_results.py` is called to sync artifacts into `exp/`.
4. `ensure_ground_truth` and `run_evaluation` are called as above.

### Low-level blindset run (`python run_inference_blindset.py --tid ... --eval_dataset blindset_A`)

1. Config loaded, pipeline constructed identically to devset.
2. Dataset loaded; **only the last turn** per session is used (blindset sessions have a single final turn, `run_inference_blindset.py:83`).
3. Results written to `exp/inference/{eval_dataset}/{tid}.json`; no trace sidecar.

### Submission packaging

```bash
bash prepare_submission.sh v0plus_compiler_blindset_A
```

1. Reads `exp/inference/blindset_A/{tid}.json`.
2. Copies it to `submission/prediction.json`.
3. Zips into `submission/submission_{tid}_{YYYYMMDD}.zip` and removes the staging file.

---

## Dependencies

### Internal `mcrs` modules

| Module | Used by |
|---|---|
| `mcrs.load_crs_baseline` (`mcrs/__init__.py`) | `run_inference_devset.py:11`, `run_inference_blindset.py:9` |
| `mcrs.inference_utils.chat_history_parser` | `run_inference_devset.py:16`, `run_inference_blindset.py:13` |
| `mcrs.inference_utils.resolve_qu_kwargs_placeholders` | `run_inference_devset.py:16`, `run_inference_blindset.py:13` |
| `mcrs.crs_baseline.CRS_BASELINE` | Instantiated indirectly via `load_crs_baseline` |

### External libraries

| Library | Purpose |
|---|---|
| `omegaconf` | YAML config loading and container conversion (`OmegaConf.load`, `to_container`) |
| `datasets` (HuggingFace) | Loading `TalkPlayData-Challenge-Dataset` and track/user metadata |
| `torch` | dtype resolution (`torch.bfloat16`, etc.) |
| `tqdm` | Batch progress bars |
| `litellm` | Optional disk cache for LLM extraction calls (devset script only) |
| `streamlit` | UI framework for the explorer app |
| `pandas`, `numpy`, `matplotlib` | Metric computation and display in `streamlit_app.py` |
| `modal` (CLI) | Invoked as a subprocess by `run_modal` |

### Evaluator scripts (called as subprocesses)

- `evaluator/make_ground_truth.py` — builds `exp/ground_truth/devset.json`
- `evaluator/evaluate_devset.py` — scores predictions against ground truth

---

## Gotchas

1. **`run_inference_devset.py` does not call `_setup_logging`/`_setup_litellm_cache` when imported programmatically** — these are only called inside `main()`. Modal workers and unit tests that call `main(SimpleNamespace(...))` directly get proper logging; the `__main__` block parses args and delegates to `main`.

2. **Sharding and `--num_sessions` are mutually exclusive** (`run_inference_devset.py:137–151`). Combining them raises `ValueError` because each shard would independently random-sample the corpus. The Modal sharded entry point (`modal/app.py::run_inference_sharded`) always passes `num_sessions=0`.

3. **`run_inference_blindset.py` has no trace sidecar** — it mirrors the devset script's sharding interface (`--num_shards`, `--shard_id`, `--output_suffix`, read with `getattr` defaults) but does not write a `_trace.json` sidecar. `_setup_logging` and `_setup_litellm_cache` are imported from `run_inference_devset` and called at the start of `main`.

4. **`--output_suffix` and `num_shards`/`shard_id` are read with `getattr` defaults** (`run_inference_devset.py:133–135`, `run_inference_devset.py:204–205`) — these arguments were added after the initial arg surface. Programmatic callers (tests, Modal) that pass a `SimpleNamespace` without these fields still work.

5. **`prepare_submission.sh` hard-codes `blindset_A`** in the `BLINDSET_DIR` path (`prepare_submission.sh:12`). Running it for a different blindset split (`blindset_B`, etc.) would require editing the script or passing an additional argument; currently only one split is supported.

6. **`streamlit_app.py` uses hard-coded relative paths** (`exp/inference/devset`, `exp/inference/blindset`) via `glob` — it must be launched from the repo root. It also hard-codes the `blind_a` HF split name (`streamlit_app.py:66`), which differs from the inference output subdirectory name `blindset_A`.

7. **`streamlit_app.py` computes metrics independently** from `evaluator/evaluate_devset.py`. The comment at `streamlit_app.py:83` acknowledges this: the evaluator submodule is canonical for leaderboard numbers.

8. **`resolve_qu_kwargs_placeholders`** (`mcrs/inference_utils.py:32`) rewrites `<tid>` tokens and `./exp/` / `exp/` prefixes in QU config strings to use the actual `--exp_dir` at runtime. This means QU configs that reference experiment artifacts (e.g. pre-compiled retrieval caches) are portable across non-default `--exp_dir` values.

9. **`_test_dataset_name`** (`run_experiment.py:99`) re-reads the config just to extract `test_dataset_name` for subset sampling — it loads the YAML a second time rather than sharing the config object already available in `run_local`/`run_modal`.
