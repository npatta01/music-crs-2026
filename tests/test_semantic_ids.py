import numpy as np

from mcrs.analysis.semantic_ids import (
    build_hierarchical_semantic_ids,
    common_prefix_depth,
    rrf_score,
    semantic_branch_ranks,
)


def test_build_hierarchical_semantic_ids_separates_simple_clusters():
    track_ids = ["a0", "a1", "b0", "b1", "c0", "c1"]
    vectors = np.array(
        [
            [1.00, 0.00],
            [0.95, 0.05],
            [0.00, 1.00],
            [0.05, 0.95],
            [-1.00, 0.00],
            [-0.95, -0.05],
        ],
        dtype=np.float32,
    )

    ids = build_hierarchical_semantic_ids(
        track_ids,
        vectors,
        level_sizes=(3, 2),
        iterations=20,
        seed=7,
    )

    assert set(ids) == set(track_ids)
    assert all(len(code) == 2 for code in ids.values())
    assert ids["a0"][0] == ids["a1"][0]
    assert ids["b0"][0] == ids["b1"][0]
    assert ids["c0"][0] == ids["c1"][0]
    assert len({ids["a0"][0], ids["b0"][0], ids["c0"][0]}) == 3


def test_common_prefix_depth_counts_matching_levels():
    assert common_prefix_depth((1, 4, 2), (1, 4, 9)) == 2
    assert common_prefix_depth((1, 4), (2, 4)) == 0
    assert common_prefix_depth((), (2, 4)) == 0


def test_semantic_branch_ranks_orders_candidates_by_seed_cluster_then_base_rank():
    base_order = ["a", "b", "c", "d", "e"]
    semantic_ids = {
        "a": (1, 1),
        "b": (2, 1),
        "c": (1, 2),
        "d": (3, 1),
        "e": (2, 2),
    }

    ranks = semantic_branch_ranks(
        base_order,
        semantic_ids,
        seed_topn=2,
        level=1,
    )

    assert ranks == {
        "a": 1,
        "c": 2,
        "b": 3,
        "e": 4,
    }


def test_rrf_score_ignores_missing_branch_rank():
    assert rrf_score(base_rank=10, semantic_rank=None, semantic_weight=3.0) == 1 / 70
    assert rrf_score(base_rank=10, semantic_rank=5, semantic_weight=3.0) == (
        1 / 70 + 3 / 65
    )
