# Retrieval Trace & Branch Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the v0+ compiler's per-branch candidate pools, the fused list, and the final recommendation into the devset trace, and add a standalone diagnostics tool reporting per-retriever recall, hit@k, and unionhit@k.

**Architecture:** Refactor `V0PlusCompiler.compile()` to delegate to a new internal `_compile()` that returns a structured `CompileResult` (Approach C — thread-safe value, no shared state, since branches run off-thread via `asyncio.to_thread`). `compile()` becomes a thin wrapper returning `.ranked`, so the submission/blindset output is byte-identical. `V0PlusCompilerQU` attaches `CompileResult.to_trace_dict()` to each per-turn trace under a new `branches` key. A new `scripts/branch_diagnostics.py` reads the trace sidecar + ground truth and prints/dumps the metrics. The evaluator git submodule is not touched.

**Tech Stack:** Python 3.10, dataclasses, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-01-retrieval-trace-and-branch-diagnostics-design.md`

---

## File Structure

- `mcrs/qu_modules/compiler_v0plus.py` — MODIFY. Add `BranchPool` + `CompileResult` dataclasses (with `to_trace_dict()`), add `_compile()`, make `compile()` a wrapper.
- `mcrs/qu_modules/compiler_v0plus_qu.py` — MODIFY. Call `_compile()`, attach `branches` to the per-turn trace.
- `scripts/branch_diagnostics.py` — CREATE. Standalone diagnostics CLI + pure metric functions.
- `tests/test_v0plus_compiler.py` — MODIFY. Tests for `CompileResult`/`_compile()`/`compile()` equivalence.
- `tests/test_v0plus_compiler_qu.py` — MODIFY. Test the `branches` trace key.
- `tests/test_branch_diagnostics.py` — CREATE. Tests for the metric functions + CLI error handling.
- `docs/evaluation.md` — MODIFY. Document the `branches` trace key + the diagnostics script.

---

## Task 1: `CompileResult` / `BranchPool` dataclasses + `_compile()` refactor

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus.py` (add dataclasses near top after imports ~line 47; refactor `compile()` at lines 191-277)
- Test: `tests/test_v0plus_compiler.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_v0plus_compiler.py` (reuse the existing `_catalog()`, `FakeRetriever`, `FakeEmbeddingClient`, resolver helpers already in that file; mirror an existing test's setup for building `rs`). Append:

```python
from mcrs.qu_modules.compiler_v0plus import (
    BranchPool,
    CompileResult,
    CompilerConfig,
    DenseBranch,
    V0PlusCompiler,
)


def _compiler_with_hits():
    """Compiler whose BM25 + one dense branch return scripted hits."""
    catalog = _catalog()
    retriever = FakeRetriever(
        text_hits_by_field={
            "track_name": [("t-morphine-1", 5.0), ("t-fugazi-1", 3.0)],
        },
        embedding_hits=[("t-morphine-2", 0.9), ("t-fugazi-2", 0.8)],
    )
    cfg = CompilerConfig(
        final_topk=10,
        bm25_k=10,
        dense_k=10,
        dense_branches=[DenseBranch(vector_field="metadata_qwen3_embedding_0_6b")],
    )
    compiler = V0PlusCompiler(
        catalog=catalog,
        retriever=retriever,
        encoder=FakeEmbeddingClient(),
        config=cfg,
    )
    return compiler


def _resolved_state_track_query():
    """A resolved state with a free-text turn_intent so BM25 + dense both fire."""
    state = ConversationStateV0Plus(turn_intent="smoky lounge")
    resolver = V0PlusResolver(RapidfuzzCatalogMatcher(_catalog()))
    return resolver.resolve(state, played_track_ids=[])


def test_compile_returns_list_of_str_unchanged():
    compiler = _compiler_with_hits()
    rs = _resolved_state_track_query()
    out = compiler.compile(rs)
    assert isinstance(out, list)
    assert all(isinstance(t, str) for t in out)


def test_internal_compile_returns_compileresult_with_ranked_equal_to_compile():
    compiler = _compiler_with_hits()
    rs = _resolved_state_track_query()
    res = compiler._compile(rs)
    assert isinstance(res, CompileResult)
    assert res.ranked == compiler.compile(rs)


def test_compile_result_has_named_branch_pools():
    compiler = _compiler_with_hits()
    rs = _resolved_state_track_query()
    res = compiler._compile(rs)
    names = [p.name for p in res.branch_pools]
    assert "bm25" in names
    assert "dense:metadata_qwen3_embedding_0_6b" in names
    for p in res.branch_pools:
        assert isinstance(p, BranchPool)
        assert all(isinstance(t, str) and isinstance(s, float) for t, s in p.hits)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_v0plus_compiler.py -k "compile_result or internal_compile or returns_list_of_str" -v`
Expected: FAIL — `ImportError: cannot import name 'CompileResult'` (and `_compile` not defined).

- [ ] **Step 3: Add the dataclasses**

In `mcrs/qu_modules/compiler_v0plus.py`, after the existing imports and before `@dataclass class DenseBranch` (around line 47), add:

```python
@dataclass
class BranchPool:
    """One retriever branch's contribution to fusion, retained for tracing.

    `hits` is post-mask, post-hard-drop, capped at the compiler's final_topk.
    Rank is the list index. A branch that did not fire on a turn is omitted
    from CompileResult.branch_pools entirely (never emitted as an empty pool).
    """

    name: str
    hits: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class CompileResult:
    """Structured output of `V0PlusCompiler._compile()`.

    `ranked` is the exact list `compile()` returns (top-final_topk). The other
    fields are the per-branch / fused / provenance artifacts the devset trace
    persists for downstream rerank / explanation pickup.
    """

    ranked: list[str]
    branch_pools: list[BranchPool] = field(default_factory=list)
    fused: list[tuple[str, float]] = field(default_factory=list)
    n_from_fusion: int = 0
    n_from_backfill: int = 0
    depth: int = 1000

    def to_trace_dict(self) -> dict:
        """Serialize to the `branches` trace schema (JSON-friendly)."""
        return {
            "depth": self.depth,
            "pools": [
                {"name": p.name, "hits": [[t, float(s)] for t, s in p.hits]}
                for p in self.branch_pools
            ],
            "fused": [[t, float(s)] for t, s in self.fused],
            "final": {
                "track_ids": list(self.ranked),
                "n_from_fusion": self.n_from_fusion,
                "n_from_backfill": self.n_from_backfill,
            },
            "recommended": {
                "top1_track_id": self.ranked[0] if self.ranked else None,
            },
        }
```

- [ ] **Step 4: Refactor `compile()` into a wrapper + `_compile()`**

Replace the entire current `compile()` method body (lines 191-277) with:

```python
    def compile(self, rs: ResolvedConversationState, user_id: str | None = None) -> list[str]:
        """Public entry point. Returns top-final_topk track_ids (unchanged
        output contract). Internally delegates to `_compile`, which also
        retains the per-branch pools for tracing."""
        return self._compile(rs, user_id=user_id).ranked

    def _compile(
        self, rs: ResolvedConversationState, user_id: str | None = None
    ) -> CompileResult:
        state = rs.state

        # 1. Pre-fusion catalog mask from hard_filters.release_date
        candidate_mask = self._release_date_mask(state)

        # 2. Build queries
        bm25_clauses = self._build_bm25_clauses(rs)
        encoded_query = self._build_dense_query_text(rs) if self.cfg.enable_dense else None

        # 3. Retrieval — 1 BM25 call + 1 search_embedding per enabled dense branch.
        #    Track (name, hits) per branch so we can retain pools for tracing.
        bm25_hits = self.retriever.search(bm25_clauses, topk=self.cfg.bm25_k)
        named_pools: list[tuple[str, list[tuple[str, float]]]] = [("bm25", bm25_hits)]

        dense_branch_results: list[list[tuple[str, float]]] = []
        if encoded_query is not None:
            for branch in self.cfg.dense_branches:
                vec = self._mix_for_branch(rs, encoded_query, branch)
                hits = self.retriever.search_embedding(
                    query_vector=vec,
                    vector_field=branch.vector_field,
                    topk=self.cfg.dense_k,
                    distance_type=branch.distance_type,
                )
                dense_branch_results.append(hits)
                named_pools.append((f"dense:{branch.vector_field}", hits))

        # 3b. Centroid-only branches — one search_embedding call per entry.
        centroid_branches = self._resolve_centroid_only_branches()
        centroid_branch_results: list[tuple[list[tuple[str, float]], float]] = []
        for cb in centroid_branches:
            centroid = self._centroid_for_branch(rs, user_id, cb)
            if centroid is None:
                continue
            hits = self.retriever.search_embedding(
                query_vector=centroid,
                vector_field=cb.vector_field,
                topk=cb.topk,
                distance_type=cb.distance_type,
            )
            centroid_branch_results.append((hits, cb.weight))
            prefix = "centroid_user" if cb.centroid_source == "user" else "centroid"
            named_pools.append((f"{prefix}:{cb.vector_field}", hits))

        # 4. Apply pre-fusion mask (post-hoc until the retriever supports masks)
        bm25_hits = [(t, s) for t, s in bm25_hits if t in candidate_mask]
        dense_branch_results = [
            [(t, s) for t, s in hits if t in candidate_mask]
            for hits in dense_branch_results
        ]
        centroid_branch_results = [
            ([(t, s) for t, s in hits if t in candidate_mask], w)
            for hits, w in centroid_branch_results
        ]

        # 5. Hard-drop set (played + rejections + tf.rejected)
        hard_drop = self._hard_drop_set(rs)
        bm25_hits = [(t, s) for t, s in bm25_hits if t not in hard_drop]
        dense_branch_results = [
            [(t, s) for t, s in hits if t not in hard_drop]
            for hits in dense_branch_results
        ]
        centroid_branch_results = [
            ([(t, s) for t, s in hits if t not in hard_drop], w)
            for hits, w in centroid_branch_results
        ]

        # 5b. Re-apply mask + hard-drop to the retained named pools, then cap
        #     each at final_topk. `named_pools` contains exactly the branches
        #     that fired (issued a search), so we keep all of them — a fired
        #     branch left empty after filtering stays as an empty pool; only
        #     non-firing branches are absent (they were never appended).
        keep = lambda hits: [
            (t, s) for t, s in hits if t in candidate_mask and t not in hard_drop
        ][: self.cfg.final_topk]
        branch_pools = [BranchPool(name=name, hits=keep(hits)) for name, hits in named_pools]

        # 6. Weighted RRF fusion (compiler-owned, cross-modal)
        weighted_pools: list[tuple[list[tuple[str, float]], float]] = [(bm25_hits, 1.0)]
        for hits, branch in zip(dense_branch_results, self.cfg.dense_branches):
            weighted_pools.append((hits, branch.weight))
        for hits, weight in centroid_branch_results:
            if hits:
                weighted_pools.append((hits, weight))
        fused = self._rrf_fuse_weighted(weighted_pools, k=self.cfg.rrf_k)

        # 7. Soft (de)promotes
        adjusted = self._apply_soft_adjustments(fused, rs)

        # 8. Backfill to topk (popularity-sorted, mask + hard-drop-respecting)
        ranked = [tid for tid, _ in adjusted]
        n_from_fusion = min(len(ranked), self.cfg.final_topk)
        if len(ranked) < self.cfg.final_topk:
            ranked = self._backfill(ranked, candidate_mask, hard_drop)
        ranked = ranked[: self.cfg.final_topk]
        n_from_backfill = len(ranked) - n_from_fusion

        return CompileResult(
            ranked=ranked,
            branch_pools=branch_pools,
            fused=fused[: self.cfg.final_topk],
            n_from_fusion=n_from_fusion,
            n_from_backfill=n_from_backfill,
            depth=self.cfg.final_topk,
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_v0plus_compiler.py -v`
Expected: PASS — all existing compiler tests still pass (output contract unchanged) plus the 3 new tests.

- [ ] **Step 6: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus.py tests/test_v0plus_compiler.py
git commit -m "feat(compiler): structured CompileResult with retained branch pools"
```

---

## Task 2: `to_trace_dict()` schema correctness + provenance counts

**Files:**
- Test: `tests/test_v0plus_compiler.py`
- Modify: `mcrs/qu_modules/compiler_v0plus.py` (only if a test reveals a bug — `to_trace_dict` was added in Task 1)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_v0plus_compiler.py`:

```python
def test_to_trace_dict_shape_and_recommended():
    compiler = _compiler_with_hits()
    rs = _resolved_state_track_query()
    res = compiler._compile(rs)
    d = res.to_trace_dict()

    assert set(d.keys()) == {"depth", "pools", "fused", "final", "recommended"}
    assert d["depth"] == 10  # cfg.final_topk in _compiler_with_hits

    # pools: list of {name, hits:[[id, score], ...]}
    for pool in d["pools"]:
        assert set(pool.keys()) == {"name", "hits"}
        for hit in pool["hits"]:
            assert len(hit) == 2 and isinstance(hit[0], str)

    # final + recommended consistency
    assert d["final"]["track_ids"] == res.ranked
    assert d["recommended"]["top1_track_id"] == (res.ranked[0] if res.ranked else None)
    assert d["final"]["n_from_fusion"] + d["final"]["n_from_backfill"] == len(res.ranked)


def test_provenance_counts_pure_backfill_when_no_hits():
    """No BM25/dense hits → final list is entirely popularity backfill."""
    catalog = _catalog()
    retriever = FakeRetriever()  # returns nothing
    cfg = CompilerConfig(final_topk=5, dense_branches=[], enable_dense=False)
    compiler = V0PlusCompiler(
        catalog=catalog, retriever=retriever, encoder=FakeEmbeddingClient(), config=cfg
    )
    rs = _resolved_state_track_query()
    res = compiler._compile(rs)
    assert res.n_from_fusion == 0
    assert res.n_from_backfill == len(res.ranked)
    assert res.to_trace_dict()["recommended"]["top1_track_id"] == res.ranked[0]
```

- [ ] **Step 2: Run tests to verify pass/fail**

Run: `pytest tests/test_v0plus_compiler.py -k "trace_dict or provenance" -v`
Expected: If Task 1 was implemented correctly these PASS immediately. If either fails, fix `to_trace_dict()` or the `n_from_fusion`/`n_from_backfill` computation in `_compile()` until green. (These tests pin the schema the diagnostics script and downstream stages depend on.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_v0plus_compiler.py mcrs/qu_modules/compiler_v0plus.py
git commit -m "test(compiler): pin branches trace schema + provenance counts"
```

---

## Task 3: Attach `branches` to the per-turn QU trace

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus_qu.py` (compile call at line ~421-424; trace dict at lines 469-487)
- Test: `tests/test_v0plus_compiler_qu.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_v0plus_compiler_qu.py`. Reuse the file's existing `_build_qu()` and `_state()` helpers and the already-imported `MentionedEntity` — model this on the existing `test_batch_compile_track_ids_populates_last_traces`. The `FakeRetriever` wired inside `_build_qu` already returns `artist_name`/`tag_list` BM25 hits + `embedding_hits`, so BM25 and the dense branch both fire:

```python
def test_trace_contains_branches_key():
    """A v0+ QU run populates trace['branches'] with pools + fused + final."""
    state = _state(
        turn_intent="more like Morphine",
        mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)],
    )
    qu = _build_qu(state)
    qu.batch_compile_track_ids([[{"role": "user", "content": "hi"}]], topk=10)
    branches = qu.last_traces[0]["branches"]

    assert set(branches.keys()) == {"depth", "pools", "fused", "final", "recommended"}
    names = [p["name"] for p in branches["pools"]]
    assert "bm25" in names
    assert branches["final"]["track_ids"][:1] == [branches["recommended"]["top1_track_id"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_v0plus_compiler_qu.py -k branches -v`
Expected: FAIL — `KeyError: 'branches'` (trace has no such key yet).

- [ ] **Step 3: Switch the compile call to `_compile` and capture the result**

In `mcrs/qu_modules/compiler_v0plus_qu.py`, find the `_compile` thread wrapper (lines ~421-424):

```python
        def _compile() -> list[str]:
            return self.compiler.compile(rs, user_id=user_id)[:topk]

        track_ids = await asyncio.to_thread(_compile)
```

Replace with (rename the local to avoid shadowing the compiler method name):

```python
        def _run_compile() -> CompileResult:
            return self.compiler._compile(rs, user_id=user_id)

        compile_result = await asyncio.to_thread(_run_compile)
        track_ids = compile_result.ranked[:topk]
```

Add the import at the top of the file alongside the existing compiler import:

```python
from mcrs.qu_modules.compiler_v0plus import CompileResult, V0PlusCompiler
```

(If `V0PlusCompiler` is already imported there, just add `CompileResult` to that import line.)

- [ ] **Step 4: Add `branches` to the trace dict**

In the trace dict literal (lines ~469-487), add the `branches` key. Change the closing of the dict from:

```python
            "compiler": {
                "n_candidates": len(track_ids),
                "n_hard_filters": len(state.hard_filters),
                "n_explicit_rejections": len(state.explicit_rejections),
            },
        }
        return idx, track_ids, trace
```

to:

```python
            "compiler": {
                "n_candidates": len(track_ids),
                "n_hard_filters": len(state.hard_filters),
                "n_explicit_rejections": len(state.explicit_rejections),
            },
            "branches": compile_result.to_trace_dict(),
        }
        return idx, track_ids, trace
```

(The early-return `extractor_returned_none` trace at lines ~402-414 stays as-is — it has no `branches` key, which the diagnostics script treats as a non-firing turn.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_v0plus_compiler_qu.py -v`
Expected: PASS — all existing QU tests still pass plus the new branches test.

- [ ] **Step 6: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus_qu.py tests/test_v0plus_compiler_qu.py
git commit -m "feat(qu): persist branches (pools+fused+final) into per-turn trace"
```

---

## Task 4: Diagnostics metric functions (pure, no I/O)

**Files:**
- Create: `scripts/branch_diagnostics.py`
- Create: `tests/test_branch_diagnostics.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_branch_diagnostics.py`:

```python
"""Unit tests for scripts/branch_diagnostics.py metric functions."""

from __future__ import annotations

from scripts.branch_diagnostics import (
    compute_metrics,
    final_hit_at_k,
    per_branch_recall,
    union_hit_at_k,
)


def _turn(final_ids, pools, top1=None):
    """Build a minimal `branches` dict like the trace emits."""
    return {
        "depth": 1000,
        "pools": [{"name": n, "hits": [[t, 1.0] for t in ids]} for n, ids in pools.items()],
        "fused": [[t, 1.0] for t in final_ids],
        "final": {"track_ids": final_ids, "n_from_fusion": len(final_ids), "n_from_backfill": 0},
        "recommended": {"top1_track_id": top1 if top1 is not None else (final_ids[0] if final_ids else None)},
    }


def test_final_hit_at_k():
    b = _turn(["a", "b", "c"], {})
    assert final_hit_at_k(b, "a", 1) is True
    assert final_hit_at_k(b, "c", 1) is False
    assert final_hit_at_k(b, "c", 3) is True
    assert final_hit_at_k(b, "z", 3) is False


def test_union_hit_at_k():
    b = _turn(["x"], {"bm25": ["a", "b"], "dense:f": ["c", "d"]})
    assert union_hit_at_k(b, "c", 100) is True
    assert union_hit_at_k(b, "z", 100) is False
    # cutoff applies per branch before union
    b2 = _turn(["x"], {"bm25": ["a", "b", "gt"], "dense:f": ["c"]})
    assert union_hit_at_k(b2, "gt", 2) is False  # gt is at rank 3 in bm25
    assert union_hit_at_k(b2, "gt", 3) is True


def test_per_branch_recall_only_counts_fired_branches():
    turns = [
        (_turn(["x"], {"bm25": ["gt", "a"], "dense:f": ["b"]}), "gt"),  # bm25 hits, dense misses
        (_turn(["x"], {"bm25": ["a", "b"]}), "gt"),                      # dense did NOT fire this turn
    ]
    rec = per_branch_recall(turns, ks=[100])
    # bm25 fired twice, hit once
    assert rec["bm25"]["fired"] == 2
    assert rec["bm25"]["recall@100"] == 0.5
    # dense fired once (turn 1 only), missed -> 0.0 over 1 fired turn
    assert rec["dense:f"]["fired"] == 1
    assert rec["dense:f"]["recall@100"] == 0.0


def test_compute_metrics_aggregates():
    turns = [
        (_turn(["gt", "a", "b"], {"bm25": ["gt"], "dense:f": ["a"]}), "gt"),
        (_turn(["a", "b", "gt"], {"bm25": ["a"], "dense:f": ["gt"]}), "gt"),
    ]
    m = compute_metrics(turns)
    assert m["n_turns"] == 2
    assert m["hit@1"] == 0.5           # turn1 top1=gt hit, turn2 top1=a miss
    assert m["hit@20"] == 1.0          # gt in final top-20 both turns
    assert m["unionhit@100"] == 1.0    # gt in union both turns
    assert "fusion_efficiency@100" in m
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_branch_diagnostics.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` (script not created).

- [ ] **Step 3: Create the script with the metric functions**

Create `scripts/branch_diagnostics.py`:

```python
"""Branch-level retrieval diagnostics for v0+ devset trace files.

Reads a trace sidecar (exp/inference/devset/{tid}_trace.json) plus the
evaluator ground truth (evaluator/exp/ground_truth/devset.json) and reports:

  - hit@{1,20,100,200,1000}        over the FINAL recommendation
  - unionhit@{100,200}             over the union of every branch's top-k
  - recall@{100,200,1000} per branch (denominator = turns the branch fired)
  - union_size@{100,200}           mean distinct candidates in the union
  - fusion_efficiency@{100,200}    hit@k(final) / unionhit@k

Single GT track per turn, so recall@k == hit@k. The evaluator submodule is
not touched; this is an adjacent standalone tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

FINAL_KS = [1, 20, 100, 200, 1000]
UNION_KS = [100, 200]
BRANCH_KS = [100, 200, 1000]


def final_hit_at_k(branches: dict, gt: str, k: int) -> bool:
    if k == 1:
        return branches.get("recommended", {}).get("top1_track_id") == gt
    final_ids = branches.get("final", {}).get("track_ids", [])
    return gt in set(final_ids[:k])


def _branch_topk_ids(pool: dict, k: int) -> set[str]:
    return {t for t, _ in (h[:2] for h in pool.get("hits", [])[:k])}


def union_at_k(branches: dict, k: int) -> set[str]:
    out: set[str] = set()
    for pool in branches.get("pools", []):
        out |= _branch_topk_ids(pool, k)
    return out


def union_hit_at_k(branches: dict, gt: str, k: int) -> bool:
    return gt in union_at_k(branches, k)


def per_branch_recall(turns: list[tuple[dict, str]], ks: list[int]) -> dict:
    """turns: list of (branches_dict, gt_track_id). Denominator per branch is
    the number of turns that branch FIRED (appeared in pools)."""
    fired: dict[str, int] = defaultdict(int)
    hits: dict[str, dict[int, int]] = defaultdict(lambda: {k: 0 for k in ks})
    for branches, gt in turns:
        if gt is None:
            continue
        for pool in branches.get("pools", []):
            name = pool["name"]
            fired[name] += 1
            for k in ks:
                if gt in _branch_topk_ids(pool, k):
                    hits[name][k] += 1
    out: dict[str, dict] = {}
    for name, n in fired.items():
        row = {"fired": n}
        for k in ks:
            row[f"recall@{k}"] = (hits[name][k] / n) if n else 0.0
        out[name] = row
    return out


def compute_metrics(turns: list[tuple[dict, str]]) -> dict:
    """turns: list of (branches_dict, gt_track_id). Turns with gt is None or
    no `branches` are excluded from the scored denominator."""
    scored = [(b, gt) for b, gt in turns if gt is not None and b]
    n = len(scored)
    m: dict = {"n_turns": n}
    if n == 0:
        return m

    for k in FINAL_KS:
        m[f"hit@{k}"] = sum(final_hit_at_k(b, gt, k) for b, gt in scored) / n
    for k in UNION_KS:
        m[f"unionhit@{k}"] = sum(union_hit_at_k(b, gt, k) for b, gt in scored) / n
        m[f"union_size@{k}"] = sum(len(union_at_k(b, k)) for b, _ in scored) / n
        uh = m[f"unionhit@{k}"]
        m[f"fusion_efficiency@{k}"] = (m[f"hit@{k}"] / uh) if uh > 0 else None

    m["per_branch"] = per_branch_recall(scored, BRANCH_KS)
    return m
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_branch_diagnostics.py -v`
Expected: PASS — all metric-function tests green.

- [ ] **Step 5: Commit**

```bash
git add scripts/branch_diagnostics.py tests/test_branch_diagnostics.py
git commit -m "feat(diagnostics): branch-level recall + hit/unionhit metric functions"
```

---

## Task 5: Diagnostics CLI (load, align, report, error-handle)

**Files:**
- Modify: `scripts/branch_diagnostics.py` (add loaders, alignment, `main()`, `__main__`)
- Modify: `tests/test_branch_diagnostics.py` (add alignment + error-handling tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_branch_diagnostics.py`:

```python
import json as _json

from scripts.branch_diagnostics import align_turns, load_ground_truth, load_trace


def test_align_turns_matches_on_session_and_turn():
    trace = [
        {"session_id": "s1", "turn_number": 1, "trace": {"branches": {"final": {"track_ids": ["gt"]},
            "recommended": {"top1_track_id": "gt"}, "pools": [], "fused": [], "depth": 1000}}},
        {"session_id": "s1", "turn_number": 2, "trace": {"branches": {"final": {"track_ids": ["x"]},
            "recommended": {"top1_track_id": "x"}, "pools": [], "fused": [], "depth": 1000}}},
    ]
    gt = [
        {"session_id": "s1", "turn_number": 1, "ground_truth_track_id": "gt"},
        {"session_id": "s1", "turn_number": 2, "ground_truth_track_id": "y"},
        {"session_id": "s9", "turn_number": 1, "ground_truth_track_id": "z"},  # no trace -> skipped
    ]
    aligned = align_turns(trace, load_ground_truth(gt))
    assert len(aligned) == 2
    assert aligned[0][1] == "gt"
    assert aligned[1][1] == "y"


def test_load_trace_rejects_missing_branches(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(_json.dumps([{"session_id": "s1", "turn_number": 1, "trace": {"state": {}}}]))
    with __import__("pytest").raises(SystemExit):
        load_trace(str(p), require_branches=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_branch_diagnostics.py -k "align or rejects_missing" -v`
Expected: FAIL — `ImportError: cannot import name 'align_turns'`.

- [ ] **Step 3: Add loaders, alignment, and `main()`**

Append to `scripts/branch_diagnostics.py`:

```python
def load_trace(path: str, require_branches: bool = True) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    if require_branches:
        has_any = any(
            isinstance(r.get("trace"), dict) and "branches" in r["trace"]
            for r in records
        )
        if not has_any:
            sys.stderr.write(
                f"ERROR: no per-turn `branches` found in {path}. This trace was "
                "produced by a non-v0+ run or before branch tracing was added. "
                "Re-run devset inference with the v0+ compiler QU.\n"
            )
            raise SystemExit(2)
    return records


def load_ground_truth(records: list[dict]) -> dict[tuple[str, int], str]:
    """(session_id, turn_number) -> ground_truth_track_id. Accepts an already
    loaded list (tests) or use load_ground_truth_file for a path."""
    return {
        (r["session_id"], int(r["turn_number"])): r.get("ground_truth_track_id")
        for r in records
    }


def load_ground_truth_file(path: str) -> dict[tuple[str, int], str]:
    with open(path, encoding="utf-8") as f:
        return load_ground_truth(json.load(f))


def align_turns(
    trace_records: list[dict], gt: dict[tuple[str, int], str]
) -> list[tuple[dict, str]]:
    """Return [(branches_dict, gt_track_id)] for every trace turn that has a
    `branches` payload AND a ground-truth entry. Turns missing either are
    skipped (counted by the caller)."""
    out: list[tuple[dict, str]] = []
    for r in trace_records:
        tr = r.get("trace")
        if not isinstance(tr, dict) or "branches" not in tr:
            continue
        key = (r["session_id"], int(r["turn_number"]))
        if key not in gt:
            continue
        out.append((tr["branches"], gt[key]))
    return out


def _format_report(metrics: dict) -> str:
    lines = [f"n_turns scored: {metrics['n_turns']}", ""]
    lines.append("FINAL recommendation:")
    for k in FINAL_KS:
        lines.append(f"  hit@{k:<4} = {metrics.get(f'hit@{k}', 0.0):.4f}")
    lines.append("")
    lines.append("UNION of branches:")
    for k in UNION_KS:
        eff = metrics.get(f"fusion_efficiency@{k}")
        eff_s = "n/a" if eff is None else f"{eff:.3f}"
        lines.append(
            f"  unionhit@{k} = {metrics.get(f'unionhit@{k}', 0.0):.4f}"
            f"  (mean union size {metrics.get(f'union_size@{k}', 0.0):.0f},"
            f" fusion_efficiency {eff_s})"
        )
    lines.append("")
    lines.append("PER-BRANCH recall (denominator = turns fired):")
    for name, row in sorted(metrics.get("per_branch", {}).items()):
        cells = "  ".join(f"r@{k}={row.get(f'recall@{k}', 0.0):.4f}" for k in BRANCH_KS)
        lines.append(f"  {name:<32} fired={row['fired']:<5} {cells}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="v0+ branch retrieval diagnostics")
    ap.add_argument("--trace", required=True, help="path to {tid}_trace.json")
    ap.add_argument(
        "--ground-truth",
        required=True,
        help="path to evaluator/exp/ground_truth/devset.json",
    )
    ap.add_argument("--out", default=None, help="optional path to dump metrics JSON")
    args = ap.parse_args(argv)

    trace = load_trace(args.trace, require_branches=True)
    gt = load_ground_truth_file(args.ground_truth)
    aligned = align_turns(trace, gt)
    skipped = sum(
        1
        for r in trace
        if isinstance(r.get("trace"), dict) and "branches" in r["trace"]
    ) - len(aligned)

    metrics = compute_metrics(aligned)
    metrics["n_skipped_no_gt"] = skipped
    print(_format_report(metrics))
    if skipped:
        print(f"\n({skipped} traced turns skipped: no ground-truth entry)")

    if args.out:
        import os

        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_branch_diagnostics.py -v`
Expected: PASS — alignment + error-handling tests green alongside the metric tests.

- [ ] **Step 5: Smoke-test the CLI on synthetic files**

Run:
```bash
python - <<'PY'
import json, subprocess, tempfile, os
d = tempfile.mkdtemp()
trace = [{"session_id":"s1","turn_number":1,"trace":{"branches":{
    "depth":1000,"pools":[{"name":"bm25","hits":[["gt",1.0],["a",0.9]]}],
    "fused":[["gt",1.0]],"final":{"track_ids":["gt","a"],"n_from_fusion":2,"n_from_backfill":0},
    "recommended":{"top1_track_id":"gt"}}}}]
gt = [{"session_id":"s1","turn_number":1,"ground_truth_track_id":"gt"}]
tp, gp = os.path.join(d,"t.json"), os.path.join(d,"gt.json")
json.dump(trace, open(tp,"w")); json.dump(gt, open(gp,"w"))
subprocess.run(["python","scripts/branch_diagnostics.py","--trace",tp,"--ground-truth",gp], check=True)
PY
```
Expected: prints a report with `hit@1 = 1.0000`, `unionhit@100 = 1.0000`, and a `bm25 fired=1 r@100=1.0000` row. Exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/branch_diagnostics.py tests/test_branch_diagnostics.py
git commit -m "feat(diagnostics): CLI for trace+GT alignment and reporting"
```

---

## Task 6: Document the trace key + diagnostics tool

**Files:**
- Modify: `docs/evaluation.md`

- [ ] **Step 1: Add a "Branch diagnostics" subsection**

In `docs/evaluation.md`, after the "Per-turn breakdown" subsection (before the "Devset Leaderboard" section), insert:

```markdown
### Branch diagnostics (per-retriever coverage)

The v0+ devset trace sidecar (`exp/inference/devset/{tid}_trace.json`) carries a
per-turn `branches` key: each retriever branch's top-1000 `(track_id, score)`
pool (`bm25`, `dense:<field>`, `centroid:<field>`, `centroid_user:<field>`), the
RRF `fused` list, the `final` recommendation (with `n_from_fusion` /
`n_from_backfill` provenance), and `recommended.top1_track_id` (the headline
track an explanation would target). Submission/blindset runs do not write traces.

`scripts/branch_diagnostics.py` reads the trace + ground truth and reports:

- `hit@{1,20,100,200,1000}` over the final recommendation,
- `unionhit@{100,200}` over the union of every branch's top-k (the coverage
  ceiling if fusion were perfect), `union_size@k`, and `fusion_efficiency@k`,
- per-branch `recall@{100,200,1000}` (denominator = turns the branch fired).

```bash
python scripts/branch_diagnostics.py \
  --trace exp/inference/devset/{tid}_trace.json \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  --out exp/diagnostics/devset/{tid}.json   # optional; always prints a table
```

This is a standalone tool — it does not modify the evaluator submodule and is
independent of `evaluate_devset.py`.
```

- [ ] **Step 2: Verify the doc renders / links are sane**

Run: `grep -n "branch_diagnostics\|Branch diagnostics" docs/evaluation.md`
Expected: shows the new subsection heading and the script reference.

- [ ] **Step 3: Commit**

```bash
git add docs/evaluation.md
git commit -m "docs(evaluation): document branches trace key + branch_diagnostics"
```

---

## Final verification

- [ ] **Run the full affected test suite**

Run: `pytest tests/test_v0plus_compiler.py tests/test_v0plus_compiler_qu.py tests/test_branch_diagnostics.py -v`
Expected: all PASS.

- [ ] **Confirm the submission path is unchanged**

Run: `pytest tests/test_v0plus_compiler.py -k "returns_list_of_str or ranked_equal" -v`
Expected: PASS — `compile()` still returns `list[str]` identical to `_compile().ranked`.
```
