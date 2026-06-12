# Reranker — packed-matrix trainer (2026-06-12)

Test: 160 sessions, 1075 playable turns. RRF: ndcg20=0.1840 hit20=0.3870

| arm | ndcg@20 | Δ vs RRF | t | hit@20 | hit@1 | best_iter | val ndcg@20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| full | 0.2444 | +0.0604 | +7.37 | 0.4781 | 0.0977 | 450 | 0.2380 |

## Per-cohort (full arm vs RRF, test)


### by warm_user

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| 0.0 | 176 | 0.1623 | 0.2282 | 0.4659 |
| 1.0 | 899 | 0.1882 | 0.2476 | 0.4805 |

### by request_type

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| attribute_search | 630 | 0.1476 | 0.1973 | 0.4000 |
| exact_track | 48 | 0.2963 | 0.4208 | 0.6458 |
| hidden_target | 58 | 0.2292 | 0.3116 | 0.5690 |
| new_artist | 137 | 0.1272 | 0.2183 | 0.4453 |
| same_artist | 103 | 0.3301 | 0.3714 | 0.7961 |
| similar_to_prior | 37 | 0.1733 | 0.1534 | 0.2432 |
| unknown | 32 | 0.2963 | 0.3514 | 0.6250 |

### by goal_category

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| A | 92 | 0.1367 | 0.1652 | 0.3370 |
| B | 137 | 0.1758 | 0.2516 | 0.5255 |
| C | 58 | 0.1532 | 0.2027 | 0.3621 |
| D | 111 | 0.1630 | 0.2277 | 0.4505 |
| E | 101 | 0.2203 | 0.2753 | 0.5050 |
| F | 80 | 0.2408 | 0.3075 | 0.5875 |
| G | 102 | 0.1897 | 0.2775 | 0.4902 |
| H | 175 | 0.1991 | 0.2400 | 0.4800 |
| I | 19 | 0.1298 | 0.1349 | 0.3684 |
| J | 76 | 0.2256 | 0.3092 | 0.5526 |
| K | 124 | 0.1515 | 0.2196 | 0.4758 |

### by turn_number

| value | n | RRF ndcg@20 | model ndcg@20 | model hit@20 |
|---|---:|---:|---:|---:|
| 1 | 116 | 0.2297 | 0.2793 | 0.4655 |
| 2 | 141 | 0.1941 | 0.2700 | 0.5106 |
| 3 | 139 | 0.2017 | 0.2423 | 0.4748 |
| 4 | 144 | 0.1745 | 0.2046 | 0.4444 |
| 5 | 134 | 0.1902 | 0.2835 | 0.5821 |
| 6 | 134 | 0.1689 | 0.2461 | 0.4552 |
| 7 | 130 | 0.1733 | 0.2260 | 0.4385 |
| 8 | 137 | 0.1454 | 0.2099 | 0.4526 |

## Top-25 features (gain, full arm)

| feature | gain |
|---|---:|
| n_branches | 643760 |
| best_branch_rank | 170258 |
| same_artist_session | 116425 |
| artist_track_count | 54067 |
| within_artist_pop | 45538 |
| sim_mean | 41946 |
| tag_overlap_idf | 36859 |
| margin__lookup.resolved_artist_discography | 30128 |
| margin__bm25 | 29813 |
| duration_ms | 27129 |
| msg_attr_cos | 24079 |
| msg_lyr_cos | 23406 |
| x_clap_centroid__siglip_centroid | 23218 |
| fam_count | 21451 |
| margin__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b | 21122 |
| pct_tag_overlap_idf | 18939 |
| q06_attributes_cos | 18626 |
| rank_gap12 | 18589 |
| x_user_cf__msg_meta_cos | 18453 |
| x_pop_within_artist | 17766 |
| tag_count | 17656 |
| clap_centroid | 17495 |
| pct_user_cf | 16979 |
| pct_lex_overlap_idf | 16616 |
| artist_share | 16584 |
| no_pool | 0.2303 | +0.0464 | +5.46 | 0.4744 | 0.0763 | 234 | 0.2362 |
