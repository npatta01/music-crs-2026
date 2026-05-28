"""Unit tests for CrossEncoderReranker.

Uses a stub backend so tests run without downloading any model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from mcrs.qu_modules.cross_encoder_reranker import CrossEncoderReranker


@dataclass
class StubBackend:
    """Returns scores from a configured dict keyed by candidate doc text.
    Anything not in the dict gets score 0."""

    score_map: dict = field(default_factory=dict)
    score_calls: list = field(default_factory=list)

    def score(self, pairs):
        self.score_calls.append(list(pairs))
        return [self.score_map.get(doc, 0.0) for _, doc in pairs]


@dataclass
class StubState:
    turn_intent: str = "default"


class StubCatalog:
    def __init__(self, texts: dict[str, str]):
        self.texts = texts

    def track_text(self, track_id: str) -> str:
        return self.texts.get(track_id, "")


def _make_reranker(score_map, top_k=200):
    r = CrossEncoderReranker(
        model_name="stub",
        rerank_top_k=top_k,
        backend=StubBackend(score_map=score_map),
    )
    return r


# ---------------- core behavior ----------------


def test_rerank_reorders_head_by_backend_scores():
    cat = StubCatalog({"t1": "a", "t2": "b", "t3": "c"})
    # backend says t2 is best, t1 mediocre, t3 worst
    r = _make_reranker({"a": 0.3, "b": 0.9, "c": 0.1})
    # Input order: t1, t2, t3 (RRF) — expect t2, t1, t3 after rerank
    fused = [("t1", 0.5), ("t2", 0.4), ("t3", 0.3)]
    out = r.rerank(fused, StubState("anything"), cat)
    assert [tid for tid, _ in out] == ["t2", "t1", "t3"]
    # Scores in output are the backend's scores, not the RRF scores
    by_tid = dict(out)
    assert by_tid["t2"] == 0.9
    assert by_tid["t1"] == 0.3


def test_rerank_passthrough_tail_at_original_positions():
    """rerank_top_k=2 → only reranks t1+t2; t3 t4 t5 keep their RRF positions."""
    cat = StubCatalog({"t1": "a", "t2": "b", "t3": "c", "t4": "d", "t5": "e"})
    r = _make_reranker({"a": 0.1, "b": 0.9}, top_k=2)
    fused = [("t1", 0.5), ("t2", 0.4), ("t3", 0.3), ("t4", 0.2), ("t5", 0.1)]
    out = r.rerank(fused, StubState("q"), cat)
    # Head (first 2): reranked to t2, t1
    # Tail (last 3): passthrough t3, t4, t5 in RRF order
    assert [tid for tid, _ in out] == ["t2", "t1", "t3", "t4", "t5"]
    # Tail scores are unchanged
    by_tid = dict(out)
    assert by_tid["t3"] == 0.3
    assert by_tid["t4"] == 0.2


def test_rerank_returns_input_when_empty():
    r = _make_reranker({})
    assert r.rerank([], StubState("q"), StubCatalog({})) == []


def test_rerank_skips_when_turn_intent_empty():
    """No query → can't score → preserve RRF order, don't call backend."""
    cat = StubCatalog({"t1": "a"})
    backend = StubBackend(score_map={"a": 0.9})
    r = CrossEncoderReranker(model_name="stub", rerank_top_k=10, backend=backend)
    fused = [("t1", 0.5)]
    out = r.rerank(fused, StubState(""), cat)
    assert out == fused
    assert backend.score_calls == []  # backend never invoked


def test_rerank_top_k_caps_at_list_length():
    """rerank_top_k larger than fused list shouldn't error."""
    cat = StubCatalog({"t1": "a", "t2": "b"})
    r = _make_reranker({"a": 0.1, "b": 0.9}, top_k=999)
    fused = [("t1", 0.5), ("t2", 0.4)]
    out = r.rerank(fused, StubState("q"), cat)
    assert [tid for tid, _ in out] == ["t2", "t1"]


def test_rerank_uses_state_turn_intent_as_query():
    cat = StubCatalog({"t1": "doc1"})
    backend = StubBackend(score_map={"doc1": 1.0})
    r = CrossEncoderReranker(model_name="stub", rerank_top_k=5, backend=backend)
    r.rerank([("t1", 0.5)], StubState("my custom query"), cat)
    assert backend.score_calls == [[("my custom query", "doc1")]]


def test_rerank_uses_catalog_track_text(monkeypatch):
    """track_text() is called per candidate."""
    accesses = []

    class TracingCatalog:
        def track_text(self, tid):
            accesses.append(tid)
            return f"text-of-{tid}"

    backend = StubBackend(score_map={})
    r = CrossEncoderReranker(model_name="stub", rerank_top_k=5, backend=backend)
    r.rerank([("t1", 0.5), ("t2", 0.4)], StubState("q"), TracingCatalog())
    assert accesses == ["t1", "t2"]


# ---------------- backend selection ----------------


def test_backend_selection_defaults_to_sentence_transformers():
    from mcrs.qu_modules.cross_encoder_reranker import (
        SentenceTransformersBackend,
        build_backend,
    )

    b = build_backend("cross-encoder/ms-marco-MiniLM-L-12-v2")
    assert isinstance(b, SentenceTransformersBackend)
    b = build_backend("BAAI/bge-reranker-base")
    assert isinstance(b, SentenceTransformersBackend)
    b = build_backend("BAAI/bge-reranker-v2-m3")
    assert isinstance(b, SentenceTransformersBackend)


def test_backend_selection_picks_qwen3_for_qwen_models():
    from mcrs.qu_modules.cross_encoder_reranker import (
        Qwen3RerankerBackend,
        build_backend,
    )

    b = build_backend("Qwen/Qwen3-Reranker-0.6B")
    assert isinstance(b, Qwen3RerankerBackend)
    b = build_backend("Qwen/Qwen3-Reranker-4B")
    assert isinstance(b, Qwen3RerankerBackend)


def test_backend_selection_picks_flag_for_gemma():
    from mcrs.qu_modules.cross_encoder_reranker import (
        FlagEmbeddingBackend,
        build_backend,
    )

    b = build_backend("BAAI/bge-reranker-v2-gemma")
    assert isinstance(b, FlagEmbeddingBackend)


def test_backend_selection_explicit_override():
    from mcrs.qu_modules.cross_encoder_reranker import (
        FlagEmbeddingBackend,
        build_backend,
    )

    # Even a MiniLM name routes to Flag if explicitly requested
    b = build_backend("cross-encoder/ms-marco-MiniLM-L-12-v2", backend="flag")
    assert isinstance(b, FlagEmbeddingBackend)
