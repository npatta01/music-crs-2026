"""Tests for the reusable session-metadata plumbing (kept for future Tier-B work).

Covers the pure pieces that don't need the HF dataset: flattening a session record to the
reranker-relevant fields, and joining those fields into a groups.jsonl by session_id (the
``build_dataset`` offline-join path used `_flatten` + this augmenter).
"""

from __future__ import annotations

import json

from mcrs.rerank.build_dataset import build_group_record
from mcrs.rerank.session_meta import (
    SESSION_META_FIELDS,
    _flatten,
    augment_groups_jsonl,
    flatten_session_row,
)


def test_flatten_extracts_reranker_fields():
    rec = {
        "session_id": "s1",
        "session_date": "2020-06-01",
        "user_profile": {"age": 30, "gender": "male", "country_code": "US",
                         "preferred_language": "English",
                         "preferred_musical_culture": "Anglo-American Rock"},
        "conversation_goal": {"category": "J", "specificity": "HH", "listener_goal": "..."},
    }
    flat = _flatten(rec)
    assert set(flat) == set(SESSION_META_FIELDS)
    assert flat["goal_category"] == "J"
    assert flat["goal_specificity"] == "HH"
    assert flat["user_age"] == 30
    assert flat["user_gender"] == "male"
    assert flat["session_date"] == "2020-06-01"
    assert flat["user_preferred_musical_culture"] == "Anglo-American Rock"
    # listener_goal / goal_progress are intentionally not surfaced
    assert "listener_goal" not in flat


def test_flatten_handles_missing_subdicts():
    flat = _flatten({"session_id": "s", "session_date": None})
    assert set(flat) == set(SESSION_META_FIELDS)
    assert all(flat[k] is None for k in SESSION_META_FIELDS)


def test_augment_groups_joins_by_session_id(tmp_path):
    src = tmp_path / "groups.jsonl"
    with open(src, "w") as fh:
        fh.write(json.dumps({"session_id": "s1", "turn_number": 1}) + "\n")
        fh.write(json.dumps({"session_id": "missing", "turn_number": 1}) + "\n")
    meta = {"s1": {k: ("J" if k == "goal_category" else None) for k in SESSION_META_FIELDS}}
    out = tmp_path / "out.jsonl"
    stats = augment_groups_jsonl(src, out, meta)
    assert stats == {"n_groups": 2, "n_joined": 1}
    rows = [json.loads(l) for l in open(out)]
    assert rows[0]["goal_category"] == "J"
    # unmatched session still gets the keys (as None) so the schema stays stable
    assert all(k in rows[1] for k in SESSION_META_FIELDS)
    assert rows[1]["goal_category"] is None


_ROW = {
    "user_profile": {"age": 30, "gender": "male", "country_code": "US",
                     "preferred_language": "English",
                     "preferred_musical_culture": "Anglo-American Rock"},
    "conversation_goal": {"category": "J", "specificity": "HH", "listener_goal": "..."},
    "session_date": "2020-06-01",
}


def _bare_entry():
    return {"session_id": "s1", "user_id": "u1", "turn_number": 1,
            "trace": {"state": {}, "resolver": {}, "branches": {}}}


def test_build_group_record_serve_and_offline_join_parity():
    """Serve path (entry carries flat session_meta) and offline join (session_meta map by
    session_id) must populate identical block-U fields — the train/serve parity guarantee."""
    flat = flatten_session_row(_ROW)

    # offline / training: join by session_id
    rec_offline = build_group_record(_bare_entry(), gt_tid=None, session_meta={"s1": flat})
    # serve: compiler stamped entry["session_meta"] = flatten_session_row(session_context)
    entry_serve = _bare_entry()
    entry_serve["session_meta"] = flat
    rec_serve = build_group_record(entry_serve, gt_tid=None)

    for k in SESSION_META_FIELDS:
        assert rec_offline[k] == rec_serve[k] == flat[k], k
    assert rec_serve["goal_category"] == "J"
    assert rec_serve["user_preferred_musical_culture"] == "Anglo-American Rock"


def test_build_group_record_no_session_meta_is_neutral():
    rec = build_group_record(_bare_entry(), gt_tid=None)  # neither source -> fields absent
    assert all(k not in rec for k in SESSION_META_FIELDS)
