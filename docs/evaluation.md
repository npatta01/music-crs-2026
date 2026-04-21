# Evaluation

Evaluator repo: https://github.com/nlp4musa/music-crs-evaluator

Scores are stored in `evaluator/exp/scores/devset/`.

---

## Metrics

| Metric | Description |
|--------|-------------|
| **NDCG@1** | Normalized Discounted Cumulative Gain — relevance of the top-1 prediction |
| **NDCG@10** | NDCG over top-10 predictions — primary ranking metric |
| **NDCG@20** | NDCG over top-20 predictions |
| **Catalog Diversity** | Fraction of unique tracks recommended across all test predictions |
| **Lexical Diversity** | Text diversity in generated responses |

Higher is better for all metrics.

---

## Devset Leaderboard

| Rank | Model | NDCG@1 | NDCG@10 | NDCG@20 | Catalog Diversity | Lexical Diversity |
|------|-------|--------|---------|---------|-------------------|-------------------|
| 1 | llama1b_bm25 | 0.0098 | **0.0627** | 0.0815 | 0.3795 | 0.2549 |
| 2 | llama1b_bert | 0.0018 | 0.0048 | 0.0063 | 0.0607 | 0.2069 |
| 3 | popularity | 0.0005 | 0.0018 | 0.0024 | 0.0004 | 0.0000 |
| 4 | random | 0.0000 | 0.0001 | 0.0001 | **0.9652** | 0.0000 |

Catalog size: 47,071 tracks.

**Notes:**
- `llama1b_bm25` is the best baseline on relevance (NDCG) — 13× better NDCG@10 than BERT.
- `random` has the highest catalog diversity but near-zero relevance.
- `popularity` returns the same 20 tracks for everyone — zero diversity.

---

## Adding Experiment Results

When you run a new experiment, append a row to the table above with the config name and scores.
