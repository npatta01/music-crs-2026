# State Projection Label Evaluation

- Samples: `56`
- Passes: `53`
- Failures: `3`
- Pass rate: `0.946`

## Failures

### `a930da0d-07f1-46c6-909d-e4fd95ae1148::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `popular_new_artist`
- Missing: `positive:popular`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "well-known",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "widely loved",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "feel-good",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "strong beat",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "upbeat",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "energetic",
      "sentiment": 1
    }
  ],
  "compiler_style_reference_entities": [],
  "compiler_explicit_rejections": []
}
```

### `1e14a07f-7369-4d24-9285-9343b6b18353::t8`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `style_rejection`
- Missing: `negative_mention:metal, explicit_rejection:metal`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "heavy and intense",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "dark folk",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "gothic folk",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "atmospheric",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "haunting",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "ethereal vocals",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "traditional instruments",
      "sentiment": 1
    }
  ],
  "compiler_style_reference_entities": [],
  "compiler_explicit_rejections": [
    {
      "kind": "tag",
      "value": "heavy and intense",
      "source_turn": 3
    }
  ]
}
```

### `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `negative_feedback_attribute`
- Missing: `positive:boost my energy`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "artist",
      "value": "Lupe Fiasco",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "heavy and intense",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "he said 'positive vibe'",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "energetic",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "uplifting",
      "sentiment": 1
    }
  ],
  "compiler_style_reference_entities": [],
  "compiler_explicit_rejections": [
    {
      "kind": "artist",
      "value": "Lupe Fiasco",
      "source_turn": 3
    },
    {
      "kind": "tag",
      "value": "heavy and intense",
      "source_turn": 3
    }
  ]
}
```

