# State Role Label Evaluation

- Labels: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_role_labels_v2.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_role_v2_current_deepseek_fresh56_audit.jsonl`
- Samples: `56`
- All-pass: `0.857`

## Checks

| Check | Rate |
|---|---:|
| schema_valid | `1.000` |
| request_type | `1.000` |
| exact_seeds | `0.982` |
| style_references | `1.000` |
| query_facets | `0.929` |
| context_entities | `0.946` |
| exclusions | `1.000` |
| forbidden_exact_seeds | `1.000` |
| temporal_constraint | `0.982` |

## Failures

### `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `attribute_from_prior`
- Missing: `query_facet: electronic, query_facet: soulful`

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
          "confidence": 0.3,
          "evidence_text": "interesting mix of sounds",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "really out there",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Something really out there, unique, and unexpected, continuing the discovery journey."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "really out there",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "out there"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "very unique",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
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
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "unexpected"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Flying Lotus! This is cool",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Flying Lotus"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "love for Aphex Twin",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "history",
        "source_turn": 1,
        "type": "artist",
        "value": "Aphex Twin"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Boards of Canada is awesome",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "history",
        "source_turn": 2,
        "type": "artist",
        "value": "Boards of Canada"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "pretty wild",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "history",
        "source_turn": 3,
        "type": "artist",
        "value": "Severed Heads"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "totally what I was looking for",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "history",
        "source_turn": 4,
        "type": "artist",
        "value": "Liu Fang"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "cool change of pace",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "history",
        "source_turn": 5,
        "type": "artist",
        "value": "Noriko Miyamoto"
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
- Missing: `temporal: kind`

```json
{
  "checks": {
    "context_entities": true,
    "exact_seeds": true,
    "exclusions": true,
    "forbidden_exact_seeds": true,
    "query_facets": true,
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
          "evidence_text": "warm, ethereal, and subtly rhythmic quality",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "defining track from that specific bygone musical period",
          "request_type": "hidden_target"
        }
      ],
      "evidence_text": "warm, ethereal, and subtly rhythmic quality that truly embodies the distinct feel of the late 2000s (2007-2009)",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "A strictly instrumental, warm, ethereal, subtly rhythmic, dreamy, atmospheric, evolving electronic track from 2007-2009 that defines the late 2000s ambient electronic sound."
    },
    "exclusions": [
      {
        "evidence_text": "not what I'm looking for at all",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 8,
        "type": "track",
        "value": "Sleep Paralysis"
      },
      {
        "evidence_text": "spoken word element",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 7,
        "type": "track",
        "value": "A Glorious Dawn"
      },
      {
        "evidence_text": "too dramatic and intense",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 4,
        "type": "track",
        "value": "100 Years of Choke"
      },
      {
        "evidence_text": "era is off",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 6,
        "type": "track",
        "value": "Tyrkisk Pepper - Dolle Jolle Remix"
      },
      {
        "evidence_text": "too dark and harsh",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 8,
        "type": "attribute",
        "value": "dark and harsh"
      }
    ],
    "facts": [
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
        "evidence_text": "dreamy",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "dreamy"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "atmospheric",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "atmospheric"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "serene",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
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
        "relation": "query_facet",
        "reuse": "not_applicable",
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
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "warm"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "subtly rhythmic quality",
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
        "evidence_text": "evolving",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "evolving"
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
        "anchor_use": "do_not_use",
        "evidence_text": "too dark and harsh",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 8,
        "type": "attribute",
        "value": "dark and harsh"
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
        "type": "track",
        "value": "Sleep Paralysis"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "spoken word element makes it not quite what I'm looking for",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 7,
        "type": "track",
        "value": "A Glorious Dawn"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "too dramatic and intense",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 4,
        "type": "track",
        "value": "100 Years of Choke"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "era is off (2011)",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 6,
        "type": "track",
        "value": "Tyrkisk Pepper - Dolle Jolle Remix"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "good start but too minimal",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "history",
        "source_turn": 2,
        "type": "track",
        "value": "Napolese"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "much closer but not era-defining enough",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "history",
        "source_turn": 3,
        "type": "track",
        "value": "Circle"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "mood excellent but era not specific enough",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "history",
        "source_turn": 5,
        "type": "track",
        "value": "Anthropocene"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "Sleep Paralysis"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "A Glorious Dawn"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "100 Years of Choke"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "Tyrkisk Pepper - Dolle Jolle Remix"
      },
      {
        "kind": "style",
        "scope": "soft",
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
      "summary": "Another iconic female artist from the 90s with a thoughtful, storytelling approach similar to Natalie Merchant."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "introspective and raw style",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 5,
        "type": "artist",
        "value": "Alanis Morissette"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "great pick",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Natalie Merchant"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "introspective",
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
        "evidence_text": "emotionally resonant",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "emotionally resonant"
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

### `b2582e52-6d13-40b4-8552-2d8b63fa6c75::t8`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `hard_rejection`
- Missing: `context_entity: System Of A Down`

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
        "value": "System Of A Down"
      },
      {
        "value": "System Of A Down"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "rejected"
        ],
        "type": "artist",
        "value": "System Of A Down"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [
      {
        "scope": "hard",
        "type": "artist",
        "value": "System Of A Down"
      }
    ],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "heavy alternative metal"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "new bands with that heavy, alternative metal sound",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.3,
          "evidence_text": "similar in style to System Of A Down",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "new bands with that heavy, alternative metal sound",
      "request_type": "new_artist",
      "source_turn": 8,
      "summary": "New heavy alternative metal bands with powerful vocals and complex song structures, similar to System Of A Down but not them."
    },
    "exclusions": [
      {
        "evidence_text": "but not them",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 8,
        "type": "artist",
        "value": "System Of A Down"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "similar in style to System Of A Down, but not them",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "contrast",
        "source_turn": 8,
        "type": "artist",
        "value": "System Of A Down"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "heavy, alternative metal sound",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "heavy alternative metal"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "powerful vocals",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 7,
        "type": "attribute",
        "value": "powerful vocals"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "complex song structures",
        "facet": "sonic",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 7,
        "type": "attribute",
        "value": "complex song structures"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "political rock bands",
        "facet": "lyrical_theme",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "political"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "System Of A Down"
      }
    ],
    "temporal_constraint": null
  }
}
```

### `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `negative_feedback_attribute`
- Missing: `query_facet: boost my energy`

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
      "attribute_search",
      "similar_to_prior"
    ],
    "forbidden_exact_seeds": [
      {
        "type": "artist",
        "value": "Lupe Fiasco"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "contrast",
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Lupe Fiasco"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [
      {
        "scope": "hard",
        "type": "style",
        "value": "heavy and intense"
      }
    ],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "positive vibe"
      },
      {
        "type": "tag",
        "value": "boost my energy"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "positive vibe, energetic, feel-good, good mood",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "even if it's not Lupe",
          "request_type": "new_artist"
        }
      ],
      "evidence_text": "genuinely upbeat, energetic, and feel-good",
      "request_type": "attribute_search",
      "source_turn": 5,
      "summary": "Genuinely upbeat, energetic, feel-good hip-hop to boost mood and energy."
    },
    "exclusions": [
      {
        "evidence_text": "heavy and intense",
        "facet": "sonic",
        "scope": "soft_preference",
        "source_turn": 5,
        "type": "attribute",
        "value": "heavy and intense"
      },
      {
        "evidence_text": "not what I'm looking for right now",
        "facet": "mood",
        "scope": "soft_preference",
        "source_turn": 5,
        "type": "attribute",
        "value": "thoughtful"
      },
      {
        "evidence_text": "chill, reflective side",
        "facet": "mood",
        "scope": "soft_preference",
        "source_turn": 5,
        "type": "attribute",
        "value": "chill reflective"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "I love Lupe Fiasco, but these last few recommendations are missing that completely",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
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
        "relation": "query_facet",
        "reuse": "not_applicable",
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
        "evidence_text": "uplifting vibe",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "uplifting"
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
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not what I'm looking for right now",
        "facet": "mood",
        "mentioned_current_turn": false,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 5,
        "type": "attribute",
        "value": "thoughtful"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "chill, reflective side",
        "facet": "mood",
        "mentioned_current_turn": false,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 5,
        "type": "attribute",
        "value": "chill reflective"
      }
    ],
    "rejections": [
      {
        "kind": "style",
        "scope": "soft",
        "value": "heavy and intense"
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "thoughtful"
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "chill reflective"
      }
    ],
    "temporal_constraint": null
  }
}
```

### `1c567917-f931-4609-9695-a9c0f8e39f3d::t2`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Fact class: `genre_search`
- Missing: `query_facet: tecno brega, query_facet: funk carioca, context_entity: Anitta`

```json
{
  "checks": {
    "context_entities": false,
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
      "attribute_search",
      "similar_to_prior"
    ],
    "forbidden_exact_seeds": [
      {
        "type": "artist",
        "value": "Anitta"
      },
      {
        "value": "Anitta"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Anitta"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "tecno brega"
      },
      {
        "type": "tag",
        "value": "funk carioca"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "tecno brega or funk carioca scenes",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "What about something more recent",
          "request_type": "new_artist"
        }
      ],
      "evidence_text": "more recent and upbeat, specifically from the 'tecno brega' or 'funk carioca' scenes",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "Recent upbeat tracks from the tecno brega or funk carioca scenes."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "tecno brega",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "tecno brega"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "funk carioca",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "funk carioca"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "upbeat",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "upbeat"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "more recent",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 2,
        "type": "artist",
        "value": "recent"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Anitta is definitely on point for contemporary pop",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 2,
        "type": "artist",
        "value": "contemporary pop"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Brazilian dance and pop scenes",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "style_reference",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 1,
        "type": "artist",
        "value": "Brazilian dance"
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
- Missing: `context_entity: Baker Street`

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
        "type": "track",
        "value": "Baker Street"
      },
      {
        "value": "Baker Street"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "contrast",
          "history"
        ],
        "type": "track",
        "value": "Baker Street"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "guitar"
      }
    ],
    "required_style_references": [
      {
        "type": "track",
        "value": "Reelin' In The Years"
      }
    ]
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "guitar is the star, specifically with intricate or smooth solos",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "like the one in Reelin' In The Years",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "guitar is the star, specifically with intricate or smooth solos like the one in Reelin' In The Years",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "70s rock songs with intricate or smooth guitar solos like Reelin' In The Years, where the guitar is the star."
    },
    "exclusions": [
      {
        "evidence_text": "Baker Street is a classic, but I'm really looking for tracks where the guitar is the star",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 3,
        "type": "track",
        "value": "Baker Street"
      }
    ],
    "facts": [
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "like the one in Reelin' In The Years",
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
        "evidence_text": "like the one in Reelin' In The Years",
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
        "evidence_text": "Baker Street is a classic, but I'm really looking for tracks where the guitar is the star",
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
        "anchor_use": "query_facet",
        "evidence_text": "70s rock songs",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "rock"
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
        "value": "intricate guitar solo"
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
        "value": "smooth guitar solo"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "70s rock songs",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 3,
        "type": "attribute",
        "value": "1970s"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "Baker Street"
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

### `737a65cf-9c45-4b1d-910d-2f1f1ef5eab7::t8`

- Pack: `POS_clean_final_hit_control`
- Fact class: `same_artist_album`
- Missing: `exact_seed: Cracker Island`

```json
{
  "checks": {
    "context_entities": true,
    "exact_seeds": false,
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
      "same_artist",
      "exact_artist"
    ],
    "forbidden_exact_seeds": [],
    "required_context_entities": [],
    "required_exact_seeds": [
      {
        "type": "artist",
        "value": "Gorillaz"
      },
      {
        "type": "album",
        "value": "Cracker Island"
      }
    ],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "upbeat"
      },
      {
        "type": "tag",
        "value": "quirky electronic"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "Gorillaz track",
          "request_type": "same_artist"
        },
        {
          "confidence": 0.5,
          "evidence_text": "upbeat or quirky electronic feel",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "Gorillaz track with a more upbeat or quirky electronic feel, maybe instrumental-focused or from Cracker Island",
      "request_type": "same_artist",
      "source_turn": 8,
      "summary": "A Gorillaz track with a more upbeat or quirky electronic feel, maybe instrumental-focused or from Cracker Island."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "Gorillaz track",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 8,
        "type": "artist",
        "value": "Gorillaz"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "upbeat",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "upbeat"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "quirky electronic feel",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "quirky"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "instrumental-focused",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "instrumental-focused"
      },
      {
        "anchor_use": "partial_anchor",
        "evidence_text": "from Cracker Island",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "style_reference",
        "reuse": "may_reuse",
        "role": "current_target",
        "source_turn": 8,
        "type": "album",
        "value": "Cracker Island"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

