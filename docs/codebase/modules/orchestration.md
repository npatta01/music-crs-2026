# Pipeline Orchestration & Services

## Purpose

This module group wires together and drives the end-to-end CRS pipeline.
`CRS_BASELINE` is the central integration point: it instantiates the QU module,
the retrieval module, the LM module, and both catalog databases, then drives a
single turn or a batch of turns through the full QU → retrieval → generation
chain.  `inference_utils` provides stateless helpers used by the top-level
inference scripts (`run_inference_devset.py`, `run_inference_blindset.py`) to
parse raw conversation data and resolve per-run config placeholders before
constructing `CRS_BASELINE`.  `RetrievalService` is a thin composable wrapper
used by the Modal cloud service to expose a retriever (plus optional embedder)
behind a uniform interface.  `retrieval_analysis` is an offline evaluation
library that loads saved prediction files, scores them against ground truth, and
supports diagnostic utilities such as RRF fusion and failure inspection.
`dashboard.py` is the entry point for the Streamlit evaluation UI.

Within the broader architecture these modules sit at the outermost layer: above
the QU, retrieval, and LM modules but below the top-level scripts and Modal
app.

---

## Files

| File | Responsibility |
|------|---------------|
| `mcrs/crs_baseline.py` | `CRS_BASELINE` class — single-turn and batch orchestrator for QU + retrieval + LM. |
| `mcrs/inference_utils.py` | Stateless helpers: conversation history parsing and QU config placeholder resolution. |
| `mcrs/retrieval_services/service.py` | `RetrievalService` dataclass — provider-neutral facade over a retriever and optional embedding client. |
| `mcrs/analysis/retrieval_analysis.py` | Offline evaluation library: load runs, score against ground truth, RRF fusion, failure views. |
| `mcrs/dashboard.py` | `main()` entry point that spawns the Streamlit app via `music-dashboard` CLI. |

---

## Public API

### `mcrs/__init__.py` — top-level factory

```python
load_crs_baseline(
    lm_type="meta-llama/Llama-3.2-1B-Instruct",
    retrieval_type="bm25",
    qu_type="passthrough",
    item_db_name: str = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata",
    user_db_name: str = "talkpl-ai/TalkPlayData-Challenge-User-Metadata",
    track_split_types: list[str] = ["all_tracks"],
    user_split_types: list[str] = ["all_users"],
    corpus_types: list[str] = ["track_name", "artist_name", "album_name"],
    cache_dir: str = "./cache",
    device: str = "cuda",
    attn_implementation: str = "eager",
    dtype=None,
    retrieval_topk: int = 20,
    retrieval_config: dict | None = None,
    qu_kwargs=None,
    lm_kwargs=None,
) -> CRS_BASELINE
```
Thin factory exported from `mcrs/__init__.py` (line 6). Resolves `dtype` to
`torch.bfloat16` when omitted and constructs a fully initialised `CRS_BASELINE`.
Called by both inference scripts.

---

### `mcrs/crs_baseline.py` — `CRS_BASELINE`

**`__init__`** (`crs_baseline.py:31`) — Loads all four subsystems: LM
(`load_lm_module`), retrieval (`load_retrieval_module`), QU (`load_qu_module`),
item catalog (`MusicCatalogDB`), and user profiles (`UserProfileDB`). Also
reads the three system-prompt templates from `mcrs/system_prompts/`.

**`chat(user_query, user_id=None) -> dict`** (`crs_baseline.py:136`) — Single-turn CRS step.
Appends the user query to `session_memory`, builds the system prompt, runs
retrieval (or delegates to `qu.compile_track_ids` for v0+ QUs), resolves the
top-1 item metadata, and calls `lm.response_generation`. Returns a dict with
keys `user_id`, `user_query`, `retrieval_items`, `recommend_item`, `response`.

**`batch_chat(batch_data) -> list[dict]`** (`crs_baseline.py:188`) — Batch variant
of `chat`. Accepts a list of dicts each containing `user_query`, optional
`user_id`, and `session_memory`. Uses `batch_compile_track_ids` /
`batch_text_to_item_retrieval` / `batch_response_generation` when available,
falling back to sequential loops otherwise. Output dicts include an extra
`trace` key populated from `qu.last_traces` when the QU is `V0PlusCompilerQU`.

**`_get_system_prompt(user_id=None) -> str`** (`crs_baseline.py:123`) — Concatenates
role-play and response-generation prompt templates; appends the personalization
template plus a user profile string when `user_id` is given.

**`_reset_session_memory()`** (`crs_baseline.py:113`) — Clears `self.session_memory`.

**`_upload_session_memory(chat_history)`** (`crs_baseline.py:118`) — Replaces
`self.session_memory` wholesale from pre-built history.

---

### `mcrs/inference_utils.py`

**`chat_history_parser(conversations, music_crs, target_turn_number) -> (list[dict], str)`**
(`inference_utils.py:7`) — Converts the raw per-session conversation list from
the dataset into a `(chat_history, user_query)` pair ready for `batch_chat`.
Turns with `role == "music"` are resolved from track IDs to metadata strings
via `music_crs.item_db.id_to_metadata`. Turns with `turn_number >= target_turn_number`
are excluded.

**`resolve_qu_kwargs_placeholders(qu_kwargs, tid, exp_dir=None) -> dict`**
(`inference_utils.py:32`) — Recursively walks a QU kwargs dict (which may be
deeply nested) and replaces the literal `<tid>` token with the current
experiment ID. Also rewrites relative `./exp/` or `exp/` path strings to
absolute paths under `exp_dir` when provided. Used to late-bind file paths into
QU configs at inference time.

---

### `mcrs/retrieval_services/service.py` — `RetrievalService`

**`RetrievalService(retriever, embedding_client=None)`** (`service.py:9`) — Dataclass
wrapping any retriever that implements `retrieve(query, topk)` /
`retrieve_batch(queries, topk)` and an optional `EmbeddingClient`.

**`retrieve(query, topk) -> list[str]`** (`service.py:15`) — Delegates to
`self.retriever.retrieve`.

**`retrieve_batch(queries, topk) -> list[list[str]]`** (`service.py:18`) — Delegates to
`self.retriever.retrieve_batch`.

**`embed_batch(texts) -> list[list[float]]`** (`service.py:21`) — Delegates to
`self.embedding_client.embed_batch`; raises `RuntimeError` if no client is
configured.

---

### `mcrs/analysis/retrieval_analysis.py`

**`load_run(split, tid, exp_dir=None) -> pd.DataFrame`** (`retrieval_analysis.py:100`) —
Reads `evaluator/exp/inference/{split}/{tid}.json` and returns a normalised
prediction DataFrame with columns `session_id`, `turn_number`,
`predicted_track_ids`, `predicted_response`, `tid`.

**`load_ground_truth(split="devset", exp_dir=None) -> pd.DataFrame`**
(`retrieval_analysis.py:112`) — Reads `evaluator/exp/ground_truth/{split}.json`.

**`evaluate_run(df_predictions, df_ground_truth, k_values=None) -> (pd.DataFrame, dict)`**
(`retrieval_analysis.py:128`) — Joins predictions to ground truth, calls
`compute_recsys_metrics` for each turn, computes MRR and macro-averaged
NDCG/Hit/Recall at each K in `K_VALUES = [20, 100, 200, 500, 1000]`. Returns
a per-turn result DataFrame and an aggregate metrics dict.

**`rrf_fuse_runs(run_dfs, source_tids, rrf_k=60, topk=1000) -> pd.DataFrame`**
(`retrieval_analysis.py:225`) — Reciprocal Rank Fusion across two or more
prediction DataFrames with identical `(session_id, turn_number)` coverage.

**`compute_pairwise_complementarity(run_a_instances, run_b_instances, run_a_name, run_b_name, k=1000) -> pd.DataFrame`**
(`retrieval_analysis.py:191`) — Merges two result DataFrames and labels each
turn as `A_only`, `B_only`, or `both_or_neither` based on hit-at-K status.

**`build_failure_view(df_predictions, track_meta, session_id, turn_number, gold_track_id) -> dict`**
(`retrieval_analysis.py:301`) — Returns a diagnostic dict with the gold track
metadata, its rank in the prediction list, and full metadata for the top-20
candidates. `track_meta` may be either a DataFrame or a `dict[str, Any]`.

---

### `mcrs/dashboard.py`

**`main()`** (`dashboard.py:11`) — CLI entry point registered as the `music-dashboard`
console script. Locates `streamlit_app.py` at the project root and launches it
via `streamlit run`.

---

## Key Data Structures / Config

**`CRS_BASELINE` constructor parameters** — All constructor parameters are
stored as instance attributes. The most consequential:
- `qu_type` / `qu_kwargs`: selects and configures the QU module; v0+
  compiler configs embed nested dicts with `<tid>` placeholder paths.
- `retrieval_type` / `retrieval_config`: selects BM25, LanceDB, or Modal-backed
  retrieval. `retrieval_config` is merged with a `device` default.
- `retrieval_topk` (default 20): how many track IDs to return per turn.

**`batch_chat` input schema** — Each dict in `batch_data` must have:
```python
{"user_query": str, "user_id": str | None, "session_memory": list[dict]}
```
`session_memory` items follow the `{"role": str, "content": str}` chat format.

**`batch_chat` output schema** — Each result dict has:
```python
{
    "user_id": str | None,
    "user_query": str,
    "retrieval_items": list[str],     # track IDs, length ≤ retrieval_topk
    "recommend_item": dict | None,    # metadata for retrieval_items[0], or None
    "response": str,                  # LM-generated text
    "trace": dict | None,             # v0+ QU diagnostic trace, else None
}
```

**Prediction DataFrame schema** (normalised by `_normalize_prediction_df`):

| Column | Type | Required |
|--------|------|---------|
| `session_id` | str | yes |
| `turn_number` | int | yes |
| `predicted_track_ids` | list[str] | yes |
| `predicted_response` | str | added if missing |
| `tid` | str | added from arg |

**`K_VALUES`** (`retrieval_analysis.py:24`) — Module-level constant `[20, 100, 200, 500, 1000]`
used as default K values for all metric computations.

**`DEFAULT_EXP_DIR`** (`retrieval_analysis.py:14`) — `<repo_root>/evaluator/exp`.
All prediction and ground-truth path helpers default to this directory.

---

## Internal Flow

1. **Inference script** calls `load_crs_baseline(...)` (via `mcrs/__init__.py`)
   which constructs `CRS_BASELINE` and initialises all subsystems.

2. **Per-session loop**: the inference script calls `chat_history_parser`
   (`inference_utils.py:7`) to convert raw dataset conversations into a
   `(chat_history, user_query)` pair.

3. **`CRS_BASELINE.batch_chat`** is called with a list of prepared dicts.
   Internally it:
   - Builds per-item system prompts via `_get_system_prompt` (which may call
     `user_db.id_to_profile_str`).
   - Dispatches retrieval through one of three paths (in priority order):
     a. `qu.batch_compile_track_ids` — v0+ full-pipeline QU (bypasses
        `self.retrieval` entirely).
     b. `qu.compile_track_ids` called sequentially — single-session v0+ QU.
     c. `qu.batch_transform_queries` → `retrieval.batch_text_to_item_retrieval`
        — classic two-step QU + retriever.
   - Looks up metadata for the top-1 retrieved track via `item_db.id_to_metadata`.
   - Calls `lm.batch_response_generation` (or falls back to sequential
     `lm.response_generation`).
   - Collects `qu.last_traces` (v0+ only) and pads to match batch length.

4. **Modal cloud path**: `modal/app.py:ModalRetrievalService` wraps a LanceDB
   retriever inside `RetrievalService` (`retrieval_services/service.py`) and
   exposes `retrieve` / `retrieve_batch` / `embed_batch` methods that the
   `modal_lancedb` retrieval module delegates to.

5. **Offline analysis**: notebooks and `experiments/` scripts call
   `load_run` + `load_ground_truth` + `evaluate_run` from `retrieval_analysis`
   to score saved prediction files without re-running inference.

6. **Dashboard**: `mcrs.dashboard.main` launches `streamlit_app.py` which has
   its own `load_ground_truth` helper (not the one in `retrieval_analysis`) and
   reads prediction JSON files directly.

---

## Dependencies

**Internal mcrs modules used by this group:**

| Dependency | Used by |
|-----------|---------|
| `mcrs.lm_modules.load_lm_module` | `crs_baseline.py` |
| `mcrs.retrieval_modules.load_retrieval_module` | `crs_baseline.py` |
| `mcrs.qu_modules.load_qu_module` | `crs_baseline.py` |
| `mcrs.db_item.MusicCatalogDB` | `crs_baseline.py` |
| `mcrs.db_user.UserProfileDB` | `crs_baseline.py` |
| `mcrs.embeddings.base.EmbeddingClient` (Protocol) | `retrieval_services/service.py` |
| `evaluator/metrics.compute_recsys_metrics` | `retrieval_analysis.py` (sys.path insert) |
| `evaluator/metrics/metrics_recsys.get_rank`, `get_reciprocal_rank` | `retrieval_analysis.py` |

**External libraries:**

| Library | Used by |
|---------|---------|
| `torch` | `crs_baseline.py` (dtype default) |
| `pandas` | `inference_utils.py`, `retrieval_analysis.py` |
| `numpy` | `retrieval_analysis.py` |
| `streamlit` (subprocess) | `dashboard.py` |
| `inspect` (stdlib) | `crs_baseline.py` (signature introspection) |
| `pathlib`, `json` (stdlib) | `retrieval_analysis.py` |

---

## Gotchas

1. **`compile_track_ids` completely bypasses `self.retrieval`** (`crs_baseline.py:156`).
   Any QU module that defines `compile_track_ids` (currently `V0PlusCompilerQU`)
   owns the entire retrieve pipeline; the `self.retrieval` attribute is
   constructed but never called in these runs. This is easy to miss when
   reading the config.

2. **Signature introspection for `user_id`/`user_ids`** (`crs_baseline.py:157-166`,
   `crs_baseline.py:225-234`). `CRS_BASELINE` uses `inspect.signature` at
   inference time to decide whether to forward user IDs. This means a QU module
   that wants user-aware retrieval must declare the parameter explicitly in its
   function signature.

3. **Empty retrieval list is silently converted to `recommend_item=None`**
   (`crs_baseline.py:177`, `crs_baseline.py:264-266`). The code does not
   backfill with popularity or any other fallback, so the LM sees `None` and
   evaluation records zero hits. This is intentional (see comment) but could be
   surprising when debugging low-retrieval runs.

4. **`batch_traces` padding** (`crs_baseline.py:278-280`). Non-v0+ QUs do not
   populate `qu.last_traces`, so the list is padded with `None` to match batch
   length. Downstream code reading `result["trace"]` must handle `None`.

5. **`retrieval_analysis` inserts `evaluator/` onto `sys.path`** at import time
   (`retrieval_analysis.py:17-19`). This couples the analysis module to the
   on-disk layout of the `evaluator/` package and can cause confusing import
   errors if the module is imported from a different working directory.

6. **`dashboard.py` is a one-line shim**. `mcrs/dashboard.py` only delegates to
   `streamlit_app.py` at the project root; all dashboard logic lives in
   `streamlit_app.py`, which defines its own `load_ground_truth` function that
   is not the same as `mcrs.analysis.retrieval_analysis.load_ground_truth`.

7. **`RetrievalService` is only used in the Modal path**. The class is not
   touched by `CRS_BASELINE` itself; it is instantiated inside
   `modal/app.py:ModalRetrievalService` to wrap LanceDB + SigLIP embedding
   clients before exposing them via Modal's RPC mechanism.

8. **`_upload_session_memory` / `_reset_session_memory` are interactive-mode
   helpers** only. The batch inference path never calls them; each call to
   `batch_chat` receives `session_memory` as part of the input dict and builds
   fresh local lists.
