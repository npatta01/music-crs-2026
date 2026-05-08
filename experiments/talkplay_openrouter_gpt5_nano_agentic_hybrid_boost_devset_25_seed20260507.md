# Experiment: talkplay_openrouter_gpt5_nano_agentic_hybrid_boost_devset_25_seed20260507

**Date:** 2026-05-07
**Branch:** `talkplay-agentic-hybrid-boost`
**Session subset:** `exp/session_splits/devset_25_seed20260507.json`
**Config:** `config/talkplay_openrouter_gpt5_nano_agentic_hybrid_boost_devset.yaml`

## Goal

Evaluate whether the new agentic hybrid-boost architecture can beat the current best baseline on a fixed 25-session devset slice before running a larger wave.

The comparison in this report is apples-to-apples on the same 25 sessions:

- Best baseline: `bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset`
- New approach: `talkplay_openrouter_gpt5_nano_agentic_hybrid_boost_devset`

## Architecture

### Best baseline

- Query understanding: `llm_rewrite`
- Rewriter model: `google/gemma-4-E2B-it`
- Retrieval: `bm25`
- Retrieval depth: `1000`
- Output depth: top `20`

This path rewrites the multi-turn conversation into a stronger lexical query, then does deep BM25 retrieval over title, artist, album, and tag fields.

### New approach

- Pipeline: `agentic`
- Planner model: `openai/gpt-5-nano`
- Planner contract: `structured_retrieval_bm25_boost`
- Retrieval tools enabled:
  - `bm25_search`
  - `text_to_item_similarity`
  - `item_to_item_similarity`
  - `user_to_item_similarity`
- Retrieval depth: top `20`
- Optional second stage: pool-restricted `bm25_boost`

The planner sees the conversation history and current user turn, then returns:

1. one retrieval choice
2. optional BM25 boost over the retrieved pool

The runtime executes retrieval locally and, if requested, reranks the retrieved pool with BM25. It does not retrieve a fresh catalog-wide list in stage 2.

## Fixed 25-Session Comparison

### Ranking quality

| Run | NDCG@10 | NDCG@20 | MRR |
|---|---:|---:|---:|
| `bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset` | `0.0714` | `0.0982` | `0.0543` |
| `talkplay_openrouter_gpt5_nano_agentic_hybrid_boost_devset_25_seed20260507` | `0.0284` | `0.0373` | `0.0217` |

### Retrieval coverage

| Run | Hit@10 | Hit@20 | % GT not in top-20 |
|---|---:|---:|---:|
| `bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset` | `0.1650` | `0.2700` | `73.0%` |
| `talkplay_openrouter_gpt5_nano_agentic_hybrid_boost_devset_25_seed20260507` | `0.0600` | `0.0950` | `90.5%` |

### Gap

- `NDCG@20`: `0.0373` vs `0.0982` (`-0.0609`)
- `Hit@20`: `0.0950` vs `0.2700` (`-0.1750`)
- `MRR`: `0.0217` vs `0.0543` (`-0.0326`)

## New Approach Operational Notes

- The 25-session run was executed as `5` shards × `5` sessions and merged after completion.
- Aggregate new-run health on the 25-session slice:
  - `200` turns evaluated
  - `7` fallbacks
  - `45` repair retries
- Final ranking source:
  - `193/200` turns were `retrieval_only`
  - `7/200` turns fell back
- Retrieval mode mix:
  - `126` `text_to_item_similarity`
  - `66` `bm25_search`
  - `1` `item_to_item_similarity`
  - `7` fallback/no retrieval mode

## Interpretation

The new architecture looks stronger on paper, but it is currently weaker as a retrieval system on this benchmark.

Why it underperforms:

- The best baseline rewrites the query and then retrieves a deep `1000`-item BM25 pool, which is a strong fit for this dataset.
- The new approach usually ends as `retrieval_only`, so the optional hybrid stage rarely rescues a weak first-stage choice.
- The planner overuses `text_to_item_similarity` relative to BM25 for a benchmark where lexical/entity carryover appears highly valuable.
- The new path starts from a top-20 pool, so there is much less room to recover if the first retrieval decision is wrong.

This subset result suggests the current hybrid-boost agentic path is not yet competitive with the best rewrite-wave baseline.

## Files

- Session subset: `exp/session_splits/devset_25_seed20260507.json`
- New merged predictions: `exp/inference/devset/talkplay_openrouter_gpt5_nano_agentic_hybrid_boost_devset_25_seed20260507.json`
- New merged trace: `exp/inference/devset/talkplay_openrouter_gpt5_nano_agentic_hybrid_boost_devset_25_seed20260507_trace.json`
- New scores: `exp/scores/devset/talkplay_openrouter_gpt5_nano_agentic_hybrid_boost_devset_25_seed20260507.json`
- New per-sample metrics: `exp/scores/devset/talkplay_openrouter_gpt5_nano_agentic_hybrid_boost_devset_25_seed20260507_samples.csv`
- Baseline predictions used for subset scoring: `exp/inference/devset/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.json`
- Baseline scores on the same subset: `exp/scores/devset/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.json`
