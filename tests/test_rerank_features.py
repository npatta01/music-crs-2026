"""Unit tests for scripts/rerank/features_v9 pivot/abandoned-set behaviour."""

from __future__ import annotations

import sys
from pathlib import Path

# features_v9 does `from build_features import ...` (sibling) — put the rerank
# scripts dir on the path so the module chain imports.
_RERANK = Path(__file__).resolve().parents[1] / "scripts" / "rerank"
if str(_RERANK) not in sys.path:
    sys.path.insert(0, str(_RERANK))

from features_v9 import _abandoned_sets  # noqa: E402


class _StubCat:
    """Minimal Catalog stand-in: _abandoned_sets only touches `.meta` for the
    negatively-rated track-feedback path, which these tests don't exercise."""

    meta: dict = {}


def test_abandoned_sets_includes_satisfied_prior_artists():
    """Over-anchor fix: on a pivot, a satisfied_prior artist (kept as a style
    reference, e.g. 'other bands, not Nirvana') must enter the abandoned-artist
    set so the reranker's same_artist_as_abandoned / x_same_artist_wants_new
    features can demote it. catalog_tag_key('Nirvana') == 'nirvana'."""
    state = {
        "facts": [
            {"type": "artist", "value": "Nirvana",
             "role": "satisfied_prior", "anchor_use": "do_not_use"},
        ],
        "track_feedback": [],
    }
    artists, _tags = _abandoned_sets(state, {}, _StubCat())
    assert "nirvana" in artists


def test_abandoned_sets_ignores_current_target_artists():
    """A current_target artist (refinement: 'more like Nirvana') must NOT be
    abandoned — only satisfied_prior pivots demote the artist."""
    state = {
        "facts": [
            {"type": "artist", "value": "Nirvana",
             "role": "current_target", "anchor_use": "must_use"},
        ],
        "track_feedback": [],
    }
    artists, _tags = _abandoned_sets(state, {}, _StubCat())
    assert "nirvana" not in artists
