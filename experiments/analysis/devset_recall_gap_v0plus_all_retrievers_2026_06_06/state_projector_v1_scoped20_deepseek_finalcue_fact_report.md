# State Fact Label Evaluation

- Labels: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_projector_v1_scoped20_fact_labels.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_projector_v1_scoped20_deepseek_finalcue_audit.jsonl`
- Samples: `20`
- All-pass: `0.600`

## Fact Classes

| Fact class | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| album_rejection_visual | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_from_prior | 4 | 0.500 | 0.750 | 0.750 | 0.750 | 1.000 | 1.000 | 1.000 |
| attribute_new_artist | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_refinement | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| attribute_temporal | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_artist_alternatives | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_entity | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hard_rejection | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hidden_target_temporal | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| negative_feedback_attribute | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| negative_feedback_temporal | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| new_artist_from_prior | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| same_artist_or_attribute | 1 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| style_rejection | 1 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |

## Packs

| Pack | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_named_artist_ranker_failure | 2 | 0.500 | 1.000 | 0.500 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 1 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 4 | 0.500 | 1.000 | 0.500 | 1.000 | 1.000 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 3 | 0.000 | 0.333 | 0.667 | 0.667 | 1.000 | 0.333 | 1.000 |
| P1_temporal_constraint_failure | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |

## Failures

### `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `attribute_from_prior`
- Missing facts: `electronic, electronic role in ['current_target', 'seed'], electronic, electronic use_as_retrieval_seed=True, soulful, out there`

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
      "evidence_text": "What else have you got that's really out there?",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Really out-there, unique, unexpected, and experimental electronic/soulful tracks that feel like cool discoveries."
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
        "value": "experimental"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "track #1"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "track #2"
      },
      {
        "role": "satisfied",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "electronic"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "totally what I was looking for",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 1,
        "type": "track",
        "value": "track #1"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "cool change of pace",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "track",
        "value": "track #2"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "interesting mix of sounds",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Flying Lotus"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "really out there",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "unique"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "electronic but also soulful",
        "facet": "genre",
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "attribute",
        "value": "electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "really out there",
        "facet": "sonic",
        "mentioned_current_turn": true,
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
      "evidence_text": "still trying to find",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "A dreamy, serene, warm, evolving, atmospheric purely instrumental or electronic track specifically from the late 2000s, recalling a specific track from that era."
    },
    "entities": [
      {
        "role": "history",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "A Glorious Dawn"
      },
      {
        "role": "rejected",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Sleep Paralysis"
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
        "value": "warm evolving pads"
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
        "value": "instrumental electronic"
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
        "value": "subtle rhythms"
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
        "value": "warm"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "instrumental"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "dreamy atmospheric"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "too dark and harsh",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "attribute",
        "value": "dark and harsh"
      },
      {
        "evidence_text": "what I'm looking for at all",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "track",
        "value": "Sleep Paralysis"
      }
    ],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "dreamy or serene",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "dreamy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "serene",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "serene"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "warm, evolving pads",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "warm evolving pads"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "subtle rhythms",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "subtle rhythms"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "atmospheric",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "atmospheric"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "instrumental or purely electronic",
        "facet": "genre",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "instrumental electronic"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too dark and harsh",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "attribute",
        "value": "dark and harsh"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "warm",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "warm"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "instrumental",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "track",
        "value": "instrumental"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dreamy, serene",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "track",
        "value": "dreamy atmospheric"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "Sleep Paralysis"
      },
      {
        "kind": "style",
        "scope": "soft",
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
      "evidence_text": "atmospheric and haunting, with ethereal vocals and traditional instruments, not so much the metal side",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Atmospheric, haunting tracks with ethereal female vocals and traditional instruments, avoiding intense/heavy metal elements."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Gladiatrix"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "atmospheric haunting"
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
        "value": "heavy metal side"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "intense"
      }
    ],
    "exclusions": [
      {
        "evidence_text": "too heavy and intense",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "track",
        "value": "Gladiatrix"
      },
      {
        "evidence_text": "not so much the metal side",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "attribute",
        "value": "heavy metal side"
      },
      {
        "evidence_text": "too heavy and intense",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 3,
        "type": "attribute",
        "value": "intense"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too heavy and intense",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "track",
        "value": "Gladiatrix"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "atmospheric and haunting",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "atmospheric haunting"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "ethereal vocals",
        "facet": "sonic",
        "mentioned_current_turn": true,
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
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "traditional instruments"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not so much the metal side",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "attribute",
        "value": "heavy metal side"
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
        "kind": "track",
        "scope": "hard",
        "value": "Gladiatrix"
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "heavy metal side"
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "intense"
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
      "evidence_text": "new album discoveries",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "New album discoveries: electronic albums from the 2010s with striking, artistically unique cover art, beyond Daft Punk and Four Tet."
    },
    "entities": [
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
        "value": "Daft Punk"
      },
      {
        "role": "rejected",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "New Energy"
      },
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Four Tet"
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
        "value": "artistically unique"
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
        "evidence_text": "listened to Random Access Memories countless times",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "evidence_text": "beyond Daft Punk",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "evidence_text": "beyond New Energy",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 2,
        "type": "album",
        "value": "New Energy"
      },
      {
        "evidence_text": "beyond New Energy",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 2,
        "type": "artist",
        "value": "Four Tet"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "listened to Random Access Memories countless times",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "album",
        "value": "Random Access Memories"
      },
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
        "evidence_text": "beyond New Energy",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "rejected",
        "source_turn": 2,
        "type": "album",
        "value": "New Energy"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "beyond New Energy",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "rejected",
        "source_turn": 2,
        "type": "artist",
        "value": "Four Tet"
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
        "value": "striking cover art"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "artistically unique",
        "facet": "visual",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "artistically unique"
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
- Missing facts: `Lupe Fiasco, Lupe Fiasco role in ['contrast', 'history', 'satisfied'], positive vibe, boost my energy, exclusion: heavy and intense`

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
      "evidence_text": "hip-hop that has a positive vibe to boost my energy and put me in a good mood",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Hip-hop with a positive, uplifting, energetic vibe to boost mood; not reflective, heavy, or Lupe Fiasco."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Lupe Fiasco"
      },
      {
        "role": "rejected",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Streets On Fire"
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
        "value": "positive uplifting"
      },
      {
        "role": "rejected",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "The Coolest"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "energetic"
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
        "evidence_text": "you trying to stick with Lupe Fiasco",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "artist",
        "value": "Lupe Fiasco"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "you trying to stick with Lupe Fiasco",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "artist",
        "value": "Lupe Fiasco"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Streets On Fire is not positive or uplifting",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "rejected",
        "source_turn": 3,
        "type": "track",
        "value": "Streets On Fire"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not what I'm looking for right now",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "rejected",
        "source_turn": 2,
        "type": "track",
        "value": "The Coolest"
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
        "evidence_text": "positive vibe to boost my energy and put me in a good mood",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "positive uplifting"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "boost my energy",
        "facet": "energy",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "energetic"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "heavy and intense",
        "facet": "sonic",
        "mentioned_current_turn": true,
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
        "kind": "style",
        "scope": "soft",
        "value": "heavy and intense"
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
      "evidence_text": "not even Rusty Cage",
      "request_type": "exact_track",
      "source_turn": 3,
      "summary": "First try Soundgarden's \"Rusty Cage\" as a specific probe, then fall back to Stone Temple Pilots or Nirvana if not available."
    },
    "entities": [
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
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Alice In Chains"
      },
      {
        "role": "history",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Man in the Box"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Pearl Jam"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Black"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Once"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "not even Soundgarden at all",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Soundgarden"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "Rusty Cage",
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
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "one of my absolute favorites",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "track",
        "value": "Black"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Pearl Jam is awesome",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Pearl Jam"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Once is cool",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "track",
        "value": "Once"
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
      "source_turn": 3,
      "summary": "More tracks similar to Talk 2 U by Brent Faiyaz, or with a bit more groove but still chill R&B."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
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
        "value": "groove"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "R&B"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "chill"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Dennis Lloyd"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "chill R&B",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "R&B"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "chill R&B",
        "facet": "mood",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "chill"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "more of a groove",
        "facet": "energy",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "groove"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "I like Brent Faiyaz",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "artist",
        "value": "Brent Faiyaz"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "good one",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "satisfied_prior",
        "source_turn": 3,
        "type": "track",
        "value": "Talk 2 U"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "something similar to Dennis Lloyd",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "history",
        "source_turn": 2,
        "type": "artist",
        "value": "Dennis Lloyd"
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
      "evidence_text": "more hip-hop tracks that are super strong on the lyrical storytelling about relationships",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "More hip-hop tracks that are super strong on lyrical storytelling about relationships, by Mac Miller or similar artists."
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
        "value": "lyrical storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling about relationships"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "deep introspective storytelling"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "To the Moon"
      },
      {
        "role": "satisfied",
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
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Soulmate"
      }
    ],
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "good one",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 1,
        "type": "track",
        "value": "To the Moon"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "more hip-hop tracks",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 1,
        "type": "artist",
        "value": "Phora"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "exactly the kind",
        "facet": null,
        "mentioned_current_turn": false,
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "track",
        "value": "Planet God Damn"
      },
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "by Mac Miller or artists with a similar",
        "facet": null,
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "artist",
        "value": "Mac Miller"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "fantastic pick",
        "facet": null,
        "mentioned_current_turn": false,
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
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "hip-hop"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "lyrical storytelling",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
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
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "storytelling about relationships"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "deep, introspective storytelling",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "deep introspective storytelling"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

