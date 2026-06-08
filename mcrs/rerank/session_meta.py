"""Session-level metadata (user profile + conversation goal + date) for Tier-A reranker features.

The organizer challenge dataset (`talkpl-ai/TalkPlayData-Challenge-Dataset`) carries session-level
signals the conversation-state extractor drops: the listener's `conversation_goal`
(category/specificity), the `session_date`, and the inline `user_profile` (age, gender, country,
preferred language/culture). This module loads them keyed by `session_id` so the offline rerank
dataset builder can join them in by `session_id` — no trace regeneration, mirroring how block P
reused `track_feedback` already in the trace.

Only a flat, reranker-relevant subset is exposed (see ``SESSION_META_FIELDS``). `goal_progress_*`
and free-text `listener_goal`/`thought` are intentionally excluded (leakage / not reranker
features).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DATASET = "talkpl-ai/TalkPlayData-Challenge-Dataset"

# Flat group-record keys this module writes (consumed by features.py block U: Tier-A goal /
# age / gender + the Tier-B preferred_musical_culture match).
SESSION_META_FIELDS = (
    "goal_category", "goal_specificity", "session_date",
    "user_age", "user_gender", "user_country_code",
    # recorded for future Tier-B culture/language work; not used by Tier-A features
    "user_preferred_language", "user_preferred_musical_culture",
)


def _flatten(rec: dict[str, Any]) -> dict[str, Any]:
    """One session record -> flat reranker-relevant fields (``SESSION_META_FIELDS``)."""
    up = rec.get("user_profile") or {}
    cg = rec.get("conversation_goal") or {}
    return {
        "goal_category": cg.get("category"),
        "goal_specificity": cg.get("specificity"),
        "session_date": rec.get("session_date"),
        "user_age": up.get("age"),
        "user_gender": up.get("gender"),
        "user_country_code": up.get("country_code"),
        "user_preferred_language": up.get("preferred_language"),
        "user_preferred_musical_culture": up.get("preferred_musical_culture"),
    }


def flatten_session_row(row: dict[str, Any]) -> dict[str, Any]:
    """Public: flatten one raw session row ({user_profile, conversation_goal, session_date})
    to the flat reranker fields (``SESSION_META_FIELDS``).

    Used at **serve** time by the compiler to carry session context onto the reranker entry,
    and by the inference runners to stamp it onto trace records — so serve and training (which
    can also join offline via ``load_session_meta``) produce identical block-U inputs."""
    return _flatten(row)


def load_session_meta(dataset_name: str = DEFAULT_DATASET, split: str = "test",
                      offline: bool = True) -> dict[str, dict[str, Any]]:
    """``session_id -> flat session-meta dict`` from the challenge dataset (HF cache)."""
    import os

    if offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    from datasets import load_dataset

    ds = load_dataset(dataset_name, split=split)
    out: dict[str, dict[str, Any]] = {}
    for rec in ds:
        out[rec["session_id"]] = _flatten(rec)
    return out


def augment_groups_jsonl(in_path: str | Path, out_path: str | Path,
                         session_meta: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Copy a ``groups.jsonl`` adding the session-meta fields by ``session_id`` (fast, ~8k rows).

    Lets us add Tier-A fields to an existing rerank dataset without re-streaming the multi-GB
    trace. Rows whose session is missing from ``session_meta`` get the keys set to ``None``.
    """
    n, n_joined = 0, 0
    with open(in_path) as fh, open(out_path, "w") as out:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            g = json.loads(line)
            meta = session_meta.get(g.get("session_id"))
            if meta is not None:
                g.update(meta)
                n_joined += 1
            else:
                for k in SESSION_META_FIELDS:
                    g.setdefault(k, None)
            out.write(json.dumps(g) + "\n")
            n += 1
    return {"n_groups": n, "n_joined": n_joined}
