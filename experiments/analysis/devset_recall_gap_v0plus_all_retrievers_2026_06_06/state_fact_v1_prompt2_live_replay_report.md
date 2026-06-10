# State Replay Extraction Report

- State source: `live`
- Model: `openrouter/deepseek/deepseek-v4-flash / prompt=current`
- Samples: `56`
- Overall all-pass rate: `0.429`
- New state captures expected information: `24/56`
- Improved vs previous trace state: `16/56`
- Regressed vs previous trace state: `10/56`

## Pack Results

| Pack | N | All Pass | Role | Artist Mode | Profile | Temporal | Rejection | Positive Control |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_good_state_ranker_near_miss_failure | 5 | 0.200 | 1.000 | 0.800 | 0.400 | 1.000 | 1.000 | 1.000 |
| P0_named_artist_ranker_failure | 5 | 0.600 | 0.800 | 0.600 | 0.600 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 5 | 0.800 | 1.000 | 0.800 | 0.800 | 1.000 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 5 | 0.200 | 0.600 | 0.600 | 0.600 | 0.800 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 5 | 0.600 | 1.000 | 0.800 | 0.600 | 1.000 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 5 | 0.200 | 0.600 | 0.200 | 0.200 | 1.000 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 5 | 0.000 | 1.000 | 0.200 | 0.000 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 5 | 0.600 | 1.000 | 1.000 | 1.000 | 1.000 | 0.600 | 1.000 |
| P1_temporal_constraint_failure | 5 | 0.200 | 1.000 | 0.600 | 0.200 | 0.800 | 1.000 | 1.000 |
| POS_clean_final_hit_control | 5 | 0.200 | 1.000 | 0.200 | 0.200 | 1.000 | 1.000 | 0.200 |
| POS_exact_entity_success_control | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## State Change Evaluation

Each row compares the previous trace state snapshot against the new extracted state and the desired state contract for the replay example.

## Failures

### `78cdaccb-0f9b-4876-80b1-c20bf0b444e6::t8`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `retrieval_profile_correct`
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
      "role_correct",
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
    "previous_all_pass": true,
    "regressed_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
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
        "value": "angsty"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "early 2000s"
      }
    ],
    "rejections": [
      {
        "kind": "tag",
        "scope": "soft",
        "value": "heavier"
      }
    ],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
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
        "value": "pop punk"
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
        2004
      ],
      "strength": "soft"
    }
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
      "kind": "style_era",
      "range": [
        2015,
        2016
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
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
        "value": "hip-hop"
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
    "target_artist_mode": "new_artist",
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
    "entities": [
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
      },
      {
        "role": "rejected",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Tom Sawyer"
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
    "improved_checks": [],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Mr. Bungle"
      },
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Violenza Domestica"
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
        "value": "theatrical avant-garde vocals"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  }
}
```

### `5f085552-b56b-440e-830b-b4e40b58f854::t6`

- Pack: `P0_novelty_prior_anchor_failure`
- Failed checks: `temporal_semantics_correct`
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
    "previous_all_pass": true,
    "regressed_checks": [
      "temporal_semantics_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "entities": [
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
        "value": "rousing sing-along"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
      "range": [
        1990,
        2005
      ],
      "strength": "hard"
    }
  },
  "previous_state_read": {
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": {
      "apply_as_filter": true,
      "kind": "release_date",
      "range": [
        2015,
        2017
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
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
- Failed checks: `schema_valid, target_artist_mode_correct, retrieval_profile_correct, temporal_semantics_correct`
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
      "schema_valid",
      "temporal_semantics_correct"
    ],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "entities": [],
    "rejections": [],
    "retrieval_profile": null,
    "target_artist_mode": null,
    "temporal_constraint": null
  },
  "previous_state_read": {
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
        "value": "mid-2000s"
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
        "value": "emo angst breakup"
      }
    ],
    "rejections": [
      {
        "kind": "track",
        "scope": "soft",
        "value": "This Is Gospel"
      },
      {
        "kind": "track",
        "scope": "soft",
        "value": "But It's Better If You Do"
      },
      {
        "kind": "track",
        "scope": "soft",
        "value": "Always"
      }
    ],
    "retrieval_profile": "hidden_target_search",
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
  },
  "previous_state_read": {
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

### `71bb177a-dab1-4bbc-8508-22d809b05c31::t6`

- Pack: `P1_temporal_constraint_failure`
- Failed checks: `retrieval_profile_correct`
- Current user: Yes, Natalie Merchant is a great pick! 'Wonder' definitely fits that introspective and emotionally resonant style. Can you suggest another iconic female artist from the 90s who has a similar thoughtful, storytelling approach to their music?

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
    "previous_all_pass": true,
    "regressed_checks": [
      "retrieval_profile_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Alanis Morissette"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Natalie Merchant"
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
        "value": "1990s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "thoughtful, storytelling"
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
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
    "entities": [
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "atmospheric dark folk"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "gothic folk"
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
        "value": "haunting"
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
        "value": "metal"
      }
    ],
    "rejections": [
      {
        "kind": "style",
        "scope": "soft",
        "value": "metal"
      },
      {
        "kind": "style",
        "scope": "soft",
        "value": "heavy"
      }
    ],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
    "entities": [
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Lupe Fiasco"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "positive, uplifting, energetic"
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
        "scope": "soft",
        "value": "Lupe Fiasco"
      }
    ],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
        "value": "hip hop"
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
    "target_artist_mode": "new_artist",
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
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct",
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Golpe a Golpe"
      },
      {
        "role": "history",
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
    "regressed_checks": [
      "target_artist_mode_correct"
    ],
    "still_missing_checks": [
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
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
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  }
}
```

### `71b80ec3-6cca-48b4-b471-08efa00afa2d::t4`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `role_correct, target_artist_mode_correct, retrieval_profile_correct`
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
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Lin-Manuel Miranda"
      },
      {
        "role": "current_target",
        "type": "album",
        "use_as_retrieval_seed": true,
        "value": "Hamilton: An American Musical"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "character development of Eliza"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Eliza relationship with Alexander"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
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
        "value": "movie-like"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "dense narrative"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
    "regressed_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
    "regressed_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ],
    "still_missing_checks": [
      "role_correct"
    ]
  },
  "new_state_read": {
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
        "value": "storytelling about relationships and connection"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "deep introspective"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
        "value": "hip hop"
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
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
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
        "value": "hit"
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
        "value": "cyberpunk city at night"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
        "value": "encouraging"
      },
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "male"
      }
    ],
    "rejections": [],
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
        "value": "cinematic"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "any_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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

### `1c567917-f931-4609-9695-a9c0f8e39f3d::t2`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Failed checks: `retrieval_profile_correct`
- Current user: That's a good start! Anitta is definitely on point for contemporary pop. What about something more recent and upbeat, specifically from the 'tecno brega' or 'funk carioca' scenes?

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
      "retrieval_profile_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Anitta"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "tecno brega"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "funk carioca"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "upbeat"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Anitta",
        "was_stale_in_trace": false
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "Brazilian"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "contemporary"
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
        "value": "pop"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "recent"
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
        "value": "tecno brega"
      }
    ],
    "rejections": [],
    "retrieval_profile": "novelty",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  }
}
```

### `be88097f-b6b0-4fb4-bed9-857a92a733c0::t3`

- Pack: `P0_good_state_ranker_near_miss_failure`
- Failed checks: `retrieval_profile_correct`
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
    "improved_checks": [
      "role_correct",
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
    "entities": [
      {
        "role": "contrast",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "Reelin' In The Years"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Steely Dan"
      },
      {
        "role": "contrast",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Gerry Rafferty"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "guitar solo intricate smooth"
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
        "value": "1970s"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
    "target_artist_mode": "new_artist",
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
- Failed checks: `target_artist_mode_correct`
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
    "improved_checks": [
      "retrieval_profile_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "target_artist_mode_correct"
    ]
  },
  "new_state_read": {
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
        "value": "70s rock sound"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "lyrical depth"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": "new_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
    "target_artist_mode": "new_artist",
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
    "entities": [
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
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Here Comes the Sun"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
- Failed checks: `retrieval_profile_correct`
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
        "value": "early 90s"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "underground"
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
        1995
      ],
      "strength": "soft"
    }
  },
  "previous_state_read": {
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
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": {
      "apply_as_filter": false,
      "kind": "release_date",
      "range": [
        null,
        2016
      ],
      "strength": "hard"
    }
  },
  "previous_state_read": {
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
    "entities": [
      {
        "role": "current_target",
        "type": "artist",
        "use_as_retrieval_seed": true,
        "value": "Pearl Jam"
      },
      {
        "role": "current_target",
        "type": "track",
        "use_as_retrieval_seed": true,
        "value": "Even Flow"
      }
    ],
    "rejections": [],
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
    "retrieval_profile": "exact_probe",
    "target_artist_mode": "same_artist",
    "temporal_constraint": null
  },
  "previous_state_read": {
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
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "hip-hop"
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

