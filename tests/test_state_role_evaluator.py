from mcrs.conversation_state.state_role_eval import evaluate_role_labels, score_role_label


def test_role_label_accepts_allowed_request_types():
    label = {
        "sample_id": "s1",
        "state_label": {
            "allowed_request_types": ["attribute_search", "similar_to_prior"],
        },
    }
    observed = {
        "schema_valid": True,
        "current_request": {"request_type": "attribute_search"},
        "facts": [],
    }

    row = score_role_label(label, observed)

    assert row["checks"]["request_type"] is True
    assert row["all_pass"] is True


def test_role_label_accepts_allowed_candidate_request_type():
    label = {
        "sample_id": "s1",
        "state_label": {
            "allowed_request_types": ["attribute_search", "similar_to_prior"],
        },
    }
    observed = {
        "schema_valid": True,
        "current_request": {
            "request_type": "new_artist",
            "candidate_types": [
                {
                    "request_type": "attribute_search",
                    "confidence": 0.7,
                    "evidence_text": "lyrical storytelling",
                }
            ],
        },
        "facts": [],
    }

    row = score_role_label(label, observed)

    assert row["checks"]["request_type"] is True
    assert row["all_pass"] is True


def test_role_label_splits_exact_seed_style_reference_and_query_facet():
    label = {
        "sample_id": "s1",
        "state_label": {
            "required_exact_seeds": [{"type": "album", "value": "Cracker Island"}],
            "required_style_references": [
                {"type": "artist", "value": "Mac Miller", "reuse": "avoid_exact"}
            ],
            "required_query_facets": [
                {"facet": "lyrical_theme", "value": "storytelling about relationships"}
            ],
            "forbidden_exact_seeds": [{"type": "artist", "value": "Mac Miller"}],
            "required_context_entities": [
                {"type": "track", "value": "Night Moves", "allowed_roles": ["satisfied_prior", "history"]}
            ],
        },
    }
    observed = {
        "schema_valid": True,
        "current_request": {"request_type": "attribute_search"},
        "facts": [
            {
                "type": "album",
                "value": "Cracker Island",
                "role": "current_target",
                "anchor_use": "must_use",
                "relation": "exact_target",
                "reuse": "must_reuse",
            },
            {
                "type": "artist",
                "value": "Mac Miller",
                "role": "current_target",
                "anchor_use": "partial_anchor",
                "relation": "style_reference",
                "reuse": "avoid_exact",
            },
            {
                "type": "attribute",
                "facet": "lyrical_theme",
                "value": "storytelling about relationships",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
            },
            {
                "type": "track",
                "value": "Night Moves",
                "role": "satisfied_prior",
                "anchor_use": "do_not_use",
                "relation": "satisfied_prior",
            },
        ],
    }

    row = score_role_label(label, observed)

    assert row["all_pass"] is True
    assert row["checks"] == {
        "schema_valid": True,
        "request_type": True,
        "exact_seeds": True,
        "style_references": True,
        "query_facets": True,
        "context_entities": True,
        "exclusions": True,
        "forbidden_exact_seeds": True,
        "temporal_constraint": True,
    }


def test_role_label_fails_when_style_reference_is_exact_seeded():
    label = {
        "sample_id": "s1",
        "state_label": {
            "required_style_references": [
                {"type": "artist", "value": "Mac Miller", "reuse": "avoid_exact"}
            ],
            "forbidden_exact_seeds": [{"type": "artist", "value": "Mac Miller"}],
        },
    }
    observed = {
        "schema_valid": True,
        "facts": [
            {
                "type": "artist",
                "value": "Mac Miller",
                "role": "current_target",
                "anchor_use": "must_use",
                "relation": "exact_target",
                "reuse": "must_reuse",
            }
        ],
    }

    row = score_role_label(label, observed)

    assert row["all_pass"] is False
    assert row["checks"]["style_references"] is False
    assert row["checks"]["forbidden_exact_seeds"] is False
    assert "style_reference: Mac Miller" in row["missing_facts"]
    assert "forbidden_exact_seed: Mac Miller" in row["missing_facts"]


def test_role_label_accepts_projected_style_reference_entities():
    label = {
        "sample_id": "s1",
        "state_label": {
            "required_style_references": [
                {"type": "artist", "value": "Mac Miller"}
            ],
        },
    }
    observed = {
        "schema_valid": True,
        "facts": [
            {
                "type": "artist",
                "value": "Mac Miller",
                "role": "satisfied_prior",
                "anchor_use": "do_not_use",
                "relation": "satisfied_prior",
                "reuse": "avoid_exact",
            }
        ],
        "compiler_style_reference_entities": [
            {"type": "artist", "value": "Mac Miller", "sentiment": 1}
        ],
    }

    row = score_role_label(label, observed)

    assert row["checks"]["style_references"] is True
    assert row["all_pass"] is True


def test_role_label_scores_context_entities_separately_from_seeds():
    label = {
        "sample_id": "s1",
        "state_label": {
            "required_context_entities": [
                {"type": "artist", "value": "Brent Faiyaz", "allowed_roles": ["satisfied_prior", "history"]}
            ],
            "forbidden_exact_seeds": [{"type": "artist", "value": "Brent Faiyaz"}],
        },
    }
    observed = {
        "schema_valid": True,
        "facts": [
            {
                "type": "artist",
                "value": "Brent Faiyaz",
                "role": "satisfied_prior",
                "anchor_use": "do_not_use",
                "relation": "satisfied_prior",
                "reuse": "avoid_exact",
            }
        ],
    }

    row = score_role_label(label, observed)

    assert row["checks"]["context_entities"] is True
    assert row["checks"]["forbidden_exact_seeds"] is True
    assert row["all_pass"] is True


def test_role_label_accepts_decomposed_popularity_and_genre_query_facets():
    label = {
        "sample_id": "s1",
        "state_label": {
            "required_query_facets": [{"type": "tag", "value": "90s dance hits"}],
        },
    }
    observed = {
        "schema_valid": True,
        "facts": [
            {
                "type": "attribute",
                "facet": "popularity",
                "value": "iconic",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "1990s dance",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
            },
        ],
    }

    row = score_role_label(label, observed)

    assert row["checks"]["query_facets"] is True
    assert row["all_pass"] is True


def test_role_label_accepts_functional_energy_goal_as_energy_facets():
    label = {
        "sample_id": "s1",
        "state_label": {
            "required_query_facets": [{"type": "tag", "value": "boost my energy"}],
        },
    }
    observed = {
        "schema_valid": True,
        "facts": [
            {
                "type": "attribute",
                "facet": "energy",
                "value": "energetic",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
            },
            {
                "type": "attribute",
                "facet": "energy",
                "value": "high-energy",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
            },
        ],
    }

    row = score_role_label(label, observed)

    assert row["checks"]["query_facets"] is True
    assert row["all_pass"] is True


def test_role_label_accepts_style_reference_as_context_entity():
    label = {
        "sample_id": "s1",
        "state_label": {
            "required_context_entities": [
                {
                    "type": "artist",
                    "value": "Mr. Bungle",
                    "allowed_roles": ["satisfied_prior", "history"],
                }
            ],
            "forbidden_exact_seeds": [{"type": "artist", "value": "Mr. Bungle"}],
        },
    }
    observed = {
        "schema_valid": True,
        "facts": [
            {
                "type": "artist",
                "value": "Mr. Bungle",
                "role": "current_target",
                "anchor_use": "partial_anchor",
                "relation": "style_reference",
                "reuse": "may_reuse",
            }
        ],
    }

    row = score_role_label(label, observed)

    assert row["checks"]["context_entities"] is True
    assert row["checks"]["forbidden_exact_seeds"] is True
    assert row["all_pass"] is True


def test_role_label_accepts_exclusion_as_context_entity():
    label = {
        "sample_id": "s1",
        "state_label": {
            "required_context_entities": [
                {"type": "track", "value": "Baker Street", "allowed_roles": ["contrast"]}
            ],
            "forbidden_exact_seeds": [{"type": "track", "value": "Baker Street"}],
        },
    }
    observed = {
        "schema_valid": True,
        "facts": [
            {
                "type": "track",
                "value": "Baker Street",
                "role": "rejected",
                "anchor_use": "do_not_use",
                "relation": "exclude",
                "reuse": "must_exclude",
            }
        ],
        "exclusions": [
            {"type": "track", "value": "Baker Street", "scope": "next_turn_hard"}
        ],
    }

    row = score_role_label(label, observed)

    assert row["checks"]["context_entities"] is True
    assert row["checks"]["forbidden_exact_seeds"] is True
    assert row["all_pass"] is True


def test_evaluate_role_labels_groups_summary_rates():
    labels = [
        {
            "sample_id": "s1",
            "pack": "p",
            "fact_class": "style",
            "state_label": {"required_query_facets": [{"value": "raw power"}]},
        },
        {
            "sample_id": "s2",
            "pack": "p",
            "fact_class": "style",
            "state_label": {"required_query_facets": [{"value": "darkness"}]},
        },
    ]
    observed = {
        "s1": {
            "schema_valid": True,
            "facts": [
                {
                    "type": "attribute",
                    "facet": "sonic",
                    "value": "raw power",
                    "relation": "query_facet",
                    "role": "current_target",
                    "anchor_use": "query_facet",
                }
            ],
        },
        "s2": {"schema_valid": True, "facts": []},
    }

    result = evaluate_role_labels(labels, observed)

    assert result["summary"]["samples"] == 2
    assert result["summary"]["all_pass_rate"] == 0.5
    assert result["by_pack"]["p"]["all_pass_rate"] == 0.5
