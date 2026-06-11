# Seed-50 Paired Smoke Matrix (2026-06-10)

Five configs run on the **identical seeded 50-session devset slice** (400 turns,
`SUBSET_RANDOM_SEED` via `run_experiment.py --num_sessions 50`; subset files
verified byte-identical). Paired per-turn stats computed from
`exp/scores/devset/*_samples.csv`.

**Why this exists:** comparing smoke slices against the full-devset baseline
number is invalid — this slice is harder than average (control scores 0.1012
here vs 0.1255 on the full devset). All deltas below are paired, same-turn.

## Results

| config | ndcg@20 | hit@20 | hit@1000 | mrr | union@20 | union@100 | union@1000 | fus_eff@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `all_retrievers_smoke50` (control) | 0.1012 | 0.225 | 0.638 | 0.072 | **0.433** | **0.620** | **0.898** | 0.520 |
| `safe_tags_bm25` (all branches + catalog_exact) | 0.0974 | 0.215 | 0.625 | 0.070 | 0.418 | 0.615 | 0.893 | 0.515 |
| `pruned` (dedup 0.6B branches) | 0.1177 | 0.270 | 0.663 | 0.080 | 0.393 | 0.583 | 0.863 | 0.688 |
| `pruned_safe_tags` (pruned + catalog_exact) | 0.1133 | 0.258 | 0.655 | 0.078 | 0.385 | 0.580 | 0.850 | 0.669 |
| `pruned_resolved_tags` (pruned + tiered resolver) | **0.1189** | **0.273** | 0.660 | **0.081** | 0.390 | 0.585 | 0.863 | **0.699** |

## Paired per-turn deltas (n=400)

| comparison | Δndcg@20 | t | hit@20 flips w/l |
|---|---:|---:|---:|
| safe_tags_bm25 vs control | −0.0039 | −1.78 | 2/6 |
| pruned vs control | **+0.0165** | **+2.36** | **26/8** |
| pruned_safe_tags vs control | +0.0121 | +1.74 | 21/8 |
| pruned_resolved_tags vs pruned | +0.0012 | +0.83 | 2/1 |

## Conclusions

1. **Branch pruning is the win** (+16% ndcg@20, t=2.36, 26/8 flips). The
   duplicate Qwen 0.6B dense branches were RRF dilution: fusion efficiency
   0.52 → 0.69, and even final-list hit@1000 improves despite the thinner
   union pool. (Verified: `enable_similar_artist_anchors: true` is set in
   BOTH configs — the delta is purely branch dedup, no bundled confound.)
2. **`catalog_exact` is a consistent small regression** (−0.004 in both
   contexts). Dropping unmatched attribute phrases loses BM25 token-level
   recall. Policy retired.
3. **The tiered resolver (`resolved` policy) is neutral on retrieval**
   (+0.0012, t=0.83) — it repairs catalog_exact's signal loss (substitution +
   raw-text fallback) but tag-clause grounding is not a score lever, matching
   the tag-concept-grounding finding. Its payload is the per-fact
   `(tag, score, tier)` resolution metadata for trained-ranker features.
   Fire-rate on real phrases (focused-110, 271 unique): exact 43% /
   substring 54% / embedding 3% / unresolved 0% → LLM resolution tier not
   worth building; consider `embedding_min_score` 0.60 → 0.85 (junk matches
   all scored ≤0.81 in the small sample; re-verify on a random slice).
4. **Union cost of pruning is real** (−4pp union@20, −3.5pp union@1000).
   For the union-pool reranker workstream, `all_retrievers` remains the
   candidate-generation config; pruned is the production-ranking config.

## Next

- 100-session (800-turn) rerun of control / pruned / pruned_resolved_tags
  in flight for tighter confidence intervals.
- Full-devset confirmation run of `pruned` (and/or `pruned_resolved_tags`)
  vs the 0.1255 all_retrievers baseline — **needs owner approval**.
- Trained ranker over the union pool remains the primary score lever;
  resolver metadata feeds its tag-overlap features.

## 100-Session Confirmation (800 turns, 2026-06-10)

Same three-way comparison rerun at `--num_sessions 100` (seeded, all arms
byte-identical sessions; seed-50 artifacts preserved in
`exp/scores/devset/seed50_backup/`).

| config | ndcg@20 | hit@20 | hit@1000 | mrr | union@20 | union@100 | union@1000 | fus_eff@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| control (all_retrievers) | 0.1129 | 0.2413 | 0.6538 | 0.0815 | 0.4263 | 0.6300 | 0.9075 | 0.5660 |
| pruned | 0.1266 | 0.2787 | 0.6775 | 0.0886 | 0.3875 | 0.5900 | 0.8800 | 0.7194 |
| pruned_resolved_tags | **0.1273** | 0.2775 | **0.6800** | **0.0899** | 0.3875 | 0.5913 | 0.8788 | 0.7161 |

| paired comparison (n=800) | Δndcg@20 | t | hit@20 flips w/l |
|---|---:|---:|---:|
| pruned vs control | +0.0137 | **+3.10** | **43/13** |
| pruned_resolved vs control | +0.0144 | **+3.20** | 43/14 |
| pruned_resolved vs pruned | +0.0006 | +0.68 | 2/3 |

**Pruning confirmed (t=3.1, p<0.002).** Resolver neutral, confirmed. The
100-session slice tracks full-devset difficulty more closely (control 0.1129
vs 0.1255 full) → projected full-devset pruned ≈ 0.139. Promotion candidate:
`pruned_resolved_tags` (statistically identical to pruned, ships per-fact
tag-resolution metadata for the trained-ranker workstream).
