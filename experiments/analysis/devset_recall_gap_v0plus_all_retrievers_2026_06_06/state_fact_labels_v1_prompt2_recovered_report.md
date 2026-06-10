# State Fact Label Evaluation

- Labels: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_fact_labels_v1.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_fact_v1_prompt2_recovered_live_audit.jsonl`
- Samples: `56`
- All-pass: `0.571`

## Fact Classes

| Fact class | N | All pass | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|
| album_rejection_visual | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| artist_similarity | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| attribute_from_prior | 6 | 0.333 | 0.833 | 0.333 | 1.000 | 1.000 | 1.000 |
| attribute_new_artist | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| attribute_refinement | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_search | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| attribute_temporal | 5 | 0.600 | 0.800 | 1.000 | 1.000 | 1.000 | 0.800 |
| attribute_visual | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| contrast_hidden_target | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_album | 2 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_artist_alternatives | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_entity | 10 | 0.900 | 1.000 | 1.000 | 1.000 | 1.000 | 0.900 |
| exact_track_album | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| genre_search | 2 | 0.500 | 0.500 | 1.000 | 1.000 | 1.000 | 1.000 |
| hard_rejection | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hidden_target_attribute | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| hidden_target_temporal | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| lyric_hidden_target | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| negative_feedback_attribute | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| negative_feedback_temporal | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| new_artist_from_prior | 4 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| new_artist_temporal | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| popular_new_artist | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| same_album | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_artist_album | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_artist_or_attribute | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| same_artist_refinement | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_style_after_exact | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| style_rejection | 1 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |
| temporal_style_era | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Packs

| Pack | N | All pass | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0_good_state_ranker_near_miss_failure | 5 | 0.200 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 |
| P0_named_artist_ranker_failure | 5 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 5 | 0.600 | 0.800 | 0.600 | 1.000 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 5 | 0.600 | 0.800 | 0.800 | 1.000 | 1.000 | 0.800 |
| P0_roleless_stale_entity_failure | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 5 | 0.200 | 0.800 | 0.400 | 1.000 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 5 | 0.600 | 1.000 | 0.600 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 5 | 0.400 | 1.000 | 0.600 | 1.000 | 0.600 | 1.000 |
| P1_temporal_constraint_failure | 5 | 0.400 | 0.400 | 0.800 | 1.000 | 0.800 | 1.000 |
| POS_clean_final_hit_control | 5 | 0.600 | 0.800 | 1.000 | 1.000 | 1.000 | 0.600 |
| POS_exact_entity_success_control | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Failures

### `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Fact class: `attribute_from_prior`
- Missing facts: `request_type, Mr. Bungle, Mr. Bungle role in ['history', 'positive_anchor', 'satisfied'], Mr. Bungle, Mr. Bungle use_as_retrieval_seed=False`

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
      "evidence_text": "similar experimental, genre-bending vibe",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "Similar experimental, genre-bending vibe to Mr. Bungle, possibly with a theatrical or avant-garde vocal style."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Mr. Bungle"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Violenza Domestica"
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
        "value": "theatrical avant-garde vocals"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "exactly the band I was trying to remember",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Mr. Bungle"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "great example of their sound",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "track",
        "value": "Violenza Domestica"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "similar experimental, genre-bending vibe",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "experimental genre-bending"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "theatrical or avant-garde vocal style",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "theatrical avant-garde vocals"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `5f085552-b56b-440e-830b-b4e40b58f854::t6`

- Pack: `P0_novelty_prior_anchor_failure`
- Fact class: `attribute_temporal`
- Missing facts: `temporal: kind, temporal: strength, temporal: apply_as_filter`

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
        "value": "upbeat"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "high-energy country"
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
      "evidence_text": "another upbeat, high-energy country track from the late 90s or early 2000s that really gets you moving",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another upbeat, high-energy country track from the late 90s to early 2000s with a big, rousing, sing-along feel; keep the same artist scope but not pinned to the previously played specific artists."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "country"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "upbeat high-energy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rousing sing-along"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "another upbeat",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 1,
        "type": "artist",
        "value": "Shania Twain"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Keep them coming",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "history",
        "source_turn": 2,
        "type": "artist",
        "value": "Tim McGraw"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "country track",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "country"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "upbeat, high-energy",
        "facet": "energy",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "upbeat high-energy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "anthem",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "rousing sing-along"
      }
    ],
    "rejections": [],
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
      "range": [
        1990,
        2005
      ],
      "strength": "hard"
    }
  }
}
```

### `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `popular_new_artist`
- Missing facts: `request_type, popular`

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
      "evidence_text": "other well-known songs, popular and h...",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another well-known, popular, feel-good pop or R&B song with a strong beat and high energy, similar in popularity to the recent tracks."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Shawn Mendes"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Camila Cabello"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "India.Arie"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Michael Jackson"
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
        "value": "high energy"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Great recommendations so far",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 1,
        "type": "artist",
        "value": "Shawn Mendes"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Great recommendations so far",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 1,
        "type": "artist",
        "value": "Camila Cabello"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "great artist but still more upbeat popular",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "artist",
        "value": "India.Arie"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Another fantastic Michael Jackson track",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Michael Jackson"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "well-known songs, popular",
        "facet": "popularity",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "well-known"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "feel-good hits",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "feel-good"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "these are exactly",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "strong beat"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "powerful, energetic",
        "facet": "energy",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "high energy"
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
- Missing facts: `out there`

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
      "evidence_text": "What else have you got that's really out there?",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Other really out-there, unique, experimental music with a mix of cool electronic, soulful, and unexpected sounds."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Flying Lotus"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "unique"
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
        "value": "experimental"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "This is cool",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Flying Lotus"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "very unique, out there",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "unique"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "like electronic",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "soulful",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "soulful"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "out there",
        "facet": "genre",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "experimental"
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
- Missing facts: `request_type, ambient electronic, exclusion: dark and harsh`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": false,
    "required_exclusions": false,
    "schema_valid": true,
    "temporal_constraint": true
  },
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
      "evidence_text": "specifically looking for something with a wa...",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "Trying to recall a late 2000s dreamy, atmospheric, evolving instrumental electronic track."
    },
    "entities": [
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
        "value": "dreamy serene"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "instrumental electronic"
      },
      {
        "role": "rejected",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Sleep Paralysis"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "spoken word element wrong",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 2,
        "type": "track",
        "value": "A Glorious Dawn"
      },
      {
        "evidence_text": "too dark and harsh",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "track",
        "value": "Sleep Paralysis"
      },
      {
        "evidence_text": "too dark and harsh",
        "facet": "mood",
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "attribute",
        "value": "dark harsh"
      }
    ],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "late 2000s ambient electronic I'm trying to find",
        "facet": "era",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "late 2000s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dreamy or serene like the late 2000s ambient electronic",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "dreamy serene"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "evolving atmosphere",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "evolving"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "instrumental or purely electronic track",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "instrumental electronic"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "spoken word element wrong",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "contrast",
        "source_turn": 2,
        "type": "track",
        "value": "A Glorious Dawn"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "spoken word wrong",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "contrast",
        "source_turn": 2,
        "type": "artist",
        "value": "Carl Sagan"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too dark and harsh",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "contrast",
        "source_turn": 3,
        "type": "track",
        "value": "Sleep Paralysis"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not what I'm looking for",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "contrast",
        "source_turn": 3,
        "type": "artist",
        "value": "Sidewalks and Skeletons"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "Sleep Paralysis"
      },
      {
        "kind": "tag",
        "scope": "soft",
        "value": "dark harsh"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2005,
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
      "evidence_text": "track from their first album, A Fever You Can't Sweat Out, mid-2000s emo phase",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "Recall a specific mid-2000s Panic! At The Disco track from 'A Fever You Can't Sweat Out' with dramatic, driving sound and emo angst/breakup angst lyrics."
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
        "value": "mid-2000s"
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
        "value": "emo angst breakup"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "not the song I'm thinking of",
        "facet": null,
        "scope": "soft_preference",
        "source_turn": 1,
        "type": "track",
        "value": "This Is Gospel"
      },
      {
        "evidence_text": "you're so close but not the right lyrics",
        "facet": null,
        "scope": "soft_preference",
        "source_turn": 2,
        "type": "track",
        "value": "But It's Better If You Do"
      },
      {
        "evidence_text": "still not the one",
        "facet": null,
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "track",
        "value": "Always"
      }
    ],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "first album, A Fever You Can't Sweat Out",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Panic! At The Disco"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "their first album, A Fever You Can't Sweat Out",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "album",
        "value": "A Fever You Can't Sweat Out"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "mid-2000s emo phase",
        "facet": "era",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "mid-2000s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dramatic, driving sound",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "dramatic driving sound"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "emotional chorus, intense lyrics about angst or a breakup",
        "facet": "lyrical_theme",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "emo angst breakup"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "soft",
        "value": "This Is Gospel"
      },
      {
        "kind": "track",
        "scope": "soft",
        "value": "But It's Better If You Do"
      },
      {
        "kind": "track",
        "scope": "soft",
        "value": "Always"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2005,
        2006
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
      "evidence_text": "another iconic female artist from the 90s",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another iconic female artist from the 90s with a thoughtful, storytelling, introspective, and raw style, similar to Alanis Morissette and Natalie Merchant."
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
        "value": "1990s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "thoughtful, storytelling"
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
        "value": "raw"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "female artist from the 90s",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Alanis Morissette"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "great pick",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Natalie Merchant"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "iconic female artist",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "female artist"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "from the 90s",
        "facet": "era",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "1990s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "thoughtful, storytelling approach",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "thoughtful, storytelling"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "introspective",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "introspective"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "raw style",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "raw"
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
      "evidence_text": "something much more atmospheric and haunting, with ethereal vocals and traditional instruments",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Atmospheric, haunting dark/gothic folk with ethereal female vocals and traditional instruments, no metal side."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "atmospheric dark folk"
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
        "value": "ethereal"
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
        "value": "traditional instruments"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "metal"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "not so much the metal side",
        "facet": "genre",
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "attribute",
        "value": "metal"
      },
      {
        "evidence_text": "too heavy",
        "facet": "energy",
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "attribute",
        "value": "heavy"
      }
    ],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "atmospheric dark folk",
        "facet": "genre",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "atmospheric dark folk"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "gothic folk",
        "facet": "genre",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "gothic folk"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "ethereal vocals",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "ethereal"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "haunting",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "haunting"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "traditional instruments",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "traditional instruments"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not so much the metal side",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "attribute",
        "value": "metal"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too heavy",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 2,
        "type": "attribute",
        "value": "heavy"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too heavy and intense",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "attribute",
        "value": "intense"
      }
    ],
    "rejections": [
      {
        "kind": "style",
        "scope": "soft",
        "value": "metal"
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "heavy"
      }
    ],
    "temporal_constraint": null
  }
}
```

### `d265b5a9-af57-4070-90f5-692a960c5aaa::t6`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `album_rejection_visual`
- Missing facts: `artistically unique`

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
      "evidence_text": "new album discoveries ... electronic albums with covers that are just as striking ... beyond Daft Punk ... outside of '4",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Electronic albums from the 2010s with striking, artistically unique covers; exclude Daft Punk/Random Access Memories and Four Tet/New Energy."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Daft Punk"
      },
      {
        "role": "rejected",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "Random Access Memories"
      },
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Four Tet"
      },
      {
        "role": "rejected",
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
        "value": "2010s"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "beyond Daft Punk",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "evidence_text": "listened to 'Random Access Memories' countless times",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "evidence_text": "outside of 'Four Tet",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "artist",
        "value": "Four Tet"
      },
      {
        "evidence_text": "beyond 'New Energy'",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "album",
        "value": "New Energy"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "beyond Daft Punk",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "listened to 'Random Access Memories' countless times",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "outside of 'Four Tet",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "rejected",
        "source_turn": 3,
        "type": "artist",
        "value": "Four Tet"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "beyond 'New Energy'",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 2,
        "type": "album",
        "value": "New Energy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "electronic albums",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "striking",
        "facet": "visual",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "striking"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "artistically unique",
        "facet": "visual",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "artistically unique cover"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "from the 2010s",
        "facet": "era",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "2010s"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Daft Punk"
      },
      {
        "kind": "album",
        "scope": "hard",
        "value": "Random Access Memories"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Four Tet"
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
- Missing facts: `positive vibe, boost my energy, exclusion: heavy and intense`

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
      "evidence_text": "hip-hop that has a *positive vibe* to boost my energy and put me in a good mood",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Positive, uplifting, energetic hip-hop."
    },
    "entities": [
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Lupe Fiasco"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "positive, uplifting, energetic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip-hop"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "these last few suggestions not working",
        "facet": null,
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "artist",
        "value": "Lupe Fiasco"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "my favorite artist but those tracks are not positive",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "contrast",
        "source_turn": 3,
        "type": "artist",
        "value": "Lupe Fiasco"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "positive vibe, boost my energy, put me in a good mood",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "positive, uplifting, energetic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "hip-hop",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "hip-hop"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "soft",
        "value": "Lupe Fiasco"
      }
    ],
    "temporal_constraint": null
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
      "evidence_text": "But really, no Soundgarden at all? Like, not even 'Rusty Cage'?",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "Check if Soundgarden is available; if not, recommend Stone Temple Pilots or Nirvana."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Soundgarden"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Rusty Cage"
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
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": null,
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 1,
        "type": "artist",
        "value": "Alice In Chains"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": null,
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 1,
        "type": "track",
        "value": "Man in the Box"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": null,
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 2,
        "type": "artist",
        "value": "Pearl Jam"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": null,
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 2,
        "type": "track",
        "value": "Black"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "really, no Soundgarden at all?",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Soundgarden"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "not even 'Rusty Cage'?",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "track",
        "value": "Rusty Cage"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "how about something by Stone Temple Pilots",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Stone Temple Pilots"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "or Nirvana",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Nirvana"
      }
    ],
    "rejections": [],
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
      "evidence_text": "explore her earlier work",
      "request_type": "same_artist",
      "source_turn": 2,
      "summary": "Explore Natalia Lafourcade's earlier work from her first album 'Natalia Lafourcade'."
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
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "Natalia Lafourcade"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "first album",
        "facet": null,
        "mentioned_current_turn": true,
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
      "evidence_text": "songs from Hamilton that really showcase Eliza's character development or her relationship",
      "request_type": "exact_album",
      "source_turn": 3,
      "summary": "Songs from Hamilton that showcase Eliza's character development or her relationship with Alexander."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Lin-Manuel Miranda"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Hamilton: An American Musical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "character development of Eliza"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Eliza relationship with Alexander"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "Hamilton (the musical)",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Lin-Manuel Miranda"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "songs from Hamilton",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "album",
        "value": "Hamilton: An American Musical"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "Eliza's character development",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "character development of Eliza"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "her relationship with Alexander",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "Eliza relationship with Alexander"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "brilliant choice",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "artist",
        "value": "Lin-Manuel Miranda"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `692611f0-d9ef-406c-8327-902575197aee::t8`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `attribute_from_prior`
- Missing facts: `Kendrick, watching a movie`

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
  "expected": {
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "satisfied",
          "history"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kendrick"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "vivid storytelling"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "watching a movie"
      }
    ]
  },
  "observed": {
    "current_request": {
      "evidence_text": "vivid storytelling that almost feel like watching a movie, where the details are super clear",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Tracks with vivid, movie-like storytelling where the details are super clear and every line feels cinematic."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "vivid storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "movie-like"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dense narrative"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Kevin Gates always speaks his truth",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 1,
        "type": "artist",
        "value": "Kevin Gates"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Is There Any Love",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 2,
        "type": "artist",
        "value": "Kid Cudi"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "DNA. is a banger",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "history",
        "source_turn": 3,
        "type": "artist",
        "value": "Kendrick Lamar"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "vivid storytelling that almost feel like watching a movie, where the details are super clear",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "vivid storytelling, movie-like, clear details"
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
- Missing facts: `lyrical storytelling`

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
      "evidence_text": "more hip-hop tracks that are super strong on the lyrical storytelling",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "More hip-hop tracks by Mac Miller or similar artists with super strong lyrical storytelling about relationships and connection, keeping that deep introspective vibe."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Mac Miller"
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
        "value": "storytelling about relationships and connection"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "deep introspective"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "Mac Miller",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Mac Miller"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "hip-hop",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "hip-hop"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "lyrical storytelling about relationships",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "storytelling about relationships and connection"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "deep, introspective storytelling",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "deep introspective"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `c96d7bb9-65d4-44be-9bc2-891e8e485f4e::t7`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `attribute_new_artist`
- Missing facts: `deep longing`

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
  "expected": {
    "request_type": "new_artist",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "deep longing"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "emotional storytelling"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "sertanejo"
      }
    ]
  },
  "observed": {
    "current_request": {
      "evidence_text": "other artists but with a similar powerful, emotional sertanejo storytelling",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Songs by other artists with similar powerful, emotional Sertanejo storytelling."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Marília Mendonça"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "sertanejo"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "emotional storytelling"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "other artists",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Marília Mendonça"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "sertanejo storytelling",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "sertanejo"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "powerful",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "powerful"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "emotional sertanejo storytelling",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "emotional storytelling"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "deep emotional storytelling and heartbreak",
        "facet": "lyrical_theme",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "heartbreak and deep longing"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `a8df96e2-c196-462c-9484-72aa093aedf4::t1`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Fact class: `hidden_target_attribute`
- Missing facts: `male artist`

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
  "expected": {
    "request_type": "hidden_target",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Christian"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "encouraging message"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "male artist"
      }
    ]
  },
  "observed": {
    "current_request": {
      "evidence_text": "trying to remember a Christian song",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "A Christian song with an encouraging message, possibly by a male artist."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Christian"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "encouraging"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "male"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "Christian song",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "Christian"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "encouraging message",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "encouraging message"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "encouraging message",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "encouraging"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `5a0dfe9d-ec8a-4449-97df-35535cbf162f::t1`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Fact class: `attribute_search`
- Missing facts: `movie soundtrack`

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
        "value": "epic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "orchestral"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "movie soundtrack"
      }
    ]
  },
  "observed": {
    "current_request": {
      "evidence_text": "epic and orchestral, like a movie soundtrack, for background music",
      "request_type": "attribute_search",
      "source_turn": 1,
      "summary": "Epic, orchestral, cinematic background music like a movie soundtrack."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "epic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "orchestral"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "cinematic"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "epic",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "epic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "orchestral",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "orchestral"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "like a movie soundtrack",
        "facet": "visual",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "cinematic"
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
- Missing facts: `Baker Street, Reelin' In The Years, Reelin' In The Years role in ['current_target', 'positive_anchor', 'seed'], Reelin' In The Years, Reelin' In The Years use_as_retrieval_seed=True`

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
      "evidence_text": "tracks where the guitar is the star, specifically with intricate or smooth solos like the one in Reelin' In The Years",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "70s rock songs with intricate or smooth guitar solos like Reelin' In The Years by Steely Dan."
    },
    "entities": [
      {
        "role": "contrast",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Reelin' In The Years"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Steely Dan"
      },
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Gerry Rafferty"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "guitar solo intricate smooth"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "1970s"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "like the one in Reelin' In The Years",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "contrast",
        "source_turn": 3,
        "type": "track",
        "value": "Reelin' In The Years"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "other ideas",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "artist",
        "value": "Steely Dan"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Baker Street is a classic",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Gerry Rafferty"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "guitar solos like the one in Reelin' In The Years",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "guitar solo intricate smooth"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "70s rock songs",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "rock"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "70s rock",
        "facet": "era",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "1970s"
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

### `2db3ddc8-78a1-412c-a71e-e0d748aab0e7::t2`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Fact class: `artist_similarity`
- Missing facts: `Night Moves`

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
      "evidence_text": "artists with that same distinctive 70s rock sound and lyrical depth, perhaps from someone like John Fogerty or Bruce Spr",
      "request_type": "similar_to_prior",
      "source_turn": 2,
      "summary": "More tracks from artists with a classic 70s rock sound and lyrical depth, like John Fogerty or Bruce Springsteen."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Bob Seger"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "John Fogerty"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Bruce Springsteen"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "70s rock sound"
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
        "evidence_text": "Night Moves is exactly what I had in mind",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "artist",
        "value": "Bob Seger"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "from someone like John Fogerty",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "John Fogerty"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "or Bruce Springsteen",
        "facet": null,
        "mentioned_current_turn": true,
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
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "70s rock sound"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "lyrical depth",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 2,
        "type": "attribute",
        "value": "lyrical depth"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `66ff896f-fcbc-4c42-9d69-b0b5b5ae5a56::t3`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Fact class: `attribute_temporal`
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
        "value": "classic rock"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "arena-rock"
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
      "evidence_text": "another classic rock song from the late 70s or early 80s",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Another classic rock song from the late 70s or early 80s with a powerful, arena-rock feel, avoiding Bruce Springsteen."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Bruce Springsteen"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful arena-rock feel"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic rock"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "could you suggest another classic rock song",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Bruce Springsteen"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "powerful, arena-rock feel",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "powerful arena-rock feel"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "classic rock song",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "classic rock"
      }
    ],
    "rejections": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1977,
        1984
      ],
      "strength": "soft"
    }
  }
}
```

### `c4c0c288-dbcd-4970-ad52-901aafe91b88::t1`

- Pack: `P0_good_state_ranker_near_miss_failure`
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
      "evidence_text": "like A Tribe Called Quest",
      "request_type": "similar_to_prior",
      "source_turn": 1,
      "summary": "Classic jazz-infused hip-hop from the early 90s popular with underground fans, similar to A Tribe Called Quest."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
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
        "value": "early 90s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "like A Tribe Called Quest",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "artist",
        "value": "A Tribe Called Quest"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "jazz-infused hip-hop",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "jazz-infused hip-hop"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "early 90s",
        "facet": "era",
        "mentioned_current_turn": true,
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
        1995
      ],
      "strength": "soft"
    }
  }
}
```

### `a9b423bf-d05c-418d-98af-2a3b1e1d7917::t1`

- Pack: `POS_clean_final_hit_control`
- Fact class: `lyric_hidden_target`
- Missing facts: `request_type, temporal: temporal_constraint`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
    "required_entities": true,
    "required_exclusions": true,
    "schema_valid": true,
    "temporal_constraint": false
  },
  "expected": {
    "request_type": "hidden_target",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Ice Cube"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Just wakin' up in the morning"
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
      "evidence_text": "starts with 'Just wakin' up in the morning, gotta thank God'",
      "request_type": "exact_track",
      "source_turn": 1,
      "summary": "Play Ice Cube's 90s song starting with 'Just wakin' up in the morning, gotta thank God'."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Ice Cube"
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
        "value": "Just wakin' up in the morning, gotta thank God"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "Ice Cube",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "artist",
        "value": "Ice Cube"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "90s",
        "facet": "era",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "90s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "starts with 'Just wakin' up in the morning, gotta thank God'",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "Just wakin' up in the morning, gotta thank God"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `5080d5a0-336e-4bd1-b5bc-4cc611983429::t1`

- Pack: `POS_clean_final_hit_control`
- Fact class: `exact_entity`
- Missing facts: `temporal: temporal_constraint`

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
  "expected": {
    "request_type": "exact_track",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Rock with You"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Michael Jackson"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Off the Wall"
      }
    ],
    "temporal_constraint": {
      "apply_as_filter": [
        true,
        false
      ],
      "kind": [
        "release_date",
        "style_era"
      ],
      "strength": [
        "hard",
        "soft"
      ]
    }
  },
  "observed": {
    "current_request": {
      "evidence_text": "Play Michael Jackson's 'Rock with You' from his 1979 album 'Off the Wall'",
      "request_type": "exact_track",
      "source_turn": 1,
      "summary": "Play Michael Jackson's Rock with You from Off the Wall."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Michael Jackson"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Rock with You"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Off the Wall"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "Michael Jackson",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "artist",
        "value": "Michael Jackson"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "Rock with You",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "track",
        "value": "Rock with You"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "Off the Wall",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "album",
        "value": "Off the Wall"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

