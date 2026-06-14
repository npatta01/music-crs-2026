# Response-Gen V0: State-Serialization Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the state-conditioned response path see the *full* extracted state — restore `mentioned_entities`, `explicit_rejections`, and `release_year_range`, which are currently silently dropped before they reach the response generator.

**Architecture:** Those three fields are plain `@property` on `ConversationStateV0Plus`, so `state.model_dump(mode="json")` omits them. The trace dict built in `compiler_v0plus_qu._acompile_one` stores that lossy dump under `trace["state"]`, and `crs_baseline.batch_chat` feeds it to `format_state_block`. Fix: a small **local augmentation helper** (`response_state_dict`) that dumps the model *and* adds the three derived fields, used at the single trace-emission site. No global `@computed_field` (it would change every `model_dump` caller).

**Tech Stack:** Python 3.10, pydantic v2, pytest. Source: `mcrs/`. Tests: `tests/`.

**Scope:** This is **Plan 1 of the response-gen judge sweep** (spec: [`docs/superpowers/specs/2026-06-13-response-gen-judge-sweep-design.md`](../specs/2026-06-13-response-gen-judge-sweep-design.md), variant **V0**). It is intentionally standalone — it produces working, tested software on its own (a correctly-serialized response state) and is landable/PR-able before any sweep work. The sweep harness, offline judge, variants V1–V5, and model arm M1 are **follow-on plans** (see "Roadmap" at the end) because they depend on this fix landing and on the spec's §10 open decisions.

**Why it was never caught (read before writing tests):** the existing trace test `tests/test_v0plus_compiler_qu.py::test_batch_compile_track_ids_populates_last_traces` drives a **fake `_state()`** double whose `model_dump` *does* include these fields. The bug only manifests with the *real* `ConversationStateV0Plus`. **Every test below must use the real schema, not the `_state()` fake.**

---

## File Structure

- **Create:** nothing new.
- **Modify:** `mcrs/response_context.py` — add `response_state_dict(state) -> dict` (duck-typed; no new imports). This is the natural home: it sits next to `format_state_block`, its sole consumer-shape owner.
- **Modify:** `mcrs/qu_modules/compiler_v0plus_qu.py` — import and call `response_state_dict` at the trace-emission site (line 746).
- **Test:** `tests/test_response_context.py` — unit tests for the helper against the real schema (authoritative).
- **Test:** `tests/test_v0plus_compiler_qu.py` — one integration test proving the wired trace carries the fields when a real state flows through.

---

## Task 1: `response_state_dict` helper (authoritative unit tests)

**Files:**
- Modify: `mcrs/response_context.py`
- Test: `tests/test_response_context.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_response_context.py`)

```python
from mcrs.response_context import (
    format_state_block, is_metadata_echo, xml_track_item, response_state_dict,
)
from mcrs.conversation_state.schema import (
    ConversationStateV0Plus, StateEntity, EntityRole,
    TemporalConstraint, TemporalConstraintKind, ConstraintStrength,
)


def _real_state_with_derived_fields() -> ConversationStateV0Plus:
    """A REAL V0Plus (not the test fake) whose three derived @property fields
    are all non-empty: a seed artist (+1), a rejected artist (-1 + rejection),
    and a temporal range."""
    return ConversationStateV0Plus(
        turn_intent="something from the 90s, not Coldplay",
        entities=[
            StateEntity(type="artist", value="Radiohead", role=EntityRole.seed,
                        source_turn=1, mentioned_current_turn=True, use_as_retrieval_seed=True),
            StateEntity(type="artist", value="Coldplay", role=EntityRole.rejected,
                        source_turn=1, mentioned_current_turn=True, use_as_retrieval_seed=False),
        ],
        temporal_constraint=TemporalConstraint(
            kind=TemporalConstraintKind.style_era, strength=ConstraintStrength.soft,
            start_year=1990, end_year=1999,
        ),
    )


def test_model_dump_drops_derived_properties_documents_the_bug():
    # The three fields the response path needs are @property -> model_dump omits them.
    raw = _real_state_with_derived_fields().model_dump(mode="json")
    assert "mentioned_entities" not in raw
    assert "explicit_rejections" not in raw
    assert "release_year_range" not in raw


def test_response_state_dict_restores_derived_properties():
    state = _real_state_with_derived_fields()
    d = response_state_dict(state)
    # Plain fields still present.
    assert d["turn_intent"] == "something from the 90s, not Coldplay"
    # Derived fields restored, in the dict shape format_state_block reads.
    values = {m["value"] for m in d["mentioned_entities"]}
    assert {"Radiohead", "Coldplay"} <= values
    assert any(m["sentiment"] > 0 and m["value"] == "Radiohead" for m in d["mentioned_entities"])
    assert any(r["kind"] == "artist" and r["value"] == "Coldplay" for r in d["explicit_rejections"])
    assert d["release_year_range"]["start"] == 1990 and d["release_year_range"]["end"] == 1999


def test_response_state_dict_release_year_range_none_when_absent():
    d = response_state_dict(ConversationStateV0Plus(turn_intent="anything"))
    assert d["release_year_range"] is None
    assert d["mentioned_entities"] == []
    assert d["explicit_rejections"] == []


def test_format_state_block_renders_derived_fields_via_helper():
    # End-to-end: the helper output makes format_state_block emit the lines that
    # were silently empty in production.
    block = format_state_block(response_state_dict(_real_state_with_derived_fields()), None)
    assert "Radiohead" in block          # Liked / wants
    assert "Coldplay" in block           # Disliked / avoid + explicit rejection
    assert "Explicit rejections:" in block
    assert "1990-1999" in block
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_response_context.py -v -k "derived or response_state_dict"`
Expected: FAIL — `ImportError: cannot import name 'response_state_dict'` (and once that's stubbed, the assertions fail). `test_model_dump_drops_derived_properties_documents_the_bug` should PASS immediately (it asserts the bug).

- [ ] **Step 3: Implement `response_state_dict`** (add to `mcrs/response_context.py`, after `format_state_block`)

```python
def response_state_dict(state: Any) -> dict:
    """Serialize a ConversationStateV0Plus for the response path.

    pydantic's ``model_dump()`` only serializes declared fields, so the derived
    ``@property`` fields the response prompt depends on — ``mentioned_entities``,
    ``explicit_rejections``, ``release_year_range`` — are dropped. This augments
    the dump with their evaluated values in the dict shape ``format_state_block``
    consumes. Duck-typed (no schema import) so this module stays dependency-free.
    """
    d = state.model_dump(mode="json")
    d["mentioned_entities"] = [m.model_dump(mode="json") for m in state.mentioned_entities]
    d["explicit_rejections"] = [r.model_dump(mode="json") for r in state.explicit_rejections]
    ryr = state.release_year_range
    d["release_year_range"] = ryr.model_dump(mode="json") if ryr is not None else None
    return d
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_response_context.py -v`
Expected: PASS (all, including the pre-existing `format_state_block`/`xml_track_item` tests).

- [ ] **Step 5: Commit**

```bash
git add mcrs/response_context.py tests/test_response_context.py
git commit -m "fix(respgen): restore derived state fields dropped by model_dump (V0)

mentioned_entities/explicit_rejections/release_year_range are @property on
ConversationStateV0Plus and were silently dropped by model_dump(), so the
state-conditioned response prompt never saw the user's mentioned artists/tags,
explicit rejections, or year range. Add response_state_dict() augmentation."
```

---

## Task 2: Wire the helper into the trace-emission site

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus_qu.py` (import near top; call site at line 746)
- Test: `tests/test_v0plus_compiler_qu.py`

- [ ] **Step 1: Write the failing integration test** (append to `tests/test_v0plus_compiler_qu.py`)

```python
def test_last_traces_state_serializes_derived_property_fields():
    """V0 regression with the REAL schema (the existing trace test uses a fake
    _state() whose model_dump already includes these fields, so it cannot catch
    the bug). With the real ConversationStateV0Plus, the trace state dict must
    still carry the three derived @property fields the response path reads."""
    from mcrs.conversation_state.schema import (
        ConversationStateV0Plus, StateEntity, EntityRole,
        TemporalConstraint, TemporalConstraintKind, ConstraintStrength,
    )
    real_state = ConversationStateV0Plus(
        turn_intent="90s, not Coldplay",
        entities=[
            StateEntity(type="artist", value="Radiohead", role=EntityRole.seed,
                        source_turn=1, mentioned_current_turn=True, use_as_retrieval_seed=True),
            StateEntity(type="artist", value="Coldplay", role=EntityRole.rejected,
                        source_turn=1, mentioned_current_turn=True, use_as_retrieval_seed=False),
        ],
        temporal_constraint=TemporalConstraint(
            kind=TemporalConstraintKind.style_era, strength=ConstraintStrength.soft,
            start_year=1990, end_year=1999),
    )
    qu = _build_qu(real_state)  # existing helper; wraps a _FakeExtractor returning `state`
    qu.batch_compile_track_ids([[{"role": "user", "content": "hi"}]], topk=10)
    state_dump = qu.last_traces[0]["state"]
    assert "mentioned_entities" in state_dump
    assert "explicit_rejections" in state_dump
    assert "release_year_range" in state_dump
    assert state_dump["release_year_range"]["start"] == 1990
```

> **If `_build_qu` rejects a real state** (the fakes were built around the `_state()` double and may call methods the real resolver path needs differently): do not fight it. Delete this integration test and rely on Task 1's `test_format_state_block_renders_derived_fields_via_helper` as the behavioral guarantee — the call-site change below is a one-line substitution that Task 1 fully covers by construction. Note the decision in the commit message.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_v0plus_compiler_qu.py::test_last_traces_state_serializes_derived_property_fields -v`
Expected: FAIL — `KeyError`/`assert "mentioned_entities" in state_dump` is False (line 746 still uses bare `model_dump`).

- [ ] **Step 3: Add the import** near the other imports at the top of `mcrs/qu_modules/compiler_v0plus_qu.py`

```python
from mcrs.response_context import response_state_dict
```

- [ ] **Step 4: Swap the call site** in `mcrs/qu_modules/compiler_v0plus_qu.py` (inside `_acompile_one`, currently line 746)

Change:
```python
            "state": state.model_dump(mode="json"),
```
to:
```python
            "state": response_state_dict(state),
```

- [ ] **Step 5: Run the new test + the existing trace/QU suite**

Run: `pytest tests/test_v0plus_compiler_qu.py -v`
Expected: PASS — the new test passes, and all pre-existing tests (incl. `test_batch_compile_track_ids_populates_last_traces`) stay green (no regression).

- [ ] **Step 6: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus_qu.py tests/test_v0plus_compiler_qu.py
git commit -m "fix(respgen): emit augmented response state in the v0+ trace (V0 wiring)"
```

---

## Task 3: Full-suite regression + manual trace eyeball

**Files:** none (verification only)

- [ ] **Step 1: Run the response + compiler test suites together**

Run: `pytest tests/test_response_context.py tests/test_v0plus_compiler_qu.py tests/test_crs_baseline_response.py -v`
Expected: PASS (no regressions in the response path).

- [ ] **Step 2: (Optional, needs a real run) Eyeball one regenerated trace**

After this lands, when the next devset/blind `rr2` run is produced (Plan 2 regenerates the frozen traces anyway), open `exp/inference/<split>/<tid>_trace.jsonl` and confirm a turn's `state` block now contains non-empty `mentioned_entities` / `explicit_rejections` / `release_year_range` where the conversation warrants them. This is a sanity check, not a gate — the unit tests are the gate.

- [ ] **Step 3: Confirm clean tree**

Run: `git status`
Expected: clean (both commits landed).

---

## Self-Review

- **Spec coverage:** Implements spec variant **V0** (state-serialization fix) and its §9 work-map line (`compiler_v0plus_qu.py` augmentation + regression test on `format_state_block`) and the §10 resolution (local helper, not global `@computed_field`). ✅
- **No placeholders:** every step has runnable code/commands. ✅
- **Type consistency:** the helper is named `response_state_dict` in the source step (Task 1 Step 3), the import (Task 2 Step 3), and all test imports — consistent. The dict keys (`mentioned_entities`, `explicit_rejections`, `release_year_range`) match exactly what `format_state_block` reads (`response_context.py:80,93,97`). ✅
- **Scope:** standalone, landable; produces tested working software on its own. ✅

---

## Roadmap — follow-on plans (author after V0 lands)

These are deliberately *not* expanded here: each depends on V0 being in, and on spec §10 open decisions being settled. Author each as its own plan via the writing-plans skill when its predecessor lands.

- **Plan 2 — Retrieval-frozen replay harness.** New `batch_respond(...)` in `crs_baseline.py` (stages 0/2 from cached retrieval, assert track-IDs byte-identical); `scripts/respgen/run_variant.py`; **regenerate the frozen devset/blind `rr2` traces once post-V0** (Codex: cached traces predate V0) and assert track-IDs match the committed cache. *Depends on V0.*
- **Plan 3 — Offline judge.** `scripts/respgen/offline_judge.py`: reference-FREE Gemini-primary + neutral diagnostic, bootstrap CIs, acceptance gate vs the 4 Blind-A anchors. *Depends on Plan 2's replay output to score.*
- **Plan 4 — Variants + model arm.** V1 (`listener_goal` via `session_meta`), V2 (`build_grounding_scaffold` + in-pool branch check + whitelisted fields), V3 (register-match), V4 (explicit turn-context block), V5 (stack), M1 (Gemini generator). All arms at **temperature 0** (override prod `0.7`). *Depends on Plans 2–3.*
- **Plan 5 — Sweep execution runbook.** Stratified screening slice, `judge_tracker.md`, predeclared `δ` stop rule, Wave 0/1 submission protocol. *Manual runbook, not code.*
