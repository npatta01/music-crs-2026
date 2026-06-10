# State Role Label Evaluation

- Labels: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_role_labels_v2_failures6.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_role_v2_current_deepseek_promptfix_failures6_audit.jsonl`
- Samples: `6`
- All-pass: `0.667`

## Checks

| Check | Rate |
|---|---:|
| schema_valid | `1.000` |
| request_type | `1.000` |
| exact_seeds | `1.000` |
| style_references | `1.000` |
| query_facets | `0.667` |
| context_entities | `1.000` |
| exclusions | `1.000` |
| forbidden_exact_seeds | `1.000` |
| temporal_constraint | `0.833` |

## Failures

### `f2d85aa5-2086-4b1e-9974-d188c43621db::t8`

- Pack: `P1_temporal_constraint_failure`
- Fact class: `negative_feedback_temporal`
- Missing: `query_facet: serene, temporal: kind`

```json
{
  "checks": {
    "context_entities": true,
    "exact_seeds": true,
    "exclusions": true,
    "forbidden_exact_seeds": true,
    "query_facets": false,
    "request_type": true,
    "schema_valid": true,
    "style_references": true,
    "temporal_constraint": false
  },
  "expected": {
    "allowed_request_types": [
      "attribute_search",
      "similar_to_prior"
    ],
    "forbidden_exact_seeds": [],
    "required_context_entities": [],
    "required_exact_seeds": [],
    "required_exclusions": [
      {
        "scope": "hard",
        "type": "style",
        "value": "dark and harsh"
      }
    ],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "dreamy"
      },
      {
        "type": "tag",
        "value": "serene"
      },
      {
        "type": "tag",
        "value": "ambient electronic"
      }
    ],
    "required_style_references": [],
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
          "evidence_text": "I'm specifically looking for something with a warm, ethereal, and subtly rhythmic quality that truly embodies the late 2",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.6,
          "evidence_text": "We haven't quite found that yet",
          "request_type": "hidden_target"
        }
      ],
      "evidence_text": "I'm specifically looking for something with a warm, ethereal, and subtly rhythmic quality that truly embodies the late 2",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "A warm, ethereal, subtly rhythmic, strictly instrumental ambient electronic track that defines the late 2000s (2007-2009) period."
    },
    "exclusions": [
      {
        "evidence_text": "not dreamy or serene",
        "facet": "mood",
        "scope": "soft_preference",
        "source_turn": 8,
        "type": "attribute",
        "value": "dark harsh"
      }
    ],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "warm, ethereal, and subtly rhythmic quality",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "warm ethereal subtly rhythmic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "strictly instrumental",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "instrumental"
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
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "dreamy, atmospheric",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "dreamy atmospheric"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not dreamy or serene",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
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

### `71bb177a-dab1-4bbc-8508-22d809b05c31::t6`

- Pack: `P1_temporal_constraint_failure`
- Fact class: `new_artist_temporal`
- Missing: `query_facet: female artist`

```json
{
  "checks": {
    "context_entities": true,
    "exact_seeds": true,
    "exclusions": true,
    "forbidden_exact_seeds": true,
    "query_facets": false,
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
        "value": "Natalie Merchant"
      },
      {
        "value": "Natalie Merchant"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Natalie Merchant"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "female artist"
      },
      {
        "type": "tag",
        "value": "storytelling"
      }
    ],
    "required_style_references": [],
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
          "confidence": 0.9,
          "evidence_text": "another iconic female artist",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.5,
          "evidence_text": "similar thoughtful, storytelling approach",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "another iconic female artist from the 90s who has a similar thoughtful, storytelling approach",
      "request_type": "new_artist",
      "source_turn": 6,
      "summary": "Another iconic female artist from the 90s with a thoughtful, storytelling approach similar to Alanis Morissette and Natalie Merchant."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "YES! Alanis Morissette",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "may_reuse",
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
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Natalie Merchant"
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
        "value": "1990s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "thoughtful",
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
        "evidence_text": "storytelling approach",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "storytelling"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "introspective",
        "facet": "mood",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "introspective"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "raw style",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "raw"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "emotionally resonant",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "emotionally resonant"
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

