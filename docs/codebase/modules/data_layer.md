# Data Layer — Catalog, User, and Corpus Formatters

## Purpose

The data layer provides in-memory access to the two external HuggingFace datasets (track metadata and user metadata) and a pluggable formatter that serialises track fields into plain text for indexing and LLM prompts.

It sits at the bottom of the pipeline — below retrieval, LLM, and QU modules — and is consumed in two distinct contexts:

1. **Retrieval-time document formatting** (`corpus_formatters`): when a retrieval module (BM25, BERT dense, Milvus BM25) builds its text corpus it calls the formatter to convert each track's metadata dict into a single string that will be indexed or embedded.
2. **Inference-time metadata lookup** (`db_item`, `db_user`): after retrieval returns track IDs, `CRS_BASELINE` uses `MusicCatalogDB.id_to_metadata` to format the top-1 track for the LLM prompt, and `UserProfileDB.id_to_profile_str` to inject user demographics into the system prompt.

Neither `MusicCatalogDB` nor `UserProfileDB` write data; they are read-only in-memory indexes loaded once at construction time.

---

## Files

| File | Responsibility |
|---|---|
| `mcrs/db_item/music_catalog.py` | Loads the HF track-metadata dataset into a dict keyed by `track_id`; formats a track as a comma-separated field string for LLM prompts. |
| `mcrs/db_user/user_profile.py` | Loads the HF user-metadata dataset into a dict keyed by `user_id`; formats a user as `key: value\n` lines for personalization prompts. |
| `mcrs/corpus_formatters/base.py` | Stateless `DefaultFormatter` that serializes a metadata dict and a field-name list into `field: value\n` lines for indexing. |
| `mcrs/corpus_formatters/__init__.py` | Registry shim: exposes `load_corpus_formatter(formatter_type)` as the single public entry point. |
| `mcrs/db_item/__init__.py` | Re-exports `MusicCatalogDB`. |
| `mcrs/db_user/__init__.py` | Re-exports `UserProfileDB`. |

---

## Public API

### `MusicCatalogDB` (`mcrs/db_item/music_catalog.py:6`)

```python
class MusicCatalogDB:
    def __init__(
        self,
        dataset_name: str,       # HF dataset identifier, e.g. "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
        split_types: list[str],  # splits to concatenate, e.g. ["all_tracks"]
        corpus_types: list[str], # metadata fields to render, e.g. ["track_name", "artist_name", "album_name"]
    ): ...
```

**`id_to_metadata(track_id: str, use_semantic_id: bool = False) -> str`** (`music_catalog.py:17`)

Returns a single comma-separated string:
```
track_id: <uuid>, track_name: <val>, artist_name: <val>, album_name: <val>
```
The `corpus_types` list controls which fields appear after `track_id`. Values that are lists (e.g. `artist_name`) are joined with `", "` and lowercased. The `use_semantic_id` parameter is accepted but has no effect — it is unused in the body (dead parameter).

---

### `UserProfileDB` (`mcrs/db_user/user_profile.py:6`)

```python
class UserProfileDB:
    def __init__(
        self,
        dataset_name: str,      # HF dataset identifier, e.g. "talkpl-ai/TalkPlayData-Challenge-User-Metadata"
        split_types: list[str], # splits to concatenate, e.g. ["all_users"]
    ): ...
```

**`id_to_profile(user_id: str) -> dict`** (`user_profile.py:16`)

Returns the raw dataset row dict for the given user.

**`id_to_profile_str(user_id: str) -> str`** (`user_profile.py:20`)

Returns a newline-delimited string of `key: value` pairs for the fixed columns `['user_id', 'age_group', 'gender', 'country_name']`. Used by `CRS_BASELINE._get_system_prompt`.

---

### `DefaultFormatter` (`mcrs/corpus_formatters/base.py:1`)

```python
class DefaultFormatter:
    name = "default"

    def format(self, metadata: dict, corpus_types: list[str]) -> str: ...
```

Renders selected fields as `field: value\n` lines. List-valued fields are joined with `", "`. The string ends with a trailing newline. This is the canonical document format for BM25 and dense indexing.

---

### `load_corpus_formatter` (`mcrs/corpus_formatters/__init__.py:4`)

```python
def load_corpus_formatter(formatter_type: str) -> DefaultFormatter: ...
```

Registry entry point. Currently only `"default"` is supported; any other value raises `ValueError`. Used by retrieval modules that accept an optional injected formatter but fall back to this factory.

---

## Key Data Structures / Config

| Symbol | Location | Notes |
|---|---|---|
| `MusicCatalogDB.metadata_dict` | `music_catalog.py:15` | `dict[str, dict]` — `track_id` → raw HF row. Held in memory for the lifetime of the process. |
| `MusicCatalogDB.corpus_types` | `music_catalog.py:14` | `list[str]` — controls which fields `id_to_metadata` renders. Set from `CRS_BASELINE.corpus_types`, default `["track_name", "artist_name", "album_name"]`. |
| `UserProfileDB.user_profiles` | `user_profile.py:14` | `dict[str, dict]` — `user_id` → raw HF row. |
| `UserProfileDB.default_columns` | `user_profile.py:13` | Hard-coded to `['user_id', 'age_group', 'gender', 'country_name']`. No config path. |
| `DefaultFormatter.name` | `corpus_formatters/base.py:4` | `"default"` — used by `DENSE_TRANSFORMER_MODEL` to build a stable `corpus_name` for the on-disk cache key. |

There are no dataclasses or pydantic models in this group; all structures are plain Python dicts backed by HuggingFace `datasets.Dataset` rows.

---

## Internal Flow

The three sub-packages do not call each other. Each is used independently by the orchestration layer (`CRS_BASELINE`) and by retrieval modules. The only indirect coupling is:

1. **`CRS_BASELINE.__init__`** constructs both `MusicCatalogDB` and `UserProfileDB`, passing `item_db_name` / `track_split_types` / `corpus_types` to the item DB for response-context formatting. Active inference no longer constructs a separate CRS-level retrieval module.

2. **Retrieval modules** (`bert.py:62-77`, `litellm_embedding.py:45-59`) each call `load_corpus_formatter("default")` at construction time unless a custom formatter is injected. They then call `formatter.format(metadata, corpus_types)` for every track when building the index corpus.

3. **`CRS_BASELINE.chat` and `batch_chat`** call `item_db.id_to_metadata(retrieval_items[0])` (`crs_baseline.py:177, 265`) on the top-1 retrieved track ID, feeding the result as `recommend_item` into the LLM response-generation call.

4. **`CRS_BASELINE._get_system_prompt`** (`crs_baseline.py:132`) calls `user_db.id_to_profile_str(user_id)` and appends the result to the system prompt when a `user_id` is provided.

5. **`inference_utils.chat_history_parser`** (`inference_utils.py:19`) calls `music_crs.item_db.id_to_metadata(track_id)` to convert `role=music` turns (which store raw track IDs in the dataset) into human-readable metadata strings before feeding the history to the QU or LLM.

6. **`mcrs/milvus/indexing.py:215`** calls `load_corpus_formatter("default")` inside `render_bm25_text_fields` to build BM25 text fields for the Milvus schema — same formatter, same contract, but outside the normal `CRS_BASELINE` path.

---

## Dependencies

### External

| Library | Used by | Purpose |
|---|---|---|
| `datasets` (HuggingFace) | `music_catalog.py`, `user_profile.py` | `load_dataset` + `concatenate_datasets` to pull track/user metadata from HF Hub |
| `torch` | `music_catalog.py` (import only) | Imported at module top but not used — dead import |

### Internal `mcrs` modules

The data-layer modules themselves have **no inbound dependencies on other `mcrs` modules**. They are leaves in the dependency graph.

Callers of the data layer:

| Caller | What it uses |
|---|---|
| `mcrs.crs_baseline.CRS_BASELINE` | `MusicCatalogDB`, `UserProfileDB` |
| `mcrs.inference_utils.chat_history_parser` | `MusicCatalogDB.id_to_metadata` (via `music_crs.item_db`) |
| `mcrs.retrieval_modules.bert.DENSE_TRANSFORMER_MODEL` | `load_corpus_formatter` |
| `mcrs.retrieval_modules.litellm_embedding` | `load_corpus_formatter` |
| `mcrs.milvus.indexing` | `load_corpus_formatter` |

---

## Gotchas

1. **Dead import in `music_catalog.py`** (`music_catalog.py:2`): `import torch` is present at the top level but `torch` is never referenced in the file. It will trigger a GPU library load on import even in CPU-only environments.

2. **Dead parameter `use_semantic_id`** (`music_catalog.py:17`): `id_to_metadata` accepts `use_semantic_id: bool = False` but the parameter is never read — both branches produce the same output. Callers pass `False` (or omit it) and the flag has no effect.

3. **Duplicate HF dataset load for non-LanceDB paths**: `DENSE_TRANSFORMER_MODEL` and `MusicCatalogDB` each independently call `load_dataset(dataset_name)` and build their own `metadata_dict`. In v0+ production runs the catalog is served from LanceDB (`catalog_lance.py`) and `MusicCatalogDB` is only used for the `recommend_item` string passed to the LLM, so this duplication is acceptable but worth noting in refactors.

4. **Hard-coded user profile columns**: `UserProfileDB.default_columns` (`user_profile.py:13`) is a hard-coded list. There is no config path to render additional fields (e.g. `listening_history`) without editing the source.

5. **`DefaultFormatter` is the only formatter**: `load_corpus_formatter` will raise `ValueError` for any type other than `"default"`. The registry exists as an extension point but no alternative formatters have been registered yet.

6. **`MusicCatalogDB` lowercase behaviour**: `id_to_metadata` lowercases all field values (`music_catalog.py:22`), but `DefaultFormatter.format` does not lowercase. Code paths that use `MusicCatalogDB` (inference-time prompt) therefore receive lowercase text, while paths that use `DefaultFormatter` (index-build time) receive the original casing. This divergence is intentional per the original design but can cause subtle differences in retrieval vs. prompt text.
