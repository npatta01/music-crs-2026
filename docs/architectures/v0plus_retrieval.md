# v0+ Retrieval Pipeline — Retrievers, Flow & Fusion

> **Scope:** the canonical conversational-retrieval path used by every `v0plus_compiler_*` config.
> **Source of truth:** `mcrs/qu_modules/compiler_v0plus.py` (+ `resolver_v0plus.py`, `post_fusion_features.py`, `cross_encoder_reranker.py`, `v0plus_catalog_lance.py`).
> **Reflects:** code at `1a8aee5` (#84), including the #80 prompt_v4 extractor + new retriever branches.
> Last verified: 2026-06-01.

This doc answers three things: **what the retrievers are**, **how a conversation flows through them**, and **how their results are fused and ranked**. For per-file responsibilities see [`docs/codebase/modules/qu_modules.md`](../codebase/modules/qu_modules.md); for the dataset/embedding columns see [`docs/data.md`](../data.md).

---

## 1. End-to-end flow

A multi-turn conversation becomes a ranked top-1000 track list through these ordered stages. The whole thing runs inside `V0PlusCompiler._compile()` (`compiler_v0plus.py`), called once per turn.

```
multi-turn conversation (session_memory)
  │
  1. EXTRACT   LiteLLMExtractor → ConversationStateV0Plus   (compiler_v0plus_qu.py)
  │              LLM (prompt_v4) emits structured intent/entities/constraints
  │
  2. RESOLVE   V0PlusResolver → ResolvedConversationState   (resolver_v0plus.py)
  │              fuzzy-match surface names → catalog artist/track IDs;
  │              resolve rejections, collect played_track_ids, resolved_targets
  │
  3. COMPILE   V0PlusCompiler._compile(rs, user_id)          (compiler_v0plus.py)
  │   ├─ 3a. candidate mask     release-date / year pre-filter → allowed track IDs
  │   ├─ 3b. build queries      BM25 field clauses + per-branch dense query strings
  │   ├─ 3c. RUN BRANCHES       1 BM25 + N dense ANN + M centroid ANN + lookup pools
  │   ├─ 3d. mask + hard-drop   keep only allowed; drop played/rejected
  │   ├─ 3e. WEIGHTED RRF       fuse all branch pools → single ranked list
  │   ├─ 3f. soft adjustments   PostFusionReranker multiplicative (de)promotes
  │   ├─ (3g. cross-encoder)    OPTIONAL, OFF by default
  │   └─ 3h. backfill           pad to final_topk by popularity
  │
  → CompileResult(ranked, branch_pools, fused, n_from_fusion, n_from_backfill)
```

`CRS_BASELINE` detects the compiler's `compile_track_ids` method and bypasses the legacy `retrieval_type` retriever entirely — the compiler owns its own retrieval. All branch searches go through the **v0+ Retriever Protocol** (`search` / `search_embedding`, defined in `mcrs/retrieval_modules/base.py`), implemented by `LanceDbRetriever` over the LanceDB catalog.

---

## 2. Retriever branches

The compiler can fan out across four families of branch. Each branch produces an independent `(track_id, score)` pool that is fused in stage 3e. Which branches fire is config-driven; the two live configs sit at opposite ends of the spectrum.

| Branch (trace name) | Family | Catalog field(s) queried | Query source | Enable knob | `image_devset` (canonical) | `all_retrievers` (frontier) |
|---|---|---|---|---|:--:|:--:|
| `bm25` | Sparse FTS | `track_name`, `artist_name`, `album_name`, `tag_list` (+ `release_year`, `release_decade`) | intent + mentioned entities + anchor-tag expansion + year terms | always on | ✅ | ✅ |
| `dense.…​.metadata_qwen3_embedding_0_6b` | Dense text ANN | `metadata_qwen3_embedding_0_6b` | encoded intent query (Qwen3-0.6B) | `enable_dense` + `dense_branches` | ❌ | ✅ |
| `dense.…​.attributes_qwen3_embedding_0_6b` | Dense text ANN | `attributes_qwen3_embedding_0_6b` | encoded `"music attributes, tags: …"` | `enable_dense` + `dense_branches` | ❌ | ✅ |
| `dense.…​.lyrics_qwen3_embedding_0_6b` | Dense text ANN | `lyrics_qwen3_embedding_0_6b` | encoded `"music lyrics: {lyrical_theme}"` | `enable_dense` + `dense_branches` | ❌ | ✅ |
| `dense.clap_text.sonic.audio_laion_clap` | Dense CLAP-text ANN | `audio_laion_clap` | sonic text query via Modal CLAP text encoder | `dense_branches` w/ `encoder_id: clap_text` | ❌ | ✅ |
| `centroid.anchor_tracks.image_siglip2` | Centroid-only ANN | `image_siglip2` | mean of positive-anchor track vectors (cover-art space) | `centroid_only_branches` | ✅ | ✅ |
| `centroid.anchor_tracks.audio_laion_clap` | Centroid-only ANN | `audio_laion_clap` | anchor centroid (CLAP audio space) | `centroid_only_branches` | ❌ | ✅ |
| `centroid.anchor_tracks.cf_bpr` | Centroid-only ANN (behavioral) | `cf_bpr` | anchor centroid (co-listening BPR, 128-d) | `centroid_only_branches` / `enable_cf_bpr` | ❌ | ✅ |
| `centroid.user.cf_bpr` | Centroid-only ANN (behavioral) | `cf_bpr` | user's precomputed CF vector | `centroid_only_branches` w/ `centroid_source: user` | ❌ | ✅ |
| `lookup.resolved_artist_discography` | Lookup pool | catalog metadata | top-popularity tracks of resolved-artist targets | `enable_resolved_artist_discography` | ❌ | ✅ |
| `lookup.era_popularity` | Lookup pool | catalog metadata | top-popularity tracks within extracted `release_year_range` | `enable_era_popularity` | ❌ | ✅ |

**Family notes**

- **Sparse FTS (`bm25`)** — one `retriever.search()` over the LanceDB/Tantivy FTS index. Built by `_build_bm25_clauses()`; per-field weights come from `field_boosts` (default `track_name`/`artist_name` 3.0, `album_name` 2.0, `tag_list` 1.5). `release_year`/`release_decade` are additive year boosts (dedicated exact/bucketed FTS fields from #81; default boost 0.0, enabled in `all_retrievers`). Always runs — there is no kill-switch.
- **Dense text ANN** — one `retriever.search_embedding()` per `DenseBranch`. The query text is *encoded* (Qwen3-0.6B via DeepInfra by default, or a named encoder such as `clap_text` via Modal). Branches that share an `(encoder_id, query_id)` pay a single encode. Master switch: `enable_dense`. Off entirely in the canonical config (full-devset dense was a net NDCG@20 regression; re-enable behind a reranker).
- **Centroid-only ANN** — no encoded query text. The query vector is the **mean of the positive-anchor track vectors** in that branch's embedding space (or the user's CF vector for `centroid_source: user`). Captures "more tracks like the ones already in play," including signals (cover art, audio timbre, co-listening) that text can't express. Skipped on `pivot` turns and turn-1 with no anchors — RRF naturally falls back to text branches there.
- **Lookup pools** — not searches; deterministic catalog slices ranked linearly by popularity. Discography = top tracks of high-confidence resolved artists (gated off `pivot` by default); era/popularity = top tracks inside the extracted year range. Both target canonical items that no content/CF branch reaches.

The **canonical `image_devset`** config is deliberately minimal: **BM25 + image-SigLIP2 centroid only**. It is the current devset best (NDCG@20 0.145). The **`all_retrievers`** config exercises *every* branch above — best candidate coverage (Hit@1000 0.697) but weaker top-20 ranking; treat it as a source-pool / reranker-input config, not a ranking config.

---

## 3. Fusion & ranking

After every branch returns its pool, results are combined in three steps.

### 3.1 Weighted Reciprocal Rank Fusion (the core ranker)

`_rrf_fuse_weighted()` merges all branch pools into one ranked list:

```
score(track) = Σ_branches   weight_branch / (rrf_k + rank_in_branch)
```

- `rrf_k = 60` (smoothing constant; larger = flatter rank discount).
- `rank_in_branch` is 1-indexed position within that branch's pool.
- **Per-branch `weight`** defaults to 1.0 and is set per branch in config. BM25, each dense branch, each centroid branch, and each lookup pool contribute with their own weight.
- **Routing multipliers** (`_routing_multiplier()` + `_ROUTING_MAP`) optionally scale a branch's weight when the extractor flags a matching intent. Example tags: `exact_entity_probe` → up-weights `bm25` + discography; `lyric_search` → lyric dense branch; `feature_articulation` → CLAP/metadata; `image_or_visual_search` → image branch. Empty `routing_boost` (the default and the live configs) means multiplier = 1.0 — i.e. routing is off, so branch coverage is measured raw.

RRF is rank-based, so branches with wildly different score scales (BM25 vs cosine vs popularity) combine cleanly without normalization.

### 3.2 Centroid-α mixing (pre-retrieval, dense branches only)

Before a dense branch searches, `_mix_for_branch()` can blend its encoded query with the anchor centroid in the same space:

```
query_vec = normalize( (1-α)·encoded_query + α·anchor_centroid )
```

`α = centroid_alpha[intent_mode]`. Defaults: `refinement` 0.4, `playlist_build` 0.5, `pivot` 0.0, `open_explore` 0.0 — i.e. refinement/playlist turns lean on what's already in play, while pivot/open-explore trust the fresh query. (The canonical config overrides refinement/playlist to 0.30.)

### 3.3 Post-fusion soft (de)promotes

`_apply_soft_adjustments()` → `PostFusionReranker.rerank()` multiplies each fused score by a product of feature multipliers (`post_fusion_features.py`):

| Feature | Effect |
|---|---|
| **UserFeedback** | Explicit track/artist rejection → ×0.0 (hard drop). Inferred same-artist-as-rejected → `same_artist_demote` (default 0.7). Per overlapping rejected tag → `rejected_tag_multiplier^count` (0.5). Per overlapping positive tag → `(1+positive_tag_multiplier_step)^count` (1.15). |
| **SessionAnchor** | Already-played → ×0.0. Anchor-artist / anchor-album demotes keyed on `exploration_policy` (e.g. `diversify_artists` demotes the anchor artist ×0.4; `diversify_albums` demotes the anchor album ×0.6). |
| **ReleaseYearRange** | In-range ×1.10; out-of-range linear decay (0.05/yr) with a 0.6 floor. |

```
final(track) = rrf_score · Π_features  feature_value ^ feature_weight
```

Feature weights default to 1.0; a disabled feature contributes 1.0 (no-op). Ties break on first-seen order.

### 3.4 Cross-encoder reranker — OPTIONAL, OFF by default

`CrossEncoderReranker` (`cross_encoder_reranker.py`) exists but is **not wired into the default `_compile()` path**. When run, it re-scores the top `rerank_top_k` (default 200) `(query, candidate_text)` pairs with a cross-encoder backend (Sentence-Transformers MiniLM/bge, FlagEmbedding bge-gemma, or Qwen3-Reranker via DeepInfra). Fusion mode is either `replace` (xenc score wins) or `rrf` (rank-fuse xenc rank with the prior RRF rank). Deferred pending evidence it beats the cheaper post-fusion features — see [`docs/superpowers/plans/2026-05-27-cross-encoder-reranker.md`](../superpowers/plans/2026-05-27-cross-encoder-reranker.md).

### 3.5 Backfill

If fusion + adjustments leave fewer than `final_topk` tracks, `_backfill()` pads by global popularity (respecting the candidate mask and hard-drop set). `CompileResult` reports `n_from_fusion` vs `n_from_backfill` so you can see how much of the tail is real retrieval vs. padding.

---

## 4. Intent & state knobs

The extractor's structured `ConversationStateV0Plus` is what makes branch behavior conversation-aware. Enums live in the extraction schema (`experiments/analysis/conversation_state_extraction_bakeoff/schema.py`).

- **`IntentMode`** — `open_explore` (broad, no anchor), `refinement` (tweak, keep anchors), `pivot` (deliberate change, drop anchors), `playlist_build` (cumulative, heavy anchors). Drives centroid-α, anchor-tag expansion, centroid-branch skipping, and discography gating.
- **`ExplorationPolicy`** — `exploit`, `diversify_artists`, `diversify_albums`, `balanced`. Drives the SessionAnchor demotes in §3.3.
- **`RoutingTags`** — `exact_entity_probe`, `lyric_search`, `feature_articulation`, `image_or_visual_search`, `hidden_target_search`. Drive the §3.1 routing multipliers (no-op unless `routing_boost` is populated).

---

## 5. Config quick-reference (live configs)

| Knob | `image_devset` (canonical) | `all_retrievers` (frontier) |
|---|---|---|
| Extractor | gemma-3-12b | deepseek-v4-flash, `prompt_version: v4` |
| `enable_dense` | `false` (BM25-only text) | `true` (metadata + attributes + lyrics + CLAP-text sonic) |
| `centroid_only_branches` | `image_siglip2` | `image_siglip2`, `audio_laion_clap`, `cf_bpr` (anchor + user) |
| `enable_resolved_artist_discography` | off | on |
| `enable_era_popularity` | off | on |
| year FTS boosts | off | `release_year`/`release_decade` = 1.0 |
| `rrf_k` / `final_topk` | 60 / 1000 | 60 / 1000 |
| Result | **NDCG@20 0.145 (rank 1)** | Hit@1000 0.697 (best coverage) |

See [`leaderboard.md`](../../leaderboard.md) for the full devset ranking and [`scripts/branch_diagnostics.py`](../../scripts/branch_diagnostics.py) (+ the `branches` trace key, `branch_trace_topk > 0`) for per-branch recall / hit@k / unionhit@k diagnostics.

---

## Pointers

- Per-file internals: [`docs/codebase/modules/qu_modules.md`](../codebase/modules/qu_modules.md), [`retrieval_modules.md`](../codebase/modules/retrieval_modules.md)
- Catalog / embedding columns: [`docs/data.md`](../data.md), `mcrs/qu_modules/v0plus_catalog_lance.py`
- Trace + diagnostics design: [`docs/superpowers/specs/2026-06-01-retrieval-trace-and-branch-diagnostics-design.md`](../superpowers/specs/2026-06-01-retrieval-trace-and-branch-diagnostics-design.md)
- Verified-bugs audit: [`docs/codebase/bugs.md`](../codebase/bugs.md)
