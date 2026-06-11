# Reranker — packed-matrix trainer (2026-06-11)

Test: 160 sessions, 1075 playable turns. RRF: ndcg20=0.1840 hit20=0.3870

| arm | ndcg@20 | Δ vs RRF | t | hit@20 | hit@1 | best_iter | val ndcg@20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| full | 0.2447 | +0.0608 | +7.45 | 0.4865 | 0.0940 | 212 | 0.2404 |

## Per-cohort (full arm vs RRF, test)


### by warm_user

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| 0.0 | 176 | 0.1623 | 0.2339 | 0.5000 |
| 1.0 | 899 | 0.1882 | 0.2468 | 0.4839 |

### by request_type

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| attribute_search | 630 | 0.1476 | 0.1916 | 0.4063 |
| exact_track | 48 | 0.2963 | 0.4485 | 0.6667 |
| hidden_target | 58 | 0.2292 | 0.3335 | 0.6379 |
| new_artist | 137 | 0.1272 | 0.2093 | 0.4526 |
| same_artist | 103 | 0.3301 | 0.3990 | 0.7864 |
| similar_to_prior | 37 | 0.1733 | 0.1642 | 0.2432 |
| unknown | 32 | 0.2963 | 0.3772 | 0.6250 |

### by goal_category

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| A | 92 | 0.1367 | 0.1585 | 0.3478 |
| B | 137 | 0.1758 | 0.2619 | 0.5328 |
| C | 58 | 0.1532 | 0.2021 | 0.4310 |
| D | 111 | 0.1630 | 0.2090 | 0.4234 |
| E | 101 | 0.2203 | 0.2627 | 0.4752 |
| F | 80 | 0.2408 | 0.2880 | 0.5750 |
| G | 102 | 0.1897 | 0.2901 | 0.5294 |
| H | 175 | 0.1991 | 0.2705 | 0.5257 |
| I | 19 | 0.1298 | 0.1459 | 0.4211 |
| J | 76 | 0.2256 | 0.2985 | 0.5658 |
| K | 124 | 0.1515 | 0.2073 | 0.4435 |

### by turn_number

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| 1 | 116 | 0.2297 | 0.2846 | 0.5172 |
| 2 | 141 | 0.1941 | 0.2778 | 0.5248 |
| 3 | 139 | 0.2017 | 0.2370 | 0.4748 |
| 4 | 144 | 0.1745 | 0.2155 | 0.4375 |
| 5 | 134 | 0.1902 | 0.2503 | 0.5224 |
| 6 | 134 | 0.1689 | 0.2258 | 0.4552 |
| 7 | 130 | 0.1733 | 0.2349 | 0.4769 |
| 8 | 137 | 0.1454 | 0.2378 | 0.4891 |

## Top-25 features (gain, full arm)

| feature | gain |
|---|---:|
| n_branches | 681249 |
| stage1_score | 169611 |
| best_branch_rank | 151407 |
| artist_track_count | 54974 |
| same_artist_session | 44684 |
| within_artist_pop | 33736 |
| tag_overlap_idf | 29166 |
| artist_share | 25793 |
| margin__lookup.resolved_artist_discography | 24284 |
| margin__bm25 | 22432 |
| clap_centroid | 21706 |
| msg_attr_cos | 17456 |
| margin__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 15948 |
| same_album_any | 15689 |
| year_in_constraint | 15029 |
| siglip_centroid | 14584 |
| x_pop_within_artist | 14566 |
| duration_ms | 14543 |
| clap_last | 13278 |
| msg_lyr_cos | 12524 |
| margin__centroid.anchor_tracks.image_siglip2 | 11708 |
| pct_cf_centroid | 11238 |
| pct_tag_overlap_idf | 11185 |
| rank__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 11147 |
| rank__bm25 | 10847 |
| no_pool | 0.2386 | +0.0546 | +6.15 | 0.4828 | 0.0912 | 345 | 0.2353 |
