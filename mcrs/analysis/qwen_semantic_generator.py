"""Qwen-embedded conversation to semantic-ID generation helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import torch


def _normalise_rows(values: np.ndarray) -> np.ndarray:
    arr = np.nan_to_num(np.asarray(values, dtype=np.float32), copy=False)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    np.divide(arr, norms, out=arr, where=norms > 0)
    return arr


def _normalise_vector(value: np.ndarray) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm > 0:
        arr = arr / norm
    return arr.astype(np.float32, copy=False)


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


class CompactNpzEmbeddingCache:
    """Small NPZ-backed cache for deterministic text embeddings.

    Keys are SHA1(text). Vectors are stored as float16 on disk and returned as
    L2-normalized float32. This is intentionally simple: one file per experiment
    view, fast enough for ~100k conversation strings, and easy to inspect.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._keys: list[str] = []
        self._vectors: np.ndarray | None = None
        self._index: dict[str, int] = {}
        self._pending: dict[str, np.ndarray] = {}
        if self.path.exists():
            data = np.load(self.path, allow_pickle=False)
            self._keys = [str(v) for v in data["keys"]]
            self._vectors = _normalise_rows(np.asarray(data["vectors"], dtype=np.float32))
            self._index = {key: idx for idx, key in enumerate(self._keys)}

    @property
    def size(self) -> int:
        return len(self._index) + len(self._pending)

    def _get_key(self, key: str) -> np.ndarray | None:
        if key in self._pending:
            return self._pending[key]
        idx = self._index.get(key)
        if idx is None or self._vectors is None:
            return None
        return self._vectors[int(idx)]

    def get_many(self, texts: Sequence[str], *, embedder=None, offline: bool = False) -> np.ndarray:
        """Return embeddings for `texts`, embedding and caching misses if allowed."""

        ordered = [str(text or "") for text in texts]
        unique = list(dict.fromkeys(text for text in ordered if text))
        missing = [text for text in unique if self._get_key(_sha1(text)) is None]
        if missing:
            if offline:
                raise KeyError(f"{len(missing)} text embeddings missing from {self.path}")
            if embedder is None:
                raise ValueError("embedder is required when the cache has misses")
            encoded = embedder.embed_batch(missing)
            if len(encoded) != len(missing):
                raise ValueError(f"embedder returned {len(encoded)} vectors for {len(missing)} texts")
            for text, vec in zip(missing, encoded):
                self._pending[_sha1(text)] = _normalise_vector(np.asarray(vec, dtype=np.float32))

        dim = self._infer_dim()
        rows = np.zeros((len(ordered), dim), dtype=np.float32)
        for idx, text in enumerate(ordered):
            if not text:
                continue
            vec = self._get_key(_sha1(text))
            if vec is not None:
                rows[idx] = vec
        return rows

    def _infer_dim(self) -> int:
        if self._vectors is not None and self._vectors.size:
            return int(self._vectors.shape[1])
        if self._pending:
            return int(next(iter(self._pending.values())).shape[0])
        raise ValueError("embedding dimension is unknown before any vectors are cached")

    def flush(self) -> None:
        if not self._pending:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._vectors is None or not self._keys:
            keys = list(self._pending)
            vectors = np.vstack([self._pending[key] for key in keys])
        else:
            keys = list(self._keys) + list(self._pending)
            vectors = np.vstack([self._vectors] + [self._pending[key] for key in self._pending])
        np.savez_compressed(
            self.path,
            keys=np.asarray(keys, dtype="U40"),
            vectors=np.asarray(vectors, dtype=np.float16),
        )
        self._keys = keys
        self._vectors = _normalise_rows(np.asarray(vectors, dtype=np.float32))
        self._index = {key: idx for idx, key in enumerate(keys)}
        self._pending.clear()


def build_prior_code_tokens(
    session: Mapping,
    *,
    turn_number: int,
    track_to_codes: Mapping[str, tuple[int, int]],
    n_l1: int,
    n_l2: int,
    max_prior_tracks: int,
) -> list[int]:
    """Encode prior played tracks as semantic-ID code tokens."""

    del n_l2  # l2 tokens are offset by n_l1; caller validates code ranges.
    played_by_turn = session.get("played_by_turn") or {}
    pairs: list[tuple[int, str]] = []
    for raw_turn in sorted(played_by_turn):
        try:
            turn = int(raw_turn)
        except Exception:
            continue
        if turn >= int(turn_number):
            continue
        for track_id in played_by_turn.get(raw_turn) or []:
            pairs.append((turn, str(track_id)))
    if max_prior_tracks > 0:
        pairs = pairs[-max_prior_tracks:]

    tokens: list[int] = []
    for _, track_id in pairs:
        codes = track_to_codes.get(track_id)
        if codes is None:
            continue
        l1, l2 = int(codes[0]), int(codes[1])
        if l1 < 0 or l2 < 0:
            continue
        tokens.extend([l1, int(n_l1) + l2])
    return tokens


class SemanticIdSequenceGenerator(torch.nn.Module):
    """Transformer conditioned on Qwen text embeddings and prior semantic IDs."""

    def __init__(
        self,
        *,
        text_dim: int,
        n_l1: int,
        n_l2: int,
        d_model: int = 256,
        nhead: int = 8,
        num_layers: int = 2,
        max_prior_tokens: int = 32,
        dropout: float = 0.1,
    ):
        super().__init__()
        if d_model % nhead != 0:
            raise ValueError("d_model must be divisible by nhead")
        self.n_l1 = int(n_l1)
        self.n_l2 = int(n_l2)
        self.max_prior_tokens = int(max_prior_tokens)
        self.pad_token = self.n_l1 + self.n_l2
        self.text_proj = torch.nn.Linear(int(text_dim), int(d_model))
        self.code_embedding = torch.nn.Embedding(self.pad_token + 1, int(d_model), padding_idx=self.pad_token)
        self.position_embedding = torch.nn.Embedding(self.max_prior_tokens + 1, int(d_model))
        layer = torch.nn.TransformerEncoderLayer(
            d_model=int(d_model),
            nhead=int(nhead),
            dim_feedforward=int(d_model) * 4,
            dropout=float(dropout),
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = torch.nn.TransformerEncoder(layer, num_layers=int(num_layers))
        self.norm = torch.nn.LayerNorm(int(d_model))
        self.l2_context_norm = torch.nn.LayerNorm(int(d_model))
        self.l1_head = torch.nn.Linear(int(d_model), self.n_l1)
        self.l2_head = torch.nn.Linear(int(d_model), self.n_l2)

    def forward(
        self,
        text_embeddings: torch.Tensor,
        prior_tokens: torch.Tensor,
        l1_tokens: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if prior_tokens.ndim != 2:
            raise ValueError("prior_tokens must have shape [batch, seq]")
        batch_size, prior_len = prior_tokens.shape
        if prior_len > self.max_prior_tokens:
            prior_tokens = prior_tokens[:, -self.max_prior_tokens :]
            prior_len = self.max_prior_tokens

        clean_tokens = prior_tokens.clamp(min=0)
        clean_tokens = torch.where(prior_tokens < 0, torch.full_like(clean_tokens, self.pad_token), clean_tokens)
        clean_tokens = clean_tokens.clamp(max=self.pad_token)

        text_token = self.text_proj(text_embeddings).unsqueeze(1)
        code_tokens = self.code_embedding(clean_tokens)
        seq = torch.cat([text_token, code_tokens], dim=1)
        positions = torch.arange(prior_len + 1, device=seq.device).unsqueeze(0).expand(batch_size, -1)
        seq = seq + self.position_embedding(positions)
        key_padding = torch.cat(
            [
                torch.zeros((batch_size, 1), dtype=torch.bool, device=seq.device),
                clean_tokens == self.pad_token,
            ],
            dim=1,
        )
        encoded = self.encoder(seq, src_key_padding_mask=key_padding)
        pooled = self.norm(encoded[:, 0])
        logits_l1 = self.l1_head(pooled)
        if l1_tokens is None:
            l1_tokens = logits_l1.argmax(dim=1)
        l1_tokens = l1_tokens.to(device=pooled.device, dtype=torch.long).clamp(min=0, max=self.n_l1 - 1)
        conditioned = self.l2_context_norm(pooled + self.code_embedding(l1_tokens))
        return logits_l1, self.l2_head(conditioned)


def code_beams_from_logits(
    logits_l1: np.ndarray,
    logits_l2: np.ndarray,
    *,
    top_l1: int,
    top_l2: int,
) -> list[tuple[tuple[int, int], float]]:
    """Build independent l1/l2 code beams from model logits."""

    l1_order = np.argsort(-logits_l1, kind="mergesort")[:top_l1]
    l2_order = np.argsort(-logits_l2, kind="mergesort")[:top_l2]
    beams = [
        ((int(l1), int(l2)), float(logits_l1[int(l1)] + logits_l2[int(l2)]))
        for l1 in l1_order
        for l2 in l2_order
    ]
    return sorted(beams, key=lambda item: (-item[1], item[0]))


def rank_tracks_from_code_beams(
    beams: Sequence[tuple[tuple[int, int], float]],
    *,
    leaf_tracks: Mapping[tuple[int, int], Sequence[int]],
    item_vectors: np.ndarray,
    prior_vector: np.ndarray,
    max_candidates: int,
    strategy: str = "leaf_block",
    rank_vectors: np.ndarray | None = None,
    query_vector: np.ndarray | None = None,
    query_weight: float = 1.0,
    prior_weight: float = 0.25,
) -> list[int]:
    """Expand predicted semantic-ID leaves to a de-duplicated track ranking."""

    prior = _normalise_vector(prior_vector)
    use_prior = float(np.linalg.norm(prior)) > 0
    ordered_by_leaf: list[list[int]] = []
    for leaf, _score in beams:
        codes = [int(code) for code in leaf_tracks.get((int(leaf[0]), int(leaf[1])), [])]
        code_arr = np.asarray(codes, dtype=np.int32)
        scores = np.zeros(len(code_arr), dtype=np.float32)
        if rank_vectors is not None and query_vector is not None and len(code_arr):
            query = _normalise_vector(query_vector)
            if rank_vectors.shape[1] != query.shape[0]:
                raise ValueError(
                    f"rank vector dim {rank_vectors.shape[1]} does not match query dim {query.shape[0]}"
                )
            scores += float(query_weight) * (np.asarray(rank_vectors[code_arr], dtype=np.float32) @ query)
        if use_prior and len(code_arr):
            scores += float(prior_weight) * (np.asarray(item_vectors[code_arr], dtype=np.float32) @ prior)
        if len(code_arr):
            ordered = [int(code) for code in code_arr[np.argsort(-scores, kind="mergesort")]]
        else:
            ordered = []
        if ordered:
            ordered_by_leaf.append(ordered)

    selected: list[int] = []
    seen: set[int] = set()

    def add_code(code: int) -> bool:
        if code in seen:
            return False
        seen.add(code)
        selected.append(int(code))
        return len(selected) >= max_candidates

    if strategy == "leaf_block":
        for ordered in ordered_by_leaf:
            for code in ordered:
                if add_code(int(code)):
                    return selected
        return selected

    if strategy == "round_robin":
        max_depth = max((len(codes) for codes in ordered_by_leaf), default=0)
        for depth in range(max_depth):
            for ordered in ordered_by_leaf:
                if depth < len(ordered) and add_code(int(ordered[depth])):
                    return selected
        return selected

    raise ValueError(f"unknown expansion strategy: {strategy}")
