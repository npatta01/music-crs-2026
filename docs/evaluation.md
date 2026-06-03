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
python evaluate_devset.py --tid v0plus_compiler_image_devset
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

The v0+ devset trace sidecar (`exp/inference/devset/{tid}_trace.jsonl`) carries a
per-turn `branches` key when `CompilerConfig.branch_trace_topk > 0`: each
retriever branch's RAW top-`branch_trace_topk` `(track_id, score)` pool keyed by
a stable name (`bm25`, `dense.<encoder_id>.<query_id>.<vector_field>`,
`centroid.<source>.<vector_field>`, `lookup.resolved_artist_discography`,
`lookup.era_popularity`), the RRF `fused` list, the `final` recommendation (with
`n_from_fusion` / `n_from_backfill` provenance), and `recommended.top1_track_id`
(the headline track an explanation would target). Devset trace rows also carry a
`trace_schema_version` and `run` metadata (`tid`, `git_sha`, `config_hash`).
Inside `branches`, ranker-first diagnostics include `branch_queries`,
`branch_status`, and `candidate_filter_summary`: exact query/source descriptors,
fired/skipped status with skip reasons, and compact candidate-filter counts. The
candidate-filter counts are over the traced top-`branch_trace_topk` slice per
branch, not the full candidate pools used by fusion. The trace never writes dense
vectors or full per-candidate ranker feature rows. The knob is 0 by default, so
submission/blindset runs pay nothing and write no `branches`.

`scripts/branch_diagnostics.py` reads the trace + ground truth and reports:

- `hit@{1,20,50,100,200,1000}` over the final recommendation,
- `unionhit@{20,50,100,200}` over the union of every branch's top-k (the coverage
  ceiling if fusion were perfect), `union_size@k`, and `fusion_efficiency@k`,
- per-branch `recall@{100,200,1000}` (denominator = turns the branch fired).

```bash
python scripts/branch_diagnostics.py \
  --trace exp/inference/devset/{tid}_trace.jsonl \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  --out exp/diagnostics/devset/{tid}.json   # optional; always prints a table
```

This is a standalone tool — it does not modify the evaluator submodule and is
independent of `evaluate_devset.py`.

---

## Devset Leaderboard

The compact current leaderboard lives in [`leaderboard.md`](../leaderboard.md).
Historical BM25, dense-only, rewrite, Milvus, LanceDB, and generative baseline
rows were pruned from the working tree and remain available in Git history.

Catalog size: 47,071 tracks.

**Notes:**
- `v0plus_compiler_image_devset` is the current top-20 score anchor.
- `v0plus_compiler_all_retrievers_devset` is the latest deep-coverage run and
  is useful for reranker/candidate-pool diagnostics.
- Retrieval-only `lm_type: dummy` runs have lexical diversity of zero by
  construction; prose generation is currently downstream of retrieval work.

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
