# State Replay Extraction Report

- State source: `live`
- Model: `openrouter/deepseek/deepseek-v4-flash / prompt=current`
- Samples: `20`
- Overall all-pass rate: `0.550`
- New state captures expected information: `11/20`
- Improved vs previous trace state: `12/20`
- Regressed vs previous trace state: `2/20`

## Pack Results

| Pack | N | All Pass | Request Type | Role | Artist Mode | Profile | Temporal | Rejection | Positive Control |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_named_artist_ranker_failure | 2 | 0.500 | 1.000 | 1.000 | 1.000 | 0.500 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 1 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| P0_novelty_prior_anchor_failure | 3 | 0.333 | 1.000 | 0.667 | 0.333 | 0.333 | 1.000 | 1.000 | 1.000 |
| P0_roleless_stale_entity_failure | 5 | 0.800 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.800 | 1.000 |
| P0_same_album_ranker_failure | 4 | 0.500 | 1.000 | 0.750 | 0.750 | 0.500 | 1.000 | 1.000 | 1.000 |
| P1_positive_tag_retrieval_gap_failure | 1 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| P1_temporal_constraint_failure | 1 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |

## State Change Evaluation

Each row compares the previous trace state snapshot against the new extracted state and the desired state contract for the replay example.

## Failures

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
    "retrieval_profile": "hidden_target_search",
    "target_artist_mode": "any_artist",
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
      "evidence_text": "really vivid storytelling that almost feel like watching a movie",
      "request_type": "attribute_search",
      "source_turn": 3,
      "summary": "Tracks with vivid storytelling that feels like watching a movie, with super clear details."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "track",
        "use_as_retrieval_seed": false,
        "value": "DNA."
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
        "value": "Kid Cudi"
      },
      {
        "role": "history",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Kevin Gates"
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
        "value": "super clear details"
      }
    ],
    "rejections": [],
    "retrieval_profile": "feature_search",
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

### `c863175a-bbaf-4f6c-aef7-cb16f2792cb5::t6`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `role_correct, retrieval_profile_correct`
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
    "improved_checks": [
      "target_artist_mode_correct"
    ],
    "new_all_pass": false,
    "previous_all_pass": false,
    "regressed_checks": [],
    "still_missing_checks": [
      "role_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
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
      }
    ],
    "rejections": [],
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
      "evidence_text": "trying to remember a Latin Pop song",
      "request_type": "hidden_target",
      "source_turn": 1,
      "summary": "A half-remembered Latin Pop song from around the early 2000s that was a hit."
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

### `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4`

- Pack: `P0_roleless_stale_entity_failure`
- Failed checks: `rejection_normalization_correct`
- Current user: Suffocation is always a solid listen, but I'm really looking to discover some *new* bands. Can you suggest some more recent acts that are making waves in the technical or progressive death metal scene? I'm open to anything that's pushing the envelope.

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
    "regressed_checks": [
      "rejection_normalization_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": {
      "evidence_text": "discover some new bands",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "New, more recent bands in the technical or progressive death metal scene that are pushing the envelope."
    },
    "entities": [
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Suffocation"
      },
      {
        "role": "satisfied",
        "type": "artist",
        "use_as_retrieval_seed": false,
        "value": "Brain Drill"
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
        "value": "recent"
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
        null
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
      "evidence_text": "popular Hip-Hop tracks from other artists",
      "request_type": "new_artist",
      "source_turn": 3,
      "summary": "Popular hip-hop hits from other artists, late 2015 to early 2016 period, no more Drake."
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
      "evidence_text": "play 'The Spirit of Radio' by Rush instead",
      "request_type": "exact_track",
      "source_turn": 3,
      "summary": "Play 'The Spirit of Radio' by Rush instead of the problematic 'Tom Sawyer'."
    },
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
      },
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

