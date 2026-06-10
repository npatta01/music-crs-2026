# State Projection Label Evaluation

- Samples: `20`
- Passes: `19`
- Failures: `1`
- Pass rate: `0.950`

## Failures

### `93199894-d3db-4335-8278-e1be175944e4::t6`

- Pack: `P0_named_artist_ranker_failure`
- Fact class: `exact_artist_alternatives`
- Missing: `positive:Rusty Cage`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "artist",
      "value": "Soundgarden",
      "sentiment": 1
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
  "compiler_style_reference_entities": [
    {
      "type": "track",
      "value": "Rusty Cage",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

