from pathlib import Path

from mcrs.conversation_state.replay_eval import (
    FOCUSED_PACKS,
    apply_expected_state_overrides,
    build_full_history_messages_for_extraction,
    compare_state_change,
    evaluate_observed_states,
    load_replay_pack,
    observed_from_ideal,
    observed_from_state,
    observed_from_state_snapshot,
    trim_messages_for_extraction,
)
from mcrs.conversation_state.schema import ConversationStateV0Plus


PACK_PATH = Path(
    "experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/"
    "state_experiment_pack.json"
)


def test_load_replay_pack_focuses_on_seventy_state_examples():
    samples = load_replay_pack(PACK_PATH, packs=FOCUSED_PACKS)

    assert len(samples) == 70
    counts = {pack: 0 for pack in FOCUSED_PACKS}
    for sample in samples:
        counts[sample["pack"]] += 1
    assert set(counts.values()) == {10}


def test_trim_messages_for_extraction_excludes_gt_music_and_assistant():
    sample = load_replay_pack(PACK_PATH, packs=["P0_roleless_stale_entity_failure"])[0]

    trimmed = trim_messages_for_extraction(sample)

    assert trimmed[-1]["role"] == "user"
    assert trimmed[-1]["turn"] == sample["turn"]
    assert all(
        msg["turn"] < sample["turn"] or msg["role"] == "user"
        for msg in trimmed
    )


def test_full_history_messages_for_extraction_excludes_current_gt_response():
    sample = {
        "session_id": "s1",
        "turn": 3,
        "recent_messages": [
            {"turn": 3, "role": "user", "content": "current ask"},
            {"turn": 3, "role": "music", "content": "gt-track"},
            {"turn": 3, "role": "assistant", "content": "hidden answer"},
        ],
    }
    session_messages = [
        {"turn_number": 1, "role": "user", "content": "old ask"},
        {"turn_number": 1, "role": "music", "content": "old-track"},
        {"turn_number": 1, "role": "assistant", "content": "old response"},
        {"turn_number": 2, "role": "user", "content": "middle ask"},
        {"turn_number": 2, "role": "music", "content": "middle-track"},
        {"turn_number": 3, "role": "user", "content": "current ask"},
        {"turn_number": 3, "role": "music", "content": "gt-track"},
        {"turn_number": 3, "role": "assistant", "content": "hidden answer"},
    ]

    messages = build_full_history_messages_for_extraction(sample, session_messages)

    assert messages == [
        {"role": "user", "content": "old ask"},
        {"role": "music", "content": "old-track"},
        {"role": "assistant", "content": "old response"},
        {"role": "user", "content": "middle ask"},
        {"role": "music", "content": "middle-track"},
        {"role": "user", "content": "current ask"},
    ]


def test_ideal_state_source_scores_all_focused_samples_as_passing():
    samples = load_replay_pack(PACK_PATH, packs=FOCUSED_PACKS)
    observed = {
        sample["sample_id"]: observed_from_ideal(sample)
        for sample in samples
    }

    result = evaluate_observed_states(samples, observed)

    assert result["summary"]["samples"] == 70
    assert result["summary"]["all_pass_rate"] == 1.0
    assert all(row["all_pass"] for row in result["rows"])


def test_state_change_evaluation_compares_previous_new_and_desired_state():
    sample = load_replay_pack(PACK_PATH, packs=["P0_roleless_stale_entity_failure"])[0]
    previous = observed_from_state_snapshot(sample)
    new = observed_from_ideal(sample)

    comparison = compare_state_change(sample, previous, new)

    assert comparison["previous_all_pass"] is False
    assert comparison["new_all_pass"] is True
    assert comparison["captured_expected_info"] is True
    assert "role_correct" in comparison["improved_checks"]
    assert comparison["previous_read"]["entities"]
    assert comparison["new_read"]["target_artist_mode"] == "new_artist"
    assert comparison["desired_read"]["target_artist_mode"] == "new_artist"


def test_observed_from_state_includes_deterministic_compiler_projection():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "new_artist",
            "summary": "New bands besides Linkin Park with aggressive nu-metal sound.",
            "source_turn": 8,
        },
        facts=[
            {
                "type": "artist",
                "value": "Linkin Park",
                "role": "satisfied_prior",
                "anchor_use": "do_not_use",
                "source_turn": 8,
                "mentioned_current_turn": True,
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "aggressive nu-metal",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 8,
                "mentioned_current_turn": True,
            },
        ],
        exclusions=[
            {
                "type": "artist",
                "value": "Linkin Park",
                "scope": "next_turn_hard",
                "source_turn": 8,
            }
        ],
        entities=[
            {
                "type": "artist",
                "value": "Linkin Park",
                "role": "current_target",
                "source_turn": 8,
                "mentioned_current_turn": True,
                "use_as_retrieval_seed": True,
            }
        ],
    )

    observed = observed_from_state(state)

    assert observed["entities"][0]["use_as_retrieval_seed"] is True
    assert observed["compiler_mentioned_entities"] == [
        {"type": "artist", "value": "Linkin Park", "sentiment": -1},
        {"type": "tag", "value": "aggressive nu-metal", "sentiment": 1},
    ]
    assert observed["compiler_explicit_rejections"] == [
        {"kind": "artist", "value": "Linkin Park", "source_turn": 8}
    ]


def test_expected_state_checks_override_gt_contaminated_ideal_labels():
    sample = load_replay_pack(PACK_PATH, packs=["POS_exact_entity_success_control"])[0]
    sample = {
        **sample,
        "expected_state_checks": {
            "retrieval_profile": "exact_probe",
            "entities": [
                {
                    "value": "Numb",
                    "allowed_roles": ["current_target", "seed"],
                    "use_as_retrieval_seed": True,
                },
                {
                    "value": "Linkin Park",
                    "allowed_roles": ["current_target", "seed"],
                    "use_as_retrieval_seed": True,
                },
            ],
        },
    }
    observed = {
        "schema_valid": True,
        "target_artist_mode": "same_artist",
        "retrieval_profile": "exact_probe",
        "entities": [
            {
                "type": "track",
                "value": "Numb",
                "role": "current_target",
                "use_as_retrieval_seed": True,
            },
            {
                "type": "artist",
                "value": "Linkin Park",
                "role": "current_target",
                "use_as_retrieval_seed": True,
            },
        ],
        "rejections": [],
        "temporal_constraint": None,
    }

    result = evaluate_observed_states([sample], {sample["sample_id"]: observed})

    assert result["rows"][0]["all_pass"] is True
    assert result["rows"][0]["desired_read"]["retrieval_profile"] == ["exact_probe"]
    assert result["rows"][0]["desired_read"]["expected_check_source"] == "expected_state_checks"


def test_expected_state_checks_scores_current_request_type():
    sample = load_replay_pack(PACK_PATH, packs=["P0_novelty_prior_anchor_failure"])[0]
    sample = {
        **sample,
        "expected_state_checks": {
            "request_type": "new_artist",
            "retrieval_profile": "novelty",
        },
    }
    observed = {
        "schema_valid": True,
        "current_request": {
            "request_type": "same_artist",
            "summary": "More Britney Spears.",
        },
        "target_artist_mode": "new_artist",
        "retrieval_profile": "novelty",
        "entities": [],
        "rejections": [],
        "temporal_constraint": None,
    }

    result = evaluate_observed_states([sample], {sample["sample_id"]: observed})

    assert result["rows"][0]["request_type_correct"] is False
    assert result["rows"][0]["all_pass"] is False
    assert result["rows"][0]["desired_read"]["request_type"] == ["new_artist"]


def test_apply_expected_state_overrides_filters_to_reviewed_subset():
    samples = load_replay_pack(PACK_PATH, packs=FOCUSED_PACKS)
    overrides = {
        samples[0]["sample_id"]: {
            "expected_state_checks": {"retrieval_profile": "novelty"},
            "label_review": {"status": "clean"},
        }
    }

    reviewed = apply_expected_state_overrides(
        samples,
        overrides,
        filter_to_overrides=True,
    )

    assert [sample["sample_id"] for sample in reviewed] == [samples[0]["sample_id"]]
    assert reviewed[0]["expected_state_checks"] == {"retrieval_profile": "novelty"}
    assert reviewed[0]["label_review"] == {"status": "clean"}


def test_expected_rejection_value_allows_specific_album_or_soundtrack_suffix():
    sample = load_replay_pack(PACK_PATH, packs=["P1_rejection_guardrail_failure"])[0]
    sample = {
        **sample,
        "expected_state_checks": {
            "requires_hard_rejection": True,
            "hard_rejection_values": ["Blade Runner 2049"],
        },
    }
    observed = {
        "schema_valid": True,
        "target_artist_mode": "new_artist",
        "retrieval_profile": "novelty",
        "entities": [],
        "rejections": [
            {
                "kind": "style",
                "value": "Blade Runner 2049 soundtrack",
                "scope": "hard",
            }
        ],
        "temporal_constraint": None,
    }

    result = evaluate_observed_states([sample], {sample["sample_id"]: observed})

    assert result["rows"][0]["rejection_normalization_correct"] is True


def test_expected_soft_rejection_value_requires_soft_scope():
    sample = load_replay_pack(PACK_PATH, packs=["P1_rejection_guardrail_failure"])[0]
    sample = {
        **sample,
        "expected_state_checks": {
            "soft_rejection_values": ["rain"],
        },
    }
    observed = {
        "schema_valid": True,
        "target_artist_mode": "same_artist",
        "retrieval_profile": "continuation",
        "entities": [],
        "rejections": [
            {
                "kind": "tag",
                "value": "rain-based",
                "scope": "hard",
            }
        ],
        "temporal_constraint": None,
    }

    result = evaluate_observed_states([sample], {sample["sample_id"]: observed})

    assert result["rows"][0]["rejection_normalization_correct"] is False


def test_expected_entity_value_matching_ignores_punctuation_noise():
    sample = load_replay_pack(PACK_PATH, packs=["P0_roleless_stale_entity_failure"])[0]
    sample = {
        **sample,
        "expected_state_checks": {
            "entities": [
                {
                    "type": "tag",
                    "value": "high-energy",
                    "allowed_roles": ["current_target", "seed"],
                    "use_as_retrieval_seed": True,
                }
            ]
        },
    }
    observed = {
        "schema_valid": True,
        "target_artist_mode": "unknown",
        "retrieval_profile": "feature_search",
        "entities": [
            {
                "type": "tag",
                "value": "high energy",
                "role": "current_target",
                "use_as_retrieval_seed": True,
            }
        ],
        "rejections": [],
        "temporal_constraint": None,
    }

    result = evaluate_observed_states([sample], {sample["sample_id"]: observed})

    assert result["rows"][0]["role_correct"] is True


def test_expected_entity_value_matching_allows_retriever_phrase_containment():
    sample = load_replay_pack(PACK_PATH, packs=["P0_roleless_stale_entity_failure"])[0]
    sample = {
        **sample,
        "expected_state_checks": {
            "entities": [
                {
                    "type": "tag",
                    "value": "disco",
                    "allowed_roles": ["current_target", "seed"],
                    "use_as_retrieval_seed": True,
                }
            ]
        },
    }
    observed = {
        "schema_valid": True,
        "target_artist_mode": "unknown",
        "retrieval_profile": "feature_search",
        "entities": [
            {
                "type": "tag",
                "value": "classic disco",
                "role": "current_target",
                "use_as_retrieval_seed": True,
            }
        ],
        "rejections": [],
        "temporal_constraint": None,
    }

    result = evaluate_observed_states([sample], {sample["sample_id"]: observed})

    assert result["rows"][0]["role_correct"] is True


def test_expected_temporal_constraint_allows_multiple_acceptable_kinds():
    sample = load_replay_pack(PACK_PATH, packs=["P1_temporal_constraint_failure"])[0]
    sample = {
        **sample,
        "expected_state_checks": {
            "temporal_constraint": {
                "kind": ["style_era", "reference_era"],
                "strength": "soft",
                "apply_as_filter": False,
            }
        },
    }
    observed = {
        "schema_valid": True,
        "target_artist_mode": "new_artist",
        "retrieval_profile": "novelty",
        "entities": [],
        "rejections": [],
        "temporal_constraint": {
            "kind": "reference_era",
            "strength": "soft",
            "apply_as_filter": False,
            "range": [2004, 2006],
        },
    }

    result = evaluate_observed_states([sample], {sample["sample_id"]: observed})

    assert result["rows"][0]["temporal_semantics_correct"] is True


def test_observed_from_ideal_normalizes_allowed_temporal_values():
    sample = load_replay_pack(PACK_PATH, packs=["P1_temporal_constraint_failure"])[0]
    sample = {
        **sample,
        "expected_state_checks": {
            "temporal_constraint": {
                "kind": ["style_era", "reference_era"],
                "strength": "soft",
                "apply_as_filter": False,
            }
        },
    }

    observed = observed_from_ideal(sample)
    result = evaluate_observed_states([sample], {sample["sample_id"]: observed})

    assert result["rows"][0]["temporal_semantics_correct"] is True
    assert result["rows"][0]["all_pass"] is True
