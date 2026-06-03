# LambdaMART reranker (`mcrs.rerank`)

Learned final ranker over the v0+ **branch-pool union**, replacing weighted RRF (GH #93).
Retrieval becomes recall-only; the reranker owns all ordering and is trained to optimise
**NDCG@20**. No RRF-derived features (`rrf_score`/`rrf_rank`) — only raw per-retriever
position + raw branch score; the trees learn any rank transform themselves.

## Pipeline

```
branch trace (branch_trace_topk>0)
  → build_dataset.py   union of all branch pools per (session,turn) + golden label  → candidates.parquet + groups.jsonl
  → features.py        blocks A/A′/C/D/E/F/G; catalog join; NaN+hit handling          → features.parquet (+ .meta.json)
  → train.py           LGBMRanker(lambdarank), GroupKFold by session_id, early stop   → models/, oof.parquet, importance.json
  → evaluate.py        metrics_recsys adapter; NDCG@20/@1/MRR/hit@20 vs RRF baseline   → report
  → interpret.py       SHAP + gain importance; popularity-prior acceptance gate        → interpret_report.json
```

Run it all via the root orchestrator:

```bash
# 1000-turn smoke (uses the checked-in trace sample)
python run_rerank_phase1.py --trace exp/inference/trace/devset_trace_first1000.json --out-root exp/rerank/smoke

# full devset gate (cap the negative union; golden is always kept regardless of the cap)
python run_rerank_phase1.py --max-pool-depth 250 --out-root exp/rerank/devset
```

Prereqs: `pip install -e .[rerank]` and a LanceDB catalog at `cache/lancedb`
(`python scripts/build_lancedb_index.py --metadata-only` is enough — the feature set needs only
catalog metadata, no embedding vectors).

## Feature blocks (first cut, locked 2026-06-03)

| Block | Columns | Notes |
|---|---|---|
| A  | `{branch}__{rank,norm_rank,score,hit}` ×11 | absent ⇒ NaN; `_hit` carries presence |
| A′ | `agg__n_branches_hit`, `agg__n_{lexical,content,behavioral}_hit`, `agg__min_rank`, `agg__mean_norm_rank`, `agg__{mean,max}_score_z` | within-group z of each branch score |
| C  | `c__{log_popularity,release_year,release_decade,n_tags}` | **no raw artist/album IDs** (leakage guard) |
| D  | `intent_mode`,`exploration_policy` (categorical), `q__routing_*` (×5), `q__n_*`, `q__frac_through_session`, `q__resolved_*_confidence`, … | group-constant; help via interactions |
| E  | `e__{artist_match_anchor,artist_match_resolved_target,is_resolved_target_track,is_anchor_track,same_artist_as_rejected,is_rejected_track,is_played_already,tag_overlap_positive,tag_overlap_rejected,in_release_year_range,years_outside_range}` | learned routing-multiplier replacement |
| F  | `{branch}__score_{gap,ratio}_to_top`, `f__n_same_artist_in_union`, `f__artist_best_rank_in_union`, `f__jaccard_tag_overlap`, `f__n_candidate_tags_not_in_positive` | cheap structural signals |

**Tested and dropped:** block G (sentiment-split embedding relevance — cos to accepted/rejected
centroid + margin over cf_bpr/audio_clap/metadata_qwen3) added only +0.001 NDCG@20 on devset,
redundant with the `centroid.*` branches, at ~5× the feature-build cost. See git history.

**Deferred** (post-gate iteration): `turns_since_last_*` recency/staleness; full dense
cross-scoring; inter-candidate diversity. Branch registry & canonical names: `branches.py`.

## Acceptance gate

The model must (1) beat the RRF baseline NDCG@20 on held-out session folds, and (2) pass the
popularity-prior check in `interpret.py` (popularity-family gain share below threshold, and the
top feature is not popularity) — confirming it learned intent-conditioned weighting rather than
a global "recommend popular" prior. Otherwise: close as a documented negative result.
