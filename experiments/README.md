# Experiment Index

Quick index for experiment reports in [`experiments/`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments) and the cross-run summaries in [`docs/experiment_log.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/docs/experiment_log.md).

## Current Bests

| Category | Run | Key result | Report |
|---|---|---:|---|
| Best sparse retrieval-only | `bm25_devset_retrieval_only_with_tag_list` | `NDCG@20 0.0970` | [bm25_devset_retrieval_only_with_tag_list.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_devset_retrieval_only_with_tag_list.md) |
| Best dense retrieval-only | `dense_qwen3_embedding_8b_devset` | `NDCG@20 0.1025` | [dense_qwen3_embedding_8b_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/dense_qwen3_embedding_8b_devset.md) |
| Best generative baseline | `llama1b_bm25_devset` | `NDCG@20 0.0815` | [llama1b_bm25_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/llama1b_bm25_devset.md) |
| Best rewrite wave result | `bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset` | `NDCG@20 0.1092` | [bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md) |
| Best offline hybrid so far | `RRF(bm25_with_tags, dense_qwen3_8b)` | `NDCG@20 0.1072` | [retrieval_analysis_findings_2026-04-28.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/retrieval_analysis_findings_2026-04-28.md) |

## Analysis Utilities

- Cross-run summary: [docs/experiment_log.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/docs/experiment_log.md)
- Offline retrieval comparison notebook: [notebooks/retrieval_analysis.ipynb](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/notebooks/retrieval_analysis.ipynb)
- Complementarity / hybrid findings note: [retrieval_analysis_findings_2026-04-28.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/retrieval_analysis_findings_2026-04-28.md)

## Waves

### Wave 1: BM25 Metadata Signal

- [bm25_devset_retrieval_only.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_devset_retrieval_only.md)
- [bm25_devset_retrieval_only_no_release_date.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_devset_retrieval_only_no_release_date.md)
- [bm25_devset_retrieval_only_with_tag_list.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_devset_retrieval_only_with_tag_list.md)
- [bm25_devset_retrieval_only_tag_list_only.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_devset_retrieval_only_tag_list_only.md)
- [bm25_devset_retrieval_only_tag_list_no_release_date.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_devset_retrieval_only_tag_list_no_release_date.md)

### Wave 2: Deterministic Query Understanding

- [bm25_qu_last_user_turn_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_last_user_turn_devset.md)
- [bm25_qu_user_turns_only_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_user_turns_only_devset.md)
- [bm25_qu_last_2_user_turns_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_last_2_user_turns_devset.md)
- [bm25_qu_last_3_user_turns_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_last_3_user_turns_devset.md)
- [bm25_qu_no_music_history_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_no_music_history_devset.md)

### Wave 3: LLM Rewrite Query Understanding

#### Preserve Entities v1

- [bm25_qu_llmrewrite_llama32_1b_preserve_entities_v1_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_llama32_1b_preserve_entities_v1_devset.md)
- [bm25_qu_llmrewrite_smollm2_1p7b_preserve_entities_v1_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_smollm2_1p7b_preserve_entities_v1_devset.md)
- [bm25_qu_llmrewrite_gemma4_e2b_preserve_entities_v1_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_gemma4_e2b_preserve_entities_v1_devset.md)
- [bm25_qu_llmrewrite_qwen25_3b_preserve_entities_v1_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_qwen25_3b_preserve_entities_v1_devset.md)
- [bm25_qu_llmrewrite_qwen3_4b_preserve_entities_v1_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_qwen3_4b_preserve_entities_v1_devset.md)

#### Catalog Terms v2

- [bm25_qu_llmrewrite_smollm2_1p7b_catalog_terms_v2_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_smollm2_1p7b_catalog_terms_v2_devset.md)
- [bm25_qu_llmrewrite_gemma4_e2b_catalog_terms_v2_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_gemma4_e2b_catalog_terms_v2_devset.md)
- [bm25_qu_llmrewrite_qwen25_3b_catalog_terms_v2_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_qwen25_3b_catalog_terms_v2_devset.md)
- [bm25_qu_llmrewrite_qwen3_4b_catalog_terms_v2_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_qwen3_4b_catalog_terms_v2_devset.md)

#### Carryover Guard v3

- [bm25_qu_llmrewrite_smollm2_1p7b_carryover_guard_v3_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_smollm2_1p7b_carryover_guard_v3_devset.md)
- [bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md)
- [bm25_qu_llmrewrite_qwen25_3b_carryover_guard_v3_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_qwen25_3b_carryover_guard_v3_devset.md)
- [bm25_qu_llmrewrite_qwen3_4b_carryover_guard_v3_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_qwen3_4b_carryover_guard_v3_devset.md)

### Wave 4: Dense Text Retrieval

- [dense_e5_base_v2_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/dense_e5_base_v2_devset.md)
- [dense_e5_large_v2_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/dense_e5_large_v2_devset.md)
- [dense_bge_base_en_v1_5_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/dense_bge_base_en_v1_5_devset.md)
- [dense_bge_large_en_v1_5_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/dense_bge_large_en_v1_5_devset.md)
- [dense_qwen3_embedding_0_6b_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/dense_qwen3_embedding_0_6b_devset.md)
- [dense_qwen3_embedding_4b_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/dense_qwen3_embedding_4b_devset.md)
- [dense_qwen3_embedding_8b_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/dense_qwen3_embedding_8b_devset.md)

### Retrieval Analysis and Hybrid Diagnostics

- [retrieval_analysis_findings_2026-04-28.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/retrieval_analysis_findings_2026-04-28.md)

## Conventions

- One per-run report per file: `experiments/{tid}.md`
- Cross-run conclusions go in [docs/experiment_log.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/docs/experiment_log.md)
- Retrieval comparison and hybrid analysis belongs in [notebooks/retrieval_analysis.ipynb](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/notebooks/retrieval_analysis.ipynb)

## Recommended Next Cleanup

- Add a short metadata block to each experiment report with `wave`, `family`, and `status` so this index can eventually be generated automatically.
