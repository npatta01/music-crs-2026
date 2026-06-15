from __future__ import annotations

import pytest

from mcrs.crs_baseline import CRS_BASELINE


class FullPipelineQU:
    def batch_compile_track_ids(self, session_memories, topk, user_ids=None, session_meta=None):
        return [["track-1"] for _ in session_memories]


class TransformOnlyQU:
    def transform_query(self, session_memory):
        return "query"


def _patch_lightweight_deps(monkeypatch, qu):
    monkeypatch.setattr("mcrs.crs_baseline.load_lm_module", lambda *args, **kwargs: object())
    monkeypatch.setattr("mcrs.crs_baseline.load_qu_module", lambda *args, **kwargs: qu)
    monkeypatch.setattr("mcrs.crs_baseline.MusicCatalogDB", lambda *args, **kwargs: object())
    monkeypatch.setattr("mcrs.crs_baseline.UserProfileDB", lambda *args, **kwargs: object())


def test_full_pipeline_qu_skips_legacy_retrieval_load(monkeypatch):
    _patch_lightweight_deps(monkeypatch, FullPipelineQU())

    crs = CRS_BASELINE(
        lm_type="dummy",
        retrieval_type="bm25",
        qu_type="state_ranker",
        device="cpu",
    )

    import mcrs.crs_baseline as crs_baseline

    assert not hasattr(crs_baseline, "load_retrieval_module")
    assert crs.retrieval is None


def test_transform_only_qu_is_unsupported_without_legacy_retrieval(monkeypatch):
    _patch_lightweight_deps(monkeypatch, TransformOnlyQU())

    with pytest.raises(ValueError, match="must provide compile_track_ids"):
        CRS_BASELINE(
            lm_type="dummy",
            retrieval_type="bm25",
            qu_type="passthrough",
            device="cpu",
        )
