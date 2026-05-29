# Evaluator Module Group

## Purpose

The `evaluator/` directory is the official offline scoring harness for the RecSys Challenge 2026 Music-CRS system. It sits **after** the inference pipeline: it reads a completed prediction file, compares each predicted ranked list to the held-out ground truth, and writes a structured score JSON plus a per-sample CSV.

Within the overall system the evaluator is a standalone subprocess, not an importable library. `run_experiment.py` (project root) calls it via `subprocess.run`; `modal/app.py` calls the same scripts inside the Modal cloud environment. `mcrs/analysis/retrieval_analysis.py` injects `evaluator/` onto `sys.path` directly so it can reuse `metrics.compute_recsys_metrics` for cohort-level analysis without running the full eval pipeline.

The harness operates on two filesystem contracts:

```
evaluator/exp/
  ground_truth/<split>.json          # generated once by make_ground_truth.py
  inference/<split>/<tid>.json       # written by run_inference_*.py
  scores/<split>/<tid>.json          # written by evaluate_devset.py
  scores/<split>/<tid>_samples.csv   # per-turn metrics, written by evaluate_devset.py
```

---

## Files

| File | Responsibility |
|------|---------------|
| `evaluator/make_ground_truth.py` | Downloads the HF TalkPlay dataset and extracts one `ground_truth_track_id` per (session, turn) into `exp/ground_truth/devset.json`. |
| `evaluator/evaluate_devset.py` | Main scoring script: loads ground truth + prediction file, calls metrics, prints a report, saves `exp/scores/<split>/<tid>.json` and `<tid>_samples.csv`. |
| `evaluator/metrics/__init__.py` | Re-exports `compute_recsys_metrics`, `compute_catalog_diversity`, `compute_lexical_diversity` as the package's public surface. |
| `evaluator/metrics/metrics_recsys.py` | Implements nDCG, Hit, Recall, Precision, MRR, MAP, and rank-finding primitives. |
| `evaluator/metrics/metrics_diversity.py` | Implements catalog-coverage and Distinct-2 lexical-diversity metrics. |
| `evaluator/readme.md` | Official challenge documentation: format contract, metric definitions, dataset table, baseline results. |

---

## Public API

These are the symbols other code in the project imports or invokes.

### `metrics/metrics_recsys.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `compute_recsys_metrics` | `(preds, gold, k_values, metrics=STANDARD_METRICS) -> dict[str, float]` | Thin alias for `compute_metrics`; computes all enabled metrics at all k values for a single (preds, gold) pair. Entry point used by `evaluate_devset.py` and `retrieval_analysis.py`. Lines 108–115. |
| `compute_metrics` | `(preds, gold, k_values, metrics=STANDARD_METRICS) -> dict[str, float]` | Core per-example scorer. Validates no duplicates, then dispatches to individual metric functions via `_STANDARD_METRIC_MAP`. Returns `{"ndcg@k": float, "hit@k": float, "recall@k": float, ...}`. Lines 118–144. |
| `get_ndcg` | `(gold, preds, k: int) -> float` | Standard nDCG@k with binary relevance. Uses `2^rel − 1 / log₂(i+1)` DCG formula. Lines 14–34. |
| `get_hit` | `(gold, preds, k: int) -> int` | Binary hit@k: 1 if any top-k prediction is in gold. Lines 37–40. |
| `get_reciprocal_rank` | `(gold, preds, k: Optional[int] = None) -> float` | Reciprocal rank of `gold` (a single item, not a set) in `preds`, optionally capped at k. Lines 43–56. |
| `get_rank` | `(gold, preds) -> int | None` | 1-based rank of first gold item in preds, or `None` if not found. Lines 100–106. |
| `STANDARD_METRICS` | `list[str]` | Sorted list `["hit", "ndcg", "recall"]`; governs which metrics `compute_metrics` runs by default. Line 97. |

### `metrics/metrics_diversity.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `compute_catalog_diversity` | `(list_of_recommendations: Sequence[str], catalog_size: int) -> float` | Fraction of the catalog covered: `len(unique recommended IDs) / catalog_size`. Lines 9–15. |
| `compute_lexical_diversity` | `(list_of_responses: Sequence[str], n: int = 2) -> float` | Distinct-n (default bigrams): unique n-grams ÷ total n-grams across all predicted text responses. Lines 18–38. |

### `evaluate_devset.py` — top-level functions

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `evaluate` | `(df_predictions: DataFrame, df_ground_truth: DataFrame) -> (DataFrame, dict)` | Core evaluation loop. Returns `(df_results, agg_dict)`. `df_results` has one row per (session, turn) with raw per-instance scores. `agg_dict` contains macro-averaged scalars plus internal `_recommended_20`, `_recommended_100`, `_responses` lists (consumed by `main`). Lines 131–246. |
| `print_report` | `(m: dict, tid: str) -> None` | Console-formatted report with ranking quality, retrieval coverage, diversity, and per-turn breakdown. Lines 249–293. |
| `main` | `(args: argparse.Namespace) -> None` | CLI entry point: loads files, calls `evaluate`, computes diversity, serialises score JSON and samples CSV. Lines 302–364. |

### `make_ground_truth.py`

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `make_ground_truth` | `(dataset_name: str, split: str, exp_dir: str | Path = "exp") -> None` | Downloads HF dataset, iterates sessions × turns 1–8, calls `parsing_groundtruth`, and writes `exp/ground_truth/devset.json`. Lines 33–48. |
| `parsing_groundtruth` | `(conversations: List[Dict], target_turn_number: int) -> Tuple[str, str]` | Extracts the ground-truth track ID (iloc[1]) and response text (iloc[2]) for a given turn from the raw conversation list. Lines 10–25. |

---

## Key Data Structures / Config

### Ground truth record (one element of `exp/ground_truth/devset.json`)

```json
{
  "session_id": "69137__2020-02-08",
  "user_id": "69137",
  "turn_number": 1,
  "ground_truth_track_id": "<uuid>"
}
```

Each session has exactly 8 records (turns 1–8). A single track ID is the ground truth per turn (not a set).

### Prediction record (one element of `exp/inference/<split>/<tid>.json`)

```json
{
  "session_id": "69137__2020-02-08",
  "user_id": "69137",
  "turn_number": 1,
  "predicted_track_ids": ["<uuid>", ...],
  "predicted_response": "Here are some songs you might enjoy."
}
```

Submission files use top-20 lists; dev-set runs may use up to 1000 for full diagnostic coverage.

### Aggregate score dict (written to `exp/scores/<split>/<tid>.json`)

Key fields:

| Field | Type | Notes |
|-------|------|-------|
| `n_turns_evaluated` | int | Total (session × turn) rows scored |
| `require_full_diagnostic_depth` | bool | Always `True`; signals 1000-item contract |
| `available_cutoffs` | list[int] | k values supported given minimum pool depth |
| `min_pool_depth` / `max_pool_depth` | int | Min/max len of `predicted_track_ids` across rows |
| `n_shallow_rows` | int | Rows with depth < 1000 |
| `ndcg@{k}` | float or null | For k ∈ {1,5,10,20,50,100,200,500,1000}; null if pool too shallow |
| `hit@{k}`, `recall@{k}` | float or null | Same cutoffs |
| `mrr`, `mrr@{100,200,500,1000}` | float or null | Mean reciprocal rank |
| `mean_rank_when_found`, `median_rank_when_found` | float or null | Rank diagnostics (only for turns where GT was retrieved) |
| `pct_gt_not_in_top{20,100,200,500,1000}` | float or null | Miss rates |
| `catalog_diversity` | float | Unique recommended IDs ÷ catalog size, at top-20 |
| `catalog_diversity@100` | float | Same at top-100 |
| `lexical_diversity` | float | Distinct-2 across predicted responses |
| `per_turn` | dict[str, dict] | Per-turn (1–8) `ndcg@20`, `hit@20`, `hit@100`, `n` |

### Module-level constants (`evaluate_devset.py`)

| Constant | Value | Purpose |
|----------|-------|---------|
| `K_VALUES` | `[1,5,10,20,50,100,200,500,1000]` | Full sweep cutoffs |
| `HEADLINE_K` | `[1,10,20]` | Leaderboard-comparable cutoffs |
| `MRR_K_VALUES` | `[100,200,500,1000]` | MRR truncation cutoffs |
| `REQUIRED_DIAGNOSTIC_DEPTH` | `1000` | `max(K_VALUES)`; minimum pool depth for full diagnostics |

---

## Internal Flow

1. **Ground truth generation** (`make_ground_truth.py`): `main` calls `make_ground_truth`, which streams the HF dataset and calls `parsing_groundtruth` for each (session, turn 1–8) pair. The function reads `conversations` as a DataFrame, selects by `turn_number`, and extracts `iloc[1]['content']` (track ID) and `iloc[2]['content']` (response). Output is written once to `exp/ground_truth/devset.json`.

2. **Prediction loading** (`evaluate_devset.py:main`): Reads `exp/inference/<split>/<tid>.json` into `df_predictions` and `exp/ground_truth/<split>.json` into `df_ground_truth`. Optionally filters to a subset of session IDs from `--session_ids_file`.

3. **Per-turn scoring loop** (`evaluate_devset.py:evaluate`): Iterates over every ground-truth row. For each row it:
   - Looks up the matching prediction row via `df_filtering` (exact match on `session_id` + `turn_number`).
   - Calls `compute_recsys_metrics(preds, [gt_id], K_VALUES)` → raw metric dict.
   - Calls `_null_unsupported_metrics` to replace metrics at cutoffs beyond `pred_depth` with `None`.
   - Calls `get_rank` and `get_reciprocal_rank` for MRR diagnostics.
   - Accumulates top-20 and top-100 track lists for diversity.
   - Appends a row to `rows`.

4. **Aggregation** (`evaluate_devset.py:evaluate`): Builds `df_results` from all rows. Groups by `turn_number` and calls `.mean()` to get per-turn averages (`df_turnwise`). Then computes the macro-average across turns for headline metrics. Emits `agg` dict with all scalar metrics plus internal `_recommended_20`, `_recommended_100`, `_responses` lists.

5. **Diversity computation** (`evaluate_devset.py:main`): After `evaluate` returns, `main` loads the HF catalog to get `total_catalog_size`, then calls `compute_catalog_diversity(recommended_20, ...)`, `compute_catalog_diversity(recommended_100, ...)`, and `compute_lexical_diversity(responses)`. Results are merged into `agg`.

6. **Output**: `agg` is written as `exp/scores/<split>/<tid>.json`; `df_results` is written as `exp/scores/<split>/<tid>_samples.csv`. `print_report` formats and prints the summary to stdout.

---

## Dependencies

### Other mcrs modules

| Module | Usage |
|--------|-------|
| `mcrs/analysis/retrieval_analysis.py` | Imports `compute_recsys_metrics`, `get_rank`, `get_reciprocal_rank` directly from `evaluator/metrics` by injecting `evaluator/` into `sys.path`. |
| `run_experiment.py` | Calls `evaluator/make_ground_truth.py` and `evaluator/evaluate_devset.py` as subprocesses via `run_command`. |
| `modal/app.py` | Runs both evaluator scripts inside the Modal container; sets `PYTHONPATH=/app/evaluator` so the `metrics` package is importable. |
| `modal/download_results.py` | Writes artifacts into `evaluator/exp/` so that `evaluate_devset.py` can find them. |

### External libraries

| Library | Usage |
|---------|-------|
| `numpy` | `np.log2` in nDCG, `np.mean`/`np.median` for aggregation, `np.nan` for missing ranks. |
| `scipy` | Imported in `metrics_recsys.py` (`from scipy import linalg`) but **never used**. Dead import. |
| `pandas` | DataFrames for predictions, ground truth, and per-sample results; `groupby` for per-turn aggregation. |
| `datasets` (HuggingFace) | `load_dataset` in both `make_ground_truth.py` (to pull TalkPlay train/test data) and `evaluate_devset.py` (to fetch track catalog size). Lazily imported in `main` to keep pure-metric tests import-free. |
| `tqdm` | Progress bars in both top-level scripts. |

---

## Gotchas

1. **`scipy.linalg` dead import** (`metrics_recsys.py:11`): `from scipy import linalg` is present but `linalg` is never referenced. This adds a dependency on `scipy` for no benefit and will fail if `scipy` is not installed.

2. **Single-item gold set per turn**: The ground truth is always a list with exactly one track ID (`[gt_id]`). Functions like `get_ndcg` and `get_hit` accept a collection, so the code is general, but `get_reciprocal_rank` (line 43) takes a single item `gold` (not a list) and calls `preds.index(gold)`. Passing a list of gold items to that function would silently fail.

3. **`parsing_groundtruth` positional slice assumption** (`make_ground_truth.py:23–24`): The function extracts `iloc[1]` and `iloc[2]` after filtering by `turn_number`. This relies on the raw conversation format always having the assistant recommendation as the second row and the response as the third row within each turn block. If the conversation schema changes, this will silently return wrong track IDs.

4. **Macro-averaging order**: The headline metrics are averaged first over sessions within each turn (via `groupby("turn_number").mean()`), then the per-turn means are averaged. This is documented as intentional to preserve backward compatibility with the published leaderboard. The deep-cutoff diagnostics use the same aggregation path, so they are also comparable.

5. **`evaluate_devset.py` is not importable as a library from the project root** without injecting `evaluator/` into `sys.path` first, because it imports `from metrics import ...` using a relative package name. `retrieval_analysis.py` and `modal/app.py` handle this with explicit `sys.path` manipulation.

6. **`catalog_diversity` is gated on `available_cutoffs`** (`evaluate_devset.py:325–333`): If the prediction pool is shallower than 20, `catalog_diversity` is set to `None` rather than computed from a partial list. This is the correct behaviour for the contest but means local test runs with very small stub files may produce null diversity values.

7. **`get_precision` and `get_average_precision` are implemented but excluded from `_STANDARD_METRIC_MAP`** (`metrics_recsys.py:90–96`): Both functions exist in the module and are commented out of the map. They are dead code — present for reference but not computed during evaluation.
