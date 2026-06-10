# State Fact Label Evaluation

- Labels: `/tmp/state_fact_core_fail_labels.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_fact_v1_paid_rubric_full_corefail_audit.jsonl`
- Samples: `14`
- All-pass: `0.214`

## Fact Classes

| Fact class | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| album_rejection_visual | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| attribute_from_prior | 4 | 0.250 | 0.250 | 0.750 | 0.250 | 1.000 | 1.000 | 1.000 |
| attribute_new_artist | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_artist_alternatives | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hidden_target_temporal | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| lyric_hidden_target | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| negative_feedback_attribute | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| negative_feedback_temporal | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 |
| new_artist_from_prior | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| same_artist_or_attribute | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| style_rejection | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |

## Packs

| Pack | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_good_state_ranker_near_miss_failure | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_named_artist_ranker_failure | 2 | 0.000 | 0.500 | 0.500 | 0.500 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 4 | 0.250 | 0.250 | 0.500 | 0.250 | 1.000 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 3 | 0.000 | 0.000 | 1.000 | 0.333 | 1.000 | 0.333 | 1.000 |
| P1_temporal_constraint_failure | 1 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 |
| POS_clean_final_hit_control | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Failures

### `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `attribute_from_prior`
- Missing facts: `Flying Lotus, electronic, soulful, out there`

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
        "value": "unexpected"
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
        "anchor_use": "query_facet",
        "evidence_text": "really out there",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "unique"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "unexpected discoveries",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "unexpected"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "interesting mix of sounds",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "experimental"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "What else",
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
- Missing facts: `request_type, exclusion: dark and harsh, temporal: kind`

```json
{
  "checks": {
    "forbidden_seeds": true,
    "request_type": false,
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
      "evidence_text": "I'm specifically looking for something with a warm, ethereal, and subtly rhythmic quality that truly embodies the feel",
      "request_type": "hidden_target",
      "source_turn": 8,
      "summary": "A defining instrumental ambient electronic track from 2007-2009 with a warm, ethereal, subtly rhythmic, dreamy, serene, and floating quality."
    },
    "entities": [
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
        "value": "dreamy"
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
        "value": "ethereal"
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
        "value": "subtly rhythmic"
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
        "value": "floating"
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
        "value": "dark harsh"
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
        "value": "dramatic intense"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "minimal"
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
      },
      {
        "evidence_text": "too dramatic and intense",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 4,
        "type": "attribute",
        "value": "dramatic intense"
      },
      {
        "evidence_text": "less minimal",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 2,
        "type": "attribute",
        "value": "minimal"
      }
    ],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "ambient electronic",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "ambient electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dreamy",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "dreamy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "serene",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "serene"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "ethereal",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "ethereal"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "warm",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "warm"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "subtly rhythmic",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "subtly rhythmic"
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
        "anchor_use": "query_facet",
        "evidence_text": "floating",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "floating"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "evolving",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "evolving"
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
        "evidence_text": "too dramatic and intense",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "rejected",
        "source_turn": 4,
        "type": "attribute",
        "value": "dramatic intense"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "less minimal",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "role": "rejected",
        "source_turn": 2,
        "type": "attribute",
        "value": "minimal"
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
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "dramatic intense"
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "minimal"
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
      "evidence_text": "more on the delicate, melancholic, and ethereal dark folk side",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "Delicate, melancholic, ethereal dark folk with atmospheric and haunting qualities, ethereal vocals, and traditional instruments; less heavy and intense, less metal."
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
        "value": "dark folk"
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
        "value": "delicate melancholic ethereal"
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
        "evidence_text": "strong female vocals like Myrkur",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 8,
        "type": "artist",
        "value": "Myrkur"
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
        "anchor_use": "query_facet",
        "evidence_text": "atmospheric",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "atmospheric"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "haunting",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "haunting"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "delicate, melancholic, and ethereal",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "delicate melancholic ethereal"
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
      "summary": "Electronic albums from the 2010s with striking, abstract, or artistically unique cover art, from different artists than Daft Punk or Four Tet."
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
        "value": "abstract cover art"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "memorable visual identity"
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
        "evidence_text": "different artists",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 6,
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
        "role": "rejected",
        "source_turn": 6,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "different artists",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "rejected",
        "source_turn": 6,
        "type": "artist",
        "value": "Four Tet"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "I've listened to 'Random Access Memories' countless times",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 6,
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "different artists",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "rejected",
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
        "evidence_text": "covers that are just as striking or artistically unique",
        "facet": "visual",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "striking cover art"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "abstract or have a strong, memorable artistic direction",
        "facet": "visual",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "abstract cover art"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "truly memorable visual identity on the album art",
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
      "evidence_text": "genuinely upbeat, energetic, and feel-good",
      "request_type": "attribute_search",
      "source_turn": 5,
      "summary": "Genuinely upbeat, energetic, feel-good hip-hop with a positive vibe to boost mood."
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
        "evidence_text": "not a positive or uplifting track",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 5,
        "type": "artist",
        "value": "Lupe Fiasco"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not a positive or uplifting track",
        "facet": null,
        "mentioned_current_turn": false,
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
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "positive"
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
        "kind": "artist",
        "scope": "hard",
        "value": "Lupe Fiasco"
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
      }
    ],
    "exclusions": [],
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
        "evidence_text": "besides ... Pantera",
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
        "mentioned_current_turn": true,
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
    "rejections": [],
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
      "evidence_text": "Soundgarden at all? Like, not even 'Rusty Cage'? If not, how about something by Stone Temple Pilots or Nirvana?",
      "request_type": "new_artist",
      "source_turn": 6,
      "summary": "Soundgarden, Stone Temple Pilots, or Nirvana tracks; if Soundgarden is unavailable, try Stone Temple Pilots or Nirvana."
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
        "value": "Rusty Cage"
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
        "anchor_use": "must_use",
        "evidence_text": "Soundgarden at all? Like, not even 'Rusty Cage'?",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Soundgarden"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "how about something by Stone Temple Pilots",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Stone Temple Pilots"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "or Nirvana",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "artist",
        "value": "Nirvana"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "not even 'Rusty Cage'?",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 6,
        "type": "track",
        "value": "Rusty Cage"
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
      "summary": "Hip-hop tracks with vivid, cinematic storytelling where the details are super clear, like watching a movie."
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
        "value": "dense detailed narrative"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Kendrick really goes in",
        "facet": null,
        "mentioned_current_turn": false,
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
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Kevin Gates"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Kid Cudi's vibe is different",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 7,
        "type": "artist",
        "value": "Kid Cudi"
      },
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
        "evidence_text": "feel like watching a movie",
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
        "value": "dense detailed narrative"
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
      "summary": "More tracks similar to Brent Faiyaz's smooth R&B vibe, or with a bit more groove but still chill R&B."
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
        "value": "R&B"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "chill"
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
        "value": "R&B"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "chill R&B",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "chill"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "smooth vibe",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "smooth"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "bit more of a groove",
        "facet": "mood",
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
      "evidence_text": "more hip-hop tracks that are super strong on the lyrical storytelling, especially if they have that thoughtful, reflect",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Hip-hop tracks with strong lyrical storytelling and a thoughtful, reflective vibe, from any artist."
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
        "value": "lyrical storytelling"
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
        "value": "hip-hop"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Masta Ace definitely brought the storytelling",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "artist",
        "value": "Masta Ace"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Phora is a good one too",
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
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `2bbc0a7e-3ab0-4376-8135-182cd4ae075f::t1`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Fact class: `hidden_target_temporal`
- Missing facts: `hit`

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
    "request_type": "hidden_target",
    "required_entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Latin Pop"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hit"
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
      "evidence_text": "trying to remember a Latin Pop song from around the early 2000s",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "A Latin Pop hit from the early 2000s the user is trying to recall."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Latin Pop"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "Latin Pop song",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "Latin Pop"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "around the early 2000s",
        "facet": "era",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "early 2000s"
      }
    ],
    "rejections": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2005
      ],
      "strength": "soft"
    }
  }
}
```

