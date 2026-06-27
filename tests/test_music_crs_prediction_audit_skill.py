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
