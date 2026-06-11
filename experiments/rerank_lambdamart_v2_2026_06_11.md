# Reranker v1 — devset union-pool LambdaMART (2026-06-11)

Test sessions: 157 (880 playable turns). RRF baseline: ndcg20=0.1870 hit20=0.3966 hit1=0.0648

| arm | ndcg@20 | Δ vs RRF | t | hit@20 | hit@1 | best_iter | train ndcg@20 | val ndcg@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| full | 0.2389 | +0.0520 | +5.88 | 0.4875 | 0.0795 | 192 | 0.6988 | 0.2781 |

## Per-cohort conversion (full arm vs RRF, test)


### by warm_user

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| 0.0 | 178 | 0.1988 | 0.2226 | 0.4494 |
| 1.0 | 702 | 0.1839 | 0.2431 | 0.4972 |

### by request_type

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| attribute_search | 531 | 0.1377 | 0.1747 | 0.3804 |
| exact_track | 18 | 0.3848 | 0.6183 | 0.7222 |
| hidden_target | 43 | 0.2416 | 0.2606 | 0.4884 |
| new_artist | 134 | 0.1470 | 0.2669 | 0.5821 |
| same_artist | 86 | 0.3984 | 0.3932 | 0.8140 |
| similar_to_prior | 20 | 0.2233 | 0.3692 | 0.6000 |
| unknown | 25 | 0.2163 | 0.2562 | 0.5600 |

### by goal_category

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| A | 50 | 0.1941 | 0.2706 | 0.6200 |
| B | 159 | 0.2064 | 0.2741 | 0.5597 |
| C | 38 | 0.1388 | 0.1656 | 0.3947 |
| D | 65 | 0.3059 | 0.2877 | 0.6000 |
| E | 65 | 0.1479 | 0.2243 | 0.4000 |
| F | 56 | 0.1788 | 0.2875 | 0.5893 |
| G | 57 | 0.1436 | 0.1669 | 0.3509 |
| H | 147 | 0.1687 | 0.2311 | 0.4558 |
| J | 80 | 0.2369 | 0.2813 | 0.5250 |
| K | 150 | 0.1619 | 0.1912 | 0.4133 |

### by turn_number

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| 1 | 110 | 0.1903 | 0.2522 | 0.4727 |
| 2 | 128 | 0.2392 | 0.2774 | 0.5469 |
| 3 | 105 | 0.1987 | 0.2441 | 0.4667 |
| 4 | 112 | 0.1920 | 0.2294 | 0.4643 |
| 5 | 104 | 0.1522 | 0.2404 | 0.5192 |
| 6 | 106 | 0.1537 | 0.2314 | 0.4906 |
| 7 | 104 | 0.2033 | 0.2132 | 0.4615 |
| 8 | 111 | 0.1562 | 0.2160 | 0.4685 |

## Top-25 features (gain, full arm)

| feature | importance |
|---|---:|
| artist_track_count | 1128 |
| clap_centroid | 862 |
| best_branch_rank | 753 |
| pct_cf_centroid | 715 |
| q06_metadata_cos | 687 |
| siglip_centroid | 667 |
| duration_ms | 655 |
| tag_count | 645 |
| within_artist_pop | 639 |
| score__dense.clap_text.sonic_nl.audio_laion_clap | 594 |
| clap_last | 592 |
| pct_tag_overlap_idf | 557 |
| score__dense.qwen_8b.attributes.attributes_qwen3_embedding_8b | 542 |
| score__centroid.user.cf_bpr | 534 |
| pct_user_cf | 530 |
| listener_goal_cos | 528 |
| pct_q06_metadata_cos | 508 |
| q06_attributes_cos | 489 |
| tag_overlap_idf | 483 |
| score__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 475 |
| score__bm25 | 474 |
| cf_centroid | 470 |
| user_cf | 450 |
| rank__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 443 |
| tag_emb_cos | 440 |

| no_pool | 0.2304 | +0.0434 | +4.49 | 0.4648 | 0.0818 | 220 | 0.6935 | 0.2728 |

## v2 context (vs v1)

v2 = null-free features (rank sentinels, score floor-imputation, has_* flags),
RRF features banned from inputs, within_artist_pop + title_request_overlap,
lambdarank truncation 40→200 / lr 0.025 / leaves 127, **user-grouped split**
(Gemini review: devset = 500 users × 2 sessions; session split leaked ~52% of
test users into train) and 25% user-cf dropout on train sessions.

v1 (leaky split): +43% vs RRF. v2 (honest): **+28% (t=5.88)** → ~⅓ of v1's
lift was user memorization. Cohorts: new_artist 0.147→0.267, cold users
+12% (no regression), every turn improves. Train 0.699 vs val 0.278: model
memorizes train turns → train-split scale-up (real Modal pools) is the next
data unlock. Projected overall devset ≈0.167 vs shipped 0.1374.

## Stage-1 / Stage-2 experiment (train-split scale-up probe, 2026-06-11)

$5 probe of the cheap data-scaling path: raw-only model (no state, no
retrieval; conversation proxies incl. resolver-on-raw-text) trained on all
121k train-split turns with pool-mimicking sampled negatives (24.4M rows).

- **Stage-1 direct transfer to devset real pools: FAILED** — ndcg@20 0.055 vs
  RRF 0.187 (t=−13). Real pools are uniformly query-matched; sampled-negative
  boundaries collapse. Gemini's distribution-mismatch warning confirmed in
  full.
- **Stage-2 stack (stage1_score as v2 feature): +0.003** (0.2418 vs 0.2389) —
  no meaningful prior value either.

**Conclusion:** train-split scale-up requires REAL retrieved pools
(extraction + retrieval, ~$300–400) or doesn't happen. The raw-feature
pipeline (`build_train_features.py`) remains useful: its conversation-proxy
features (resolver-on-raw-text tag overlap, lexical mentions, negation
rejection) separated strongly and can be ported into the devset feature set.
