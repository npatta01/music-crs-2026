"""Tests for the state-conditioned graded-relevance label builder.

Exercises `grade_candidate` — the per-candidate rule that turns conversation
state + the (offline-known) ground truth into a graded label and a hard-negative
weight. The gating is the whole point: the same-artist push-down must fire ONLY
when the GT is a verified new artist, and a later-accepted track must never be
floored.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RERANK_DIR = ROOT / "scripts" / "rerank"
if str(RERANK_DIR) not in sys.path:
    sys.path.insert(0, str(RERANK_DIR))

from build_label_grades import grade_candidate  # noqa: E402

K = 2
W_NEG = 3.0

# track -> artist name-keys (abandoned / neighbor logic)
ARTIST_KEYS = {
    "gt_old": frozenset({"kendrick"}),       # GT when over-anchoring is correct
    "gt_new": frozenset({"jcole"}),          # GT when user pivoted to a new artist
    "old_same": frozenset({"kendrick"}),     # resembles the abandoned artist
    "newcand": frozenset({"sza"}),
    "fewtag": frozenset({"drake"}),
    "rejart": frozenset({"someband"}),
    "tagmatch": frozenset({"others"}),
    "none": frozenset({"metallica"}),
}
# track -> tag keys
TAG_KEYS = {
    "gt_old": frozenset({"rap", "hiphop", "conscious"}),
    "gt_new": frozenset({"rap", "hiphop", "conscious"}),
    "old_same": frozenset({"rap", "hiphop", "conscious"}),
    "newcand": frozenset({"rap", "hiphop", "conscious"}),
    "fewtag": frozenset({"rap"}),
    "rejart": frozenset({"rap", "hiphop"}),
    "tagmatch": frozenset({"rap", "hiphop"}),
    "none": frozenset({"metal"}),
}
# track -> artist *ids* (explicit-rejection match)
ARTIST_IDS = {
    "rejart": ("A_REJ",),
}


def _grade(tid, info):
    return grade_candidate(tid, info, ARTIST_KEYS, TAG_KEYS, ARTIST_IDS, K, W_NEG)


def _info(**over):
    base = dict(
        gt="gt_old", gt_art=frozenset(), gt_tags=frozenset(),
        pivot_to_new=False, aband=frozenset(), future=set(),
        rej_tracks=frozenset(), rej_artist_ids=frozenset(),
    )
    base.update(over)
    return base


PIVOT_NEW = _info(
    gt="gt_new", gt_art=ARTIST_KEYS["gt_new"], gt_tags=TAG_KEYS["gt_new"],
    pivot_to_new=True, aband=frozenset({"kendrick"}),
    future={"futtrk"},
)
OVERANCHOR_OK = _info(
    gt="gt_old", gt_art=ARTIST_KEYS["gt_old"], gt_tags=TAG_KEYS["gt_old"],
    pivot_to_new=False, aband=frozenset({"kendrick"}),  # GT *is* the abandoned artist
)
CONTINUATION = _info(
    gt="gt_old", gt_art=ARTIST_KEYS["gt_old"], gt_tags=TAG_KEYS["gt_old"],
    rej_tracks=frozenset({"rejtrk"}), rej_artist_ids=frozenset({"A_REJ"}),
)


def test_ground_truth_is_top_grade():
    assert _grade("gt_new", PIVOT_NEW) == (3, 1.0)


def test_future_accepted_is_grade_2_and_beats_hard_negative_floor():
    # futtrk would be floored as same-artist-as-abandoned, but future wins.
    assert "futtrk" not in ARTIST_KEYS  # absent -> only the future rule can grade it
    assert _grade("futtrk", PIVOT_NEW) == (2, 1.0)


def test_pivot_to_new_floors_same_artist_as_abandoned():
    # old_same shares all of GT's tags, yet the over-anchor floor beats the neighbor rule.
    assert _grade("old_same", PIVOT_NEW) == (0, W_NEG)


def test_pivot_to_new_credits_new_direction_neighbor():
    assert _grade("newcand", PIVOT_NEW) == (1, 1.0)  # >=K shared tags, not abandoned


def test_pivot_to_new_no_credit_below_tag_threshold():
    assert _grade("fewtag", PIVOT_NEW) == (0, 1.0)  # only 1 shared tag < K


def test_overanchor_correct_does_not_floor_old_artist():
    # GT *is* the abandoned artist -> pivot_to_new is False -> same-artist gets grade 1.
    assert _grade("old_same", OVERANCHOR_OK) == (1, 1.0)


def test_continuation_credits_same_artist_as_gt():
    assert _grade("old_same", CONTINUATION) == (1, 1.0)  # shares artist with GT


def test_continuation_credits_tag_overlap():
    assert _grade("tagmatch", CONTINUATION) == (1, 1.0)  # 2 shared tags >= K


def test_continuation_no_match_is_zero():
    assert _grade("none", CONTINUATION) == (0, 1.0)


def test_explicit_track_rejection_is_hard_negative():
    assert "rejtrk" not in TAG_KEYS  # absent from catalog maps
    assert _grade("rejtrk", CONTINUATION) == (0, W_NEG)


def test_explicit_artist_rejection_floors_even_a_neighbor():
    # rejart shares 2 tags with GT (would be grade 1) but its artist id is rejected.
    assert _grade("rejart", CONTINUATION) == (0, W_NEG)
