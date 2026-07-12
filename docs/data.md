# Data

All data is loaded from Hugging Face at runtime. No local data files are committed to the repo.

HF collection: [talkpl-ai/talkplay-data-challenge](https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge)

---

## Dataset Inventory

The challenge exposes more than the three core tables used by the baseline. As of this repo, the relevant Hugging Face datasets are:

| Dataset | Primary key | Split(s) used here | Purpose |
|-------|-------------|--------------------|---------|
| `talkpl-ai/TalkPlayData-Challenge-Dataset` | `session_id` | `train`, `test`, `blind_a`, `blind_b` | Conversations, turn labels, goals, and inline user profile snapshots |
| `talkpl-ai/TalkPlayData-Challenge-Track-Metadata` | `track_id` | `all_tracks` | Retrieval catalog and track-side metadata |
| `talkpl-ai/TalkPlayData-Challenge-User-Metadata` | `user_id` | `all_users` | Standalone demographic table for personalization |
| `talkpl-ai/TalkPlayData-Challenge-Track-Embeddings` | typically `track_id` | dataset-defined | Precomputed dense vectors for tracks |
| `talkpl-ai/TalkPlayData-Challenge-User-Embeddings` | typically `user_id` | dataset-defined | Precomputed dense vectors for users |

The baseline in this repo directly loads only the conversation, track metadata, and user metadata datasets. The embedding datasets are available for extensions such as dense retrieval, reranking, and user-track personalization, but they are not consumed by `CRS_BASELINE` out of the box.

> Some older tip docs still reference `TalkPlayData-2-*` dataset names. For challenge work, prefer the `TalkPlayData-Challenge-*` datasets listed above.

---

## Conversations

**Dataset**: `talkpl-ai/TalkPlayData-Challenge-Dataset`

| Split | Description |
|-------|-------------|
| `train` | 15,199 sessions for training / analysis |
| `test` | Development set (all 8 turns per session) |
| `blind_a` | Blind test A — only final turn provided |
| `blind_b` | Blind test B — released 15 June 2026 |

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | str | Unique session UUID |
| `user_id` | str | User UUID (joins to User Metadata) |
| `session_date` | str | Date of session (YYYY-MM-DD) |
| `user_profile` | dict | Inline user profile snapshot (see below) |
| `conversation_goal` | dict | Goal metadata for the session |
| `conversations` | list[dict] | Ordered list of turns |
| `goal_progress_assessments` | list[dict] | 8 assessments, one per turn |

**`user_profile` fields**: `age`, `age_group`, `country_code`, `country_name`, `gender`, `preferred_language`, `preferred_musical_culture`

**`conversation_goal` fields**: `category`, `specificity`, `listener_goal` (natural language description)

**Each turn in `conversations`**:
| Field | Type | Description |
|-------|------|-------------|
| `turn_number` | int | 1–8 |
| `role` | str | `"user"`, `"assistant"`, or `"music"` |
| `content` | str | Message text, or track_id when role is `"music"` |
| `thought` | str | Internal reasoning (assistant turns only) |

> `role="music"` turns carry the ground-truth `track_id` — this is the target for retrieval evaluation.

### Sample Row

```json
{
  "session_id": "9c337a02-15b1-408f-8103-c2f9459b3bed",
  "user_id": "64ea97af-bbc6-4756-ac94-b931048e5fef",
  "session_date": "2011-12-26",
  "user_profile": {
    "age": 20,
    "age_group": "20s",
    "country_code": "BR",
    "country_name": "Brazil",
    "gender": "female",
    "preferred_language": "English",
    "preferred_musical_culture": "Western Alternative Rock"
  },
  "conversation_goal": {
    "category": "H",
    "specificity": "LL",
    "listener_goal": "The listener wants to explore different artists and discover new songs..."
  },
  "conversations": [
    {"turn_number": 1, "role": "user",      "content": "...", "thought": null},
    {"turn_number": 1, "role": "music",     "content": "<track_id>", "thought": null},
    {"turn_number": 1, "role": "assistant", "content": "...", "thought": "..."},
    ...
  ],
  "goal_progress_assessments": [...]
}
```

---

## Track Metadata

**Dataset**: `talkpl-ai/TalkPlayData-Challenge-Track-Metadata`
**Split**: `all_tracks` — **47,071 tracks** (always use this split for retrieval)

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `track_id` | str | UUID, primary key |
| `track_name` | list[str] | Track title(s) |
| `artist_name` | list[str] | Artist name(s) |
| `album_name` | list[str] | Album name(s) |
| `tag_list` | list[str] | Genre/mood tags (up to 37) |
| `popularity` | float | Popularity score |
| `release_date` | str | YYYY-MM-DD |
| `duration` | int | Duration in milliseconds |
| `ISRC` | list[str] | International Standard Recording Code |
| `artist_id` | list[str] | Artist UUIDs |
| `album_id` | list[str] | Album UUIDs |

Fields indexed for retrieval are set via `corpus_types` in the YAML config (default: `track_name`, `artist_name`, `album_name`, `release_date`).

### Sample Row

```json
{
  "track_id": "97f5eeec-1ec7-4bb9-93e9-a948ee7466fc",
  "track_name": ["With Rainy Eyes"],
  "artist_name": ["Emancipator"],
  "album_name": ["Soon It Will Be Cold Enough"],
  "tag_list": ["relaxing", "experimental", "ambient", "lo-fi", "electronic", "instrumental", "..."],
  "popularity": 39.0,
  "release_date": "2006-12-06",
  "duration": 300920,
  "ISRC": ["TCABY1497179"],
  "artist_id": ["22f09759-f15c-475b-98aa-00d25e1ed50c"],
  "album_id": ["a204a441-3a18-435a-9652-0ab4192f0d63"]
}
```

---

## User Metadata

**Dataset**: `talkpl-ai/TalkPlayData-Challenge-User-Metadata`
**Split**: `all_users` — **8,772 users**

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | str | UUID, primary key |
| `age` | int | Exact age |
| `age_group` | str | Decade bucket (`"10s"`, `"20s"`, `"30s"`, …) |
| `country_code` | str | ISO 3166-1 alpha-2 |
| `country_name` | str | Full country name |
| `gender` | str | `"male"` or `"female"` |

Used by `UserProfileDB` to build a personalization string injected into the LLM system prompt.

### Sample Rows

```json
{"user_id": "5e51258a-27e3-4b49-aed9-10c9d05f139c", "age": 19, "age_group": "10s", "country_code": "BG", "country_name": "Bulgaria",      "gender": "female"}
{"user_id": "0c7e49b3-c87b-4759-8da2-cfd400af29bf", "age": 31, "age_group": "30s", "country_code": "US", "country_name": "United States", "gender": "male"}
```

---

## Embedding Datasets

Two additional Hugging Face datasets in the same collection provide precomputed dense vectors:

### Track Embeddings

**Dataset**: `talkpl-ai/TalkPlayData-Challenge-Track-Embeddings`
**Splits**: `all_tracks` (47,071 rows), `test_tracks` (7,411 rows)

This dataset is the track-side dense representation companion to `TalkPlayData-Challenge-Track-Metadata`. It is useful when you want to:

- replace lexical BM25 retrieval with vector similarity over the full catalog
- seed a two-stage retriever or reranker without recomputing track embeddings locally
- combine text retrieval scores with dense retrieval scores

In this repo, the nearest extension point is a custom retrieval or reranker module. See [tips/add_reranker.md](../tips/add_reranker.md) and [tips/improve_item_representation.md](../tips/improve_item_representation.md) for related directions.

#### Schema

| Field | Type | Description |
|-------|------|-------------|
| `track_id` | str | UUID, joins to `Track Metadata.track_id` |
| `audio-laion_clap` | list[float] | Audio embedding, length 512 |
| `image-siglip2` | list[float] | Image embedding, length 768 |
| `cf-bpr` | list[float] | Collaborative filtering embedding, length 128 |
| `attributes-qwen3_embedding_0.6b` | list[float] | Attribute-text embedding, length 1024 |
| `lyrics-qwen3_embedding_0.6b` | list[float] | Lyrics embedding, length 1024 |
| `metadata-qwen3_embedding_0.6b` | list[float] | Metadata-text embedding, length 1024 |

Some rows contain empty arrays for one or more modalities, so downstream code should not assume every field is populated.

#### Sample Row

```json
{
  "track_id": "97f5eeec-1ec7-4bb9-93e9-a948ee7466fc",
  "audio-laion_clap": [-0.052960943430662155, -0.015500283800065517, -0.00036561343586072326, "... 509 more"],
  "image-siglip2": [-0.008145928382873535, -0.3267313241958618, -0.16615962982177734, "... 765 more"],
  "cf-bpr": [0.0030792823527008295, 0.0032442151568830013, 0.0003919258888345212, "... 125 more"],
  "attributes-qwen3_embedding_0.6b": [1.0537109375, 1.7294921875, -1.029296875, "... 1021 more"],
  "lyrics-qwen3_embedding_0.6b": [-5.4453125, 7.6484375, -0.460205078125, "... 1021 more"],
  "metadata-qwen3_embedding_0.6b": [2.255859375, 2.40234375, -0.8056640625, "... 1021 more"]
}
```

### User Embeddings

**Dataset**: `talkpl-ai/TalkPlayData-Challenge-User-Embeddings`
**Splits**: `train` (8,591 rows), `test_warm` (371 rows), `test_cold` (129 rows)

This dataset provides dense user-side representations that can be paired with retrieved candidate tracks for personalization. Typical uses:

- score retrieved tracks by user-track similarity
- personalize reranking beyond the demographic fields in `User Metadata`
- cluster or analyze users offline for better retrieval strategies

The baseline currently uses only structured demographics from `User Metadata` to build the prompt-time personalization string. If you want to use user embeddings, you will need to add a module that loads them explicitly and merges them into retrieval or reranking.

#### Schema

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | str | UUID, joins to `User Metadata.user_id` |
| `cf-bpr` | list[float] | Collaborative filtering embedding, length 128 |

#### Sample Row

```json
{
  "user_id": "5e0690dc-ffcf-41c1-94e5-2fdafc4bd4ed",
  "cf-bpr": [0.0013940718490630388, -0.0011165891773998737, 0.000915041018743068, "... 125 more"]
}
```

### Practical Notes

- These embedding datasets are optional: nothing in the current baseline pipeline depends on them.
- The repo already contains a local dense retriever in [mcrs/retrieval_modules/bert.py](../mcrs/retrieval_modules/bert.py), but that module computes its own embeddings from track metadata rather than loading the precomputed challenge embeddings.
- When documenting or wiring a new module, join track embeddings on `track_id` and user embeddings on `user_id`.

---

## Inference Output Format

Results written to `exp/inference/{split}/{config_id}.json` — a JSON array where each element is one prediction:

```json
{
  "session_id": "9c337a02-15b1-408f-8103-c2f9459b3bed",
  "user_id":    "64ea97af-bbc6-4756-ac94-b931048e5fef",
  "turn_number": 3,
  "predicted_track_ids": [
    "97f5eeec-1ec7-4bb9-93e9-a948ee7466fc",
    "cdf6f46e-9399-499f-8347-ac5c98d1fe8a",
    "... (20 total)"
  ],
  "predicted_response": "I found a great match for you! ..."
}
```

> **Rule**: `predicted_track_ids` must always contain exactly 20 track IDs drawn from `all_tracks`. Never filter or subset the catalog.
