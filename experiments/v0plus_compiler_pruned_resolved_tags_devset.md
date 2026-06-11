# Experiment: v0plus_compiler_pruned_resolved_tags_devset

**Date:** 2026-06-11
**Config:** `configs/v0plus_compiler_pruned_resolved_tags_devset.yaml`
**Run:** full devset, 1000 sessions / 8000 turns, 5 Modal shards.

## What this config is

`v0plus_compiler_all_retrievers_devset` with two changes, each validated on
paired seeded smokes (50 then 100 sessions — see
[seed50_paired_smoke_matrix.md](seed50_paired_smoke_matrix.md)):

1. **Branch pruning** — duplicate Qwen 0.6B dense branches removed (0.6B keeps
   lyrics only; 8B owns metadata/attributes; CLAP keeps one text branch).
   Paired effect: +0.0137 ndcg@20, t=3.1, 43/13 hit@20 flips on 800 turns.
2. **Tiered tag resolver** (`bm25_v1_attribute_tag_policy: "resolved"`) —
   attribute phrases ground to catalog tags (exact → alias → substring →
   embedding); unresolved phrases keep raw text. Retrieval-neutral (paired
   +0.0006); kept for the per-fact `(tag, score, tier)` resolution metadata
   feeding the trained-ranker workstream.

## Ranking Quality

| Metric | Value | all_retrievers | Δ |
|---|---:|---:|---:|
| NDCG@20 | **0.1374** | 0.1255 | **+0.0119 (+9.5%)** |
| MRR | 0.0987 | 0.0897 | +0.0090 |

## Retrieval Coverage

| Metric | Value | all_retrievers | Δ |
|---|---:|---:|---:|
| Hit@20 | 0.2931 | 0.2742 | +0.0189 |
| Hit@100 | 0.4632 | — | — |
| Hit@1000 | 0.6980 | 0.7289 | −0.0309 |

## Branch Union Coverage

| Metric | Value |
|---|---:|
| union@20 | 0.4305 |
| union@100 | 0.6260 |
| union@200 | 0.7219 |
| union@1000 | 0.8926 |
| fusion_efficiency@20 | 0.6809 |
| fusion_efficiency@1000 | 0.7820 |

union@1000 0.8926 vs all_retrievers 0.905: the pruning costs ~1pp of deep
union on the full devset — far less than the 3pp seen on smoke slices.

## Per-Turn Breakdown (NDCG@20)

| Turn | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| NDCG@20 | 0.159 | 0.205 | 0.167 | 0.137 | 0.122 | 0.109 | 0.102 | 0.098 |

Monotonic decline after turn 2 — the established later-turns-harder pattern.

## Verdict

**New ranking baseline.** Strictly dominates `all_retrievers` on head metrics
(+9.5% ndcg@20, +1.9pp hit@20) at ~1pp union cost. vs the retired
`image_devset` anchor (0.1452): −0.008 ndcg@20 but +7.2pp hit@1000 and a full
multi-retriever union pool — the right substrate for the union-pool reranker
(#95), which is where the next step-change lives.

## Files

- Inference: `exp/inference/devset/v0plus_compiler_pruned_resolved_tags_devset.json`
- Scores: `exp/scores/devset/v0plus_compiler_pruned_resolved_tags_devset.json`
- Per-sample: `exp/scores/devset/v0plus_compiler_pruned_resolved_tags_devset_samples.csv`
