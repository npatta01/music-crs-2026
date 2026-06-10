# State Role Label Evaluation

- Labels: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_role_labels_v2.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_role_v2_current_gpt41_full56_audit.jsonl`
- Samples: `56`
- All-pass: `0.857`

## Checks

| Check | Rate |
|---|---:|
| schema_valid | `0.982` |
| request_type | `0.964` |
| exact_seeds | `0.982` |
| style_references | `1.000` |
| query_facets | `0.964` |
| context_entities | `0.893` |
| exclusions | `1.000` |
| forbidden_exact_seeds | `1.000` |
| temporal_constraint | `1.000` |

## Failures

### `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8`

- Pack: `P0_roleless_stale_entity_failure`
- Fact class: `attribute_from_prior`
- Missing: `context_entity: Guano Apes`

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
        "value": "Guano Apes"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Guano Apes"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "powerful rock"
      },
      {
        "type": "tag",
        "value": "strong guitar riff"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "powerful rock songs, strong guitar riff",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "Do you have any other powerful rock songs",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "other powerful rock songs, maybe with a really strong guitar riff?",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "Other powerful rock songs, maybe with a really strong guitar riff."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "rock songs",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "rock"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "powerful",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "powerful"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "really strong guitar riff",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "strong guitar riff"
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
          "evidence_text": "positive energy, regardless of genre",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "other well-known songs",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "well-known songs that are popular and have a great, positive energy, regardless of genre, as long as they're not too n n",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Other well-known, popular songs with great, positive energy that are not too niche, regardless of genre."
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
        "evidence_text": "great, positive energy",
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
        "facet": "popularity",
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
          "evidence_text": "really out there, unique, electronic but also soulful",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "What else have you got",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "What else have you got that's really out there?",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Something really out there, unique, electronic but also soulful, continuing the unexpected discovery journey."
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
        "value": "really out there"
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
        "evidence_text": "it's like electronic",
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
        "evidence_text": "also soulful",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "soulful"
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
- Missing: `request_type: None not in ['similar_to_prior', 'attribute_search'], query_facet: 90s dance hits, context_entity: Finally, context_entity: CeCe Peniston`

```json
{
  "checks": {
    "context_entities": false,
    "exact_seeds": true,
    "exclusions": true,
    "forbidden_exact_seeds": true,
    "query_facets": false,
    "request_type": false,
    "schema_valid": false,
    "style_references": true,
    "temporal_constraint": true
  },
  "expected": {
    "allowed_request_types": [
      "similar_to_prior",
      "attribute_search"
    ],
    "forbidden_exact_seeds": [
      {
        "type": "track",
        "value": "Finally"
      },
      {
        "type": "artist",
        "value": "CeCe Peniston"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "track",
        "value": "Finally"
      },
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "CeCe Peniston"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "90s dance hits"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": null,
    "exclusions": [],
    "facts": [],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `d265b5a9-af57-4070-90f5-692a960c5aaa::t6`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `album_rejection_visual`
- Missing: `context_entity: Random Access Memories`

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
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "value": "Random Access Memories"
      },
      {
        "value": "Daft Punk"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "rejected",
          "satisfied_prior"
        ],
        "type": "album",
        "value": "Random Access Memories"
      },
      {
        "allowed_roles": [
          "history",
          "rejected",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Daft Punk"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "striking"
      },
      {
        "type": "tag",
        "value": "artistically unique"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "electronic albums from the 2010s with covers that are just as striking or artistically unique",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.7,
          "evidence_text": "from different artists",
          "request_type": "new_artist"
        }
      ],
      "evidence_text": "new album discoveries from the 2010s, specifically electronic albums with covers that are just as striking or artistcail",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Electronic albums from the 2010s by different artists with striking or artistically unique cover art, not Daft Punk or Four Tet."
    },
    "exclusions": [
      {
        "evidence_text": "I've listened to 'Random Access Memories' countless times",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 6,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "evidence_text": "beyond 'Random Access Memories' and 'New Energy'",
        "facet": null,
        "scope": "next_turn_hard",
        "source_turn": 6,
        "type": "artist",
        "value": "Four Tet"
      }
    ],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "I've listened to 'Random Access Memories' countless times",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 6,
        "type": "artist",
        "value": "Daft Punk"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "beyond 'Random Access Memories' and 'New Energy'",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exclude",
        "reuse": "must_exclude",
        "role": "rejected",
        "source_turn": 6,
        "type": "artist",
        "value": "Four Tet"
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
        "evidence_text": "covers that are just as striking",
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
        "evidence_text": "artistically unique",
        "facet": "visual",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "artistically unique"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "particularly abstract",
        "facet": "visual",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "abstract"
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

### `692611f0-d9ef-406c-8327-902575197aee::t8`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `attribute_from_prior`
- Missing: `context_entity: Kendrick`

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
        "value": "Kendrick"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Kendrick"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "vivid storytelling"
      },
      {
        "type": "tag",
        "value": "watching a movie"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "vivid storytelling, watching a movie",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "like DNA., Is There Any Love",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "tracks with really vivid storytelling that almost feel like watching a movie, where the details are super clear?",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "Hip-hop tracks with really vivid storytelling, almost like watching a movie, with super clear details."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "really vivid storytelling",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
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
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "watching a movie"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "where the details are super clear",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "super clear details"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
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
          "evidence_text": "upbeat or quirky electronic feel, more instrumental-focused",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "more upbeat or quirky electronic feel, maybe something that's more instrumental-focused or from one of their newer album",
      "request_type": "same_artist",
      "source_turn": 8,
      "summary": "A Gorillaz track with a more upbeat or quirky electronic feel, possibly more instrumental-focused or from a newer album like 'Cracker Island'."
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
        "evidence_text": "electronic feel",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "electronic"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "more upbeat",
        "facet": "energy",
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
        "facet": "sonic",
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
        "evidence_text": "more instrumental-focused",
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
        "anchor_use": "query_facet",
        "evidence_text": "newer albums like 'Cracker Island'",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "newer albums"
      }
    ],
    "rejections": [],
    "temporal_constraint": null
  }
}
```

### `a9b423bf-d05c-418d-98af-2a3b1e1d7917::t1`

- Pack: `POS_clean_final_hit_control`
- Fact class: `lyric_hidden_target`
- Missing: `request_type: exact_track not in ['hidden_target'], query_facet: Just wakin' up in the morning`

```json
{
  "checks": {
    "context_entities": true,
    "exact_seeds": true,
    "exclusions": true,
    "forbidden_exact_seeds": true,
    "query_facets": false,
    "request_type": false,
    "schema_valid": true,
    "style_references": true,
    "temporal_constraint": true
  },
  "expected": {
    "allowed_request_types": [
      "hidden_target"
    ],
    "forbidden_exact_seeds": [],
    "required_context_entities": [],
    "required_exact_seeds": [
      {
        "type": "artist",
        "value": "Ice Cube"
      }
    ],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "type": "tag",
        "value": "Just wakin' up in the morning"
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
          "confidence": 0.4,
          "evidence_text": "starts with 'Just wakin' up in the morning, gotta thank God'",
          "request_type": "hidden_target"
        }
      ],
      "evidence_text": "classic Ice Cube song from the 90s that starts with 'Just wakin' up in the morning, gotta thank God'",
      "request_type": "exact_track",
      "source_turn": 1,
      "summary": "Play the classic Ice Cube song from the 90s that starts with 'Just wakin' up in the morning, gotta thank God'."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "must_use",
        "evidence_text": "Ice Cube",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 1,
        "type": "artist",
        "value": "Ice Cube"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "from the 90s",
        "facet": "era",
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "1990s"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "starts with 'Just wakin' up in the morning, gotta thank God'",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "Just wakin' up in the morning, gotta thank God"
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

