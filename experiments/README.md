# Experiment Index

Use this directory as the main navigation surface for experiment runs, analysis packages, and cross-run status.

## Start Here

- Main status index: [README.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/README.md)
- Cross-run log: [experiment_log.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/experiment_log.md)
- Analysis index: [analysis/README.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/README.md)
- Local agent guidance: [CLAUDE.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/CLAUDE.md)
- Offline retrieval notebook: [notebooks/retrieval_analysis.ipynb](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/notebooks/retrieval_analysis.ipynb)
- LanceDB indexing notebook: [notebooks/05_lancedb_indexing.ipynb](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/notebooks/05_lancedb_indexing.ipynb)

## Status Vocabulary

- `planned`: scoped next step, not started
- `running`: experiment execution or labeling in progress
- `analyzed`: results exist and have a written analysis, but follow-up work remains open
- `done`: wave or analysis is complete for now
- `superseded`: kept for history, but replaced by a better follow-up

## Current Bests

| Category | Run | Key result | Status | Report |
|---|---|---:|---|---|
| Best sparse retrieval-only | `bm25_devset_retrieval_only_with_tag_list` | `NDCG@20 0.0970` | `done` | [bm25_devset_retrieval_only_with_tag_list.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_devset_retrieval_only_with_tag_list.md) |
| Best dense retrieval-only | `dense_qwen3_embedding_8b_devset` | `NDCG@20 0.1025` | `done` | [dense_qwen3_embedding_8b_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/dense_qwen3_embedding_8b_devset.md) |
| Best generative baseline | `llama1b_bm25_devset` | `NDCG@20 0.0815` | `done` | [llama1b_bm25_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/llama1b_bm25_devset.md) |
| Best rewrite wave result | `bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset` | `NDCG@20 0.1092` | `done` | [bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md) |
| Best offline hybrid so far | `RRF(bm25_with_tags, dense_qwen3_8b)` | `NDCG@20 0.1072` | `analyzed` | [retrieval_analysis_findings_2026-04-28.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/retrieval_analysis_findings_2026-04-28.md) |
| Best v0+ ConversationState compiler (BM25-only) | `v0plus_compiler_devset` | `NDCG@20 0.1005` | `superseded` | [v0plus_compiler_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_compiler_devset.md) |
| **Best v0+ retrieval overall (multimodal)** | `v0plus_compiler_image_devset` | `NDCG@20 0.1461` | `analyzed` | [v0plus_compiler_ablation_2026-05-26.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_compiler_ablation_2026-05-26.md) |
| Best v0+ candidate coverage (Hit@1000) | `v0plus_compiler_all_devset` | `Hit@1000 0.6730` | `analyzed` | [v0plus_compiler_ablation_2026-05-26.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_compiler_ablation_2026-05-26.md) |

## Current Active Work

| Workstream | Status | Where to read |
|---|---|---|
| v0+ compiler multimodal embedding ablation | `analyzed` | [v0plus_compiler_ablation_2026-05-26.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_compiler_ablation_2026-05-26.md) |
| Cross-encoder reranker over top-200 (attacks novel-artist gap) | `planned` | [experiment_log.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/experiment_log.md) |
| Hybrid sparse+dense retrieval follow-up | `planned` | [experiment_log.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/experiment_log.md) |
| Conversation-aware query representation direction | `analyzed` | [analysis/query_intent_v1/README.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/query_intent_v1/README.md) |
| Milvus native sparse retrieval evaluation | `analyzed` | [milvus_bm25_with_tag_list_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/milvus_bm25_with_tag_list_devset.md) |
| LanceDB CPU FTS retrieval evaluation | `done` | [lancedb_fts_with_tag_list_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/lancedb_fts_with_tag_list_devset.md) |

## Analysis

- [analysis/README.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/README.md) tracks packaged analysis work and linked artifacts.
- [query_intent_v1](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/query_intent_v1/README.md) is the current conversation-intent analysis package with labeling artifacts and retrieval implications.
- [conversation_state_extraction_bakeoff](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/conversation_state_extraction_bakeoff/README.md) ([`analyzed`](README.md), 3 iteration rounds) picked `google/gemma-3-12b-it` as the v0+ ConversationState extractor — 0.812 F1 vs Opus 4.7 hand labels, 100% schema validity via strict json_schema, $1.86 full-devset cost. See [`analysis.md`](analysis/conversation_state_extraction_bakeoff/analysis.md) for the long-form methodology + caveats writeup.
- [conversation_state_compiler_v0plus](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/conversation_state_compiler_v0plus/README.md) (`planned`) is the design doc for the v0+ retrieval compiler — 3-branch fusion (BM25 + dense-text + entity-probe), with per-field mapping table, pseudocode, and 6 open questions for review.
- [retrieval_analysis_findings_2026-04-28.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/retrieval_analysis_findings_2026-04-28.md) is a top-level experiment note because it summarizes cross-run hybrid diagnostics rather than a self-contained artifact package.

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

### Wave 5: Milvus Retrieval

- [milvus_bm25_with_tag_list_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/milvus_bm25_with_tag_list_devset.md)

### Wave 6: LanceDB Retrieval

- [lancedb_fts_with_tag_list_devset.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/lancedb_fts_with_tag_list_devset.md)

## Conventions

- One per-run report per file: `experiments/{tid}.md`
- Cross-run conclusions go in [experiment_log.md](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/experiment_log.md)
- Packaged analyses live at `experiments/analysis/<analysis_name>/README.md`
- Analysis artifacts live beside their analysis README in a local artifact subdirectory
- Retrieval comparison and hybrid notebook work belongs in [notebooks/retrieval_analysis.ipynb](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/notebooks/retrieval_analysis.ipynb)
- LanceDB local indexing, Modal upload, and Modal smoke-test notebook work belongs in [notebooks/05_lancedb_indexing.ipynb](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/notebooks/05_lancedb_indexing.ipynb)
