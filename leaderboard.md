# Music Recommender Leaderboard — Devset

*Higher is better for all metrics. Ranked by **NDCG@20** (project headline metric). Devset = 1000 sessions × 8 turns = 8000 turns, 47,071-track catalog.*

*Last groomed: 2026-06-01 (post #80 all-retrievers run). `—` = metric not captured for that run. The `image` row reflects the post-bugfix re-run; the all-retrievers row is a 5-shard full devset run at `9f4904a`; rows from the controlled [embedding ablation](experiments/v0plus_compiler_ablation_2026-05-26.md) are pre-bugfix unless noted; other rows come from their per-run reports.*

## Ranking (by NDCG@20)

| Rank | Run / model | Type | NDCG@20 | Hit@1 | Hit@20 | MRR | Report |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | `v0plus_compiler_image_devset` ⁰ | v0+ multimodal | **0.1452** | — | 0.299 | 0.106 | [report](experiments/v0plus_compiler_image_devset.md) |
| 2 | `v0plus_compiler_all_devset` | v0+ multimodal | 0.1432 | 0.044 | 0.309 | 0.101 | [ablation](experiments/v0plus_compiler_ablation_2026-05-26.md) |
| 3 | `v0plus_compiler_audio_image_devset` | v0+ multimodal | 0.1421 | 0.045 | 0.303 | 0.101 | [ablation](experiments/v0plus_compiler_ablation_2026-05-26.md) |
| 4 | `v0plus_compiler_all_retrievers_devset` | v0+ all retrievers | 0.1219 | 0.038 | 0.266 | 0.087 | [report](experiments/v0plus_compiler_all_retrievers_devset.md) |
| 5 | `v0plus_compiler_metadata_devset` | v0+ dense-text | 0.1188 | 0.039 | 0.259 | 0.085 | [ablation](experiments/v0plus_compiler_ablation_2026-05-26.md) |
| 6 | `bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset` | LLM-rewrite QU | 0.1092 | — | — | — | [report](experiments/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md) |
| 7 | `v0plus_compiler_audio_devset` | v0+ multimodal | 0.1081 | 0.034 | 0.239 | 0.077 | [ablation](experiments/v0plus_compiler_ablation_2026-05-26.md) |
| 8 | `RRF(bm25_with_tags, dense_qwen3_8b)` | offline hybrid | 0.1072 | — | — | — | [findings](experiments/retrieval_analysis_findings_2026-04-28.md) |
| 9 | `v0plus_compiler_cfbpr_devset` ¹ | v0+ CF anchor | 0.1041 | 0.031 | 0.230 | 0.073 | [ablation](experiments/v0plus_compiler_ablation_2026-05-26.md) |
| 10 | `dense_qwen3_embedding_8b_devset` | dense retrieval-only | 0.1025 | — | — | — | [report](experiments/dense_qwen3_embedding_8b_devset.md) |
| 11 | `v0plus_compiler_user_devset` | v0+ user CF | 0.1004 | 0.027 | 0.230 | 0.069 | [ablation](experiments/v0plus_compiler_ablation_2026-05-26.md) |
| 12 | `v0plus_compiler_devset` (BM25-only) ² | v0+ baseline | 0.0980 | 0.025 | 0.233 | 0.066 | [report](experiments/v0plus_compiler_devset.md) |
| 13 | `bm25_devset_retrieval_only_with_tag_list` | sparse retrieval-only | 0.0970 | — | — | — | [report](experiments/bm25_devset_retrieval_only_with_tag_list.md) |
| 14 | `v0plus_compiler_attributes_devset` | v0+ dense-text | 0.0915 | 0.025 | 0.214 | 0.064 | [ablation](experiments/v0plus_compiler_ablation_2026-05-26.md) |
| 15 | `v0plus_compiler_lyrics_devset` | v0+ dense-text | 0.0893 | 0.021 | 0.216 | 0.060 | [ablation](experiments/v0plus_compiler_ablation_2026-05-26.md) |
| 16 | `llama1b_bm25_devset` | generative end-to-end | 0.0815 | — | — | — | [report](experiments/llama1b_bm25_devset.md) |
| 17 | `llama1b_bert_devset` | generative end-to-end | 0.0063 | — | — | — | [report](experiments/llama1b_bert_devset.md) |
| 18 | `popularity` | non-personalized baseline | 0.0024 | — | — | — | — |
| 19 | `random` | floor | 0.0001 | — | — | — | — |

⁰ Post #66/#71 bugfix re-run (NDCG@20 0.1452 vs prior ablation 0.1461; deep-pool coverage improved, Hit@1000 0.598→0.626). Top-20 quality is essentially flat — the fixes were correctness, not a regression.
¹ `cf_bpr` ran with a partially-cold LLM cache (12.72% extractor `state=None` vs ~0.14% elsewhere); a cache-warm re-run would likely score 3–5% higher.
² The standalone `v0plus_compiler_devset` report records NDCG@20 **0.1005** (+36% vs BM25 retrieval-only); the **0.0980** here is the same config re-run as the ablation's controlled BM25-only baseline.

## Notes

- **`v0plus_compiler_image_devset` is the current overall best** (NDCG@20 0.146). Cover-art SigLIP2 embeddings are a strong same-artist / same-era signal, but the lift is almost entirely on the *continuation* cohort (Cont NDCG@20 +64%); it barely moves the novel-artist cohort.
- **`v0plus_compiler_all_retrievers_devset`** has the best candidate coverage (Hit@1000 0.697), but the older `v0plus_compiler_all_devset` remains much stronger at top-20 ranking (NDCG@20 0.143 vs 0.122). Treat the all-retrievers run as a reranker/source-pool candidate, not a canonical ranking config.
- **Two qwen3 dense branches hurt at the macro level** (attributes −7%, lyrics −9% NDCG@20); only `metadata_qwen3` is positive (+21%).
- The **novel-artist cohort (64% of turns)** is the standing gap: baseline Hit@20 is 5× worse there (0.093 vs 0.486). No single modality solves it.
- Diversity metrics (catalog/lexical) were tracked for the early baselines but are not part of the v0+ ablation; re-run `evaluator` with diversity enabled to repopulate if needed.
- Catalog size: 47,071 tracks. Full cross-run takeaways: [experiments/experiment_log.md](experiments/experiment_log.md). Status & current bests: [experiments/README.md](experiments/README.md).
