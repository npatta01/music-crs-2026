# Baseline Architecture: BM25 / BERT + Llama-3.2-1B

Two-stage pipeline: retrieve candidate tracks, then generate a natural language response.

---

## Pipeline

```
User Query + Chat History
        │
        ▼
┌───────────────────────────────────────────┐
│  Stage 1: Retrieval                        │
│                                            │
│  BM25  (mcrs/retrieval_modules/bm25.py)   │  ← sparse keyword matching
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

```python
crs = CRS_BASELINE(
    lm_type="meta-llama/Llama-3.2-1B-Instruct",
    retrieval_type="bm25",          # or "bert"
    item_db_name="talkpl-ai/TalkPlayData-Challenge-Track-Metadata",
    user_db_name="talkpl-ai/TalkPlayData-Challenge-User-Metadata",
    track_split_types=["all_tracks"],
    corpus_types=["track_name", "artist_name", "album_name", "release_date"],
    cache_dir="./cache",
    device="cuda",
    attn_implementation="sdpa",     # or "eager" / "flash_attention_2"
)

# Single turn
result = crs.chat(user_query="I want something chill", user_id="...")

# Batch (preferred for inference scripts)
results = crs.batch_chat([
    {"user_query": "...", "user_id": "...", "session_memory": [...]},
    ...
])
```

Return dict keys: `user_id`, `user_query`, `retrieval_items` (list[str], 20 ids), `recommend_item` (str), `response` (str).

---

## Retrieval Modules

### BM25 (`mcrs/retrieval_modules/bm25.py`)
- Sparse keyword matching using the `bm25s` library
- Index built from concatenated `corpus_types` fields for all 47,071 tracks
- Index cached to `cache/bm25/{corpus_name}/`
- **Devset NDCG@10: 0.0627** — best baseline

### BERT (`mcrs/retrieval_modules/bert.py`)
- Model: `bert-base-uncased`
- Mean-pooling over token embeddings (masked), then L2-normalize
- Similarity: cosine (dot product of normalized vectors)
- Embeddings cached to `cache/bert/{corpus_name}/embeddings.pt`
- **Devset NDCG@10: 0.0048**

Both expose the same interface:
```python
retrieval.text_to_item_retrieval(query: str, topk: int = 20) -> list[str]
retrieval.batch_text_to_item_retrieval(queries: list[str], topk: int = 20) -> list[list[str]]
```

New retrieval backends: add a class with these two methods and register in `mcrs/retrieval_modules/__init__.py`.

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

YAML files in `config/`. Provided configs:

| Config | Retrieval | Dataset |
|--------|-----------|---------|
| `llama1b_bm25_devset` | BM25 | dev set |
| `llama1b_bert_devset` | BERT | dev set |
| `llama1b_bm25_blindset_A` | BM25 | blind A |
| `llama1b_bert_blindset_A` | BERT | blind A |

Key YAML fields:

```yaml
lm_type: "meta-llama/Llama-3.2-1B-Instruct"
retrieval_type: "bm25"            # bm25 | bert
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

---

## Lower Bounds

| Script | Description |
|--------|-------------|
| `lowerbound/popularity.py` | Returns the same 20 most-popular tracks for every query |
| `lowerbound/random_sample.py` | Returns 20 randomly sampled tracks |
