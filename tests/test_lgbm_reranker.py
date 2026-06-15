from __future__ import annotations

import numpy as np

from mcrs.qu_modules.lgbm_reranker import _FeatureCatalogFromCompilerCatalog


class _CompilerCatalogSource:
    def __init__(self):
        self._per_track = {
            "t-one": {
                "track_id": "t-one",
                "track_name": "Blue Smoke",
                "artist_name": ["The Example"],
                "artist_id": ["a-example"],
                "album_id": ["al-example"],
                "tag_list": ["smoky jazz", "late night"],
                "popularity": 25.0,
                "release_date": "1999-01-02",
                "duration": 180000,
            },
            "t-two": {
                "track_id": "t-two",
                "track_name": "Hard Pivot",
                "artist_name": ["Other Band"],
                "artist_id": ["a-other"],
                "album_id": ["al-other"],
                "tag_list": ["punk"],
                "popularity": 75.0,
                "release_date": "2005-03-04",
                "duration": 210000,
            },
        }
        self.vector_calls = []

    def vector(self, track_id: str, vector_field: str):
        self.vector_calls.append((track_id, vector_field))
        if track_id == "t-one" and vector_field == "metadata_qwen3_embedding_0_6b":
            return [3.0, 4.0]
        return None


def test_feature_catalog_adapter_reuses_compiler_metadata_and_vectors():
    source = _CompilerCatalogSource()

    catalog = _FeatureCatalogFromCompilerCatalog(source)

    assert set(catalog.meta) == {"t-one", "t-two"}
    assert catalog.meta["t-one"]["artists"] == ("a-example",)
    assert catalog.meta["t-one"]["albums"] == ("al-example",)
    assert catalog.meta["t-one"]["year"] == 1999
    assert catalog.meta["t-one"]["n_tags"] == 2
    assert catalog.artist_track_count["a-example"] == 1
    assert catalog.median_year == 2002
    assert catalog.median_duration == 195000.0

    np.testing.assert_allclose(
        catalog.v("metadata_qwen3_embedding_0_6b", "t-one"),
        np.array([0.6, 0.8], dtype=np.float32),
    )
    np.testing.assert_allclose(
        catalog.v("metadata_qwen3_embedding_0_6b", "t-one"),
        np.array([0.6, 0.8], dtype=np.float32),
    )
    assert source.vector_calls == [("t-one", "metadata_qwen3_embedding_0_6b")]
    assert catalog.v("metadata_qwen3_embedding_0_6b", "missing") is None
