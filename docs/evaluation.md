# Evaluation

Evaluator lives in the `evaluator/` git submodule
(fork of https://github.com/nlp4musa/music-crs-evaluator with
`--session_ids_file` support and extended dev-set metrics).

```bash
git submodule update --init evaluator
cd evaluator
python make_ground_truth.py                      # once
# Predictions are read from ./exp/inference/devset/<tid>.json
# (symlink or copy from the main repo's exp/inference/devset/).
python evaluate_devset.py --tid llama1b_bm25_devset
```

This writes `evaluator/exp/scores/devset/<tid>.json` and prints a grouped
report. The streamlit explorer in the main repo recomputes the same metrics
inline for interactive exploration.

---

## Metrics

Grouped so each group answers a different question.

### Ranking quality — *given the GT is somewhere in the pool, is it ranked well?*

| Metric | Description |
|--------|-------------|
| **NDCG@{1,5,10,20,50,100}** | Normalized Discounted Cumulative Gain. NDCG@10 is the official primary ranking metric. |
| **MRR** | Mean Reciprocal Rank over the full retrieved pool. |
| **MRR@100** | MRR restricted to the top-100 — comparable across runs with different pool depths. |

### Retrieval coverage — *is the GT even in the pool?*

| Metric | Description |
|--------|-------------|
| **Recall@{1,5,10,20,50,100}** | Fraction of turns where the GT track appears in the top-k. With a single GT per turn, Recall@k = Hit@k. |
| **% GT not in top-20** | Ceiling on NDCG@20: any miss here is unrecoverable by reranking. |
| **% GT not in top-100** | Ceiling on what a reranker over the top-100 can ever achieve. |
| **Mean / median rank (when found)** | Rank of the GT conditional on it being retrieved at all — useful for spotting reranking headroom. |

### Diversity

| Metric | Description |
|--------|-------------|
| **Catalog Diversity @20 / @100** | Unique tracks recommended across all turns / catalog size. |
| **Distinct-1 / Distinct-2** | Unigram / bigram distinct-n over generated responses. |

### Per-turn breakdown

NDCG@20, Recall@20, Recall@100 split by turn index (1–8). Late turns with
long conversation histories usually underperform; watching this split is how
you catch that before it affects the final score.

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

## Notes on submission vs dev-set

- `retrieval_topk` defaults to **20** in `CRS_BASELINE`, so blindset / submission
  outputs remain unchanged (the leaderboard expects exactly 20 ids per turn).
- Devset configs override `retrieval_topk: 100` so the offline evaluator can
  report Recall@100 / NDCG@100. The submission file format is independent.
