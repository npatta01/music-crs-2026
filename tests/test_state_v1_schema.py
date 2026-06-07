import pytest
from pydantic import ValidationError

from mcrs.conversation_state.schema import (
    ConversationStateV1,
    ConversationStateV0Plus,
    EntityRole,
    RetrievalProfile,
    TargetArtistMode,
    project_v1_to_v0plus,
)
from mcrs.conversation_state.prompts import current as current_prompt


def test_conversation_state_v1_is_llm_facing_and_forbids_compiler_fields():
    state = ConversationStateV1(
        current_request={
            "request_type": "new_artist",
            "summary": "Other popular hip-hop hits, but no more Drake.",
            "source_turn": 6,
        },
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "hip-hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 6,
                "mentioned_current_turn": True,
            }
        ],
    )

    assert state.current_request is not None
    assert not hasattr(state, "target_artist_mode")
    assert not hasattr(state, "retrieval_profile")
    assert not hasattr(state, "entities")
    assert not hasattr(state, "rejections")

    with pytest.raises(ValidationError):
        ConversationStateV1.model_validate(
            {
                "current_request": {
                    "request_type": "new_artist",
                    "summary": "Other popular hip-hop hits.",
                    "source_turn": 6,
                },
                "facts": [],
                "target_artist_mode": "new_artist",
            }
        )


def test_project_v1_to_v0plus_derives_retriever_contract_without_raw_text_policy():
    state_v1 = ConversationStateV1(
        current_request={
            "request_type": "new_artist",
            "summary": "Other popular hip-hop hits from late 2015 to early 2016, but no more Drake.",
            "source_turn": 6,
            "evidence_text": "other popular hip-hop hits",
        },
        facts=[
            {
                "type": "artist",
                "value": "Drake",
                "role": "rejected",
                "anchor_use": "do_not_use",
                "relation": "exclude",
                "reuse": "must_exclude",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "evidence_text": "no more Drake",
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "hip-hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "evidence_text": "hip-hop hits",
            },
            {
                "type": "attribute",
                "facet": "popularity",
                "value": "popular hits",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "evidence_text": "popular",
            },
        ],
        exclusions=[
            {
                "type": "artist",
                "value": "Drake",
                "scope": "next_turn_hard",
                "source_turn": 6,
                "evidence_text": "no more Drake",
            }
        ],
        temporal_constraint={
            "kind": "release_date",
            "start_year": 2015,
            "end_year": 2016,
            "strength": "hard",
            "apply_as_filter": True,
            "evidence_text": "late 2015 to early 2016",
        },
    )

    projected = project_v1_to_v0plus(state_v1)

    assert projected.turn_intent.startswith("Other popular hip-hop hits")
    assert projected.target_artist_mode is TargetArtistMode.new_artist
    assert projected.retrieval_profile is RetrievalProfile.novelty
    assert [(me.type, me.value, me.sentiment) for me in projected.mentioned_entities] == [
        ("artist", "Drake", -1),
        ("tag", "hip-hop", 1),
        ("tag", "popular hits", 1),
    ]
    assert [(r.kind, r.value) for r in projected.explicit_rejections] == [
        ("artist", "Drake")
    ]
    assert projected.hard_filters


def test_project_v1_to_v0plus_treats_query_facet_relation_as_retriever_tag():
    state_v1 = ConversationStateV1(
        current_request={
            "request_type": "attribute_search",
            "summary": "Another upbeat, high-energy country track.",
            "source_turn": 6,
            "evidence_text": "high-energy country track",
        },
        facts=[
            {
                "type": "artist",
                "value": "country",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "evidence_text": "country track",
            }
        ],
    )

    projected = project_v1_to_v0plus(state_v1)

    assert [(entity.type, entity.value, entity.use_as_retrieval_seed) for entity in projected.entities] == [
        ("tag", "country", True)
    ]
    assert [(mention.type, mention.value, mention.sentiment) for mention in projected.mentioned_entities] == [
        ("tag", "country", 1)
    ]


def test_state_v1_role_typed_entities_drive_current_seed_view():
    state = ConversationStateV0Plus(
        turn_intent="other high-energy classic disco tracks",
        entities=[
            {
                "type": "artist",
                "value": "The Real Thing",
                "role": "satisfied",
                "source_turn": 5,
                "mentioned_current_turn": False,
                "use_as_retrieval_seed": False,
                "evidence_text": "that's exactly the kind",
            },
            {
                "type": "tag",
                "value": "classic disco",
                "role": "current_target",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "use_as_retrieval_seed": True,
                "evidence_text": "classic disco",
            },
        ],
        target_artist_mode="new_artist",
        retrieval_profile="novelty",
        rejections=[],
    )

    assert state.entities[0].role is EntityRole.satisfied
    assert state.target_artist_mode is TargetArtistMode.new_artist
    assert state.retrieval_profile is RetrievalProfile.novelty
    assert [me.value for me in state.mentioned_entities] == ["classic disco"]
    assert state.intent_mode.value == "pivot"
    assert state.process_constraints.exploration_policy.value == "diversify_artists"


def test_state_v1_rejects_long_evidence_spans():
    with pytest.raises(ValidationError):
        ConversationStateV0Plus(
            turn_intent="no more hans zimmer",
            entities=[
                {
                    "type": "artist",
                    "value": "Hans Zimmer",
                    "role": "rejected",
                    "source_turn": 7,
                    "mentioned_current_turn": True,
                    "use_as_retrieval_seed": False,
                    "evidence_text": "x" * 241,
                }
            ],
            target_artist_mode="new_artist",
            retrieval_profile="novelty",
            rejections=[],
        )


def test_state_v1_temporal_soft_era_does_not_create_hard_filter():
    state = ConversationStateV0Plus(
        turn_intent="late 70s golden era R&B sound",
        entities=[],
        target_artist_mode="new_artist",
        retrieval_profile="novelty",
        rejections=[],
        temporal_constraint={
            "kind": "style_era",
            "start_year": 1975,
            "end_year": 1984,
            "strength": "soft",
            "apply_as_filter": False,
            "evidence_text": "golden era",
        },
    )

    assert state.hard_filters == []
    assert state.release_year_range is not None
    assert state.release_year_range.start == 1975
    assert state.release_year_range.end == 1984


def test_state_v1_hard_rejections_project_to_explicit_rejections():
    state = ConversationStateV0Plus(
        turn_intent="similar vibe but no more Daft Punk",
        entities=[],
        target_artist_mode="new_artist",
        retrieval_profile="novelty",
        rejections=[
            {
                "kind": "artist",
                "value": "Daft Punk",
                "scope": "hard",
                "source_turn": 4,
                "evidence_text": "no more Daft Punk",
            },
            {
                "kind": "tag",
                "value": "too heavy",
                "scope": "soft",
                "source_turn": 4,
                "evidence_text": "too heavy",
            },
        ],
    )

    assert [(r.kind, r.value) for r in state.explicit_rejections] == [
        ("artist", "Daft Punk"),
        ("tag", "too heavy"),
    ]


def test_state_v1_album_rejections_project_to_explicit_rejections():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "new_artist",
            "summary": "New artists with the same dark score vibe, no more Blade Runner 2049.",
            "source_turn": 7,
        },
        facts=[
            {
                "type": "album",
                "value": "Blade Runner 2049",
                "role": "rejected",
                "anchor_use": "do_not_use",
                "relation": "exclude",
                "reuse": "must_exclude",
                "source_turn": 7,
                "mentioned_current_turn": True,
            }
        ],
        exclusions=[
            {
                "type": "album",
                "value": "Blade Runner 2049",
                "scope": "next_turn_hard",
                "source_turn": 7,
            }
        ],
    )

    assert ("album", "Blade Runner 2049") in [
        (rejection.kind, rejection.value) for rejection in state.explicit_rejections
    ]
def test_current_prompt_schema_exposes_v1_fields_not_old_mode_fields():
    response_format = current_prompt.json_schema_for_response_format()
    schema = response_format["json_schema"]["schema"]
    props = schema["properties"]

    assert "current_request" in props
    assert "facts" in props
    assert "exclusions" in props
    assert "temporal_constraint" in props
    assert "track_feedback" in props
    assert "referenced_track_ids" in props
    assert response_format["json_schema"]["name"] == "ConversationStateV1"
    assert "entities" not in props
    assert "target_artist_mode" not in props
    assert "retrieval_profile" not in props
    assert "rejections" not in props
    assert "mentioned_entities" not in props
    assert "process_constraints" not in props
    assert "routing_tags" not in props
    assert "release_year_range" not in props


def test_current_request_accepts_candidate_types_with_confidence():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "More chill R&B with a bit more groove, similar to this.",
            "source_turn": 5,
            "candidate_types": [
                {
                    "request_type": "attribute_search",
                    "confidence": 0.85,
                    "evidence_text": "more groove but still chill R&B",
                },
                {
                    "request_type": "similar_to_prior",
                    "confidence": 0.45,
                    "evidence_text": "similar to this",
                },
            ],
        },
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "chill R&B",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 5,
                "mentioned_current_turn": True,
            }
        ],
    )

    assert state.current_request is not None
    assert [item.request_type.value for item in state.current_request.candidate_types] == [
        "attribute_search",
        "similar_to_prior",
    ]
    assert state.current_request.candidate_types[0].confidence == 0.85


def test_current_prompt_teaches_role_typed_state_contract():
    system = current_prompt.SYSTEM

    assert "conversation facts" in system
    assert "current_request" in system
    assert "candidate_types" in system
    assert "facts" in system
    assert "exclusions" in system
    assert "policy guesses" in system
    assert "style_reference" in system
    assert "not just x" in system.casefold()
    assert "someone like x" in system.casefold()
    assert "evidence_text" in system
    assert "process_constraints" not in system
    assert "routing_tags" not in system


def test_current_prompt_few_shots_validate_against_state_schema():
    states = [
        ConversationStateV1.model_validate(example["output"])
        for example in current_prompt.FEW_SHOT_EXAMPLES
    ]

    assert len(states) >= 10
    assert any(state.current_request and state.facts for state in states)
    assert any(
        state.current_request and state.current_request.candidate_types
        for state in states
    )
    assert any(
        any(fact.role.value == "satisfied_prior" for fact in state.facts)
        and state.current_request
        and state.current_request.request_type.value == "new_artist"
        for state in states
    )
    assert any(
        state.current_request
        and state.current_request.request_type.value == "hidden_target"
        and state.lyrical_theme
        for state in states
    )
    assert any(
        state.temporal_constraint
        and state.temporal_constraint.kind.value == "release_date"
        and state.temporal_constraint.apply_as_filter
        for state in states
    )
    assert any(
        state.temporal_constraint
        and state.temporal_constraint.kind.value == "style_era"
        and not state.temporal_constraint.apply_as_filter
        for state in states
    )


def test_current_prompt_teaches_generic_for_now_artist_rejection():
    system = current_prompt.SYSTEM.casefold()
    examples = current_prompt.FEW_SHOT_EXAMPLES
    states = [
        ConversationStateV1.model_validate(example["output"])
        for example in examples
    ]

    assert "good on x for now" in system
    assert any(
        any(
            exclusion.type.value == "artist"
            and exclusion.scope.value == "next_turn_hard"
            and "for now" in (exclusion.evidence_text or "").casefold()
            for exclusion in state.exclusions
        )
        and all(
            fact.role.value != "current_target" or fact.value != state.exclusions[0].value
            for fact in state.facts
        )
        for state in states
    )


def test_current_prompt_preserves_explicit_current_turn_album_and_track_names():
    system = current_prompt.SYSTEM

    assert "Never drop explicitly named current-turn albums or tracks" in system
    assert "from <album>" in system


def test_current_prompt_keeps_satisfied_new_artist_turns_out_of_rejections():
    system = current_prompt.SYSTEM

    assert "System of a Down is great" in system
    assert "not an exclusion" in system
    assert "satisfied_prior" in system
    assert "new_artist" in system


def test_current_prompt_narrows_similar_to_prior_request_type():
    system = current_prompt.SYSTEM

    assert "Do not use similar_to_prior for attribute-rich asks" in system
    assert "Use similar_to_prior only for bare similarity" in system
    assert "groove" in system
    assert "chill R&B" in system
    assert "trying" in system
    assert "remember" in system


def test_current_prompt_preserves_retriever_ready_phrases_and_lyric_quotes():
    system = current_prompt.SYSTEM

    assert "Preserve retriever-ready phrases" in system
    assert "raw power" in system
    assert "quoted lyric" in system


def test_current_prompt_teaches_relation_reuse_boundary():
    system = current_prompt.SYSTEM

    assert "relation" in system
    assert "reuse" in system
    assert "style_reference" in system
    assert "exact_target" in system
    assert "avoid_exact" in system


def test_current_prompt_teaches_retriever_critical_surface_cues():
    system = current_prompt.SYSTEM

    assert "Retriever-critical cue classes" in system
    assert "hit back then" in system
    assert "watching a movie" in system
    assert "boost my energy" in system
    assert "electronic but also soulful" in system
    assert "female artist" in system
    assert "facet=performer" in system
    assert "tecno brega" in system
    assert "funk carioca" in system
    assert "mid-2000s emo" in system
    assert "do not replace it with broader adjacent genres" in system
    assert "not quite the one" in system
    assert "as striking as" in system
    assert "Immediate-prior context rule" in system
    assert "Named feedback before the next ask" in system
    assert "Current-turn named-entity completeness" in system
    assert "Feedback sentence before broad category ask" in system
    assert "Before returning, run this named-entity checklist" in system
    assert "another fantastic X track" in system
    assert "X really" in system
    assert "Random Access Memories" in system
    assert "Night Moves is exactly what I had in mind" in system
    assert "DNA is a banger" in system
    assert "lyric fragment" in system
    assert "Unresolved hidden-target constraints carry forward" in system
    assert "mid-2000s emo phase" in system
    assert "actually heavy" in system
    assert "emit a separate fact with value" in system
    assert "Anitta is definitely on point" in system
    assert "newer albums like" in system
    assert "era is still off" in system
    assert "not even" in system
    assert "instead" in system


def test_current_prompt_few_shots_cover_remaining_surface_cue_gaps():
    states = [
        ConversationStateV1.model_validate(example["output"])
        for example in current_prompt.FEW_SHOT_EXAMPLES
    ]
    values = {
        fact.value
        for state in states
        for fact in state.facts
        if fact.role.value == "current_target"
    }

    assert "ethereal vocals" in values
    assert "artistically unique" in values
    assert "watching a movie" in values
    assert "deep longing" in values
    assert "emotional storytelling" in values
    assert "female artist" in values
    assert "serene" in values
    assert "strong guitar riff" in values
    assert "Cracker Island" in values
    assert "Just wakin' up in the morning, gotta thank God" in values
    assert "mid-2000s emo" in values
    assert any(
        fact.facet and fact.facet.value == "performer" and fact.value == "female artist"
        for state in states
        for fact in state.facts
    )
    assert any(
        fact.type.value == "artist"
        and fact.value == "Guano Apes"
        and fact.role.value == "satisfied_prior"
        and fact.anchor_use.value == "do_not_use"
        for state in states
        for fact in state.facts
    )
    assert any(
        fact.type.value == "artist"
        and fact.value == "John Fogerty"
        and fact.relation.value == "style_reference"
        and fact.anchor_use.value == "partial_anchor"
        for state in states
        for fact in state.facts
    )
    assert any(
        fact.type.value == "artist"
        and fact.value == "Bruce Springsteen"
        and fact.relation.value == "style_reference"
        and fact.anchor_use.value == "partial_anchor"
        for state in states
        for fact in state.facts
    )
    assert any(
        state.current_request
        and state.current_request.request_type.value == "hidden_target"
        and state.lyrical_theme == "Just wakin' up in the morning, gotta thank God"
        for state in states
    )
    assert any(
        state.current_request
        and state.current_request.request_type.value == "hidden_target"
        and any(
            fact.value == "mid-2000s emo"
            and fact.relation.value == "query_facet"
            for fact in state.facts
        )
        for state in states
    )
    assert any(
        state.temporal_constraint
        and state.temporal_constraint.evidence_text == "late 2000s ambient electronic"
        and not state.temporal_constraint.apply_as_filter
        for state in states
    )


def test_fact_first_state_derives_legacy_entities_rejections_and_policy():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "new_artist",
            "summary": "Other popular hip-hop hits from late 2015 to early 2016 by artists other than Drake.",
            "source_turn": 6,
            "evidence_text": "other artists around late 2015 to early 2016",
        },
        facts=[
            {
                "type": "artist",
                "value": "Drake",
                "role": "rejected",
                "anchor_use": "do_not_use",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "evidence_text": "good on Drake for now",
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "Hip-Hop",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "evidence_text": "popular Hip-Hop tracks",
            },
            {
                "type": "attribute",
                "facet": "popularity",
                "value": "popular major hits",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "evidence_text": "major hits",
            },
        ],
        exclusions=[
            {
                "type": "artist",
                "value": "Drake",
                "scope": "next_turn_hard",
                "source_turn": 6,
                "evidence_text": "good on Drake for now",
            }
        ],
        temporal_constraint={
            "kind": "release_date",
            "start_year": 2015,
            "end_year": 2016,
            "strength": "hard",
            "apply_as_filter": True,
            "evidence_text": "late 2015 to early 2016",
        },
    )

    assert state.turn_intent.startswith("Other popular hip-hop hits")
    assert state.target_artist_mode is TargetArtistMode.new_artist
    assert state.retrieval_profile is RetrievalProfile.novelty
    assert state.process_constraints.exploration_policy.value == "diversify_artists"
    assert [(me.type, me.value, me.sentiment) for me in state.mentioned_entities] == [
        ("artist", "Drake", -1),
        ("tag", "Hip-Hop", 1),
        ("tag", "popular major hits", 1),
    ]
    assert [(r.kind, r.value) for r in state.explicit_rejections] == [
        ("artist", "Drake")
    ]
    assert state.hard_filters


def test_attribute_fact_without_facet_recovers_to_sonic():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "Something warm and dreamy.",
            "source_turn": 1,
        },
        facts=[
            {
                "type": "attribute",
                "value": "warm and dreamy",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 1,
                "mentioned_current_turn": True,
            }
        ],
    )

    assert state.facts[0].facet.value == "sonic"
    assert state.entities[0].type == "tag"
    assert state.entities[0].use_as_retrieval_seed is True


def test_performer_facet_projects_to_query_tag_surface():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "new_artist",
            "summary": "Another iconic female artist from the 90s.",
            "source_turn": 6,
        },
        facts=[
            {
                "type": "attribute",
                "facet": "performer",
                "value": "female artist",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "evidence_text": "female artist",
            }
        ],
    )

    assert state.facts[0].facet.value == "performer"
    assert [(me.type, me.value, me.sentiment) for me in state.mentioned_entities] == [
        ("tag", "female artist", 1)
    ]


def test_context_fact_cannot_keep_exact_target_reuse_semantics():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "More tracks with that same 70s rock storytelling.",
            "source_turn": 2,
        },
        facts=[
            {
                "type": "track",
                "value": "Night Moves",
                "role": "satisfied_prior",
                "anchor_use": "must_use",
                "relation": "exact_target",
                "reuse": "must_reuse",
                "source_turn": 2,
                "mentioned_current_turn": True,
                "evidence_text": "Night Moves is exactly what I had in mind",
            }
        ],
    )

    fact = state.facts[0]
    assert fact.anchor_use.value == "do_not_use"
    assert fact.relation.value == "style_reference"
    assert fact.reuse.value == "may_reuse"
    assert state.entities[0].use_as_retrieval_seed is False


def test_fact_first_state_adds_missing_facts_into_partial_entities():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "Use Reelin' In The Years as the guitar reference, not Baker Street.",
            "source_turn": 3,
        },
        facts=[
            {
                "type": "track",
                "value": "Baker Street",
                "role": "contrast",
                "anchor_use": "do_not_use",
                "source_turn": 3,
                "mentioned_current_turn": True,
                "evidence_text": "Baker Street is a classic, but",
            },
            {
                "type": "track",
                "value": "Reelin' In The Years",
                "role": "current_target",
                "anchor_use": "must_use",
                "source_turn": 3,
                "mentioned_current_turn": True,
                "evidence_text": "solos like the one in Reelin' In The Years",
            },
            {
                "type": "attribute",
                "facet": "lyrical_theme",
                "value": "Just wakin' up in the morning",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 3,
                "mentioned_current_turn": True,
                "evidence_text": "starts with Just wakin' up in the morning",
            },
        ],
        entities=[
            {
                "type": "track",
                "value": "Reelin' In The Years",
                "role": "current_target",
                "source_turn": 3,
                "mentioned_current_turn": True,
                "use_as_retrieval_seed": True,
            },
        ],
    )

    by_value = {entity.value: entity for entity in state.entities}
    assert by_value["Baker Street"].role is EntityRole.contrast
    assert by_value["Baker Street"].use_as_retrieval_seed is False
    assert by_value["Reelin' In The Years"].use_as_retrieval_seed is True
    assert by_value["Just wakin' up in the morning"].type == "tag"
    assert state.lyrical_theme == "Just wakin' up in the morning"


def test_fact_first_state_does_not_downgrade_existing_current_entity():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "same_album",
            "summary": "More from Cracker Island.",
            "source_turn": 8,
        },
        facts=[
            {
                "type": "album",
                "value": "Cracker Island",
                "role": "satisfied_prior",
                "anchor_use": "do_not_use",
                "source_turn": 7,
                "mentioned_current_turn": False,
                "evidence_text": "previous album context",
            }
        ],
        entities=[
            {
                "type": "album",
                "value": "Cracker Island",
                "role": "current_target",
                "source_turn": 8,
                "mentioned_current_turn": True,
                "use_as_retrieval_seed": True,
                "evidence_text": "More from Cracker Island",
            }
        ],
    )

    assert state.entities[0].role is EntityRole.current_target
    assert state.entities[0].use_as_retrieval_seed is True


def test_fact_first_facets_project_to_retrieval_surfaces():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "hidden_target",
            "summary": "A song with an encouraging Christian message by a male artist.",
            "source_turn": 1,
            "evidence_text": "encouraging message",
        },
        facts=[
            {
                "type": "attribute",
                "facet": "lyrical_theme",
                "value": "encouraging message",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 1,
                "mentioned_current_turn": True,
                "evidence_text": "encouraging message",
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "Christian",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 1,
                "mentioned_current_turn": True,
                "evidence_text": "Christian song",
            },
            {
                "type": "attribute",
                "facet": "visual",
                "value": "bold album cover",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 1,
                "mentioned_current_turn": True,
                "evidence_text": "album art",
            },
        ],
    )

    assert state.lyrical_theme == "encouraging message"
    assert state.retrieval_profile is RetrievalProfile.hidden_target_search
    assert state.routing_tags.hidden_target_search is True
    assert state.routing_tags.lyric_search is True
    assert state.routing_tags.image_or_visual_search is True
    assert [me.value for me in state.mentioned_entities] == [
        "encouraging message",
        "Christian",
        "bold album cover",
    ]


def test_fact_projection_overrides_noisy_llm_seed_flags_for_compiler_view():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "new_artist",
            "summary": "New bands besides Linkin Park with aggressive nu-metal sound.",
            "source_turn": 8,
            "evidence_text": "new bands for me, besides Linkin Park",
        },
        facts=[
            {
                "type": "artist",
                "value": "Linkin Park",
                "role": "satisfied_prior",
                "anchor_use": "do_not_use",
                "source_turn": 8,
                "mentioned_current_turn": True,
                "evidence_text": "besides Linkin Park",
            },
            {
                "type": "attribute",
                "facet": "genre",
                "value": "aggressive nu-metal",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 8,
                "mentioned_current_turn": True,
                "evidence_text": "aggressive nu-metal sound",
            },
        ],
        exclusions=[
            {
                "type": "artist",
                "value": "Linkin Park",
                "scope": "next_turn_hard",
                "source_turn": 8,
                "evidence_text": "besides Linkin Park",
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
                "evidence_text": "besides Linkin Park",
            }
        ],
    )

    assert state.entities[0].role is EntityRole.current_target
    assert state.entities[0].use_as_retrieval_seed is True
    assert [(me.type, me.value, me.sentiment) for me in state.mentioned_entities] == [
        ("artist", "Linkin Park", -1),
        ("tag", "aggressive nu-metal", 1),
    ]
    assert [(r.kind, r.value) for r in state.explicit_rejections] == [
        ("artist", "Linkin Park")
    ]


def test_fact_projection_keeps_soft_style_dislikes_as_tag_demotions():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "Delicate dark folk, not the metal side.",
            "source_turn": 8,
            "evidence_text": "not so much the metal side",
        },
        facts=[
            {
                "type": "attribute",
                "facet": "genre",
                "value": "dark folk",
                "role": "current_target",
                "anchor_use": "query_facet",
                "source_turn": 8,
                "mentioned_current_turn": True,
                "evidence_text": "dark folk side",
            },
            {
                "type": "attribute",
                "facet": "sonic",
                "value": "metal",
                "role": "rejected",
                "anchor_use": "do_not_use",
                "source_turn": 8,
                "mentioned_current_turn": True,
                "evidence_text": "not so much the metal side",
            },
        ],
        exclusions=[
            {
                "type": "attribute",
                "facet": "sonic",
                "value": "metal",
                "scope": "soft_preference",
                "source_turn": 8,
                "evidence_text": "not so much the metal side",
            }
        ],
        rejections=[
            {
                "kind": "artist",
                "value": "Myrkur",
                "scope": "hard",
                "source_turn": 8,
                "evidence_text": "bad compatibility field",
            }
        ],
    )

    assert [(me.type, me.value, me.sentiment) for me in state.mentioned_entities] == [
        ("tag", "metal", -1),
        ("tag", "dark folk", 1),
    ]
    assert [(r.kind, r.value) for r in state.explicit_rejections] == [
        ("tag", "metal")
    ]


def test_soft_entity_exclusion_does_not_override_current_exact_target():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "exact_track",
            "summary": "Play The Spirit of Radio by Rush instead.",
            "source_turn": 3,
            "evidence_text": "play The Spirit of Radio by Rush instead",
        },
        facts=[
            {
                "type": "track",
                "value": "Tom Sawyer",
                "role": "rejected",
                "anchor_use": "do_not_use",
                "relation": "exclude",
                "reuse": "must_exclude",
                "source_turn": 3,
                "mentioned_current_turn": True,
                "evidence_text": "problem with Tom Sawyer",
            },
            {
                "type": "track",
                "value": "The Spirit of Radio",
                "role": "current_target",
                "anchor_use": "must_use",
                "relation": "exact_target",
                "reuse": "must_reuse",
                "source_turn": 3,
                "mentioned_current_turn": True,
                "evidence_text": "play The Spirit of Radio",
            },
            {
                "type": "artist",
                "value": "Rush",
                "role": "current_target",
                "anchor_use": "must_use",
                "relation": "exact_target",
                "reuse": "must_reuse",
                "source_turn": 3,
                "mentioned_current_turn": True,
                "evidence_text": "by Rush",
            },
        ],
        exclusions=[
            {
                "type": "track",
                "value": "Tom Sawyer",
                "scope": "next_turn_hard",
                "source_turn": 3,
                "evidence_text": "problem with Tom Sawyer",
            },
            {
                "type": "artist",
                "value": "Rush",
                "scope": "soft_preference",
                "source_turn": 1,
                "evidence_text": "prior compatibility noise",
            },
        ],
    )

    assert [(me.type, me.value, me.sentiment) for me in state.mentioned_entities] == [
        ("track", "Tom Sawyer", -1),
        ("track", "The Spirit of Radio", 1),
        ("artist", "Rush", 1),
    ]
    assert [(r.kind, r.value) for r in state.explicit_rejections] == [
        ("track", "Tom Sawyer")
    ]


def test_fact_relation_and_reuse_split_exact_targets_from_style_references():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "new_artist",
            "summary": "A new artist with the off-kilter Flying Lotus feel, but keep Mac Miller.",
            "source_turn": 4,
            "evidence_text": "new artist with the off-kilter Flying Lotus feel",
        },
        facts=[
            {
                "type": "artist",
                "value": "Mac Miller",
                "role": "current_target",
                "anchor_use": "must_use",
                "relation": "exact_target",
                "reuse": "must_reuse",
                "source_turn": 4,
                "mentioned_current_turn": True,
                "evidence_text": "keep Mac Miller",
            },
            {
                "type": "artist",
                "value": "Flying Lotus",
                "role": "current_target",
                "anchor_use": "partial_anchor",
                "relation": "style_reference",
                "reuse": "avoid_exact",
                "source_turn": 4,
                "mentioned_current_turn": True,
                "evidence_text": "Flying Lotus feel",
            },
            {
                "type": "attribute",
                "facet": "sonic",
                "value": "off-kilter",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 4,
                "mentioned_current_turn": True,
                "evidence_text": "off-kilter",
            },
        ],
    )

    assert [(me.type, me.value, me.sentiment) for me in state.mentioned_entities] == [
        ("artist", "Mac Miller", 1),
        ("tag", "off-kilter", 1),
    ]
    assert [
        (entity.type, entity.value, entity.sentiment)
        for entity in state.style_reference_entities
    ] == [("artist", "Flying Lotus", 1)]


def test_satisfied_prior_can_still_project_as_style_reference_when_explicit():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "new_artist",
            "summary": "Different artists with Sadistik's dark introspective style.",
            "source_turn": 3,
            "evidence_text": "different artists",
        },
        facts=[
            {
                "type": "artist",
                "value": "Sadistik",
                "role": "satisfied_prior",
                "anchor_use": "do_not_use",
                "relation": "style_reference",
                "reuse": "avoid_exact",
                "source_turn": 3,
                "mentioned_current_turn": True,
                "evidence_text": "big fan of his work but branch out",
            },
            {
                "type": "attribute",
                "facet": "lyrical_theme",
                "value": "dark introspective lyrics",
                "role": "current_target",
                "anchor_use": "query_facet",
                "relation": "query_facet",
                "reuse": "not_applicable",
                "source_turn": 3,
                "mentioned_current_turn": True,
                "evidence_text": "dark and introspective",
            },
        ],
    )

    assert ("artist", "Sadistik", 1) not in [
        (entity.type, entity.value, entity.sentiment)
        for entity in state.mentioned_entities
    ]
    assert [
        (entity.type, entity.value, entity.sentiment)
        for entity in state.style_reference_entities
    ] == [("artist", "Sadistik", 1)]


def test_satisfied_prior_projects_as_soft_style_context_by_default():
    state = ConversationStateV0Plus(
        current_request={
            "request_type": "attribute_search",
            "summary": "More hip-hop with strong lyrical storytelling.",
            "source_turn": 6,
        },
        facts=[
            {
                "type": "artist",
                "value": "Mac Miller",
                "role": "satisfied_prior",
                "anchor_use": "do_not_use",
                "relation": "satisfied_prior",
                "reuse": "avoid_exact",
                "source_turn": 6,
                "mentioned_current_turn": True,
                "evidence_text": "fantastic pick from Mac Miller",
            }
        ],
    )

    assert [
        (entity.type, entity.value, entity.sentiment)
        for entity in state.style_reference_entities
    ] == [("artist", "Mac Miller", 1)]
