# State Replay Extraction Report

- State source: `live`
- Model: `openrouter/anthropic/claude-sonnet-4.6 / prompt=current`
- Samples: `4`
- Overall all-pass rate: `0.000`
- New state captures expected information: `0/4`
- Improved vs previous trace state: `1/4`
- Regressed vs previous trace state: `4/4`

## Pack Results

| Pack | N | All Pass | Request Type | Role | Artist Mode | Profile | Temporal | Rejection | Positive Control |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0_named_artist_ranker_failure | 1 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| P0_new_artist_union20_gap_failure | 1 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 |
| P0_same_album_ranker_failure | 1 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 |
| P1_rejection_guardrail_failure | 1 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |

## State Change Evaluation

Each row compares the previous trace state snapshot against the new extracted state and the desired state contract for the replay example.

## Failures

### `b466a64b-b3cc-4c62-8a70-8261434f915f::t2`

- Pack: `P0_new_artist_union20_gap_failure`
- Failed checks: `schema_valid, target_artist_mode_correct, retrieval_profile_correct, temporal_semantics_correct`
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
    "current_request": null,
    "entities": [],
    "rejections": [],
    "retrieval_profile": null,
    "target_artist_mode": null,
    "temporal_constraint": null
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

### `b2582e52-6d13-40b4-8552-2d8b63fa6c75::t8`

- Pack: `P1_rejection_guardrail_failure`
- Failed checks: `schema_valid, rejection_normalization_correct`
- Current user: Yeah, "Revenga" is awesome! System Of A Down is always great. But I was really hoping for some *new* bands with that heavy, alternative metal sound. Do you have any bands that are similar in style to System Of A Down, but not them? I'm ready to discover som...

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
      "schema_valid",
      "rejection_normalization_correct"
    ],
    "still_missing_checks": []
  },
  "new_state_read": {
    "current_request": null,
    "entities": [],
    "rejections": [],
    "retrieval_profile": null,
    "target_artist_mode": null,
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

### `93199894-d3db-4335-8278-e1be175944e4::t6`

- Pack: `P0_named_artist_ranker_failure`
- Failed checks: `schema_valid, role_correct, target_artist_mode_correct, retrieval_profile_correct`
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
      "schema_valid",
      "role_correct"
    ],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": null,
    "entities": [],
    "rejections": [],
    "retrieval_profile": null,
    "target_artist_mode": null,
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

### `c96d7bb9-65d4-44be-9bc2-891e8e485f4e::t7`

- Pack: `P0_same_album_ranker_failure`
- Failed checks: `schema_valid, target_artist_mode_correct, retrieval_profile_correct`
- Current user: This is wonderful! 'O Que Falta Em Você Sou Eu' definitely hits that spot of deep longing and emotional storytelling that I love. It's truly beautiful. Keep them coming! What other songs, maybe by other artists but with a similar powerful, emotional sertane...

```json
{
  "desired_state_read": {
    "current_target_entities": [],
    "normalized_rejections": null,
    "prior_entities": [
      {
        "role": "satisfied_or_history",
        "use_as_retrieval_seed": false,
        "value": "Marília Mendonça"
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
      "schema_valid"
    ],
    "still_missing_checks": [
      "target_artist_mode_correct",
      "retrieval_profile_correct"
    ]
  },
  "new_state_read": {
    "current_request": null,
    "entities": [],
    "rejections": [],
    "retrieval_profile": null,
    "target_artist_mode": null,
    "temporal_constraint": null
  },
  "previous_state_read": {
    "current_request": null,
    "entities": [
      {
        "role": "current_target",
        "type": "unknown",
        "use_as_retrieval_seed": true,
        "value": "Marília Mendonça",
        "was_stale_in_trace": true
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "sertanejo"
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
        "value": "powerful"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "deep"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "heartfelt"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "longing"
      },
      {
        "role": "current_target",
        "type": "tag",
        "use_as_retrieval_seed": true,
        "value": "sertanejo universitário"
      }
    ],
    "rejections": [],
    "retrieval_profile": "continuation",
    "target_artist_mode": null,
    "temporal_constraint": null
  }
}
```

