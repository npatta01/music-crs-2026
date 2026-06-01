"""v0+ ConversationState Resolver.

Takes the LLM extractor's `ConversationStateV0Plus` (surface forms only) and
returns a `ResolvedConversationState` with deterministic id annotations the
Compiler needs:

1. **Rejection resolution** — `explicit_rejections.kind == "artist" | "track"`
   surface forms resolved to catalog ids via the `FuzzyMatcher`; artist
   rejections resolve to artist ids, while track rejections resolve to both
   track ids and their owning artist ids. The Compiler hard-drops these.
2. **Same-artist annotation** — for each `track_feedback[i].track_id`, the
   artist_id so the Compiler can apply the same-artist demote on rejected
   feedback.
3. **Mechanical fields** — `played_track_ids` rides along here too because
   it's not part of the LLM-extracted schema but the Compiler needs it.

Positive `mentioned_entities` are **not** resolved (they flow directly into
the Compiler's BM25 channels and dense query string).

The Resolver owns no rapidfuzz code — it talks to a `FuzzyMatcher` Protocol,
so the matching backend (in-memory rapidfuzz today, FST or SaaS tomorrow)
can be swapped without touching the Resolver.

See: experiments/analysis/conversation_state_compiler_v0plus/README.md
"""

from __future__ import annotations

from dataclasses import dataclass, field

from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    ConversationStateV0Plus,
)
from mcrs.qu_modules.fuzzy_matcher import FuzzyMatcher
from mcrs.qu_modules.v0plus_catalog import CompilerCatalog


@dataclass(frozen=True)
class ResolvedRejection:
    """Resolved ids for one `explicit_rejections[i]` entry."""

    artist_ids: tuple[str, ...] = ()
    track_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedTarget:
    """A grounded positive `mentioned_entities` entry: surface form + best
    catalog match + confidence + full candidate list. The Compiler uses
    high-confidence artist targets to fetch discography candidates."""

    kind: str  # "artist" | "track"
    source_text: str
    entity_id: str | None
    confidence: float
    candidates: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class ResolvedConversationState:
    """Sidecar struct wrapping a v0+ state with the Resolver's deterministic
    id annotations + the mechanical (non-LLM) fields the Compiler needs.

    The Pydantic LLM contract (`ConversationStateV0Plus`) covers only the 7
    LLM-extracted fields per the v0+ schema doc; `played_track_ids` is
    mechanical (attached from the conversation log, not predicted by the LLM)
    so it lives here rather than on the LLM schema.
    """

    state: ConversationStateV0Plus
    played_track_ids: tuple[str, ...] = ()
    resolved_rejections: dict[int, ResolvedRejection] = field(default_factory=dict)
    track_feedback_artist_ids: dict[str, str | None] = field(default_factory=dict)
    resolved_targets: tuple[ResolvedTarget, ...] = ()


class V0PlusResolver:
    """Resolves rejections + annotates track_feedback artist_id.

    Pure orchestration over two dependencies:
      - `FuzzyMatcher` for surface-form → entity-id resolution
      - `CompilerCatalog` for track_id → artist_id lookups and
        artist_id → track_ids expansion
    """

    def __init__(
        self,
        matcher: FuzzyMatcher,
        catalog: CompilerCatalog,
        *,
        score_cutoff: int = 80,
        artist_match_topk: int = 20,
        track_match_topk: int = 5,
    ) -> None:
        self.matcher = matcher
        self.catalog = catalog
        self.score_cutoff = score_cutoff
        self.artist_match_topk = artist_match_topk
        self.track_match_topk = track_match_topk

    def resolve(
        self,
        state: ConversationStateV0Plus,
        played_track_ids: list[str] | None = None,
    ) -> ResolvedConversationState:
        resolved_rejections = {
            i: self._resolve_rejection(er.kind, er.value)
            for i, er in enumerate(state.explicit_rejections)
            if er.kind in ("artist", "track")
        }
        tf_artists = {
            tf.track_id: self.catalog.artist_id_of(tf.track_id)
            for tf in state.track_feedback
        }
        resolved_targets = tuple(
            self._ground_target(me.type, me.value)
            for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type in ("artist", "track")
        )
        return ResolvedConversationState(
            state=state,
            played_track_ids=tuple(played_track_ids or ()),
            resolved_rejections=resolved_rejections,
            track_feedback_artist_ids=tf_artists,
            resolved_targets=resolved_targets,
        )

    def _ground_target(self, kind: str, value: str) -> ResolvedTarget:
        topk = self.artist_match_topk if kind == "artist" else self.track_match_topk
        matches = self.matcher.match(
            value, kind, topk=topk, score_cutoff=self.score_cutoff
        )
        best_id, best_score = matches[0] if matches else (None, 0.0)
        return ResolvedTarget(
            kind=kind,
            source_text=value,
            entity_id=best_id,
            confidence=float(best_score),
            candidates=tuple((eid, float(s)) for eid, s in matches),
        )

    def _resolve_rejection(self, kind: str, value: str) -> ResolvedRejection:
        if kind == "artist":
            matches = self.matcher.match(
                value,
                "artist",
                topk=self.artist_match_topk,
                score_cutoff=self.score_cutoff,
            )
            return ResolvedRejection(artist_ids=tuple(eid for eid, _ in matches))
        if kind == "track":
            matches = self.matcher.match(
                value,
                "track",
                topk=self.track_match_topk,
                score_cutoff=self.score_cutoff,
            )
            track_ids = tuple(eid for eid, _ in matches)
            artist_ids = tuple(
                dict.fromkeys(
                    artist_id
                    for track_id in track_ids
                    if (artist_id := self.catalog.artist_id_of(track_id)) is not None
                )
            )
            return ResolvedRejection(artist_ids=artist_ids, track_ids=track_ids)
        return ResolvedRejection()
