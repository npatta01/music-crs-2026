# Reranker v1 — devset union-pool LambdaMART (2026-06-11)

Test sessions: 157 (880 playable turns). RRF baseline: ndcg20=0.1870 hit20=0.3966 hit1=0.0648

| arm | ndcg@20 | Δ vs RRF | t | hit@20 | hit@1 | best_iter | train ndcg@20 | val ndcg@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| full | 0.2488 | +0.0619 | +6.51 | 0.4989 | 0.0955 | 308 | 0.7941 | 0.2777 |

## Per-cohort conversion (full arm vs RRF, test)


### by warm_user

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| 0.0 | 178 | 0.1988 | 0.2536 | 0.4663 |
| 1.0 | 702 | 0.1839 | 0.2476 | 0.5071 |

### by request_type

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| attribute_search | 531 | 0.1377 | 0.1844 | 0.3842 |
| exact_track | 18 | 0.3848 | 0.5584 | 0.6667 |
| hidden_target | 43 | 0.2416 | 0.2825 | 0.5349 |
| new_artist | 134 | 0.1470 | 0.2845 | 0.6119 |
| same_artist | 86 | 0.3984 | 0.4061 | 0.8140 |
| similar_to_prior | 20 | 0.2233 | 0.3361 | 0.6500 |
| unknown | 25 | 0.2163 | 0.2490 | 0.6000 |

### by goal_category

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| A | 50 | 0.1941 | 0.2475 | 0.5600 |
| B | 159 | 0.2064 | 0.2951 | 0.5660 |
| C | 38 | 0.1388 | 0.1582 | 0.3684 |
| D | 65 | 0.3059 | 0.3000 | 0.5846 |
| E | 65 | 0.1479 | 0.2071 | 0.4769 |
| F | 56 | 0.1788 | 0.2737 | 0.5714 |
| G | 57 | 0.1436 | 0.1845 | 0.3509 |
| H | 147 | 0.1687 | 0.2312 | 0.4490 |
| J | 80 | 0.2369 | 0.3134 | 0.6000 |
| K | 150 | 0.1619 | 0.2300 | 0.4533 |

### by turn_number

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| 1 | 110 | 0.1903 | 0.2642 | 0.4818 |
| 2 | 128 | 0.2392 | 0.3063 | 0.5469 |
| 3 | 105 | 0.1987 | 0.2337 | 0.4857 |
| 4 | 112 | 0.1920 | 0.2239 | 0.4643 |
| 5 | 104 | 0.1522 | 0.2447 | 0.5096 |
| 6 | 106 | 0.1537 | 0.2453 | 0.5000 |
| 7 | 104 | 0.2033 | 0.2310 | 0.4904 |
| 8 | 111 | 0.1562 | 0.2309 | 0.5045 |

## Top-25 features (gain, full arm)

| feature | importance |
|---|---:|
| stage1_score | 1514 |
| artist_track_count | 1393 |
| clap_centroid | 1252 |
| duration_ms | 1173 |
| best_branch_rank | 1143 |
| listener_goal_cos | 1028 |
| score__dense.clap_text.sonic_nl.audio_laion_clap | 979 |
| score__dense.qwen_8b.attributes.attributes_qwen3_embedding_8b | 970 |
| pct_tag_overlap_idf | 960 |
| q06_metadata_cos | 958 |
| clap_last | 947 |
| score__centroid.user.cf_bpr | 943 |
| siglip_centroid | 940 |
| pct_cf_centroid | 937 |
| tag_count | 934 |
| q06_attributes_cos | 915 |
| score__bm25 | 887 |
| pct_q06_metadata_cos | 851 |
| pct_user_cf | 779 |
| within_artist_pop | 750 |
| tag_overlap_idf | 739 |
| score__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 722 |
| pct_pop_pct | 709 |
| tag_emb_cos | 707 |
| rank__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 690 |

| no_pool | 0.2422 | +0.0552 | +5.58 | 0.4841 | 0.0886 | 266 | 0.7504 | 0.2715 |

## Context: the architecture-class pivot (2026-06-11/12)

Gap analysis (5-agent workflow) concluded competitors' ~0.6 blind nDCG comes
from direct next-play prediction trained on the 121k-turn train split, not
better retrieval (0.6 needs GT@top-3 on ~80% of turns; pool-reranking caps
~0.5; text→item alone is dead — median GT full-catalog rank 4,268).

Two-tower next-play model (scripts/nextplay/train_two_tower.py): context
(user_cf + last/centroid/drift cf + msg embedding + goal/profile) × track
(cf_bpr + priors + metadata embedding) + same-artist/album/replay flags,
sampled softmax over all 47k, trained on 121k turns locally (MPS):
- v1 cf-only: full-catalog ndcg 0.074 / hit@20 0.158 (vs production 0.137/0.293)
- v2 +text towers: 0.090 / 0.199, plateaus epoch 4-5
- As a feature in the LambdaMART (this report): +0.010 ndcg over v2 reranker,
  cold users +14%, hit@1 +20%, stage1_score = top importance.

Next: SASRec-style sequence model (GPU) over in-session track sequences;
full-catalog blend to recover the 30% of turns outside pools; blind-A
validation before trusting devset deltas (cf_bpr leakage bound).
