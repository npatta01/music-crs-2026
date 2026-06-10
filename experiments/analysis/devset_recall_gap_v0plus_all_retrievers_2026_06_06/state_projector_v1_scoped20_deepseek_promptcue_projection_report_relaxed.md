# State Projector Scoped20 Projection Evaluation - Prompt Cue Pass Relaxed

- Matching: token containment ignoring small function words.
- Samples: `20`
- Passes: `16`
- Pass rate: `0.800`

## Failures

### `1e14a07f-7369-4d24-9285-9343b6b18353::t8`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `style_rejection`
- Missing: `positive:ethereal vocals`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "metal",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "heavy and intense",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "atmospheric dark folk",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "gothic folk",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "female vocals",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "haunting ethereal",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "traditional instruments",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": [
    {
      "kind": "tag",
      "value": "metal",
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

### `d265b5a9-af57-4070-90f5-692a960c5aaa::t6`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `album_rejection_visual`
- Missing: `positive:artistically unique`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "album",
      "value": "Random Access Memories",
      "sentiment": -1
    },
    {
      "type": "album",
      "value": "New Energy",
      "sentiment": -1
    },
    {
      "type": "tag",
      "value": "electronic",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "striking cover art",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
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
      "value": "cinematic",
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

### `c96d7bb9-65d4-44be-9bc2-891e8e485f4e::t7`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `attribute_new_artist`
- Missing: `positive:deep longing, positive:emotional storytelling`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "sertanejo",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "powerful emotional",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

