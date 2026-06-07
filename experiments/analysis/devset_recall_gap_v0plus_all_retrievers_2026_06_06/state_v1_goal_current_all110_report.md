# State Replay Extraction Report

- State source: `live`
- Model: `openrouter/deepseek/deepseek-v4-flash / prompt=current`
- Samples: `110`
- Overall all-pass rate: `0.291`
- New state captures expected information: `32/110`
- Improved vs previous trace state: `33/110`
- Regressed vs previous trace state: `11/110`

## Pack Results

| Pack | N | All Pass | Request Type | Role | Artist Mode | Profile | Temporal | Rejection | Positive Control |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_good_state_ranker_near_miss_failure | 10 | 0.000 | 1.000 | 0.900 | 0.000 | 0.100 | 1.000 | 1.000 | 1.000 |
| P0_named_artist_ranker_failure | 10 | 0.300 | 1.000 | 0.500 | 0.300 | 0.300 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 10 | 0.100 | 1.000 | 1.000 | 0.100 | 0.100 | 1.000 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 10 | 0.200 | 1.000 | 0.900 | 0.200 | 0.200 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 10 | 0.200 | 1.000 | 0.900 | 0.200 | 0.200 | 0.900 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 10 | 0.100 | 1.000 | 0.900 | 0.100 | 0.100 | 0.900 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 10 | 0.100 | 1.000 | 1.000 | 0.100 | 0.100 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 10 | 0.900 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.900 | 1.000 |
| P1_temporal_constraint_failure | 10 | 0.200 | 1.000 | 1.000 | 0.200 | 0.200 | 1.000 | 1.000 | 1.000 |
| POS_clean_final_hit_control | 10 | 0.200 | 1.000 | 1.000 | 0.200 | 0.200 | 1.000 | 1.000 | 0.200 |
| POS_exact_entity_success_control | 10 | 0.900 | 1.000 | 1.000 | 1.000 | 0.900 | 1.000 | 1.000 | 1.000 |

## State Change Evaluation

Each row compares the previous trace state snapshot against the new extracted state and the desired state contract for the replay example.

## Failures

### `0b9d547f-e748-464a-90e2-2199149f915c::t6`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes! "Can You Feel the Force" is awesome, such a great track. That's exactly the kind of energy I'm looking for. What are some other high-energy, classic disco or funk tracks from that late 70s to early 80s period?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "The Real Thing"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "high-energy, classic disco or funk tracks",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "exactly the kind of energy I'm looking for",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "other high-energy, classic disco or funk tracks from that late 70s to early 80s period",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Other high-energy, classic disco or funk tracks from the late 70s to early 80s period."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "The Sweetest Pain"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Toto"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Georgy Porgy"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Can You Feel the Force"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "The Real Thing"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "high-energy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic disco"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1977,
        1984
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "The Real Thing",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Can You Feel the Force",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "high-energy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "disco"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "late 70s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 80s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1975,
        1984
      ],
      "strength": "soft"
    }
  }
}
```

### `e66c6a88-88ba-4117-9114-363bfa96294a::t7`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: This is absolutely perfect! "Anthem of the World" is exactly the powerful and uplifting epic music I was looking for. Can you give me more recommendations that are similar to this or Two Steps from Hell?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "Future World Music"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "similar to this or Two Steps from Hell",
          "request_type": "similar_to_prior"
        },
        {
          "confidence": 0.5,
          "evidence_text": "powerful and uplifting epic music",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "similar to this or Two Steps from Hell",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "More powerful and uplifting epic orchestral tracks like the prior matched track (Anthem of the World) or similar to Two Steps from Hell."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Future World Music"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Anthem of the World"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Two Steps from Hell"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "epic orchestral"
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
        "value": "uplifting"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Two Steps from Hell",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Future World Music",
        "was_stale_in_trace": true
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
        "value": "uplifting"
      },
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
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intense"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `0858f444-c9af-4f08-a9fc-2a731a24182b::t5`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes! "Pallbearer" is absolutely brutal, exactly the kind of intricate and relentless breakcore I was hoping for. Great pick! Can you recommend something with a similar raw power and darkness, but maybe a bit more stripped-down or minimalistic in its approac...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "Igorrr"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "more stripped-down or minimalistic",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.55,
          "evidence_text": "similar raw power and darkness",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "more stripped-down or minimalistic",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Something with similar raw power and darkness, but more stripped-down/minimalistic, possibly from the experimental industrial/breakcore sphere."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Ministry"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": ":Wumpscut:"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Igorrr"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Pallbearer"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw power"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "darkness"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "stripped-down minimalistic"
      },
      {
        "role": "satisfied",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "intricate breakbeats"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Igorrr",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Pallbearer",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw"
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
        "value": "dark"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "stripped-down"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "minimalistic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intense"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  }
}
```

### `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
- Current user: This is exactly the kind of intricate storytelling I'm digging into. The way Kendrick builds a narrative and develops characters, with the music itself being a part of that journey, is just next level. 'untitled 03' definitely has that layered depth. Keep '...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Deltron 3030"
      },
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Kendrick Lamar"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.8,
          "evidence_text": "Keep 'em coming. More Kendrick storytelling tracks like that.",
          "request_type": "same_artist"
        },
        {
          "confidence": 0.3,
          "evidence_text": "intricate storytelling",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "Keep 'em coming. More Kendrick storytelling tracks like that.",
      "request_type": "same_artist",
      "source_turn": 3,
      "summary": "More Kendrick Lamar tracks with intricate storytelling, narrative, character development, and music that is a vital part of the journey."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Kendrick Lamar"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "DUCKWORTH."
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intricate storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "narrative and character development"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "music is part of the journey"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Deltron 3030",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Kendrick Lamar",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "narrative flow"
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
        "value": "storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "production-intertwined"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "concept album"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip hop"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct, temporal_semantics_correct`
- Current user: Yes! That's a classic, I know that one well! It definitely fits the vibe of what I was looking for. It's got that undeniable groove.

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1970,
        1979
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "temporal_semantics_correct"
    ],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [],
      "evidence_text": "Yes! That's a classic, I know that one well!",
      "request_type": "unknown",
      "source_turn": 2,
      "summary": "The user is satisfied with the recommendation but has not requested any additional action or follow-up yet."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Hollywood Swinging"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kool & The Gang"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Kool & The Gang",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Hollywood Swinging",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funky"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk"
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
        "value": "70s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dance"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "groove"
      }
    ],
    "rejections": [],
    "retrieval_profile": null,
    "target_artist_mode": "unknown",
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

### `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes! Guano Apes! I love this song, it's so powerful. The vocalist is amazing. Do you have any other powerful rock songs, maybe with a really strong guitar riff?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Guano Apes"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "powerful rock songs with a really strong guitar riff",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "other powerful rock songs",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "other powerful rock songs, maybe with a really strong guitar riff",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Other powerful rock songs with a strong guitar riff, with Guano Apes as satisfied context."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Guano Apes"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Big in Japan"
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
        "value": "powerful"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong guitar riff"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Guano Apes",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Big in Japan",
        "was_stale_in_trace": true
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
        "value": "rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong guitar riff"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "guitar riff"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "female vocalist"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "female fronted"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  }
}
```

### `88af7ec3-c368-421b-9512-d0180da3d1f6::t2`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Oh my goodness, that's a very interesting choice! "I Write Sins Not Tragedies" definitely has a strong story. I remember a song like that, with a wedding drama. Can you remind me of any specific lines about a bartender, or someone overhearing gossip?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "Panic! At The Disco"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "remember a song",
          "request_type": "hidden_target"
        },
        {
          "confidence": 0.3,
          "evidence_text": "lyrics about a bartender overhearing gossip",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "I remember a song like that, with a wedding drama. ... lines about a bartender, or someone overhearing gossip?",
      "request_type": "hidden_target",
      "source_turn": 2,
      "summary": "User is trying to recall a 2000s song with a wedding drama scene, specific lines about a bartender or overhearing gossip; \n   'I Write Sins Not Tragedies' is a contrast."
    },
    "entities": [
      {
        "role": "contrast",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "I Write Sins Not Tragedies"
      },
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Panic! At The Disco"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "overhearing gossip"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "bartender"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "wedding drama"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2000s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2009
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Panic! At The Disco",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "I Write Sins Not Tragedies",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "mini-drama"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2000s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "wedding"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "drama"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2009
      ],
      "strength": "soft"
    }
  }
}
```

### `d9a65836-7165-45bf-aa3e-3ef7ba5d073a::t2`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: That's a good one, it totally brings back early 2000s pop-punk! It's got the energy, but I'm looking for something that feels a bit more... not quite heavier, but with a stronger angsty feel. Still from that early 2000s pop-punk or alternative rock vibe, ma...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2004
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "stronger angsty feel",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.45,
          "evidence_text": "brings back early 2000s pop-punk",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "something that feels a bit more... not quite heavier, but with a stronger angsty feel",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "An early 2000s pop-punk or alternative rock track with a stronger angsty feel, without being too heavy."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pop-punk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "alternative rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 2000s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "angsty"
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
        "value": "heavier"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "heavier"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "heavier"
      }
    ],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1999,
        2003
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Bowling For Soup",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Girl All the Bad Guys Want",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pop-punk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "alternative rock"
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
        "value": "energetic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "angsty"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 2000s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2004
      ],
      "strength": "soft"
    }
  }
}
```

### `c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes! That's exactly the track! 'Toxic' by Britney Spears always makes me feel that way. It's so iconic and brings back all those confident, dancing vibes. You nailed it! Thanks! Can you recommend something else with a similar super strong, driving beat? May...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Britney Spears"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "super strong, driving beat",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.6,
          "evidence_text": "similar super strong, driving beat",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "similar super strong, driving beat",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Something else with a similar super strong, driving beat, maybe a bit more recent but still empowering pop energy."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Toxic"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Britney Spears"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "super strong driving beat"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "empowering pop energy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "more recent"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Britney Spears",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Toxic",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "driving beat"
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
        "value": "empowering"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dance"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "confident"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  }
}
```

### `88beb200-0334-4aba-be15-8e1303725766::t6`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Legend" is a classic, no doubt! I'm good on Drake for now though. I was hoping for some popular Hip-Hop tracks from *other artists* around late 2015 to early 2016. Any major hits from that period by someone different?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": {
      "artist_ids": "from resolver.rejected_artist_ids",
      "names": "verified aliases only",
      "track_ids": "from resolver.rejected_track_ids"
    },
    "prior_entities": [],
    "retrieval_profile": "continuation",
    "state_to_retriever_contract": null,
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "other artists",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.7,
          "evidence_text": "popular Hip-Hop tracks from late 2015 to early 2016",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "other artists around late 2015 to early 2016",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Popular hip-hop hits from late 2015 to early 2016 by artists other than Drake."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Drake"
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
        "value": "popular"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "major hits"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "PARTYNEXTDOOR"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Drake"
      }
    ],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
      "range": [
        2015,
        2016
      ],
      "strength": "hard"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Drake",
        "was_stale_in_trace": false
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
        "value": "hip hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rap"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "late 2015"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 2016"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "major hits"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Drake"
      }
    ],
    "retrieval_profile": "novelty",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2015,
        2016
      ],
      "strength": "soft"
    }
  }
}
```

### `daeef24e-b041-4140-9101-882820c63408::t7`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
- Current user: Okay, it sounds like there's a problem with 'Tom Sawyer'. That's a bummer. Can you please play 'The Spirit of Radio' by Rush instead?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Rush"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.3,
          "evidence_text": "by Rush",
          "request_type": "exact_artist"
        }
      ],
      "evidence_text": "play 'The Spirit of Radio' by Rush instead",
      "request_type": "exact_track",
      "source_turn": 3,
      "summary": "Play 'The Spirit of Radio' by Rush as a replacement for 'Tom Sawyer'."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Tom Sawyer"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "The Spirit of Radio"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Rush"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "Tom Sawyer"
      },
      {
        "kind": "artist",
        "scope": "soft",
        "value": "Rush"
      }
    ],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "The Spirit of Radio",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Rush",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Tom Sawyer",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "progressive rock"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  }
}
```

### `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: This is excellent! The melodic technicality of Allegaeon is exactly the kind of balance I was looking for. Can you suggest something else that leans into orchestral or symphonic elements alongside the technicality?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Allegaeon"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "orchestral or symphonic elements",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.45,
          "evidence_text": "similar in terms of experimental complexity",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "orchestral or symphonic elements alongside the technicality",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Something that leans into orchestral or symphonic elements alongside technicality, similar to the experimental complexity found but now with a more melodic/atmospheric edge."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Testimonial Ruins"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Gorguts"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "The Cleansing"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Allegaeon"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "technical"
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
        "value": "symphonic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "melodic"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Allegaeon",
        "was_stale_in_trace": false
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
        "value": "symphonic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "technical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "technical death metal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "melodic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "progressive metal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "metal"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `5f085552-b56b-440e-830b-b4e40b58f854::t6`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes, Tim McGraw definitely brings that big energy! That's another great anthem from that era. Keep them coming – can you find me another upbeat, high-energy country track from the late 90s or early 2000s that really gets you moving?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1995,
        2004
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "upbeat, high-energy country track",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.5,
          "evidence_text": "another upbeat, high-energy country track",
          "request_type": "similar_to_prior"
        },
        {
          "confidence": 0.4,
          "evidence_text": "Keep them coming",
          "request_type": "new_artist"
        }
      ],
      "evidence_text": "another upbeat, high-energy country track from the late 90s or early 2000s",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another upbeat, high-energy country track from the late 90s or early 2000s."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "I Ain't Goin' Down"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Shania Twain"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "You Get Used To Somebody"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Tim McGraw"
      },
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
        "value": "late 90s or early 2000s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1997,
        2004
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Tim McGraw",
        "was_stale_in_trace": false
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
        "value": "high-energy"
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
        "value": "country"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "anthem"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "stadium-filling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "sing-along"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1995,
        2004
      ],
      "strength": "soft"
    }
  }
}
```

### `d6e50fb5-a135-4008-80b6-d0be434369ac::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes, this is absolutely perfect! Frank Sinatra's 'In The Wee Small Hours Of The Morning' really captures that nostalgic, contemplative mood I was looking for, with the classic vocals and instrumentation. This is exactly the blend of classic vocals and bitte...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Frank Sinatra"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "absolutely perfect",
          "request_type": "similar_to_prior"
        },
        {
          "confidence": 0.25,
          "evidence_text": "classic vocals and bittersweet",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "this is absolutely perfect! Frank Sinatra's 'In The Wee Small Hours Of The Morning' really captures that nostalgic, contemplative mood",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "More songs similar to 'In The Wee Small Hours Of The Morning' with classic vocals, wistful nostalgic mood, piano or string accompaniment, and a bittersweet feeling."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "In the Wee Small Hours of the Morning"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Frank Sinatra"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "nostalgic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "contemplative"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "bittersweet"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic vocal style"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "piano or string accompaniment"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1950,
        1960
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Frank Sinatra",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "In The Wee Small Hours Of The Morning",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic vocalist"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic vocals"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "nostalgic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "contemplative"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "reflective"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "melancholic"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "hard",
        "value": "cheerful"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `38d8ba41-a4ea-48ea-b460-bd93d164302a::t4`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yeah, M.O.P. is pure raw energy! "Cold as Ice" is a banger, definitely keeps that gritty East Coast sound going strong. Give me another one that brings that same kind of raw, uncompromising street vibe from the 90s.

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "M.O.P."
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "raw, uncompromising street vibe",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "same kind of raw",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "another one that brings that same kind of raw, uncompromising street vibe from the 90s",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another track with the same raw, uncompromising gritty 90s East Coast street vibe; previous tracks satisfied."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "C.R.E.A.M."
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Wu-Tang Clan"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Cold as Ice"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "M.O.P."
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "gritty 90s East Coast"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "uncompromising street vibe"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "1990s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1999
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "M.O.P.",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "uncompromising"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "street"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "gritty"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "east coast"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "east coast hip hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip hop"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": null,
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

### `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes, this is exactly the kind of sound I was looking for! "Welcome To Jamrock" is a classic. That definitely fits the "defined an era" vibe. Can you give me another track that has that timeless, era-defining feeling, maybe an old-school hip-hop gem this time?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Damian Marley"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "timeless, era-defining feeling, old-school hip-hop gem",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "this is exactly the kind of sound",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "another track that has that timeless, era-defining feeling, maybe an old-school hip-hop gem",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "An old-school hip-hop track with a timeless, era-defining feeling; Damian Marley jamrock style is satisfied context."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Welcome To Jamrock"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Damian Marley"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "old-school hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "timeless era-defining"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Damian Marley",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Welcome To Jamrock",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "timeless"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "era-defining"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "old-school"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "foundational"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Another fantastic Michael Jackson track! 'Will You Be There' is definitely a powerful and energetic song that everybody knows. These are exactly the kind of widely loved, feel-good hits I enjoy. What other well-known songs do you have that are popular and h...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": "derive a focused retrieval profile from current target, entity roles, tags, goal/profile context, and constraints",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
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
    "entities": [
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
        "value": "widely loved"
      },
      {
        "role": "satisfied",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "hugely popular"
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
        "value": "upbeat"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "energetic"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
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
        "value": "not too niche"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "mainstream"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `5ee0dbbc-c1d1-4bed-ba09-7dafeec198bc::t8`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Dude, 'The Ultimate Showdown of Ultimate Destiny' is awesome! That song is a classic, the story is just so over-the-top and hilarious. You really crushed it with these meme and goofy song recommendations! Thanks! What else you got for me? Maybe something mo...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": "derive a focused retrieval profile from current target, entity roles, tags, goal/profile context, and constraints",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": true,
    "regressed_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [],
      "evidence_text": "funny because it tells a really absurd or unexpected story with characters",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "A funny meme song that tells an absurd or unexpected story with characters."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "meme song/goofy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "absurd story with characters"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "famous viral"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "catchy vocal hook"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
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
        "value": "hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rap"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  }
}
```

### `4e2482dc-a76c-4f4b-9d3f-7becec2f8a3a::t4`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: That was a fantastic, energetic piece! The swing was just what I was looking for. I'm really getting a good sense of the range of classic jazz. To round out this exploration, could we try something that perhaps feels a bit more bluesy or soulful, but still...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": "derive a focused retrieval profile from current target, entity roles, tags, goal/profile context, and constraints",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "bluesy or soulful",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "to round out this exploration",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "something that perhaps feels a bit more bluesy or soulful, but still...",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "A classic jazz piece that feels bluesy or soulful, rounding out the exploration of different moods."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic jazz"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "bluesy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "soulful"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Chet Baker"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Django Reinhardt"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic jazz"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazz"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "bluesy"
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
        "value": "blues"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "soul"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  }
}
```

### `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Oh, Flying Lotus! This is cool, it's got a really interesting mix of sounds. It's like electronic but also soulful, very unique. What else have you got that's really out there?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Boards of Canada"
      },
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Flying Lotus"
      },
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Liu Fang"
      },
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Noriko Miyamoto"
      },
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Severed Heads"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
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
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "unique and out-there"
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
        "value": "interesting mix of sounds"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Boards of Canada",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Aphex Twin",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Severed Heads",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Liu Fang",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Noriko Miyamoto",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Flying Lotus",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "fresh and unexpected"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "unique"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `907921a3-d08f-4ba1-8cce-0e760a9e7044::t7`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: This one has a cool electronic sound and it's definitely emotional. But I'm still looking for that really strong, direct "plea" or "begging" in the lyrics, like in "Iris," but for electronic songs. Do you have any tracks that really hit that direct lyrical...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "Men I Trust"
      },
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "The Goo Goo Dolls"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "strong, direct 'plea' or 'begging' in the lyrics",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "similar electronic sound resonant lyrics",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "strong, direct 'plea' or 'begging' in the lyrics",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Electronic songs with a direct, intense plea or begging in the lyrics, similar in style to Men I Trust but with stronger direct plea language."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Men I Trust"
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
        "value": "direct intense plea"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "begging"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Men I Trust",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Iris",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "The Goo Goo Dolls",
        "was_stale_in_trace": true
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
        "value": "indie-electronic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heartfelt plea"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "plea"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "begging"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `ab5eac17-909e-4271-8cf9-40c06b27ee56::t2`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Oh, "IDGAF"! That's a good one, it was definitely super popular back then. Let me listen again... Hmm, it's not quite the one I'm thinking of, but it's really close in vibe! The one I'm remembering felt a bit more upbeat, maybe a bit more dancey.

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": "derive a focused retrieval profile from current target, entity roles, tags, goal/profile context, and constraints",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "not quite the one I'm thinking of",
          "request_type": "hidden_target"
        },
        {
          "confidence": 0.5,
          "evidence_text": "more upbeat, maybe a bit more dancey",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "not quite the one I'm thinking of",
      "request_type": "hidden_target",
      "source_turn": 2,
      "summary": "A highly popular pop song from around 2015-2017, more upbeat and dancey than IDGAF by Dua Lipa."
    },
    "entities": [
      {
        "role": "contrast",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "IDGAF"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pop"
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
        "value": "dancey"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "super popular"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2015 to 2017"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2015,
        2017
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pop"
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
        "value": "dancey"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dance"
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
        "value": "2015-2017"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2015,
        2017
      ],
      "strength": "soft"
    }
  }
}
```

### `324ddfb5-8a18-4729-9acb-c851907a297c::t3`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yeah, that Dead Prez track is fire! Super authentic and exactly the kind of vibe I'm into from that era. What else hits like that? Maybe some more underground stuff from the late 90s or early 2000s?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1995,
        2004
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "underground stuff from the late 90s or early 2000s",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.55,
          "evidence_text": "hits like that",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "Maybe some more underground stuff from the late 90s or early 2000s?",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "More underground, classic, raw hip-hop from the late 90s or early 2000s with an authentic vibe."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Shook Ones, Pt. II"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Mobb Deep"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Hip Hop"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Dead Prez"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "authentic vibe"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1997,
        2004
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Mobb Deep",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Dead Prez",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic"
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
        "value": "hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "authentic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1995,
        2004
      ],
      "strength": "soft"
    }
  }
}
```

### `b466a64b-b3cc-4c62-8a70-8261434f915f::t2`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes! 'Finally' by CeCe Peniston! That's exactly the track I was trying to remember. Spot on! 'Finally' is it. Can you suggest other iconic 90s dance hits similar to this one?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1999
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "iconic 90s dance hits",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.65,
          "evidence_text": "similar to this one",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "other iconic 90s dance hits similar to this one",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "Other iconic 90s dance hits with similar energetic, dance-worthy feel to 'Finally'."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Finally"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "CeCe Peniston"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "iconic"
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
        "value": "dance"
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
        "value": "dance-worthy"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1999
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "CeCe Peniston",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Finally",
        "was_stale_in_trace": false
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
        "value": "dance"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dance-pop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "iconic"
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
        "value": "house"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": null,
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

### `ba68a3cc-5278-4680-917a-4ca66d33ef31::t5`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes, this selection is great! "Wannabe" is iconic, it really gets me in a powerful mood. I think these are all perfect for what I asked for. What else do you have that's like these? Maybe some other pop artists from that same time?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Spice Girls"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.8,
          "evidence_text": "What else do you have that's like these",
          "request_type": "similar_to_prior"
        },
        {
          "confidence": 0.5,
          "evidence_text": "confident, high-energy pop anthems",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "What else do you have that's like these? Maybe some other pop artists from that same time?",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "More pop tracks similar to the first two high-energy, confident, empowering anthems, preferably from other artists and the early 2000s."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Stop"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Spice Girls"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "high-energy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "iconic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "empowering"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "confident"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 2000s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2003
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Spice Girls",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Who Do You Think You Are",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Stop",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Holler",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Wannabe",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "empowering"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "confident"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "high-energy"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes! "He's the Greatest Dancer" is such a jam! That's exactly the kind of funky, soulful sound from the late 70s I'm looking for. What else do you have from that golden era of R&B?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1975,
        1984
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "funky, soulful sound from the late 70s",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.45,
          "evidence_text": "that's exactly the kind",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "golden era of R&B",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Funky, soulful late 70s R&B from the golden era, like He's the Greatest Dancer."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "He's the Greatest Dancer"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Boogie Wonderland"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Sister Sledge"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "The Isley Brothers"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "R&B/Soul"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funky"
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
        "value": "late 1970s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1977,
        1980
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Sister Sledge",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "He's the Greatest Dancer",
        "was_stale_in_trace": false
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
        "value": "Soul"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funky"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk"
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
        "value": "soulful"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1975,
        1984
      ],
      "strength": "soft"
    }
  }
}
```

### `f2d85aa5-2086-4b1e-9974-d188c43621db::t8`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Unfortunately, 'Sleep Paralysis' is not what I'm looking for at all. The mood is too dark and harsh, not dreamy or serene like the late 2000s ambient electronic I'm trying to find. Also, the era is still off. I'm specifically looking for something with a wa...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2007,
        2009
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "specifically trying to recall",
          "request_type": "hidden_target"
        },
        {
          "confidence": 0.7,
          "evidence_text": "not what I'm looking for at all",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "not what I'm looking for at all. The mood is too dark and harsh, not dreamy or serene like the late 2000s ambient electronic I'm trying to find. Also, the era is still off. I'm specifically looking for something with a wa...",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "Find a warm, dreamy, serene, strictly instrumental ambient electronic track that screams late 2000s (specifically 2009 era); not too dark or harsh."
    },
    "entities": [
      {
        "role": "contrast",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Sleep Paralysis"
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
        "value": "dreamy serene"
      },
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
        "value": "late 2000s"
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
        "value": "subtle rhythms"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "instrumental"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "dark and harsh"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "dark and harsh"
      }
    ],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2007,
        2009
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
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
        "value": "atmospheric"
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
        "value": "shimmering"
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
        "value": "melancholic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "floating"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "hard",
        "value": "spoken word"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "dark"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "harsh"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
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

### `67b9ba8a-382f-4b70-af76-576848d8cf67::t8`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: DMX is a beast! "Where The Hood At" is definitely a raw, aggressive banger and fits that dark, intense vibe perfectly. You nailed it with these last few tracks. Thanks for the awesome recommendations! Can you suggest another track that's just pure, unfilter...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1995,
        2004
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "pure unfiltered raw aggression, dark intense gritty beats, horrorcore-influenced lyrics",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.7,
          "evidence_text": "you nailed it with these last few tracks",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "another track that's just pure, unfiltered raw aggression, dark and intense gritty beats, and horrorcore-influenced lyrics",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Pure unfiltered raw aggressive track with dark intense gritty beats and horrorcore-influenced lyrics, late 90s/early 2000s East Coast underground style."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Butcher Knife Bloodbath"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Where The Hood At"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Jedi Mind Tricks"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "DMX"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw aggression"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark and intense"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "gritty beats"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "horrorcore-influenced lyrics"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1997,
        2003
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Jedi Mind Tricks",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "DMX",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "aggressive"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "gritty"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "horrorcore"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1995,
        2004
      ],
      "strength": "soft"
    }
  }
}
```

### `9468e467-d396-461b-be29-b30b6cf87c35::t5`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes! "Blinded By The Lights" is exactly the track I was trying to recall! That's the one! You totally nailed it with that recommendation. Thanks so much! Now that you've found that one for me, can you recommend some other tracks that have a similar kind of...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2005
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "similar kind of...",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "similar kind of...",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "Other tracks like 'Blinded By The Lights' by The Streets, capturing its atmospheric, late-night, spoken-word storytelling style."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Blinded By The Lights"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "The Streets"
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
        "value": "night-time city walk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "spoken-word storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 2000s UK sound"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2004
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "The Streets",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Blinded By The Lights",
        "was_stale_in_trace": false
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
        "value": "late-night"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "spoken word"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "UK garage"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early grime"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": null,
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

### `e978bb5b-26af-4c7d-b720-b9210bdddf25::t8`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Make My" is a strong track and Black Thought's lyrics are always on point, but I'm really trying to branch out from The Roots and Masta Ace for a bit. Can you definitely give me a narrative-driven track from a *different* classic 90s East Coast artist, like...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "continuation",
    "state_to_retriever_contract": null,
    "target_artist_mode": "same_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1999
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "branch out from The Roots and Masta Ace",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.5,
          "evidence_text": "narrative-driven",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "branch out from The Roots and Masta Ace",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "A narrative-driven track from a different classic 90s East Coast hip-hop artist, branching out from The Roots and Masta Ace."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Masta Ace"
      },
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "The Roots"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "narrative-driven"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "East Coast hip-hop"
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
        "value": "classic"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Masta Ace"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "The Roots"
      }
    ],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1999
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Ghostface Killah",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Raekwon",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Kool G Rap",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "narrative"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "lyrical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "90s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": null,
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

### `3676005d-5b7c-4c48-9b73-3e10dd509c07::t3`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: YES! That's 'Divano' by ERA! That's exactly the quintessential early 2000s sound I was searching for. You nailed it! Thank you so much! Can you suggest other instrumental tracks that have a similar epic or new-age feel?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2005
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "other instrumental tracks that have a similar epic or new-age feel",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.5,
          "evidence_text": "similar",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "similar epic or new-age feel",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Other instrumental tracks with a similar epic or new-age feel to Divano by ERA."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Divano"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "ERA"
      },
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
        "value": "new-age"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "instrumental"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2005
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "ERA",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Divano",
        "was_stale_in_trace": false
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
        "value": "epic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "new-age"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "neo-classical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "neoclassical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "orchestral"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
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

### `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: You're doing so well with Panic! At The Disco and the emotional vibe! "Always" is a great song, but it's still not the one that screams "mid-2000s emo phase" to me. The track I'm thinking of is definitely from their first album, "A Fever You Can't Sweat Out...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "continuation",
    "state_to_retriever_contract": null,
    "target_artist_mode": "same_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2005,
        2006
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "target_artist_mode_correct"
    ],
    "still_missing_checks": [
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "the track I'm thinking of",
          "request_type": "hidden_target"
        }
      ],
      "evidence_text": "not the one that screams mid-2000s emo phase to me",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "Find the mid-2000s Panic! At The Disco track from A Fever You Can't Sweat Out with a dramatic, driving sound and lyrics about a messy breakup or angst."
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
        "value": "mid-2000s emo"
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
        "value": "messy breakup angst"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2004,
        2007
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Panic! At The Disco",
        "was_stale_in_trace": false
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
        "value": "emo"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pop-punk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "alternative rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dramatic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "theatrical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "anthemic"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
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

### `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: I'm trying to remember a really powerful, orchestral song from the early 2000s, like something from a movie score.

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2004
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "trying to remember",
          "request_type": "hidden_target"
        },
        {
          "confidence": 0.3,
          "evidence_text": "powerful, orchestral song from the early 2000s",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "trying to remember a really powerful, orchestral song from the early 2000s",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "Find a powerful, orchestral song from the early 2000s, like something from a movie score."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful orchestral"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "like something from a movie score"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 2000s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2005
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
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
        "value": "orchestral"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "movie score"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "cinematic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 2000s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2004
      ],
      "strength": "soft"
    }
  }
}
```

### `3ebc2b49-0f5c-4161-bbcf-e1615821103f::t2`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `rejection_normalization_correct`
- Current user: This is a good start, and it definitely fits the Assassin's Creed vibe and artist. However, I'm looking for something that emphasizes the dramatic and exploratory orchestral elements more than direct combat. Could you suggest tracks with a similar epic feel...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": {
      "artist_ids": "from resolver.rejected_artist_ids",
      "names": "verified aliases only",
      "track_ids": "from resolver.rejected_track_ids"
    },
    "prior_entities": [],
    "retrieval_profile": "continuation",
    "state_to_retriever_contract": null,
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": true,
    "regressed_checks": [
      "rejection_normalization_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "dramatic and exploratory orchestral elements",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.55,
          "evidence_text": "similar epic feel, same artist",
          "request_type": "same_artist"
        }
      ],
      "evidence_text": "emphasizes the dramatic and exploratory orchestral elements more than direct combat",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "Epic orchestral game scores similar to Assassin's Creed but emphasizing dramatic and exploratory orchestral elements more than direct combat."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Jesper Kyd"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "Assassin's Creed series"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "epic adventurous"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dramatic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "exploratory"
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
        "value": "tempo 80-120 BPM"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "direct combat"
      }
    ],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Jesper Kyd",
        "was_stale_in_trace": true
      },
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
        "value": "adventurous"
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
        "value": "game score"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "video game soundtrack"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dramatic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "exploratory"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "hard",
        "value": "combat"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  }
}
```

### `f4115525-7e44-40df-8957-e38df99f214d::t4`

- Pack: `P0_named_artist_ranker_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes! "Sad Girl" is absolutely perfect and captures that emotional depth and melancholic vibe from Lana Del Rey beautifully. This is exactly what I was looking for. Can you recommend a few more tracks like this, either from Lana Del Rey or other artists that...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Lana Del Rey"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.65,
          "evidence_text": "from Lana Del Rey",
          "request_type": "same_artist"
        },
        {
          "confidence": 0.45,
          "evidence_text": "or other artists",
          "request_type": "new_artist"
        }
      ],
      "evidence_text": "a few more tracks like this, either from Lana Del Rey or other artists",
      "request_type": "same_artist",
      "source_turn": 3,
      "summary": "More Lana Del Rey tracks with the same melancholic, atmospheric, emotional intensity; also open to other artists with that style."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Lana Del Rey"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "melancholic"
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
        "value": "emotional intensity"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Sad Girl"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Pretty When You Cry"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Lana Del Rey",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Pretty When You Cry",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Sad Girl",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "melancholic"
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
        "value": "emotional"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "female vocalist"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "female vocals"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `eee89ca2-fc86-4a9a-b4c5-2d77cb3346c8::t7`

- Pack: `P0_named_artist_ranker_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
- Current user: This is a bit too electronic. I'm looking for something with more raw power and a heavier sound, like the Deftones track, or the Tool tracks you mentioned. Do you have anything more in that heavy metal/rock vein with a really distinct and immersive sound?

```json
{
  "desired_state_read": {
    "current_target_entities": [
      {
        "role": "current_target",
        "source": "current_user_turn",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Deftones"
      }
    ],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "continuation",
    "state_to_retriever_contract": null,
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct",
      "retrieval_profile_correct"
    ],
    "still_missing_checks": [
      "target_artist_mode_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "heavy metal/rock vein with a really distinct and immersive sound",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.55,
          "evidence_text": "like the Deftones track, or the Tool tracks you mentioned",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "more raw power and a heavier sound, like the Deftones track, or the Tool tracks",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Something in the heavy metal/rock vein with raw power, heavier sound, and a distinct immersive sound, using Tool and Deftones as style context."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Eple"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Röyksopp"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Lateralus"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Tool"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Deftones"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw power"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavier"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy metal/rock"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "too electronic"
      }
    ],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Deftones",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Tool",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw power"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy metal"
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
        "value": "distinct"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "immersive"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "hard",
        "value": "electronic"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `44c3948c-bc44-4e40-ae77-82c2fec9c944::t7`

- Pack: `P0_named_artist_ranker_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
- Current user: Ah, Alejandro Fernández! 'Procuro Olvidarte' is a beautiful song, a classic. I know his music, he's great for Latin Pop. But I was hoping for a new artist this time. Can you find another *new* artist who makes Latin Pop, maybe with a strong beat?

```json
{
  "desired_state_read": {
    "current_target_entities": [
      {
        "role": "current_target",
        "source": "current_user_turn",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Alejandro Fernandez, Alejandro Fernández"
      }
    ],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "continuation",
    "state_to_retriever_contract": null,
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "retrieval_profile_correct"
    ],
    "still_missing_checks": [
      "role_correct",
      "target_artist_mode_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "hoping for a new artist this time",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.35,
          "evidence_text": "strong beat",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "new artist in Latin Pop with a strong beat",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "A new artist in Latin Pop with a strong beat, continuing from the liked prior yet seeking novelty this session."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Golpe a Golpe"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Alejandro Fernández"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Latin Pop"
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
        "value": "new artist"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Alejandro Fernández"
      },
      {
        "kind": "artist",
        "scope": "soft",
        "value": "Golpe a Golpe"
      }
    ],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "new artist"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Latin Pop"
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
        "value": "upbeat"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `93199894-d3db-4335-8278-e1be175944e4::t6`

- Pack: `P0_named_artist_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Once" is cool! Pearl Jam is awesome. But really, no Soundgarden at all? Like, not even "Rusty Cage"? If not, how about something by Stone Temple Pilots or Nirvana?

```json
{
  "desired_state_read": {
    "current_target_entities": [
      {
        "role": "current_target",
        "source": "current_user_turn",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Nirvana"
      }
    ],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "any Soundgarden",
          "request_type": "exact_artist"
        },
        {
          "confidence": 0.3,
          "evidence_text": "Pearl Jam is awesome",
          "request_type": "same_artist"
        }
      ],
      "evidence_text": "how about something by Stone Temple Pilots or Nirvana?",
      "request_type": "exact_artist",
      "source_turn": 3,
      "summary": "Fallback request for any Soundgarden track (especially Rusty Cage), otherwise Stone Temple Pilots or Nirvana."
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
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Pearl Jam",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Soundgarden",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Rusty Cage",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Stone Temple Pilots",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Nirvana",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "grunge"
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
        "value": "alternative rock"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `7d2bb60e-1046-4956-91d0-cf1dd73037cc::t3`

- Pack: `P0_named_artist_ranker_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
- Current user: Oh, "Material Girl" is such a classic! I love that one too, it really takes me back. Do you have any other Madonna songs that are a bit more upbeat, maybe from her later years, or something similar to 'La Isla Bonita' in terms of its vibe?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Madonna"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "other Madonna songs",
          "request_type": "same_artist"
        },
        {
          "confidence": 0.5,
          "evidence_text": "similar to 'La Isla Bonita' in its vibe",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.35,
          "evidence_text": "similar to 'La Isla Bonita'",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "other Madonna songs",
      "request_type": "same_artist",
      "source_turn": 3,
      "summary": "More upbeat Madonna songs from her later years, or something similar to 'La Isla Bonita' in vibe; 'Material Girl' is a classic but that context is satisfied."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Madonna"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "La Isla Bonita"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Material Girl"
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
        "value": "later era"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dreamy island vibe"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Madonna",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "La Isla Bonita",
        "was_stale_in_trace": false
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
        "value": "later years"
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
        "value": "island"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "vibe"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  }
}
```

### `1b406c88-9dfd-42cd-a1f5-9683f35f849b::t1`

- Pack: `P0_named_artist_ranker_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
- Current user: I'm looking for some classic 90s underground hip-hop with a jazzy, laid-back vibe, similar to Digable Planets or Souls Of Mischief.

```json
{
  "desired_state_read": {
    "current_target_entities": [
      {
        "role": "current_target",
        "source": "current_user_turn",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Souls Of Mischief"
      }
    ],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct"
    ],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "jazzy, laid-back vibe",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.45,
          "evidence_text": "similar to Digable Planets or Souls Of Mischief",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "classic 90s underground hip-hop with a jazzy, laid-back vibe",
      "request_type": "attribute_search",
      "source_turn": 1,
      "summary": "Classic 90s underground hip-hop with a jazzy laid-back vibe, using Digable Planets and Souls Of Mischief as style references."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Digable Planets"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Souls Of Mischief"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground hip-hop"
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
        "value": "jazzy laid-back"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1999
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Digable Planets",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Souls Of Mischief",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic"
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
        "value": "underground hip hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazzy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazz rap"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": null,
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

### `7be411cd-f002-459e-8326-3ebe8be10b42::t6`

- Pack: `P0_named_artist_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Hmm, that's a very different vibe, but it's not really what I meant by 'older songs' or 'classic eras'. I'm really looking to explore music from earlier times. Can you try again with something truly vintage, perhaps from the 80s or 70s, by an artist other t...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Kate Bush"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "something truly vintage, perhaps from the 80s or 70s",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.65,
          "evidence_text": "by an artist other than Kate Bush",
          "request_type": "new_artist"
        }
      ],
      "evidence_text": "something truly vintage, perhaps from the 80s or 70s, by an artist other than Kate Bush",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Explore music from the 80s or 70s by an artist other than Kate Bush, with a classic vintage sound."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kate Bush"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "1980s or 1970s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "vintage"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Kate Bush"
      }
    ],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1970,
        1989
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Kate Bush",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "vintage"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "80s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "70s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "older"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "nostalgic"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Kate Bush"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1970,
        1989
      ],
      "strength": "soft"
    }
  }
}
```

### `84803908-48e7-41b7-9269-a465a44f4c10::t2`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes, that's exactly the kind of strong, bold hip-hop I wanted! Are there other tracks with that intense, anthemic quality?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Kanye West"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "intense, anthemic quality",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.6,
          "evidence_text": "that exact",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "other tracks with that intense, anthemic quality",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "Other tracks with intense, anthemic quality like the previous recommendation."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "All Of The Lights"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kanye West"
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
        "value": "intense anthemic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong bold confident"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Kanye West",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "All Of The Lights",
        "was_stale_in_trace": true
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
        "value": "powerful"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "grand"
      },
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
        "value": "confident"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `6d825b33-dc20-4b3c-a277-0c8214163007::t6`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct, temporal_semantics_correct`
- Current user: Oh, "Bad Religion" is such a classic, it's one of my favorites! It perfectly captures that deep, introspective R&B feel. Do you have any tracks from actual late 90s or early 2000s neo-soul artists that are considered cult classics or essential listens withi...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [],
    "retrieval_profile": "continuation",
    "state_to_retriever_contract": null,
    "target_artist_mode": "same_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1995,
        2004
      ],
      "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "retrieval_profile_correct",
      "temporal_semantics_correct"
    ],
    "still_missing_checks": [
      "target_artist_mode_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "cult classics or essential listens within neo-soul",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "captures that deep, introspective R&B feel",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "late 90s or early 2000s neo-soul cult classics",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Late 90s or early 2000s neo-soul tracks that are cult classics or essential listens, deep introspective R&B."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "neo-soul"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "cult classics"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "essential listens"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "deep introspective"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Bad Religion"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Frank Ocean"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "C U Girl"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Steve Lacy"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
      "range": [
        1997,
        2003
      ],
      "strength": "hard"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Frank Ocean",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Bad Religion",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "neo-soul"
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
        "value": "rnb"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "cult classic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "essential listen"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "introspective"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1995,
        2004
      ],
      "strength": "soft"
    }
  }
}
```

### `942c0b23-c5ad-4270-b23f-3ba456ea0ccf::t5`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yeah, "Even Flow" is awesome too! This is exactly what I was looking for. I'm really digging this kind of powerful, thought-provoking rock. What else do you have that's like this?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Bad Religion"
      },
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Pearl Jam"
      },
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Rage Against The Machine"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "I'm really digging this kind of powerful, thought-provoking rock. What else do you have that's like this?",
          "request_type": "similar_to_prior"
        },
        {
          "confidence": 0.4,
          "evidence_text": "Pearl Jam is awesome! Show me more like this!",
          "request_type": "same_artist"
        },
        {
          "confidence": 0.6,
          "evidence_text": "powerful, thought-provoking rock",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "What else do you have that's like this?, ",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "More powerful, thought-provoking rock like Pearl Jam (the style the user liked), not specifically Pearl Jam themselves."
    },
    "entities": [
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Rage Against The Machine"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Pearl Jam"
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
        "value": "thought-provoking"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rock"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Even Flow"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Jeremy"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Bad Religion",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Rage Against The Machine",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Pearl Jam",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Even Flow",
        "was_stale_in_trace": false
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
        "value": "thought-provoking"
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
        "value": "intense"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `19c7e5bf-0797-40c5-b798-4d024af9558d::t4`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Oh, "Once Upon a December" is a classic! It absolutely has that beautiful, dramatic longing I enjoy in musicals. I'm definitely looking for more songs with that kind of deep, expressive emotion. Do you have any other suggestions, perhaps something with a gr...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Christy Altomare"
      },
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Lin-Manuel Miranda"
      },
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Phillipa Soo"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "deep, expressive emotion",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.55,
          "evidence_text": "more songs with that kind of",
          "request_type": "similar_to_prior"
        },
        {
          "confidence": 0.4,
          "evidence_text": "other musicals",
          "request_type": "same_artist"
        }
      ],
      "evidence_text": "that kind of deep, expressive emotion",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "More songs with deep, expressive emotion and dramatic longing in musicals, with a slower or more powerful build."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Once Upon a December"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Hamilton"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Anastasia"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "deep, expressive emotion"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dramatic longing"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "slower build"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "It's Quiet Uptown",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Burn",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Once Upon a December",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Lin-Manuel Miranda",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Phillipa Soo",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Christy Altomare",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "musical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "show tune"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `71b80ec3-6cca-48b4-b471-08efa00afa2d::t4`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yes, "Your Obedient Servant" is a brilliant choice for exploring the Hamilton-Burr rivalry! That's another great addition to my Hamilton playlist. Could you recommend some songs from Hamilton that really showcase Eliza's character development or her relatio...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Lin-Manuel Miranda"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "songs from Hamilton",
          "request_type": "same_album"
        },
        {
          "confidence": 0.4,
          "evidence_text": "Eliza's character development",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "songs from Hamilton that really showcase Eliza's character development or her relationship with Alexander",
      "request_type": "same_album",
      "source_turn": 3,
      "summary": "Songs from Hamilton that showcase Eliza's character development or her relationship with Alexander."
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
        "value": "Eliza character development"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Eliza's relationship with Alexander"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Cabinet Battle #2"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "The Election of 1800"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Your Obedient Servant"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Lin-Manuel Miranda",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Cabinet Battle #2",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "The Election of 1800",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Your Obedient Servant",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Eliza"
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
        "value": "relationship"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "musical"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  }
}
```

### `692611f0-d9ef-406c-8327-902575197aee::t8`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Oh yeah, "DNA." is a banger, super intense with those lyrics! Kendrick really goes in. That's a good one for sure. Can you recommend any tracks with really vivid storytelling that almost feel like watching a movie, where the details are super clear?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "DUCKWORTH."
      },
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "Kendrick Lamar"
      },
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "Kevin Gates"
      },
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "Kid Cudi"
      }
    ],
    "retrieval_profile": "continuation",
    "state_to_retriever_contract": null,
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "retrieval_profile_correct"
    ],
    "still_missing_checks": [
      "target_artist_mode_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "vivid storytelling that almost feel like watching a movie",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.5,
          "evidence_text": "that's a good one for sure",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "vivid storytelling that almost feel like watching a movie, where the details are super clear",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Tracks with vivid, dense, movie-like storytelling where details are super clear, inspired by the storytelling quality of prior tracks."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kevin Gates"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kendrick Lamar"
      },
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
        "value": "watching a movie"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dense"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "DUCKWORTH.",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Kendrick Lamar",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Kevin Gates",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Kid Cudi",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "vivid"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "detailed narrative"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "narrative"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `8071d14d-7e0f-4f72-90a6-0941db80a371::t5`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Yeah, that's a good one, I like Brent Faiyaz. "Talk 2 U" has a nice smooth vibe. What else do you have that's similar to this, or maybe something with a bit more of a groove but still chill R&B?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Brent Faiyaz"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.85,
          "evidence_text": "bit more of a groove but still chill R&B",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.5,
          "evidence_text": "similar to this",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "bit more of a groove but still chill R&B",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Chill R&B with a groove, using Brent Faiyaz's smooth vibe and the liked track as context."
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
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Dennis Lloyd"
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
        "value": "R&B"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "groove"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Brent Faiyaz",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Talk 2 U",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Dennis Lloyd",
        "was_stale_in_trace": true
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
        "value": "R&B"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Soul"
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
        "value": "groove"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `c863175a-bbaf-4f6c-aef7-cb16f2792cb5::t6`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
- Current user: Soulmate" is another fantastic pick from Mac Miller! It definitely has that deep, introspective storytelling about relationships I'm into. You're really nailing it with these. Can you hit me with more hip-hop tracks that are super strong on the lyrical stor...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Mac Miller"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.8,
          "evidence_text": "more hip-hop tracks that are super strong on the lyrical storytelling about relationships",
          "request_type": "similar_to_prior"
        },
        {
          "confidence": 0.65,
          "evidence_text": "super strong on the lyrical storytelling about relationships",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.5,
          "evidence_text": "either by Mac Miller or artists with a similar... [interrupted turn 2]",
          "request_type": "same_artist"
        }
      ],
      "evidence_text": "more hip-hop tracks that are super strong on the lyrical storytelling about relationships",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "More hip-hop tracks with strong lyrical storytelling about relationships, either by Mac Miller or similar artists."
    },
    "entities": [
      {
        "role": "history",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "To the Moon"
      },
      {
        "role": "history",
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
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Mac Miller"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Soulmate"
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
        "value": "relationships"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Mac Miller",
        "was_stale_in_trace": false
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
        "value": "storytelling"
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
        "value": "reflective"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "introspective"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `e6ba98e1-9bee-4cc9-a6b7-0a8dcd767a1f::t7`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: That's a different take on the rap-rock blend, but I'm really keen on finding tracks where the lyrical content carries that strong political or social commentary. "N 2 Gether Now" doesn't quite hit that mark for me. Can you recommend bands from that late 90...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Rage Against The Machine"
      }
    ],
    "retrieval_profile": "novelty",
    "state_to_retriever_contract": null,
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "lyrical content carries that strong political or social commentary",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.7,
          "evidence_text": "other bands from that late 90s",
          "request_type": "new_artist"
        }
      ],
      "evidence_text": "political or social commentary",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Late 90s to early 2000s rap-rock bands with raw aggressive sound and strong political/social commentary in the lyrics."
    },
    "entities": [
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Linkin Park"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "P.O.D."
      },
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Limp Bizkit"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rap-rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw aggressive"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong political or social commentary"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "late 90s to early 2000s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1997,
        2004
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Rage Against The Machine",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rap-metal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "aggressive"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "political"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "social commentary"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "overt"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "impactful"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "N 2 Gether Now"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1995,
        2004
      ],
      "strength": "soft"
    }
  }
}
```


Only the first 50 of 78 failures are shown.
