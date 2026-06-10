# State Projector Projection Evaluation

- Samples: `20`
- Passes: `16`
- Failures: `4`
- Pass rate: `0.800`

## Failures

### `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `attribute_from_prior`
- Missing: `positive:electronic, positive:soulful, positive:out there`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "unique",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "experimental",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

### `f2d85aa5-2086-4b1e-9974-d188c43621db::t8`

- Pack: `P1_temporal_constraint_failure`
- Fact class: `negative_feedback_temporal`
- Missing: `positive:ambient electronic`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "dark and harsh",
      "sentiment": -1
    },
    {
      "type": "track",
      "value": "Sleep Paralysis",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "dreamy",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "serene",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "warm evolving pads",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "subtle rhythms",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "atmospheric",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "instrumental electronic",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "warm",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": [
    {
      "kind": "tag",
      "value": "dark and harsh",
      "source_turn": 3
    },
    {
      "kind": "track",
      "value": "Sleep Paralysis",
      "source_turn": 3
    }
  ]
}
```

### `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `negative_feedback_attribute`
- Missing: `positive:positive vibe, positive:boost my energy`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "artist",
      "value": "Lupe Fiasco",
      "sentiment": -1
    },
    {
      "type": "track",
      "value": "Streets On Fire",
      "sentiment": -1
    },
    {
      "type": "track",
      "value": "The Coolest",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "heavy and intense",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "hip-hop",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "positive uplifting",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "energetic",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": [
    {
      "kind": "artist",
      "value": "Lupe Fiasco",
      "source_turn": 3
    },
    {
      "kind": "track",
      "value": "Streets On Fire",
      "source_turn": 3
    },
    {
      "kind": "track",
      "value": "The Coolest",
      "source_turn": 2
    },
    {
      "kind": "tag",
      "value": "heavy and intense",
      "source_turn": 3
    }
  ]
}
```

### `c863175a-bbaf-4f6c-aef7-cb16f2792cb5::t6`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `same_artist_or_attribute`
- Missing: `positive:Mac Miller`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "hip-hop",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "lyrical storytelling",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "storytelling about relationships",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "deep introspective storytelling",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

