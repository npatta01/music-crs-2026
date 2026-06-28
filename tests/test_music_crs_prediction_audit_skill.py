import importlib.util
import sys
from pathlib import Path


def load_audit_module():
    root = Path(__file__).resolve().parents[1]
    path = root / ".claude/skills/music-crs-prediction-audit/scripts/audit_submission_predictions.py"
    spec = importlib.util.spec_from_file_location("audit_submission_predictions", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_state_judge_prompt_is_diagnostic_and_state_focused():
    audit = load_audit_module()
    row = {
        "session_id": "s1",
        "turn_number": 2,
        "latest_user_text": "No more Beatles, give me a different artist.",
        "conversation_goal": None,
        "conversation": [
            {"role": "user", "turn_number": 1, "content": "Play something by The Beatles."},
            {"role": "music", "turn_number": 1, "content": "track_beatles"},
            {"role": "user", "turn_number": 2, "content": "No more Beatles, give me a different artist."},
        ],
        "intent_mode": "switch",
        "request_type": "attribute_search",
        "retrieval_profile": "feature_search",
        "routing_tags": ["feature_articulation"],
        "state_excerpt": {
            "exclusions": [],
            "facts": [{"role": "current_target", "value": "The Beatles"}],
            "resolver": {"rejected_artist_ids": []},
        },
    }
    catalog = audit.Catalog(
        {
            "track_beatles": {
                "track_name": "Come Together",
                "artist_name": "The Beatles",
            }
        }
    )

    prompt = audit.build_state_judge_prompt(row, catalog)

    assert "No more Beatles" in prompt
    assert "Come Together -- The Beatles" in prompt
    assert '"current_target"' in prompt
    assert "Candidate recommendations" not in prompt
    assert "Top submitted recommendation" not in prompt
    assert '"missing_constraints"' in prompt
    assert '"extra_or_stale_state"' in prompt


def test_state_judge_cache_key_changes_with_rendered_state():
    audit = load_audit_module()
    catalog = audit.Catalog({})
    row = {
        "session_id": "s1",
        "turn_number": 2,
        "latest_user_text": "No more Beatles.",
        "conversation": [{"role": "user", "turn_number": 2, "content": "No more Beatles."}],
        "state_excerpt": {"exclusions": []},
        "routing_tags": ["feature_articulation"],
    }
    changed = {
        **row,
        "state_excerpt": {"exclusions": [{"value": "The Beatles"}]},
    }

    first = audit.state_judge_cache_key(row, catalog, "model-a")
    second = audit.state_judge_cache_key(changed, catalog, "model-a")

    assert first != second


def test_judge_verdict_labels_are_user_facing():
    audit = load_audit_module()

    assert audit.verdict_label("recommendation", "good") == "strong fit"
    assert audit.verdict_label("recommendation", "bad") == "bad fit"
    assert audit.verdict_label("explanation", "weak") == "thin"
    assert audit.verdict_label("explanation", "bad") == "misleading"
    assert audit.verdict_label("state", "good") == "accurate"
    assert audit.verdict_label("state", "bad") == "inaccurate"


def test_recommendation_and_state_judges_auto_only_for_label_free_trace_audits():
    audit = load_audit_module()
    old_argv = sys.argv
    try:
        sys.argv = ["audit_submission_predictions.py", "--tid", "state_ranker_v10_lgbm_blindset_B"]
        args = audit.parse_args()
        assert args.llm_judge is None
        assert args.llm_state_judge is None

        sys.argv = [
            "audit_submission_predictions.py",
            "--tid",
            "state_ranker_v10_lgbm_blindset_B",
            "--no-llm-judge",
            "--no-llm-state-judge",
        ]
        args = audit.parse_args()
        assert args.llm_judge is False
        assert args.llm_state_judge is False
    finally:
        sys.argv = old_argv

    assert audit.should_run_default_judge(
        None,
        has_ground_truth=False,
    )
    assert not audit.should_run_default_judge(
        None,
        has_ground_truth=True,
    )
    assert audit.should_run_default_judge(
        None,
        has_ground_truth=False,
        requires_trace=True,
        has_trace=True,
    )
    assert not audit.should_run_default_judge(
        None,
        has_ground_truth=False,
        requires_trace=True,
        has_trace=False,
    )
    assert not audit.should_run_default_judge(
        True,
        has_ground_truth=True,
        requires_trace=True,
        has_trace=True,
    )


def test_recommendation_judge_prompt_identifies_submitted_rank_one():
    audit = load_audit_module()
    row = {
        "session_id": "s1",
        "turn_number": 2,
        "latest_user_text": "Not Insomnia, play the Silverthorn track about Jolee.",
        "conversation_goal": None,
        "conversation": [
            {"role": "user", "turn_number": 1, "content": "Try Insomnia by Kamelot."},
            {"role": "music", "turn_number": 1, "content": "old_track"},
            {
                "role": "user",
                "turn_number": 2,
                "content": "Not Insomnia, play the Silverthorn track about Jolee.",
            },
        ],
        "items": [
            {
                "rank": 1,
                "track": {
                    "track_name": "Sacrimony (Angel of Afterlife)",
                    "artist_name": "Kamelot",
                    "album_name": "Silverthorn",
                    "popularity": 42,
                    "tags": [],
                },
            },
            {
                "rank": 2,
                "track": {
                    "track_name": "Insomnia",
                    "artist_name": "Kamelot",
                    "album_name": "Haven",
                    "popularity": 41,
                    "tags": [],
                },
            },
        ],
    }
    catalog = audit.Catalog(
        {
            "old_track": {
                "track_name": "Insomnia",
                "artist_name": "Kamelot",
                "album_name": "Haven",
            }
        }
    )

    prompt = audit.build_judge_prompt(row, catalog, top_k=20)

    assert "Rank 1 is the submitted top recommendation under review." in prompt
    assert "1. [SUBMITTED TOP] Sacrimony (Angel of Afterlife) by Kamelot" in prompt
    assert "best_rank must be one of the displayed candidate ranks" in prompt


def _empty_audit_terms(**overrides):
    terms = {
        "rejected_names": [],
        "avoid_names": [],
        "rejected_name_terms": [],
        "avoid_name_terms": [],
        "rejected_artist_ids": [],
        "rejected_track_ids": [],
        "prior_artists": {},
        "prior_albums": {},
        "switch_requested": False,
        "different_album_requested": False,
        "current_request_type": "",
        "exact_track_album_names": [],
    }
    terms.update(overrides)
    return terms


def test_audit_avoid_track_title_does_not_flag_album_title_collision():
    audit = load_audit_module()
    catalog = audit.Catalog(
        {
            "sibling": {
                "track_name": "Ole",
                "artist_name": "The Bouncing Souls",
                "album_name": "Hopeless Romantic",
                "tag_list": ["punk"],
            },
            "exact": {
                "track_name": "Hopeless Romantic",
                "artist_name": "The Bouncing Souls",
                "album_name": "Hopeless Romantic",
                "tag_list": ["punk"],
            },
        }
    )
    terms = _empty_audit_terms(
        avoid_names=["Hopeless Romantic"],
        avoid_name_terms=[{"value": "Hopeless Romantic", "kind": "track"}],
    )

    assert audit.violation_flags("sibling", catalog, terms) == []
    assert audit.violation_flags("exact", catalog, terms) == [
        "avoid_name:Hopeless Romantic"
    ]


def test_audit_avoid_title_requires_exact_field_not_substring():
    audit = load_audit_module()
    catalog = audit.Catalog(
        {
            "substring": {
                "track_name": "All We Are",
                "artist_name": "OneRepublic",
                "album_name": "Dreaming Out Loud",
                "tag_list": ["rock"],
            },
            "exact": {
                "track_name": "We Are",
                "artist_name": "ONE OK ROCK",
                "album_name": "Ambitions",
                "tag_list": ["rock"],
            },
        }
    )
    terms = _empty_audit_terms(
        avoid_names=["We Are"],
        avoid_name_terms=[{"value": "We Are", "kind": "track"}],
    )

    assert audit.violation_flags("substring", catalog, terms) == []
    assert audit.violation_flags("exact", catalog, terms) == ["avoid_name:We Are"]


def test_audit_rejected_tag_matches_tags_not_album_text():
    audit = load_audit_module()
    catalog = audit.Catalog(
        {
            "album_text": {
                "track_name": "Elvis",
                "artist_name": "The Rubens",
                "album_name": "Australian Post-Punk and Alt Rock",
                "tag_list": ["Indie Rock", "Rock", "Alternative"],
            },
            "tagged": {
                "track_name": "Bad Punk Song",
                "artist_name": "Band",
                "album_name": "Record",
                "tag_list": ["punk rock"],
            },
        }
    )
    terms = _empty_audit_terms(
        rejected_names=["punk"],
        rejected_name_terms=[{"value": "punk", "kind": "tag"}],
    )

    assert audit.violation_flags("album_text", catalog, terms) == []
    assert audit.violation_flags("tagged", catalog, terms) == ["rejected_name:punk"]


def test_audit_exact_track_allows_its_own_album_soft_avoid():
    audit = load_audit_module()
    catalog = audit.Catalog(
        {
            "target": {
                "track_name": "Johnny Too Bad Freestyle - Rarities Version",
                "artist_name": "Sublime",
                "album_name": "Everything Under The Sun",
                "tag_list": ["reggae-punk"],
            }
        }
    )
    terms = _empty_audit_terms(
        avoid_names=["Everything Under The Sun"],
        avoid_name_terms=[{"value": "Everything Under The Sun", "kind": "album"}],
        current_request_type="exact_track",
        exact_track_album_names=["Everything Under The Sun"],
    )

    assert audit.violation_flags("target", catalog, terms) == []


def test_render_html_groups_metric_cards_into_collapsible_rows():
    audit = load_audit_module()
    rendered = audit.render_html(
        {
            "aggregate": {
                "n_rows": 80,
                "n_with_trace": 80,
                "top1_flagged": 28,
                "top20_flagged_rows": 34,
                "hard_top1_invalid": 3,
                "hard_top20_invalid_rows": 3,
                "with_better_submitted": 33,
                "with_better_pool": 34,
                "label_metrics": None,
                "gap_counts": {},
                "llm_judge_metrics": {"n_judged": 80, "weak_or_bad": 54},
                "llm_explanation_judge_metrics": {"n_judged": 80, "weak_or_bad": 16},
                "llm_state_judge_metrics": {"n_judged": 80, "partial_or_bad": 41},
                "metadata": {
                    "tid": "t1",
                    "split": "blindset_A",
                    "generated_at": "2026-06-27 08:32:20",
                    "prediction_path": "prediction.zip",
                    "trace_path": "trace.jsonl",
                    "ground_truth_path": None,
                    "dataset_name": "dataset",
                    "leaderboard_metadata": None,
                    "llm_judge": {"enabled": True},
                    "llm_explanation_judge": {"enabled": True},
                    "llm_state_judge": {"enabled": True},
                },
            },
            "rows": [],
        },
        audit.Catalog({}),
    )

    assert 'class="metric-groups"' in rendered
    assert "Run Coverage" in rendered
    assert "Validity And Gaps" in rendered
    assert "Judge Evaluations" in rendered
    assert "Judge Coverage" in rendered
    assert "Fit 80/80" in rendered
    assert "Response 80/80" in rendered
    assert "State 80/80" in rendered
    assert "Judge Issues" in rendered
    assert "Weak/bad fits 54" in rendered
    assert "Thin/misleading 16" in rendered
    assert "Partial/inaccurate state 41" in rendered
    assert "Fit Judged" not in rendered
    assert "Responses Judged" not in rendered
    assert "State Judged" not in rendered
