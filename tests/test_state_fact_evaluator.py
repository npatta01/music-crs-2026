from mcrs.conversation_state.state_fact_eval import (
    evaluate_fact_labels,
    score_fact_label,
)
from scripts.evaluate_state_projection_labels import score_projection_labels


def test_fact_label_scores_required_entity_rejection_and_temporal_fact():
    label = {
        "sample_id": "s1::t2",
        "pack": "P1_rejection_guardrail_failure",
        "fact_label": {
            "request_type": "new_artist",
            "required_entities": [
                {
                    "value": "Radiohead",
                    "allowed_roles": ["rejected"],
                    "use_as_retrieval_seed": False,
                },
                {
                    "value": "moody alternative rock",
                    "allowed_roles": ["current_target", "seed"],
                    "use_as_retrieval_seed": True,
                },
            ],
            "required_exclusions": [
                {"value": "Radiohead", "scope": "hard"},
            ],
            "forbidden_seed_values": ["Radiohead"],
            "temporal_constraint": {
                "kind": ["style_era", "reference_era"],
                "strength": "soft",
                "apply_as_filter": False,
            },
        },
    }
    observed = {
        "schema_valid": True,
        "current_request": {
            "request_type": "new_artist",
            "summary": "Find a new artist, not Radiohead.",
        },
        "entities": [
            {
                "type": "artist",
                "value": "Radiohead",
                "role": "rejected",
                "use_as_retrieval_seed": False,
            },
            {
                "type": "tag",
                "value": "moody alternative rock",
                "role": "current_target",
                "use_as_retrieval_seed": True,
            },
        ],
        "rejections": [
            {"kind": "artist", "value": "Radiohead", "scope": "hard"},
        ],
        "temporal_constraint": {
            "kind": "reference_era",
            "strength": "soft",
            "apply_as_filter": False,
            "range": [1995, 2004],
        },
    }

    row = score_fact_label(label, observed)

    assert row["all_pass"] is True
    assert row["request_type"] == "new_artist"
    assert row["checks"] == {
        "schema_valid": True,
        "request_type": True,
        "required_entities": True,
        "forbidden_seeds": True,
        "required_exclusions": True,
        "temporal_constraint": True,
    }


def test_projection_label_accepts_style_reference_as_positive_retriever_input():
    labels = [
        {
            "sample_id": "s1",
            "fact_label": {
                "required_entities": [
                    {"type": "artist", "value": "Mac Miller", "use_as_retrieval_seed": True}
                ]
            },
        }
    ]
    audit_rows = {
        "s1": {
            "new_observed": {
                "compiler_mentioned_entities": [],
                "compiler_style_reference_entities": [
                    {"type": "artist", "value": "Mac Miller", "sentiment": 1}
                ],
                "compiler_explicit_rejections": [],
            }
        }
    }

    result = score_projection_labels(labels, audit_rows)

    assert result["summary"]["pass_rate"] == 1.0


def test_fact_label_fails_when_rejected_entity_is_seeded():
    label = {
        "sample_id": "s1::t2",
        "pack": "P1_rejection_guardrail_failure",
        "fact_label": {
            "required_entities": [
                {
                    "value": "Radiohead",
                    "allowed_roles": ["rejected"],
                    "use_as_retrieval_seed": False,
                },
            ],
            "required_exclusions": [{"value": "Radiohead", "scope": "hard"}],
            "forbidden_seed_values": ["Radiohead"],
        },
    }
    observed = {
        "schema_valid": True,
        "entities": [
            {
                "type": "artist",
                "value": "Radiohead",
                "role": "current_target",
                "use_as_retrieval_seed": True,
            }
        ],
        "rejections": [],
        "temporal_constraint": None,
    }

    row = score_fact_label(label, observed)

    assert row["all_pass"] is False
    assert row["checks"]["required_entities"] is False
    assert row["checks"]["forbidden_seeds"] is False
    assert row["checks"]["required_exclusions"] is False
    assert "Radiohead" in row["missing_facts"]


def test_fact_label_fails_when_current_request_type_mismatches():
    label = {
        "sample_id": "s1::t2",
        "fact_label": {"request_type": "new_artist"},
    }
    observed = {
        "schema_valid": True,
        "current_request": {
            "request_type": "same_artist",
            "summary": "More Radiohead.",
        },
    }

    row = score_fact_label(label, observed)

    assert row["all_pass"] is False
    assert row["compiler_core_pass"] is True
    assert row["checks"]["request_type"] is False
    assert "request_type" in row["missing_facts"]


def test_evaluate_fact_labels_groups_by_pack_and_fact_class():
    labels = [
        {
            "sample_id": "s1",
            "pack": "p",
            "fact_class": "rejection",
            "fact_label": {"required_exclusions": [{"value": "Radiohead"}]},
        },
        {
            "sample_id": "s2",
            "pack": "p",
            "fact_class": "entity",
            "fact_label": {"required_entities": [{"value": "Numb"}]},
        },
    ]
    observed = {
        "s1": {
            "schema_valid": True,
            "entities": [{"value": "Radiohead", "role": "rejected", "use_as_retrieval_seed": False}],
            "rejections": [{"value": "Radiohead", "scope": "hard"}],
        },
        "s2": {"schema_valid": True, "entities": [], "rejections": []},
    }

    result = evaluate_fact_labels(labels, observed)

    assert result["summary"]["samples"] == 2
    assert result["summary"]["all_pass_rate"] == 0.5
    assert result["summary"]["compiler_core_pass_rate"] == 0.5
    assert result["by_pack"]["p"]["all_pass_rate"] == 0.5
    assert result["by_pack"]["p"]["compiler_core_pass_rate"] == 0.5
    assert result["by_fact_class"]["entity"]["all_pass_rate"] == 0.0
    assert result["by_fact_class"]["rejection"]["all_pass_rate"] == 1.0


def test_compiler_core_pass_ignores_request_type_but_keeps_fact_checks():
    label = {
        "sample_id": "s1::t2",
        "fact_label": {
            "request_type": "new_artist",
            "required_entities": [
                {
                    "value": "Radiohead",
                    "allowed_roles": ["rejected"],
                    "use_as_retrieval_seed": False,
                },
            ],
            "required_exclusions": [{"value": "Radiohead", "scope": "hard"}],
            "forbidden_seed_values": ["Radiohead"],
        },
    }
    observed = {
        "schema_valid": True,
        "current_request": {"request_type": "same_artist"},
        "entities": [
            {
                "type": "artist",
                "value": "Radiohead",
                "role": "rejected",
                "use_as_retrieval_seed": False,
            }
        ],
        "rejections": [{"kind": "artist", "value": "Radiohead", "scope": "hard"}],
    }

    row = score_fact_label(label, observed)

    assert row["all_pass"] is False
    assert row["compiler_core_pass"] is True


def test_fact_label_matches_short_retriever_terms_inside_longer_phrases():
    label = {
        "sample_id": "s1::t1",
        "fact_label": {
            "required_entities": [
                {
                    "type": "tag",
                    "value": "hit",
                    "allowed_roles": ["current_target"],
                    "use_as_retrieval_seed": True,
                }
            ],
            "required_exclusions": [
                {
                    "type": "tag",
                    "value": "dark and harsh",
                    "scope": "soft",
                }
            ],
        },
    }
    observed = {
        "schema_valid": True,
        "entities": [
            {
                "type": "tag",
                "value": "hit back then",
                "role": "current_target",
                "use_as_retrieval_seed": True,
            }
        ],
        "rejections": [
            {"kind": "tag", "value": "dark harsh", "scope": "soft"},
        ],
    }

    row = score_fact_label(label, observed)

    assert row["compiler_core_pass"] is True
    assert row["missing_facts"] == []
