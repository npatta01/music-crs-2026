# State Role Label Evaluation

- Labels: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_role_labels_v2.json`
- States: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_fact_v1_paid_current_full_audit.jsonl`
- Samples: `56`
- All-pass: `0.679`

## Checks

| Check | Rate |
|---|---:|
| schema_valid | `1.000` |
| request_type | `0.893` |
| exact_seeds | `0.964` |
| style_references | `0.964` |
| query_facets | `0.875` |
| context_entities | `0.929` |
| exclusions | `0.982` |
| forbidden_exact_seeds | `0.982` |
| temporal_constraint | `0.982` |

## Failures

### `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `popular_new_artist`
- Missing: `request_type: attribute_search not in ['new_artist']`

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
      "new_artist"
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
        "value": "well-known"
      },
      {
        "value": "popular"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "well-known songs that are popular and have a great, positive energy, regardless of genre, as long as they're not too",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Well-known, popular, feel-good songs with great positive energy, regardless of genre, not too niche."
    },
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
        "value": "electronic"
      },
      {
        "value": "soulful"
      },
      {
        "value": "out there"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "What else have you got that's really out there?",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Something really out there and unique, continuing the discovery journey of unexpected music."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "totally what I was looking for",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 4,
        "type": "track",
        "value": "fd7a7448-c45b-468d-ac9b-8e9e0afbfc77"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "cool change of pace",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 5,
        "type": "track",
        "value": "9516fd50-17ac-4c3b-98bb-d3953da822b7"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "interesting mix of sounds",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "track",
        "value": "87f586dc-843e-43a5-a29e-06c67ebdb870"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Flying Lotus",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 6,
        "type": "artist",
        "value": "Flying Lotus"
      },
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
        "evidence_text": "unique",
        "facet": "sonic",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 6,
        "type": "attribute",
        "value": "unique"
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
- Missing: `query_facet: ambient electronic, temporal: kind`

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
        "value": "dreamy"
      },
      {
        "value": "serene"
      },
      {
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
      "evidence_text": "warm, ethereal, and subtly rhythmic quality that truly embodies the distinct feel of the late 2000s (2007-2009)",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "A warm, ethereal, subtly rhythmic, strictly instrumental ambient electronic track from 2007-2009 that defines that late 2000s era."
    },
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
- Missing: `request_type: hidden_target not in ['exact_album', 'same_album']`

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
      "exact_album",
      "same_album"
    ],
    "forbidden_exact_seeds": [],
    "required_context_entities": [],
    "required_exact_seeds": [
      {
        "type": "artist",
        "value": "Panic! At The Disco"
      },
      {
        "type": "album",
        "value": "A Fever You Can't Sweat Out"
      }
    ],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "value": "mid-2000s emo"
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
      "evidence_text": "the track I'm thinking of is definitely from their first album, 'A Fever You Can't Sweat Out'",
      "request_type": "hidden_target",
      "source_turn": 6,
      "summary": "Find the specific Panic! At The Disco track from 'A Fever You Can't Sweat Out' with a dramatic, theatrical, anthemic chorus about something intense."
    },
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
- Missing: `request_type: attribute_search not in ['new_artist']`

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
      "new_artist"
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
        "value": "female artist"
      },
      {
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
      "evidence_text": "another iconic female artist from the 90s who has a similar thoughtful, storytelling approach",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Another iconic female artist from the 90s with a thoughtful, storytelling approach to their music."
    },
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
- Missing: `query_facet: artistically unique`

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
        "value": "striking"
      },
      {
        "value": "artistically unique"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "new album discoveries from the 2010s, specifically electronic albums with covers that are just as striking or artistclyc",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Electronic albums from the 2010s with striking, unique, abstract, or memorable cover art, from different artists than Daft Punk or Four Tet."
    },
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
      "new_artist"
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
        "value": "heavy alternative metal"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
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
        "evidence_text": "but not them",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 8,
        "type": "artist",
        "value": "System Of A Down"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "new bands",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 7,
        "type": "artist",
        "value": "Flying Lotus"
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
- Missing: `query_facet: boost my energy, context_entity: Lupe Fiasco, exclusion: heavy and intense`

```json
{
  "checks": {
    "context_entities": false,
    "exact_seeds": true,
    "exclusions": false,
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
        "value": "positive vibe"
      },
      {
        "value": "boost my energy"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "suggest something genuinely upbeat, energetic, and feel-good",
      "request_type": "attribute_search",
      "source_turn": 5,
      "summary": "Genuinely upbeat, energetic, feel-good hip-hop to boost mood and energy; no more Lupe Fiasco tracks."
    },
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
- Missing: `context_entity: Linkin Park`

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
      "new_artist"
    ],
    "forbidden_exact_seeds": [
      {
        "type": "artist",
        "value": "Pantera"
      },
      {
        "type": "artist",
        "value": "Linkin Park"
      },
      {
        "value": "Pantera"
      },
      {
        "value": "Linkin Park"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "rejected",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Pantera"
      },
      {
        "allowed_roles": [
          "history",
          "rejected"
        ],
        "type": "artist",
        "value": "Linkin Park"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "value": "aggressive nu-metal"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "new bands for me, besides Linkin Park and Pantera",
      "request_type": "new_artist",
      "source_turn": 8,
      "summary": "Discover new bands besides Linkin Park and Pantera with an aggressive nu-metal sound from the late 90s/early 2000s, mixing heavy riffs with rap or industrial/electronic influences."
    },
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
- Missing: `request_type: new_artist not in ['exact_artist', 'same_artist'], exact_seed: Rusty Cage`

```json
{
  "checks": {
    "context_entities": true,
    "exact_seeds": false,
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
      "exact_artist",
      "same_artist"
    ],
    "forbidden_exact_seeds": [],
    "required_context_entities": [],
    "required_exact_seeds": [
      {
        "type": "artist",
        "value": "Soundgarden"
      },
      {
        "type": "track",
        "value": "Rusty Cage"
      },
      {
        "type": "artist",
        "value": "Stone Temple Pilots"
      },
      {
        "type": "artist",
        "value": "Nirvana"
      }
    ],
    "required_exclusions": [],
    "required_query_facets": [],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "no Soundgarden at all? ... If not, how about something by Stone Temple Pilots or Nirvana?",
      "request_type": "new_artist",
      "source_turn": 6,
      "summary": "User wants Soundgarden (specifically tracks like \"Spoonman\" or \"Rusty Cage\"), or if unavailable, another grunge band like Stone Temple Pilots or Nirvana."
    },
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
        "mentioned_current_turn": false,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 5,
        "type": "track",
        "value": "Spoonman"
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
- Missing: `request_type: same_artist not in ['exact_album', 'same_album']`

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
      "exact_album",
      "same_album"
    ],
    "forbidden_exact_seeds": [],
    "required_context_entities": [],
    "required_exact_seeds": [
      {
        "type": "artist",
        "value": "Natalia Lafourcade"
      },
      {
        "type": "album",
        "value": "Natalia Lafourcade"
      }
    ],
    "required_exclusions": [],
    "required_query_facets": [],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "anything from her first album, 'Natalia Lafourcade'",
      "request_type": "same_artist",
      "source_turn": 2,
      "summary": "A track from Natalia Lafourcade's first album 'Natalia Lafourcade'."
    },
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
- Missing: `request_type: attribute_search not in ['same_album', 'exact_album'], query_facet: Eliza`

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
      "same_album",
      "exact_album"
    ],
    "forbidden_exact_seeds": [],
    "required_context_entities": [],
    "required_exact_seeds": [
      {
        "type": "album",
        "value": "Hamilton"
      }
    ],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "value": "Eliza"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "songs from Hamilton that really showcase Eliza's character development or her relationship with Alexander",
      "request_type": "attribute_search",
      "source_turn": 4,
      "summary": "Recommend Hamilton songs that showcase Eliza's character development or her relationship with Alexander."
    },
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
- Missing: `query_facet: watching a movie`

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
        "value": "vivid storytelling"
      },
      {
        "value": "watching a movie"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "tracks with really vivid storytelling that almost feel like watching a movie, where the details are super clear",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "Hip-hop tracks with vivid, cinematic storytelling where the details are super clear, like watching a movie."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "query_facet",
        "evidence_text": "vivid storytelling that almost feel like watching a movie",
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
        "evidence_text": "like watching a movie, where the details are super clear",
        "facet": "lyrical_theme",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "cinematic narrative"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Kendrick really goes in",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 8,
        "type": "artist",
        "value": "Kendrick Lamar"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Kevin Gates always keeps it real",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "history",
        "reuse": "not_applicable",
        "role": "history",
        "source_turn": 5,
        "type": "artist",
        "value": "Kevin Gates"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "Kid Cudi's vibe is different",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "history",
        "reuse": "not_applicable",
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
- Missing: `context_entity: Brent Faiyaz, forbidden_exact_seed: Brent Faiyaz`

```json
{
  "checks": {
    "context_entities": false,
    "exact_seeds": true,
    "exclusions": true,
    "forbidden_exact_seeds": false,
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
        "value": "Brent Faiyaz"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "artist",
        "value": "Brent Faiyaz"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "value": "groove"
      },
      {
        "value": "chill R&B"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "similar to this, or maybe something with a bit more of a groove but still chill R&B",
      "request_type": "attribute_search",
      "source_turn": 5,
      "summary": "Chill R&B/Soul with a smooth vibe, possibly with more groove but still chill."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": null,
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "history",
        "reuse": "not_applicable",
        "role": "history",
        "source_turn": 4,
        "type": "artist",
        "value": "Dennis Lloyd"
      },
      {
        "anchor_use": "must_use",
        "evidence_text": "I like Brent Faiyaz",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
        "role": "current_target",
        "source_turn": 5,
        "type": "artist",
        "value": "Brent Faiyaz"
      },
      {
        "anchor_use": "do_not_use",
        "evidence_text": "good one",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
        "role": "satisfied_prior",
        "source_turn": 5,
        "type": "track",
        "value": "Talk 2 U"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "chill R&B",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
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
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "smooth"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "chill R&B",
        "facet": "genre",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 5,
        "type": "attribute",
        "value": "R&B"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "more of a groove",
        "facet": "energy",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
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
- Missing: `style_reference: Mac Miller`

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
    "style_references": false,
    "temporal_constraint": true
  },
  "expected": {
    "allowed_request_types": [
      "similar_to_prior",
      "attribute_search"
    ],
    "forbidden_exact_seeds": [],
    "required_context_entities": [],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "value": "lyrical storytelling"
      }
    ],
    "required_style_references": [
      {
        "type": "artist",
        "value": "Mac Miller"
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
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "not just Mac Miller",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
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
- Missing: `query_facet: deep longing, query_facet: emotional storytelling`

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
      "new_artist"
    ],
    "forbidden_exact_seeds": [],
    "required_context_entities": [],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [
      {
        "value": "deep longing"
      },
      {
        "value": "emotional storytelling"
      },
      {
        "value": "sertanejo"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "other artists but with a similar powerful, emotional sertanejo vibe",
      "request_type": "new_artist",
      "source_turn": 7,
      "summary": "Other artists with a powerful, emotional sertanejo vibe similar to Marília Mendonça's heartfelt style."
    },
    "exclusions": [],
    "facts": [
      {
        "anchor_use": "do_not_use",
        "evidence_text": "other artists",
        "facet": null,
        "mentioned_current_turn": false,
        "relation": "satisfied_prior",
        "reuse": "avoid_exact",
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
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 7,
        "type": "attribute",
        "value": "sertanejo"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "powerful, emotional",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 7,
        "type": "attribute",
        "value": "powerful emotional"
      },
      {
        "anchor_use": "query_facet",
        "evidence_text": "deep, heartfelt lyrics",
        "facet": "lyrical_theme",
        "mentioned_current_turn": false,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 1,
        "type": "attribute",
        "value": "deep heartfelt lyrics"
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
- Missing: `style_reference: John Fogerty, style_reference: Bruce Springsteen`

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
    "style_references": false,
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
        "value": "Night Moves"
      }
    ],
    "required_context_entities": [
      {
        "allowed_roles": [
          "history",
          "satisfied_prior"
        ],
        "type": "track",
        "value": "Night Moves"
      }
    ],
    "required_exact_seeds": [],
    "required_exclusions": [],
    "required_query_facets": [],
    "required_style_references": [
      {
        "type": "artist",
        "value": "John Fogerty"
      },
      {
        "type": "artist",
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
        "anchor_use": "must_use",
        "evidence_text": "from someone like John Fogerty",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "must_reuse",
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
        "relation": "exact_target",
        "reuse": "must_reuse",
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
        "value": "upbeat"
      },
      {
        "value": "quirky electronic"
      }
    ],
    "required_style_references": []
  },
  "observed": {
    "current_request": {
      "evidence_text": "Gorillaz track with a more upbeat or quirky electronic feel",
      "request_type": "same_artist",
      "source_turn": 8,
      "summary": "A Gorillaz track with a more upbeat or quirky electronic feel, maybe instrumental-focused or from 'Cracker Island'."
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
        "evidence_text": "upbeat or quirky electronic feel",
        "facet": "mood",
        "mentioned_current_turn": true,
        "relation": "query_facet",
        "reuse": "not_applicable",
        "role": "current_target",
        "source_turn": 8,
        "type": "attribute",
        "value": "upbeat quirky electronic"
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
        "anchor_use": "query_facet",
        "evidence_text": "from one of their newer albums like 'Cracker Island'",
        "facet": null,
        "mentioned_current_turn": true,
        "relation": "exact_target",
        "reuse": "not_applicable",
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

