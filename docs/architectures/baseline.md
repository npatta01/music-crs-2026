# Legacy Baseline Architecture: BM25 / BERT + Llama-3.2-1B

For a separate Milvus retrieval extension, see [Milvus Architecture](./milvus.md).

Historical two-stage pipeline: retrieve candidate tracks, then generate a
natural language response. Current competition configs use the v10 state-ranker
full-pipeline QU instead; see [v10 State-Ranker Pipeline](./v0plus_retrieval.md).

---

## Pipeline

```
User Query + Chat History
        │
        ▼
┌───────────────────────────────────────────┐
│  Stage 0: Query Understanding             │
│                                           │
│  Passthrough / deterministic QU /         │
│  llm_rewrite                              │
│  (mcrs/qu_modules/)                       │
│                                           │
│  Returns retrieval query text             │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Stage 1: Retrieval                        │
│                                            │
│  BM25  (removed standalone backend)       │  ← historical sparse baseline
│    or                                      │
│  BERT  (mcrs/retrieval_modules/bert.py)   │  ← dense cosine similarity
│                                            │
│  Returns top-20 track_ids                 │
└───────────────────────────────────────────┘
        │
        ▼
  MusicCatalogDB.id_to_metadata(track_ids[0])
  (mcrs/db_item/music_catalog.py)
        │
        ▼
┌───────────────────────────────────────────┐
│  Stage 2: Response Generation             │
│                                           │
│  Llama-3.2-1B-Instruct                   │
│  (mcrs/lm_modules/llama.py)              │
│                                           │
│  Input:                                   │
│    system_prompt  ← roleplay.txt          │
│                   + response_generation.txt│
│                   + personalization.txt   │
│                   + user_profile_str      │
│    chat_history   ← full conversation     │
│    recommend_item ← top-1 track metadata  │
│                                           │
│  Output: natural language response        │
└───────────────────────────────────────────┘
        │
        ▼
  {predicted_track_ids: [...20 ids],
   predicted_response: "..."}
```

---

## Orchestrator

**`CRS_BASELINE`** — `mcrs/crs_baseline.py`

Active runs normally construct `CRS_BASELINE` through `run_inference_devset.py`,
`run_inference_blindset.py`, or `run_experiment.py` using the YAML configs under
`configs/`. Direct construction is possible, but the QU must be a full-pipeline
QU with valid `qu_kwargs`; for examples, use `state_ranker_v10_rrf_devset` or
`state_ranker_v10_lgbm_devset`.

Return dict keys: `user_id`, `user_query`, `retrieval_items` (list[str], 20 ids), `recommend_item` (str), `response` (str).

---

## Retrieval Modules

### Corpus document format (shared by historical BM25 and BERT)

Both modules call `_stringify_metadata()` to convert each track into a text document for indexing:

```
track_name: With Rainy Eyes
artist_name: Emancipator
album_name: Soon It Will Be Cold Enough
release_date: 2006-12-06
```

Fields included = `corpus_types` from the YAML config (default: `track_name`, `artist_name`, `album_name`, `release_date`). List-valued fields are joined with `", "`. The index name / cache key is the underscore-joined `corpus_types` string (e.g. `track_name_artist_name_album_name_release_date`).

### Query format

By default, the retrieval query is the **full conversation history** up to and including the current user turn, formatted as:

```
user: I want something chill and relaxing
assistant: Here are some ambient tracks...
user: maybe something with piano?
```

Each turn is `role: content`, joined by `\n`. This format is still produced by
`CRS_BASELINE.chat()` / `batch_chat()`, but active configs pass it to a
full-pipeline QU rather than to a standalone retrieval module.

### Query-understanding modules (`mcrs/qu_modules/`)

These older QU modules predate the full-pipeline state ranker and return plain
text queries. They are retained for tests and historical ablations, but
`CRS_BASELINE` now requires a QU that returns track IDs directly via
`compile_track_ids` or `batch_compile_track_ids`.

`llm_rewrite` is a retrieval-facing backend for query-rewrite experiments. It:

- starts from the same passthrough conversation text
- prompts a small instruction model to emit exactly one `QUERY:` line
- falls back to the raw passthrough query if generation or parsing fails
- writes optional sidecars for audit and aggregate stats when `audit_path` / `stats_path` are configured

Supported `qu_kwargs`:

```yaml
qu_type: "llm_rewrite"
qu_kwargs:
  model_name: "HuggingFaceTB/SmolLM2-1.7B-Instruct"
  prompt_name: "preserve_entities_v1"
  max_new_tokens: 96
  audit_path: "./exp/inference/devset/<tid>_rewrite_audit.jsonl"
  stats_path: "./exp/inference/devset/<tid>_rewrite_stats.json"
```

`<tid>` placeholders in `qu_kwargs` paths are expanded by the inference scripts before the CRS is instantiated.

---

### BM25 (removed standalone backend)

The old CRS-level `retrieval_type: bm25` backend was removed from the current
tree. Use Git history for the historical standalone implementation. Active v10
configs still use BM25-style text search inside LanceDB through the
full-pipeline state-ranker compiler; that is a separate path.

**Indexing:**
- Tokenizes each track's corpus document with `bm25s.tokenize(corpus)`
- Saves index to `cache/bm25/{corpus_name}/` (BM25 model + `track_ids.json`)

**Querying:**
- Lowercases the query: `bm25s.tokenize([query.lower()])`
- Returns top-k track IDs by BM25 score

**Devset NDCG@10: 0.0627** — best baseline

### BERT (`mcrs/retrieval_modules/bert.py`)

**Indexing:**
- Model: `bert-base-uncased`
- Tokenizes each document: `max_length=128`, padding + truncation
- Mean-pools token embeddings over non-padding tokens (masked mean)
- L2-normalizes each embedding: `F.normalize(pooled, p=2, dim=1)`
- Saves `embeddings.pt` [47071, 768] + `track_ids.json` to `cache/bert/{corpus_name}/`
- Embedding batch size: 32

**Querying:**
- Embeds the query string the same way (tokenize → mean-pool → L2-normalize)
- Scores all tracks: `scores = embeddings @ query_emb` (dot product = cosine sim because both are L2-normalized)
- Returns top-k track IDs by score

**Devset NDCG@10: 0.0048**

### LiteLLM embedding (`mcrs/retrieval_modules/litellm_embedding.py`)

Optional path that calls a hosted embedding model (OpenAI / OpenRouter) through
a local LiteLLM proxy instead of running a transformer locally. See
[../litellm_proxy.md](../litellm_proxy.md) for setup and the available models.

---

### LLM context string (Stage 2 input)

After retrieval, `MusicCatalogDB.id_to_metadata()` formats the top-1 track for the LLM:

```
track_id: 97f5eeec-...
track_name: With Rainy Eyes
artist_name: Emancipator
album_name: Soon It Will Be Cold Enough
release_date: 2006-12-06
```

Line-oriented via the shared corpus formatter, with an additional `track_id`
line so downstream adapters can recover played-track IDs from music turns.

---

### Interface

The legacy standalone retrievers expose the same API:

```python
retrieval.text_to_item_retrieval(query: str, topk: int = 20) -> list[str]
retrieval.batch_text_to_item_retrieval(queries: list[str], topk: int = 20) -> list[list[str]]
```

For standalone retriever tooling, add a class with these two methods and
register it in `mcrs/retrieval_modules/__init__.py`. Current inference configs
do not route through this factory.

---

## LLM Module

**`LLAMA_MODEL`** — `mcrs/lm_modules/llama.py`

- Model: `meta-llama/Llama-3.2-1B-Instruct` (default, swappable via config)
- Uses `apply_chat_template()` for instruction format
- Attention options: `eager` (default), `sdpa` (faster, built-in), `flash_attention_2` (requires CUDA + flash-attn)

```python
lm.response_generation(sys_prompt, chat_history, recommend_item, max_new_tokens=512) -> str
lm.batch_response_generation(sys_prompts, chat_histories, recommend_items, max_new_tokens=64) -> list[str]
```

New LLM backends: implement these two methods and register in `mcrs/lm_modules/__init__.py`.

For retrieval-only experiments, you can still use an LLM-backed QU with `lm_type: "dummy"`. In that setup, the response generator is disabled while the QU backend still loads its own rewrite model.

---

## System Prompts (`mcrs/system_prompts/`)

Three composable text files concatenated at runtime:

| File | Content |
|------|---------|
| `roleplay.txt` | "You are an expert music recommendation assistant..." |
| `response_generation.txt` | Instructions: base response on retrieved track, explain match, invite follow-up |
| `personalization.txt` | "Consider the following user profile (age, country, gender)..." |

Final prompt = `roleplay` + `response_generation` + `personalization` + `user_profile_str` (if user_id provided).

---

## Database Modules

| Class | File | Purpose |
|-------|------|---------|
| `MusicCatalogDB` | `mcrs/db_item/music_catalog.py` | `track_id → metadata string` for LLM context |
| `UserProfileDB` | `mcrs/db_user/user_profile.py` | `user_id → profile string` for system prompt |

---

## Configuration

Runnable experiment YAML files live in `configs/`. The working tree keeps only
current configs; older experiment YAMLs were pruned and are available through
Git history.

| Config | Retrieval | Dataset |
|--------|-----------|---------|
| `state_ranker_v10_rrf_devset` | v10 state-ranker, explicit candidate fusion/RRF | dev set |
| `state_ranker_v10_lgbm_devset` | v10 state-ranker, LambdaMART final stage | dev set |
| `state_ranker_v10_lgbm_blindset_A` | v10 state-ranker, LambdaMART final stage | blind set A |

Key YAML fields:

```yaml
lm_type: "meta-llama/Llama-3.2-1B-Instruct"
qu_type: "state_ranker"           # active configs require a full-pipeline QU
qu_kwargs: {}                     # full-pipeline retrieval/ranking settings
corpus_types:                     # fields used for retrieval index
  - "track_name"
  - "artist_name"
  - "album_name"
  - "release_date"
track_split_types:
  - "all_tracks"                  # REQUIRED — never change this
device: "cuda"
attn_implementation: "sdpa"       # eager | sdpa | flash_attention_2
```

Wave 3 rewrite experiments use the sparse control corpus:

```yaml
corpus_types:
  - "track_name"
  - "artist_name"
  - "album_name"
  - "tag_list"
```

---

## Lower Bounds

| Script | Description |
|--------|-------------|
| `lowerbound/popularity.py` | Returns the same 20 most-popular tracks for every query |
| `lowerbound/random_sample.py` | Returns 20 randomly sampled tracks |
