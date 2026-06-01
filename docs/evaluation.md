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
python evaluate_devset.py --tid bm25_devset_retrieval_only_with_tag_list
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
| **NDCG@{1,5,10,20,50,100}** | Headline ranking metrics plus near-pool diagnostics. NDCG@10 is the official primary ranking metric. |
| **NDCG@{200,500,1000}** | Deep-cutoff diagnostics: useful for separating candidate-generation limits from reranking limits. Values become `null` when the retrieved pool is shallower than the cutoff. |
| **MRR** | Mean Reciprocal Rank over the full retrieved pool. |
| **MRR@{100,200,500,1000}** | Reciprocal-rank diagnostics at fixed cutoffs, comparable across runs with the same retrieved depth. |

### Retrieval coverage — *is the GT even in the pool?*

| Metric | Description |
|--------|-------------|
| **Recall@{1,5,10,20,50,100}** | Headline coverage metrics. With a single GT per turn, Recall@k = Hit@k. |
| **Recall@{200,500,1000}** | Deep-cutoff coverage diagnostics: tells you whether more recall is available beyond the top-100. Values become `null` when the retrieved pool is shallower than the cutoff. |
| **% GT not in top-20** | Ceiling on NDCG@20: any miss here is unrecoverable by reranking. |
| **% GT not in top-100** | Ceiling on what a reranker over the top-100 can ever achieve. |
| **% GT not in top-200 / top-500 / top-1000** | Same ceiling analysis for deeper candidate pools. |
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

## Branch diagnostics (per-retriever coverage)

The v0+ devset trace sidecar (`exp/inference/devset/{tid}_trace.json`) carries a
per-turn `branches` key when `CompilerConfig.branch_trace_topk > 0`: each
retriever branch's RAW top-`branch_trace_topk` `(track_id, score)` pool keyed by
a stable name (`bm25`, `dense.<encoder_id>.<query_id>.<vector_field>`,
`centroid.<source>.<vector_field>`, `lookup.resolved_artist_discography`,
`lookup.era_popularity`), the RRF `fused` list, the `final` recommendation (with
`n_from_fusion` / `n_from_backfill` provenance), and `recommended.top1_track_id`
(the headline track an explanation would target). The knob is 0 by default, so
submission/blindset runs pay nothing and write no `branches`.

`scripts/branch_diagnostics.py` reads the trace + ground truth and reports:

- `hit@{1,20,50,100,200,1000}` over the final recommendation,
- `unionhit@{20,50,100,200}` over the union of every branch's top-k (the coverage
  ceiling if fusion were perfect), `union_size@k`, and `fusion_efficiency@k`,
- per-branch `recall@{100,200,1000}` (denominator = turns the branch fired).

```bash
python scripts/branch_diagnostics.py \
  --trace exp/inference/devset/{tid}_trace.json \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  --out exp/diagnostics/devset/{tid}.json   # optional; always prints a table
```

This is a standalone tool — it does not modify the evaluator submodule and is
independent of `evaluate_devset.py`.

---

## Devset Leaderboard

| Rank | Experiment | NDCG@1 | NDCG@10 | NDCG@20 | Catalog Diversity | Lexical Diversity |
|------|------------|--------|---------|---------|-------------------|-------------------|
| 1 | dense_qwen3_embedding_8b | 0.0136 | **0.0804** | **0.1025** | 0.4123 | 0.0000 |
| 2 | dense_qwen3_embedding_4b | **0.0175** | 0.0788 | 0.0994 | 0.3679 | 0.0000 |
| 3 | bm25_devset_retrieval_only_with_tag_list | 0.0095 | 0.0752 | 0.0970 | 0.4542 | 0.0000 |
| 4 | dense_e5_base_v2 | 0.0115 | 0.0728 | 0.0906 | 0.3612 | 0.0000 |
| 5 | dense_e5_large_v2 | 0.0105 | 0.0725 | 0.0895 | 0.3509 | 0.0000 |
| 6 | dense_bge_large_en_v1_5 | 0.0113 | 0.0689 | 0.0865 | 0.3316 | 0.0000 |
| 7 | dense_qwen3_embedding_0_6b | 0.0169 | 0.0688 | 0.0849 | 0.3373 | 0.0000 |
| 8 | dense_bge_base_en_v1_5 | 0.0110 | 0.0674 | 0.0836 | 0.3611 | 0.0000 |
| 9 | llama1b_bm25 | 0.0098 | 0.0626 | 0.0815 | 0.3796 | 0.2554 |
| 10 | llama1b_bert | 0.0018 | 0.0048 | 0.0063 | 0.0607 | 0.2069 |
| 11 | popularity | 0.0005 | 0.0018 | 0.0024 | 0.0004 | 0.0000 |
| 12 | random | 0.0000 | 0.0001 | 0.0001 | **0.9652** | 0.0000 |

Catalog size: 47,071 tracks.

**Notes:**
- `dense_qwen3_embedding_8b` is the current relevance leader on the devset leaderboard, edging `dense_qwen3_embedding_4b` and the best sparse retrieval-only baseline.
- `bm25_devset_retrieval_only_with_tag_list` remains the strongest sparse retrieval-only baseline and outperforms every dense run except the Qwen 4B and 8B variants.
- Retrieval-only `lm_type: dummy` runs have `lexical_diversity = 0.0` by construction, so lexical diversity is only meaningful for generative runs such as `llama1b_bm25` and `llama1b_bert`.
- `random` has the highest catalog diversity but near-zero relevance.
- `popularity` returns the same 20 tracks for everyone — zero diversity.

---

## Adding Experiment Results

When you run a new experiment, append one or more rows to the table above with the config name and scores.

## Notes on submission vs dev-set

- `retrieval_topk` defaults to **20** in `CRS_BASELINE`, so blindset / submission
  outputs remain unchanged (the leaderboard expects exactly 20 ids per turn).
- Devset configs override `retrieval_topk: 1000` so the offline evaluator can
  report deep-cutoff diagnostics through `@1000`. The submission file format is independent.
- The evaluator reports cutoff metrics even when a devset row returns fewer than 1000 candidates. A shallow row can still hit at deep cutoffs if the GT is present in the returned pool; otherwise the missing tail counts as a miss.
- Score JSON files also include depth metadata such as `available_cutoffs`, `min_pool_depth`, `max_pool_depth`, and `n_shallow_rows` so raw native Milvus runs stay easy to compare.
