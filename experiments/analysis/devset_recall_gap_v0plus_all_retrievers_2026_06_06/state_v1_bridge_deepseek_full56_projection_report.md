# State Projection Label Evaluation

- Samples: `56`
- Passes: `55`
- Failures: `1`
- Pass rate: `0.982`

## Failures

### `5f085552-b56b-440e-830b-b4e40b58f854::t6`

- Pack: `P0_novelty_prior_anchor_failure`
- Fact class: `attribute_temporal`
- Missing: `positive:high-energy country`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "tag",
      "value": "upbeat high-energy",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "late 90s or early 2000s",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "gets you moving",
      "sentiment": 1
    }
  ],
  "compiler_style_reference_entities": [
    {
      "type": "artist",
      "value": "Shania Twain",
      "sentiment": 1
    },
    {
      "type": "artist",
      "value": "Tim McGraw",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

