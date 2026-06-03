"""End-to-end smoke for the v0+ QU wrapper.

Uses the test fakes (DictCatalog + FakeRetriever + FakeEmbeddingClient) plus
an injected fake LiteLLMExtractor so the whole pipeline runs offline.
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from mcrs.conversation_state.schema import (
    ConversationStateV0Plus,
    ExplicitRejection,
    MentionedEntity,
    TrackFeedback,
)
from mcrs.qu_modules import load_qu_module
from mcrs.qu_modules.compiler_v0plus_qu import (
    LiteLLMExtractor,
    V0PlusCompilerQU,
    build_v0plus_compiler_qu,
    session_memory_to_conversation,
)
from mcrs.qu_modules.fuzzy_matcher import RapidfuzzCatalogMatcher
from tests.v0plus_fakes import DictCatalog, FakeEmbeddingClient, FakeRetriever


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


def _catalog() -> DictCatalog:
    return DictCatalog(
        tracks={
            "t-morphine-1": {
                "artist_id": "a-morphine", "artist_name": "Morphine",
                "track_name": "Cure for Pain",
                "tag_list": ["smoky", "lounge"],
                "popularity": 70.0, "release_date": "1993-09-14",
                "metadata_vector": [1.0, 0.0, 0.0],
            },
            "t-fugazi-1": {
                "artist_id": "a-fugazi", "artist_name": "Fugazi",
                "track_name": "Waiting Room",
                "tag_list": ["post-hardcore"],
                "popularity": 80.0, "release_date": "1988-11-04",
                "metadata_vector": [0.0, 1.0, 0.0],
            },
            "t-filler-1": {
                "artist_id": "a-filler", "artist_name": "Filler",
                "track_name": "Filler",
                "tag_list": [],
                "popularity": 50.0, "release_date": "2010-01-01",
                "metadata_vector": [0.0, 0.0, 1.0],
            },
        }
    )


@dataclass
class _FakeExtractor:
    """Returns a scripted ConversationStateV0Plus regardless of input.
    Pass `state=None` to simulate extractor failure."""

    state: ConversationStateV0Plus | None = None

    def extract(self, conversation, played_track_ids):
        return self.state

    async def aextract(self, conversation, played_track_ids):
        return self.state


@dataclass
class _ConcurrencyRecordingExtractor:
    """Tracks max concurrent in-flight `aextract` calls and per-call latency.
    Used to verify the async batch fan-out is actually parallelizing."""

    state: ConversationStateV0Plus | None = None
    per_call_sleep_s: float = 0.05
    in_flight: int = 0
    max_in_flight_observed: int = 0
    call_count: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def extract(self, conversation, played_track_ids):
        raise NotImplementedError("use aextract — this fake only supports the async path")

    async def aextract(self, conversation, played_track_ids):
        async with self._lock:
            self.in_flight += 1
            self.max_in_flight_observed = max(self.max_in_flight_observed, self.in_flight)
            self.call_count += 1
        try:
            await asyncio.sleep(self.per_call_sleep_s)
            return self.state
        finally:
            async with self._lock:
                self.in_flight -= 1


_SENTINEL = object()


def _state(**overrides) -> ConversationStateV0Plus:
    defaults = dict(
        turn_intent="anything",
        intent_mode="refinement",
        track_feedback=[],
        referenced_track_ids=[],
        mentioned_entities=[],
        hard_filters=[],
        explicit_rejections=[],
    )
    defaults.update(overrides)
    return ConversationStateV0Plus(**defaults)


def _build_qu(state=_SENTINEL) -> V0PlusCompilerQU:
    """`state=_SENTINEL` (default) → extractor returns default _state().
    `state=None` → extractor returns None (LLM failure simulation).
    `state=<ConversationStateV0Plus>` → extractor returns that."""
    extracted = _state() if state is _SENTINEL else state
    catalog = _catalog()
    return build_v0plus_compiler_qu(
        qu_kwargs={},
        _overrides={
            "catalog": catalog,
            "matcher": RapidfuzzCatalogMatcher(catalog),
            "encoder": FakeEmbeddingClient(vector=[0.5, 0.5, 0.5]),
            "retriever": FakeRetriever(
                text_hits_by_field={
                    "artist_name": [("t-morphine-1", 5.0), ("t-fugazi-1", 3.0)],
                    "tag_list": [("t-morphine-1", 2.0)],
                },
                embedding_hits=[("t-morphine-1", 0.9), ("t-fugazi-1", 0.7)],
            ),
            "extractor": _FakeExtractor(state=extracted),
        },
    )


# ---------------------------------------------------------------------
# session_memory -> v0+ conversation format
# ---------------------------------------------------------------------


def test_session_memory_to_conversation_basic_shape():
    memory = [
        {"role": "user", "content": "play me something smoky"},
        {"role": "assistant", "content": "how about Morphine"},
        {"role": "music", "content": "t-morphine-1"},
        {"role": "user", "content": "more like that"},
    ]
    conv, played = session_memory_to_conversation(memory)
    assert played == ["t-morphine-1"]
    assert [c["role"] for c in conv] == ["user", "assistant", "music", "user"]
    # turn numbers increment on each user message
    assert conv[0]["turn"] == 1
    assert conv[1]["turn"] == 1
    assert conv[2]["turn"] == 1
    assert conv[3]["turn"] == 2


def test_session_memory_to_conversation_attaches_track_id_for_music_items():
    memory = [
        {"role": "user", "content": "x"},
        {"role": "music", "content": "t-abc"},
    ]
    conv, played = session_memory_to_conversation(memory)
    music_item = next(c for c in conv if c["role"] == "music")
    assert music_item["track_id"] == "t-abc"
    assert "label" in music_item


# ---------------------------------------------------------------------
# QU wrapper end-to-end
# ---------------------------------------------------------------------


def test_qu_wrapper_compile_track_ids_runs_full_pipeline():
    state = _state(
        turn_intent="more like Morphine",
        mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)],
        explicit_rejections=[ExplicitRejection(kind="artist", value="Fugazi", source_turn=2)],
    )
    qu = _build_qu(state)
    # No music turns yet -> nothing in played_track_ids -> Morphine isn't pre-dropped
    result = qu.compile_track_ids(
        [{"role": "user", "content": "play me Morphine"}]
    )
    # Fugazi resolved + hard-dropped via artist rejection
    assert "t-fugazi-1" not in result
    # Morphine retained (top-ranked from BM25 + dense)
    assert "t-morphine-1" in result
    assert result[0] == "t-morphine-1"


def test_qu_wrapper_compile_track_ids_hard_drops_played_tracks():
    """When the conversation has played a track, it must be excluded from results
    (challenge convention)."""
    state = _state(
        turn_intent="more",
        mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)],
    )
    qu = _build_qu(state)
    result = qu.compile_track_ids(
        [
            {"role": "user", "content": "play"},
            {"role": "music", "content": "t-morphine-1"},  # played -> hard-drop
            {"role": "user", "content": "more"},
        ]
    )
    assert "t-morphine-1" not in result


def test_qu_wrapper_transform_query_returns_state_json():
    state = _state(turn_intent="something smoky")
    qu = _build_qu(state)
    out = qu.transform_query([{"role": "user", "content": "anything"}])
    assert isinstance(out, str)
    assert "turn_intent" in out
    assert "something smoky" in out


def test_qu_wrapper_extractor_failure_returns_empty_list():
    """When the extractor fails, the QU returns []. CRS_BASELINE handles
    empty by passing recommend_item=None to the LM; eval scores the row as
    zero hits — that's the honest signal. Popularity backfill is
    intentionally NOT applied here because it would bypass any resolver
    filters that would normally have run."""
    qu = _build_qu(state=None)  # extractor returns None
    memory = [{"role": "user", "content": "hi"}]
    result = qu.compile_track_ids(memory, topk=10)
    assert result == []


# ---------------------------------------------------------------------
# load_qu_module dispatch
# ---------------------------------------------------------------------


def test_load_qu_module_rejects_v0plus_compiler_without_lancedb_settings():
    """Verifies the dispatch path; without lancedb config the LanceDB connect
    will fail. We just confirm the dispatch routes correctly by catching the
    expected failure."""
    with pytest.raises((KeyError, FileNotFoundError, Exception)):
        load_qu_module(
            "v0plus_compiler",
            # No qu_kwargs => no lancedb config => construction will fail.
        )


def test_load_qu_module_unsupported_raises():
    with pytest.raises(ValueError, match="Unsupported QU type"):
        load_qu_module("not_a_real_qu_type")


# ---------------------------------------------------------------------
# Encoder backend selection
# ---------------------------------------------------------------------


def test_build_qu_rejects_unknown_encoder_backend():
    catalog = _catalog()
    with pytest.raises(ValueError, match="Unknown encoder.backend"):
        build_v0plus_compiler_qu(
            qu_kwargs={"encoder": {"backend": "bogus"}},
            _overrides={
                "catalog": catalog,
                "matcher": RapidfuzzCatalogMatcher(catalog),
                # retriever / extractor / compiler aren't reached — factory
                # bails on the encoder branch first.
                "retriever": FakeRetriever(),
                "extractor": _FakeExtractor(state=_state()),
            },
        )


# ---------------------------------------------------------------------
# Async batch fan-out
# ---------------------------------------------------------------------


def _build_qu_with_extractor(extractor, max_in_flight: int) -> V0PlusCompilerQU:
    catalog = _catalog()
    qu = build_v0plus_compiler_qu(
        qu_kwargs={"max_in_flight": max_in_flight},
        _overrides={
            "catalog": catalog,
            "matcher": RapidfuzzCatalogMatcher(catalog),
            "encoder": FakeEmbeddingClient(vector=[0.5, 0.5, 0.5]),
            "retriever": FakeRetriever(
                text_hits_by_field={
                    "artist_name": [("t-morphine-1", 5.0), ("t-fugazi-1", 3.0)],
                },
                embedding_hits=[("t-morphine-1", 0.9)],
            ),
            "extractor": extractor,
        },
    )
    assert qu.max_in_flight == max_in_flight
    return qu


def test_batch_compile_track_ids_runs_extractor_calls_concurrently():
    """N entries with 50 ms simulated latency should complete in roughly one
    'wave' when max_in_flight ≥ N — not N × 50 ms (which would mean serial)."""
    ext = _ConcurrencyRecordingExtractor(state=_state(turn_intent="x"), per_call_sleep_s=0.05)
    qu = _build_qu_with_extractor(ext, max_in_flight=8)
    n = 8
    memories = [[{"role": "user", "content": f"q{i}"}] for i in range(n)]

    t0 = time.perf_counter()
    results = qu.batch_compile_track_ids(memories, topk=5)
    elapsed = time.perf_counter() - t0

    assert len(results) == n
    assert ext.call_count == n
    # Concurrency actually happened — at some point ≥ 2 calls were in flight.
    assert ext.max_in_flight_observed >= 2, (
        f"expected at least 2 concurrent calls, observed max {ext.max_in_flight_observed}"
    )
    # With 8 calls × 50 ms each, serial would be ~400 ms. Concurrent should
    # finish in well under 200 ms even on a slow CI box.
    assert elapsed < 0.2, f"batch took {elapsed:.3f}s — looks serial"


def test_batch_compile_track_ids_respects_max_in_flight_cap():
    """With max_in_flight=2, 6 calls should never have more than 2 in flight
    at once. Latency-based verification: 6 × 50 ms with cap 2 ≈ 3 waves ≈ 150 ms."""
    ext = _ConcurrencyRecordingExtractor(state=_state(turn_intent="x"), per_call_sleep_s=0.05)
    qu = _build_qu_with_extractor(ext, max_in_flight=2)
    memories = [[{"role": "user", "content": f"q{i}"}] for i in range(6)]

    results = qu.batch_compile_track_ids(memories, topk=5)

    assert len(results) == 6
    assert ext.max_in_flight_observed <= 2, (
        f"semaphore was supposed to cap at 2 but {ext.max_in_flight_observed} ran together"
    )


def test_batch_compile_track_ids_handles_empty_batch():
    ext = _FakeExtractor(state=_state())
    qu = _build_qu_with_extractor(ext, max_in_flight=4)
    assert qu.batch_compile_track_ids([], topk=10) == []
    # Empty batch should still reset the trace list (so a previous call's
    # traces don't leak into an empty rerun).
    assert qu.last_traces == []


def test_batch_compile_track_ids_populates_last_traces():
    """The QU records a per-session trace so callers (e.g. run_inference_devset)
    can save extracted state + resolver/compiler decisions alongside predictions.

    Contract: `last_traces` is set on every `batch_compile_track_ids` call,
    one entry per input session, in input order, with the documented shape.
    """
    state = _state(
        turn_intent="more like Morphine",
        mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)],
        explicit_rejections=[ExplicitRejection(kind="artist", value="Fugazi", source_turn=2)],
    )
    qu = _build_qu(state)
    session_memories = [
        [{"role": "user", "content": "hi"}],
        [{"role": "user", "content": "bye"}],
    ]
    out = qu.batch_compile_track_ids(session_memories, topk=10)
    assert len(out) == 2
    assert len(qu.last_traces) == 2
    for trace in qu.last_traces:
        assert trace["intent_mode"] == "refinement"
        # Full state dump round-trips fields the caller cares about.
        assert trace["state"]["turn_intent"] == "more like Morphine"
        # Resolver block carries the resolved rejection ids + anchor lists.
        assert "anchor_artist_ids" in trace["resolver"]
        assert "rejected_artist_ids" in trace["resolver"]
        # Compiler block carries the summary counts.
        assert trace["compiler"]["n_explicit_rejections"] == 1
        assert trace["compiler"]["n_candidates"] == len(out[0])


def test_batch_compile_track_ids_trace_handles_extractor_failure():
    """When the extractor returns None for a session, the trace still records
    that fact (so the user can tell extractor failure from compiler emptiness)."""
    qu = _build_qu(state=None)
    out = qu.batch_compile_track_ids([[{"role": "user", "content": "x"}]], topk=10)
    assert out == [[]]
    assert len(qu.last_traces) == 1
    t = qu.last_traces[0]
    assert t["state"] is None
    assert t["intent_mode"] is None
    assert t["compiler"]["extractor_returned_none"] is True


def test_litellm_extractor_manually_stores_only_valid_responses(monkeypatch):
    completion_kwargs = []
    stored = []

    class FakeCache:
        def add_cache(self, result, **kwargs):
            stored.append((result, kwargs))

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"turn_intent": "more like Fugazi", "intent_mode": "refinement"}'
                )
            )
        ],
        model_dump_json=lambda: '{"cached": true}',
    )

    def fake_completion(**kwargs):
        completion_kwargs.append(kwargs)
        return response

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(completion=fake_completion, cache=FakeCache()),
    )

    extractor = LiteLLMExtractor(model_name="openrouter/fake", retry_temperature=0.0)

    state = extractor.extract([{"turn": 1, "role": "user", "text": "x"}], [])

    assert state is not None
    assert state.turn_intent == "more like Fugazi"
    assert completion_kwargs[0]["cache"] == {"no-store": True}
    assert stored == [
        (
            '{"cached": true}',
            {key: value for key, value in completion_kwargs[0].items() if key != "cache"},
        )
    ]


def test_litellm_extractor_does_not_store_malformed_json(monkeypatch):
    stored = []
    completion_kwargs = []

    class FakeCache:
        def add_cache(self, result, **kwargs):
            stored.append((result, kwargs))

    def fake_completion(**kwargs):
        completion_kwargs.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"turn_intent": "broken"')
                )
            ]
        )

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(completion=fake_completion, cache=FakeCache()),
    )

    extractor = LiteLLMExtractor(model_name="openrouter/fake", retry_temperature=0.0)

    assert extractor.extract([{"turn": 1, "role": "user", "text": "x"}], []) is None
    assert completion_kwargs[0]["cache"] == {"no-store": True}
    assert stored == []


def test_litellm_extractor_manually_stores_only_valid_responses_async(monkeypatch):
    completion_kwargs = []
    stored = []

    class FakeCache:
        async def async_add_cache(self, result, **kwargs):
            stored.append((result, kwargs))

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"turn_intent": "more like Fugazi", "intent_mode": "refinement"}'
                )
            )
        ],
        model_dump_json=lambda: '{"cached": true}',
    )

    async def fake_acompletion(**kwargs):
        completion_kwargs.append(kwargs)
        return response

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(acompletion=fake_acompletion, cache=FakeCache()),
    )

    extractor = LiteLLMExtractor(model_name="openrouter/fake", retry_temperature=0.0)

    state = asyncio.run(extractor.aextract([{"turn": 1, "role": "user", "text": "x"}], []))

    assert state is not None
    assert state.turn_intent == "more like Fugazi"
    assert completion_kwargs[0]["cache"] == {"no-store": True}
    assert stored == [
        (
            '{"cached": true}',
            {key: value for key, value in completion_kwargs[0].items() if key != "cache"},
        )
    ]


def test_litellm_extractor_no_store_prevents_async_malformed_cache_write(monkeypatch):
    deferred_bad_writes = []
    completion_kwargs = []

    async def fake_acompletion(**kwargs):
        completion_kwargs.append(kwargs)
        if kwargs.get("cache", {}).get("no-store") is not True:
            async def deferred_write():
                await asyncio.sleep(0)
                deferred_bad_writes.append("bad-json-wrote-after-eviction")

            asyncio.create_task(deferred_write())
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"turn_intent": "broken"')
                )
            ]
        )

    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(acompletion=fake_acompletion, cache=SimpleNamespace()),
    )

    extractor = LiteLLMExtractor(model_name="openrouter/fake", retry_temperature=0.0)

    async def exercise_extractor():
        result = await extractor.aextract([{"turn": 1, "role": "user", "text": "x"}], [])
        await asyncio.sleep(0)
        return result

    result = asyncio.run(exercise_extractor())

    assert result is None
    assert completion_kwargs[0]["cache"] == {"no-store": True}
    assert deferred_bad_writes == []


def test_batch_compile_track_ids_returns_results_in_input_order():
    """`asyncio.gather` preserves order even when tasks complete out of order
    (variable per-call latency). Verify by giving each entry a distinguishable
    state and checking results map back correctly."""
    # State1 references Morphine, state2 references Fugazi.
    s1 = _state(mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)])
    s2 = _state(mentioned_entities=[MentionedEntity(type="artist", value="Fugazi", sentiment=1)])

    @dataclass
    class _IndexedExtractor:
        states: list
        idx: int = 0

        async def aextract(self, conversation, played_track_ids):
            # Read which session this is from the conversation text "q{i}"
            text = conversation[-1]["text"]
            i = int(text[1:])
            # Asymmetric latency — later entries return faster, would scramble
            # output if gather didn't preserve order.
            await asyncio.sleep(0.05 - 0.005 * i)
            return self.states[i]

        def extract(self, *a, **kw):
            raise NotImplementedError

    ext = _IndexedExtractor(states=[s1, s2])
    qu = _build_qu_with_extractor(ext, max_in_flight=4)
    memories = [
        [{"role": "user", "content": "q0"}],
        [{"role": "user", "content": "q1"}],
    ]
    results = qu.batch_compile_track_ids(memories, topk=5)
    assert len(results) == 2
    # First entry's state mentioned Morphine -> Morphine should rank first.
    assert results[0][0] == "t-morphine-1"
    # Second entry's state mentioned Fugazi -> Fugazi first (Morphine got
    # demoted to 0 hits because retriever returns artist_name hits for both
    # but only the resolved artist anchor matches).
    assert "t-fugazi-1" in results[1]


# ---------------------------------------------------------------------
# Production catalog wiring (LanceDB-backed)
# ---------------------------------------------------------------------


def test_build_qu_raises_when_no_lancedb_uri(monkeypatch):
    """The factory should raise a clear ValueError when neither MCRS_LANCEDB_URI
    env var nor qu_kwargs.lancedb.db_uri is set and no catalog override is
    given. This is the production wiring's first defensive check — failing
    early here is much friendlier than a mysterious LanceDB connect error."""
    monkeypatch.delenv("MCRS_LANCEDB_URI", raising=False)
    with pytest.raises(ValueError, match="LanceDB URI"):
        build_v0plus_compiler_qu(qu_kwargs={})


def test_build_qu_constructs_lancedb_catalog_from_qu_kwargs(tmp_path, monkeypatch):
    """When no _overrides['catalog'] is provided, build_v0plus_compiler_qu
    constructs a LanceDbCatalog from qu_kwargs.lancedb.db_uri. Tests the new
    production wiring without needing a real model / retriever stack — we
    override every other heavy component."""
    import lancedb
    from datetime import date

    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog

    # Clear any inherited env-var URI so we exercise the qu_kwargs path.
    monkeypatch.delenv("MCRS_LANCEDB_URI", raising=False)

    db = lancedb.connect(str(tmp_path))
    db.create_table(
        "music_track_catalog",
        data=[
            {
                "track_id": "t1", "release_date": date(2020, 1, 1), "popularity": 0.0,
                "track_name": ["X"], "artist_name": ["A"], "artist_id": ["a"],
                "album_name": ["X"], "album_id": ["x"], "tag_list": [],
            },
        ],
    )

    qu = build_v0plus_compiler_qu(
        qu_kwargs={
            "lancedb": {
                "db_uri": str(tmp_path),
                "table_name": "music_track_catalog",
                # Empty eager-load list keeps init cheap; the wiring path is
                # what's under test, not the vector eager-load behavior.
                "eager_vector_fields": [],
            },
            "max_in_flight": 1,
        },
        _overrides={
            # Catalog is INTENTIONALLY omitted — that's what we're testing.
            "extractor": _FakeExtractor(state=_state()),
            "encoder": FakeEmbeddingClient(vector=[0.5, 0.5, 0.5]),
            "retriever": FakeRetriever(),
        },
    )
    assert isinstance(qu.catalog, LanceDbCatalog)
    # Sanity: the catalog actually loaded the fixture row.
    assert qu.catalog.artist_id_of("t1") == "a"


def test_trace_includes_resolved_targets():
    state = _state(
        turn_intent="more like Morphine",
        mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)],
    )
    qu = _build_qu(state)
    qu.batch_compile_track_ids([[{"role": "user", "content": "hi"}]], topk=10)
    trace = qu.last_traces[0]
    rts = trace["resolved_targets"]
    assert any(r["kind"] == "artist" and r["entity_id"] for r in rts)
    assert all({"kind", "source_text", "entity_id", "confidence"} <= set(r) for r in rts)


def test_build_qu_respects_mcrs_lancedb_uri_env_var(tmp_path, monkeypatch):
    """MCRS_LANCEDB_URI overrides qu_kwargs.lancedb.db_uri — matches the
    precedence used elsewhere in this factory (and on Modal)."""
    import lancedb
    from datetime import date

    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog

    db = lancedb.connect(str(tmp_path))
    db.create_table(
        "music_track_catalog",
        data=[
            {
                "track_id": "t-env", "release_date": date(2020, 1, 1), "popularity": 0.0,
                "track_name": ["E"], "artist_name": ["EnvArtist"], "artist_id": ["e"],
                "album_name": ["E"], "album_id": ["e"], "tag_list": [],
            },
        ],
    )
    monkeypatch.setenv("MCRS_LANCEDB_URI", str(tmp_path))

    qu = build_v0plus_compiler_qu(
        qu_kwargs={
            # Bogus db_uri here — env var should win.
            "lancedb": {"db_uri": "/does/not/exist", "eager_vector_fields": []},
        },
        _overrides={
            "extractor": _FakeExtractor(state=_state()),
            "encoder": FakeEmbeddingClient(vector=[0.5, 0.5, 0.5]),
            "retriever": FakeRetriever(),
        },
    )
    assert isinstance(qu.catalog, LanceDbCatalog)
    assert qu.catalog.artist_id_of_name("EnvArtist") == "e"


def test_trace_contains_branches_key():
    """A v0+ QU run with branch tracing on populates trace['branches']."""
    state = _state(
        turn_intent="more like Morphine",
        mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)],
    )
    qu = _build_qu(state)
    qu.compiler.cfg.branch_trace_topk = 50  # enable per-branch tracing
    qu.batch_compile_track_ids([[{"role": "user", "content": "hi"}]], topk=10)
    branches = qu.last_traces[0]["branches"]

    assert set(branches.keys()) == {"depth", "pools", "fused", "final", "recommended"}
    names = [p["name"] for p in branches["pools"]]
    assert "bm25" in names
    assert branches["final"]["track_ids"][:1] == [branches["recommended"]["top1_track_id"]]


def test_shard_slice_math_partitions_all_indices():
    """For any (total, num_shards), every index in [0, total) belongs to exactly one shard."""
    for total in (1, 100, 999, 1000, 1001):
        for num_shards in (1, 2, 3, 4, 7, 8, 10):
            seen = set()
            for shard_id in range(num_shards):
                start = (shard_id * total) // num_shards
                end   = ((shard_id + 1) * total) // num_shards
                for i in range(start, end):
                    assert i not in seen, f"idx {i} in two shards for total={total} S={num_shards}"
                    seen.add(i)
            assert seen == set(range(total)), \
                f"missed indices for total={total} S={num_shards}: {set(range(total)) - seen}"


def test_trace_includes_routing_tags():
    from mcrs.conversation_state.schema import RoutingTags
    state = _state(routing_tags=RoutingTags(lyric_search=True), lyrical_theme="rainy day blues")
    qu = _build_qu(state)
    qu.batch_compile_track_ids([[{"role": "user", "content": "hi"}]], topk=10)
    tr = qu.last_traces[0]
    assert tr["routing_tags"]["lyric_search"] is True
    assert tr["lyrical_theme"] == "rainy day blues"


def test_routing_boost_survives_yaml_allowlist():
    """Guards the disco-branch gotcha: a routing_boost in qu_kwargs.compiler must
    reach CompilerConfig, not be silently dropped by the allowlist filter."""
    import tests.v0plus_fakes as fakes
    catalog = _catalog()
    qu = build_v0plus_compiler_qu(
        qu_kwargs={"compiler": {"routing_boost": {"lyric_search": 4.0}}},
        _overrides={
            "catalog": catalog,
            "matcher": RapidfuzzCatalogMatcher(catalog),
            "encoder": FakeEmbeddingClient(vector=[0.5, 0.5, 0.5]),
            "retriever": FakeRetriever(),
            "extractor": _FakeExtractor(state=_state()),
        },
    )
    assert qu.compiler.cfg.routing_boost == {"lyric_search": 4.0}


def test_build_qu_rejects_missing_configured_vector_fields():
    catalog = _catalog()

    with pytest.raises(ValueError, match="metadata_qwen3_embedding_8b"):
        build_v0plus_compiler_qu(
            qu_kwargs={
                "compiler": {
                    "enable_dense": True,
                    "dense_branches": [
                        {
                            "vector_field": "metadata_qwen3_embedding_8b",
                            "encoder_id": "qwen_8b",
                            "query_id": "metadata",
                        }
                    ],
                }
            },
            _overrides={
                "catalog": catalog,
                "matcher": RapidfuzzCatalogMatcher(catalog),
                "encoders": {"qwen_8b": FakeEmbeddingClient(vector=[0.5, 0.5, 0.5])},
                # FakeRetriever only advertises metadata_qwen3_embedding_0_6b.
                "retriever": FakeRetriever(),
                "extractor": _FakeExtractor(state=_state()),
            },
        )


def test_resolve_prompt_fns_uses_current_prompt():
    from mcrs.qu_modules.compiler_v0plus_qu import _resolve_prompt_fns
    from mcrs.conversation_state.prompts import current

    for alias in ("current", "v4", None):
        bm, schema = _resolve_prompt_fns(alias)
        assert bm is current.build_messages
        assert schema is current.json_schema_for_response_format


def test_resolve_prompt_fns_keeps_previous_reference_prompt():
    from mcrs.qu_modules.compiler_v0plus_qu import _resolve_prompt_fns
    from mcrs.conversation_state.prompts import previous

    for alias in ("previous", "reference", "v3"):
        bm, schema = _resolve_prompt_fns(alias)
        assert bm is previous.build_messages
        assert schema is previous.json_schema_for_response_format


def test_litellm_encoder_forwards_extra_params():
    from mcrs.qu_modules.compiler_v0plus_qu import _build_encoder

    enc = _build_encoder(
        {
            "backend": "litellm",
            "model_name": "openai/Qwen/Qwen3-Embedding-4B",
            "api_base": "https://fake/v1",
            "api_key": "k",
            "extra_params": {"timeout": 600},
        }
    )
    assert enc.extra_params == {"timeout": 600}


def test_litellm_encoder_forwards_cache_and_query_instruct():
    from mcrs.qu_modules.compiler_v0plus_qu import _build_encoder

    instruct = (
        "Instruct: Given a music recommendation conversation, retrieve relevant "
        "track metadata passages.\nQuery: "
    )
    enc = _build_encoder(
        {
            "backend": "litellm",
            "model_name": "openai/Qwen/Qwen3-Embedding-8B",
            "api_base": "https://fake/v1",
            "api_key": "k",
            "encoding_format": "float",
            "cache": {"ttl": 86400},
            "query_instruct": instruct,
        }
    )

    assert enc.cache == {"ttl": 86400}
    assert enc.query_instruct == instruct
    assert enc.build_request_kwargs(["state query"])["input"] == [instruct + "state query"]


def test_openrouter_response_format_goes_in_extra_body_with_require_parameters():
    """litellm strips a top-level response_format for OpenRouter models, so it
    must ride in extra_body, with provider.require_parameters to force a
    schema-enforcing provider. Non-OpenRouter models keep it top-level."""
    from mcrs.qu_modules.compiler_v0plus_qu import LiteLLMExtractor
    ex = LiteLLMExtractor(model_name="openrouter/google/gemma-4-26b-a4b-it", prompt_version="v4")
    kw = ex._build_kwargs(conversation=[{"role": "user", "turn": 1, "text": "hi"}], played_track_ids=[])
    assert "response_format" not in kw, "top-level response_format would be stripped by litellm"
    eb = kw["extra_body"]
    assert eb["response_format"]["type"] == "json_schema"
    assert eb["provider"] == {"require_parameters": True}
    assert eb["reasoning"] == {"enabled": False}

    ex2 = LiteLLMExtractor(model_name="openai/gpt-4o", prompt_version="v4")
    kw2 = ex2._build_kwargs(conversation=[{"role": "user", "turn": 1, "text": "hi"}], played_track_ids=[])
    assert kw2["response_format"]["type"] == "json_schema"  # top-level for non-OpenRouter
    assert "extra_body" not in kw2
