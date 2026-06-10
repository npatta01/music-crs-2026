# State Fact Label Evaluation

- Labels: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_fact_labels_v1.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_fact_v1_paid_current_full_current_repaired_audit.jsonl`
- Samples: `56`
- All-pass: `0.768`

## Fact Classes

| Fact class | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| album_rejection_visual | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| artist_similarity | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| attribute_from_prior | 6 | 0.833 | 1.000 | 0.833 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_new_artist | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_refinement | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_search | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_temporal | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_visual | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contrast_hidden_target | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_album | 2 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_artist_alternatives | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_entity | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_track_album | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| genre_search | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hard_rejection | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hidden_target_attribute | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hidden_target_temporal | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| lyric_hidden_target | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| negative_feedback_attribute | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| negative_feedback_temporal | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| new_artist_from_prior | 4 | 0.750 | 0.750 | 1.000 | 0.750 | 1.000 | 1.000 | 1.000 |
| new_artist_temporal | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| popular_new_artist | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_album | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_artist_album | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_artist_or_attribute | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| same_artist_refinement | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_style_after_exact | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| style_rejection | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| temporal_style_era | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Packs

| Pack | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_good_state_ranker_near_miss_failure | 5 | 0.800 | 0.800 | 0.800 | 0.800 | 1.000 | 1.000 | 1.000 |
| P0_named_artist_ranker_failure | 5 | 0.400 | 0.800 | 0.600 | 0.800 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 5 | 0.800 | 1.000 | 0.800 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 5 | 0.800 | 1.000 | 0.800 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 5 | 0.600 | 0.800 | 0.600 | 0.800 | 1.000 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 5 | 0.600 | 0.800 | 0.800 | 0.800 | 1.000 | 1.000 | 1.000 |
| P1_temporal_constraint_failure | 5 | 0.400 | 0.800 | 0.600 | 1.000 | 1.000 | 1.000 | 0.800 |
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
      "evidence_text": "similar experimental, genre-bending vibe, maybe with some really unique vocalists",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "Other experimental, genre-bending music with unique vocalists, similar to Mr. Bungle."
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
        "value": "unique vocalists"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Violenza Domestica"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "That's exactly the band I was trying to remember",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Mr. Bungle"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "great example of their sound",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "track",
        "value": "Violenza Domestica"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "experimental, genre-bending vibe",
        "facet": "sonic",
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
        "evidence_text": "unique vocalists",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "unique vocalists"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `popular_new_artist`
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
      "evidence_text": "well-known songs that are popular and have a great, positive energy, regardless of genre, as long as they're not too",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Well-known, popular, feel-good songs with great positive energy, regardless of genre, not too niche."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Michael Jackson"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Whitney Houston"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Justin Timberlake"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "India.Arie"
      },
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
        "value": "popular"
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
        "value": "positive energy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "not too niche"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Another fantastic Michael Jackson track",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Michael Jackson"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Whitney Houston is legendary",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "history",
        "reuse": "not_applicable",
        "role": "history",
        "source_turn": 3,
        "type": "artist",
        "value": "Whitney Houston"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "fantastic pick",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "history",
        "reuse": "not_applicable",
        "role": "history",
        "source_turn": 4,
        "type": "artist",
        "value": "Justin Timberlake"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "great artist",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "history",
        "reuse": "not_applicable",
        "role": "history",
        "source_turn": 5,
        "type": "artist",
        "value": "India.Arie"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "well-known songs",
        "facet": "popularity",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "well-known"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "popular",
        "facet": "popularity",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "popular"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "feel-good hits",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "feel-good"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "positive energy",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "positive energy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "not too niche",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "not too niche"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `f2d85aa5-2086-4b1e-9974-d188c43621db::t8`

- Pack: `P1_temporal_constraint_failure`
- Fact class: `negative_feedback_temporal`
- Missing facts: `temporal: kind`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": true,
    "required_entities": true,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": false
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
      "evidence_text": "warm, ethereal, and subtly rhythmic quality that truly embodies the distinct feel of the late 2000s (2007-2009)",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "A warm, ethereal, subtly rhythmic, strictly instrumental ambient electronic track from 2007-2009 that defines that late 2000s era."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dreamy"
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
        "value": "warm"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ethereal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "subtly rhythmic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strictly instrumental"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "evolving"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "too dark and harsh"
      },
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Sidewalks and Skeletons"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "serene"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ambient electronic"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "too dark and harsh",
        "facet": "mood",
        "scope": "soft_preference",
        "source_turn": 8,
        "type": "attribute",
        "value": "dark and harsh"
      },
      {
        "evidence_text": "not what I'm looking for at all",
        "facet": null,
        "scope": "soft_preference",
        "source_turn": 8,
        "type": "artist",
        "value": "Sidewalks and Skeletons"
      }
    ],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "dreamy",
        "facet": "mood",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "dreamy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "atmospheric",
        "facet": "mood",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "atmospheric"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "warm",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "warm"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "ethereal",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "ethereal"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "subtly rhythmic",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "subtly rhythmic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "strictly instrumental",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 7,
        "type": "attribute",
        "value": "strictly instrumental"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "evolving",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "evolving"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "serene",
        "facet": "mood",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 4,
        "type": "attribute",
        "value": "serene"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too dark and harsh",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 8,
        "type": "attribute",
        "value": "too dark and harsh"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not what I'm looking for at all",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 8,
        "type": "artist",
        "value": "Sidewalks and Skeletons"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "ambient electronic",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "ambient electronic"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "too dark and harsh"
      },
      {
        "kind": "artist",
        "scope": "soft",
        "value": "Sidewalks and Skeletons"
      },
      {
        "kind": "style",
        "scope": "hard",
        "value": "dark and harsh"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
      "range": [
        2007,
        2009
      ],
      "strength": "hard"
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
      "evidence_text": "the track I'm thinking of is definitely from their first album, 'A Fever You Can't Sweat Out'",
      "request_type": "hidden_target",
      "source_turn": 6,
      "summary": "Find the specific Panic! At The Disco track from 'A Fever You Can't Sweat Out' with a dramatic, theatrical, anthemic chorus about something intense."
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
        "value": "dramatic theatrical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "anthemic chorus"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intense breakup or angst"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "mid-2000s"
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
        "source_turn": 6,
        "type": "artist",
        "value": "Panic! At The Disco"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "from their first album, 'A Fever You Can't Sweat Out'",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 6,
        "type": "album",
        "value": "A Fever You Can't Sweat Out"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dramatic, theatrical sound",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "dramatic theatrical"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "iconic, anthemic chorus",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "anthemic chorus"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "lyrics about something more intense, like a breakup or just general angst",
        "facet": "lyrical_theme",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "intense breakup or angst"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "mid-2000s emo phase",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "mid-2000s"
      }
    ],
    "rejections": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2004,
        2008
      ],
      "strength": "soft"
    }
  }
}
```

### `71bb177a-dab1-4bbc-8508-22d809b05c31::t6`

- Pack: `P1_temporal_constraint_failure`
- Fact class: `new_artist_temporal`
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
      "Natalie Merchant"
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
        "value": "Natalie Merchant"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "female artist"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling"
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
      "evidence_text": "another iconic female artist from the 90s who has a similar thoughtful, storytelling approach",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Another iconic female artist from the 90s with a thoughtful, storytelling approach to their music."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Alanis Morissette"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Natalie Merchant"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "female artist"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "90s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "thoughtful storytelling"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "YES! Alanis Morissette, that's exactly who I was thinking of!",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 5,
        "type": "artist",
        "value": "Alanis Morissette"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Natalie Merchant is a great pick",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Natalie Merchant"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "female artist",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "female artist"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "from the 90s",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "90s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "thoughtful, storytelling approach",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "thoughtful storytelling"
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
      "evidence_text": "new album discoveries from the 2010s, specifically electronic albums with covers that are just as striking or artistclyc",
      "request_type": "new_artist",
      "source_turn": 6,
      "summary": "Electronic albums from the 2010s with striking, unique, abstract, or memorable cover art, from different artists than Daft Punk or Four Tet."
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
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Four Tet"
      },
      {
        "role": "satisfied",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "Random Access Memories"
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
        "value": "striking cover art"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "memorable visual identity"
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
        "value": "artistically unique"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "different artists",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 6,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "evidence_text": "different artists",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 6,
        "type": "artist",
        "value": "Four Tet"
      },
      {
        "evidence_text": "I've listened to 'Random Access Memories' countless times",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 6,
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "evidence_text": "beyond 'Random Access Memories' and 'New Energy'",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 5,
        "type": "album",
        "value": "New Energy"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "different artists",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "different artists",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Four Tet"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "I've listened to 'Random Access Memories' countless times",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "beyond 'Random Access Memories' and 'New Energy'",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 5,
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
        "source_turn": 6,
        "type": "attribute",
        "value": "electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "covers that are just as striking or artistically unique",
        "facet": "visual",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "striking cover art"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "memorable visual identity on the album art",
        "facet": "visual",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "memorable visual identity"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "from the 2010s",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "2010s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "artistically unique",
        "facet": "visual",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "artistically unique"
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
      },
      {
        "kind": "album",
        "scope": "hard",
        "value": "Random Access Memories"
      },
      {
        "kind": "album",
        "scope": "hard",
        "value": "New Energy"
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

### `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `negative_feedback_attribute`
- Missing facts: `Lupe Fiasco, Lupe Fiasco role in ['contrast', 'history', 'satisfied']`

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
      "evidence_text": "suggest something genuinely upbeat, energetic, and feel-good",
      "request_type": "attribute_search",
      "source_turn": 5,
      "summary": "Genuinely upbeat, energetic, feel-good hip-hop to boost mood and energy; no more Lupe Fiasco tracks."
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
        "value": "positive"
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
        "value": "hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "positive vibe"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "boost my energy"
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
        "evidence_text": "these last few recommendations are missing that completely",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 5,
        "type": "artist",
        "value": "Lupe Fiasco"
      },
      {
        "evidence_text": "heavy and intense",
        "facet": "mood",
        "scope": "soft_preference",
        "source_turn": 5,
        "type": "attribute",
        "value": "heavy"
      },
      {
        "evidence_text": "heavy and intense",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 5,
        "type": "attribute",
        "value": "heavy and intense"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "sticking with Lupe Fiasco... these last few recommendations are missing that completely",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 5,
        "type": "artist",
        "value": "Lupe Fiasco"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "positive vibe",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "positive"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "upbeat",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "upbeat"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "energetic",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "energetic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "feel-good",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "feel-good"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "hip-hop",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "hip-hop"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "positive vibe",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "positive vibe"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "boost my energy",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "boost my energy"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "heavy and intense",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 5,
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
        "kind": "style",
        "scope": "hard",
        "value": "heavy and intense"
      }
    ],
    "temporal_constraint": null
  }
}
```

### `899f906b-9b0b-42a6-9689-643eb9f1ed31::t8`

- Pack: `P0_named_artist_ranker_failure`
- Fact class: `new_artist_from_prior`
- Missing facts: `Linkin Park, Linkin Park role in ['history', 'rejected']`

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
      "Pantera",
      "Linkin Park"
    ],
    "request_type": "new_artist",
    "required_entities": [
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "rejected"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Pantera"
      },
      {
        "allowed_roles": [
          "history",
          "rejected"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Linkin Park"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "aggressive nu-metal"
      }
    ]
  },
  "observed": {
    "current_request": {
      "evidence_text": "new bands for me, besides Linkin Park and Pantera",
      "request_type": "new_artist",
      "source_turn": 8,
      "summary": "Discover new bands besides Linkin Park and Pantera with an aggressive nu-metal sound from the late 90s/early 2000s, mixing heavy riffs with rap or industrial/electronic influences."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Linkin Park"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Pantera"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "nu-metal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy riffs"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rap influences"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "industrial/electronic influences"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "late 90s/early 2000s"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "besides Linkin Park",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 8,
        "type": "artist",
        "value": "Linkin Park"
      },
      {
        "evidence_text": "besides Linkin Park and Pantera",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 8,
        "type": "artist",
        "value": "Pantera"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "besides Linkin Park",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 8,
        "type": "artist",
        "value": "Linkin Park"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "besides Linkin Park and Pantera",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 8,
        "type": "artist",
        "value": "Pantera"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "aggressive nu-metal sound",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "nu-metal"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "heavy riffs",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "heavy riffs"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "rap or industrial/electronic influences",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "rap influences"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "rap or industrial/electronic influences",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "industrial/electronic influences"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "late 90s/early 2000s",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "late 90s/early 2000s"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Linkin Park"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Pantera"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1997,
        2004
      ],
      "strength": "soft"
    }
  }
}
```

### `93199894-d3db-4335-8278-e1be175944e4::t6`

- Pack: `P0_named_artist_ranker_failure`
- Fact class: `exact_artist_alternatives`
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
    "request_type": "exact_artist",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Soundgarden"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Rusty Cage"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Stone Temple Pilots"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Nirvana"
      }
    ]
  },
  "observed": {
    "current_request": {
      "evidence_text": "no Soundgarden at all? ... If not, how about something by Stone Temple Pilots or Nirvana?",
      "request_type": "new_artist",
      "source_turn": 6,
      "summary": "User wants Soundgarden (specifically tracks like \"Spoonman\" or \"Rusty Cage\"), or if unavailable, another grunge band like Stone Temple Pilots or Nirvana."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Pearl Jam"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Soundgarden"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Stone Temple Pilots"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Nirvana"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Spoonman"
      },
      {
        "role": "satisfied",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "Ten"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "grunge"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Rusty Cage"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Pearl Jam is awesome",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Pearl Jam"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not explicitly requested to continue",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "album",
        "value": "Ten"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "No Soundgarden at all? Like, not even 'Rusty Cage'?",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Soundgarden"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "implicit from prior turns",
        "facet": "genre",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "grunge"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "how about something by Stone Temple Pilots",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Stone Temple Pilots"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "how about something by ... Nirvana",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Nirvana"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "Do you have any Soundgarden then, like, 'Spoonman' or something?",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 5,
        "type": "track",
        "value": "Spoonman"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "Rusty Cage",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 6,
        "type": "track",
        "value": "Rusty Cage"
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
      "evidence_text": "anything from her first album, 'Natalia Lafourcade'",
      "request_type": "same_artist",
      "source_turn": 2,
      "summary": "A track from Natalia Lafourcade's first album 'Natalia Lafourcade'."
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
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early work"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "Natalia Lafourcade",
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
        "evidence_text": "her first album, 'Natalia Lafourcade'",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 2,
        "type": "album",
        "value": "Natalia Lafourcade"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "earlier work",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "early"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `71b80ec3-6cca-48b4-b471-08efa00afa2d::t4`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `same_album`
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
    "request_type": "same_album",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Hamilton"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Eliza"
      }
    ]
  },
  "observed": {
    "current_request": {
      "evidence_text": "songs from Hamilton that really showcase Eliza's character development or her relationship with Alexander",
      "request_type": "attribute_search",
      "source_turn": 4,
      "summary": "Recommend Hamilton songs that showcase Eliza's character development or her relationship with Alexander."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Hamilton"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Eliza's character development"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "relationship with Alexander"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "character development"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Eliza"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "songs from Hamilton",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 4,
        "type": "album",
        "value": "Hamilton"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "Eliza's character development",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 4,
        "type": "attribute",
        "value": "character development"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "relationship with Alexander",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 4,
        "type": "attribute",
        "value": "relationship with Alexander"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "Eliza",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 4,
        "type": "attribute",
        "value": "Eliza"
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
- Missing facts: `request_type, Mac Miller, Mac Miller use_as_retrieval_seed=True`

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
      "evidence_text": "more hip-hop tracks that are super strong on the lyrical storytelling, especially if they have that thoughtful, reflect",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "More hip-hop tracks with strong lyrical storytelling and a thoughtful, reflective vibe, from any artist (not just Mac Miller)."
    },
    "entities": [
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Masta Ace"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Phora"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Mac Miller"
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
        "value": "hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "introspective"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "thoughtful reflective"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling lyrical storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "thoughtful"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling about relationships"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "not just Mac Miller",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Mac Miller"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "lyrical storytelling",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "storytelling lyrical storytelling"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "hip-hop tracks",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "hip-hop"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "introspective, storytelling",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "introspective"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "thoughtful, reflective",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "thoughtful"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "storytelling about relationships",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "storytelling about relationships"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
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
      "evidence_text": "same distinctive 70s rock sound and lyrical depth",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "More tracks from artists with a classic 70s rock sound and lyrical depth, similar to John Fogerty or Bruce Springsteen."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Bob Seger"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Night Moves"
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
        "value": "70s rock"
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
        "evidence_text": "that's a fantastic start",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "artist",
        "value": "Bob Seger"
      },
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
        "anchor_use": "partial_anchor",
        "evidence_text": "from someone like John Fogerty",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
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
        "reuse": "avoid_exact",
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "Bruce Springsteen"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "70s rock sound",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "70s rock"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "lyrical depth",
        "facet": "sonic",
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

