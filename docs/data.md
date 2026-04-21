# Data

All data is loaded from Hugging Face at runtime. No local data files are committed to the repo.

HF collection: [talkpl-ai/talkplay-data-challenge](https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge)

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
    {"turn_number": 1, "role": "assistant", "content": "...", "thought": "..."},
    {"turn_number": 1, "role": "music",     "content": "<track_id>", "thought": null},
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
