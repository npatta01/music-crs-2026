import numpy as np
import torch

from mcrs.analysis.qwen_semantic_generator import (
    CompactNpzEmbeddingCache,
    SemanticIdSequenceGenerator,
    build_prior_code_tokens,
    rank_tracks_from_code_beams,
)


class ToyEmbedder:
    def __init__(self):
        self.calls = []

    def embed_batch(self, texts):
        self.calls.append(list(texts))
        return [[float(len(t)), 1.0] for t in texts]


def test_compact_npz_embedding_cache_deduplicates_and_reuses_vectors(tmp_path):
    cache = CompactNpzEmbeddingCache(tmp_path / "qwen_cache.npz")
    embedder = ToyEmbedder()

    first = cache.get_many(["bright pop", "bright pop", "dark jazz"], embedder=embedder)
    cache.flush()
    second = CompactNpzEmbeddingCache(tmp_path / "qwen_cache.npz").get_many(
        ["dark jazz", "bright pop"],
        embedder=ToyEmbedder(),
        offline=True,
    )

    assert embedder.calls == [["bright pop", "dark jazz"]]
    assert first.shape == (3, 2)
    np.testing.assert_allclose(first[0], first[1])
    np.testing.assert_allclose(second[0], first[2], rtol=1e-3)
    np.testing.assert_allclose(second[1], first[0], rtol=1e-3)


def test_build_prior_code_tokens_uses_only_tracks_before_turn():
    session = {"played_by_turn": {1: ["a"], 2: ["missing"], 3: ["b"]}}
    track_to_codes = {"a": (2, 5), "b": (7, 1)}

    tokens = build_prior_code_tokens(
        session,
        turn_number=3,
        track_to_codes=track_to_codes,
        n_l1=8,
        n_l2=10,
        max_prior_tracks=4,
    )

    assert tokens == [2, 8 + 5]


def test_sequence_generator_outputs_l1_and_l2_logits():
    model = SemanticIdSequenceGenerator(
        text_dim=3,
        n_l1=4,
        n_l2=5,
        d_model=8,
        nhead=2,
        num_layers=1,
        max_prior_tokens=4,
    )

    logits_l1, logits_l2 = model(
        text_embeddings=torch.ones(2, 3),
        prior_tokens=torch.tensor([[0, 4, -1], [2, -1, -1]], dtype=torch.long),
        l1_tokens=torch.tensor([1, 3], dtype=torch.long),
    )

    assert logits_l1.shape == (2, 4)
    assert logits_l2.shape == (2, 5)


def test_sequence_generator_conditions_l2_on_l1_token():
    torch.manual_seed(3)
    model = SemanticIdSequenceGenerator(
        text_dim=3,
        n_l1=4,
        n_l2=5,
        d_model=8,
        nhead=2,
        num_layers=1,
        max_prior_tokens=4,
        dropout=0.0,
    )
    text = torch.ones(1, 3)
    prior = torch.tensor([[0, -1]], dtype=torch.long)

    _l1_a, l2_a = model(text, prior, l1_tokens=torch.tensor([0]))
    _l1_b, l2_b = model(text, prior, l1_tokens=torch.tensor([3]))

    assert not torch.allclose(l2_a, l2_b)


def test_rank_tracks_from_code_beams_expands_valid_leaves_and_prior_similarity():
    leaf_tracks = {
        (1, 1): [0, 1],
        (2, 0): [2],
    }
    item_vectors = np.array(
        [[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]],
        dtype=np.float32,
    )
    beams = [((1, 1), 3.0), ((2, 0), 2.0)]

    ranked = rank_tracks_from_code_beams(
        beams,
        leaf_tracks=leaf_tracks,
        item_vectors=item_vectors,
        prior_vector=np.array([0.0, 1.0], dtype=np.float32),
        max_candidates=3,
    )

    assert ranked == [1, 0, 2]


def test_rank_tracks_from_code_beams_round_robin_interleaves_leaves():
    leaf_tracks = {
        (1, 1): [0, 1, 2],
        (2, 0): [3],
    }
    item_vectors = np.eye(4, 2, dtype=np.float32)
    beams = [((1, 1), 3.0), ((2, 0), 2.0)]

    ranked = rank_tracks_from_code_beams(
        beams,
        leaf_tracks=leaf_tracks,
        item_vectors=item_vectors,
        prior_vector=np.zeros(2, dtype=np.float32),
        max_candidates=4,
        strategy="round_robin",
    )

    assert ranked == [0, 3, 1, 2]


def test_rank_tracks_from_code_beams_uses_query_vector_for_within_leaf_order():
    leaf_tracks = {(1, 1): [0, 1]}
    item_vectors = np.zeros((2, 2), dtype=np.float32)
    rank_vectors = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)

    ranked = rank_tracks_from_code_beams(
        [((1, 1), 1.0)],
        leaf_tracks=leaf_tracks,
        item_vectors=item_vectors,
        prior_vector=np.zeros(2, dtype=np.float32),
        max_candidates=2,
        rank_vectors=rank_vectors,
        query_vector=np.array([1.0, 0.0], dtype=np.float32),
    )

    assert ranked == [1, 0]
