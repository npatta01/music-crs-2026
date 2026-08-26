"""Unit tests for the supply-gated pivot reorder (fix #1 / block-P concept).

The reorder demotes blocked-artist tracks (artists the user is pivoting away
from) below non-blocked ones within a top window — but ONLY when enough
non-blocked alternatives exist. It never *removes* a track, so recall@window is
preserved even when the referenced artist is the only valid supply.
"""

import types

from mcrs.qu_modules.lgbm_reranker import (
    LgbmOnlineReranker,
    supply_gated_pivot_reorder,
)


def _bare_reranker(meta, *, enabled=True, min_alt=2, window=20):
    """A reranker instance without __init__ (no model/catalog load).

    `meta` maps tid -> artists tuple, or tid -> dict({artists, artist_name_keys}).
    """
    rr = LgbmOnlineReranker.__new__(LgbmOnlineReranker)
    rr.pivot_demote_enabled = enabled
    rr.pivot_demote_min_alternatives = min_alt
    rr.pivot_demote_window = window
    norm = {}
    for tid, v in meta.items():
        norm[tid] = v if isinstance(v, dict) else {"artists": v}
    cat = types.SimpleNamespace(meta=norm)
    rr.ctx = types.SimpleNamespace(cat=cat)
    return rr


def test_blocks_rejected_artist_by_name_key_not_just_id():
    # The rejected artist "Deltron 3030" has no id in rejected_artist_ids (resolver
    # mapped only some names). An id-only block would promote it; the name-key
    # block must keep it demoted.
    from mcrs.qu_modules.tag_resolver import catalog_tag_key
    rr = _bare_reranker({
        "t_del": {"artists": ("id_del",),
                  "artist_name_keys": (catalog_tag_key("Deltron 3030"),)},
        "t_new": {"artists": ("id_new",),
                  "artist_name_keys": (catalog_tag_key("Someone Else"),)},
    }, min_alt=1)
    trace = {
        "intent_mode": "pivot",
        "compiled_state": {
            "explicit_rejections": [{"kind": "artist", "value": "Deltron 3030"}],
        },
    }
    res = {"rejected_artist_ids": [], "played_track_ids": []}
    out = rr._maybe_pivot_reorder(["t_del", "t_new"], trace, res)
    assert out == ["t_new", "t_del"]


def test_reorder_fires_on_pivot_intent_with_played_blocked():
    rr = _bare_reranker({"t1": ("A",), "t2": ("A",), "t3": ("B",), "t4": ("C",)})
    trace = {"intent_mode": "pivot", "compiled_state": {}}
    res = {"rejected_artist_ids": [], "played_track_ids": ["tp"]}
    rr.ctx.cat.meta["tp"] = {"artists": ("A",)}  # played track -> artist A blocked
    out = rr._maybe_pivot_reorder(["t1", "t2", "t3", "t4"], trace, res)
    assert out == ["t3", "t4", "t1", "t2"]


def test_reorder_uses_rejected_artist_ids_and_target_mode():
    rr = _bare_reranker({"t1": ("A",), "t2": ("B",), "t3": ("C",)})
    trace = {"intent_mode": "refinement",
             "compiled_state": {"target_artist_mode": "new_artist"}}
    res = {"rejected_artist_ids": ["A"], "played_track_ids": []}
    out = rr._maybe_pivot_reorder(["t1", "t2", "t3"], trace, res)
    assert out == ["t2", "t3", "t1"]


def test_noop_when_not_pivot_turn():
    rr = _bare_reranker({"t1": ("A",), "t2": ("B",)})
    trace = {"intent_mode": "refinement", "compiled_state": {}}
    res = {"rejected_artist_ids": ["A"], "played_track_ids": []}
    out = rr._maybe_pivot_reorder(["t1", "t2"], trace, res)
    assert out == ["t1", "t2"]


def test_noop_when_disabled():
    rr = _bare_reranker({"t1": ("A",), "t2": ("B",)}, enabled=False)
    trace = {"intent_mode": "pivot", "compiled_state": {}}
    res = {"rejected_artist_ids": ["A"], "played_track_ids": []}
    out = rr._maybe_pivot_reorder(["t1", "t2"], trace, res)
    assert out == ["t1", "t2"]


def _artist_of(mapping):
    return lambda tid: mapping.get(tid, ())


def test_promotes_non_blocked_above_blocked_when_supply_exists():
    # t1,t2 blocked (artist A = pivoted-away); t3,t4 non-blocked.
    ranked = ["t1", "t2", "t3", "t4"]
    art = _artist_of({"t1": ("A",), "t2": ("A",), "t3": ("B",), "t4": ("C",)})
    out = supply_gated_pivot_reorder(
        ranked, artist_of=art, blocked_artists={"A"},
        min_alternatives=2, window=4,
    )
    # non-blocked first (stable), blocked after — nothing dropped.
    assert out == ["t3", "t4", "t1", "t2"]
    assert sorted(out) == sorted(ranked)


def test_noop_when_insufficient_alternatives():
    # Only one non-blocked candidate, min_alternatives=2 -> leave as-is so we do
    # not demote based on a thin/fluke alternative (over-anchoring often correct).
    ranked = ["t1", "t2", "t3"]
    art = _artist_of({"t1": ("A",), "t2": ("A",), "t3": ("B",)})
    out = supply_gated_pivot_reorder(
        ranked, artist_of=art, blocked_artists={"A"},
        min_alternatives=2, window=3,
    )
    assert out == ["t1", "t2", "t3"]


def test_noop_when_no_alternatives_referenced_artist_is_only_supply():
    # All candidates are the pivoted-away artist -> keep (recall ceiling, the
    # referenced artist may genuinely be the only fit). No removal.
    ranked = ["t1", "t2"]
    art = _artist_of({"t1": ("A",), "t2": ("A",)})
    out = supply_gated_pivot_reorder(
        ranked, artist_of=art, blocked_artists={"A"},
        min_alternatives=1, window=2,
    )
    assert out == ["t1", "t2"]


def test_window_bounds_the_reorder_tail_untouched():
    ranked = ["t1", "t2", "t3", "t4", "t5"]
    art = _artist_of({"t1": ("A",), "t2": ("B",), "t3": ("A",), "t4": ("A",), "t5": ("B",)})
    out = supply_gated_pivot_reorder(
        ranked, artist_of=art, blocked_artists={"A"},
        min_alternatives=1, window=3,
    )
    # within first 3: non-blocked t2 promoted above blocked t1,t3; tail t4,t5 kept.
    assert out == ["t2", "t1", "t3", "t4", "t5"]


def test_collab_with_blocked_artist_counts_as_blocked():
    # A track whose artist set includes the blocked artist is still blocked
    # (a collab featuring the pivoted-away artist is not a "new" artist).
    ranked = ["t1", "t2"]
    art = _artist_of({"t1": ("A", "B"), "t2": ("C",)})
    out = supply_gated_pivot_reorder(
        ranked, artist_of=art, blocked_artists={"A"},
        min_alternatives=1, window=2,
    )
    assert out == ["t2", "t1"]


def test_empty_blocked_set_is_noop():
    ranked = ["t1", "t2", "t3"]
    art = _artist_of({"t1": ("A",), "t2": ("B",), "t3": ("C",)})
    out = supply_gated_pivot_reorder(
        ranked, artist_of=art, blocked_artists=set(),
        min_alternatives=1, window=3,
    )
    assert out == ranked


def test_no_recall_loss_blocked_track_stays_in_window():
    # Many non-blocked but blocked track must remain within window (not pushed
    # past it) when window covers the whole serve depth.
    ranked = ["b", "n1", "n2", "n3"]
    art = _artist_of({"b": ("A",), "n1": ("B",), "n2": ("C",), "n3": ("D",)})
    out = supply_gated_pivot_reorder(
        ranked, artist_of=art, blocked_artists={"A"},
        min_alternatives=2, window=4,
    )
    assert out == ["n1", "n2", "n3", "b"]
    assert "b" in out  # never removed
