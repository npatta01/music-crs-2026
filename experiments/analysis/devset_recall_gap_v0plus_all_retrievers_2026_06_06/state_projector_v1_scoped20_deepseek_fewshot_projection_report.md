# State Projector Scoped20 Projection Evaluation - Few Shot Pass

- Matching: state_fact_eval token containment.
- Samples: `20`
- Passes: `18`
- Pass rate: `0.900`

## Failures

### `963b3ee7-17d1-4bb3-8a3f-0bc528a1f096::t5`

- Pack: `P1_rejection_guardrail_failure`
- Fact class: `negative_feedback_attribute`
- Missing: `negative_mention:heavy and intense, explicit_rejection:heavy and intense`

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
      "value": "hip-hop",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "positive vibe",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "boost my energy",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "put me in a good mood",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": [
    {
      "kind": "artist",
      "value": "Lupe Fiasco",
      "source_turn": 3
    }
  ]
}
```

### `c863175a-bbaf-4f6c-aef7-cb16f2792cb5::t6`

- Pack: `P0_same_album_ranker_failure`
- Fact class: `same_artist_or_attribute`
- Missing: `positive:lyrical storytelling`

```json
{
  "compiler_mentioned_entities": [
    {
      "type": "artist",
      "value": "Mac Miller",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "storytelling about relationships",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "hip-hop",
      "sentiment": 1
    },
    {
      "type": "tag",
      "value": "deep introspective",
      "sentiment": 1
    }
  ],
  "compiler_explicit_rejections": []
}
```

