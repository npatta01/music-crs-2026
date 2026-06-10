# State Fact Label Evaluation

- Labels: `/tmp/state_fact_remaining_core_labels.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_fact_v1_paid_current_literal_remaining_core_audit.jsonl`
- Samples: `12`
- All-pass: `0.083`

## Fact Classes

| Fact class | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| album_rejection_visual | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| attribute_from_prior | 3 | 0.000 | 0.000 | 0.667 | 0.000 | 1.000 | 1.000 | 1.000 |
| attribute_new_artist | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| exact_artist_alternatives | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| hidden_target_temporal | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| negative_feedback_attribute | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| negative_feedback_temporal | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 |
| new_artist_from_prior | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| same_artist_or_attribute | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| style_rejection | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |

## Packs

| Pack | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_named_artist_ranker_failure | 2 | 0.000 | 0.000 | 0.500 | 0.000 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 4 | 0.000 | 0.000 | 0.500 | 0.000 | 1.000 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 3 | 0.000 | 0.000 | 1.000 | 0.333 | 1.000 | 0.333 | 1.000 |
| P1_temporal_constraint_failure | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 |

## Failures

### `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `attribute_from_prior`
- Missing facts: `electronic, electronic role in ['current_target', 'seed'], electronic, electronic use_as_retrieval_seed=True, soulful, soulful role in ['current_target', 'seed'], soulful, soulful use_as_retrieval_seed=True`

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
      "evidence_text": "really out there",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Something really out there, unique, and unexpected, continuing the discovery journey."
    },
    "entities": [
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
        "value": "out there"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Flying Lotus"
      },
      {
        "role": "satisfied",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "electronic but also soulful"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "very unique",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "unique"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "really out there",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "out there"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "electronic but also soulful",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "attribute",
        "value": "electronic but also soulful"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Flying Lotus! This is cool",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Flying Lotus"
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
- Missing facts: `exclusion: dark and harsh, temporal: kind`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": true,
    "required_entities": true,
    "required_exclusions": false,
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
      "evidence_text": "defining track from that specific bygone musical period",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "A defining instrumental ambient electronic track from 2007-2009 with a warm, ethereal, dreamy, serene, subtly rhythmic quality typical of late 2000s ambient electronic."
    },
    "entities": [
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Ochre"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Jon Hopkins"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "World's End Girlfriend"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Loscil"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Blackbelt Andersen"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Carl Sagan"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Sidewalks and Skeletons"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "late 2000s ambient electronic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "warm ethereal subtly rhythmic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "instrumental"
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
        "value": "dreamy serene"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ambient electronic"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "spoken word"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "dark harsh"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "too dark and harsh",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 8,
        "type": "attribute",
        "value": "dark harsh"
      },
      {
        "evidence_text": "spoken word element",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 7,
        "type": "attribute",
        "value": "spoken word"
      }
    ],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "distinct feel of the late 2000s (2007-2009)",
        "facet": "era",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "late 2000s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "warm, ethereal, and subtly rhythmic",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "warm ethereal subtly rhythmic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dreamy or serene",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "dreamy serene"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "late 2000s ambient electronic",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "ambient electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "instrumental",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "instrumental"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "good start",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 1,
        "type": "artist",
        "value": "Ochre"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "much closer",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 2,
        "type": "artist",
        "value": "Jon Hopkins"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too dramatic",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 3,
        "type": "artist",
        "value": "World's End Girlfriend"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "mood is good but era not right",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 4,
        "type": "artist",
        "value": "Loscil"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "era off",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 5,
        "type": "artist",
        "value": "Blackbelt Andersen"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not instrumental",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 6,
        "type": "artist",
        "value": "Carl Sagan"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too dark and harsh",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 7,
        "type": "artist",
        "value": "Sidewalks and Skeletons"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "spoken word element",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "rejected",
        "source_turn": 7,
        "type": "attribute",
        "value": "spoken word"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too dark and harsh",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 8,
        "type": "attribute",
        "value": "dark harsh"
      }
    ],
    "rejections": [
      {
        "kind": "style",
        "scope": "soft",
        "value": "dark harsh"
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "spoken word"
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
      "evidence_text": "more atmospheric and haunting, with ethereal vocals and traditional instruments, not so much the metal side",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "Atmospheric, haunting dark folk with ethereal vocals and traditional instruments, delicate and melancholic, not heavy or metal."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Myrkur"
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
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "delicate melancholic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark folk"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "heavy intense metal"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "too heavy and intense",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 8,
        "type": "attribute",
        "value": "heavy intense metal"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "I like that it's Myrkur",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 8,
        "type": "artist",
        "value": "Myrkur"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "atmospheric",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "atmospheric"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "haunting",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "haunting"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "ethereal vocals",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "ethereal vocals"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "traditional instruments",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "traditional instruments"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "delicate, melancholic",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "delicate melancholic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dark folk side",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "dark folk"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too heavy and intense",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 8,
        "type": "attribute",
        "value": "heavy intense metal"
      }
    ],
    "rejections": [
      {
        "kind": "style",
        "scope": "soft",
        "value": "heavy intense metal"
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
  "compiler_core_pass": false,
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
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Electronic albums from the 2010s with striking, artistically unique cover art, from different artists than Daft Punk or Four Tet."
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
        "role": "rejected",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "Random Access Memories"
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
        "role": "satisfied",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "New Energy"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "listened to Random Access Memories countless times",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 6,
        "type": "album",
        "value": "Random Access Memories"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "different artists",
        "facet": null,
        "mentioned_current_turn": true,
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
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Four Tet"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "listened to Random Access Memories countless times",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 6,
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "beyond New Energy",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "album",
        "value": "New Energy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "electronic albums",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "striking or artistically unique",
        "facet": "visual",
        "mentioned_current_turn": true,
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
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "memorable visual identity"
      }
    ],
    "rejections": [
      {
        "kind": "album",
        "scope": "hard",
        "value": "Random Access Memories"
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
- Missing facts: `boost my energy, exclusion: heavy and intense`

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
      "evidence_text": "suggest something genuinely upbeat, energetic, and feel-good",
      "request_type": "attribute_search",
      "source_turn": 5,
      "summary": "Genuinely upbeat, energetic, feel-good hip-hop to boost mood and energy."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Lupe Fiasco"
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
      }
    ],
    "exclusions": [
      {
        "evidence_text": "Streets On Fire is not a positive or uplifting track",
        "facet": "mood",
        "scope": "soft_preference",
        "source_turn": 5,
        "type": "attribute",
        "value": "heavy intense"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Lupe Fiasco",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 5,
        "type": "artist",
        "value": "Lupe Fiasco"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "positive vibe",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "positive vibe"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "upbeat",
        "facet": "energy",
        "mentioned_current_turn": true,
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
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "hip-hop"
      }
    ],
    "rejections": [
      {
        "kind": "style",
        "scope": "soft",
        "value": "heavy intense"
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
      "summary": "New nu-metal bands from the late 90s/early 2000s with heavy riffs and rap or industrial/electronic influences, besides Linkin Park and Pantera."
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
        "role": "satisfied_prior",
        "source_turn": 8,
        "type": "artist",
        "value": "Pantera"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "aggressive nu-metal sound",
        "facet": "genre",
        "mentioned_current_turn": false,
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
- Missing facts: `request_type, Rusty Cage`

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
      "evidence_text": "Soundgarden at all? ... Stone Temple Pilots or Nirvana?",
      "request_type": "new_artist",
      "source_turn": 6,
      "summary": "Soundgarden, Stone Temple Pilots, or Nirvana tracks."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Pearl Jam"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Alice In Chains"
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
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "grunge"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Pearl Jam is awesome",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Pearl Jam"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "I love Alice In Chains",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 4,
        "type": "artist",
        "value": "Alice In Chains"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "Soundgarden at all?",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Soundgarden"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "Stone Temple Pilots",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Stone Temple Pilots"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "Nirvana",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Nirvana"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "grunge band from the 90s",
        "facet": "genre",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "grunge"
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
- Missing facts: `watching a movie`

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
      "evidence_text": "tracks with really vivid storytelling that almost feel like watching a movie, where the details are super clear",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "Hip-hop tracks with vivid, cinematic storytelling where the details are super clear, almost like watching a movie."
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
        "value": "cinematic narrative"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "detailed narrative"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kendrick Lamar"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kevin Gates"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kid Cudi"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "vivid storytelling",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "vivid storytelling"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "almost feel like watching a movie",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "cinematic narrative"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "details are super clear",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "detailed narrative"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Kendrick really goes in",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 8,
        "type": "artist",
        "value": "Kendrick Lamar"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "other artists",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 6,
        "type": "artist",
        "value": "Kevin Gates"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Kid Cudi's vibe",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 7,
        "type": "artist",
        "value": "Kid Cudi"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `8071d14d-7e0f-4f72-90a6-0941db80a371::t5`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `attribute_from_prior`
- Missing facts: `request_type, Brent Faiyaz, Brent Faiyaz role in ['history', 'satisfied'], Brent Faiyaz, Brent Faiyaz use_as_retrieval_seed=False`

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
    "request_type": "attribute_search",
    "required_entities": [
      {
        "allowed_roles": [
          "satisfied",
          "history"
        ],
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Brent Faiyaz"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "groove"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "chill R&B"
      }
    ]
  },
  "observed": {
    "current_request": {
      "evidence_text": "similar to this, or maybe something with a bit more of a groove but still chill R&B",
      "request_type": "similar_to_prior",
      "source_turn": 5,
      "summary": "More tracks similar to the smooth, chill R&B/Soul vibe of Brent Faiyaz's 'Talk 2 U', possibly with a bit more groove."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Brent Faiyaz"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Talk 2 U"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "chill R&B"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "smooth"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "groove"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "I like Brent Faiyaz",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 5,
        "type": "artist",
        "value": "Brent Faiyaz"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "nice smooth vibe",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 5,
        "type": "track",
        "value": "Talk 2 U"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "chill R&B",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "chill R&B"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "smooth vibe",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "smooth"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "bit more of a groove",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "groove"
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
      "evidence_text": "more hip-hop tracks that are super strong on the lyrical storytelling, especially if they have that thoughtful, reflecti",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "More hip-hop tracks with strong lyrical storytelling and a thoughtful, reflective vibe, from any artists."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Masta Ace"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Phora"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
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
        "value": "lyrical storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "thoughtful reflective"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "other artists",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Masta Ace"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "other artists",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 4,
        "type": "artist",
        "value": "Phora"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not just Mac Miller this time",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Mac Miller"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "hip-hop tracks",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "hip-hop"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "lyrical storytelling",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "lyrical storytelling"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "thoughtful, reflective vibe",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "thoughtful reflective"
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
- Missing facts: `deep longing, emotional storytelling`

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
      "evidence_text": "other artists but with a similar powerful, emotional sertanejo vibe",
      "request_type": "new_artist",
      "source_turn": 7,
      "summary": "Other artists with a similar powerful, emotional sertanejo vibe."
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
        "value": "powerful emotional"
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
        "source_turn": 7,
        "type": "artist",
        "value": "Marília Mendonça"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "sertanejo vibe",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 7,
        "type": "attribute",
        "value": "sertanejo"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "powerful, emotional sertanejo vibe",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 7,
        "type": "attribute",
        "value": "powerful emotional"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

