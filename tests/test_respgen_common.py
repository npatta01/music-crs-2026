from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.respgen.offline_judge import aggregate_judge_scores, parse_judge_response
from scripts.respgen.judgepick import (
    build_judgepick_rows,
    judge_scores_by_key,
    promote_selected_safe_candidates,
)
from scripts.respgen.common import (
    build_variant_rows,
    distinct_n,
    extract_avoid_hints,
    heuristic_audit_row,
    load_traces,
    load_predictions,
    response_risk_flags,
    render_context,
    select_response_track,
    variant_flags_for_name,
    write_submission_zip,
)


def _write_prediction_zip(path: Path, rows: list[dict]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("prediction.json", json.dumps(rows))


def _dataset_row() -> dict:
    return {
        "session_id": "s1",
        "user_id": "u1",
        "user_profile": {
            "preferred_language": "English",
            "preferred_musical_culture": "Americana",
        },
        "conversation_goal": {
            "listener_goal": "discover new roots rock artists with gritty blues influence",
            "category": "J",
        },
        "conversations": [
            {"turn_number": 1, "role": "user", "content": "Play roots rock like The Wood Brothers."},
            {"turn_number": 1, "role": "music", "content": "t1"},
            {"turn_number": 1, "role": "assistant", "content": "Try this."},
            {
                "turn_number": 2,
                "role": "user",
                "content": "No more The Wood Brothers for now. Who else has that gritty Americana sound?",
            },
        ],
    }


def test_load_predictions_reads_codabench_zip(tmp_path: Path) -> None:
    rows = [{"session_id": "s1", "turn_number": 2, "predicted_track_ids": ["t1"], "predicted_response": "hi"}]
    path = tmp_path / "submission.zip"
    _write_prediction_zip(path, rows)

    assert load_predictions(path) == rows


def test_distinct_n_matches_whitespace_bigram_metric() -> None:
    responses = ["hello world hello world", "hello new world"]

    assert distinct_n(responses, n=2) == pytest.approx(4 / 5)


def test_render_context_includes_goal_language_and_recent_turns() -> None:
    context = render_context(
        _dataset_row(),
        {
            "listener_goal": True,
            "latest_user": True,
            "previous_user": True,
            "preferred_language": True,
        },
    )

    assert "Listener goal: discover new roots rock artists" in context
    assert "Preferred language: English" in context
    assert "Latest user request: No more The Wood Brothers" in context
    assert "Previous user request: Play roots rock like The Wood Brothers." in context


def test_extract_avoid_hints_finds_no_more_and_move_beyond_phrases() -> None:
    text = (
        "Please, no more The Wood Brothers for now. I want to move beyond Casseurs Flowters. "
        "Find artists other than Orelsan/Casseurs Flowters."
    )

    assert {"the wood brothers", "casseurs flowters", "orelsan"} <= extract_avoid_hints(text)


def test_select_response_track_skips_avoided_top_artist_without_promoting_ids() -> None:
    metadata = {
        "t1": {"artist_name": ["The Wood Brothers"], "track_name": ["Spirit"]},
        "t2": {"artist_name": ["Bryce Janey"], "track_name": ["Funky Guitar Blues"]},
    }

    selected = select_response_track(["t1", "t2"], metadata, {"the wood brothers"}, promote=False)

    assert selected.track_id == "t2"
    assert selected.changed is True
    assert selected.track_ids == ["t1", "t2"]


def test_select_response_track_can_promote_safe_candidate() -> None:
    metadata = {
        "t1": {"artist_name": ["The Wood Brothers"], "track_name": ["Spirit"]},
        "t2": {"artist_name": ["Bryce Janey"], "track_name": ["Funky Guitar Blues"]},
    }

    selected = select_response_track(["t1", "t2"], metadata, {"the wood brothers"}, promote=True)

    assert selected.track_id == "t2"
    assert selected.track_ids == ["t2", "t1"]


def test_heuristic_audit_flags_constraint_confession_and_overconfident_generic_reply() -> None:
    row = {
        "latest_user": "Please no more The Wood Brothers.",
        "predicted_response": (
            "I know you're looking to move beyond The Wood Brothers, and while Spirit has that "
            "perfect rootsy vibe, it's by the artist you specifically asked to avoid."
        ),
    }

    audit = heuristic_audit_row(row)

    assert audit["constraint_confession"] is True
    assert audit["overconfident"] is True
    assert audit["generic_word_count"] >= 2


def test_write_submission_zip_contains_single_prediction_json(tmp_path: Path) -> None:
    rows = [{"session_id": "s1", "turn_number": 2, "predicted_track_ids": ["t1"], "predicted_response": "hi"}]
    path = tmp_path / "out.zip"

    write_submission_zip(rows, path)

    with zipfile.ZipFile(path) as zf:
        assert zf.namelist() == ["prediction.json"]
        assert json.loads(zf.read("prediction.json")) == rows


def test_load_traces_indexes_by_session_and_turn(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text(
        json.dumps({"session_id": "s1", "turn_number": 2, "trace": {"extracted_state": {"turn_intent": "play blues"}}})
        + "\n",
        encoding="utf-8",
    )

    traces = load_traces(path)

    assert traces[("s1", 2)]["trace"]["extracted_state"]["turn_intent"] == "play blues"


def test_build_variant_rows_rejects_safe_candidate_without_promotion() -> None:
    base_rows = [
        {
            "session_id": "s1",
            "user_id": "u1",
            "turn_number": 2,
            "predicted_track_ids": ["t1", "t2"],
            "predicted_response": "old",
        }
    ]
    metadata = {
        "t1": {"artist_name": ["The Wood Brothers"], "track_name": ["Spirit"], "album_name": ["A"], "tag_list": ["folk"]},
        "t2": {"artist_name": ["Bryce Janey"], "track_name": ["Funky Guitar Blues"], "album_name": ["B"], "tag_list": ["blues"]},
    }

    def fake_generate(requests: list[dict]) -> list[str]:
        return ["new response"]

    with pytest.raises(ValueError, match="safe_candidate"):
        build_variant_rows(
            base_rows,
            {"s1": _dataset_row()},
            metadata,
            {
                "listener_goal": True,
                "latest_user": True,
                "safe_candidate": True,
                "trace_state": True,
                "item_format": "xml",
            },
            fake_generate,
            promote_response_track=False,
            trace_rows_by_key={
                ("s1", 2): {
                    "trace": {
                        "extracted_state": {
                            "turn_intent": "find new bluesy roots rock",
                            "mentioned_entities": [{"type": "tag", "value": "bluesy", "sentiment": 1}],
                            "track_feedback": [],
                            "explicit_rejections": [],
                        }
                    }
                }
            },
        )


def test_top1_response_variant_keeps_recommend_item_on_submitted_top_track() -> None:
    base_rows = [
        {
            "session_id": "s1",
            "user_id": "u1",
            "turn_number": 2,
            "predicted_track_ids": ["t1", "t2"],
            "predicted_response": "old",
        }
    ]
    metadata = {
        "t1": {"artist_name": ["The Wood Brothers"], "track_name": ["Spirit"], "album_name": ["A"], "tag_list": ["folk"]},
        "t2": {"artist_name": ["Bryce Janey"], "track_name": ["Funky Guitar Blues"], "album_name": ["B"], "tag_list": ["blues"]},
    }

    def fake_generate(requests: list[dict]) -> list[str]:
        assert requests[0]["selected_track_id"] == "t1"
        assert requests[0]["selection_changed"] is False
        assert "<recommended_track>" in requests[0]["recommend_item"]
        assert "Spirit" in requests[0]["recommend_item"]
        return ["new top-1 response"]

    rows = build_variant_rows(
        base_rows,
        {"s1": _dataset_row()},
        metadata,
        variant_flags_for_name("top1_concise_qwen"),
        fake_generate,
        promote_response_track=False,
    )

    assert rows[0]["predicted_track_ids"] == ["t1", "t2"]
    assert rows[0]["predicted_response"] == "new top-1 response"


def test_phase2_best_alias_points_to_latest_state_template() -> None:
    assert variant_flags_for_name("phase2_best_qwen") == variant_flags_for_name("top1_constraint_latest_state_qwen")


def test_anchor_replay_uses_state_only_context() -> None:
    base_rows = [
        {
            "session_id": "s1",
            "user_id": "u1",
            "turn_number": 2,
            "predicted_track_ids": ["t1"],
            "predicted_response": "old",
        }
    ]
    metadata = {
        "t1": {"artist_name": ["The Wood Brothers"], "track_name": ["Spirit"], "album_name": ["A"], "tag_list": ["folk"]},
    }

    def fake_generate(requests: list[dict]) -> list[str]:
        assert "find new bluesy roots rock" in requests[0]["context"]
        assert "Latest user request:" not in requests[0]["context"]
        assert "Previous user request:" not in requests[0]["context"]
        return ["replayed"]

    rows = build_variant_rows(
        base_rows,
        {"s1": _dataset_row()},
        metadata,
        variant_flags_for_name("anchor_replay"),
        fake_generate,
        trace_rows_by_key={
            ("s1", 2): {
                "trace": {
                    "extracted_state": {
                        "turn_intent": "find new bluesy roots rock",
                        "mentioned_entities": [{"type": "tag", "value": "bluesy", "sentiment": 1}],
                        "track_feedback": [],
                        "explicit_rejections": [],
                    }
                }
            }
        },
    )

    assert rows[0]["predicted_response"] == "replayed"


def test_build_variant_rows_promotes_safe_candidate_when_explicit() -> None:
    base_rows = [
        {
            "session_id": "s1",
            "user_id": "u1",
            "turn_number": 2,
            "predicted_track_ids": ["t1", "t2"],
            "predicted_response": "old",
        }
    ]
    metadata = {
        "t1": {"artist_name": ["The Wood Brothers"], "track_name": ["Spirit"], "album_name": ["A"], "tag_list": ["folk"]},
        "t2": {"artist_name": ["Bryce Janey"], "track_name": ["Funky Guitar Blues"], "album_name": ["B"], "tag_list": ["blues"]},
    }

    rows = build_variant_rows(
        base_rows,
        {"s1": _dataset_row()},
        metadata,
        {"safe_candidate": True, "item_format": "xml"},
        lambda requests: [f"recommend {requests[0]['selected_track_label']}"],
        promote_response_track=True,
    )

    assert rows[0]["predicted_track_ids"] == ["t2", "t1"]
    assert rows[0]["predicted_response"] == "recommend Funky Guitar Blues — Bryce Janey"


def test_response_risk_flags_queue_and_followup_are_diagnostics_not_no_followup_penalty() -> None:
    flags = response_risk_flags(
        {
            "predicted_response": (
                "I lined up a few options; first, try Perfect Song by Artist. "
                "Want more in this lane?"
            )
        },
        top_track_label="Different Song — Artist",
    )

    assert flags["playlist_or_queue_framing"] is True
    assert flags["generic_followup_question"] is True
    assert flags["overclaiming"] is True
    assert flags["possible_non_top_explanation"] is True
    assert "no_followup" not in heuristic_audit_row({"predicted_response": "Try Spirit by The Wood Brothers."})


def test_response_risk_flags_accepts_remix_suffix_title_match() -> None:
    flags = response_risk_flags(
        {
            "predicted_response": (
                'Try "You Make Me Feel Good" by Satin Jackets for a bright dance groove.'
            )
        },
        top_track_label="You Make Me Feel Good - Original Mix — Satin Jackets",
    )

    assert flags["possible_non_top_explanation"] is False


def test_parse_judge_response_accepts_top1_rubric_json_object() -> None:
    parsed = parse_judge_response(
        json.dumps(
            {
                "top1_faithfulness": 5,
                "latest_request_alignment": 4,
                "constraint_respect": 3,
                "grounded_explanation": 4.5,
                "language_match": 5,
                "response_quality": 4,
                "risk_flags": {"playlist_or_queue_framing": False},
                "notes": "grounded",
            }
        )
    )

    assert parsed == {
        "top1_faithfulness": 5.0,
        "latest_request_alignment": 4.0,
        "constraint_respect": 3.0,
        "grounded_explanation": 4.5,
        "language_match": 5.0,
        "response_quality": 4.0,
        "risk_flags": {"playlist_or_queue_framing": False},
        "notes": "grounded",
    }


def test_parse_judge_response_rejects_malformed_without_fake_score() -> None:
    assert parse_judge_response("not json") is None
    assert parse_judge_response(
        json.dumps(
            {
                "top1_faithfulness": 9,
                "latest_request_alignment": 1,
                "constraint_respect": 1,
                "grounded_explanation": 1,
                "language_match": 1,
                "response_quality": 1,
            }
        )
    ) is None


def test_aggregate_judge_scores_excludes_parse_failures() -> None:
    aggregate = aggregate_judge_scores(
        [
            {
                "top1_faithfulness": 4.0,
                "latest_request_alignment": 5.0,
                "constraint_respect": 3.0,
                "grounded_explanation": 4.0,
                "language_match": 5.0,
                "response_quality": 3.0,
                "risk_flags": {},
                "notes": "a",
            },
            None,
        ]
    )

    assert aggregate["n_scored"] == 1
    assert aggregate["n_failed"] == 1
    assert aggregate["mean_top1_faithfulness"] == 4.0
    assert aggregate["mean_combined"] == pytest.approx(4.0)


def test_build_judgepick_rows_keeps_base_unless_variant_scores_higher() -> None:
    base_rows = [
        {"session_id": "s1", "turn_number": 1, "predicted_track_ids": ["t1"], "predicted_response": "base one"},
        {"session_id": "s1", "turn_number": 2, "predicted_track_ids": ["t1"], "predicted_response": "base two"},
    ]
    variant_rows = [
        {"session_id": "s1", "turn_number": 1, "predicted_track_ids": ["t1"], "predicted_response": "variant one"},
        {"session_id": "s1", "turn_number": 2, "predicted_track_ids": ["t1"], "predicted_response": "variant two"},
    ]
    judge_report = {
        "rows": [
            {
                "session_id": "s1",
                "turn_number": 1,
                "judge": {"personalization": 5, "explanation": 4, "constraint_following": 3},
            }
        ]
    }

    variant_scores = judge_scores_by_key(judge_report)
    rows, selected, scores = build_judgepick_rows(
        base_rows,
        variant_rows,
        {("s1", 1): 3.0, ("s1", 2): 4.0},
        {**variant_scores, ("s1", 2): 3.5},
    )

    assert rows[0]["predicted_response"] == "variant one"
    assert rows[1]["predicted_response"] == "base two"
    assert selected == [("s1", 1)]
    assert scores == [pytest.approx(4.0), pytest.approx(4.0)]


def test_promote_selected_safe_candidates_only_changes_selected_rows() -> None:
    rows = [
        {"session_id": "s1", "turn_number": 2, "predicted_track_ids": ["t1", "t2"], "predicted_response": "picked"},
        {"session_id": "s1", "turn_number": 1, "predicted_track_ids": ["t1", "t2"], "predicted_response": "kept"},
    ]
    metadata = {
        "t1": {"artist_name": ["The Wood Brothers"], "track_name": ["Spirit"]},
        "t2": {"artist_name": ["Bryce Janey"], "track_name": ["Funky Guitar Blues"]},
    }

    promoted, promotions = promote_selected_safe_candidates(
        rows,
        {("s1", 2)},
        {"s1": _dataset_row()},
        metadata,
        traces=None,
    )

    assert promoted[0]["predicted_track_ids"] == ["t2", "t1"]
    assert promoted[1]["predicted_track_ids"] == ["t1", "t2"]
    assert promotions == [
        {
            "session_id": "s1",
            "turn_number": 2,
            "from": "t1",
            "to": "t2",
            "reason": "skipped_avoided_top_artist",
        }
    ]
