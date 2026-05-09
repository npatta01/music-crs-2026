# Experiment: talkplay_openrouter_qwen35_9b_agentic_hardened_devset_full

**Date:** 2026-05-06
**Config:** `config/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_full.yaml`

## Configuration

| Field | Value |
|---|---|
| pipeline_type | agentic |
| planner_backend | litellm_chat_completions |
| planner_model_name | `openai/qwen3.5-9b` |
| lm_type | dummy |
| retrieval_type | bm25 |
| qu_type | passthrough |
| retrieval_topk | 20 |
| planner_protocol | structured_two_step_plan |
| prediction_depth | 20 |
| planner_max_tokens | 8192 |
| enabled_tools | `sql_filter`, `bm25_search`, `text_to_item_similarity`, `item_to_item_similarity`, `user_to_item_similarity` |
| dense embedding model | `openai/text-embedding-3-small` |

## Ranking Quality

| Metric | Value |
|---|---|
| NDCG@1 | 0.0120 |
| NDCG@5 | 0.0199 |
| NDCG@10 | 0.0236 |
| NDCG@20 | 0.0262 |
| NDCG@50 | N/A |
| NDCG@100 | N/A |
| NDCG@200 | N/A |
| NDCG@500 | N/A |
| NDCG@1000 | N/A |
| MRR | 0.0196 |
| MRR@100 | N/A |
| MRR@200 | N/A |
| MRR@500 | N/A |
| MRR@1000 | N/A |

## Retrieval Coverage

| Metric | Value |
|---|---|
| Hit@1 | 0.0120 |
| Hit@5 | 0.0278 |
| Hit@10 | 0.0393 |
| Hit@20 | 0.0494 |
| Hit@50 | N/A |
| Hit@100 | N/A |
| Hit@200 | N/A |
| Hit@500 | N/A |
| Hit@1000 | N/A |
| % GT not in top-20 | 95.1% |
| % GT not in top-100 | N/A |
| % GT not in top-200 | N/A |
| % GT not in top-500 | N/A |
| % GT not in top-1000 | N/A |
| Mean rank (when found) | 6.2 |
| Median rank (when found) | 5.0 |

## Diversity

| Metric | Value |
|---|---|
| Catalog diversity @20 | 0.3859 |
| Catalog diversity @100 | 0.3859 |
| Lexical diversity | 0.0000 |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---|---|---|---|---|
| 1 | 0.0660 | 0.1060 | N/A | 1000 |
| 2 | 0.0471 | 0.0820 | N/A | 1000 |
| 3 | 0.0272 | 0.0560 | N/A | 1000 |
| 4 | 0.0160 | 0.0370 | N/A | 1000 |
| 5 | 0.0153 | 0.0310 | N/A | 1000 |
| 6 | 0.0179 | 0.0340 | N/A | 1000 |
| 7 | 0.0088 | 0.0220 | N/A | 1000 |
| 8 | 0.0110 | 0.0270 | N/A | 1000 |

## Operational Notes

- Full devset completed as `40` shards x `25` sessions.
- Aggregate run health was clean: `1000` sessions, `8000` turns, `0` fallbacks, `0` repairs.
- This is a shallow top-20 run, so deeper diagnostic metrics beyond `@20` are intentionally unavailable under the relaxed evaluator contract.
- The dominant successful tool pattern during smoke and shard checks was `text_to_item_similarity -> sql_filter`, with `bm25_search -> sql_filter` as the main cheaper alternative.

## Comparison To Best So Far

- Against the current best rewrite-wave run `bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset` (`NDCG@20 0.1092`), this agentic qwen run is lower by `0.0830` absolute.
- Against the best dense retrieval-only run `dense_qwen3_embedding_8b_devset` (`NDCG@20 0.1025`), it is lower by `0.0763` absolute.
- Against the best sparse retrieval-only run `bm25_devset_retrieval_only_with_tag_list` (`NDCG@20 0.0970`), it is lower by `0.0708` absolute.
- Against the generative baseline `llama1b_bm25_devset` (`NDCG@20 0.0815`), it is lower by `0.0553` absolute.
- The main positive result here is runtime reliability, not ranking quality: the hardened structured-output agentic path reached `0` fallbacks over the full devset.

## Files

- Inference predictions: `exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_full.json`
- Inference trace: `exp/inference/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_full_trace.json`
- Aggregate scores: `exp/scores/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_full.json`
- Per-sample metrics: `exp/scores/devset/talkplay_openrouter_qwen35_9b_agentic_hardened_devset_full_samples.csv`
