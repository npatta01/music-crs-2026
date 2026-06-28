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

    def match_track_by_artist(
        self,
        query: str,
        *,
        artist_ids: set[str],
        artist_names: set[str],
        topk: int = 20,
        score_cutoff: int = 80,
    ) -> list[tuple[str, float]]:
        """Return track matches whose catalog artist credit matches a constraint."""
        ...


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if item is not None]
    return [value]


def _surface_key(value: object) -> str:
    return str(value or "").casefold().strip()


class RapidfuzzCatalogMatcher:
    """Catalog-backed FuzzyMatcher using rapidfuzz scorers with case-folding.

    Artist names use `token_set_ratio` because artist credits often include
    extra collaborators or punctuation. Track names use `WRatio` so full-title
    exact matches outrank short subset ties such as "Bad" inside a long title.
    Pre-bakes the catalog's name lists on init so every match call is in-memory.

    For ~9k artists / 47k tracks (TalkPlayData), this is small enough to keep
    in RAM. If the catalog grows order-of-magnitude, swap in a FST/Aho-Corasick
    backed impl behind the same Protocol.
    """

    def __init__(self, catalog: CompilerCatalog) -> None:
        self._catalog = catalog
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

        scorer = fuzz.WRatio if entity_type == "track" else fuzz.token_set_ratio

        # rapidfuzz returns (name, score, index). We map name → entity_id.
        raw = process.extract(
            query,
            self._choices[entity_type],
            scorer=scorer,
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

    def match_track_by_artist(
        self,
        query: str,
        *,
        artist_ids: set[str],
        artist_names: set[str],
        topk: int = 20,
        score_cutoff: int = 80,
    ) -> list[tuple[str, float]]:
        if not query or not query.strip():
            return []
        if not artist_ids and not artist_names:
            return self.match(query, "track", topk=topk, score_cutoff=score_cutoff)
        feature_rows = getattr(self._catalog, "feature_rows", None)
        if not callable(feature_rows):
            return []
        artist_name_keys = {
            _surface_key(name) for name in artist_names if str(name or "").strip()
        }
        matches: list[tuple[float, int, str]] = []
        for track_id, row in feature_rows().items():
            if not isinstance(row, dict):
                continue
            row_artist_ids = {str(value) for value in _as_list(row.get("artist_id"))}
            artist_id_of = getattr(self._catalog, "artist_id_of", None)
            if callable(artist_id_of):
                if artist_id := artist_id_of(str(track_id)):
                    row_artist_ids.add(str(artist_id))
            row_artist_names = {
                _surface_key(value) for value in _as_list(row.get("artist_name"))
            }
            if artist_ids and row_artist_ids & artist_ids:
                artist_match = True
            else:
                artist_match = bool(artist_name_keys and row_artist_names & artist_name_keys)
            if not artist_match:
                continue
            for track_name in _as_list(row.get("track_name")):
                text = str(track_name or "").strip()
                if not text:
                    continue
                score = float(fuzz.WRatio(query, text, processor=str.lower))
                if score < score_cutoff:
                    continue
                matches.append((score, len(text), str(track_id)))
        out: list[tuple[str, float]] = []
        seen: set[str] = set()
        for score, _, track_id in sorted(matches, reverse=True):
            if track_id in seen:
                continue
            seen.add(track_id)
            out.append((track_id, score))
            if len(out) >= topk:
                break
        return out
