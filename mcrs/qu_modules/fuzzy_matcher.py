"""Fuzzy-matching abstraction for entity resolution.

The Resolver doesn't do rapidfuzz directly anymore — it talks to a
`FuzzyMatcher`. This lets us swap in different matchers (rapidfuzz over a
DictCatalog for tests, rapidfuzz over an HF dataset for production, a future
FST-based matcher for high throughput) without touching Resolver code.

Two impls in this file:

- `FuzzyMatcher` Protocol — the interface.
- `RapidfuzzCatalogMatcher` — a `Catalog`-backed impl. **Pre-bakes** the
  lowercased name → id maps on init so every `match()` call hits in-memory
  data, not the catalog.

For tests, see `tests/v0plus_fakes.py` — the `DictCatalog` is small enough
that wrapping it in `RapidfuzzCatalogMatcher` IS the test fake.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from rapidfuzz import fuzz, process

from mcrs.qu_modules.v0plus_catalog import CompilerCatalog


VALID_ENTITY_TYPES = frozenset({"artist", "track", "album"})


@runtime_checkable
class FuzzyMatcher(Protocol):
    """Match a surface form against a pre-baked catalog of entity names."""

    @property
    def supported_entity_types(self) -> frozenset[str]:
        """Which `entity_type` values the matcher knows about."""
        ...

    def match(
        self,
        query: str,
        entity_type: str,
        *,
        topk: int = 20,
        score_cutoff: int = 80,
    ) -> list[tuple[str, float]]:
        """Return ranked `(entity_id, score)` pairs for the surface form.

        Args:
            query: surface form (case- and punctuation-insensitive).
            entity_type: must be in `supported_entity_types`.
            topk: max matches to return.
            score_cutoff: minimum match score (0-100) to include.

        Returns:
            `[(entity_id, score), ...]` sorted by score desc. Empty if
            `query` is blank or no match clears `score_cutoff`. Raises
            `ValueError` if `entity_type` is unknown.
        """
        ...


class RapidfuzzCatalogMatcher:
    """Catalog-backed FuzzyMatcher using rapidfuzz `token_set_ratio` with
    case-folding. Pre-bakes the catalog's name lists on init so every match
    call is in-memory.

    For ~9k artists / 47k tracks (TalkPlayData), this is small enough to keep
    in RAM. If the catalog grows order-of-magnitude, swap in a FST/Aho-Corasick
    backed impl behind the same Protocol.
    """

    def __init__(self, catalog: CompilerCatalog) -> None:
        # Pre-bake: per entity type, (original_name, entity_id) tuples.
        # `process.extract` with `processor=str.lower` lowercases both query
        # and choice at match time, so we keep the originals here for return.
        self._choices: dict[str, list[str]] = {
            "artist": list(catalog.artist_names),
            "track": list(catalog.track_names),
        }
        self._id_of_name: dict[str, dict[str, str]] = {
            "artist": {
                name: aid
                for name in catalog.artist_names
                if (aid := catalog.artist_id_of_name(name)) is not None
            },
            "track": {
                name: tid
                for name in catalog.track_names
                if (tid := catalog.track_id_of_name(name)) is not None
            },
        }
        # Album support is on the Protocol but not on the catalog yet. Skip.

    @property
    def supported_entity_types(self) -> frozenset[str]:
        return frozenset(self._choices.keys())

    def match(
        self,
        query: str,
        entity_type: str,
        *,
        topk: int = 20,
        score_cutoff: int = 80,
    ) -> list[tuple[str, float]]:
        if entity_type not in self._choices:
            raise ValueError(
                f"Unsupported entity_type {entity_type!r}. "
                f"Supported: {sorted(self.supported_entity_types)}"
            )
        if not query or not query.strip():
            return []

        # rapidfuzz returns (name, score, index). We map name → entity_id.
        raw = process.extract(
            query,
            self._choices[entity_type],
            scorer=fuzz.token_set_ratio,
            limit=topk,
            score_cutoff=score_cutoff,
            processor=str.lower,
        )
        id_map = self._id_of_name[entity_type]
        out: list[tuple[str, float]] = []
        for name, score, _ in raw:
            eid = id_map.get(name)
            if eid is not None:
                out.append((eid, float(score)))
        return out
