# State Projector Projection Evaluation

- Samples: `20`
- Passes: `18`
- Failures: `2`
- Pass rate: `0.900`

## Failures

### `15b1caf3-d1ed-46ef-a8e3-c9f7657e6b77::t6`

- Pack: `P0_new_artist_union20_gap_failure`
- Fact class: `attribute_from_prior`
- Missing: `positive:out there`

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
      "value": "electronic but also soulful",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "unexpected discoveries",
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
      "value": "complex relationships",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "hip-hop",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "storytelling about relationships",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

