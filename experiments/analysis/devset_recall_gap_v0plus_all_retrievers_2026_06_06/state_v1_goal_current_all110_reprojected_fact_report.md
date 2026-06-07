# State Fact Label Evaluation

- Labels: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_fact_labels_v1.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_goal_current_all110_reprojected_audit.jsonl`
- Samples: `56`
- All-pass: `0.714`

## Fact Classes

| Fact class | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| album_rejection_visual | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| artist_similarity | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| attribute_from_prior | 6 | 0.500 | 0.667 | 0.833 | 0.667 | 1.000 | 1.000 | 1.000 |
| attribute_new_artist | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_refinement | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_search | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_temporal | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_visual | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contrast_hidden_target | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_album | 2 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_artist_alternatives | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_entity | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_track_album | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| genre_search | 2 | 0.000 | 0.500 | 0.500 | 0.500 | 1.000 | 1.000 | 1.000 |
| hard_rejection | 3 | 0.667 | 0.667 | 1.000 | 0.667 | 1.000 | 1.000 | 1.000 |
| hidden_target_attribute | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hidden_target_temporal | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| lyric_hidden_target | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| negative_feedback_attribute | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| negative_feedback_temporal | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 |
| new_artist_from_prior | 4 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| new_artist_temporal | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| popular_new_artist | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| same_album | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_artist_album | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_artist_or_attribute | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| same_artist_refinement | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_style_after_exact | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| style_rejection | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |
| temporal_style_era | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Packs

| Pack | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_good_state_ranker_near_miss_failure | 5 | 0.400 | 0.400 | 0.800 | 0.400 | 1.000 | 1.000 | 1.000 |
| P0_named_artist_ranker_failure | 5 | 0.800 | 1.000 | 0.800 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 5 | 0.400 | 0.600 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 5 | 0.800 | 1.000 | 0.800 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 5 | 0.800 | 0.800 | 1.000 | 0.800 | 1.000 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 5 | 0.800 | 1.000 | 0.800 | 1.000 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 5 | 0.200 | 0.400 | 0.800 | 0.600 | 1.000 | 0.600 | 1.000 |
| P1_temporal_constraint_failure | 5 | 0.600 | 0.800 | 0.600 | 1.000 | 1.000 | 0.800 | 1.000 |
| POS_clean_final_hit_control | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| POS_exact_entity_success_control | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Failures

### `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Fact class: `attribute_from_prior`
- Missing facts: `request_type`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": true,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": true,
  "expected": {
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "positive_anchor"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Mr. Bungle"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "experimental"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "genre-bending"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "what else",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.4,
          "evidence_text": "similar experimental genre-bending vibe",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "what else could you recommend that has a similar experimental, genre-bending vibe",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Other experimental genre-bending rock from the 90s with avant-garde theatrical energy, using Mr. Bungle as a style reference but different artists."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Mr. Bungle"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "experimental genre-bending"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "avant-garde theatrical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "high energy"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "different artists",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "artist",
        "value": "Mr. Bungle"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "That's exactly the band",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Mr. Bungle"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "experimental, genre-bending vibe",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "experimental genre-bending"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "avant-garde or theatrical feel",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "avant-garde theatrical"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "high energy",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "high energy"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Mr. Bungle"
      }
    ],
    "temporal_constraint": null
  }
}
```

### `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `popular_new_artist`
- Missing facts: `request_type, Michael Jackson, popular, popular role in ['current_target', 'seed'], popular, popular use_as_retrieval_seed=True`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": false,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "forbidden_seed_values": [
      "Michael Jackson"
    ],
    "request_type": "new_artist",
    "required_entities": [
      {
        "allowed_roles": [
          "satisfied",
          "history"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Michael Jackson"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "well-known"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "popular"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "well-known, feel-good, strong beat, widely loved",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "These are exactly the kind",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "well-known songs... popular and have that feel-good energy",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another well-known, feel-good pop or R&B song with a strong beat and wide popularity, similar in popularity/energy to the liked prior tracks."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "well-known"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "widely loved"
      },
      {
        "role": "satisfied",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "hugely popular"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "feel-good"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong beat"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "upbeat"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "energetic"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "well-known songs",
        "facet": "popularity",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "well-known"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "widely loved",
        "facet": "popularity",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "widely loved"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "powerful and energetic song that everybody knows",
        "facet": "popularity",
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "attribute",
        "value": "hugely popular"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "feel-good energy",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "feel-good"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "strong beat",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "strong beat"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "upbeat",
        "facet": "energy",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "upbeat"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "energetic song",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "energetic"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `attribute_from_prior`
- Missing facts: `Flying Lotus`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": true,
    "required_entities": false,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "positive_anchor"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Flying Lotus"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "electronic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "soulful"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "out there"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "really out there",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "What else",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "What else have you got that's really out there?",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "What else that is really unique/out-there, electronic, and soulful; keep the discovery journey going."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "unique and out-there"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "electronic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "soulful"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "interesting mix of sounds"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "really out there",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "track",
        "value": "unique and out-there"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "electronic",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "soulful",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "soulful"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "interesting mix of sounds",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "interesting mix of sounds"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `b466a64b-b3cc-4c62-8a70-8261434f915f::t2`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `same_style_after_exact`
- Missing facts: `request_type`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": true,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": true,
  "expected": {
    "request_type": "similar_to_prior",
    "required_entities": [
      {
        "allowed_roles": [
          "satisfied",
          "history"
        ],
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Finally"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "CeCe Peniston"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "90s dance hits"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "iconic 90s dance hits",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.65,
          "evidence_text": "similar to this one",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "other iconic 90s dance hits similar to this one",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "Other iconic 90s dance hits with similar energetic, dance-worthy feel to 'Finally'."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Finally"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "CeCe Peniston"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "iconic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "1990s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dance"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "energetic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dance-worthy"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Finally is it",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "track",
        "value": "Finally"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "CeCe Peniston",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "artist",
        "value": "CeCe Peniston"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "iconic",
        "facet": "popularity",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "iconic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "90s dance hits",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "1990s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dance hits",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "dance"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "really energetic",
        "facet": "energy",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "energetic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "makes you want to dance",
        "facet": "mood",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "dance-worthy"
      }
    ],
    "rejections": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1999
      ],
      "strength": "soft"
    }
  }
}
```

### `f2d85aa5-2086-4b1e-9974-d188c43621db::t8`

- Pack: `P1_temporal_constraint_failure`
- Fact class: `negative_feedback_temporal`
- Missing facts: `request_type, exclusion: dark and harsh`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": true,
    "required_exclusions": false,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dreamy"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "serene"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ambient electronic"
      }
    ],
    "required_exclusions": [
      {
        "scope": "hard",
        "type": "style",
        "value": "dark and harsh"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": [
        true,
        false
      ],
      "kind": [
        "style_era",
        "reference_era"
      ],
      "strength": [
        "hard",
        "soft"
      ]
    }
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "specifically trying to recall",
          "request_type": "hidden_target"
        },
        {
          "confidence": 0.7,
          "evidence_text": "not what I'm looking for at all",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "not what I'm looking for at all. The mood is too dark and harsh, not dreamy or serene like the late 2000s ambient electronic I'm trying to find. Also, the era is still off. I'm specifically looking for something with a wa...",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "Find a warm, dreamy, serene, strictly instrumental ambient electronic track that screams late 2000s (specifically 2009 era); not too dark or harsh."
    },
    "entities": [
      {
        "role": "contrast",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Sleep Paralysis"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "dark and harsh"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dreamy serene"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ambient electronic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "late 2000s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "warm evolving pads"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "subtle rhythms"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "instrumental"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "too dark and harsh",
        "facet": "mood",
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "attribute",
        "value": "dark and harsh"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Sleep Paralysis is not what I'm looking for at all",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "contrast",
        "reuse": "not_applicable",
        "role": "contrast",
        "source_turn": 3,
        "type": "track",
        "value": "Sleep Paralysis"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too dark and harsh",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 3,
        "type": "attribute",
        "value": "dark and harsh"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "not dreamy or serene",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "dreamy serene"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "ambient electronic",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "ambient electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "late 2000s ambient electronic",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "late 2000s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "warm, evolving pads",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "warm evolving pads"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "subtle rhythms",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "subtle rhythms"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "instrumental or purely electronic",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "instrumental"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "dark and harsh"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "dark and harsh"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2007,
        2009
      ],
      "strength": "soft"
    }
  }
}
```

### `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6`

- Pack: `P1_temporal_constraint_failure`
- Fact class: `exact_album`
- Missing facts: `request_type`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": true,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": true,
  "expected": {
    "request_type": "exact_album",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Panic! At The Disco"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "A Fever You Can't Sweat Out"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "mid-2000s emo"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": [
        "style_era",
        "reference_era"
      ],
      "strength": "soft"
    }
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "the track I'm thinking of",
          "request_type": "hidden_target"
        }
      ],
      "evidence_text": "not the one that screams mid-2000s emo phase to me",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "Find the mid-2000s Panic! At The Disco track from A Fever You Can't Sweat Out with a dramatic, driving sound and lyrics about a messy breakup or angst."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Panic! At The Disco"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "A Fever You Can't Sweat Out"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "mid-2000s emo"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dramatic driving sound"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "messy breakup angst"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "Panic! At The Disco",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Panic! At The Disco"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "from their first album, A Fever You Can't Sweat Out",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 3,
        "type": "album",
        "value": "A Fever You Can't Sweat Out"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "mid-2000s emo phase",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "mid-2000s emo"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dramatic driving sound",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "dramatic driving sound"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "lyrics about a messy breakup or angst",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "messy breakup angst"
      }
    ],
    "rejections": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2004,
        2007
      ],
      "strength": "soft"
    }
  }
}
```

### `1e14a07f-7369-4d24-9285-9343b6b18353::t8`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `style_rejection`
- Missing facts: `exclusion: metal`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": true,
    "required_entities": true,
    "required_exclusions": false,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "forbidden_seed_values": [
      "Gladiatrix"
    ],
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "atmospheric"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "haunting"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ethereal vocals"
      }
    ],
    "required_exclusions": [
      {
        "scope": "hard",
        "type": "style",
        "value": "metal"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [],
      "evidence_text": "something much more atmospheric and haunting, with ethereal vocals and traditional instruments, not so much the metal side",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Atmospheric and haunting dark/gothic folk or ambient folk with ethereal vocals and traditional instruments, avoiding heavy/intense metal qualities."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark folk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "gothic folk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "atmospheric"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "haunting"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ethereal vocals"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "traditional instruments"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "heavy and intense"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "too heavy and intense",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "attribute",
        "value": "heavy and intense"
      }
    ],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "dark folk",
        "facet": "genre",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "dark folk"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "gothic folk",
        "facet": "genre",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "gothic folk"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "much more atmospheric",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "atmospheric"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "haunting",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "haunting"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "ethereal vocals",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "ethereal vocals"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "traditional instruments",
        "facet": "instrument",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "traditional instruments"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too heavy and intense",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 3,
        "type": "attribute",
        "value": "heavy and intense"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "heavy and intense"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "heavy and intense"
      }
    ],
    "temporal_constraint": null
  }
}
```

### `d265b5a9-af57-4070-90f5-692a960c5aaa::t6`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `album_rejection_visual`
- Missing facts: `request_type`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": true,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": true,
  "expected": {
    "forbidden_seed_values": [
      "Random Access Memories",
      "Daft Punk"
    ],
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "rejected",
          "history",
          "satisfied"
        ],
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "Random Access Memories"
      },
      {
        "allowed_roles": [
          "rejected",
          "history",
          "satisfied"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Daft Punk"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "striking"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "artistically unique"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "new album discoveries from the 2010s, specifically electronic albums with covers that are just as striking or artistically unique as Daft Punk's, but definitely not from Daft Punk or Four Tet",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.7,
          "evidence_text": "covers that are just as striking or artistically unique",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "new album discoveries from the 2010s, specifically electronic albums with covers that are just as striking or artistically unique as Daft Punk's, and not from Daft Punk or Four Tet",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "New-to-me electronic albums from the 2010s with striking, artistically unique cover art; avoid previously satisfied artists (Daft Punk, Four Tet) and the albums Random Access Memories and New Energy."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Daft Punk"
      },
      {
        "role": "satisfied",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "Random Access Memories"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Four Tet"
      },
      {
        "role": "satisfied",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "New Energy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "electronic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2010s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "striking cover art"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "artistically unique cover art"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Contact"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "not from Daft Punk",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "evidence_text": "not from Daft Punk or Four Tet",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "artist",
        "value": "Four Tet"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "I've listened to Random Access Memories countless times … not from Daft Punk or Four Tet",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "listened to Random Access Memories countless times",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not from Daft Punk or Four Tet",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Four Tet"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "beyond 'Random Access Memories' and 'New Energy'",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "album",
        "value": "New Energy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "electronic albums",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "from the 2010s",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "2010s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "striking or artistically unique cover art",
        "facet": "visual",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "striking cover art"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "striking or artistically unique cover art",
        "facet": "visual",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "artistically unique cover art"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Contact is a classic",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "track",
        "value": "Contact"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Daft Punk"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Four Tet"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2010,
        2019
      ],
      "strength": "soft"
    }
  }
}
```

### `b2582e52-6d13-40b4-8552-2d8b63fa6c75::t8`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `hard_rejection`
- Missing facts: `System Of A Down, System Of A Down role in ['rejected']`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": true,
    "required_entities": false,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "forbidden_seed_values": [
      "System Of A Down"
    ],
    "request_type": "new_artist",
    "required_entities": [
      {
        "allowed_roles": [
          "rejected"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "System Of A Down"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy alternative metal"
      }
    ],
    "required_exclusions": [
      {
        "scope": "hard",
        "type": "artist",
        "value": "System Of A Down"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "ready to discover something new",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.5,
          "evidence_text": "similar in style to System of a Down",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "new bands with that heavy, alternative metal sound",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "New bands similar in style to System of a Down (heavy alternative metal), but not System of a Down themselves."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "System of a Down"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "alternative metal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "new bands"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "similar in style to System of a Down, but not them",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "artist",
        "value": "System of a Down"
      }
    ],
    "facts": [
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "similar in style to System of a Down, but not them",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "System of a Down"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "heavy, alternative metal sound",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "alternative metal"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "heavy, alternative metal",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "heavy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "new bands",
        "facet": "performer",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "new bands"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "System of a Down"
      }
    ],
    "temporal_constraint": null
  }
}
```

### `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `negative_feedback_attribute`
- Missing facts: `Lupe Fiasco, Lupe Fiasco role in ['contrast', 'history', 'satisfied'], boost my energy, exclusion: heavy and intense`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": true,
    "required_entities": false,
    "required_exclusions": false,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "history",
          "contrast",
          "satisfied"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Lupe Fiasco"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "positive vibe"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "boost my energy"
      }
    ],
    "required_exclusions": [
      {
        "scope": "hard",
        "type": "style",
        "value": "heavy and intense"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "positive vibe to boost my energy",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.7,
          "evidence_text": "not Lupe Fiasco",
          "request_type": "new_artist"
        }
      ],
      "evidence_text": "hip-hop that has a positive vibe to boost my energy and put me in a good mood",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Positive, uplifting, energetic hip-hop, not Lupe Fiasco, not heavy/intense."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Lupe Fiasco"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "he said 'positive vibe'"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "energetic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "uplifting"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "heavy and intense"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "not Lupe Fiasco",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "artist",
        "value": "Lupe Fiasco"
      },
      {
        "evidence_text": "heavy and intense",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "attribute",
        "value": "heavy and intense"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not Lupe Fiasco",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 3,
        "type": "artist",
        "value": "Lupe Fiasco"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "positive vibe",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "he said 'positive vibe'"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "boost my energy",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "energetic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "put me in a good mood",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "uplifting"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "heavy and intense",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 3,
        "type": "attribute",
        "value": "heavy and intense"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "heavy and intense",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 3,
        "type": "attribute",
        "value": "heavy and intense"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Lupe Fiasco"
      },
      {
        "kind": "tag",
        "scope": "soft",
        "value": "heavy and intense"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "heavy and intense"
      }
    ],
    "temporal_constraint": null
  }
}
```

### `fc78453a-8798-4402-a01a-e9c557f08a03::t2`

- Pack: `P0_named_artist_ranker_failure`
- Fact class: `exact_album`
- Missing facts: `request_type`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": true,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": true,
  "expected": {
    "request_type": "exact_album",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Natalia Lafourcade"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Natalia Lafourcade"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.3,
          "evidence_text": "Natalia Lafourcade's earlier work",
          "request_type": "same_artist"
        }
      ],
      "evidence_text": "from her first album, 'Natalia Lafourcade'",
      "request_type": "same_album",
      "source_turn": 2,
      "summary": "A track from Natalia Lafourcade's first album, 'Natalia Lafourcade'."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Natalia Lafourcade"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Natalia Lafourcade"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "her earlier work",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "Natalia Lafourcade"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "first album 'Natalia Lafourcade'",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 2,
        "type": "album",
        "value": "Natalia Lafourcade"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `c863175a-bbaf-4f6c-aef7-cb16f2792cb5::t6`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `same_artist_or_attribute`
- Missing facts: `Mac Miller, Mac Miller use_as_retrieval_seed=True`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": true,
    "required_entities": false,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "request_type": "similar_to_prior",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed",
          "satisfied"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Mac Miller"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "lyrical storytelling"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.8,
          "evidence_text": "more hip-hop tracks that are super strong on the lyrical storytelling about relationships",
          "request_type": "similar_to_prior"
        },
        {
          "confidence": 0.65,
          "evidence_text": "super strong on the lyrical storytelling about relationships",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.5,
          "evidence_text": "either by Mac Miller or artists with a similar... [interrupted turn 2]",
          "request_type": "same_artist"
        }
      ],
      "evidence_text": "more hip-hop tracks that are super strong on the lyrical storytelling about relationships",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "More hip-hop tracks with strong lyrical storytelling about relationships, either by Mac Miller or similar artists."
    },
    "entities": [
      {
        "role": "history",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "To the Moon"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Phora"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Planet God Damn"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Mac Miller"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Soulmate"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "lyrical storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "relationships"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "To the Moon by Phora is a good one too",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "history",
        "source_turn": 3,
        "type": "track",
        "value": "To the Moon"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "To the Moon by Phora is a good one too",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "history",
        "source_turn": 3,
        "type": "artist",
        "value": "Phora"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Mac Miller's Planet God Damn is perfect",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "track",
        "value": "Planet God Damn"
      },
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "by Mac Miller or artists with a similar",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Mac Miller"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Soulmate is another fantastic pick",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "track",
        "value": "Soulmate"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "hip-hop tracks",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "hip-hop"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "super strong on the lyrical storytelling",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "lyrical storytelling"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "storytelling about relationships",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "relationships"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `1c567917-f931-4609-9695-a9c0f8e39f3d::t2`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Fact class: `genre_search`
- Missing facts: `request_type`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": true,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": true,
  "expected": {
    "forbidden_seed_values": [
      "Anitta"
    ],
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "satisfied",
          "history"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Anitta"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "tecno brega"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk carioca"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "what about ... scenes",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.5,
          "evidence_text": "more recent and upbeat",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "tecno brega or funk carioca scenes",
      "request_type": "new_artist",
      "source_turn": 2,
      "summary": "More recent upbeat Brazilian tracks from the 'tecno brega' or 'funk carioca' scenes; separate from Anitta."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Anitta"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "tecno brega"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk carioca"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "recent"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "upbeat"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "contemporary Brazilian dance and pop"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Anitta is definitely on point",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "artist",
        "value": "Anitta"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "tecno brega",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "tecno brega"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "funk carioca",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "funk carioca"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "more recent",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "recent"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "upbeat",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "upbeat"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "contemporary Brazilian dance and pop",
        "facet": "genre",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "contemporary Brazilian dance and pop"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `be88097f-b6b0-4fb4-bed9-857a92a733c0::t3`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Fact class: `attribute_from_prior`
- Missing facts: `Baker Street, Baker Street role in ['contrast', 'history'], Reelin' In The Years, Reelin' In The Years use_as_retrieval_seed=True`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": true,
    "required_entities": false,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "forbidden_seed_values": [
      "Baker Street"
    ],
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "history",
          "contrast"
        ],
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Baker Street"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed",
          "positive_anchor"
        ],
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Reelin' In The Years"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "guitar"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "intricate or smooth solos",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.65,
          "evidence_text": "like the one in 'Reelin' In The Years'",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "guitar is the star",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "70s rock songs where the guitar is the star, with intricate or smooth solos like 'Reelin' In The Years' by Steely Dan, but no more Baker Street."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Reelin' In The Years"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Steely Dan"
      },
      {
        "role": "rejected",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Baker Street"
      },
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Gerry Rafferty"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "70s rock guitar"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intricate guitar solos"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "smooth guitar solos"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "guitar is the star"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "1970s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "killer guitar work"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "Baker Street is a classic, but",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "track",
        "value": "Baker Street"
      },
      {
        "evidence_text": "Baker Street",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 2,
        "type": "artist",
        "value": "Gerry Rafferty"
      }
    ],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "like the one in 'Reelin' In The Years'",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "current_target",
        "source_turn": 3,
        "type": "track",
        "value": "Reelin' In The Years"
      },
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "Reelin' In The Years",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Steely Dan"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Baker Street is a classic, but",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 3,
        "type": "track",
        "value": "Baker Street"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Baker Street",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 2,
        "type": "artist",
        "value": "Gerry Rafferty"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "70s rock songs",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "70s rock guitar"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "intricate or smooth solos",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "intricate guitar solos"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "intricate or smooth solos",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "smooth guitar solos"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "guitar is the star",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "guitar is the star"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "70s",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "1970s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "killer guitar work",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "killer guitar work"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "Baker Street"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Gerry Rafferty"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1970,
        1979
      ],
      "strength": "soft"
    }
  }
}
```

### `2db3ddc8-78a1-412c-a71e-e0d748aab0e7::t2`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Fact class: `artist_similarity`
- Missing facts: `request_type, John Fogerty, John Fogerty use_as_retrieval_seed=True, Bruce Springsteen, Bruce Springsteen use_as_retrieval_seed=True`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": false,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "request_type": "similar_to_prior",
    "required_entities": [
      {
        "allowed_roles": [
          "satisfied",
          "history"
        ],
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Night Moves"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "John Fogerty"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Bruce Springsteen"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "distinctive 70s rock sound and lyrical depth",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.65,
          "evidence_text": "same distinctive 70s rock sound",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "someone like John Fogerty or Bruce Springsteen",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "More tracks with a distinctive 70s rock sound and lyrical depth, using John Fogerty and Bruce Springsteen as style references."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Night Moves"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Bob Seger"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "John Fogerty"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Bruce Springsteen"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "distinctive 70s rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "lyrical depth"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "exactly what I had in mind",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "track",
        "value": "Night Moves"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "like Bob Seger",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 1,
        "type": "artist",
        "value": "Bob Seger"
      },
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "someone like John Fogerty",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "John Fogerty"
      },
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "or Bruce Springsteen",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "Bruce Springsteen"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "distinctive 70s rock sound",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "distinctive 70s rock"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "lyrical depth",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "lyrical depth"
      }
    ],
    "rejections": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1970,
        1979
      ],
      "strength": "soft"
    }
  }
}
```

### `c4c0c288-dbcd-4970-ad52-901aafe91b88::t1`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Fact class: `genre_search`
- Missing facts: `A Tribe Called Quest, A Tribe Called Quest use_as_retrieval_seed=True`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": true,
    "required_entities": false,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": true
  },
  "compiler_core_pass": false,
  "expected": {
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazz-infused hip-hop"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed",
          "positive_anchor"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "A Tribe Called Quest"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": [
        "style_era",
        "reference_era"
      ],
      "strength": "soft"
    }
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.8,
          "evidence_text": "jazz-infused hip-hop, underground fans",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.45,
          "evidence_text": "like A Tribe Called Quest",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "jazz-infused hip-hop",
      "request_type": "attribute_search",
      "source_turn": 1,
      "summary": "Classic jazz-infused hip-hop popular with underground fans from the early 90s, using A Tribe Called Quest as a style reference."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "A Tribe Called Quest"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazz-infused hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground fans"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 90s"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "like A Tribe Called Quest",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "current_target",
        "source_turn": 1,
        "type": "artist",
        "value": "A Tribe Called Quest"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "classic jazz-infused hip-hop",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "jazz-infused hip-hop"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "popular with underground fans",
        "facet": "popularity",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "underground fans"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "from the early 90s",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "early 90s"
      }
    ],
    "rejections": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1994
      ],
      "strength": "soft"
    }
  }
}
```

