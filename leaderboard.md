# Music Recommender Leaderboard — Devset

*Higher is better for all NDCG and diversity metrics.*

## Ranking (by NDCG@10)

| Rank | Model | NDCG@1 | NDCG@10 | NDCG@20 | Catalog Diversity | Lexical Diversity |
|------|-------|--------|---------|---------|-------------------|-------------------|
| 1 | random | 0.0000 | 0.0001 | 0.0001 | 0.9652 | 0.0000 |
| 2 | popularity | 0.0005 | 0.0018 | 0.0024 | 0.0004 | 0.0000 |
| 3 | llama1b_bm25 | 0.0098 | 0.0627 | 0.0815 | 0.3795 | 0.2549 |
| 4 | llama1b_bert | 0.0018 | 0.0048 | 0.0063 | 0.0607 | 0.2069 |

## Notes

- **llama1b_bm25** is the best performing model on relevance metrics (NDCG).
- **random** has the highest catalog diversity by far, but near-zero relevance.
- Catalog size: 47,071 tracks across all experiments.
- Source scores: `evaluator/exp/scores/devset/`
