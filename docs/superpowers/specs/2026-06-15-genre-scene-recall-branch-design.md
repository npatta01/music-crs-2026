# Genre/scene similar-artist recall branch — design

**Date:** 2026-06-15
**Status:** approved (brainstorm), pending implementation plan
**Branch:** `semih_fix_pivot_gap`

## Context & problem

`knowledge/overanchor_report.html` flagged that on pivot/new-artist turns the system
keeps serving the artist the user just heard. The reranker retrain
(commit `6f84d36`) lifted devset_rr2 nDCG@20 0.3450→0.3895 and modestly improved
pivot opportunity capture, but the **over-anchor rate barely moved** — because the
problem is largely **retrieval recall, not ranking**.

Measured on the 1020 devset pivot turns (`intent_mode==pivot`, ≥1 resolved artist):

- Of 456 hits@20, **250 have GT = the pivoted-away artist** — over-anchoring is
  frequently *correct* (the Howard Shore/LOTR pattern). A hard demote would
  destroy these, so it was rejected.
- Of 466 `miss_new` turns (GT a new artist, missed@20), **318 (68%) have GT
  absent from the retrieval pool entirely** — a recall ceiling no reranker can fix.
- **93% of those missing GT tracks share ≥1 genre tag with the pivoted-away
  artist** — i.e. the right new artist is genre/scene-reachable from the one the
  user is leaving.
- The request qualities the extractor produces ("storytelling", "introspective")
  have **zero tag overlap with the GT on 72%** of these turns — a vocabulary
  mismatch. The GT tracks are well-tagged (median 16 tags) and mid-popularity
  (~42), so it is neither a missing-item nor a long-tail problem.

**State extraction is not the lever here** — it already identifies the satisfied
artist and reasonable qualities. The gap is that retrieval has no path that says
"other artists in this artist's genre/scene."

## Goal & success criteria

Add a retrieval branch that, on a pivot, recalls **top-popularity tracks by *other*
artists sharing the pivoted-away artist's genre/scene**, so the genre-reachable GTs
(93% of the recall misses) enter the candidate pool.

- **Phase-1 success:** measurable **pool recall@1000 lift** on the 318
  recall-ceiling pivot turns (their GT now enters the fused union), with **no
  nDCG@20/hit@20 regression** overall.
- Non-goal (Phase 1): guaranteeing those GTs reach top-20 — that needs the
  reranker to learn the new branch (Phase 2).

## Approach (chosen: A — dedicated lookup branch)

Clone the established `_era_popularity_pool` / `_resolved_artist_discography_pool`
pattern: a popularity-ranked lookup pool appended to the weighted RRF fusion as
`lookup.genre_scene`. Independently weightable and traceable for clean A/B.

Rejected alternatives: a genre inverted index (premature optimization — the
scan early-stops at the cap like era_popularity); BM25 tag injection (tangles with
the existing `turn_intent` tag clause, not popularity-aware, hard to isolate/trace).

## Components (new methods on `V0PlusCompiler`)

### `_genre_scene_anchor(rs) -> (anchor_artist_ids: set[str], genre_tag_keys: set[str])`
- Gate: empty unless `state.intent_mode.value in cfg.genre_scene_intents`.
- **Anchor artists** = resolved targets with `kind=="artist"` and
  `resolution_role=="style_reference"` (the satisfied/pivoted-away artists).
- **Genre tags**: collect tags across each anchor's top-`genre_scene_anchor_topk`
  popular tracks (`tracks_by_artist_id` ordered by popularity), normalize with
  `catalog_tag_key`, **rank by frequency** across those tracks, keep top
  `genre_scene_max_tags`. Album names / per-track noise fall out by frequency;
  pure-year and rating-like tags ("6 of 10 stars") are dropped (era handled
  separately). Optionally intersect the tag-resolver vocabulary (min-track-count)
  to harden when available.

### `_genre_scene_neighbor_pool(rs) -> list[(track_id, score)]`
- If disabled / no anchor / no genre tags → `[]`.
- **Era filter** per `genre_scene_era_policy`:
  - `explicit_only` (default): use `state.release_year_range` iff the extractor
    produced one; else no era filter.
  - `ignore`: never filter by era.
  - `infer_anchor`: anchor's median track year ± `genre_scene_era_window`.
- Scan `popularity_sorted_track_ids()`, collecting a track when: its artist ∉
  `anchor_artist_ids`; its tag-keys ∩ `genre_tag_keys` ≠ ∅; and (if era filter
  active) its release year is in range. Stop at `genre_scene_cap`. Return
  rank-scored `[(tid, n−i)]` (matches era_popularity).

### Wiring (`_compile`)
After the `era_popularity` block, build the pool, append to `weighted_pools` with
`genre_scene_weight × _routing_multiplier("lookup.genre_scene", rs)`, and emit the
`lookup.genre_scene` trace branch + `branch_status` (same shape as era/disco).

## Config (`CompilerConfig`, all knob-driven, defaults preserve baseline)

```python
enable_genre_scene_neighbors: bool = False     # master switch; rr2 configs set True
genre_scene_intents: tuple = ("pivot",)
# A/B options:
#   ("pivot",)                                                  → default, pivot only
#   ("pivot", "open_explore")                                   → + "artists like X"
#   ("pivot", "open_explore", "refinement", "playlist_build")   → any style_reference anchor
genre_scene_era_policy: str = "explicit_only"  # | "ignore" | "infer_anchor"
genre_scene_era_window: int = 5                # years, for infer_anchor
genre_scene_anchor_topk: int = 25              # anchor tracks sampled for tags
genre_scene_max_tags: int = 8                  # genre tags kept (by frequency)
genre_scene_cap: int = 200                     # neighbor pool size
genre_scene_weight: float = 1.0                # RRF weight
```
The qu_kwargs allowlist in `compiler_v0plus_qu.py` must include every new key
(guard test below). rr2 configs (`v0plus_compiler_devset_rr2.yaml`,
`v0plus_compiler_blindset_A_rr2.yaml`) set `enable_genre_scene_neighbors: true`.

## Data flow

```
pivot turn → resolver → style_reference artist(s)              [anchor]
  → _genre_scene_anchor: anchor top tracks → genre tag-keys (by frequency)
  → _genre_scene_neighbor_pool: scan pop-sorted catalog; keep OTHER artists'
       tracks sharing a genre tag (± era policy); cap genre_scene_cap
  → append lookup.genre_scene pool → weighted RRF fusion (union)
  → reranker reranks the union → top-20
```

## Reranker implication & phasing

The reranker's per-branch features (`rank__<b>`, `hit__<b>`, …) cover the 11
canonical branches in `branch_names.json`. A track rescued *only* by
`lookup.genre_scene` (no other branch retrieved it — exactly the targeted GTs)
enters the union and is scored from catalog/session/query features, but with
**NaN/absent branch signals** → weakly featured, may not climb to top-20 alone.

- **Phase 1 (this spec, no retrain):** ship the branch; measure pool recall@1000
  lift on the 318 recall-ceiling turns; confirm no nDCG@20 regression.
- **Phase 2 (follow-on, optional):** add `lookup.genre_scene` to
  `branch_names.json`, regenerate training traces with the branch enabled, rebuild
  features (`rank__genre_scene`/`hit__genre_scene` now present), retrain the
  reranker (same local pipeline as `6f84d36`), validate top-20 lift.

## Testing

**Unit (offline fakes, `tests/test_v0plus_compiler.py` style):**
- `_genre_scene_anchor`: genre tags by frequency, junk dropped, gated by
  `genre_scene_intents`, empty without a style_reference anchor.
- `_genre_scene_neighbor_pool`: returns *other* artists' tracks sharing a genre
  tag, **excludes the anchor artist**, respects `cap`, and each of the three era
  policies; `[]` when disabled.
- **Default-off parity:** `enable_genre_scene_neighbors=False` → no branch,
  byte-identical output.
- **Allowlist guard:** the new config keys reach `CompilerConfig` through the
  qu_kwargs allowlist (mirrors the existing routing_boost guard test).

**Phase-1 validation (Modal devset_rr2):**
- **Primary:** pool recall@1000 lift on the 318 recall-ceiling pivot turns
  (GT now in fused union) — extend `/tmp/analyze_pivot_overanchor.py`.
- **Guardrail:** overall nDCG@20 / hit@20 must not regress.

## Error handling (permissive, matches era/disco)

Anchor with no tracks/genre tags → `[]`; `infer_anchor` with no parseable years →
genre-only; missing tag vocab → frequency-only selection. Every degenerate path is
a no-op, never an exception.

## Files to modify

- `mcrs/qu_modules/compiler_v0plus.py` — config fields, the two methods, `_compile`
  wiring, `_ROUTING_MAP`/branch-name registration for `lookup.genre_scene`.
- `mcrs/qu_modules/compiler_v0plus_qu.py` — add new keys to the qu_kwargs allowlist.
- `configs/v0plus_compiler_devset_rr2.yaml`, `configs/v0plus_compiler_blindset_A_rr2.yaml`
  — `enable_genre_scene_neighbors: true` (+ any non-default knobs to A/B).
- `tests/test_v0plus_compiler.py`, `tests/test_v0plus_compiler_qu.py` — unit +
  allowlist guard tests.

## Out of scope

- Phase-2 reranker retrain (documented as the follow-on).
- Item-representation enrichment / tag cleanup (separate, larger `tips/` effort).
- Query→catalog-vocab tag expansion (separate lever).
