import numpy as np

from mcrs.analysis.semantic_hard_negatives import (
    build_turn_example,
    choose_hard_negatives,
    session_split,
)


def test_choose_hard_negatives_returns_unique_non_labels_by_rank():
    labels = np.array([0, 1, 0, 0, 0, 0], dtype=np.int8)
    track_codes = np.array([10, 99, 20, 10, 30, 40], dtype=np.int32)
    ranks = np.array([3, 1, 2, 1, 4, 5], dtype=np.float32)

    negatives = choose_hard_negatives(
        labels=labels,
        track_codes=track_codes,
        base_ranks=ranks,
        max_negatives=3,
    )

    assert negatives.tolist() == [10, 20, 30]


def test_build_turn_example_uses_top_ranked_non_label_context():
    item_vectors = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
            [-1.0, 0.0],
        ],
        dtype=np.float32,
    )
    labels = np.array([0, 1, 0, 0], dtype=np.int8)
    track_codes = np.array([0, 1, 2, 3], dtype=np.int32)
    ranks = np.array([1, 2, 3, 4], dtype=np.float32)

    example = build_turn_example(
        item_vectors=item_vectors,
        labels=labels,
        track_codes=track_codes,
        base_ranks=ranks,
        context_topn=1,
        max_negatives=2,
    )

    assert example is not None
    assert example.positive_code == 1
    assert example.negative_codes.tolist() == [0, 2]
    np.testing.assert_allclose(example.query_vector, np.array([1.0, 0.0], dtype=np.float32))


def test_build_turn_example_skips_turns_without_positive_or_negatives():
    item_vectors = np.eye(3, dtype=np.float32)

    assert build_turn_example(
        item_vectors=item_vectors,
        labels=np.array([0, 0], dtype=np.int8),
        track_codes=np.array([0, 1], dtype=np.int32),
        base_ranks=np.array([1, 2], dtype=np.float32),
        context_topn=2,
        max_negatives=2,
    ) is None

    assert build_turn_example(
        item_vectors=item_vectors,
        labels=np.array([1], dtype=np.int8),
        track_codes=np.array([0], dtype=np.int32),
        base_ranks=np.array([1], dtype=np.float32),
        context_topn=2,
        max_negatives=2,
    ) is None


def test_session_split_is_deterministic_three_way():
    assert session_split("session-a") == session_split("session-a")
    assert {session_split(f"session-{i}") for i in range(100)} == {"train", "tune", "test"}
