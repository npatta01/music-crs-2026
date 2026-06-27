"""v_struct_pt_query (modal-free, used by the b1 serving path) must stay byte-identical
to modal_build_data (the training renderer). If they drift, serving builds a different
query than the b1 model was trained on -> wrong/empty b1_cos."""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "rerank"))

import v_struct_pt_query as VQ  # noqa: E402
import modal_build_data as MBD  # noqa: E402


def test_short_track_parity():
    for doc in [
        "Music track: Bill Evans — Peace Piece (1959) | jazz, piano",
        "Music track: Boards of Canada — Dayvan Cowboy | electronic",
        "Music track: Sigur Rós — Untitled #1 (Vaka) (2002) | post-rock",  # title has (...)
        "",
    ]:
        assert VQ.short_track(doc) == MBD.short_track(doc), doc


def test_build_q_parity():
    cases = [("hi", "mellow jazz", "Bill Evans — Peace Piece"),
             ("", "something upbeat", ""),
             ("prev turn", "", "Artist — Song"),
             ("", "", "")]
    for variant in ("baseline", "v_struct", "v_struct_pt", "v_tok"):
        for prev, now, pt in cases:
            assert VQ.build_q(variant, prev, now, pt) == MBD.build_q(variant, prev, now, pt), \
                (variant, prev, now, pt)


def test_track_short_title_matches_short_track_of_doc():
    """track_short_title (catalog-derived prev_track text) must equal short_track(doc)
    for the build_doc_corpus head — incl. the edge cases the 47k parity sweep surfaced:
    a ' | ' inside the title (truncated like the tag separator), an empty artist
    (leading space stripped), and a year inside the title (only the release year stripped)."""
    cases = [
        ("Emancipator", "With Rainy Eyes", "2006", "Emancipator — With Rainy Eyes"),
        ("Kendrick Lamar", "untitled 07 | levitate", "2016", "Kendrick Lamar — untitled 07"),
        ("", "Non-Stop", "2015", "— Non-Stop"),
        ("Artist", "Song (1999)", "2020", "Artist — Song (1999)"),
        ("Artist", "Song", "", "Artist — Song"),
    ]
    for ar, nm, yr, expected in cases:
        assert VQ.track_short_title(ar, nm, yr) == expected, (ar, nm, yr)
        # and it equals short_track of the exact head build_doc_corpus writes
        head = f"Music track: {ar} — {nm}" + (f" ({yr})" if yr else "")
        assert VQ.track_short_title(ar, nm, yr) == VQ.short_track(head)


def test_catalog_head_prev_track_matches_full_doc():
    """PR #160 review P2: the SERVING path stores track_doc_head and applies short_track
    once via prev_track_str; the prewarm/training path holds the full doc. They must yield
    the SAME prev_track text — including titles ending in '(YYYY)', which the previous
    (store-the-short-title) code double-stripped."""
    cases = [("Artist", "Song (1999)", "2020"),       # title ends in a year — the P2 repro
             ("Bill Evans", "Peace Piece", "1959"),
             ("X", "untitled 07 | levitate", "2016"),  # pipe in title
             ("", "Non-Stop", "2015")]                 # empty artist
    for ar, nm, yr in cases:
        head = VQ.track_doc_head(ar, nm, yr)                         # serving stores this
        full_doc = head + " | tags: a, b | known for: x"            # prewarm/training holds this
        serving = VQ.prev_track_str({1: ["t"]}, 2, {"t": head})
        prewarm = VQ.prev_track_str({1: ["t"]}, 2, {"t": full_doc})
        assert serving == prewarm, (ar, nm, yr, serving, prewarm)


def test_prev_track_str_parity():
    doc = "Music track: Bill Evans — Peace Piece (1959) | jazz"
    played = {1: ["t1"], 2: ["t2"]}
    doc_by = {"t2": doc}
    assert VQ.prev_track_str(played, 3, doc_by) == MBD.prev_track_str(played, 3, doc_by)
    assert VQ.prev_track_str(played, 3, doc_by, exclude_tid="t2") == \
        MBD.prev_track_str(played, 3, doc_by, exclude_tid="t2")
