# State Projector Scoped20 Projection Evaluation

- Samples: `20`
- Passes: `12`
- Pass rate: `0.600`

## Failures

### `f2d85aa5-2086-4b1e-9974-d188c43621db::t8`

- Pack: `P1_temporal_constraint_failure`
- Fact class: `negative_feedback_temporal`
- Missing: `negative_mention:dark and harsh, explicit_rejection:dark and harsh`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "track",
      "value": "Sleep Paralysis",
      "sentiment": -1
    },
    {
      "type": "artist",
      "value": "Sidewalks and Skeletons",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "ambient electronic",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "instrumental",
      "sentiment": 1
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
    }
  ],
  "compiler_explicit_rejections": [
    {
      "kind": "track",
      "value": "Sleep Paralysis",
      "source_turn": 3
    },
    {
      "kind": "artist",
      "value": "Sidewalks and Skeletons",
      "source_turn": 3
    }
  ]
}
```

### `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `negative_feedback_attribute`
- Missing: `positive:boost my energy, negative_mention:heavy and intense, explicit_rejection:heavy and intense`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "heavy intense",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "positive",
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
    },
    {
      "type": "tag",
      "value": "hip-hop",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": [
    {
      "kind": "tag",
      "value": "heavy intense",
      "source_turn": 3
    }
  ]
}
```

### `93199894-d3db-4335-8278-e1be175944e4::t6`

- Pack: `P0_named_artist_ranker_failure`
- Fact class: `exact_artist_alternatives`
- Missing: `positive:Soundgarden, positive:Rusty Cage`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "artist",
      "value": "Soundgarden",
      "sentiment": -1
    },
    {
      "type": "artist",
      "value": "Stone Temple Pilots",
      "sentiment": 1
    },
    {
      "type": "artist",
      "value": "Nirvana",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": [
    {
      "kind": "artist",
      "value": "Soundgarden",
      "source_turn": 3
    }
  ]
}
```

### `692611f0-d9ef-406c-8327-902575197aee::t8`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `attribute_from_prior`
- Missing: `positive:watching a movie`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "vivid storytelling",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "detailed narrative",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
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
      "value": "lyrical storytelling",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "relationships and connection",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

### `c96d7bb9-65d4-44be-9bc2-891e8e485f4e::t7`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `attribute_new_artist`
- Missing: `positive:deep longing, positive:emotional storytelling`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "powerful emotional sertanejo",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

### `2bbc0a7e-3ab0-4376-8135-182cd4ae075f::t1`

- Pack: `P1_positive_tag_retrieval_gap_failure`
- Fact class: `hidden_target_temporal`
- Missing: `positive:hit`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "Latin Pop",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "early 2000s",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

### `daeef24e-b041-4140-9101-882820c63408::t7`

- Pack: `P0_novelty_prior_anchor_failure`
- Fact class: `exact_entity`
- Missing: `negative_mention:Tom Sawyer, explicit_rejection:Tom Sawyer`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "artist",
      "value": "Rush",
      "sentiment": 1
    },
    {
      "type": "track",
      "value": "The Spirit of Radio",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

