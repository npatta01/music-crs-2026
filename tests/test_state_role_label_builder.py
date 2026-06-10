from scripts.build_state_role_labels_v2 import convert_label


def test_builder_keeps_tag_type_for_query_facets():
    converted = convert_label(
        {
            "sample_id": "s1",
            "fact_label": {
                "request_type": "attribute_search",
                "required_entities": [
                    {"type": "tag", "value": "funk carioca"},
                ],
            },
        }
    )

    assert converted["state_label"]["required_query_facets"] == [
        {"type": "tag", "value": "funk carioca"}
    ]


def test_builder_treats_attribute_search_entities_as_style_references():
    converted = convert_label(
        {
            "sample_id": "s1",
            "fact_label": {
                "request_type": "attribute_search",
                "required_entities": [
                    {
                        "type": "artist",
                        "value": "A Tribe Called Quest",
                        "use_as_retrieval_seed": True,
                    },
                ],
            },
        }
    )

    assert converted["state_label"]["required_exact_seeds"] == []
    assert converted["state_label"]["required_style_references"] == [
        {"type": "artist", "value": "A Tribe Called Quest"}
    ]


def test_builder_allows_hidden_target_for_album_scoped_searches():
    converted = convert_label(
        {
            "sample_id": "s1",
            "fact_label": {
                "request_type": "exact_album",
                "required_entities": [
                    {
                        "type": "album",
                        "value": "A Fever You Can't Sweat Out",
                        "use_as_retrieval_seed": True,
                    },
                ],
            },
        }
    )

    assert "hidden_target" in converted["state_label"]["allowed_request_types"]


def test_builder_does_not_require_temporal_for_exact_track_seed():
    converted = convert_label(
        {
            "sample_id": "s1",
            "fact_label": {
                "request_type": "exact_track",
                "required_entities": [
                    {
                        "type": "track",
                        "value": "Rock with You",
                        "use_as_retrieval_seed": True,
                    },
                    {
                        "type": "artist",
                        "value": "Michael Jackson",
                        "use_as_retrieval_seed": True,
                    },
                ],
                "temporal_constraint": {
                    "kind": ["release_date", "style_era"],
                    "strength": ["hard", "soft"],
                    "apply_as_filter": [True, False],
                },
            },
        }
    )

    assert "temporal_constraint" not in converted["state_label"]


def test_builder_normalizes_style_era_labels_to_soft_non_filter():
    converted = convert_label(
        {
            "sample_id": "s1",
            "fact_label": {
                "request_type": "attribute_search",
                "temporal_constraint": {
                    "kind": ["style_era", "reference_era"],
                    "strength": ["hard", "soft"],
                    "apply_as_filter": [True, False],
                },
            },
        }
    )

    assert converted["state_label"]["temporal_constraint"] == {
        "kind": ["style_era", "reference_era"],
        "strength": "soft",
        "apply_as_filter": False,
    }
