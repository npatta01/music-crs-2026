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


def test_prev_track_str_parity():
    doc = "Music track: Bill Evans — Peace Piece (1959) | jazz"
    played = {1: ["t1"], 2: ["t2"]}
    doc_by = {"t2": doc}
    assert VQ.prev_track_str(played, 3, doc_by) == MBD.prev_track_str(played, 3, doc_by)
    assert VQ.prev_track_str(played, 3, doc_by, exclude_tid="t2") == \
        MBD.prev_track_str(played, 3, doc_by, exclude_tid="t2")
