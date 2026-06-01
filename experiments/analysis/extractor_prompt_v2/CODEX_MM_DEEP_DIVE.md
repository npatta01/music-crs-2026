<!--
Provenance: Independent multimodal deep-dive of `v0plus_compiler_mm_extractor_v3_devset`,
produced by a separate Codex review pass (source: /private/tmp/mm_deep_dive_summary.md, 2026-05-30).
Preserved here verbatim as the canonical code-grounded companion to RECALL_GAP_REPORT.md.

Relationship to RECALL_GAP_REPORT.md:
  - §10 of the recall-gap report folds in the cross-analysis additions from this pass.
  - §11 ("Code-grounded deep-dive reconciliation") reconciles the corrections this pass
    surfaced (bm25 unique-contribution 2169→1015; lyrics not out-of-scope; the top-100
    coverage reframe; the resolver-does-not-ground-positive-mentions root cause; tag-branch
    demotion; coverage-first priority order).

All numbers below are the reviewer's; where they overlap RECALL_GAP_REPORT.md they match
within rounding (fused Hit@1000 0.641, branch union@1000 0.780, fusion-loss 0.139,
never-reach 0.220).
-->

# Codex multimodal deep-dive (preserved verbatim)

# Deep dive: v0plus_compiler_mm_extractor_v3_devset

## Overall

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 8000 | 0.406 | 0.526 | 0.120 | 0.641 | 0.780 | 0.139 | 0.220 |


Failure accounting: final_hit1000=5128, no_branch_top1000=1761, rrf_lost_branch_pool_hit=1111, lost_union100_to_final100=998


## Recommended next step

Primary objective: **make at least one retriever/action branch bring the GT into top 100 as often as possible.** Do not optimize RRF or a final reranker first. The current final Hit@100 is `0.406`; branch union@100 is only `0.526`, so the first ceiling to raise is branch/action coverage.

The work should be framed as an action-retrieval loop:

1. **LLM extracts action state** from blind-safe conversation context.
2. **Resolver grounds LLM-emitted spans** to catalog IDs. The LLM decides conversational role/exactness; resolver only maps spans to IDs.
3. **Compiler emits explicit retriever actions** from the state.
4. **Each action/retriever is scored independently** for Hit@20/50/100/1000.
5. **Only after branch Hit@100 improves**, use fusion/reranking to prefer the best branch candidates.

Success metric for the next experiment:

| metric | why it matters |
| --- | --- |
| per-action `Hit@100` | tells whether the state/action created a useful retriever, independent of fusion |
| branch union@100 / any-action top100 | main recall target before reranking |
| candidate-pool size sent to VRank | VRank may be capped around `<=1000`; selected branch unions must stay compact enough to rerank |
| movement out of `no_branch_top100` | proves new actions create coverage, not just reshuffle known candidates |
| branch top25 when available | tells whether the action is already strong enough for top-20 reranking |
| final Hit@20 / NDCG@20 | secondary until branch/action recall is healthy |

Candidate-budget constraint: assume we may not be able to send more than roughly `1000` candidates to VRank. This makes `union@1000` a diagnostic ceiling, not the target operating point. The practical target is **high any-action/selected-union Hit@100 with a selected candidate pool <=1000**.

There is no real disagreement with the desired direction: **state + better information + retrievers should be used to raise branch Hit@100.** The main caution is scope/order: state fields are only valuable if the compiler converts them into actions whose individual branches can retrieve the GT near the top and whose selected union stays within the VRank budget. A field that only helps after all retrievers find the GT at rank 700 is less valuable than a field/action that moves it into top100.


## Turn / history

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1000 | 0.370 | 0.383 | 0.013 | 0.549 | 0.598 | 0.049 | 0.402 |
| 2 | 1000 | 0.536 | 0.602 | 0.066 | 0.728 | 0.842 | 0.114 | 0.158 |
| 3 | 1000 | 0.474 | 0.581 | 0.107 | 0.692 | 0.815 | 0.123 | 0.185 |
| 4 | 1000 | 0.426 | 0.539 | 0.113 | 0.670 | 0.820 | 0.150 | 0.180 |
| 5 | 1000 | 0.393 | 0.540 | 0.147 | 0.634 | 0.781 | 0.147 | 0.219 |
| 6 | 1000 | 0.358 | 0.522 | 0.164 | 0.645 | 0.804 | 0.159 | 0.196 |
| 7 | 1000 | 0.339 | 0.518 | 0.179 | 0.615 | 0.788 | 0.173 | 0.212 |
| 8 | 1000 | 0.350 | 0.523 | 0.173 | 0.595 | 0.791 | 0.196 | 0.209 |


### History/state bridges

#### GT artist in prior played history

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| novel_artist | 4777 | 0.229 | 0.299 | 0.070 | 0.486 | 0.663 | 0.177 | 0.337 |
| prev_artist_match | 3223 | 0.667 | 0.862 | 0.195 | 0.871 | 0.953 | 0.082 | 0.047 |

#### GT artist captured by extracted state

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_state_artist_match | 5654 | 0.226 | 0.342 | 0.116 | 0.505 | 0.689 | 0.184 | 0.311 |
| state_artist_match | 2346 | 0.839 | 0.969 | 0.130 | 0.968 | 0.998 | 0.030 | 0.002 |

`no_state_artist_match` means the extracted state did not contain a positive artist matching the GT artist. It does not necessarily mean the GT artist was absent from the visible conversation.

#### State artist match vs visible GT artist in prefix

Visible prefix here means allowed inference context: current/prior user text, prior assistant text, and prior played-track artist metadata.

| value | n | hit100 | union50 | union100 | union1000 | interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| state_match+visible | 2343 | 0.839 | 0.934 | 0.969 | 0.998 | state carried the visible artist bridge |
| state_match+not_visible | 3 | 0.667 | 1.000 | 1.000 | 1.000 | matcher noise / unusual alias case |
| no_state+visible | 1335 | 0.395 | 0.603 | 0.662 | 0.875 | actionable extractor/resolver miss plus top-K conversion |
| no_state+not_visible | 4319 | 0.174 | 0.164 | 0.243 | 0.632 | artist branch cannot help directly |

#### No-state artist cross-section facets

Common-facet read:

- `no_state+visible` is mostly a **late-turn/history-carryover** bucket. In `92.1%` of these rows, a prior played track has the GT artist; in `85.6%`, prior assistant text mentions the GT artist. The problem is usually not "artist absent"; it is state/resolver/query construction failing to carry or exploit the visible artist bridge.
- `no_state+not_visible` is mostly a **true novel/no-visible-artist** bucket. Artist-resolver work cannot directly help; it needs tag, mood/audio, lyrics/theme, popularity, user-CF, and anchor-free semantic retrievers.
- These buckets have different highest-impact fixes:
  - `no_state+visible`: branch coverage is already decent, but final ranking underuses it. Recomputed branch-cutoff view: final Hit@100 `0.395`, union@50 `0.603`, union@100 `0.662`, union@1000 `0.875`. Biggest impact is state/resolver carryover plus compiler/reranker conversion. There is a `+0.267` union-minus-final gap at @100.
  - `no_state+not_visible`: branch coverage is the bottleneck. Recomputed branch-cutoff view: final Hit@100 `0.174`, union@50 `0.164`, union@100 `0.243`, union@1000 `0.632`. Biggest impact is new non-artist retrieval. `75.7%` of these rows have no current retriever top100 and `36.8%` have no current retriever top1000.

| group | n | hit100 | union50 | union100 | union1000 | gap100 | no_branch100 | no_branch1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| state_match | 2346 | 0.839 | 0.934 | 0.969 | 0.998 | 0.130 | 0.031 | 0.002 |
| no_state_visible | 1335 | 0.395 | 0.603 | 0.662 | 0.875 | 0.267 | 0.338 | 0.125 |
| no_state_not_visible | 4319 | 0.174 | 0.164 | 0.243 | 0.632 | 0.069 | 0.757 | 0.368 |

Where the visible GT artist came from within `no_state+visible`:

| source | n | share | hit100 | union50 | union100 | union1000 | gap100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| user text prefix | 768 | 0.575 | 0.352 | 0.581 | 0.646 | 0.868 | 0.294 |
| assistant text prefix | 1143 | 0.856 | 0.369 | 0.597 | 0.657 | 0.871 | 0.288 |
| prior played same artist | 1229 | 0.921 | 0.395 | 0.620 | 0.677 | 0.879 | 0.282 |

Branch profile split:

| branch profile | no_state_visible n/share/h100/u50/u100/h1000/u1000 | no_state_not_visible n/share/h100/u50/u100/h1000/u1000 |
| --- | --- | --- |
| bm25+nonbm | 674 / 0.505 / 0.582 / 0.803 / 0.856 / 0.912 / 1.000 | 1041 / 0.241 / 0.499 / 0.419 / 0.584 / 0.929 / 1.000 |
| bm25_only | 115 / 0.086 / 0.070 / 0.226 / 0.348 / 0.443 / 1.000 | 724 / 0.168 / 0.167 / 0.153 / 0.262 / 0.623 / 1.000 |
| nonbm_only | 378 / 0.283 / 0.336 / 0.630 / 0.706 / 0.754 / 1.000 | 966 / 0.224 / 0.115 / 0.167 / 0.261 / 0.506 / 1.000 |
| no_branch_top1000 | 168 / 0.126 / 0.000 / 0.000 / 0.000 / 0.000 / 0.000 | 1588 / 0.368 / 0.000 / 0.000 / 0.000 / 0.000 / 0.000 |

Intent/policy split with branch union cutoffs:

| facet | no_state_visible n/share/u100/u1000/no1000 | no_state_not_visible n/share/u100/u1000/no1000 |
| --- | --- | --- |
| refinement | 907 / 0.679 / 0.711 / 0.908 / 0.092 | 2546 / 0.589 / 0.257 / 0.679 / 0.321 |
| open_explore | 51 / 0.038 / 0.824 / 0.961 / 0.039 | 789 / 0.183 / 0.183 / 0.473 / 0.527 |
| pivot | 192 / 0.144 / 0.333 / 0.615 / 0.385 | 349 / 0.081 / 0.146 / 0.344 / 0.656 |
| playlist_build | 183 / 0.137 / 0.727 / 0.967 / 0.033 | 633 / 0.147 / 0.316 / 0.801 / 0.199 |
| diversify_artists policy | 867 / 0.649 / 0.623 / 0.858 / 0.142 | 2319 / 0.537 / 0.256 / 0.661 / 0.339 |
| balanced policy | 404 / 0.303 / 0.740 / 0.913 / 0.087 | 1877 / 0.435 / 0.227 / 0.598 / 0.402 |

GT-tag overlap remains useful even when the GT artist is not visible:

| tag overlap | no_state_visible n/share/u100/u1000/no1000 | no_state_not_visible n/share/u100/u1000/no1000 |
| --- | --- | --- |
| 0 | 264 / 0.198 / 0.655 / 0.807 / 0.193 | 906 / 0.210 / 0.162 / 0.421 / 0.579 |
| 1 | 332 / 0.249 / 0.584 / 0.828 / 0.172 | 1215 / 0.281 / 0.165 / 0.557 / 0.443 |
| 2+ | 739 / 0.554 / 0.700 / 0.920 / 0.080 | 2198 / 0.509 / 0.319 / 0.761 / 0.239 |

Implications:

- `no_state+visible`: prioritize extractor/resolver audits, deterministic artist branch, recency-aware carryover, and fusion/rerank. This is the bucket where "we missed a visible artist bridge" is real.
- `no_state+not_visible`: prioritize non-artist retrieval, but start with route-specific gaps rather than a generic tag branch. The strongest cheap bets are current-turn/recency BM25, anchor-free dense/current-turn dense, lyrics/theme routing, popularity-routed retrieval, and then a tag-path audit if the existing tag paths are proven weak.

#### GT track captured by extracted state

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_state_track_match | 7911 | 0.399 | 0.521 | 0.121 | 0.637 | 0.777 | 0.140 | 0.223 |
| state_track_match | 89 | 0.978 | 1.000 | 0.022 | 0.989 | 1.000 | 0.011 | 0.000 |

#### Extracted positive-tag token overlap with GT catalog tags

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1457 | 0.395 | 0.502 | 0.107 | 0.555 | 0.660 | 0.105 | 0.340 |
| 1 | 1523 | 0.292 | 0.406 | 0.114 | 0.508 | 0.668 | 0.160 | 0.332 |
| 2+ | 5020 | 0.443 | 0.570 | 0.126 | 0.706 | 0.849 | 0.142 | 0.151 |

#### Number of extracted positive tags

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 317 | 0.631 | 0.672 | 0.041 | 0.716 | 0.770 | 0.054 | 0.230 |
| 1-2 | 300 | 0.553 | 0.573 | 0.020 | 0.630 | 0.693 | 0.063 | 0.307 |
| 3-5 | 2427 | 0.412 | 0.497 | 0.085 | 0.610 | 0.735 | 0.124 | 0.265 |
| 6+ | 4956 | 0.380 | 0.528 | 0.149 | 0.652 | 0.808 | 0.156 | 0.192 |

#### Number of extracted anchor artists

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2698 | 0.281 | 0.398 | 0.117 | 0.547 | 0.685 | 0.139 | 0.315 |
| 1 | 4276 | 0.498 | 0.609 | 0.110 | 0.703 | 0.837 | 0.133 | 0.163 |
| 2+ | 1026 | 0.348 | 0.518 | 0.170 | 0.629 | 0.791 | 0.163 | 0.209 |

Interpretation caveat: these count tables are useful for extractor health, but misleading as success metrics. They answer "did the state contain artists/tags?", not "did the compiler turn those fields into an action that retrieved the GT?" The primary retrieval-development slice should be session/turns where **no retriever** brings the GT into top 100 or top 1000.

#### Extracted fields inside hard branch-coverage failures

Branch-coverage buckets:

- `branch_top100`: at least one retriever has GT rank <= 100 (`4208` turns).
- `branch_101_1000`: no retriever has GT top100, but some retriever has GT rank 101-1000 (`2031` turns).
- `no_branch_top1000`: no retriever has GT in top1000 (`1761` turns).
- `no_branch_top100`: `branch_101_1000 + no_branch_top1000 = 3792` turns. This is the main action/retriever construction bucket.

Anchor-artist counts within these hard failures:

| extracted anchor artists | total n | no branch top100 n / rate | branch 101-1000 n | no branch top1000 n / rate |
| --- | ---: | ---: | ---: | ---: |
| 0 | 2698 | 1623 / 0.602 | 774 | 849 / 0.315 |
| 1 | 4276 | 1674 / 0.391 | 976 | 698 / 0.163 |
| 2+ | 1026 | 495 / 0.482 | 281 | 214 / 0.209 |

Positive-tag counts within these hard failures:

| extracted positive tags | total n | no branch top100 n / rate | branch 101-1000 n | no branch top1000 n / rate |
| --- | ---: | ---: | ---: | ---: |
| 0 | 317 | 104 / 0.328 | 31 | 73 / 0.230 |
| 1-2 | 300 | 128 / 0.427 | 36 | 92 / 0.307 |
| 3-5 | 2427 | 1221 / 0.503 | 577 | 644 / 0.265 |
| 6+ | 4956 | 2339 / 0.472 | 1387 | 952 / 0.192 |

This is the better use of artist/tag counts: not as standalone predictors, but as descriptors of the hard failures. Example: `6+` extracted tags still contains `2339` no-branch-top100 turns, so the action question is whether the existing tag paths are missing the GT entirely, being diluted by broad tags, or retrieving it but losing it in fusion.

#### Number of prior played tracks in history

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1000 | 0.370 | 0.383 | 0.013 | 0.549 | 0.598 | 0.049 | 0.402 |
| 1-2 | 2000 | 0.505 | 0.592 | 0.087 | 0.710 | 0.829 | 0.118 | 0.172 |
| 3-5 | 3000 | 0.392 | 0.534 | 0.141 | 0.650 | 0.802 | 0.152 | 0.198 |
| 6-7 | 2000 | 0.344 | 0.520 | 0.176 | 0.605 | 0.789 | 0.184 | 0.210 |


## Retrieval/fusion

### Per-retriever GT recall

Each row asks: if we look only at that retriever's own ranking, how often is the GT track inside its top-K?

| retriever | GT present in branch top1000 | Hit@20 | Hit@100 | Hit@1000 |
| --- | ---: | ---: | ---: | ---: |
| `bm25` | 4872 | 0.2164 | 0.3807 | 0.6090 |
| `centroid.audio_laion_clap` | 2868 | 0.0469 | 0.1255 | 0.3585 |
| `centroid.cf_bpr` | 2383 | 0.0897 | 0.1741 | 0.2979 |
| `centroid.image_siglip2` | 2816 | 0.2032 | 0.2694 | 0.3520 |
| `dense.intent.metadata_qwen3_embedding_0_6b` | 2797 | 0.1444 | 0.2264 | 0.3496 |

### Branch-union recall

This is the recall ceiling before final RRF truncation if we keep the union of branch candidates. `mean candidate count` / `median candidate count` are the distinct union-pool sizes after taking each branch's top-K.

| union pool | hit n | hit rate | mean candidate count | median candidate count |
| --- | ---: | ---: | ---: | ---: |
| branch union@20 | 2951 | 0.3689 | 72.0 | 81 |
| branch union@25 | 3143 | 0.3929 | 90.6 | 102 |
| branch union@50 | 3705 | 0.4631 | 185.4 | 212 |
| branch union@100 | 4208 | 0.5260 | 380.2 | 436 |
| branch union@1000 | 6239 | 0.7799 | 3729.1 | 4238 |

For comparison, final fused hit rates are Hit@20 `0.2511`, Hit@25 `0.2719`, Hit@50 `0.3423`, Hit@100 `0.4058`, Hit@1000 `0.6410`. The union-minus-final gap is roughly `0.12` at 20-100 and `0.139` at 1000.

### Final fusion profile

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bm25+nonbm | 3857 | 0.725 | 0.853 | 0.127 | 0.955 | 1.000 | 0.045 | 0.000 |
| bm25_only | 1015 | 0.199 | 0.373 | 0.174 | 0.642 | 1.000 | 0.358 | 0.000 |
| no_branch_top1000 | 1761 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| nonbm_only | 1367 | 0.180 | 0.395 | 0.215 | 0.580 | 1.000 | 0.420 | 0.000 |

Additional cross-check from Claude's gap-table analysis: fusion loss appears to be mostly a **single-branch candidate problem**, not an agreement problem. Most dropped GTs are present in only one branch, so simply rewarding cross-branch agreement would likely worsen recall. The right framing is survivor/quota protection plus downstream reranking, not just RRF reweighting.

Also, a small quota of only top `50-100` per branch may not recover deep branch hits at ranks `600-1000`. Quota size should be tuned with branch-rank diagnostics and evaluated at `Hit@1000`, `Hit@100`, `Hit@20`, and `NDCG@20`.


## State controls

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pivot | 727 | 0.210 | 0.385 | 0.175 | 0.433 | 0.582 | 0.149 | 0.418 |
| open_explore | 1093 | 0.379 | 0.394 | 0.016 | 0.558 | 0.618 | 0.059 | 0.382 |
| refinement | 4753 | 0.398 | 0.541 | 0.142 | 0.650 | 0.810 | 0.160 | 0.190 |
| playlist_build | 1423 | 0.552 | 0.652 | 0.100 | 0.782 | 0.907 | 0.125 | 0.093 |

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| diversify_artists | 4016 | 0.291 | 0.479 | 0.188 | 0.594 | 0.772 | 0.178 | 0.228 |
| balanced | 2896 | 0.398 | 0.455 | 0.057 | 0.606 | 0.727 | 0.122 | 0.273 |
| exploit | 951 | 0.853 | 0.889 | 0.036 | 0.904 | 0.945 | 0.041 | 0.055 |
| diversify_albums | 133 | 0.842 | 0.917 | 0.075 | 0.962 | 0.992 | 0.030 | 0.008 |

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 8000 | 0.406 | 0.526 | 0.120 | 0.641 | 0.780 | 0.139 | 0.220 |

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| has_release_year_range | 2131 | 0.326 | 0.450 | 0.125 | 0.631 | 0.773 | 0.142 | 0.227 |
| no_release_year_range | 5869 | 0.435 | 0.553 | 0.119 | 0.645 | 0.782 | 0.138 | 0.218 |

Cold-start vs late-turn regime note:

- Turn 1 is mostly a **never-reach** problem: no prior anchors, centroid branches do little/none, union@1000 is only `0.598`.
- Later turns become increasingly a **fusion/carryover** problem: branch union stays much higher than the final fused list, while RRF loss grows.
- So there are two different fixes: anchor-free query branches for cold-start/open/pivot, and recall-preserving fusion plus better carryover policy for later turns.


## Organizer fields

### Specificity code legend

`conversation_goal.specificity` is a two-axis code from the organizer goal templates. `L` means low specificity and `H` means high specificity. The first letter describes the **query**; the second letter describes the **target music**.

| code | query specificity | target specificity | practical meaning |
| --- | --- | --- | --- |
| `LL` | low | low | broad query, many acceptable tracks; exploratory search |
| `LH` | low | high | vague query aimed at one/few hidden target tracks |
| `HL` | high | low | detailed query, but still many acceptable tracks |
| `HH` | high | high | explicit/specific query aimed at one/few target tracks |

The generator also uses this to pace the session: `HH` tends to resolve fastest, `LH` latest, with `HL`/`LL` in between.

### Blindset field availability

Verified against `talkpl-ai/TalkPlayData-Challenge-Blind-A`, split `test`, on 2026-05-30:

| field | Blind-A raw HF data | current runner use |
| --- | --- | --- |
| `session_id`, `user_id`, `session_date` | yes | `session_id`, `user_id` only |
| `user_profile` | yes | indirectly through `user_id` -> user metadata |
| `conversation_goal.category` | yes | no |
| `conversation_goal.specificity` | yes | no |
| `conversation_goal.listener_goal` | yes | no |
| `conversations` | yes, prefix up to the current user turn | yes, but only `role` + `content` |
| prior `music` track IDs | yes when prior turns exist | yes, converted to catalog metadata |
| `user.thought` | yes, including current user turns | no |
| `assistant.thought` | yes for prior assistant turns | no |
| `music.thought` | null/absent in Blind-A rows checked | no |
| `goal_progress_assessments` | yes for included turns | no |
| current-turn ground-truth `music` ID | no; withheld | no |

Important caveat: the main public `talkpl-ai/TalkPlayData-Challenge-Dataset` currently exposes only `train` and `test`; Blind-A is a separate dataset (`talkpl-ai/TalkPlayData-Challenge-Blind-A`) with split `test`, not a `blind_a` split on the main dataset. `TalkPlayData-Challenge-Blind-B` was not accessible under that name during this check.

Leakage tiers:

| field | stance |
| --- | --- |
| `conversation_goal.listener_goal/category/specificity` | high leakage risk; use as analyzer/teacher only unless official rules explicitly allow it |
| `conversations[].thought` | highest leakage risk; simulator/private reasoning, analyzer/teacher only |
| `goal_progress_assessments` | high leakage risk; hidden-goal progress label, analyzer/teacher only |
| `user_profile` | low leakage risk; ordinary personalization metadata, likely legitimate if rules allow user metadata |

Verified HF schema note: current `test` and Blind-A rows do **not** expose an `expertise` / `listener_expertise` field; `conversation_goal` has only `category`, `listener_goal`, and `specificity`.

Goal category samples:

- A: find one specific instrumental track from "The Elder Scrolls Online Original Game Soundtrack" remembered by its distinctive orchestral sound, mood, or thematic quality (e.g., a bat

- B: find one specific song remembered by vague lyrical content or story elements

- C: discover multiple songs that have colorful, vibrant visual aesthetics matching upbeat music

- D: play one specific song by exact title and artist

- E: find what specifically they like about a seed song through guided discovery, leading to one key realization

- F: find multiple electronic/dance tracks from the late 90s and early 2000s with specific characteristics (e.g., energetic, downtempo, vocal-focused)

- G: find some positive and uplifting hip-hop tracks to boost my energy and put me in a good mood.

- H: find one specific song by exact artist and title

- I: play a specific globally popular song by exact title and artist

- J: play one specific song that is known for its high popularity within its genre or era.

- K: discover multiple instrumental pieces from a broad era, particularly film scores or contemporary classical works, that evoke a timeless or classic feel.

#### Organizer goal category

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C | 464 | 0.360 | 0.450 | 0.091 | 0.550 | 0.688 | 0.138 | 0.312 |
| I | 144 | 0.368 | 0.458 | 0.090 | 0.569 | 0.674 | 0.104 | 0.326 |
| K | 1248 | 0.349 | 0.473 | 0.124 | 0.609 | 0.760 | 0.151 | 0.240 |
| J | 616 | 0.393 | 0.502 | 0.109 | 0.617 | 0.768 | 0.151 | 0.232 |
| G | 616 | 0.351 | 0.482 | 0.131 | 0.630 | 0.779 | 0.149 | 0.221 |
| B | 1136 | 0.420 | 0.543 | 0.123 | 0.638 | 0.783 | 0.145 | 0.217 |
| D | 688 | 0.403 | 0.520 | 0.118 | 0.645 | 0.786 | 0.141 | 0.214 |
| E | 760 | 0.411 | 0.526 | 0.116 | 0.646 | 0.792 | 0.146 | 0.208 |
| A | 488 | 0.463 | 0.584 | 0.121 | 0.682 | 0.799 | 0.117 | 0.201 |
| H | 1080 | 0.444 | 0.564 | 0.120 | 0.689 | 0.815 | 0.126 | 0.185 |
| F | 760 | 0.476 | 0.616 | 0.139 | 0.692 | 0.813 | 0.121 | 0.187 |

#### Organizer specificity code

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LL | 2224 | 0.344 | 0.464 | 0.121 | 0.595 | 0.742 | 0.147 | 0.258 |
| LH | 2504 | 0.426 | 0.528 | 0.102 | 0.643 | 0.775 | 0.132 | 0.225 |
| HL | 2456 | 0.399 | 0.545 | 0.146 | 0.654 | 0.799 | 0.145 | 0.201 |
| HH | 816 | 0.532 | 0.631 | 0.099 | 0.721 | 0.839 | 0.119 | 0.161 |

#### Organizer goal-progress assessment

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DOES_NOT_MOVE_TOWARD_GOAL | 816 | 0.235 | 0.411 | 0.175 | 0.446 | 0.630 | 0.184 | 0.370 |
| None | 1000 | 0.370 | 0.383 | 0.013 | 0.549 | 0.598 | 0.049 | 0.402 |
| MOVES_TOWARD_GOAL | 6184 | 0.434 | 0.564 | 0.130 | 0.682 | 0.829 | 0.147 | 0.171 |

#### GT track popularity bucket

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20-39 | 1873 | 0.423 | 0.564 | 0.141 | 0.661 | 0.794 | 0.133 | 0.206 |
| 40-59 | 2574 | 0.441 | 0.560 | 0.119 | 0.675 | 0.816 | 0.141 | 0.184 |
| 60+ | 2132 | 0.352 | 0.439 | 0.087 | 0.584 | 0.732 | 0.147 | 0.268 |
| <20 | 1421 | 0.400 | 0.545 | 0.144 | 0.638 | 0.767 | 0.129 | 0.233 |

#### GT artist catalog-size bucket

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1-4 | 1780 | 0.252 | 0.357 | 0.105 | 0.523 | 0.690 | 0.167 | 0.310 |
| 20+ | 3836 | 0.492 | 0.604 | 0.112 | 0.699 | 0.811 | 0.112 | 0.189 |
| 5-19 | 2384 | 0.382 | 0.526 | 0.144 | 0.636 | 0.797 | 0.161 | 0.203 |

#### GT track release decade

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1970s | 380 | 0.339 | 0.426 | 0.087 | 0.584 | 0.724 | 0.139 | 0.276 |
| 2010s | 3457 | 0.382 | 0.510 | 0.129 | 0.599 | 0.750 | 0.151 | 0.250 |
| 2000s | 1991 | 0.426 | 0.547 | 0.121 | 0.662 | 0.787 | 0.124 | 0.213 |
| 1980s | 507 | 0.428 | 0.535 | 0.107 | 0.673 | 0.795 | 0.122 | 0.205 |
| 1990s | 1376 | 0.423 | 0.539 | 0.116 | 0.693 | 0.837 | 0.145 | 0.163 |
| 1960s | 204 | 0.520 | 0.632 | 0.113 | 0.750 | 0.853 | 0.103 | 0.147 |
| 1950s | 62 | 0.500 | 0.597 | 0.097 | 0.790 | 0.887 | 0.097 | 0.113 |


## Organizer music.thought keyword flags

| value | n | hit100 | union100 | gap100 | hit1000 | union1000 | rrf_loss1000 | total_miss1000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| different_or_new_artist | 352 | 0.199 | 0.392 | 0.193 | 0.395 | 0.662 | 0.267 | 0.338 |
| geo_language_culture | 542 | 0.240 | 0.384 | 0.144 | 0.542 | 0.738 | 0.196 | 0.262 |
| pool_limitation | 1073 | 0.384 | 0.550 | 0.166 | 0.568 | 0.731 | 0.163 | 0.269 |
| genre_tag | 5499 | 0.355 | 0.472 | 0.117 | 0.600 | 0.752 | 0.152 | 0.248 |
| era_or_year | 2521 | 0.327 | 0.446 | 0.119 | 0.624 | 0.766 | 0.142 | 0.234 |
| audio_mood_sound | 5244 | 0.375 | 0.502 | 0.127 | 0.625 | 0.773 | 0.148 | 0.227 |
| lyrics_theme | 1969 | 0.390 | 0.527 | 0.138 | 0.629 | 0.786 | 0.157 | 0.214 |
| popularity | 2183 | 0.359 | 0.470 | 0.110 | 0.630 | 0.774 | 0.144 | 0.226 |
| same_or_prior_artist | 1466 | 0.462 | 0.607 | 0.145 | 0.698 | 0.852 | 0.154 | 0.148 |
| explicit_or_exact_request | 2737 | 0.453 | 0.580 | 0.127 | 0.703 | 0.822 | 0.119 | 0.178 |


## Miss reason heuristic counts among final@1000 misses

- novel artist with no exact artist bridge: 1607

- fusion/ranking lost available branch candidate: 1111

- long-tail GT artist (<5 catalog tracks): 551

- zero extracted-tag overlap with GT tags: 496

- organizer rationale mentions lyrics/theme: 421

- popularity-driven rationale / popularity feature weak: 385

- mood/audio wording but no tag overlap: 294

- organizer pool-limitation/closest-fit turn: 289

- explicit new/different artist request: 119


## Cross-check additions from Claude's report

Useful points to carry forward:

- **Named-artist prefix signal:** Claude found a large gap between turns where the GT artist appears in the visible conversation prefix and turns where it does not. This is consistent with the stronger state/history slice here: when the extracted state contains the GT artist, Hit@1000 is `0.969`; when it does not, Hit@1000 is `0.514`.
- **Named but missed is actionable:** a subset of missed turns likely already have the named artist in state or BM25 branch ranks. These are good candidates for a deterministic artist-resolver branch: resolve artist mention -> all catalog tracks by that artist -> protected survivor slots.
- **Exact-tag signal is diagnostic but gold-conditioned:** `tag_overlap` uses GT catalog tags, so it is an upper bound. Because the compiler already uses extracted tags in BM25, dense query text, and post-fusion boosts, the next step is to audit those paths before adding a separate production tag branch.
- **Culture/profile is messy:** `preferred_musical_culture` has large devset spread but is high-cardinality and confounded with goal/genre. Do not build a broad "non-Anglo" boost. At most feed raw culture as a soft personalization feature and validate with A/B.
- **Blind-A is mixed turn depth, not only turn 1:** some rows are cold-start, many are multi-turn. This means both cold-start retrieval and history/carryover remain relevant.
- **Top-K conversion is separate from recall:** protecting branch-union candidates can lift Hit@1000, but `Hit@100`, `Hit@20`, and `NDCG@20` need reranking/fusion validation.

Items to be careful about in Claude's report:

- Some turn-depth numbers in Claude's §6 differ from this trace join. Use the turn table above as the checked values for this report.
- Category B's never/fusion split appears internally inconsistent in Claude's table; use this report's category table.
- Current HF rows checked here do not contain an `expertise` field.


## Current vs ideal state exploitability

### What the current state already captures

The current production-ish v0+/v3-prompt state captures some of the organizer-like information, but mostly as indirect signals rather than explicit `goal_category` or `LL/LH/HL/HH` fields.

| need from analysis | current field(s) | currently exploitable? | gap |
| --- | --- | --- | --- |
| Active user ask | `turn_intent` | yes: BM25/dense query text | free text only; no target granularity |
| Continuation vs pivot | `intent_mode` | yes: anchor centroid mix and pivot anchor dropping | too coarse for lyrics/visual/popularity routing |
| Same-history anchor | `track_feedback`, `referenced_track_ids`, played-track ledger | yes: anchor centroids, tag expansion, hard drop played tracks | no aspect-level "liked melody but not vocals" |
| Named artist/track/tag | `mentioned_entities` | yes: fielded BM25 and dense query additions | current-turn targets and historical references are mixed |
| Era constraints | `hard_filters.release_date` / latest trace `release_year_range` | yes: pre-fusion candidate mask | only release date is structured in v0+ |
| Negative feedback | `explicit_rejections`, rejected `track_feedback` | yes: hard drops and tag/artist demotion | weak for attribute-level rejection |
| Diversify vs exploit | latest trace `process_constraints.exploration_policy` | partially: useful for slicing; not fully routed yet | should directly control same-artist boost/demote and branch weights |
| Goal category (`A`-`K`) | none in safe runtime state | no | must infer from text; raw `conversation_goal` is teacher/analyzer-only |
| Specificity (`LL/LH/HL/HH`) | none in safe runtime state | no | must infer query/target specificity ourselves; raw specificity is teacher/analyzer-only |
| Lyrics / visual / popularity route | mostly buried in `turn_intent` and tags | weakly | needs explicit routing tags and branch selection |
| Hidden target / vague lookup | none explicit | no | needs `hidden_target_search` / `target_granularity` |

So yes, the current state is exploitable, but it is not expressive enough to cleanly reproduce what `conversation_goal` tells us. The safe path is to train/prompt the extractor to infer analogous fields from visible conversation text.

### Would the ideal state have helped?

Yes. The repo's v3 candidate state is basically designed for these failure modes:

| v3 candidate field | why it helps this experiment |
| --- | --- |
| `routing_tags.lyric_search` | routes category `B` / lyric-theme turns to lyrics embeddings instead of generic BM25 |
| `routing_tags.image_or_visual_search` | routes category `C` / aesthetic turns to image/SigLIP |
| `routing_tags.hidden_target_search` | separates vague one-target lookup (`LH`) from broad browsing (`LL`) |
| `target_entities.exactness` | treats exact title/artist lookups differently from remembered/fuzzy targets |
| `target_entities` vs `mentioned_entities` | avoids confusing current desired target with old history/reference anchors |
| `constraints.facet=popularity` | gives "popular/classic/widely known" turns an explicit popularity branch/rerank signal |
| `constraints.facet=lyrics/geography/mood/instrumentation` | maps organizer rationale dimensions into branch/filter choices |
| `track_feedback.aspect_feedback` | preserves "liked X but not Y", which scalar sentiment loses |
| `carryover_policy` | directly controls whether history should be exploited, windowed, or dropped |
| `open_requirements` | tracks unmet asks / catalog-gap / closest-fit behavior across turns |
| `unsupported_signals` | makes visual/sonic/external-reference misses visible instead of silent |

Important caveat: the ideal state itself does not improve retrieval unless the compiler is table-driven from these fields. The current compiler already consumes v0+ fields for BM25, dense text, anchor centroids, release-date masks, hard drops, soft tag boosts, and RRF. The next step is not just "extract more JSON"; it is to wire each new field to branch choice, branch weights, filters, fusion quotas, and reranking features.

### Recommended extraction strategy

Do not feed `conversation_goal`, `goal_progress_assessments`, or `thought` to the production inference path. Use them as teacher/analyzer labels only.

Add blind-safe inferred fields instead:

- `inferred_goal_category`: `A`-`K`-like coarse category, optional confidence.
- `query_specificity`: `low | high`.
- `target_specificity`: `low | high`.
- `target_granularity`: `single_track | small_set | open_set`.
- `routing_tags`: `lyrics`, `visual`, `audio_mood`, `popularity`, `hidden_target`, `exact_entity`.
- `history_policy`: `exploit_same_artist | more_like_prior_track | diversify_artist | pivot_away | avoid_repeats`.
- `facet_constraints`: era, genre, mood, lyrics, popularity, geography, instrumentation, activity.

These are derived from allowed inputs: visible user/assistant text, prior played track IDs/metadata, user profile, user ID, and catalog metadata/embeddings.

### Actionability contract for the next extractor

Do not add fields unless each one maps to retriever behavior now or reranker features later. The extractor output should be a compact control plane, not a natural-language report.

| extracted field | retriever action | reranker feature |
| --- | --- | --- |
| `target_granularity` | choose exact-entity branch vs broad semantic branches | expected candidate-set size; exact-vs-open prior |
| `query_specificity`, `target_specificity` | route `HH/LH/HL/LL`-like behavior without using organizer labels | specificity priors; penalize over-broad/over-exact candidates |
| `routing_tags.exact_entity` | exact title/artist/album resolver + high-boost BM25 | exact entity match flags, edit distance, resolved-id match |
| `routing_tags.hidden_target` | broad semantic + lyrics/popularity/era branches; avoid over-anchoring to history | hidden-target prior; weigh fuzzy evidence more |
| `routing_tags.lyrics` | lyrics embedding / lyric-token branch when available | lyric/theme match score |
| `routing_tags.visual` | image/SigLIP branch | visual branch rank/provenance |
| `routing_tags.audio_mood` | CLAP/audio branch, mood tag expansion | audio branch rank/provenance |
| `routing_tags.popularity` | popularity-routed branch, not global boost | popularity score conditioned on intent |
| `routing_tags.geography_culture` | culture/geography terms into metadata/tag search | culture/geography match feature |
| `history_policy` | exploit, window, demote, or drop prior anchors | same-artist/history-overlap feature with correct sign |
| `target_entities` with `exactness` | exact resolver for `exact`; fuzzy/semantic for `remembered`; anchor-only for `reference` | entity match, exactness, resolver confidence |
| `constraints` with `facet/polarity/hardness` | hard filters only for safe facets; soft boosts/demotes otherwise | per-facet satisfied/violated indicators |
| `track_feedback.aspect_feedback` | build aspect-specific anchor text/vectors; avoid scalar-only centroids | positive/negative aspect compatibility |
| `negative_constraints` | hard-drop exact rejects; soft-demote tags/aspects/artists | violation penalties |

Prompt quality should be judged by whether these fields improve branch-level `Hit@20` / `Hit@100`, branch union@100, and reranker feature utility. Field-level F1 alone is not enough.


## Actionable items

### What I would work on next, grounded in the current code

The next step should **not** be "add tag-IDF first." The current compiler already uses positive tags in several places: tag entities go into BM25 `tag_list`, accepted-anchor tags are appended to the tag query, tags are appended to dense query text, and positive tag overlap is boosted post-fusion. A separate tag branch may still be worth an A/B later, but it is not the clearest first move.

### Grounding: what fields actually exist

Do not design actions around nonexistent first-class fields like `genre`, `mood`, `instrumentation`, or `lyrics_text`. In the current catalog/index, the concrete per-track fields are:

| field family | actual fields | what this means for retrieval |
| --- | --- | --- |
| identity metadata | `track_id`, `track_name`, `artist_name`, `album_name`, `artist_id`, `album_id`, `ISRC` | safe for exact resolver, BM25 fields, artist-discography branch, exact-title protection |
| tag metadata | `tag_list` | this is where genre/mood/style usually lives; use as lexical/soft feature unless tag is clearly hard-safe |
| numeric/date metadata | `popularity`, `release_date`, `duration` | usable for popularity priors, era filters, and duration preferences |
| text fields for BM25 | `track_name_text`, `artist_name_text`, `album_name_text`, `release_date_text`, `tag_list_text`, plus combined BM25 fields | current lexical retrieval surface |
| vector fields | `metadata_qwen3_embedding_0_6b`, `attributes_qwen3_embedding_0_6b`, `lyrics_qwen3_embedding_0_6b`, `audio_laion_clap`, `image_siglip2`, `cf_bpr` | retrieval branches can query different vector columns, but there is no raw lyrics/audio/image metadata text exposed |
| vector availability | `has_*` flags | current vector search only prefilters missing vectors |

Observed local LanceDB snapshot: `47,071` tracks. Vector coverage is high (`~98.7-99.0%` depending on field). `tag_list` is large and noisy: mean `33.5` tags/track, median `17`, max `105`, with `164,050` unique lowercased tags. Top tags include broad/fuzzy values like `rock`, `alternative`, `pop`, `favorites`, `awesome`, `love`, `seen live`, `beautiful`, `chill`, and `mellow`. This is why tag-derived genre/mood should usually be a soft retrieval/rerank feature, not a hard filter.

Grounded interpretation of earlier action names:

| earlier wording | grounded version |
| --- | --- |
| genre branch | `tag_list` branch or metadata/attribute dense query using genre words extracted from the user |
| mood branch | `tag_list` soft feature plus metadata/attribute text embeddings; CLAP/audio only via anchor centroids unless a compatible text-to-audio query encoder is added |
| instrumentation/vocal branch | extracted user facet routed to `tag_list`/metadata/attributes; audio vectors can help for anchored "more like this sound" cases, not general text-only filtering |
| lyrics branch | `lyrics_qwen3_embedding_0_6b` retrieval from lyric/story/theme query text, not raw lyric-string matching |
| popularity/classic branch | popularity-conditioned rerank/branch using the real `popularity` field, often combined with era/tag/entity cues |
| culture/geography branch | extracted text routed through tags/metadata/user profile; no dedicated geography column on tracks |

So the state update should not pretend the catalog has clean genre/mood columns. It should extract user-visible facets and mark how they should be used: `entity_exact`, `tag_soft`, `era_hard_or_soft`, `popularity_intent`, `lyrics_theme`, `audio_mood`, `history_policy`. The compiler then maps those facets onto the real surfaces above.

Work on these in order. The ordering is chosen to maximize **any-branch Hit@100** first; fusion/reranking comes after a branch can retrieve the GT.

| priority | recommendation | report evidence | current code reality | concrete next step |
| --- | --- | --- | --- | --- |
| 1 | Build branch-action diagnostics as the main scorecard | Overall final Hit@100 is `0.406`, but branch union@100 is `0.526`; `3792` turns have no current branch top100. | The frosty-payne compiler already has `branch_trace_topk` and writes `trace.branch_rankings` when enabled. | Produce one table per action/retriever: Hit@20/50/100/1000, union@100 contribution, unique contribution, and movement from `no_branch_top100` / `no_branch_top1000`. This is the acceptance gate for every new state/compiler change. |
| 2 | Promote LLM action state from v3, but only fields that drive retrievers | `no_state+visible` and `no_state+not_visible` fail for different reasons; one state blob is too blunt. | Current v0+ has `mentioned_entities`, `intent_mode`, feedback, filters, rejections. It lacks `target_entities`, `exactness`, additive `routing_tags`, and explicit `history_policy`. | Add `target_entities`, `exactness`, `routing_tags`, `constraints/facets`, and `history_policy`. Require every field to name the compiler action it can trigger. |
| 3 | Extend resolver for positive LLM-emitted targets/anchors | `state_artist_match` is very strong: Hit@100 `0.839`, union@100 `0.969`; visible-artist misses still exist. | Resolver already has rapidfuzz artist/track matching, but current code explicitly does **not** resolve positive `mentioned_entities`; it resolves rejections and feedback artist IDs. | Let the LLM emit spans/roles/exactness. Resolver maps those spans to artist/track IDs. Compiler uses resolved IDs for exact-title, exact-artist, and artist-discography branches. |
| 4 | Add cheap action retrievers and measure their standalone Hit@100 | `no_state+not_visible` has union@100 only `0.243`; `75.7%` of those rows have no current branch top100. | Current run uses BM25, metadata dense, anchor-centroid image/audio/CF. Audio/image/CF skip when no anchors; lyrics/attributes were dropped globally due macro regressions. | Add/rerun action branches: exact title, resolved artist discography, current-turn BM25, recency-weighted BM25, anchor-free metadata/attributes dense, lyrics/theme, popularity/era/tag-routed. Gate each by its own branch Hit@100 on target slices. |
| 5 | Fix history/compiler policy where branch coverage already exists | `prev_artist_match` union@100 `0.862` but final Hit@100 `0.667`; `no_state+visible` union@100 `0.662` vs final `0.395`. | History anchors feed BM25 tag expansion and anchor centroids. `diversify_artists` demotes same prior artist after fusion; exploit/balanced do not protect same-artist/album candidates. | Add recency-aware anchors, exploit/diversify-specific artist behavior, and protected survivor slots. This is important, but it should be evaluated after branch Hit@100 tables show what each history action retrieved. |
| 6 | Treat tag-IDF/tag routed as an audit/ablation, not top priority | Tag-overlap `2+` has useful union@1000, but current system already has multiple tag paths. | Current code already has `tag_list` BM25 boost, anchor-tag expansion, dense query `tags: ...`, positive tag post-fusion multiplier, and rejected tag demotion. | First measure existing tag path: in tag-overlap failures, is GT absent from BM25/metadata top100, or present but under-ranked? Only add IDF/caps if existing tag path demonstrably fails due broad-tag flooding. |

### P0: enforce blind-safe input policy

Do **not** use `conversation_goal`, `goal_progress_assessments`, or any `thought` fields in the production retrieval path. They are per-session/per-turn organizer metadata and likely leakage. Their value is as offline teacher/analyzer labels only.

| field | granularity | production stance | offline use |
| --- | --- | --- | --- |
| `conversation_goal.category/specificity/listener_goal` | per session | do not use directly | label/teacher for inferred goal category and specificity |
| `goal_progress_assessments` | per turn | do not use directly | label/teacher for accepted/near-miss/rejected history policy |
| `conversations[].thought` | per message/turn | do not use directly | diagnostic only; highest leakage risk |
| `user_profile` | per user/session snapshot | allowed if rules permit user metadata | personalization feature; validate carefully |

The system path should extract its own blind-safe fields from visible user/assistant text, prior played track IDs/metadata, user_id/profile, and catalog metadata/embeddings.

### P1: state -> compiler -> action harness first

Since the LLM can generate the compiler/actions and a full-devset state extraction run is affordable, do not constrain this to only cheap standalone retriever experiments. The more useful architecture test is:

1. Extract a blind-safe action state from allowed context.
2. Compile that state into explicit retrieval actions.
3. Execute those actions with branch provenance.
4. Score whether **any selected action/retriever** put the GT into top 100 first, then top 25.

Start with the failure session set below. If the new state fields are populated and the compiler selects plausible actions on those failures, then pay for one broad full-devset extraction run. Avoid many small prompt iterations; the first paid extractor pass should expose all fields needed by branch retrieval. Reranker fields can ride along, but the first acceptance gate is branch/action Hit@100.

The action audit should classify every failure as one of:

- **State miss:** the needed signal is visible but not extracted.
- **Compiler miss:** the signal is extracted but not converted into the right action.
- **Action/retriever miss:** the action runs but the GT is not in that retriever top 25/100.
- **Fusion/rerank miss:** an action retrieves the GT near the top, but final ranking loses it.

| compiler action | state input | implementation sketch | primary test |
| --- | --- | --- | --- |
| exact track/title resolver | LLM-extracted `target_entities`, `target_granularity=single_track`, `routing_tags.exact_entity` | LLM decides the conversational role/exactness from visible text; deterministic resolver only maps the emitted span to catalog ids, then compiler protects candidates | exact requests and remembered-title failures move into action top25 |
| exact artist resolver | LLM-extracted positive artist entity plus `exploit_same_artist` / exact request | LLM decides whether the artist is wanted, historical, contrasted, or rejected; resolver maps wanted spans to artist ids; compiler expands to all tracks by resolved artist, capped/protected | visible-artist failures move into action top25/top100 |
| current-turn lexical BM25 | current user text, exact entities, high specificity | last-turn-only / recency-weighted lexical branch | reduces full-history query noise |
| tag-path audit / optional tag-IDF ablation | positive tags/facets with rarity | first measure current tag_list BM25 + dense tags + post-fusion tag boost; only then test IDF/flood caps | avoid duplicating existing tag behavior unless broad-tag flooding is proven |
| anchor-free dense metadata | open/pivot/hidden target, low entity confidence | dense query from current request and compact state, no prior-track centroid required | turn1/open/pivot no-branch failures improve |
| lyrics/theme branch | `routing_tags.lyrics`, story/theme constraints | lyrics embedding or lyric-token retrieval if available | lyric/story exact misses improve |
| audio/mood branch | `routing_tags.audio_mood`, mood/energy/instrumentation facets | use tag/metadata/attribute query paths for text-only turns; use CLAP/audio centroid branch when positive anchors exist, or add a compatible text-to-audio query encoder before making this anchor-free | vibe/mood/action-context misses improve only if branch can actually query the available vector space |
| visual branch | `routing_tags.visual`, cover-art/aesthetic language | use image/SigLIP centroid branch when visual anchors exist, or add a compatible text-to-image query encoder before making this anchor-free | visual-category failures improve only when the branch has a valid query vector |
| popularity-routed branch | popularity/classic/well-known/iconic intent | broad candidate pool plus conditional popularity prior | famous hidden-target misses improve |
| history-policy branch | `history_policy`, accepted/rejected tracks/aspects | exploit, more-like, diversify, pivot, or avoid-repeat actions | late-turn history failures improve with correct same-artist sign |

For each action report standalone `Hit@20`, `Hit@100`, `Hit@1000`, unique contribution to union@25/100, and slices for turn1/open/pivot, novel artist, no-state-artist-match, and diversify/pivot. The most important slice is `no_branch_top100` / `no_branch_top1000`, because that is where no current retriever brings the GT close enough for fusion or reranking to rescue. If an action cannot move plausible GTs from these buckets into its own top 20/100, RRF should not be expected to make it a good top-20 contributor.

### P1 target experiment: raise any-action Hit@100

Implement the next experiment as a branch-coverage test, not as a final-ranking test.

| step | deliverable | pass/fail question |
| --- | --- | --- |
| 1. Action-state extraction | one state row per session/turn with `target_entities`, `routing_tags`, `constraints`, `history_policy` | did the LLM expose the signal that a human would use to choose a retriever? |
| 2. Positive entity resolution | resolved IDs for LLM-emitted target/anchor artist/track spans | did exact/fuzzy catalog grounding work without the resolver inventing conversational roles? |
| 3. Action compilation | list of selected branch actions with query text/IDs/filters | did the compiler select the expected actions from the state? |
| 4. Branch execution | per-action ranked list and GT rank | did any action retrieve GT at @100? |
| 5. Budgeted union construction | selected action union with per-branch quotas, target `<=1000` candidates | can the compiler keep recall while staying within VRank budget? |
| 6. Coverage accounting | `no_branch_top100 -> branch_top100`, selected-union@100, and selected-union@1000 movement | did the new system create usable retriever coverage, not just huge pools? |
| 7. Only then final fusion/rerank | final top20/top100 metrics | once budgeted branch recall exists, can ranking preserve it? |

This explicitly aligns with the target: **for every session/turn, ask whether at least one retriever/action branch can bring the GT into top 100, then whether the selected branch union can stay within the VRank budget.** If the answer is no, the next fix is state/query/retriever construction, not RRF.

#### Exact entity state contract

Resolved decision: if the conversation asks for an exact artist or title, the **state must capture that explicitly**. This is not a resolver inference problem.

Minimum fields for exact lookup:

| state field | requirement |
| --- | --- |
| `target_entities[].type` | `track`, `artist`, or `album` |
| `target_entities[].source_text` | the exact span from the user/visible conversation |
| `target_entities[].role` | `positive` / wanted target, not merely historical mention |
| `target_entities[].exactness` | `exact` for direct lookup; `fuzzy` or `remembered` for partial/lyric/uncertain recall |
| `target_entities[].source_turn` | latest/current turn when possible, so compiler can distinguish current ask from old history |
| `target_entities[].qualifiers` or shared `group_id` | bind title + artist when the user says "track X by artist Y" |

The resolver then maps these emitted spans to catalog IDs and confidence. The compiler should run exact-title / exact-artist / artist-discography actions from those resolved IDs. The open question is not whether to capture exact lookup intent; it is required.

### P1: branch-coverage diagnostic loop

For every session/turn, log a compact diagnostic row:

- `session_id`, `turn_id`, GT track/artist, final rank.
- Per-retriever GT ranks and `best_retriever`.
- Boolean coverage: `any_branch_top25`, `any_branch_top100`, `any_branch_top1000`, selected-union@100, selected-union@1000, plus hard-failure bucket.
- Candidate budget: selected branch names, per-branch quota, distinct candidate count, and whether the VRank pool is `<=1000`.
- State/compiler context: `routing_tags`, `history_policy`, `exploration_policy`, extracted entities/tags, and branch provenance.

The first question is: **did any individual retriever bring the GT into top 100?** The second question is whether the selected retriever union can keep that GT inside a VRank-sized candidate pool. `top1000` remains useful for diagnosing whether a signal exists at all, but it is not a comfortable operating target when VRank may only accept around `1000` total candidates.

- If some retriever has GT top100, the problem may be top-K conversion: compiler preference, branch protection, branch query/rank tuning, and reranker features.
- If GT is only rank 101-1000, treat it as weak retriever evidence: useful for debugging, but the next iteration should try to move it into top100 unless the budgeted union still reliably fits under VRank.
- If no retriever has GT top100/top1000, RRF and reranking cannot fix the miss. Add or repair state-conditioned actions until at least one branch can retrieve the GT.

Current diagnostic bucket counts:

| bucket | n | meaning | likely fix |
| --- | ---: | --- | --- |
| `branch_top25_but_final_not_top25` | 1073 | some retriever already found the GT near the top, but final ranking lost it | compiler preference, branch protection, reranker features |
| `no_branch_top25_but_branch_top100` | 1065 | retriever is close, but not top-25 quality yet | branch-specific boosting/reranking, better query text, light branch tuning |
| `no_branch_top100_but_branch_top1000` | 2031 | retriever has weak recall only deep in list | query/retriever quality; new branch may be cheaper than fusion tuning |
| `no_branch_top1000` | 1761 | current retrievers never see the GT | missing retrieval signal/branch |
| `artist_visible_missing_state` | 1335 | GT artist is visible in allowed prefix but absent from extracted state | extractor/resolver/history carryover audit |
| `artist_not_visible_no_branch_top1000` | 1588 | GT artist not visible and no branch finds it | non-artist retrievers: tags, lyrics/theme, popularity, audio/mood, CF |
| `tag_overlap_2plus_no_branch_top25` | 2932 | GT shares 2+ catalog tags with extracted tags but no branch reaches top 25 | audit current tag paths first; only test tag-IDF/caps if broad-tag flooding or corpus mismatch is confirmed |

This should become the main acceptance test for new retrieval/compiler work: each action should state how many rows move from `no_branch_top100` into `branch_top100`, how many rows the selected budgeted union recovers at @100/@1000, and only then how many reach `branch_top25`. Extracted artist/tag counts are supporting descriptors inside those buckets, not primary success metrics.

#### Artist/tag filtering vs boosting

Artist signals need policy-dependent handling:

- Exact title/artist or `exploit_same_artist`: use a deterministic artist branch or filter-like candidate generator with protected quota. This is where "all tracks by resolved artist" is appropriate.
- `more_like_prior_track` / "similar to artist": use artist as one seed among similarity branches; boost same/related artists, but do not hard-filter to the artist.
- `diversify_artist` / `pivot_away`: use prior artist/track as contrastive context and demote or exclude that exact artist. A same-artist boost here is actively harmful.

Tag signals already have several code paths, so do not treat "add tag retrieval" as a default fix. They should usually remain soft branch/boost signals, not hard filters:

- Audit whether the existing tag paths are failing because of missing extraction, broad-tag flooding, or fusion under-ranking before adding another tag branch.
- Hard-filter only for reliable, explicit constraints where catalog coverage is trustworthy, such as instrumental/no-vocals if represented cleanly.
- Broad genre/mood/era tags should produce candidates plus reranker features: tag overlap count, rare-tag overlap, violated negative tags, and branch rank.

### P1: deterministic named-artist branch

Target slice: turns where the state contains a positive artist that resolves to the GT artist, but final retrieval still loses the GT. The broad state slice says `state_artist_match` gets Hit@1000 `0.968`, while `no_state_artist_match` gets only `0.505`.

Definition: `no_state_artist_match` means the extracted state did **not** contain an artist mention matching the GT artist. It does **not** necessarily mean the artist was absent from the visible conversation. The split is:

- `1335` turns: GT artist was visible in the allowed prefix but missing from state. This is primarily an LLM extraction/history-carryover problem: the LLM should decide whether the visible artist is a current target, a positive anchor, or irrelevant/negative. The resolver should not infer conversational intent from raw name presence; it should only map LLM-emitted spans to catalog IDs for compiler actions.
- `4319` turns: GT artist was not visible in the allowed prefix. An artist branch cannot directly help these.

Breakdown that scopes this branch:

| bucket | n | hit100 | union50 | union100 | union1000 | actionability |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `state_artist_match` | 2346 | 0.839 | 0.934 | 0.969 | 0.998 | already strong; protect from fusion/rank loss |
| `no_state+visible` | 1335 | 0.395 | 0.603 | 0.662 | 0.875 | audit extractor/resolver/query construction and top-K conversion |
| `no_state+not_visible` | 4319 | 0.174 | 0.164 | 0.243 | 0.632 | artist branch cannot directly help; needs non-artist retrieval |

Within `no_state+visible`, the visible GT artist source is mostly history:

| source | n | share of no_state+visible | hit100 | union50 | union100 | union1000 | gap100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| prior played same artist | 1229 | 0.921 | 0.395 | 0.620 | 0.677 | 0.879 | 0.282 |
| prior assistant text | 1143 | 0.856 | 0.369 | 0.597 | 0.657 | 0.871 | 0.288 |
| user text prefix | 768 | 0.575 | 0.352 | 0.581 | 0.646 | 0.868 | 0.294 |

So the named-artist branch should not be framed as a universal fix. It mainly covers: current exact artist mentions, artist history carryover misses, and fusion protection for state-matched artists. The `no_state+not_visible` bucket needs non-artist retrieval.

Implementation:

- Resolve positive artist mentions from state to catalog `artist_id`.
- Fetch all tracks by those resolved artists into a small protected branch.
- Apply only when `history_policy` / `exploration_policy` is not `diversify_artists` or `pivot_away`.
- Add an audit for named-artist misses where BM25 did not include the GT: these indicate query-construction or entity-resolution leaks.

Expected effect: mostly improves recall in exact/artist-continuation cases and prevents RRF from evicting single-branch BM25 artist hits.

### P1/P2: one broad prompt revision, not many small prompt iterations

If we pay for a full-devset extraction run, make the prompt revision broad enough to support many compiler actions and the reranker. Do not spend prompt budget on verbose summaries. Extract a compact action/control schema, validate it on the failure sessions first, then run the full devset once.

Required fields:

- `target_granularity`: `single_track | small_set | open_set`
- `query_specificity`: `low | high`
- `target_specificity`: `low | high`
- `routing_tags`: `exact_entity`, `hidden_target`, `lyrics`, `visual`, `audio_mood`, `popularity`, `era`, `geography_culture`, `activity_context`
- `history_policy`: `exploit_same_artist | more_like_prior_track | diversify_artist | pivot_away | avoid_repeats`
- `target_entities`: type, source text, role, exactness. Let the LLM extract these from the conversation; fill resolver confidence and catalog IDs after extraction.
- `constraints`: facet, value, polarity, hardness
- `track_feedback`: role plus positive/negative aspects
- `negative_constraints`: exact artists/tracks/tags/aspects to avoid

Use raw `conversation_goal.category` and `conversation_goal.specificity` only to evaluate or distill these inferred fields. Do not feed provided organizer fields into retrieval.

### P2: make history policy actionable

Target slices: previous-artist match Hit@1000 `0.871`, state-artist match `0.969`, but `different/new artist` only `0.395`.

#### What the current run already does

Source of truth for this section is the `v0plus_compiler_mm_extractor_v3_devset` artifact/config from `frosty-payne-deefb1`.

Current extracted history/control fields:

- `intent_mode`: `open_explore | refinement | pivot | playlist_build`.
- `track_feedback`: played-track sentiment with `accepted | rejected | seed | neutral`.
- `referenced_track_ids`: explicit pronoun/position references to prior played tracks.
- `process_constraints.exploration_policy`: `exploit | diversify_artists | diversify_albums | balanced`.
- `mentioned_entities`: positive/negative/neutral artist, album, track, tag surface forms.
- `explicit_rejections`: future exclusions for artist/track/tag.
- `release_year_range`: soft era hint for post-fusion reranking.

Observed extractor distribution in this run:

| field | distribution |
| --- | --- |
| `intent_mode` | refinement `4753`, playlist_build `1423`, open_explore `1093`, pivot `727`, extractor-none `4` |
| `exploration_policy` | diversify_artists `4016`, balanced `2896`, exploit `951`, diversify_albums `133`, extractor-none `4` |
| branch traces present | BM25 `7996`, metadata dense `7996`, image/audio/CF anchor-centroid `6109` |

Current compiler/history behavior:

- Positive history anchors are `track_feedback` entries with role `accepted` or `seed` and positive sentiment, plus **all** `referenced_track_ids`.
- Those anchors feed anchor-tag expansion for BM25 and anchor-centroid branches.
- Anchor-tag expansion is skipped when `intent_mode=pivot`.
- Anchor-centroid branches are skipped when `intent_mode=pivot` or when there are no positive anchors.
- For `refinement` and `playlist_build`, metadata dense query mixes the text query with the full-session anchor centroid at alpha `0.30`; for `open_explore` and `pivot`, alpha is `0.0`.
- The current multimodal run uses BM25, metadata dense, and anchor-centroid image/audio/CF branches, all with RRF weight `1.0`.
- Positive artist mentions are not resolved into a deterministic "all tracks by artist" branch. They are used as BM25/dense query text and appear in trace as `anchor_artist_ids`, but that trace field is a surface-form diagnostic, not an executable artist branch.
- `explicit_rejections.kind=track/artist` are resolved and hard-dropped. `explicit_rejections.kind=tag` demotes overlapping tags post-fusion.
- Already-played tracks are hard-dropped.
- `process_constraints.exploration_policy` currently affects post-fusion history demotion only:
  - `diversify_artists`: tracks by any prior played artist get multiplier `0.4`.
  - `diversify_albums`: tracks from any prior played album get multiplier `0.6`.
  - `balanced` and `exploit`: no same-artist or same-album boost/demote.
- Positive tag overlap gets a post-fusion multiplier of `1.15 ** overlap`.
- Inferred rejected artist demotion from `track_feedback.role=rejected` is configured as `same_artist_demote=1.0`, so it is currently a no-op.
- `release_year_range` is a soft reranker feature: in-range `1.10`, outside range decays by `0.05` per year to floor `0.6`.

Current gaps/risks:

- There is no separate `history_policy` field yet. `exploration_policy` only controls artist/album variation, and mostly after fusion.
- `exploit` is not actionable enough: it does not boost same artist, same album, or exact-discography branches. In practice, `exploit` and `balanced` are nearly identical except for whatever text/entity query terms happen to be present.
- `diversify_artists` demotes same prior artists after fusion, but retrieval still uses prior accepted tracks as centroid seeds and anchor-tag expansion. That is partly right for "same style, new artist", but it is not a true diversify branch with explicit same-artist exclusion/quotas.
- History anchors are full-session averages, not recency weighted. Late turns can blur several accepted tracks into a weak centroid.
- `referenced_track_ids` are always treated as positive anchors. If the user says "the second one was too heavy", that referenced rejected track can still enter anchor tag/centroid construction unless blocked elsewhere.
- Track feedback is scalar/coarse. We do not yet split `accepted_aspects` vs `rejected_aspects`, so "liked the vocals but too heavy" cannot create separate positive and negative retrieval actions.
- The post-fusion policy can only demote candidates already retrieved. It cannot create new branch coverage for `no_branch_top100` / `no_branch_top1000`.

Implementation:

- Only boost same artist under `exploit_same_artist` / `more_like_prior_track`.
- Under `diversify_artist`, use prior tracks as similarity seeds but demote their exact artists.
- Add recency weighting: last 1-2 accepted tracks should dominate centroid; older tracks become weak context.
- Split positive history into `accepted_tracks`, `accepted_artists`, `accepted_aspects`, and `rejected_aspects`.

This addresses the "history is low" observation more directly than simply adding more history: late turns have lots of history, but often require using it as a contrastive seed.

### P2: add missing retrieval branches for inferred modalities

Target misses: lyrics/theme `421`, mood/audio with no tag overlap `294`, geo/culture low slice `0.542`, visual category `C` Hit@1000 `0.550`.

| branch | trigger | candidate source |
| --- | --- | --- |
| lyrics embedding | inferred lyric/story/theme route | `lyrics_qwen3_embedding_0_6b` if available |
| audio mood branch | vibe, energy, acoustic, instrumental, tempo-ish language | for text-only turns, start with tag/metadata/attribute query paths; CLAP helps when positive anchors exist unless a text-to-audio query encoder is added |
| visual branch | colorful, dark cover, aesthetic, album-art language | image/SigLIP is useful for anchor/visual-neighbor retrieval; text-only visual routing needs a compatible text-to-image query encoder |
| user-CF branch | broad exploration, weak text constraints | user embedding / CF-BPR nearest items |
| popularity branch | popular, classic, well-known, trending, iconic | catalog `popularity` rerank over broad candidate pool |
| exact-tag branch | extracted positive tags, especially rare tags | **lower priority**; current code already uses tags through BM25/dense/post-fusion, so only add IDF/rareness after an audit shows broad-tag flooding |

The current branch union@1000 ceiling is `0.780`, but the full union@1000 has a median candidate count above `4000`, which is likely too large for VRank. Treat union@1000 as an upper-bound diagnostic. The immediate target is higher branch/action `Hit@100` and a **selected** branch union that keeps the candidate pool around `<=1000`. If a new branch only finds GT at rank 700, it may prove the signal exists, but it is not yet the high-quality retriever the reranker needs.

### P3: protect recall from fusion loss, then rerank

Target slice: `1111/8000` turns where the GT is in at least one branch top1000 but absent from final top1000.

This is a budgeted recall-pool fix, not a top-25 ranking fix. If none of the retrievers brings the GT near the top 25/top100, RRF tweaks alone should not be expected to improve NDCG@20. The purpose is to stop dropping branch-found candidates while keeping the survivor pool small enough for VRank, then hand that budgeted pool to a reranker or stronger final ranker.

| action | implementation sketch | success metric |
| --- | --- | --- |
| Branch survivor guarantee | reserve survivor slots per selected branch; tune quotas so total distinct candidates stay `<=1000` | reduce branch-found-but-dropped candidates without exceeding VRank budget |
| Branch-aware selection/weights | route weights from inferred fields: lyrics -> lyrics, visual -> image, mood -> audio, popularity -> popularity, exploit -> BM25/anchor | improve selected-union@100 and reranker pool quality |
| VRank over budgeted pool | rerank selected branch union/survivor top `500-1000` | lift `Hit@20` and `NDCG@20` after budgeted recall merge |

Reranker features:

- extracted action state and current user text
- track metadata/tags/popularity/release year
- branch ranks and branch provenance
- previous played track/artist overlap
- inferred goal/specificity/routing/history-policy equivalents

Primary eval slices should be `novel_artist`, `no_state_artist_match`, `different/new artist`, `lyrics_theme`, `popularity`, and `no_branch_top1000`. Macro NDCG alone will hide whether we fixed the actual weak spots.

### Validation sequence

Run these as independent A/Bs so attribution stays clean:

1. Run the new extractor on the failure-session set only; inspect whether it captures exact entities, tags/facets, routing tags, and history policy without organizer-field leakage.
2. Compile those extracted states into explicit actions; for each failure, record expected action, selected action, branch run, and branch rank of the GT.
3. Implement the high-leverage actions behind the compiler: exact track/title, exact artist, current-turn BM25, anchor-free dense/current-turn dense, popularity/lyrics routing, and history-policy branches. Treat tag-IDF as a later ablation unless the tag-path audit proves it is missing.
4. Run the action harness on the failure set; require movement from state miss -> compiler/action/fusion categories, not just aggregate NDCG.
5. If failure-set state/action behavior looks sane, pay for one broad full-devset extraction run.
6. Rebuild branch traces and report action-level `Hit@20`, `Hit@100`, `Hit@1000`, union@25/100, selected-union@100/@1000, distinct candidate count, and unique contribution.
7. For rows where an action reaches top 25 but final ranking loses it, test compiler-time route preference and protected branch survivor slots.
8. Fusion survivor/quota plus VRank over a budgeted survivor pool (`<=1000` if that is the actual limit); validate top-K conversion separately from recall.

### Alignment and open clarifications

Current alignment:

- We agree the first target should be **high Hit@100 for at least one retriever/action branch**, not just better final RRF.
- We agree the LLM should extract conversational meaning when the signal is in the conversation.
- We agree the resolver should ground LLM-emitted spans to catalog IDs, not infer intent from raw name presence.
- We agree new state fields are only worthwhile when they trigger concrete retriever/compiler actions.

Clarifications to confirm before implementation:

1. Should the next acceptance target be **overall any-action Hit@100**, or should we set separate targets per slice (`exact_entity`, `visible_artist_history`, `no_state_not_visible`, `lyrics/theme`, `popularity/classic`)?
2. When a branch gets GT at rank `101-1000`, should the next iteration first improve that branch's top100 quality, or is a large survivor pool acceptable because the reranker will handle it?
3. What is VRank's actual candidate limit and cost curve: exactly `1000`, soft `1000`, or can we rerank a little more?

Resolved clarification:

- Exact artist/title lookup intent must be captured in state as `target_entities` with `role`, `source_text`, and `exactness`; resolver only grounds those spans to IDs.

### Failure sessions to test

Full bucket dump: `/private/tmp/top25_failure_examples.md`.

| test bucket | session / turn | GT | best available rank | why test it |
| --- | --- | --- | --- | --- |
| branch top25, final lost | `0b1d1e29-f073-4aed-860d-efcd4e7919d9` t2 | That Smiling Face / Camouflage | bm25 rank 1, final rank 83 | compiler/fusion failed despite perfect BM25 |
| branch top25, final lost | `d200481d-3b1d-4b1f-8a9b-0030ea487bb9` t5 | Eleanor Rigby - Remastered / The Beatles | bm25 rank 1, dense rank 1, final missing | exact entity should be protected |
| branch top25, final lost | `5a3d339b-ef2f-444d-8c94-0ad3668a9b41` t5 | Dreams (2am) / Kye Kye | bm25 rank 1, final missing | popularity/indie-fan wording should not evict exact branch hit |
| no branch top25, branch top100 | `608bc394-1a1d-4e44-b5f2-79b13a46c284` t1 | Experience / I Virtuosi Italiani | bm25 rank 26 | popularity-routed exact album request; just outside top 25 |
| no branch top25, branch top100 | `341c2cf2-1336-460d-95df-93b518f64a75` t3 | Tripping Out / Curtis Mayfield | bm25 rank 26, audio rank 33 | close branch ranks; good reranker/provenance test |
| no branch top25, branch top100 | `9b8a5714-1337-4fd3-8006-2ae366691c87` t6 | How Much A Dollar Cost / Ronald Isley | bm25 rank 26, final rank 6 | final ranker can rescue this; compare why |
| no branch top100, branch top1000 | `acbc68e4-0562-4ee6-b293-7e20343ebeb8` t1 | Lonely Boy with a Toy Ukulele / Tomppabeats | bm25 rank 101 | exact/near-exact title request still too deep |
| no branch top100, branch top1000 | `4425f953-2084-4fbe-8108-cacf500936b6` t7 | Tabu / ARTBAT | dense rank 101 | semantic branch almost useful; needs query/rerank lift |
| no branch top100, branch top1000 | `b458f23b-6a96-4e26-94f0-ecc5a081d6ba` t4 | From Roots to Needles / If These Trees Could Talk | bm25 rank 102, final rank 44 | branch weak but final can rescue; inspect features |
| no branch top1000 | `1cda6808-b137-41df-ad34-401dcd95595a` t1 | Basket Case / Green Day | none | lyrics resolver/lyrics embedding missing |
| no branch top1000 | `5af68b4b-99de-4b43-a40a-15070a96e5fa` t1 | Smells Like Teen Spirit / Nirvana | none | popularity/classic-hidden-target branch missing |
| no branch top1000 | `db387c2c-9f0a-41e9-a6d0-694f84dbc7d6` t1 | slumpin / Jinsang | none | chill/nostalgic beat retrieval missing |
| artist visible but missing from state | `94cb73de-91be-442d-9cdd-e7a9c9fbd74b` t4 | Crosstown Traffic / Jimi Hendrix | image rank 436, final rank 489 | visible artist bridge not captured/exploited |
| artist visible but missing from state | `e0701c11-d5d8-4fba-ac05-10e614b32b65` t5 | Conqueror / Elitsa Alexandrova | bm25 rank 460 | explicit artist continuation/history carryover |
| artist visible but missing from state | `8401fae3-2d18-4c78-b7a7-afc99cd2d7fd` t4 | Damnation / Morbid Angel | dense rank 334 | foundational-artist continuation under exploit policy |
| tag overlap 2+, no branch top25 | `a335ba9f-070a-4f4b-806c-08554b37ae02` t1 | Ladybird / Ladytron | none | audit existing tag paths first; if BM25 tag text misses, inspect extraction/corpus mismatch before adding tag-IDF |
| tag overlap 2+, no branch top25 | `1103e733-3543-441f-af3a-c8d99cece804` t1 | The Whole World / OutKast | none | likely popularity + era + hip-hop routing, not necessarily a tag-only fix |
| tag overlap 2+, no branch top25 | `13066d2c-2d5e-4162-b3dc-354ecef3aff5` t1 | Light My Fire / The Doors | none | likely popularity/classic route plus current-turn lexical, not necessarily tag-IDF |


## Examples: in branch union@1000 but lost by final fusion

- 5d296d91-f425-4b2b-abbe-c8f2d266ddf9 t1: GT=Choices / Apollo Brown; final_rank=None; branches=(bm25=656, metadata_qwen3_embedding_0_6b=None); goal=A/HL; user=Can you play some mellow, instrumental hip-hop with a laid-back beat, something good for chilling out?

- d33bae60-78c0-42b8-9941-e94b12d640ad t1: GT=Unfinished Sympathy - 2012 Mix/Master / Massive Attack; final_rank=None; branches=(bm25=852, metadata_qwen3_embedding_0_6b=None); goal=K/LH; user=What about something that truly defines the sound of 90s trip-hop, maybe with some really deep bass and a unique female vocal?

- e2c24291-9369-4daa-8017-ab4ae2d05b4e t1: GT=Teen Age Riot (Album Version) / Sonic Youth; final_rank=None; branches=(bm25=688, metadata_qwen3_embedding_0_6b=None); goal=K/LL; user=Play some classic alternative rock.

- afd30f49-02af-48cb-88ca-68ef58abf6bd t1: GT=Ulvinde / Myrkur; final_rank=None; branches=(bm25=665, metadata_qwen3_embedding_0_6b=None); goal=A/LL; user=Play some atmospheric metal with female vocals.

- e826339a-470f-4bd3-9acc-bf2153e80892 t1: GT=Jeremy / Pearl Jam; final_rank=None; branches=(bm25=962, metadata_qwen3_embedding_0_6b=None); goal=B/LH; user=I'm looking for a song with really strong, emotionally charged lyrics.

- 81b8147c-dc77-4cb8-ad77-603d1eddfe46 t1: GT=Cory Wong / Vulfpeck; final_rank=None; branches=(bm25=678, metadata_qwen3_embedding_0_6b=None); goal=E/LH; user=I'm listening to 'Aunt Leslie' by Vulfpeck and I really like it, but I can't describe what it is I love about it.

- 24d9fb69-8e0f-48d4-8d54-e9a219482a33 t1: GT=Shoulders / for KING & COUNTRY; final_rank=None; branches=(bm25=977, metadata_qwen3_embedding_0_6b=None); goal=G/LL; user=I need some songs that help me feel more encouraged, like Christian music.

- ae370fad-1e3a-4802-bca3-5d8600752f97 t1: GT=Caught in the Middle / Paramore; final_rank=None; branches=(bm25=None, metadata_qwen3_embedding_0_6b=458); goal=G/HL; user=I'm searching for songs that sound upbeat and pop-influenced but have lyrics about feeling lost or dealing with personal struggles, much like Paramore's 'Hard Times' or 'Fake Happy


## Examples: not in any branch top1000

- 1cda6808-b137-41df-ad34-401dcd95595a t1: GT=Basket Case / Green Day; final_rank=None; branches=(bm25=None, metadata_qwen3_embedding_0_6b=None); goal=B/HH; user=Play the song with the exact lyrics 'Do you have the time to listen to me whine

- 31a6e3bf-c208-49c8-b246-ca0f80a5371d t1: GT=sweet sweet / Travis Scott; final_rank=None; branches=(bm25=None, metadata_qwen3_embedding_0_6b=None); goal=D/LH; user=I'm looking for some good music to listen to while driving, something that really gets me hyped on the highway.

- 5af68b4b-99de-4b43-a40a-15070a96e5fa t1: GT=Smells Like Teen Spirit / Nirvana; final_rank=None; branches=(bm25=None, metadata_qwen3_embedding_0_6b=None); goal=J/LH; user=I'm trying to remember a song from the early 90s that everyone knew, it was really big.

- db387c2c-9f0a-41e9-a6d0-694f84dbc7d6 t1: GT=slumpin / Jinsang; final_rank=None; branches=(bm25=None, metadata_qwen3_embedding_0_6b=None); goal=K/LL; user=I'm looking for some relaxed, chill beats that have that older, nostalgic feel.

- 24fd6c9f-b4e8-4077-8fcf-9c49528802f1 t1: GT=Fracasso / Pitty; final_rank=None; branches=(bm25=None, metadata_qwen3_embedding_0_6b=None); goal=E/LH; user=I'm trying to figure out what kind of music I really connect with on a deeper level. Can you play something that might help me explore my tastes?

- 461550e4-c6a5-4d9d-81f2-8bd8e8a67f99 t1: GT=Better Off Dead / Sleeping With Sirens; final_rank=None; branches=(bm25=None, metadata_qwen3_embedding_0_6b=None); goal=B/LH; user=I'm trying to find a song with lyrics about someone dealing with a really tough emotional situation, like feeling completely alone or broken.

- 705df5aa-41ae-431f-8568-237a1b4c81c8 t1: GT=White Iverson / Post Malone; final_rank=None; branches=(bm25=None, metadata_qwen3_embedding_0_6b=None); goal=K/LL; user=Play something that's not from today, maybe an older track.

- 7303b2a2-3e78-40fc-96ca-4e15f04e2741 t1: GT=Coronus, the Terminator / Flying Lotus; final_rank=None; branches=(bm25=None, metadata_qwen3_embedding_0_6b=None); goal=B/LL; user=I'm looking for songs with a contemplative and dark atmosphere, perhaps about existential themes.
