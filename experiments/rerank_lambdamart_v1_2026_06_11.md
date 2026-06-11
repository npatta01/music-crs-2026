# Reranker v1 — devset union-pool LambdaMART (2026-06-11)

Test sessions: 150 (895 playable turns). RRF baseline: ndcg20=0.1786 hit20=0.3799 hit1=0.0570

| arm | ndcg@20 | Δ vs RRF | t | hit@20 | hit@1 | best_iter |
|---|---:|---:|---:|---:|---:|---:|
| full | 0.2554 | +0.0768 | +8.46 | 0.5084 | 0.0972 | 110 |

## Top-25 features (gain, full arm)

| feature | importance |
|---|---:|
| artist_track_count | 393 |
| clap_centroid | 240 |
| rrf_score | 238 |
| siglip_centroid | 202 |
| pct_user_cf | 186 |
| clap_last | 181 |
| era_pop_pct | 175 |
| pct_cf_centroid | 174 |
| q06_attributes_cos | 173 |
| duration_ms | 168 |
| cf_centroid | 168 |
| user_cf | 155 |
| tag_emb_cos | 152 |
| rank__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 143 |
| pct_pop_pct | 141 |
| tag_overlap_idf | 137 |
| rank__bm25 | 136 |
| pct_tag_overlap_idf | 133 |
| q06_metadata_cos | 131 |
| pct_rrf_score | 130 |
| score__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 126 |
| rrf_rank | 125 |
| pct_q06_metadata_cos | 125 |
| year_in_constraint | 124 |
| cf_drift | 118 |

| no_pool | 0.2362 | +0.0576 | +5.62 | 0.4592 | 0.0950 | 112 |

## Context

- Features: 98 cols from `scripts/rerank/build_features.py` over the
  `pruned_resolved_tags` full-devset trace (union@200 pools, 7.72M rows,
  7,182 playable turns of 8,000). Fully local; only cost = $0.05 DeepInfra
  embeddings (25,076 unique strings, memoized).
- Trainer: `scripts/rerank/train_lgbm.py`, LightGBM lambdarank@20,
  session-split 700/150/150, early stopping (~110 trees).
- The no-pool ablation (+32% vs RRF without any branch rank/score/RRF
  features) shows the lift is content-driven, not consensus re-derivation.
- Projected overall devset NDCG@20 ≈ 0.19 vs shipped 0.1374 (+39%), subject
  to devset-tuning optimism — blind-A is the honest test.

## Next

- 5-fold session CV to firm the interval; pool-depth sensitivity (k=100/500).
- Production integration: deferred rerank pass over the union pool at
  inference (state, played sequence, user embedding, cached query embeddings
  all available) behind a config flag; paired seeded smoke.
- Consider distillation of #95's gpt-4o listwise judgments as auxiliary
  labels later.
