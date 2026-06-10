# State Replay Extraction Report

- State source: `live`
- Model: `openrouter/deepseek/deepseek-v4-flash / prompt=current`
- Samples: `70`
- Overall all-pass rate: `0.229`
- New state captures expected information: `16/70`
- Improved vs previous trace state: `64/70`
- Regressed vs previous trace state: `23/70`

## Pack Results

| Pack | N | All Pass | Request Type | Role | Artist Mode | Profile | Temporal | Rejection | Positive Control |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_new_artist_union20_gap_failure | 10 | 0.100 | 0.700 | 0.200 | 1.000 | 0.900 | 0.900 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 10 | 0.100 | 0.700 | 0.200 | 0.900 | 1.000 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 10 | 0.100 | 0.600 | 0.100 | 0.900 | 0.900 | 1.000 | 0.900 | 1.000 |
| P1_rejection_guardrail_failure | 10 | 0.000 | 0.700 | 0.200 | 0.900 | 0.900 | 1.000 | 0.500 | 1.000 |
| P1_temporal_constraint_failure | 10 | 0.000 | 0.700 | 0.000 | 0.800 | 0.900 | 0.500 | 1.000 | 1.000 |
| POS_clean_final_hit_control | 10 | 0.400 | 1.000 | 0.400 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| POS_exact_entity_success_control | 10 | 0.900 | 1.000 | 0.900 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## State Change Evaluation

Each row compares the previous trace state snapshot against the new extracted state and the desired state contract for the replay example.

## Failures

### `0b9d547f-e748-464a-90e2-2199149f915c::t6`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `role_correct`
- Current user: Yes! "Can You Feel the Force" is awesome, such a great track. That's exactly the kind of energy I'm looking for. What are some other high-energy, classic disco or funk tracks from that late 70s to early 80s period?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "high-energy"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "disco"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "The Real Thing"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "The Real Thing"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "other high-energy, classic disco or funk tracks",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Other high-energy classic disco or funk tracks from the late 70s to early 80s period."
    },
    "entities": [
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
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1975,
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
- Failed checks: `request_type_correct, role_correct`
- Current user: This is absolutely perfect! "Anthem of the World" is exactly the powerful and uplifting epic music I was looking for. Can you give me more recommendations that are similar to this or Two Steps from Hell?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Two Steps from Hell"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "uplifting"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "epic"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Future World Music"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Future World Music"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "more recommendations that are similar to this or Two Steps from Hell",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "More powerful, uplifting epic orchestral tracks similar to Anthem of the World or Two Steps from Hell."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Anthem of the World"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Two Steps from Hell"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful uplifting epic"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "any_artist",
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
- Failed checks: `role_correct`
- Current user: Yes! "Pallbearer" is absolutely brutal, exactly the kind of intricate and relentless breakcore I was hoping for. Great pick! Can you recommend something with a similar raw power and darkness, but maybe a bit more stripped-down or minimalistic in its approac...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Igorrr"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Igorrr"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "similar raw power and darkness, but maybe a bit more stripped-down or minimalistic",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "A track with similar raw power and darkness to Igorrr's Pallbearer, but more stripped-down or minimalistic in approach."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Pallbearer"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Igorrr"
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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

### `41367174-552b-4117-9caa-d0ba1b307d37::t2`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `role_correct`
- Current user: Yes! Twenty One Pilots is a great choice, "Stressed Out" totally has that powerful vibe I'm looking for. Can you recommend a few more songs or artists from the 2000s or 2010s that have a similar intense and emotional alternative rock sound, maybe with a str...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "alternative rock"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rock"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "My Chemical Romance"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Foo Fighters"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "My Chemical Romance",
      "Foo Fighters"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "more songs or artists from the 2000s or 2010s that have a similar intense and emotional alternative rock sound",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "More songs or artists from the 2000s or 2010s with an intense, emotional alternative rock sound similar to the powerful vibe of Twenty One Pilots, My Chemical Romance, and Foo Fighters."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Twenty One Pilots"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Stressed Out"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "My Chemical Romance"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Foo Fighters"
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
        "value": "intense emotional"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2000s or 2010s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2000,
        2019
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
        "value": "My Chemical Romance",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Foo Fighters",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Twenty One Pilots",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Stressed Out",
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
        "value": "anthemic"
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
        2019
      ],
      "strength": "soft"
    }
  }
}
```

### `10a15ba2-4126-4ae4-ac6c-dc170735ae9e::t7`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `request_type_correct, role_correct, target_artist_mode_correct`
- Current user: This is exactly the kind of intricate storytelling I'm digging into. The way Kendrick builds a narrative and develops characters, with the music itself being a part of that journey, is just next level. 'untitled 03' definitely has that layered depth. Keep '...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "narrative flow"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "character development"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Deltron 3030"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kendrick Lamar"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Deltron 3030",
      "Kendrick Lamar"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct",
      "target_artist_mode_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "Keep 'em coming, I want more tracks that have that same deep connection between the story being told and the music that’",
      "request_type": "same_artist",
      "source_turn": 3,
      "summary": "More Kendrick Lamar tracks with deep narrative storytelling and character development intertwined with the rhythm."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Kendrick Lamar"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "narrative storytelling character development deeply integrated with rhythm"
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

### `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `role_correct, rejection_normalization_correct`
- Current user: Suffocation is always a solid listen, but I'm really looking to discover some *new* bands. Can you suggest some more recent acts that are making waves in the technical or progressive death metal scene? I'm open to anything that's pushing the envelope.

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intense"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "technical"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "brutal"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Brain Drill"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Suffocation"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Brain Drill",
      "Suffocation"
    ],
    "hard_rejection_values": [
      "Suffocation"
    ],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": true,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "rejection_normalization_correct"
    ],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "new bands",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "More recent acts that are making waves in the technical or progressive death metal scene, pushing the envelope."
    },
    "entities": [
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Brain Drill"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Suffocation"
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
        "value": "progressive death metal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pushing the envelope"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2015,
        2025
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
        "value": "Brain Drill",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intense"
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
        "value": "brutal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "progressive"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "death metal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "modern"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "new"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Suffocation"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `5f29a9df-ad38-4349-a2f0-c9a690ea072d::t2`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `request_type_correct, role_correct, retrieval_profile_correct`
- Current user: Yes! That's a classic, I know that one well! It definitely fits the vibe of what I was looking for. It's got that undeniable groove.

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funky"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "upbeat"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kool & The Gang"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Hollywood Swinging"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Kool & The Gang",
      "Hollywood Swinging"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "I can't remember the name",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "Find the funky, upbeat 70s dance track the user was trying to recall."
    },
    "entities": [
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1970,
        1979
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
- Failed checks: `request_type_correct, role_correct`
- Current user: Yes! Guano Apes! I love this song, it's so powerful. The vocalist is amazing. Do you have any other powerful rock songs, maybe with a really strong guitar riff?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rock"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong guitar riff"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Big in Japan"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Big in Japan"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
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
      "request_type_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "other powerful rock songs, maybe with a really strong guitar riff",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Another powerful rock song with a strong guitar riff, different from the played artists."
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
        "value": "Guano Apes"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong guitar riff"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
- Failed checks: `role_correct`
- Current user: Oh my goodness, that's a very interesting choice! "I Write Sins Not Tragedies" definitely has a strong story. I remember a song like that, with a wedding drama. Can you remind me of any specific lines about a bartender, or someone overhearing gossip?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "mini-drama"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2000s"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Panic! At The Disco"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Panic! At The Disco"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "hidden_target"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "hidden_target_search"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": [
        "style_era",
        "reference_era"
      ],
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "song like that, with a wedding drama, lines about a bartender, overhearing gossip",
      "request_type": "hidden_target",
      "source_turn": 2,
      "summary": "A 2000s song with a story about a wedding drama, seeking specific line about a bartender or overhearing gossip."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "I Write Sins Not Tragedies"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Panic! At The Disco"
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
        "value": "bartender overhearing gossip"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "any_artist",
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

### `c7a965c3-cd7f-46f6-b166-9dce9a800e0a::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `request_type_correct, role_correct`
- Current user: Yes! That's exactly the track! 'Toxic' by Britney Spears always makes me feel that way. It's so iconic and brings back all those confident, dancing vibes. You nailed it! Thanks! Can you recommend something else with a similar super strong, driving beat? May...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "driving beat"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong beat"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "empowering"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Britney Spears"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Toxic"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Britney Spears",
      "Toxic"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "something else with a similar super strong, driving beat",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Something else with a similar super strong driving beat and empowering pop energy, maybe a bit more recent than Toxic."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Britney Spears"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Toxic"
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
        "value": "super strong driving beat"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
- Failed checks: `request_type_correct`
- Current user: Legend" is a classic, no doubt! I'm good on Drake for now though. I was hoping for some popular Hip-Hop tracks from *other artists* around late 2015 to early 2016. Any major hits from that period by someone different?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "popular"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip hop"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip-hop"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Drake"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Drake"
    ],
    "hard_rejection_values": [
      "Drake"
    ],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": true,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "role_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "other artists around late 2015 to early 2016",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Popular hip-hop tracks from other artists, around late 2015 to early 2016."
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
        "value": "Hip-Hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "popular"
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
      "apply_as_filter": false,
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

### `8dc4c630-8369-4720-b379-2a7dcd8d34aa::t7`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `role_correct`
- Current user: This is excellent! The melodic technicality of Allegaeon is exactly the kind of balance I was looking for. Can you suggest something else that leans into orchestral or symphonic elements alongside the technicality?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "orchestral"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "symphonic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "technical"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Allegaeon"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Allegaeon"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "orchestral or symphonic elements alongside the technicality",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Something that leans into orchestral or symphonic elements alongside technical complexity, similar to Allegaeon."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Allegaeon"
      },
      {
        "role": "satisfied",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "melodic technical death metal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "orchestral symphonic"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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

### `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `role_correct, target_artist_mode_correct`
- Current user: Yes! Mr. Bungle! That's exactly the band I was trying to remember. "Violenza Domestica" is definitely a great example of their sound. Thanks! Now that we found them, what else could you recommend that has a similar experimental, genre-bending vibe, maybe wi...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "experimental"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "genre-bending"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "unique vocalists"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Mr. Bungle"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Violenza Domestica"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Mr. Bungle",
      "Violenza Domestica"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct",
      "target_artist_mode_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "similar experimental, genre-bending vibe, maybe with strong theatrical vocals",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Experimental, genre-bending, avant-garde music with strong theatrical vocals, exploring other projects and artists like Mr. Bungle."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Mr. Bungle"
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
        "value": "theatrical vocals"
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
        "value": "Mr. Bungle",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Violenza Domestica",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "experimental"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "genre-bending"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "unique vocalists"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "avant-garde"
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
        "value": "experimental rock"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `5f085552-b56b-440e-830b-b4e40b58f854::t6`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `role_correct`
- Current user: Yes, Tim McGraw definitely brings that big energy! That's another great anthem from that era. Keep them coming – can you find me another upbeat, high-energy country track from the late 90s or early 2000s that really gets you moving?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "upbeat"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "high-energy"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "energetic"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Tim McGraw"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Tim McGraw"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "another upbeat, high-energy country track from the late 90s or early 2000s",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another upbeat, high-energy country track from the late 90s or early 2000s with a big, anthem-like feel."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Shania Twain"
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
        "value": "anthemic"
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
        "value": "big energetic"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
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
- Failed checks: `request_type_correct, role_correct`
- Current user: Yes, this is absolutely perfect! Frank Sinatra's 'In The Wee Small Hours Of The Morning' really captures that nostalgic, contemplative mood I was looking for, with the classic vocals and instrumentation. This is exactly the blend of classic vocals and bitte...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic vocalist"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic vocals"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "nostalgic"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Frank Sinatra"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "In The Wee Small Hours Of The Morning"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Frank Sinatra",
      "In The Wee Small Hours Of The Morning"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "classic vocals and bittersweet",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "More classic vocal songs with a nostalgic, contemplative, bittersweet mood like Frank Sinatra's In The Wee Small Hours Of The Morning, with slower tempo and piano/string accompaniment."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Frank Sinatra"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "In The Wee Small Hours Of The Morning"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Doris Day"
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
        "value": "classic vocalist"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "piano or string accompaniment"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "Que Sera, Sera"
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
- Failed checks: `role_correct`
- Current user: Yeah, M.O.P. is pure raw energy! "Cold as Ice" is a banger, definitely keeps that gritty East Coast sound going strong. Give me another one that brings that same kind of raw, uncompromising street vibe from the 90s.

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "uncompromising"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "street"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "M.O.P."
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "M.O.P."
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "another one that brings that same kind of raw, uncompromising street vibe from the 90s",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another track with raw, uncompromising street vibe, classic 90s East Coast sound."
    },
    "entities": [
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
        "value": "90s East Coast hip hop"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
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

### `8bcb7d16-9be0-40cc-9a9d-28b654997b8d::t6`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `role_correct`
- Current user: Yes, 'Virginia Woolf' is another excellent choice from Sadistik, really hits those deep, introspective notes. I'm clearly a big fan of his work. But I was hoping to branch out a little. Can you recommend any *different* artists, perhaps from the underground...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground hip hop"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip hop"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "different artists, perhaps from the underground hip-hop or alternative scene",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Different underground hip-hop or alternative artists known for similarly dark, introspective, storytelling-driven lyrics and atmospheric production."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Sadistik"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark introspective storytelling lyrics"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "atmospheric production"
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
        "value": "alternative"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Sadistik",
        "was_stale_in_trace": false
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
        "value": "underground"
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
        "value": "philosophical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "psychologically complex"
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
        "value": "introspective"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `role_correct`
- Current user: Yes, this is exactly the kind of sound I was looking for! "Welcome To Jamrock" is a classic. That definitely fits the "defined an era" vibe. Can you give me another track that has that timeless, era-defining feeling, maybe an old-school hip-hop gem this time?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "timeless"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "era-defining"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "old-school"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Damian Marley"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Welcome To Jamrock"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Damian Marley",
      "Welcome To Jamrock"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "another track that has that timeless, era-defining feeling, maybe an old-school hip-hop gem",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "An old-school hip-hop classic that has a timeless, era-defining feeling."
    },
    "entities": [
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Dendemann"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Nico Suave"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Illo"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Samy Deluxe"
      },
      {
        "role": "history",
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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

### `5ee0dbbc-c1d1-4bed-ba09-7dafeec198bc::t8`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `request_type_correct, role_correct`
- Current user: Dude, 'The Ultimate Showdown of Ultimate Destiny' is awesome! That song is a classic, the story is just so over-the-top and hilarious. You really crushed it with these meme and goofy song recommendations! Thanks! What else you got for me? Maybe something mo...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "chill"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip-hop"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip hop"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
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
      "request_type_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "What else you got for me? Maybe something mo...",
      "request_type": "unknown",
      "source_turn": 3,
      "summary": "The user praised the previous recommendations but was cut off mid-ask. The fragment suggests 'something mo...' which could be 'more of the same' or 'something more X'. Without a complete sentence, the intent is ambiguous."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Double Rainbow"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Beep Beep I'm a Sheep"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "The Ultimate Showdown of Ultimate Destiny"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Lemon Demon"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "meme and goofy"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "absurd story characters"
      }
    ],
    "rejections": [],
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
- Failed checks: `role_correct`
- Current user: That was a fantastic, energetic piece! The swing was just what I was looking for. I'm really getting a good sense of the range of classic jazz. To round out this exploration, could we try something that perhaps feels a bit more bluesy or soulful, but still...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic jazz"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazz"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "bluesy"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "something that perhaps feels a bit more bluesy or soulful, but still...",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "A classic jazz piece with a bluesy or soulful feel."
    },
    "entities": [
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Miles Davis"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Chet Baker"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Django Reinhardt"
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
        "role": "history",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "classic jazz"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
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

### `5861afef-85c0-4163-b8b9-5a11e308f352::t4`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `request_type_correct, role_correct`
- Current user: Yes, "Tic Tac" is super catchy and energetic! It's great to hear MC Lan with Lucas Lucco too. I'm finding some really good artists. Can you give me a few more diverse artists to check out, maybe with a slightly different take on that danceable or Latin sound?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "danceable"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Latin"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Brazilian Funk"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "MC WM"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "DENNIS"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "MC WM",
      "DENNIS"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "more diverse artists",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "More diverse artists with a danceable or Latin sound, possibly a slightly different take."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Latin"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "danceable"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "DENNIS"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Nego Bam"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "MC Nandinho"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Lucas Lucco"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "MC Lan"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "MC WM",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "DENNIS",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Lucas Lucco",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "MC Lan",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "danceable"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Latin"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Brazilian Funk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk carioca"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `role_correct`
- Current user: Oh, Flying Lotus! This is cool, it's got a really interesting mix of sounds. It's like electronic but also soulful, very unique. What else have you got that's really out there?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "unique"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "unexpected"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "out there"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Boards of Canada"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Aphex Twin"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Severed Heads"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Liu Fang"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Noriko Miyamoto"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Boards of Canada",
      "Aphex Twin",
      "Severed Heads",
      "Liu Fang",
      "Noriko Miyamoto"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "really out there",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Really out there, unique, unexpected music with an electronic yet soulful feel."
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
        "value": "really out there"
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
- Failed checks: `role_correct`
- Current user: This one has a cool electronic sound and it's definitely emotional. But I'm still looking for that really strong, direct "plea" or "begging" in the lyrics, like in "Iris," but for electronic songs. Do you have any tracks that really hit that direct lyrical...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "electronic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "indie-electronic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "indie electronic"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Men I Trust"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "The Goo Goo Dolls"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Men I Trust",
      "The Goo Goo Dolls"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "really strong, direct 'plea' or 'begging' in the lyrics",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Electronic tracks with strongly direct, pleading, begging lyrics, similar to the vibe of Men I Trust."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
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
        "value": "lyrical plea"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
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
- Failed checks: `temporal_semantics_correct`
- Current user: Oh, "IDGAF"! That's a good one, it was definitely super popular back then. Let me listen again... Hmm, it's not quite the one I'm thinking of, but it's really close in vibe! The one I'm remembering felt a bit more upbeat, maybe a bit more dancey.

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pop"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "upbeat"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dancey"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "hidden_target"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "hidden_target_search"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": [
        "style_era",
        "reference_era"
      ],
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "temporal_semantics_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "trying to remember",
      "request_type": "hidden_target",
      "source_turn": 2,
      "summary": "A popular pop song from 2015-2017 that was everywhere, upbeat and dancey, not IDGAF."
    },
    "entities": [
      {
        "role": "contrast",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "IDGAF"
      },
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Dua Lipa"
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
        "value": "2015-2017"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "soft",
        "value": "IDGAF"
      }
    ],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "release_date",
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
- Failed checks: `role_correct`
- Current user: Yeah, that Dead Prez track is fire! Super authentic and exactly the kind of vibe I'm into from that era. What else hits like that? Maybe some more underground stuff from the late 90s or early 2000s?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "90s"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip-hop"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip hop"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Mobb Deep"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Mobb Deep"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "What else hits like that? Maybe some more underground stuff from the late 90s or early 2000s?",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "More underground raw 90s/early 2000s hip-hop like Dead Prez's track."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Mobb Deep"
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
        "value": "raw"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground hip-hop"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1997,
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
- Failed checks: `request_type_correct, role_correct, retrieval_profile_correct`
- Current user: Yes! 'Finally' by CeCe Peniston! That's exactly the track I was trying to remember. Spot on! 'Finally' is it. Can you suggest other iconic 90s dance hits similar to this one?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "energetic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dance"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dance-pop"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "CeCe Peniston"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Finally"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "CeCe Peniston",
      "Finally"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "other iconic 90s dance hits similar to this one",
      "request_type": "similar_to_prior",
      "source_turn": 2,
      "summary": "Other iconic 90s dance hits similar to Finally by CeCe Peniston."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Finally"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "CeCe Peniston"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "90s dance"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
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
- Failed checks: `role_correct`
- Current user: Yes, this selection is great! "Wannabe" is iconic, it really gets me in a powerful mood. I think these are all perfect for what I asked for. What else do you have that's like these? Maybe some other pop artists from that same time?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "empowering"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "confident"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "high-energy"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Spice Girls"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Who Do You Think You Are"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Stop"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Holler"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Wannabe"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Spice Girls",
      "Who Do You Think You Are",
      "Stop",
      "Holler",
      "Wannabe"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "like these? Maybe some other pop artists from that same time",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Other pop artists from the early 2000s with confident, high-energy pop anthems."
    },
    "entities": [
      {
        "role": "contrast",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Stop"
      },
      {
        "role": "contrast",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Holler"
      },
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Spice Girls"
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
        "value": "confident"
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
        "value": "early 2000s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1998,
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
- Failed checks: `role_correct`
- Current user: Yes! "He's the Greatest Dancer" is such a jam! That's exactly the kind of funky, soulful sound from the late 70s I'm looking for. What else do you have from that golden era of R&B?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "R&B"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Soul"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funky"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Sister Sledge"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Sister Sledge"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "golden era of R&B",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "More funky, soulful late-70s golden-era R&B/Soul, excluding the already-played artists."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Sister Sledge"
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1977,
        1979
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
- Failed checks: `request_type_correct, role_correct, retrieval_profile_correct, temporal_semantics_correct`
- Current user: Unfortunately, 'Sleep Paralysis' is not what I'm looking for at all. The mood is too dark and harsh, not dreamy or serene like the late 2000s ambient electronic I'm trying to find. Also, the era is still off. I'm specifically looking for something with a wa...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ambient electronic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dreamy"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "atmospheric"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [
      "dark",
      "harsh",
      "spoken word"
    ],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "rejection_normalization_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct",
      "retrieval_profile_correct",
      "temporal_semantics_correct"
    ],
    "still_missing_checks": [
      "request_type_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "trying to find",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "Recall a specific late-2000s ambient electronic track that is instrumental, dreamy, serene, warm, evolving, with subtle rhythms and warm pads; not dark or harsh."
    },
    "entities": [
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Carl Sagan"
      },
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Sidewalks and Skeletons"
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
        "value": "warm evolving pads"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "dark harsh"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "Sleep Paralysis"
      }
    ],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
      "range": [
        2005,
        2010
      ],
      "strength": "hard"
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
- Failed checks: `role_correct`
- Current user: DMX is a beast! "Where The Hood At" is definitely a raw, aggressive banger and fits that dark, intense vibe perfectly. You nailed it with these last few tracks. Thanks for the awesome recommendations! Can you suggest another track that's just pure, unfilter...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "aggressive"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Jedi Mind Tricks"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Jedi Mind Tricks"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "another track that's just pure, unfiltered raw aggression, dark heavy production, and intense lyrics",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another track with pure, unfiltered raw aggression, dark heavy production, and intense lyrics; similar to the vibe of 'Butcher Knife Bloodbath' and 'Where The Hood At' but from any artist."
    },
    "entities": [
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
        "value": "horrorcore"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark heavy production"
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
        "value": "intense lyrics"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
- Failed checks: `request_type_correct, role_correct, target_artist_mode_correct, temporal_semantics_correct`
- Current user: Yes! "Blinded By The Lights" is exactly the track I was trying to recall! That's the one! You totally nailed it with that recommendation. Thanks so much! Now that you've found that one for me, can you recommend some other tracks that have a similar kind of...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "atmospheric"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "late-night"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "The Streets"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "The Streets"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "temporal_semantics_correct"
    ],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct",
      "target_artist_mode_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "some other tracks that have a similar kind of",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "Other tracks similar to Blinded By The Lights by The Streets."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "The Streets"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Blinded By The Lights"
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
- Failed checks: `role_correct, temporal_semantics_correct`
- Current user: Make My" is a strong track and Black Thought's lyrics are always on point, but I'm really trying to branch out from The Roots and Masta Ace for a bit. Can you definitely give me a narrative-driven track from a *different* classic 90s East Coast artist, like...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "narrative"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "storytelling"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "lyrical"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct",
      "temporal_semantics_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "different classic 90s East Coast artist",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "A narrative-driven track from a different classic 90s East Coast artist, not The Roots or Masta Ace."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "The Roots"
      },
      {
        "role": "rejected",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Masta Ace"
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
        "value": "90s"
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
        "value": "East Coast"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "The Roots"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Masta Ace"
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
- Failed checks: `role_correct, target_artist_mode_correct, temporal_semantics_correct`
- Current user: YES! That's 'Divano' by ERA! That's exactly the quintessential early 2000s sound I was searching for. You nailed it! Thank you so much! Can you suggest other instrumental tracks that have a similar epic or new-age feel?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "instrumental"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "epic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "new-age"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct",
      "target_artist_mode_correct",
      "temporal_semantics_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "other instrumental tracks that have a similar epic or new-age feel",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Other instrumental tracks with a similar epic or new-age feel from the early 2000s."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "ERA"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Divano"
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "same_artist",
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
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
- Failed checks: `role_correct`
- Current user: You're doing so well with Panic! At The Disco and the emotional vibe! "Always" is a great song, but it's still not the one that screams "mid-2000s emo phase" to me. The track I'm thinking of is definitely from their first album, "A Fever You Can't Sweat Out...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "mid-2000s"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "emo"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "pop-punk"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "hidden_target"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "hidden_target_search"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": [
        "style_era",
        "reference_era"
      ],
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "the track I'm thinking of is definitely from their first album, A Fever You Can't Sweat Out",
      "request_type": "hidden_target",
      "source_turn": 3,
      "summary": "Identify the specific Panic! At The Disco track from \"A Fever You Can't Sweat Out\" with lyrics about jealousy or a love triangle."
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
        "value": "jealousy or a love triangle"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "This Is Gospel"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "But It's Better If You Do"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "Always"
      }
    ],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "same_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2004,
        2006
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
- Failed checks: `role_correct, temporal_semantics_correct`
- Current user: I'm trying to remember a really powerful, orchestral song from the early 2000s, like something from a movie score.

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "powerful"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "orchestral"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "movie score"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "hidden_target"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "hidden_target_search"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [],
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": [
        "style_era",
        "reference_era"
      ],
      "strength": "soft"
    }
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct",
      "temporal_semantics_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "trying to remember a really powerful, orchestral song from the early 2000s",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "Find a powerful orchestral song from the early 2000s reminiscent of a movie score."
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
        "value": "early 2000s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": null
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

### `c4c0c288-dbcd-4970-ad52-901aafe91b88::t4`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `role_correct`
- Current user: These selections are spot on for that underground 90s hip-hop sound. Exactly what I wanted! What else is out there that I might like with a similar vibe, maybe from other artists but still with that golden age jazzy feel?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "golden age"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazzy"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazz-infused hip-hop"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "A Tribe Called Quest"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "A Tribe Called Quest"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "other artists",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Other artists with a similar golden age jazzy hip-hop vibe; Tribe Called Quest is satisfied."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "A Tribe Called Quest"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazzy hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "90s underground"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "golden age"
      }
    ],
    "rejections": [],
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
        "value": "A Tribe Called Quest",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "golden age"
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
        "value": "jazz-infused hip-hop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "jazz rap"
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
        "value": "underground"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "90s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
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

### `71bb177a-dab1-4bbc-8508-22d809b05c31::t6`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `request_type_correct, role_correct`
- Current user: Yes, Natalie Merchant is a great pick! 'Wonder' definitely fits that introspective and emotionally resonant style. Can you suggest another iconic female artist from the 90s who has a similar thoughtful, storytelling approach to their music?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "female artist"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "female vocalist"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "90s"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Alanis Morissette"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Alanis Morissette"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
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
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "suggest another iconic female artist from the 90s who has a similar thoughtful, storytelling approach",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Another iconic female artist from the 90s with a thoughtful, storytelling approach to their music."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Natalie Merchant"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Alanis Morissette"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "iconic female artist"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "thoughtful storytelling"
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
        "value": "90s"
      }
    ],
    "rejections": [],
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
        "value": "Alanis Morissette",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Natalie Merchant",
        "was_stale_in_trace": false
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
        "value": "female vocalist"
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
        "value": "introspective"
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
        "value": "storytelling"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
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

### `4d0afb6b-3705-493f-ab16-ca75ea311e1a::t7`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `role_correct`
- Current user: These Blade Runner 2049 tracks are fantastic, but I've heard quite a few from this album now. I'm really looking to discover *new* artists or different film scores that have that same dark, futuristic, and melancholic electronic instrumental vibe. Please, n...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "futuristic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "melancholic"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Hans Zimmer"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Benjamin Wallfisch"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Hans Zimmer"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Benjamin Wallfisch"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Blade Runner 2049"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Hans Zimmer",
      "Benjamin Wallfisch",
      "Blade Runner 2049"
    ],
    "hard_rejection_values": [
      "Hans Zimmer",
      "Benjamin Wallfisch",
      "Blade Runner 2049"
    ],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": true,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "new artists or different film scores",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "New artists or different film scores with a dark, futuristic, melancholic electronic instrumental vibe; no more Blade Runner 2049 soundtrack."
    },
    "entities": [
      {
        "role": "rejected",
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "Blade Runner 2049"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Hans Zimmer"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark futuristic melancholic electronic instrumental"
      }
    ],
    "rejections": [
      {
        "kind": "album",
        "scope": "hard",
        "value": "Blade Runner 2049"
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
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Hans Zimmer",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Benjamin Wallfisch",
        "was_stale_in_trace": true
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
        "value": "futuristic"
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
        "value": "electronic"
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
        "kind": "artist",
        "scope": "hard",
        "value": "Hans Zimmer"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Benjamin Wallfisch"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "2049"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "Rain"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "Wallace"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `1e14a07f-7369-4d24-9285-9343b6b18353::t8`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `role_correct`
- Current user: Uh, "Gladiatrix" is a bit too heavy and intense for what I'm looking for right now. I was hoping for something much more atmospheric and haunting, with ethereal vocals and traditional instruments, not so much the metal side. Can you find tracks that are mor...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "delicate"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "melancholic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ethereal"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Myrkur"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Myrkur"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [
      "heavy",
      "intense",
      "metal"
    ],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct",
      "rejection_normalization_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "more atmospheric and haunting",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Atmospheric and haunting dark folk or gothic folk with ethereal female vocals and traditional instruments, avoiding heavy metal elements."
    },
    "entities": [
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
        "value": "dark folk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "gothic folk"
      }
    ],
    "rejections": [
      {
        "kind": "style",
        "scope": "soft",
        "value": "heavy"
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "metal"
      }
    ],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Myrkur",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "delicate"
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
        "value": "ethereal"
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
        "value": "folk"
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
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "hard",
        "value": "heavy"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "intense"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "metal"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `d265b5a9-af57-4070-90f5-692a960c5aaa::t6`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `request_type_correct, role_correct, rejection_normalization_correct`
- Current user: Contact" is a classic, but I've listened to 'Random Access Memories' countless times. I'm really looking for *new album discoveries* from the 2010s, specifically electronic albums with covers that are just as striking or artistically unique as Daft Punk's,...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "electronic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2010s"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "striking cover art"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Four Tet"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Daft Punk"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Four Tet"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Four Tet",
      "Daft Punk"
    ],
    "hard_rejection_values": [
      "Daft Punk",
      "Four Tet"
    ],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": true,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "rejection_normalization_correct"
    ],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "new album discoveries from the 2010s, specifically electronic albums with covers that are just as striking or artistcail",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "New electronic albums from the 2010s with striking, artistically unique covers, beyond Random Access Memories and New Energy."
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
        "type": "album",
        "use_as_retrieval_seed": false,
        "value": "New Energy"
      },
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
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "electronic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "striking cover"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "artistically unique cover"
      }
    ],
    "rejections": [
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2010,
        2019
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
        "value": "Daft Punk",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Four Tet",
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
        "value": "2010s"
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
        "value": "unique cover art"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong visual identity"
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
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
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
- Failed checks: `role_correct`
- Current user: Yeah, "Revenga" is awesome! System Of A Down is always great. But I was really hoping for some *new* bands with that heavy, alternative metal sound. Do you have any bands that are similar in style to System Of A Down, but not them? I'm ready to discover som...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "alternative metal"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "metal"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "System Of A Down"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "System Of A Down"
    ],
    "hard_rejection_values": [
      "System Of A Down"
    ],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": true,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "new bands with that heavy, alternative metal sound",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "New bands similar to System Of A Down's heavy alternative metal style, but not System Of A Down."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Flying Lotus"
      },
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "System Of A Down"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy alternative metal"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "System Of A Down"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Flying Lotus"
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
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "System Of A Down",
        "was_stale_in_trace": false
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
        "value": "alternative metal"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "metal"
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
        "value": "powerful vocals"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "complex song structures"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intense"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "System Of A Down"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `d265b5a9-af57-4070-90f5-692a960c5aaa::t8`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `role_correct`
- Current user: Planet" is a good track, and Four Tet's 'New Energy' definitely has a distinct visual. But it seems like we're mostly circling back to these two artists. I was really hoping to discover some entirely new electronic albums from the 2010s with truly unique an...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "electronic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2010s"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "striking cover art"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Daft Punk"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Daft Punk"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Four Tet"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Daft Punk",
      "Four Tet"
    ],
    "hard_rejection_values": [
      "Daft Punk",
      "Four Tet"
    ],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": true,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "entirely new electronic albums from the 2010s with truly unique",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Entirely new electronic albums from the 2010s with truly unique, striking cover art from artists other than Daft Punk or Four Tet."
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2010,
        2019
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
        "value": "Daft Punk",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Four Tet",
        "was_stale_in_trace": false
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
        "value": "2010s"
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
        "value": "unique cover art"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "strong visual identity"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "abstract cover art"
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
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
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

### `3a4224d3-1e5b-4bb9-a424-886d5c45d5d3::t8`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `request_type_correct, retrieval_profile_correct, rejection_normalization_correct`
- Current user: I understand that your current selection is primarily rain-focused. Since forest and ocean sounds aren't available, could you perhaps recommend other ambient or New Age tracks by my favorite artist, Calmsound, or similar artists that are not rain-based? I'm...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Calmsound"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ambient"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "New Age"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "new age"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "same_artist"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "continuation"
    ],
    "soft_rejection_values": [
      "rain"
    ],
    "target_artist_mode": [
      "same_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "request_type_correct",
      "retrieval_profile_correct",
      "rejection_normalization_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "recommend other ambient or New Age tracks by my favorite artist, Calmsound",
      "request_type": "exact_artist",
      "source_turn": 3,
      "summary": "Ambient or New Age tracks by Calmsound or similar artists that are not rain-based."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Calmsound"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ambient"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "New Age"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "rain"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "hard",
        "value": "rain"
      }
    ],
    "retrieval_profile": "exact_probe",
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
        "value": "Calmsound",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "ambient"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "New Age"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "calming"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "soundscape"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "hard",
        "value": "rain"
      }
    ],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `rejection_normalization_correct`
- Current user: Man, I appreciate you trying to stick with Lupe Fiasco, but "Streets On Fire" is not a positive or uplifting track at all. It's actually really heavy and intense. I've been trying to get some hip-hop that has a *positive vibe* to boost my energy and put me...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip-hop"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip hop"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "positive"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [
      "heavy",
      "intense"
    ],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "rejection_normalization_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "hip-hop that has a *positive vibe* to boost my energy",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Positive, uplifting, energetic hip-hop to start the day. Not Lupe Fiasco tracks."
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
        "value": "uplifting energetic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Lupe Fiasco",
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
        "value": "positive"
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
        "value": "uplifting"
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
        "value": "good mood"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "hard",
        "value": "heavy"
      },
      {
        "kind": "tag",
        "scope": "hard",
        "value": "intense"
      }
    ],
    "retrieval_profile": "novelty",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `08bea603-846a-428b-aa27-de4dfede7ba9::t8`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `role_correct`
- Current user: L.U.V." is definitely interesting with those unique touches! But I'm really keen on discovering artists I *haven't* encountered yet. Do you have any other artists in your collection that are genuinely new to me and offer something experimental or avant-gard...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "experimental"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "avant-garde"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "unique"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Romare"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Julia Holter"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Vatican Shadow"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Robot Koch"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Romare",
      "Julia Holter",
      "Vatican Shadow",
      "Robot Koch"
    ],
    "hard_rejection_values": [
      "Romare",
      "Julia Holter",
      "Vatican Shadow",
      "Robot Koch"
    ],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": true,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "artists I haven't encountered yet",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Completely new artists, not yet encountered, with experimental or avant-garde sound design."
    },
    "entities": [
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Julia Holter"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Robot Koch"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Romare"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "experimental"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "avant-garde"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intricate sound design"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Julia Holter"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Robot Koch"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Romare"
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
        "value": "experimental"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "avant-garde"
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
        "value": "intricate sound design"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Romare"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Julia Holter"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Vatican Shadow"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Robot Koch"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `0fc60312-9a9d-4658-a950-06fc2441a2ac::t8`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `request_type_correct, role_correct, rejection_normalization_correct`
- Current user: While I appreciate getting a new artist, "Strange Weather" isn't quite what I'm looking for. It doesn't have the heavy, dark post-rock elements or the experimental electronic textures I'm after. I'm still searching for music that truly *fuses* those specifi...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "post-rock"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Have A Nice Life"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Julia Holter"
      },
      {
        "allowed_roles": [
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "David Byrne"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Have A Nice Life",
      "Julia Holter",
      "David Byrne"
    ],
    "hard_rejection_values": [
      "Julia Holter",
      "David Byrne"
    ],
    "notes": null,
    "request_type": [
      "new_artist"
    ],
    "requires_hard_rejection": true,
    "retrieval_profile": [
      "novelty"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "rejection_normalization_correct"
    ],
    "still_missing_checks": [
      "request_type_correct",
      "role_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "heavy, dark post-rock elements combined with experimental electronic textures",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "A track that fuses heavy, dark post-rock with experimental electronic textures, creating a desolate, immersive soundscape by a different/new artist."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heavy dark post-rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "experimental electronic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "desolate immersive soundscape"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "horns surrounding me"
      },
      {
        "kind": "tag",
        "scope": "soft",
        "value": "strange weather"
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
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Have A Nice Life",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "post-rock"
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
        "value": "atmospheric"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "experimental"
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
        "value": "ambient"
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Julia Holter"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "David Byrne"
      }
    ],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

### `3ebc2b49-0f5c-4161-bbcf-e1615821103f::t2`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `role_correct, target_artist_mode_correct, rejection_normalization_correct`
- Current user: This is a good start, and it definitely fits the Assassin's Creed vibe and artist. However, I'm looking for something that emphasizes the dramatic and exploratory orchestral elements more than direct combat. Could you suggest tracks with a similar epic feel...

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "epic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "adventurous"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "orchestral"
      },
      {
        "allowed_roles": [
          "satisfied",
          "history",
          "contrast",
          "rejected"
        ],
        "required": false,
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Jesper Kyd"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [
      "Jesper Kyd"
    ],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [
      "combat"
    ],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "target_artist_mode_correct"
    ],
    "still_missing_checks": [
      "role_correct",
      "rejection_normalization_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "emphasizes the dramatic and exploratory orchestral elements more than direct combat",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "Dramatic and exploratory orchestral game scores with an epic feel, similar to Assassin's Creed but emphasizing exploration over combat."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Jesper Kyd"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dramatic exploratory orchestral"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "epic"
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

### `bd2aa024-68e7-43c2-aa87-afce9b4d7cf1::t2`

- Pack: `POS_exact_entity_success_control`
- Failed checks: `role_correct`
- Current user: Yes, WALK THE MOON! That's the band I was thinking of! Do they have a really famous song that tells someone to "shut up and dance"?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "WALK THE MOON"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "alternative rock"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2010s"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "upbeat"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "hidden_target"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "hidden_target_search"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "tells someone to 'shut up and dance'",
      "request_type": "hidden_target",
      "source_turn": 2,
      "summary": "Find the famous WALK THE MOON song with lyrics about telling someone to 'shut up and dance'."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "WALK THE MOON"
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
        "value": "upbeat danceable"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "same_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2010,
        2019
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
        "value": "WALK THE MOON",
        "was_stale_in_trace": false
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
        "value": "2010s"
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
        "value": "danceable"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  }
}
```

### `737a65cf-9c45-4b1d-910d-2f1f1ef5eab7::t8`

- Pack: `POS_clean_final_hit_control`
- Failed checks: `role_correct`
- Current user: Yeah, "On Melancholy Hill" is a definite vibe! You got that right. What about a Gorillaz track with a more upbeat or quirky electronic feel, maybe something that's more instrumental-focused or from one of their newer albums like 'Cracker Island'?

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Gorillaz"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "upbeat"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "quirky"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "electronic"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "same_artist"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "same_artist"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct",
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "upbeat or quirky electronic feel, instrumental-focused, from Cracker Island",
      "request_type": "same_artist",
      "source_turn": 3,
      "summary": "A more upbeat or quirky electronic instrumental-focused Gorillaz track, possibly from 'Cracker Island' or newer albums."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Gorillaz"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Cracker Island"
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
        "value": "quirky"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "instrumental-focused"
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
        "value": "Gorillaz",
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
        "value": "quirky"
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
        "value": "instrumental"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "instrumental-focused"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  }
}
```

### `5b44bff3-76ed-495e-9dc1-0f075e3d178b::t1`

- Pack: `POS_clean_final_hit_control`
- Failed checks: `role_correct`
- Current user: I'd like to explore a musical journey, starting with some classic, melodic rock or folk from the 60s/70s, then gradually moving towards something more modern and alternative.

```json
{
  "desired_state_read": {
    "entities": [
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "melodic"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rock"
      },
      {
        "allowed_roles": [
          "current_target",
          "seed"
        ],
        "required": true,
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "folk"
      }
    ],
    "expected_check_source": "expected_state_checks",
    "forbidden_seed_values": [],
    "hard_rejection_values": [],
    "notes": null,
    "request_type": [
      "attribute_search"
    ],
    "requires_hard_rejection": false,
    "retrieval_profile": [
      "feature_search",
      "novelty",
      "continuation"
    ],
    "soft_rejection_values": [],
    "target_artist_mode": [
      "new_artist",
      "any_artist",
      "unknown"
    ],
    "temporal_constraint": null
  },
  "evaluation": {
    "captured_expected_info": false,
    "improved_checks": [
      "request_type_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [
      "role_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "starting with some classic, melodic rock or folk from the 60s/70s",
      "request_type": "attribute_search",
      "source_turn": 1,
      "summary": "Begin a musical journey with classic melodic rock or folk from the 60s/70s, then progress to modern alternative."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "melodic rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "folk"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1960,
        1979
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
        "value": "classic"
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
        "value": "rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "folk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "60s"
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
        "value": "modern"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "alternative"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1960,
        1979
      ],
      "strength": "soft"
    }
  }
}
```


Only the first 50 of 54 failures are shown.
