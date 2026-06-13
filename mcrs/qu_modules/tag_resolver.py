"""Tiered phrase -> catalog-tag resolver.

Maps free-form attribute phrases from the V1 state extractor ("intense
emotional alternative rock") to catalog tags with a score per match, so
downstream consumers know both WHAT matched and HOW confidently:

    tier "exact"      score 1.0     phrase normalizes to a catalog tag
    tier "alias"      score 0.9     curated alias table hit
    tier "substring"  score 0.8     catalog tag appears whole inside the phrase
    tier "embedding"  score=cosine  semantic neighbor above a threshold

A phrase with no match above ``min_resolved_score`` is reported unresolved so
callers can fall back to raw text search instead of dropping the signal (the
failure mode of the ``catalog_exact`` BM25 policy).

The resolver is deliberately import-light: no compiler import (the compiler
imports us), numpy required only when an embedding index is attached.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

TIER_EXACT = "exact"
TIER_ALIAS = "alias"
TIER_SUBSTRING = "substring"
TIER_EMBEDDING = "embedding"

_TIER_RANK = {TIER_EXACT: 0, TIER_ALIAS: 1, TIER_SUBSTRING: 2, TIER_EMBEDDING: 3}


def catalog_tag_key(value: str) -> str:
    """Normalize a tag/phrase the same way the v0+ compiler does. Must stay
    in lockstep with ``V0PlusCompiler._catalog_tag_key`` (asserted in tests)."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9&]+", " ", value.casefold())).strip()


@dataclass(frozen=True)
class TagMatch:
    tag: str
    score: float
    tier: str


@dataclass(frozen=True)
class TagResolution:
    phrase: str
    matches: tuple[TagMatch, ...]
    resolved: bool

    def tags(self) -> list[str]:
        return [m.tag for m in self.matches]


class TagEmbeddingIndex:
    """Brute-force cosine lookup over L2-normalized tag embeddings.

    Storage format (``.npz``): ``tags`` (unicode array of normalized tag keys)
    and ``vectors`` (float32 matrix, rows L2-normalized). A ``meta.json``
    sidecar records the encoder + filter settings used to build it.
    """

    def __init__(self, tags: Sequence[str], vectors) -> None:
        import numpy as np

        if len(tags) != len(vectors):
            raise ValueError(
                f"tags ({len(tags)}) and vectors ({len(vectors)}) length mismatch"
            )
        self.tags = list(tags)
        matrix = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        self.matrix = matrix / norms

    @classmethod
    def load(cls, path: str | Path) -> "TagEmbeddingIndex":
        import numpy as np

        data = np.load(str(path), allow_pickle=False)
        return cls(tags=[str(t) for t in data["tags"]], vectors=data["vectors"])

    def save(self, path: str | Path) -> None:
        import numpy as np

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            str(path),
            tags=np.asarray(self.tags),
            vectors=self.matrix,
        )

    def topk(self, vector: Sequence[float], k: int) -> list[tuple[str, float]]:
        import numpy as np

        query = np.asarray(vector, dtype=np.float32)
        norm = float(np.linalg.norm(query))
        if norm == 0.0:
            return []
        query = query / norm
        scores = self.matrix @ query
        if k >= len(scores):
            order = np.argsort(-scores)
        else:
            top = np.argpartition(-scores, k)[:k]
            order = top[np.argsort(-scores[top])]
        return [(self.tags[i], float(scores[i])) for i in order[:k]]


@dataclass
class TieredTagResolver:
    """Resolve attribute phrases to scored catalog-tag matches.

    ``catalog_tag_keys`` is the normalized tag vocabulary (substring + exact
    tiers scan it). ``substring_vocab`` optionally restricts the substring
    scan to a cleaner subset (e.g. frequency-filtered) — defaults to the full
    vocabulary. ``embed_fn`` maps a list of phrases to embedding vectors; it
    is only called for phrases the lexical tiers could not resolve.
    """

    catalog_tag_keys: frozenset[str]
    aliases: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    substring_vocab: frozenset[str] | None = None
    embedding_index: TagEmbeddingIndex | None = None
    embed_fn: Callable[[list[str]], list[list[float]]] | None = None
    embedding_min_score: float = 0.60
    embedding_topk: int = 3
    max_matches: int = 5
    min_resolved_score: float = 0.60
    min_substring_tag_len: int = 3
    normalize_fn: Callable[[str], str] = catalog_tag_key

    def __post_init__(self) -> None:
        self._cache: dict[str, TagResolution] = {}
        if self.substring_vocab is None:
            self.substring_vocab = self.catalog_tag_keys

    def resolve(self, phrase: str) -> TagResolution:
        key = self.normalize_fn(phrase)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        resolution = self._resolve_uncached(phrase, key)
        self._cache[key] = resolution
        return resolution

    def _resolve_uncached(self, phrase: str, key: str) -> TagResolution:
        matches: dict[str, TagMatch] = {}

        def add(tag: str, score: float, tier: str) -> None:
            existing = matches.get(tag)
            if existing is None or score > existing.score:
                matches[tag] = TagMatch(tag=tag, score=score, tier=tier)

        if key and key in self.catalog_tag_keys:
            add(key, 1.0, TIER_EXACT)

        for alias in self.aliases.get(key, ()):
            alias_key = self.normalize_fn(alias)
            if alias_key in self.catalog_tag_keys:
                add(alias_key, 0.9, TIER_ALIAS)

        if key:
            padded = f" {key} "
            for tag in self.substring_vocab:
                if (
                    len(tag) >= self.min_substring_tag_len
                    and tag != key
                    and f" {tag} " in padded
                ):
                    add(tag, 0.8, TIER_SUBSTRING)

        # Embedding tier only fires when lexical tiers found nothing confident
        # enough — it is the recall extender for non-literal phrases, not a
        # rescorer of phrases lexical tiers already grounded.
        lexically_resolved = any(
            m.score >= self.min_resolved_score for m in matches.values()
        )
        if (
            not lexically_resolved
            and key
            and self.embedding_index is not None
            and self.embed_fn is not None
        ):
            vectors = self.embed_fn([key])
            if vectors:
                for tag, score in self.embedding_index.topk(
                    vectors[0], self.embedding_topk
                ):
                    if score >= self.embedding_min_score:
                        add(tag, score, TIER_EMBEDDING)

        ordered = sorted(
            matches.values(),
            key=lambda m: (_TIER_RANK[m.tier], -m.score, -len(m.tag), m.tag),
        )[: self.max_matches]
        resolved = any(m.score >= self.min_resolved_score for m in ordered)
        return TagResolution(phrase=phrase, matches=tuple(ordered), resolved=resolved)


def load_embedding_index_meta(npz_path: str | Path) -> dict:
    meta_path = Path(npz_path).with_suffix(".meta.json")
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def filtered_tag_vocab(
    tag_document_frequency: Mapping[str, int],
    min_track_count: int = 5,
) -> frozenset[str]:
    """Frequency-filter the tag vocabulary; drops singleton/junk tags (60.7%
    of the raw 163k vocab are singletons)."""
    return frozenset(
        tag
        for tag, count in tag_document_frequency.items()
        if count >= min_track_count
    )
