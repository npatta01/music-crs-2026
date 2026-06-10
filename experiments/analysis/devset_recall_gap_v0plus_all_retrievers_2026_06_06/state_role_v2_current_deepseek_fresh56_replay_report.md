# State Replay Extraction Report

- State source: `live`
- Model: `openrouter/deepseek/deepseek-v4-flash / prompt=current`
- Samples: `56`
- Overall all-pass rate: `0.464`
- New state captures expected information: `26/56`
- Improved vs previous trace state: `22/56`
- Regressed vs previous trace state: `5/56`

## Pack Results

| Pack | N | All Pass | Request Type | Role | Artist Mode | Profile | Temporal | Rejection | Positive Control |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_good_state_ranker_near_miss_failure | 5 | 0.200 | 1.000 | 0.800 | 0.400 | 0.200 | 1.000 | 1.000 | 1.000 |
| P0_named_artist_ranker_failure | 5 | 0.400 | 1.000 | 0.800 | 0.800 | 0.400 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 5 | 0.600 | 1.000 | 1.000 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 5 | 0.400 | 1.000 | 0.600 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 5 | 0.600 | 1.000 | 1.000 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 5 | 0.400 | 1.000 | 1.000 | 0.400 | 0.400 | 1.000 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 5 | 0.200 | 1.000 | 1.000 | 0.200 | 0.200 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 5 | 0.600 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.600 | 1.000 |
| P1_temporal_constraint_failure | 5 | 0.400 | 1.000 | 1.000 | 0.600 | 0.400 | 0.800 | 1.000 | 1.000 |
| POS_clean_final_hit_control | 5 | 0.200 | 1.000 | 1.000 | 0.200 | 0.200 | 1.000 | 1.000 | 0.200 |
| POS_exact_entity_success_control | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## State Change Evaluation

Each row compares the previous trace state snapshot against the new extracted state and the desired state contract for the replay example.

## Failures

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
          "confidence": 0.9,
          "evidence_text": "raw power and darkness, but maybe a bit more stripped-down or minimalistic",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "similar raw power and darkness",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "similar raw power and darkness, but maybe a bit more stripped-down or minimalistic in its approach, while still...",
      "request_type": "attribute_search",
      "source_turn": 5,
      "summary": "Something with raw power and darkness, but more stripped-down/minimalistic, still intense electronic energy."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw power and darkness"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "stripped-down minimalistic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "intense electronic energy"
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
          "evidence_text": "powerful rock songs, maybe with a really strong guitar riff",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "I love this song, it's so powerful",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "powerful rock songs, maybe with a really strong guitar riff",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "Powerful rock songs with a really strong guitar riff, from any era or artist."
    },
    "entities": [
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
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Big in Japan"
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
          "confidence": 0.95,
          "evidence_text": "other artists",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.5,
          "evidence_text": "popular Hip-Hop tracks",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "popular Hip-Hop tracks from other artists around late 2015 to early 2016",
      "request_type": "new_artist",
      "source_turn": 6,
      "summary": "Popular Hip-Hop tracks from other artists around late 2015 to early 2016, excluding Drake."
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
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "late 2015 to early 2016"
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
          "confidence": 1.0,
          "evidence_text": "play 'The Spirit of Radio' by Rush instead",
          "request_type": "exact_track"
        }
      ],
      "evidence_text": "play 'The Spirit of Radio' by Rush instead",
      "request_type": "exact_track",
      "source_turn": 7,
      "summary": "Play 'The Spirit of Radio' by Rush."
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

### `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `role_correct`
- Current user: Yes! Mr. Bungle! That's exactly the band I was trying to remember. "Violenza Domestica" is definitely a great example of their sound. Thanks! Now that we found them, what else could you recommend that has a similar experimental, genre-bending vibe, maybe wi...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Mr. Bungle"
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
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "similar experimental, genre-bending vibe",
          "request_type": "similar_to_prior"
        },
        {
          "confidence": 0.65,
          "evidence_text": "unique vocalists",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.5,
          "evidence_text": "what else",
          "request_type": "new_artist"
        }
      ],
      "evidence_text": "similar experimental, genre-bending vibe, maybe with some really unique vocalists",
      "request_type": "similar_to_prior",
      "source_turn": 3,
      "summary": "Similar experimental, genre-bending, avant-garde vibe with unique vocalists, inspired by Mr. Bungle but not necessarily same artist."
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
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Violenza Domestica"
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
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Faith No More"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
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
          "evidence_text": "well-known, popular, positive energy, regardless of genre",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "these are exactly the kind",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "well-known songs that are popular and have a great, positive energy, regardless of genre, as long as they're not too nic",
      "request_type": "attribute_search",
      "source_turn": 6,
      "summary": "Well-known, feel-good, popular songs with great positive energy, regardless of genre, not too niche."
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
        "value": "not too niche"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Michael Jackson"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Whitney Houston"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Justin Timberlake"
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
          "confidence": 0.95,
          "evidence_text": "not quite the one I'm thinking of, but really close in vibe",
          "request_type": "hidden_target"
        },
        {
          "confidence": 0.25,
          "evidence_text": "more upbeat, maybe a bit more dancey",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "not quite the one I'm thinking of, but close in vibe; more upbeat, more dancey",
      "request_type": "hidden_target",
      "source_turn": 2,
      "summary": "A popular pop song from 2015-2017, more upbeat and dancey than IDGAF by Dua Lipa."
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
        "value": "popular"
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
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "soft",
        "value": "IDGAF"
      },
      {
        "kind": "artist",
        "scope": "soft",
        "value": "Dua Lipa"
      }
    ],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "any_artist",
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

### `f2d85aa5-2086-4b1e-9974-d188c43621db::t8`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct, temporal_semantics_correct`
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
        "value": "evolving"
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
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
      "range": [
        2007,
        2009
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

### `a33a5df0-2c2b-429c-84e6-cde28affd4d5::t6`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `retrieval_profile_correct`
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
    "regressed_checks": [],
    "still_missing_checks": [
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "definitely from their first album, A Fever You Can't Sweat Out",
          "request_type": "hidden_target"
        },
        {
          "confidence": 0.05,
          "evidence_text": "super dramatic, theatrical sound and a really iconic, anthemic chorus",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "definitely from their first album, A Fever You Can't Sweat Out",
      "request_type": "hidden_target",
      "source_turn": 6,
      "summary": "Find the specific mid-2000s Panic! At The Disco track from A Fever You Can't Sweat Out with dramatic theatrical vocals, driving rhythm, and an anthemic chorus about something intense."
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
        "value": "dramatic theatrical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "anthemic chorus"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "driving rhythm"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "mid-2000s emo"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "same_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2004,
        2008
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
          "evidence_text": "powerful orchestral song",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "trying to remember a really powerful, orchestral song from the early 2000s, like something from a movie score",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "Find a powerful orchestral song from the early 2000s that sounds like a movie score."
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
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "like a movie score"
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

### `1e14a07f-7369-4d24-9285-9343b6b18353::t8`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `rejection_normalization_correct`
- Current user: Uh, "Gladiatrix" is a bit too heavy and intense for what I'm looking for right now. I was hoping for something much more atmospheric and haunting, with ethereal vocals and traditional instruments, not so much the metal side. Can you find tracks that are mor...

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
          "confidence": 0.9,
          "evidence_text": "atmospheric and haunting, with ethereal vocals and traditional instruments",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "similar strong female presence",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "more atmospheric and haunting, with ethereal vocals and traditional instruments, not so much the metal side",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "Atmospheric, haunting, delicate, melancholic, ethereal dark folk with traditional instruments and ethereal vocals, not heavy or metal."
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
        "value": "ethereal vocals"
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
        "value": "metal side"
      }
    ],
    "retrieval_profile": "feature_search",
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

### `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `rejection_normalization_correct`
- Current user: Man, I appreciate you trying to stick with Lupe Fiasco, but "Streets On Fire" is not a positive or uplifting track at all. It's actually really heavy and intense. I've been trying to get some hip-hop that has a *positive vibe* to boost my energy and put me...

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
        "value": "uplifting"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "heavy and intense"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
        "value": "thoughtful"
      },
      {
        "role": "rejected",
        "type": "tag",
        "use_as_retrieval_seed": false,
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
    "retrieval_profile": "feature_search",
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
          "confidence": 0.95,
          "evidence_text": "new artist who makes Latin Pop",
          "request_type": "new_artist"
        },
        {
          "confidence": 0.5,
          "evidence_text": "Latin Pop with a strong beat",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "new artist who makes Latin Pop, maybe with a strong beat",
      "request_type": "new_artist",
      "source_turn": 7,
      "summary": "Another new artist in Latin Pop with a strong beat, not Golpe a Golpe or Alejandro Fernández."
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
      }
    ],
    "rejections": [
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Golpe a Golpe"
      },
      {
        "kind": "artist",
        "scope": "hard",
        "value": "Alejandro Fernández"
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
- Failed checks: `retrieval_profile_correct`
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
    "improved_checks": [
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.9,
          "evidence_text": "Soundgarden at all? Like, not even Rusty Cage?",
          "request_type": "exact_artist"
        },
        {
          "confidence": 0.7,
          "evidence_text": "how about something by Stone Temple Pilots or Nirvana?",
          "request_type": "exact_artist"
        }
      ],
      "evidence_text": "Soundgarden at all? Like, not even Rusty Cage? If not, how about something by Stone Temple Pilots or Nirvana?",
      "request_type": "exact_artist",
      "source_turn": 6,
      "summary": "Soundgarden track, or if not available, Stone Temple Pilots or Nirvana."
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
      },
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
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

### `fc78453a-8798-4402-a01a-e9c557f08a03::t2`

- Pack: `P0_named_artist_ranker_failure`
- Failed checks: `retrieval_profile_correct`
- Current user: That's a nice one, but I'm really looking to explore her earlier work. Do you have anything from her first album, "Natalia Lafourcade"?

```json
{
  "desired_state_read": {
    "current_target_entities": [
      {
        "role": "current_target",
        "source": "current_user_turn",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Natalia Lafourcade"
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
    "regressed_checks": [],
    "still_missing_checks": [
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "her first album, 'Natalia Lafourcade'",
          "request_type": "exact_album"
        }
      ],
      "evidence_text": "her first album, 'Natalia Lafourcade'",
      "request_type": "exact_album",
      "source_turn": 2,
      "summary": "A track from Natalia Lafourcade's first album 'Natalia Lafourcade'."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Natalia Lafourcade"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Natalia Lafourcade"
      }
    ],
    "rejections": [],
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
        "value": "Natalia Lafourcade",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early work"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "first album"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
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
          "request_type": "exact_album"
        },
        {
          "confidence": 0.5,
          "evidence_text": "Eliza's character development or her relationship with Alexander",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "songs from Hamilton that really showcase Eliza's character development or her relationship with Alexander",
      "request_type": "exact_album",
      "source_turn": 4,
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
        "value": "Eliza's character development"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Eliza's relationship with Alexander"
      }
    ],
    "rejections": [],
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
          "confidence": 0.9,
          "evidence_text": "vivid storytelling that almost feel like watching a movie",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.3,
          "evidence_text": "Kendrick really goes in",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "vivid storytelling that almost feel like watching a movie, where the details are super clear",
      "request_type": "attribute_search",
      "source_turn": 8,
      "summary": "Hip-hop tracks with vivid storytelling that feels like watching a movie, with super clear details."
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
        "value": "watching a movie"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "super clear details"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kendrick Lamar"
      },
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
        "value": "Kid Cudi"
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
          "confidence": 0.9,
          "evidence_text": "groove but still chill R&B",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "similar to this",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "something with a bit more of a groove but still chill R&B",
      "request_type": "attribute_search",
      "source_turn": 5,
      "summary": "Chill R&B with a bit more groove, similar to the smooth vibe of Talk 2 U by Brent Faiyaz."
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

### `2bbc0a7e-3ab0-4376-8135-182cd4ae075f::t1`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: I'm trying to remember a Latin Pop song from around the early 2000s, it was quite a hit back then.

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
          "evidence_text": "trying to remember",
          "request_type": "hidden_target"
        },
        {
          "confidence": 0.3,
          "evidence_text": "Latin Pop, early 2000s, hit",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "trying to remember a Latin Pop song from around the early 2000s, it was quite a hit back then",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "Find a Latin Pop song from the early 2000s that was a hit back then."
    },
    "entities": [
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
        "value": "hit back then"
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
        "value": "Latin pop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hit"
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

### `dd686049-59ba-439b-8c51-949a0876e1b3::t1`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: I'm looking for a really intense electronic song, something that makes you feel like you're speeding through a cyberpunk city at night.

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
          "confidence": 0.95,
          "evidence_text": "intense electronic song, cyberpunk city at night",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.1,
          "evidence_text": "makes you feel like",
          "request_type": "hidden_target"
        }
      ],
      "evidence_text": "speeding through a cyberpunk city at night",
      "request_type": "attribute_search",
      "source_turn": 1,
      "summary": "Intense electronic song with a cyberpunk city at night feel."
    },
    "entities": [
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
        "value": "intense"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "speeding through a cyberpunk city at night"
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
        "value": "intense"
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
        "value": "cyberpunk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "night"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "fast"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "driving"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dark"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  }
}
```

### `a8df96e2-c196-462c-9484-72aa093aedf4::t1`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: I'm trying to remember a Christian song, it had a really encouraging message, maybe by a male artist?

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
          "evidence_text": "trying to remember",
          "request_type": "hidden_target"
        },
        {
          "confidence": 0.3,
          "evidence_text": "encouraging message",
          "request_type": "attribute_search"
        }
      ],
      "evidence_text": "trying to remember a Christian song, it had a really encouraging message, maybe by a male artist?",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "Find a Christian song with an encouraging message, possibly by a male artist."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Christian"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "encouraging message"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "male artist"
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
        "value": "Christian"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "gospel"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "encouraging"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "inspirational"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "male vocalist"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  }
}
```

### `5a0dfe9d-ec8a-4449-97df-35535cbf162f::t1`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: Play something epic and orchestral, like a movie soundtrack, for background music.

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
          "evidence_text": "epic and orchestral, like a movie soundtrack",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.1,
          "evidence_text": "no prior track",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "epic and orchestral, like a movie soundtrack, for background music",
      "request_type": "attribute_search",
      "source_turn": 1,
      "summary": "Epic orchestral movie-soundtrack-style background music."
    },
    "entities": [
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
        "value": "movie soundtrack"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "background music"
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
        "value": "movie soundtrack"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "soundtrack"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "background music"
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
    "temporal_constraint": null
  }
}
```

### `be88097f-b6b0-4fb4-bed9-857a92a733c0::t3`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
- Current user: Baker Street" is a classic, but I'm really looking for tracks where the *guitar* is the star, specifically with intricate or smooth solos like the one in "Reelin' In The Years." Any other ideas for 70s rock songs with killer guitar work?

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Steely Dan"
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
    "entities": [
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Reelin' In The Years"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Steely Dan"
      },
      {
        "role": "rejected",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Baker Street"
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
        "value": "intricate guitar solo"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "smooth guitar solo"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
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
    "retrieval_profile": "feature_search",
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
        "value": "Steely Dan",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Reelin' In The Years",
        "was_stale_in_trace": false
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
        "value": "rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "guitar"
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
        "value": "solo"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "prominent guitar"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
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

### `2db3ddc8-78a1-412c-a71e-e0d748aab0e7::t2`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: That's a fantastic start! 'Night Moves' is exactly what I had in mind. Can you recommend some more tracks from artists with that same distinctive 70s rock sound and lyrical depth, perhaps from someone like John Fogerty or Bruce Springsteen?

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
        "value": "Bob Seger"
      },
      {
        "mentioned_current_turn": false,
        "role": "history",
        "use_as_retrieval_seed": false,
        "value": "Eagles"
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
          "evidence_text": "same distinctive 70s rock sound and lyrical depth",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.4,
          "evidence_text": "same distinctive",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "same distinctive 70s rock sound and lyrical depth, perhaps from someone like John Fogerty or Bruce Springsteen",
      "request_type": "attribute_search",
      "source_turn": 2,
      "summary": "More tracks with classic 70s rock sound and lyrical depth, referencing John Fogerty or Bruce Springsteen as style anchors."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Bob Seger"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "John Fogerty"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Bruce Springsteen"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "70s rock"
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
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Night Moves"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
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
        "value": "Bob Seger",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Eagles",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "John Fogerty",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Bruce Springsteen",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic rock"
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
        "value": "70s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "raw"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": null,
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

### `b4ffa800-8173-4f16-800a-4b5e765d7f80::t4`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Failed checks: `retrieval_profile_correct`
- Current user: Oh, that's not from Abbey Road either! Can you *please* play something from Abbey Road? How about 'Here Comes the Sun' from that album?

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
        "value": "The Beatles"
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
    "regressed_checks": [],
    "still_missing_checks": [
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "How about 'Here Comes the Sun' from that album?",
          "request_type": "exact_track"
        },
        {
          "confidence": 0.4,
          "evidence_text": "play something from Abbey Road",
          "request_type": "exact_album"
        }
      ],
      "evidence_text": "play something from Abbey Road? How about 'Here Comes the Sun' from that album?",
      "request_type": "exact_track",
      "source_turn": 4,
      "summary": "Play 'Here Comes the Sun' from Abbey Road by The Beatles."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Here Comes the Sun"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Abbey Road"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "The Beatles"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "I Want You (She's So Heavy)"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "Come Together"
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
        "value": "The Beatles",
        "was_stale_in_trace": true
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Here Comes the Sun",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "classic rock"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "rock"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "hard",
        "value": "P.S. I Love You"
      },
      {
        "kind": "track",
        "scope": "hard",
        "value": "Happiness Is A Warm Gun"
      }
    ],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  }
}
```

### `c4c0c288-dbcd-4970-ad52-901aafe91b88::t1`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct`
- Current user: I'm looking for some classic jazz-infused hip-hop, stuff popular with underground fans from the early 90s, like A Tribe Called Quest.

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
        1994
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
          "confidence": 0.8,
          "evidence_text": "jazz-infused hip-hop, popular with underground fans from the early 90s",
          "request_type": "attribute_search"
        },
        {
          "confidence": 0.5,
          "evidence_text": "like A Tribe Called Quest",
          "request_type": "similar_to_prior"
        }
      ],
      "evidence_text": "jazz-infused hip-hop, popular with underground fans from the early 90s, like A Tribe Called Quest",
      "request_type": "attribute_search",
      "source_turn": 1,
      "summary": "Classic jazz-infused hip-hop popular with underground fans from the early 90s, like A Tribe Called Quest."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "A Tribe Called Quest"
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
        "value": "popular with underground fans"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 90s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1994
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
        "was_stale_in_trace": false
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
        "value": "hip hop"
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
        "value": "classic"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 90s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1990,
        1994
      ],
      "strength": "soft"
    }
  }
}
```

### `55388720-92b7-4972-9bb2-beb37c33c86b::t1`

- Pack: `POS_clean_final_hit_control`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct, positive_control_preserved`
- Current user: Play 'Ivy' by Frank Ocean from 2016.

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
      "retrieval_profile_correct",
      "positive_control_preserved"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 1.0,
          "evidence_text": "Play 'Ivy' by Frank Ocean",
          "request_type": "exact_track"
        }
      ],
      "evidence_text": "Play 'Ivy' by Frank Ocean from 2016.",
      "request_type": "exact_track",
      "source_turn": 1,
      "summary": "Play 'Ivy' by Frank Ocean from 2016."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Ivy"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Frank Ocean"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "2016"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
      "range": [
        2016,
        2016
      ],
      "strength": "hard"
    }
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Ivy",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Frank Ocean",
        "was_stale_in_trace": false
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        2016,
        2016
      ],
      "strength": "soft"
    }
  }
}
```

### `93199894-d3db-4335-8278-e1be175944e4::t1`

- Pack: `POS_clean_final_hit_control`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct, positive_control_preserved`
- Current user: Can you put on "Even Flow" by Pearl Jam?

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
      "retrieval_profile_correct",
      "positive_control_preserved"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [],
      "evidence_text": "Even Flow by Pearl Jam",
      "request_type": "exact_track",
      "source_turn": 1,
      "summary": "Play Even Flow by Pearl Jam."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Even Flow"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Pearl Jam"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Even Flow",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Pearl Jam",
        "was_stale_in_trace": false
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "unknown",
    "temporal_constraint": null
  }
}
```

### `a9b423bf-d05c-418d-98af-2a3b1e1d7917::t1`

- Pack: `POS_clean_final_hit_control`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct, positive_control_preserved`
- Current user: Play the classic Ice Cube song from the 90s that starts with "Just wakin' up in the morning, gotta thank God".

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
      "retrieval_profile_correct",
      "positive_control_preserved"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 0.95,
          "evidence_text": "starts with 'Just wakin' up in the morning, gotta thank God'",
          "request_type": "hidden_target"
        }
      ],
      "evidence_text": "starts with 'Just wakin' up in the morning, gotta thank God'",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "Find the classic Ice Cube song from the 90s that starts with 'Just wakin' up in the morning, gotta thank God'."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Ice Cube"
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
        "value": "Just wakin' up in the morning, gotta thank God"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "same_artist",
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
        "value": "Ice Cube",
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
        "value": "hip hop"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
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
  }
}
```

### `5080d5a0-336e-4bd1-b5bc-4cc611983429::t1`

- Pack: `POS_clean_final_hit_control`
- Failed checks: `target_artist_mode_correct, retrieval_profile_correct, positive_control_preserved`
- Current user: Play Michael Jackson's 'Rock with You' from his 1979 album 'Off the Wall'.

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
      "retrieval_profile_correct",
      "positive_control_preserved"
    ]
  },
  "new_state_read": {
    "current_request": {
      "candidate_types": [
        {
          "confidence": 1.0,
          "evidence_text": "Play Michael Jackson's 'Rock with You'",
          "request_type": "exact_track"
        }
      ],
      "evidence_text": "Play Michael Jackson's 'Rock with You' from his 1979 album 'Off the Wall'",
      "request_type": "exact_track",
      "source_turn": 1,
      "summary": "Play Michael Jackson's 'Rock with You' from 'Off the Wall'."
    },
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Michael Jackson"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Rock with You"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Off the Wall"
      }
    ],
    "rejections": [],
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
        "value": "Michael Jackson",
        "was_stale_in_trace": false
      },
      {
        "role": "history",
        "type": "unknown",
        "use_as_retrieval_seed": false,
        "value": "Rock with You",
        "was_stale_in_trace": false
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "unknown",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "style_era",
      "range": [
        1979,
        1979
      ],
      "strength": "soft"
    }
  }
}
```

