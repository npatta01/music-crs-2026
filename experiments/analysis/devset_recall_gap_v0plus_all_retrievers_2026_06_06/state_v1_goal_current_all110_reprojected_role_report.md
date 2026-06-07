# State Role Label Evaluation

- Labels: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_role_labels_v2.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_goal_current_all110_reprojected_audit.jsonl`
- Samples: `56`
- All-pass: `0.929`

## Checks

| Check | Rate |
|---|---:|
| schema_valid | `1.000` |
| request_type | `0.982` |
| exact_seeds | `1.000` |
| style_references | `1.000` |
| query_facets | `1.000` |
| context_entities | `0.964` |
| exclusions | `0.982` |
| forbidden_exact_seeds | `1.000` |
| temporal_constraint | `1.000` |

## Failures

### `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Fact class: `attribute_from_prior`
- Missing: `request_type: new_artist not in ['attribute_search', 'similar_to_prior']`

```json
{
  "checks": {
    "context_entities": true,
    "exact_seeds": true,
    "exclusions": true,
    "forbidden_exact_seeds": true,
    "query_facets": true,
    "request_type": false,
    "schema_valid": true,
    "style_references": true,
    "temporal_constraint": true
  },
  "expected": {
    "allowed_request_types": [
      "attribute_search",
      "similar_to_prior"
    ],
    "forbidden_exact_seeds": [
      {
        "type": "artist",
        "value": "Mr. Bungle"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Mr. Bungle"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "experimental"
      },
      {
        "type": "tag",
        "value": "genre-bending"
      }
    ],
    "required_style_references": []
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
- Missing: `context_entity: Michael Jackson`

```json
{
  "checks": {
    "context_entities": false,
    "exact_seeds": true,
    "exclusions": true,
    "forbidden_exact_seeds": true,
    "query_facets": true,
    "request_type": true,
    "schema_valid": true,
    "style_references": true,
    "temporal_constraint": true
  },
  "expected": {
    "allowed_request_types": [
      "new_artist",
      "attribute_search",
      "similar_to_prior"
    ],
    "forbidden_exact_seeds": [
      {
        "type": "artist",
        "value": "Michael Jackson"
      },
      {
        "value": "Michael Jackson"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Michael Jackson"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "well-known"
      },
      {
        "type": "tag",
        "value": "popular"
      }
    ],
    "required_style_references": []
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
- Missing: `context_entity: Flying Lotus`

```json
{
  "checks": {
    "context_entities": false,
    "exact_seeds": true,
    "exclusions": true,
    "forbidden_exact_seeds": true,
    "query_facets": true,
    "request_type": true,
    "schema_valid": true,
    "style_references": true,
    "temporal_constraint": true
  },
  "expected": {
    "allowed_request_types": [
      "attribute_search",
      "similar_to_prior"
    ],
    "forbidden_exact_seeds": [
      {
        "type": "artist",
        "value": "Flying Lotus"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Flying Lotus"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "electronic"
      },
      {
        "type": "tag",
        "value": "soulful"
      },
      {
        "type": "tag",
        "value": "out there"
      }
    ],
    "required_style_references": []
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

### `1e14a07f-7369-4d24-9285-9343b6b18353::t8`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `style_rejection`
- Missing: `exclusion: metal`

```json
{
  "checks": {
    "context_entities": true,
    "exact_seeds": true,
    "exclusions": false,
    "forbidden_exact_seeds": true,
    "query_facets": true,
    "request_type": true,
    "schema_valid": true,
    "style_references": true,
    "temporal_constraint": true
  },
  "expected": {
    "allowed_request_types": [
      "attribute_search",
      "similar_to_prior"
    ],
    "forbidden_exact_seeds": [
      {
        "value": "Gladiatrix"
      }
    ],
    "required_context_entities": [],
    "required_exact_seeds": [],
    "required_exclusions": [
      {
        "scope": "hard",
        "type": "style",
        "value": "metal"
      }
    ],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "atmospheric"
      },
      {
        "type": "tag",
        "value": "haunting"
      },
      {
        "type": "tag",
        "value": "ethereal vocals"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "candidate_types": [],
      "evidence_text": "something much more atmospheric and haunting, with ethereal vocals and traditional instruments, not so much the metal side",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Atmospheric and haunting dark/gothic folk or ambient folk with ethereal vocals and traditional instruments, avoiding heavy/intense metal qualities."
    },
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

