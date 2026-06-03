# Union-pool Reranker Eval Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline-replay harness that, on the turns where the ground-truth track is already in the union@k retrieval pool, compares today's RRF ordering against an LLM reranker (pointwise Qwen3-Reranker, then hand-rolled listwise) on Hit@1/Hit@20/MRR/NDCG@20 — isolating ranking quality from retrieval.

**Architecture:** Pure offline replay over the existing 5.1G devset trace + ground-truth file. No re-inference, no retrieval changes. Four small, single-responsibility modules under `scripts/` (metrics, query-block builder, listwise ranker, orchestrator) compose existing helpers from `branch_diagnostics.py`, `rerank_offline.py`, and `cross_encoder_reranker.py`. Rankers and the LLM call are dependency-injected so the core logic is unit-testable with stubs (no network in tests).

**Tech Stack:** Python 3.10, pytest, `datasets` (HF metadata), the repo's `DeepInfraRerankerBackend` (hosted Qwen3-Reranker), `litellm.completion` (OpenRouter, for listwise).

**Spec:** `docs/superpowers/specs/2026-06-03-union-pool-reranker-eval-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/rank_eval_metrics.py` (NEW) | Pure ranking metrics: `ndcg_at_k`, `reciprocal_rank`, `hit_at_k`, `score_ordering`. No I/O. |
| `scripts/rank_eval_query.py` (NEW) | `build_query_block(state, history, profile)` — the lean/rich query block from state + history. Pure. |
| `scripts/listwise_ranker.py` (NEW, Phase 2) | `parse_ranking`, `listwise_rank(query_block, items, complete_fn, window, stride)` — RankGPT sliding window. LLM call injected. |
| `scripts/rank_eval_union_pool.py` (NEW) | Orchestrator: stream trace, build pool, apply ranker, score, print table + write JSON. argparse CLI. |
| `tests/test_rank_eval_metrics.py` (NEW) | Unit tests for metrics. |
| `tests/test_rank_eval_query.py` (NEW) | Unit tests for lean/rich query block. |
| `tests/test_listwise_ranker.py` (NEW) | Unit tests for parser + sliding window (stub `complete_fn`). |
| `tests/test_rank_eval_union_pool.py` (NEW) | Unit tests for pool build, playable filter, RRF/pointwise/oracle orderings (stub backend). |

Phase boundaries (gates require the user's go-ahead — runs cost money):
- **Phase 1 (Tasks 1–6):** metrics + query block + orchestrator with RRF/pointwise/oracle. Smoke-slice run.
- **Phase 1b (Task 7):** lean-vs-rich ablation on the smoke slice.
- **Phase 2 (Tasks 8–10):** listwise module, wire into orchestrator, smoke-slice then scale.

---

## Task 1: Ranking metrics module

**Files:**
- Create: `scripts/rank_eval_metrics.py`
- Test: `tests/test_rank_eval_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rank_eval_metrics.py
"""Unit tests for scripts/rank_eval_metrics.py."""
from __future__ import annotations

import math

from scripts.rank_eval_metrics import (
    hit_at_k,
    ndcg_at_k,
    reciprocal_rank,
    score_ordering,
)


def test_hit_at_k():
    order = ["a", "b", "c", "d"]
    assert hit_at_k(order, "a", 1) is True
    assert hit_at_k(order, "b", 1) is False
    assert hit_at_k(order, "c", 3) is True
    assert hit_at_k(order, "d", 3) is False
    assert hit_at_k(order, "z", 4) is False  # gt absent


def test_reciprocal_rank():
    order = ["a", "b", "c"]
    assert reciprocal_rank(order, "a") == 1.0
    assert reciprocal_rank(order, "b") == 0.5
    assert reciprocal_rank(order, "z") == 0.0  # absent


def test_ndcg_at_k_single_relevant():
    # single GT: NDCG@k = 1/log2(rank+1) if rank<=k else 0
    order = ["a", "b", "c"]
    assert ndcg_at_k(order, "a", 20) == 1.0
    assert math.isclose(ndcg_at_k(order, "b", 20), 1.0 / math.log2(3))
    assert ndcg_at_k(order, "z", 20) == 0.0  # absent
    # GT below cutoff scores 0
    order2 = ["x"] * 25 + ["gt"]
    assert ndcg_at_k(order2, "gt", 20) == 0.0


def test_score_ordering_bundle():
    order = ["a", "gt", "c"]
    m = score_ordering(order, "gt", k=20)
    assert m["hit@1"] == 0.0
    assert m["hit@20"] == 1.0
    assert m["mrr"] == 0.5
    assert math.isclose(m["ndcg@20"], 1.0 / math.log2(3))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rank_eval_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.rank_eval_metrics'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/rank_eval_metrics.py
"""Pure ranking metrics for the union-pool reranker eval.

Single relevant item per turn (one GT track), so Hit@k == Recall@k and NDCG@k
reduces to the position discount of the GT. No I/O — every function takes a
ranked list of track_ids plus the GT and returns a number.
"""
from __future__ import annotations

import math


def hit_at_k(ordered_ids: list[str], gt: str, k: int) -> bool:
    return gt in ordered_ids[:k]


def reciprocal_rank(ordered_ids: list[str], gt: str) -> float:
    try:
        rank = ordered_ids.index(gt) + 1
    except ValueError:
        return 0.0
    return 1.0 / rank


def ndcg_at_k(ordered_ids: list[str], gt: str, k: int) -> float:
    """Single-relevant NDCG@k. IDCG == 1 (GT at rank 1), so NDCG == DCG."""
    try:
        rank = ordered_ids.index(gt) + 1
    except ValueError:
        return 0.0
    if rank > k:
        return 0.0
    return 1.0 / math.log2(rank + 1)


def score_ordering(ordered_ids: list[str], gt: str, k: int = 20) -> dict:
    """Bundle the four metrics for one ordering of one turn's pool."""
    return {
        "hit@1": 1.0 if hit_at_k(ordered_ids, gt, 1) else 0.0,
        f"hit@{k}": 1.0 if hit_at_k(ordered_ids, gt, k) else 0.0,
        "mrr": reciprocal_rank(ordered_ids, gt),
        f"ndcg@{k}": ndcg_at_k(ordered_ids, gt, k),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rank_eval_metrics.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/rank_eval_metrics.py tests/test_rank_eval_metrics.py
git commit -m "feat: ranking metrics for union-pool reranker eval (#95)"
```

---

## Task 2: Query-block builder (lean / rich profiles)

**Files:**
- Create: `scripts/rank_eval_query.py`
- Test: `tests/test_rank_eval_query.py`

Background — the `state` dict (from `trace.state`) carries: `turn_intent` (str),
`mentioned_entities` (list of `{type, value, sentiment}`), `process_constraints`
(`{exploration_policy}`), `release_year_range` (`{start, end}` or None),
`routing_tags` (`{exact_entity_probe, ...}`), `explicit_rejections` (list of
`{value, ...}`). `history` is a pre-built list of annotated strings (most recent
last), e.g. `'"Nirvana - Heart-Shaped Box" (1993, grunge, rock)'`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rank_eval_query.py
"""Unit tests for scripts/rank_eval_query.py."""
from __future__ import annotations

from scripts.rank_eval_query import build_query_block, format_era


SAMPLE_STATE = {
    "turn_intent": "Play a 90s grunge track like Nirvana.",
    "mentioned_entities": [
        {"type": "artist", "value": "Nirvana", "sentiment": 1},
        {"type": "artist", "value": "Creed", "sentiment": -1},
    ],
    "explicit_rejections": [{"value": "Nickelback"}],
    "process_constraints": {"exploration_policy": "diversify_artists"},
    "release_year_range": {"start": 1990, "end": 1999},
    "routing_tags": {"exact_entity_probe": True},
}
HISTORY = ['"Pearl Jam - Black" (1991, grunge)', '"Soundgarden - Black Hole Sun" (1994, grunge)']


def test_format_era():
    assert format_era({"start": 1990, "end": 1999}) == "1990s"
    assert format_era({"start": 1985, "end": 1992}) == "1985-1992"
    assert format_era(None) == ""
    assert format_era({}) == ""


def test_lean_profile_has_core_lines_only():
    q = build_query_block(SAMPLE_STATE, HISTORY, profile="lean")
    assert "Request: Play a 90s grunge track like Nirvana." in q
    assert 'Just heard: "Soundgarden - Black Hole Sun" (1994, grunge)' in q
    assert "Recent:" in q
    assert "User likes: Nirvana" in q
    assert "Policy: prefer a different artist" in q
    # lean must NOT include rich-only lines
    assert "Era:" not in q
    assert "Avoid:" not in q
    assert "Exact target" not in q


def test_rich_profile_adds_era_avoid_exact():
    q = build_query_block(SAMPLE_STATE, HISTORY, profile="rich")
    assert "Era: 1990s" in q
    assert "Avoid:" in q and "Creed" in q and "Nickelback" in q
    assert "Exact target" in q  # because exact_entity_probe is True
    # rich is a superset of lean's core lines
    assert "Request:" in q and "User likes: Nirvana" in q


def test_rich_omits_exact_hint_when_probe_false():
    state = dict(SAMPLE_STATE, routing_tags={"exact_entity_probe": False})
    q = build_query_block(state, HISTORY, profile="rich")
    assert "Exact target" not in q


def test_empty_history_turn1():
    q = build_query_block(SAMPLE_STATE, [], profile="lean")
    assert "Just heard" not in q and "Recent" not in q
    assert "Request:" in q  # still present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rank_eval_query.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.rank_eval_query'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/rank_eval_query.py
"""Build the ranker query block from conversation state + history.

Two profiles, selectable so we can ablate lean-vs-rich (issue #95):
  - lean: Request / Just heard / Recent / User likes / Policy
          (mirrors rerank_offline.build_query_structured)
  - rich: lean + Era / Avoid / Exact-target hint

Pure: takes the `state` dict (trace.state) and a pre-annotated `history` list
(most-recent last); returns a newline-joined string. No I/O.
"""
from __future__ import annotations

_POLICY_LINES = {
    "diversify_artists": "Policy: prefer a different artist from the ones already played.",
    "exploit": "Policy: prefer more from the same artist as the recent plays.",
    "diversify_albums": "Policy: prefer a different album from the ones already played.",
}


def format_era(year_range: dict | None) -> str:
    """'1990s' for a clean decade, else '1990-1999'. '' if missing."""
    if not year_range:
        return ""
    start = year_range.get("start")
    end = year_range.get("end")
    if start is None or end is None:
        return ""
    if start % 10 == 0 and end - start == 9:
        return f"{start}s"
    return f"{start}-{end}"


def _likes(state: dict) -> list[str]:
    me = state.get("mentioned_entities") or []
    vals = [m.get("value") for m in me if (m.get("sentiment") or 0) > 0 and m.get("value")]
    return list(dict.fromkeys(vals))[:6]


def _avoid(state: dict) -> list[str]:
    me = state.get("mentioned_entities") or []
    neg = [m.get("value") for m in me if (m.get("sentiment") or 0) < 0 and m.get("value")]
    rej = [r.get("value") for r in (state.get("explicit_rejections") or []) if r.get("value")]
    return list(dict.fromkeys(neg + rej))[:6]


def build_query_block(state: dict, history: list[str], profile: str = "rich") -> str:
    if profile not in ("lean", "rich"):
        raise ValueError(f"unknown query profile {profile!r}")
    parts: list[str] = []

    intent = (state.get("turn_intent") or "").strip()
    if intent:
        parts.append(f"Request: {intent}")

    if history:
        parts.append(f"Just heard: {history[-1]}")
        recent = history[-3:]
        if len(recent) > 1:
            parts.append(f'Recent: {"; ".join(recent)}')

    likes = _likes(state)
    if likes:
        parts.append(f"User likes: {', '.join(likes)}")

    policy = (state.get("process_constraints") or {}).get("exploration_policy") or "balanced"
    if policy in _POLICY_LINES:
        parts.append(_POLICY_LINES[policy])

    if profile == "rich":
        era = format_era(state.get("release_year_range"))
        if era:
            parts.append(f"Era: {era}")
        avoid = _avoid(state)
        if avoid:
            parts.append(f"Avoid: {', '.join(avoid)}")
        if (state.get("routing_tags") or {}).get("exact_entity_probe"):
            parts.append(
                "Exact target: the user named a specific track/artist; "
                "an exact title/artist match should rank first."
            )

    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rank_eval_query.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/rank_eval_query.py tests/test_rank_eval_query.py
git commit -m "feat: lean/rich query-block builder for reranker eval (#95)"
```

---

## Task 3: Pool builder + playable filter (in orchestrator module)

**Files:**
- Create: `scripts/rank_eval_union_pool.py` (start the module with pure helpers)
- Test: `tests/test_rank_eval_union_pool.py`

This task adds only the pure pool/ordering helpers. The CLI and ranker wiring
come in Tasks 4–5. Reuses `union_at_k` from `branch_diagnostics`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rank_eval_union_pool.py
"""Unit tests for scripts/rank_eval_union_pool.py."""
from __future__ import annotations

from scripts.rank_eval_union_pool import build_pool, rrf_order_of_pool, oracle_order


def _branches(fused_ids, pools):
    """Minimal `branches` dict like the trace emits (mirrors test_branch_diagnostics)."""
    return {
        "pools": [{"name": n, "hits": [[t, 1.0] for t in ids]} for n, ids in pools.items()],
        "fused": [[t, 1.0] for t in fused_ids],
        "final": {"track_ids": fused_ids},
    }


def test_build_pool_unions_branch_topk():
    b = _branches(["a", "b"], {"bm25": ["a", "b", "x"], "dense": ["c"]})
    pool = build_pool(b, k=2)
    # bm25 top-2 = {a, b}; dense top-2 = {c}
    assert pool == {"a", "b", "c"}


def test_rrf_order_of_pool_restricts_and_preserves_fused_order():
    b = _branches(["b", "a", "c", "d"], {"bm25": ["a", "b", "c", "d"]})
    pool = {"a", "c"}
    # fused order is b,a,c,d -> restricted to {a,c} -> [a, c]
    assert rrf_order_of_pool(b, pool) == ["a", "c"]


def test_oracle_order_puts_gt_first():
    assert oracle_order(["a", "b", "gt", "c"], "gt") == ["gt", "a", "b", "c"]
    # gt absent -> unchanged
    assert oracle_order(["a", "b"], "gt") == ["a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rank_eval_union_pool.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.rank_eval_union_pool'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/rank_eval_union_pool.py
"""Union-pool reranker eval harness (issue #95).

Offline replay: for each turn where the GT is already in the union@k pool,
compare RRF ordering vs an LLM reranker on Hit@1/Hit@20/MRR/NDCG@20. Retrieval
is held fixed (the pool is built from the saved branch pools), so any metric
delta is pure ranking quality.

This file starts with pure pool/ordering helpers (Task 3); the CLI and ranker
wiring are added in later tasks.
"""
from __future__ import annotations

from scripts.branch_diagnostics import union_at_k


def build_pool(branches: dict, k: int) -> set[str]:
    """Dedup union of every branch's top-k hits."""
    return union_at_k(branches, k)


def rrf_order_of_pool(branches: dict, pool: set[str]) -> list[str]:
    """Today's RRF ordering, restricted to pool members (preserves fused order)."""
    return [tid for tid, _ in branches.get("fused", []) if tid in pool]


def oracle_order(ordered_ids: list[str], gt: str) -> list[str]:
    """Perfect-rank ceiling: GT forced to rank 1, rest unchanged."""
    if gt not in ordered_ids:
        return list(ordered_ids)
    return [gt] + [t for t in ordered_ids if t != gt]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rank_eval_union_pool.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/rank_eval_union_pool.py tests/test_rank_eval_union_pool.py
git commit -m "feat: union-pool build + RRF/oracle ordering helpers (#95)"
```

---

## Task 4: Pointwise ranker function (stub-backend testable)

**Files:**
- Modify: `scripts/rank_eval_union_pool.py`
- Test: `tests/test_rank_eval_union_pool.py`

Add a `pointwise_order(query_block, pool_ids, track_text_fn, backend)` that scores
`(query_block, track_text)` pairs with any object exposing `.score(pairs)` and
returns pool ids sorted by score descending. The backend is injected so tests use
a stub (no network).

- [ ] **Step 1: Write the failing test (append to the existing test file)**

```python
# append to tests/test_rank_eval_union_pool.py
from scripts.rank_eval_union_pool import pointwise_order


class _StubBackend:
    """Returns a score per pair from a fixed {doc_text: score} map."""
    def __init__(self, score_by_doc):
        self.score_by_doc = score_by_doc
        self.calls = []

    def score(self, pairs):
        self.calls.append(pairs)
        return [self.score_by_doc[d] for _, d in pairs]


def test_pointwise_order_sorts_by_backend_score_desc():
    pool_ids = ["a", "b", "c"]
    text = {"a": "doc-a", "b": "doc-b", "c": "doc-c"}
    backend = _StubBackend({"doc-a": 0.1, "doc-b": 0.9, "doc-c": 0.5})
    order = pointwise_order("Q", pool_ids, lambda t: text[t], backend)
    assert order == ["b", "c", "a"]
    # one query per pair, all the same query block
    assert all(q == "Q" for q, _ in backend.calls[0])


def test_pointwise_order_empty_pool():
    backend = _StubBackend({})
    assert pointwise_order("Q", [], lambda t: t, backend) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rank_eval_union_pool.py::test_pointwise_order_sorts_by_backend_score_desc -v`
Expected: FAIL with `ImportError: cannot import name 'pointwise_order'`

- [ ] **Step 3: Add the implementation**

```python
# add to scripts/rank_eval_union_pool.py (below oracle_order)
from typing import Callable, Protocol


class ScoreBackend(Protocol):
    def score(self, pairs: list[tuple[str, str]]) -> list[float]: ...


def pointwise_order(
    query_block: str,
    pool_ids: list[str],
    track_text_fn: Callable[[str], str],
    backend: ScoreBackend,
) -> list[str]:
    """Sort pool by pointwise (query_block, track_text) relevance, descending."""
    if not pool_ids:
        return []
    pairs = [(query_block, track_text_fn(tid)) for tid in pool_ids]
    scores = backend.score(pairs)
    return [tid for tid, _ in sorted(zip(pool_ids, scores), key=lambda x: -x[1])]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rank_eval_union_pool.py -v`
Expected: PASS (5 tests total)

- [ ] **Step 5: Commit**

```bash
git add scripts/rank_eval_union_pool.py tests/test_rank_eval_union_pool.py
git commit -m "feat: pointwise ranker ordering (stub-backend testable) (#95)"
```

---

## Task 5: Orchestration core + CLI + output

**Files:**
- Modify: `scripts/rank_eval_union_pool.py`
- Test: `tests/test_rank_eval_union_pool.py`

Add `evaluate_turns(...)` — the streaming core that, given an iterable of
`(branches, state, history, gt)` tuples plus a ranker callable, accumulates
per-ranker metrics on the playable subset — then a thin `main()` CLI around it.
The ranker callable and trace source are injected so the core is testable.

- [ ] **Step 1: Write the failing test (append)**

```python
# append to tests/test_rank_eval_union_pool.py
from scripts.rank_eval_union_pool import evaluate_turns


def test_evaluate_turns_playable_subset_and_metrics():
    # turn 1: gt 'a' in union@2 pool; turn 2: gt 'z' NOT in pool (skipped)
    b1 = _branches(["b", "a", "c"], {"bm25": ["a", "b", "c"]})
    b2 = _branches(["x", "y"], {"bm25": ["x", "y"]})
    turns = [
        (b1, {"turn_intent": "q"}, [], "a"),
        (b2, {"turn_intent": "q"}, [], "z"),
    ]
    # ranker that puts gt first when present (acts like a perfect ranker)
    def perfect_ranker(query_block, pool_ids, gt):
        return [gt] + [t for t in pool_ids if t != gt] if gt in pool_ids else list(pool_ids)

    res = evaluate_turns(turns, k=2, ranker=perfect_ranker, query_profile="lean")
    assert res["n_total"] == 2
    assert res["n_playable"] == 1          # only turn 1 is playable
    assert res["metrics"]["hit@20"] == 1.0  # perfect ranker hits
    assert res["metrics"]["hit@1"] == 1.0
    assert res["mean_pool_size"] == 3       # {a,b,c}


def test_evaluate_turns_no_playable():
    b = _branches(["x"], {"bm25": ["x"]})
    turns = [(b, {"turn_intent": "q"}, [], "gt-not-here")]
    res = evaluate_turns(turns, k=2, ranker=lambda q, p, g: list(p), query_profile="lean")
    assert res["n_playable"] == 0
    assert res["metrics"] == {}  # nothing to average
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rank_eval_union_pool.py::test_evaluate_turns_playable_subset_and_metrics -v`
Expected: FAIL with `ImportError: cannot import name 'evaluate_turns'`

- [ ] **Step 3: Add the implementation**

```python
# add to scripts/rank_eval_union_pool.py
from collections import defaultdict

from scripts.rank_eval_metrics import score_ordering
from scripts.rank_eval_query import build_query_block

_METRIC_KEYS = ["hit@1", "hit@20", "mrr", "ndcg@20"]


def evaluate_turns(turns, k: int, ranker, query_profile: str = "rich") -> dict:
    """Score one ranker over the playable subset.

    `turns` yields (branches, state, history, gt). `ranker(query_block, pool_ids,
    gt) -> ordered_ids` reorders the pool (gt passed only so an oracle/stub can
    use it; real rankers ignore it). Returns counts + mean metrics on the subset.
    """
    n_total = 0
    n_playable = 0
    pool_size_sum = 0
    sums = defaultdict(float)
    for branches, state, history, gt in turns:
        n_total += 1
        if not branches or gt is None:
            continue
        pool = build_pool(branches, k)
        if gt not in pool:
            continue  # retrieval miss — not the ranker's job
        n_playable += 1
        pool_size_sum += len(pool)
        rrf_ordered = rrf_order_of_pool(branches, pool)
        query_block = build_query_block(state, history, profile=query_profile)
        ordered = ranker(query_block, rrf_ordered, gt)
        m = score_ordering(ordered, gt, k=20)
        for key in _METRIC_KEYS:
            sums[key] += m[key]
    metrics = {key: sums[key] / n_playable for key in _METRIC_KEYS} if n_playable else {}
    return {
        "n_total": n_total,
        "n_playable": n_playable,
        "mean_pool_size": (pool_size_sum / n_playable) if n_playable else 0,
        "metrics": metrics,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rank_eval_union_pool.py -v`
Expected: PASS (7 tests total)

- [ ] **Step 5: Add the CLI `main()` (no test — exercised by the smoke run in Task 6)**

```python
# add to scripts/rank_eval_union_pool.py (bottom of file)
import argparse
import json
import sys
from pathlib import Path

from scripts.branch_diagnostics import iter_trace, load_ground_truth_file


def _build_history(played_ids: list[str], history_meta: dict[str, str]) -> list[str]:
    """Annotated history strings (most-recent last) for played track ids."""
    return [history_meta[t] for t in played_ids if t in history_meta]


def _iter_turns(trace_path, gt, history_meta, num_sessions):
    """Yield (branches, state, history, gt) for the first num_sessions sessions."""
    seen_sessions: set[str] = set()
    for r in iter_trace(trace_path):
        sid = r["session_id"]
        if num_sessions and sid not in seen_sessions and len(seen_sessions) >= num_sessions:
            continue
        seen_sessions.add(sid)
        key = (sid, int(r["turn_number"]))
        g = gt.get(key)
        tr = r.get("trace") or {}
        branches = tr.get("branches") or {}
        state = tr.get("state") or {}
        played = (tr.get("resolver") or {}).get("played_track_ids") or []
        yield branches, state, _build_history(played, history_meta), g


def _rrf_ranker(query_block, pool_ids, gt):
    return list(pool_ids)  # already RRF-ordered


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="union-pool reranker eval (#95)")
    ap.add_argument("--trace", required=True)
    ap.add_argument("--ground-truth", required=True)
    ap.add_argument("--k", type=int, default=20, choices=[20, 100])
    ap.add_argument("--ranker", default="rrf", choices=["rrf", "pointwise", "listwise"])
    ap.add_argument("--query-profile", default="rich", choices=["lean", "rich"])
    ap.add_argument("--num-sessions", type=int, default=0, help="0 = all sessions")
    ap.add_argument("--pointwise-model", default="Qwen/Qwen3-Reranker-4B")
    ap.add_argument("--pointwise-backend", default="deepinfra")
    ap.add_argument("--listwise-model", default="openai/gpt-4o-mini")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    gt = load_ground_truth_file(args.ground_truth)

    # Heavy metadata dicts load once (HF dataset). RRF needs neither.
    history_meta: dict[str, str] = {}
    track_text: dict[str, str] = {}
    if args.ranker in ("pointwise", "listwise"):
        from scripts.rerank_offline import build_history_metadata_dict, build_track_text_dict
        history_meta = build_history_metadata_dict()
        track_text = build_track_text_dict()

    if args.ranker == "rrf":
        ranker = _rrf_ranker
    elif args.ranker == "pointwise":
        from mcrs.qu_modules.cross_encoder_reranker import build_backend
        backend = build_backend(args.pointwise_model, backend=args.pointwise_backend)
        def ranker(query_block, pool_ids, gt):
            return pointwise_order(query_block, pool_ids, lambda t: track_text.get(t, ""), backend)
    else:  # listwise — wired in Task 9
        from scripts.listwise_ranker import make_listwise_ranker
        ranker = make_listwise_ranker(args.listwise_model, lambda t: track_text.get(t, ""))

    # RRF needs no metadata; pointwise/listwise built history above.
    turns = _iter_turns(args.trace, gt, history_meta, args.num_sessions)
    res = evaluate_turns(turns, k=args.k, ranker=ranker, query_profile=args.query_profile)

    print(f"ranker={args.ranker}  k={args.k}  profile={args.query_profile}")
    print(f"  n_total={res['n_total']}  n_playable={res['n_playable']}  "
          f"mean_pool_size={res['mean_pool_size']:.0f}")
    for key in _METRIC_KEYS:
        print(f"  {key:<8} = {res['metrics'].get(key, 0.0):.4f}")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps({"args": vars(args), **res}, indent=2))
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Verify RRF path runs end-to-end on a tiny slice (no paid API)**

Run:
```bash
python scripts/rank_eval_union_pool.py \
  --trace exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  --ranker rrf --k 20 --num-sessions 10
```
Expected: prints `n_playable` > 0 and `hit@20`/`ndcg@20` for the RRF baseline.
This is the RRF baseline on the playable subset — it sanity-checks the whole
streaming + pool + metrics path with no API cost. (NOTE: `make_listwise_ranker`
does not exist yet — only the `rrf` and `pointwise` branches run until Task 9.)

- [ ] **Step 7: Commit**

```bash
git add scripts/rank_eval_union_pool.py tests/test_rank_eval_union_pool.py
git commit -m "feat: orchestration core + CLI for union-pool reranker eval (#95)"
```

---

## Task 6: Phase 1 smoke run — pointwise vs RRF (GATE, paid API)

**No code.** Requires `DEEPINFRA_API_TOKEN` and the user's go-ahead (hits the paid
DeepInfra reranker). Matches the project's smoke-slice-first rule.

- [ ] **Step 1: Confirm go-ahead + API token present**

Run: `echo "${DEEPINFRA_API_TOKEN:+set}"` → expect `set`. If empty, STOP and ask
the user to export it. Confirm with the user before spending.

- [ ] **Step 2: Run RRF baseline on the smoke slice**

```bash
python scripts/rank_eval_union_pool.py \
  --trace exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  --ranker rrf --k 20 --num-sessions 20 \
  --out exp/inference/devset/rank_eval_union_pool_rrf_k20_smoke.json
```

- [ ] **Step 3: Run pointwise (rich profile) on the SAME slice**

```bash
python scripts/rank_eval_union_pool.py \
  --trace exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  --ranker pointwise --k 20 --num-sessions 20 --query-profile rich \
  --out exp/inference/devset/rank_eval_union_pool_pointwise_k20_rich_smoke.json
```

- [ ] **Step 4: Report the gate decision**

Compare `ndcg@20` and `hit@20`: pointwise vs RRF on the same 20-session slice.
**Gate:** if pointwise NDCG@20 > RRF NDCG@20, proceed. If not, report and STOP —
the pool is not rankable by this model; do not scale or escalate to listwise
without discussing with the user.

---

## Task 7: Phase 1b — lean-vs-rich query-profile ablation (GATE, paid API)

**No code.** Cheap ablation on the same slice; needs the user's go-ahead.

- [ ] **Step 1: Run pointwise with `--query-profile lean` on the smoke slice**

```bash
python scripts/rank_eval_union_pool.py \
  --trace exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  --ranker pointwise --k 20 --num-sessions 20 --query-profile lean \
  --out exp/inference/devset/rank_eval_union_pool_pointwise_k20_lean_smoke.json
```

- [ ] **Step 2: Compare lean vs rich and record the winner**

Compare against the rich-profile run from Task 6 Step 3. Record which profile
gives higher NDCG@20; that profile is the default for the scaled run. Report to
the user.

---

## Task 8: Listwise ranker module (RankGPT sliding window)

**Files:**
- Create: `scripts/listwise_ranker.py`
- Test: `tests/test_listwise_ranker.py`

The LLM call is injected as `complete_fn(prompt: str) -> str` so the parser and
sliding window are tested with a deterministic stub (no network).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_listwise_ranker.py
"""Unit tests for scripts/listwise_ranker.py."""
from __future__ import annotations

from scripts.listwise_ranker import parse_ranking, listwise_rank


def test_parse_ranking_well_formed():
    # "[2] > [1] > [3]" over a 3-item window -> 0-based [1, 0, 2]
    assert parse_ranking("[2] > [1] > [3]", n=3) == [1, 0, 2]


def test_parse_ranking_dedup_and_fill_missing():
    # duplicates ignored after first; missing indices appended in original order
    assert parse_ranking("[3] > [3] > [1]", n=3) == [2, 0, 1]


def test_parse_ranking_garbage_falls_back_to_identity():
    assert parse_ranking("i cannot help with that", n=3) == [0, 1, 2]


def test_listwise_rank_single_window_reorders():
    items = [("a", "doc-a"), ("b", "doc-b"), ("c", "doc-c")]
    # stub LLM always ranks the window as [2] > [3] > [1]
    def stub(prompt):
        return "[2] > [3] > [1]"
    order = listwise_rank("Q", items, complete_fn=stub, window=20, stride=10)
    assert order == ["b", "c", "a"]


def test_listwise_rank_sliding_window_covers_all():
    items = [(c, f"doc-{c}") for c in "abcde"]
    # stub reverses each window it sees (identity-ish check that all ids survive)
    def stub(prompt):
        # count candidate lines to size the window response
        n = prompt.count("\n[")
        return " > ".join(f"[{i}]" for i in range(n, 0, -1))
    order = listwise_rank("Q", items, complete_fn=stub, window=3, stride=2)
    assert sorted(order) == sorted(c for c in "abcde")
    assert len(order) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_listwise_ranker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.listwise_ranker'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/listwise_ranker.py
"""Hand-rolled listwise reranker (RankGPT-style sliding window) over an injected
LLM completion function. Used by the union-pool eval (issue #95).

`listwise_rank(query_block, items, complete_fn, window, stride)` reorders the
candidate list; `items` is [(track_id, item_text)]. The LLM call is injected so
the parser + window logic are unit-testable; production wiring uses litellm.
"""
from __future__ import annotations

import re
from typing import Callable

_SYS_PROMPT = (
    "You are an expert music recommender. Reorder candidate tracks by how well "
    "each satisfies the user's request. Favor exact matches to a named "
    "track/artist, the requested era, and the stated policy; respect \"Avoid\"."
)


def build_prompt(query_block: str, window_items: list[tuple[str, str]]) -> str:
    lines = [query_block, "", "Candidates:"]
    for i, (_tid, text) in enumerate(window_items, start=1):
        lines.append(f"[{i}] {text}")
    lines.append("")
    lines.append(
        "Rank all candidates most- to least-relevant. Output only the order, "
        "e.g. [4] > [2] > [1] > ..."
    )
    return "\n".join(lines)


def parse_ranking(text: str, n: int) -> list[int]:
    """Parse '[2] > [1] > [3]' into 0-based indices. Dedup, drop out-of-range,
    append any missing indices in original order, fall back to identity on junk."""
    found = [int(m) - 1 for m in re.findall(r"\[(\d+)\]", text)]
    order: list[int] = []
    seen: set[int] = set()
    for idx in found:
        if 0 <= idx < n and idx not in seen:
            seen.add(idx)
            order.append(idx)
    for idx in range(n):
        if idx not in seen:
            order.append(idx)
    return order


def listwise_rank(
    query_block: str,
    items: list[tuple[str, str]],
    complete_fn: Callable[[str], str],
    window: int = 20,
    stride: int = 10,
) -> list[str]:
    """RankGPT sliding window, back-to-front. Returns reordered track_ids."""
    ranked = list(items)
    n = len(ranked)
    if n == 0:
        return []
    # back-to-front passes so the strongest candidates bubble to the global top
    start = max(0, n - window)
    while True:
        win = ranked[start:start + window]
        prompt = build_prompt(query_block, win)
        order = parse_ranking(complete_fn(prompt), len(win))
        ranked[start:start + window] = [win[i] for i in order]
        if start == 0:
            break
        start = max(0, start - stride)
    return [tid for tid, _ in ranked]


def make_listwise_ranker(model: str, track_text_fn: Callable[[str], str]):
    """Production wiring: returns a ranker(query_block, pool_ids, gt) that calls
    litellm against `model`. Imported lazily by the CLI so tests need no litellm."""
    import litellm

    def _complete(prompt: str) -> str:
        resp = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": _SYS_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        return resp.choices[0].message.content or ""

    def ranker(query_block: str, pool_ids: list[str], gt: str) -> list[str]:
        items = [(t, track_text_fn(t)) for t in pool_ids]
        return listwise_rank(query_block, items, complete_fn=_complete)

    return ranker
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_listwise_ranker.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/listwise_ranker.py tests/test_listwise_ranker.py
git commit -m "feat: hand-rolled listwise reranker (sliding window) (#95)"
```

---

## Task 9: Verify listwise wires into the CLI

**Files:**
- Modify: `scripts/rank_eval_union_pool.py` (only if the Task 5 `listwise` branch needs adjustment)
- Test: existing suites

The Task 5 CLI already imports `make_listwise_ranker`. This task confirms the
whole suite is green and the import resolves.

- [ ] **Step 1: Run the full test suite for the new modules**

Run: `python -m pytest tests/test_rank_eval_metrics.py tests/test_rank_eval_query.py tests/test_rank_eval_union_pool.py tests/test_listwise_ranker.py -v`
Expected: PASS (all tests)

- [ ] **Step 2: Confirm the listwise CLI import resolves (no network)**

Run:
```bash
python -c "from scripts.rank_eval_union_pool import main; from scripts.listwise_ranker import make_listwise_ranker; print('imports ok')"
```
Expected: prints `imports ok`.

- [ ] **Step 3: Commit (if any adjustment was needed; otherwise skip)**

```bash
git add scripts/rank_eval_union_pool.py
git commit -m "chore: confirm listwise wiring in union-pool eval CLI (#95)"
```

---

## Task 10: Phase 2 runs — listwise + scale (GATE, paid API)

**No code.** Requires the user's go-ahead and `OPENROUTER_API_KEY` (litellm) +
`DEEPINFRA_API_TOKEN`. Only run after Task 6's gate passed.

- [ ] **Step 1: Listwise smoke slice (rich profile, k=20)**

```bash
python scripts/rank_eval_union_pool.py \
  --trace exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  --ranker listwise --k 20 --num-sessions 20 --query-profile rich \
  --listwise-model openai/gpt-4o-mini \
  --out exp/inference/devset/rank_eval_union_pool_listwise_k20_rich_smoke.json
```
Report listwise vs pointwise vs RRF on the slice. **Gate:** does listwise beat
pointwise enough to justify its cost?

- [ ] **Step 2: Scale the winning ranker to the full playable subset (k=20 and k=100)**

Drop `--num-sessions` (0 = all sessions) for the best ranker/profile from the
gates. Run once with `--k 20` and once with `--k 100`. Confirm cost with the user
before launching (full pointwise ≈ 600k DeepInfra pairs; listwise ≈ one LLM call
per playable turn × windows).

```bash
python scripts/rank_eval_union_pool.py \
  --trace exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl \
  --ground-truth evaluator/exp/ground_truth/devset.json \
  --ranker <winner> --k 20 --query-profile <winner> \
  --out exp/inference/devset/rank_eval_union_pool_<winner>_k20_full.json
```

- [ ] **Step 3: Write up the result and update the issue**

Post the RRF vs pointwise vs listwise table (with n_playable and mean_pool_size)
to issue #95. If a ranker wins, note the Phase 3 follow-on (GBM/LambdaMART
pre-filter, recall target unionhit@100 = 0.662) as a new issue.

---

## Self-Review notes

- **Spec coverage:** pool + playable filter (Task 3), RRF baseline (Tasks 3/5),
  pointwise (Task 4), oracle ceiling (Task 3 — `oracle_order`, available for an
  optional `--ranker oracle`), listwise (Task 8), query lean/rich profiles +
  ablation (Tasks 2/7), metrics Hit@1/Hit@20/MRR/NDCG@20 (Task 1), k∈{20,100}
  (CLI `--k`), num-sessions cost gate (Tasks 5/6/10), JSON+table output (Task 5).
- **Oracle exposure:** `oracle_order` exists and is unit-tested; to surface it in
  the CLI, add `"oracle"` to `--ranker` choices and an `oracle` branch
  (`ranker = lambda q, p, gt: oracle_order(p, gt)`). Optional — not required for
  the headline RRF-vs-LLM comparison.
- **No new dependency:** listwise uses the already-present `litellm`; rank_llm
  intentionally avoided (per spec).
