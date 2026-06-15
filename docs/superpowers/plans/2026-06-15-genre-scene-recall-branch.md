# Genre/scene similar-artist recall branch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `lookup.genre_scene` retrieval branch that, on pivot turns, recalls top-popularity tracks by *other* artists sharing the pivoted-away artist's genre/scene, lifting pool recall for the 318 recall-ceiling pivot misses.

**Architecture:** A new popularity-ranked lookup pool on `V0PlusCompiler`, cloned from `_era_popularity_pool`. Two methods (`_genre_scene_anchor` derives the anchor artists + genre tags; `_genre_scene_neighbor_pool` scans the popularity-sorted catalog for other artists' tracks sharing those tags, with a configurable era filter) feed a `lookup.genre_scene` pool into the existing weighted-RRF fusion. Off by default; enabled in the rr2 configs. Phase 1 (this plan) = recall branch, no reranker retrain.

**Tech Stack:** Python, the v0+ compiler (`mcrs/qu_modules/compiler_v0plus.py`), LanceDB catalog, pytest with `tests/v0plus_fakes.py` (DictCatalog/FakeRetriever).

**Reference spec:** `docs/superpowers/specs/2026-06-15-genre-scene-recall-branch-design.md`

---

## File structure

- `mcrs/qu_modules/compiler_v0plus.py` — config fields, a module-level noise-tag regex, three methods (`_genre_scene_anchor`, `_genre_scene_era_bounds`, `_genre_scene_neighbor_pool`), a `_genre_scene_query_trace` helper, and `_compile` wiring.
- `mcrs/qu_modules/compiler_v0plus_qu.py` — extend the qu_kwargs allowlist.
- `configs/v0plus_compiler_devset_rr2.yaml`, `configs/v0plus_compiler_blindset_A_rr2.yaml` — enable the branch.
- `tests/test_v0plus_compiler.py` — unit tests for the methods + default-off parity.
- `tests/test_v0plus_compiler_qu.py` — allowlist guard test.

All new compiler symbols are defined in Task 1–4 before they're referenced by wiring/tests.

---

### Task 1: Config fields + noise-tag regex

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus.py` (the `CompilerConfig` dataclass, after the `era_pop_cap` field ~line 318; and a module-level constant near the top imports)

- [ ] **Step 1: Add the module-level noise-tag regex**

Near the top of `compiler_v0plus.py` (with the other module constants/imports; ensure `import re` and `import statistics` are present — add them if missing):

```python
# Pure year/decade tags (1991, 90s, 00s, 2000s) — era is handled separately, so
# they are dropped from the genre/scene tag set.
_GENRE_NOISE_TAG_RE = re.compile(r"^\d+s?$")
```

- [ ] **Step 2: Add config fields to `CompilerConfig`**

Immediately after the `era_pop_cap: int = 200` field:

```python
    # Genre/scene similar-artist recall branch (over-anchor recall fix). On a
    # pivot, recall top-popularity tracks by OTHER artists sharing the
    # pivoted-away artist's genre/scene tags. Off by default => baseline
    # byte-identical. See docs/superpowers/specs/2026-06-15-genre-scene-recall-branch-design.md
    enable_genre_scene_neighbors: bool = False
    genre_scene_intents: tuple[str, ...] = ("pivot",)
    # A/B options:
    #   ("pivot",)                                                  -> default, pivot only
    #   ("pivot", "open_explore")                                   -> + "artists like X"
    #   ("pivot", "open_explore", "refinement", "playlist_build")   -> any style_reference anchor
    genre_scene_era_policy: str = "explicit_only"  # | "ignore" | "infer_anchor"
    genre_scene_era_window: int = 5                # years, for infer_anchor
    genre_scene_anchor_topk: int = 25              # anchor tracks sampled for tags
    genre_scene_max_tags: int = 8                  # genre tags kept (by frequency)
    genre_scene_cap: int = 200                     # neighbor pool size
    genre_scene_weight: float = 1.0                # RRF weight
```

- [ ] **Step 3: Verify it imports**

Run: `python -c "from mcrs.qu_modules.compiler_v0plus import CompilerConfig; c=CompilerConfig(); print(c.enable_genre_scene_neighbors, c.genre_scene_intents, c.genre_scene_era_policy)"`
Expected: `False ('pivot',) explicit_only`

- [ ] **Step 4: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus.py
git commit -m "feat(compiler): genre_scene recall branch config fields (off by default)"
```

---

### Task 2: `_genre_scene_anchor` — derive anchor artists + genre tags

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus.py` (new method near `_era_popularity_pool`)
- Test: `tests/test_v0plus_compiler.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_v0plus_compiler.py` (the `_sa_catalog`/`ResolvedTarget`/`_state` helpers already exist in this file):

```python
def _gs_catalog() -> DictCatalog:
    """Anchor artist (a-anchor) + a same-genre neighbor (a-neighbor) + an
    off-genre artist (a-jazz), for genre/scene recall tests."""
    return DictCatalog(
        tracks={
            "t-anchor-1": {"artist_id": "a-anchor", "artist_name": "Anchor",
                           "track_name": "A1", "tag_list": ["grunge", "90s rock", "1992"],
                           "popularity": 90.0, "release_date": "1992-01-01"},
            "t-anchor-2": {"artist_id": "a-anchor", "artist_name": "Anchor",
                           "track_name": "A2", "tag_list": ["grunge", "alternative"],
                           "popularity": 80.0, "release_date": "1993-01-01"},
            "t-neighbor-1": {"artist_id": "a-neighbor", "artist_name": "Neighbor",
                             "track_name": "N1", "tag_list": ["grunge", "loud"],
                             "popularity": 70.0, "release_date": "1994-01-01"},
            "t-neighbor-2": {"artist_id": "a-neighbor", "artist_name": "Neighbor",
                             "track_name": "N2", "tag_list": ["alternative", "indie"],
                             "popularity": 60.0, "release_date": "2010-01-01"},
            "t-jazz-1": {"artist_id": "a-jazz", "artist_name": "Jazzer",
                         "track_name": "J1", "tag_list": ["jazz", "smooth"],
                         "popularity": 100.0, "release_date": "2000-01-01"},
        }
    )


def _gs_rs(catalog, intent_mode="pivot"):
    return ResolvedConversationState(
        state=_state(turn_intent="other bands, not Anchor", intent_mode=intent_mode),
        resolved_targets=(
            ResolvedTarget(kind="artist", source_text="Anchor", entity_id="a-anchor",
                           confidence=100.0, resolution_role="style_reference"),
        ),
    )


def test_genre_scene_anchor_extracts_genre_tags_on_pivot():
    catalog = _gs_catalog()
    cfg = CompilerConfig(enable_genre_scene_neighbors=True, genre_scene_max_tags=8)
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), cfg)
    anchor_ids, genre_tags = compiler._genre_scene_anchor(_gs_rs(catalog))
    assert anchor_ids == {"a-anchor"}
    # genre tags by frequency, junk dropped: "grunge" kept; pure year/decade
    # ("1992", "90s") dropped; "90s rock" (has a space) kept.
    assert "grunge" in genre_tags
    assert "1992" not in genre_tags and "90s" not in genre_tags
    assert "90s rock" in genre_tags


def test_genre_scene_anchor_empty_when_intent_not_gated():
    catalog = _gs_catalog()
    cfg = CompilerConfig(enable_genre_scene_neighbors=True)  # genre_scene_intents=("pivot",)
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), cfg)
    anchor_ids, genre_tags = compiler._genre_scene_anchor(_gs_rs(catalog, intent_mode="refinement"))
    assert anchor_ids == set() and genre_tags == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_v0plus_compiler.py -k genre_scene_anchor -q`
Expected: FAIL with `AttributeError: 'V0PlusCompiler' object has no attribute '_genre_scene_anchor'`

- [ ] **Step 3: Implement `_genre_scene_anchor`**

Add near `_era_popularity_pool` in `compiler_v0plus.py` (uses `Counter` — already imported at top of the module; if not, add `from collections import Counter`):

```python
    @classmethod
    def _is_genre_noise_tag(cls, key: str) -> bool:
        return bool(_GENRE_NOISE_TAG_RE.match(key)) or "stars" in key or "of 10" in key

    def _genre_scene_anchor(
        self, rs: ResolvedConversationState
    ) -> tuple[set[str], set[str]]:
        """(anchor_artist_ids, genre_tag_keys) for the genre/scene branch.

        Anchors = resolved style_reference artists (the satisfied/pivoted-away
        artists). Genre tags = catalog_tag_keys collected across each anchor's
        top-`genre_scene_anchor_topk` popular tracks, ranked by frequency, top
        `genre_scene_max_tags` kept, with pure year/decade + rating tags dropped.
        Empty unless the turn's intent is in `genre_scene_intents`.
        """
        state = rs.state
        if state.intent_mode.value not in self.cfg.genre_scene_intents:
            return set(), set()
        anchor_ids = {
            t.entity_id
            for t in rs.resolved_targets
            if t.kind == "artist"
            and getattr(t, "resolution_role", "exact_target") == "style_reference"
            and t.entity_id is not None
        }
        if not anchor_ids:
            return set(), set()
        pop_rank = self._popularity_rank()
        sentinel = len(pop_rank)
        tag_freq: Counter = Counter()
        for aid in anchor_ids:
            ranked = sorted(
                self.catalog.tracks_by_artist_id(aid),
                key=lambda t: pop_rank.get(t, sentinel),
            )[: self.cfg.genre_scene_anchor_topk]
            for tid in ranked:
                for raw in self.catalog.tag_list(tid):
                    key = self._catalog_tag_key(raw)
                    if not key or self._is_genre_noise_tag(key):
                        continue
                    tag_freq[key] += 1
        genre_tags = {k for k, _ in tag_freq.most_common(self.cfg.genre_scene_max_tags)}
        return anchor_ids, genre_tags
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_v0plus_compiler.py -k genre_scene_anchor -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus.py tests/test_v0plus_compiler.py
git commit -m "feat(compiler): _genre_scene_anchor (anchor artists + genre tags)"
```

---

### Task 3: `_genre_scene_neighbor_pool` + era bounds

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus.py`
- Test: `tests/test_v0plus_compiler.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_genre_scene_pool_recalls_other_artist_same_genre():
    catalog = _gs_catalog()
    cfg = CompilerConfig(enable_genre_scene_neighbors=True, genre_scene_era_policy="ignore")
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), cfg)
    pool = compiler._genre_scene_neighbor_pool(_gs_rs(catalog))
    ids = [t for t, _ in pool]
    assert "t-neighbor-1" in ids          # a-neighbor shares "grunge"
    assert "t-anchor-1" not in ids and "t-anchor-2" not in ids   # anchor excluded
    assert "t-jazz-1" not in ids          # off-genre excluded


def test_genre_scene_pool_disabled_by_default():
    catalog = _gs_catalog()
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), CompilerConfig())
    assert compiler._genre_scene_neighbor_pool(_gs_rs(catalog)) == []


def test_genre_scene_pool_explicit_era_filters_off_era_neighbor():
    from mcrs.conversation_state.schema import ConversationStateV0Plus
    catalog = _gs_catalog()
    cfg = CompilerConfig(enable_genre_scene_neighbors=True, genre_scene_era_policy="explicit_only")
    compiler = V0PlusCompiler(catalog, FakeRetriever(), _fake_encoder(), cfg)
    # A state whose release_year_range is the 90s; t-neighbor-2 (2010) must drop,
    # t-neighbor-1 (1994) stays. Build the pivot state via facts so the year
    # range is populated by the extractor projection.
    state = ConversationStateV0Plus(
        current_request={"request_type": "new_artist",
                         "summary": "90s grunge bands, not Anchor", "source_turn": 1},
        facts=[
            {"type": "artist", "value": "Anchor", "role": "satisfied_prior",
             "anchor_use": "do_not_use", "relation": "satisfied_prior",
             "reuse": "avoid_exact", "source_turn": 1, "mentioned_current_turn": True},
            {"type": "attribute", "facet": "temporal", "value": "1990-1999",
             "role": "current_target", "anchor_use": "query_facet",
             "relation": "query_facet", "reuse": "not_applicable", "source_turn": 1},
        ],
    )
    rs = _resolve(state, catalog)
    if rs.state.release_year_range is None:
        import pytest; pytest.skip("extractor projection did not yield a year range")
    ids = [t for t, _ in compiler._genre_scene_neighbor_pool(rs)]
    assert "t-neighbor-1" in ids and "t-neighbor-2" not in ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_v0plus_compiler.py -k "genre_scene_pool" -q`
Expected: FAIL with `AttributeError: ... '_genre_scene_neighbor_pool'`

- [ ] **Step 3: Implement the era-bounds helper and the pool**

```python
    def _genre_scene_era_bounds(
        self, rs: ResolvedConversationState, anchor_ids: set[str]
    ) -> tuple[int | None, int | None]:
        policy = self.cfg.genre_scene_era_policy
        if policy == "ignore":
            return None, None
        if policy == "explicit_only":
            ryr = rs.state.release_year_range
            return (None, None) if ryr is None else (ryr.start, ryr.end)
        if policy == "infer_anchor":
            years = [
                y
                for aid in anchor_ids
                for tid in self.catalog.tracks_by_artist_id(aid)
                if (y := self.catalog.release_year_of(tid)) is not None
            ]
            if not years:
                return None, None
            med = int(statistics.median(years))
            w = self.cfg.genre_scene_era_window
            return med - w, med + w
        return None, None

    def _genre_scene_neighbor_pool(
        self, rs: ResolvedConversationState
    ) -> list[tuple[str, float]]:
        """Popularity-ranked tracks by OTHER artists sharing the pivoted-away
        artist's genre/scene tags (± era policy). Returns a ranked (id, score)
        pool for RRF, or [] when disabled / no anchor / no genre tags."""
        cfg = self.cfg
        if not cfg.enable_genre_scene_neighbors:
            return []
        anchor_ids, genre_tags = self._genre_scene_anchor(rs)
        if not anchor_ids or not genre_tags:
            return []
        anchor_tracks: set[str] = set()
        for aid in anchor_ids:
            anchor_tracks.update(self.catalog.tracks_by_artist_id(aid))
        lo, hi = self._genre_scene_era_bounds(rs, anchor_ids)
        era_active = lo is not None or hi is not None
        track_ids: list[str] = []
        for tid in self.catalog.popularity_sorted_track_ids():
            if tid in anchor_tracks:
                continue
            tkeys = {self._catalog_tag_key(t) for t in self.catalog.tag_list(tid)}
            if not (tkeys & genre_tags):
                continue
            if era_active:
                yr = self.catalog.release_year_of(tid)
                if yr is None or (lo is not None and yr < lo) or (hi is not None and yr > hi):
                    continue
            track_ids.append(tid)
            if len(track_ids) >= cfg.genre_scene_cap:
                break
        n = len(track_ids)
        return [(t, float(n - i)) for i, t in enumerate(track_ids)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_v0plus_compiler.py -k "genre_scene_pool" -q`
Expected: PASS (3 passed; the era test may report `skipped` if the projection yields no year range — acceptable)

- [ ] **Step 5: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus.py tests/test_v0plus_compiler.py
git commit -m "feat(compiler): _genre_scene_neighbor_pool + era policy"
```

---

### Task 4: Wire the branch into `_compile` + trace

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus.py` (`_compile`, after the `era_popularity` block ~line 862; add `_genre_scene_query_trace`)
- Test: `tests/test_v0plus_compiler.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_genre_scene_branch_injects_neighbors_into_results_on_pivot():
    catalog = _gs_catalog()
    # BM25 returns only the off-genre track; genre_scene must add the neighbor.
    retriever = FakeRetriever(text_hits_by_field={"tag_list": [("t-jazz-1", 5.0)]})
    cfg = CompilerConfig(enable_dense=False, enable_genre_scene_neighbors=True,
                         genre_scene_era_policy="ignore")
    result = V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_gs_rs(catalog))
    assert "t-neighbor-1" in result          # recalled via genre_scene branch
    assert "t-anchor-1" not in result        # anchor still excluded


def test_genre_scene_branch_off_by_default_is_noop():
    catalog = _gs_catalog()
    retriever = FakeRetriever(text_hits_by_field={"tag_list": [("t-jazz-1", 5.0)]})
    cfg = CompilerConfig(enable_dense=False)  # genre_scene disabled
    result = V0PlusCompiler(catalog, retriever, _fake_encoder(), cfg).compile(_gs_rs(catalog))
    # Only the BM25 hit + popularity backfill; neighbor not pulled by a branch.
    # (Backfill may still include it by popularity, so assert the branch didn't fire
    # by checking the neighbor does NOT outrank the BM25 hit.)
    assert result[0] == "t-jazz-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_v0plus_compiler.py -k "genre_scene_branch" -q`
Expected: FAIL — `test_genre_scene_branch_injects_neighbors_into_results_on_pivot` fails (`t-neighbor-1` absent) because the branch isn't wired.

- [ ] **Step 3: Add the query-trace helper**

Near `_era_popularity_query_trace`:

```python
    def _genre_scene_query_trace(self, rs: ResolvedConversationState) -> dict:
        anchor_ids, genre_tags = self._genre_scene_anchor(rs)
        return {
            "kind": "lookup",
            "lookup_type": "genre_scene",
            "anchor_artist_ids": sorted(anchor_ids),
            "genre_tags": sorted(genre_tags),
            "era_policy": self.cfg.genre_scene_era_policy,
        }
```

- [ ] **Step 4: Wire the pool into `_compile`**

In `_compile`, immediately after the `era_popularity` block (after the `feature_branch_inputs.append((era_branch_name, ...))` closes, ~line 862) and before the `feature_context = (` block, insert:

```python
        gs_hits = self._genre_scene_neighbor_pool(rs)
        gs_branch_name = "lookup.genre_scene"
        if trace_enabled and self.cfg.enable_genre_scene_neighbors:
            branch_queries[gs_branch_name] = self._genre_scene_query_trace(rs)
            branch_status[gs_branch_name] = (
                {"configured": True, "fired": True, "n_raw_hits": len(gs_hits)}
                if gs_hits
                else {"configured": True, "fired": False, "skip_reason": "no_anchor_or_tags"}
            )
        if trace_enabled and gs_hits:
            named_pools.append((gs_branch_name, list(gs_hits[:_trace_k])))
        gs_hits = [
            (t, s) for t, s in gs_hits if t in candidate_mask and t not in hard_drop
        ]
        if gs_hits:
            gs_w = self.cfg.genre_scene_weight * self._routing_multiplier("lookup.genre_scene", rs)
            weighted_pools.append((gs_hits, gs_w))
            feature_branch_inputs.append((gs_branch_name, gs_hits, gs_w))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_v0plus_compiler.py -k "genre_scene" -q`
Expected: PASS (all genre_scene tests)

- [ ] **Step 6: Run the full compiler suite for no-regression**

Run: `python -m pytest tests/test_v0plus_compiler.py -q`
Expected: PASS (no regressions; default-off keeps existing tests green)

- [ ] **Step 7: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus.py tests/test_v0plus_compiler.py
git commit -m "feat(compiler): wire lookup.genre_scene branch into fusion + trace"
```

---

### Task 5: qu_kwargs allowlist + guard test

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus_qu.py` (the `config_kwargs` allowlist set, ~lines 1079-1141)
- Test: `tests/test_v0plus_compiler_qu.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_v0plus_compiler_qu.py` (mirrors `test_routing_boost_survives_yaml_allowlist`):

```python
def test_genre_scene_knobs_survive_yaml_allowlist():
    catalog = _catalog()
    qu = build_v0plus_compiler_qu(
        qu_kwargs={"compiler": {
            "enable_genre_scene_neighbors": True,
            "genre_scene_intents": ["pivot", "open_explore"],
            "genre_scene_era_policy": "infer_anchor",
            "genre_scene_cap": 150,
        }},
        _overrides={
            "catalog": catalog,
            "matcher": RapidfuzzCatalogMatcher(catalog),
            "encoder": FakeEmbeddingClient(vector=[0.5, 0.5, 0.5]),
            "retriever": FakeRetriever(),
            "extractor": _FakeExtractor(state=_state()),
        },
    )
    assert qu.compiler.cfg.enable_genre_scene_neighbors is True
    assert qu.compiler.cfg.genre_scene_era_policy == "infer_anchor"
    assert qu.compiler.cfg.genre_scene_cap == 150
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_v0plus_compiler_qu.py -k genre_scene_knobs -q`
Expected: FAIL — `enable_genre_scene_neighbors` stays `False` (dropped by the allowlist).

- [ ] **Step 3: Add the keys to the allowlist**

In `compiler_v0plus_qu.py`, inside the `config_kwargs = { k: v ... if k in { ... } }` set (the same block containing `"enable_similar_artist_anchors"`), add:

```python
                "enable_genre_scene_neighbors",
                "genre_scene_intents",
                "genre_scene_era_policy",
                "genre_scene_era_window",
                "genre_scene_anchor_topk",
                "genre_scene_max_tags",
                "genre_scene_cap",
                "genre_scene_weight",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_v0plus_compiler_qu.py -k genre_scene_knobs -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus_qu.py tests/test_v0plus_compiler_qu.py
git commit -m "feat(qu): pass genre_scene knobs through the config allowlist"
```

---

### Task 6: Enable the branch in the rr2 configs

**Files:**
- Modify: `configs/v0plus_compiler_devset_rr2.yaml`, `configs/v0plus_compiler_blindset_A_rr2.yaml` (the `compiler:` block, near `enable_era_popularity`)

- [ ] **Step 1: Add the enable flag to both rr2 configs**

In the `compiler:` block of **each** file, after the `enable_era_popularity`/`era_pop_*` lines, add:

```yaml
    # Genre/scene similar-artist recall branch (over-anchor recall fix). See
    # docs/superpowers/specs/2026-06-15-genre-scene-recall-branch-design.md
    enable_genre_scene_neighbors: true
    # genre_scene_intents / genre_scene_era_policy left at defaults
    # ("pivot",) / explicit_only — A/B alternatives in the spec.
```

- [ ] **Step 2: Verify both configs parse and carry the flag**

Run:
```bash
python -c "import yaml; [print(f, yaml.safe_load(open(f))['qu_kwargs']['compiler'].get('enable_genre_scene_neighbors')) for f in ['configs/v0plus_compiler_devset_rr2.yaml','configs/v0plus_compiler_blindset_A_rr2.yaml']]"
```
Expected: both print `True`.

- [ ] **Step 3: Commit**

```bash
git add configs/v0plus_compiler_devset_rr2.yaml configs/v0plus_compiler_blindset_A_rr2.yaml
git commit -m "config(rr2): enable genre_scene recall branch"
```

---

### Task 7: Phase-1 validation (Modal devset_rr2) — recall lift

> Validation task (no new production code). Confirms the recall mechanism before any reranker retrain.

- [ ] **Step 1: Extend the analyzer with a pool-recall measure**

In `/tmp/analyze_pivot_overanchor.py`, for the `miss_new` recall-ceiling turns, the script already classifies "GT absent from fused pool". Add a counter for "GT now present in the fused pool" so a before/after delta is reportable. (The fused pool is `trace.branches.fused`.)

- [ ] **Step 2: Run the Modal validation**

Run: `python run_experiment.py --backend modal --tid v0plus_compiler_devset_rr2 --batch_size 64 --num_shards 50`
Expected: 50 shards complete, merge + eval write `exp/scores/devset/v0plus_compiler_devset_rr2.json`. (If a shard fails transiently, re-run with the printed `--run_id`.)

- [ ] **Step 3: Compare metrics**

- Pool recall@1000 on the prior 318 recall-ceiling pivot turns (run the extended analyzer on the new run-id) — expect a lift.
- Overall nDCG@20 / hit@20 vs the committed-model baseline (0.3895 / 0.5508) — must not regress.

- [ ] **Step 4: Record the outcome**

Append the before/after recall + nDCG numbers to the spec doc's success-criteria section and decide whether the lift justifies Phase 2 (retrain the reranker with `lookup.genre_scene` in `branch_names.json`). Commit the doc update.

---

## Self-review

**Spec coverage:** components (`_genre_scene_anchor` T2, `_genre_scene_neighbor_pool` + era policy T3, wiring/trace T4), config knobs incl. commented gating (T1), allowlist (T5), rr2 enable (T6), Phase-1 validation incl. pool-recall metric (T7), default-off parity (T4 step), error handling (empty returns in T2/T3 — no anchor/tags/years all yield `[]`/no-op). All spec sections map to a task.

**Placeholder scan:** every code step shows complete code; commands have expected output; no TBD/TODO.

**Type consistency:** `_genre_scene_anchor` returns `(set[str], set[str])` and is consumed that way in `_genre_scene_neighbor_pool` and `_genre_scene_query_trace`; `_genre_scene_neighbor_pool` returns `list[tuple[str,float]]` consumed by the `_compile` wiring exactly like `era_hits`; config field names are identical across Task 1, the methods, the allowlist (T5), and the configs (T6).

**Note for the implementer:** confirm `import re`, `import statistics`, and `from collections import Counter` exist at the top of `compiler_v0plus.py`; add any that are missing in Task 1.
