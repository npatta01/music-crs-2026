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

See: docs/architectures/session_state.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcrs.conversation_state.schema import (
    ConversationStateV0Plus,
)
from mcrs.qu_modules.fuzzy_matcher import FuzzyMatcher
from mcrs.qu_modules.catalog import CompilerCatalog


_EXACT_TRACK_ARTIST_CONSTRAINED_MIN_SCORE = 90


@dataclass(frozen=True)
class ResolvedRejection:
    """Resolved ids for one `explicit_rejections[i]` entry."""

    artist_ids: tuple[str, ...] = ()
    track_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedTarget:
    """A grounded positive `mentioned_entities` entry: surface form + best
    catalog match + confidence + full candidate list. `resolution_role` keeps
    exact current targets separate from style/reference anchors so the Compiler
    can route them to different retriever surfaces."""

    kind: str  # "artist" | "track"
    source_text: str
    entity_id: str | None
    confidence: float
    candidates: tuple[tuple[str, float], ...] = ()
    resolution_role: str = "exact_target"


@dataclass(frozen=True)
class ResolvedConversationState:
    """Sidecar struct wrapping a v0+ state with the Resolver's deterministic
    id annotations + the mechanical (non-LLM) fields the Compiler needs.

    The Pydantic LLM contract (`ConversationStateV0Plus`) covers the
    LLM-extracted fields; `played_track_ids` is
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
        resolved_targets = tuple(self._ground_targets(state))
        return ResolvedConversationState(
            state=state,
            played_track_ids=tuple(played_track_ids or ()),
            resolved_rejections=resolved_rejections,
            track_feedback_artist_ids=tf_artists,
            resolved_targets=resolved_targets,
        )

    def _ground_targets(self, state: ConversationStateV0Plus) -> list[ResolvedTarget]:
        out: list[ResolvedTarget] = []
        seen: set[tuple[str, str]] = set()
        exact_artist_ids, exact_artist_names = self._exact_artist_constraints(state)
        for me in state.mentioned_entities:
            if me.sentiment < 0 or me.type not in ("artist", "track"):
                continue
            key = (me.type, me.value.casefold().strip())
            if key in seen:
                continue
            seen.add(key)
            out.append(
                self._ground_target(
                    me.type,
                    me.value,
                    "exact_target",
                    exact_artist_ids=exact_artist_ids,
                    exact_artist_names=exact_artist_names,
                )
            )
        for me in state.style_reference_entities:
            if me.sentiment < 0 or me.type not in ("artist", "track"):
                continue
            key = (me.type, me.value.casefold().strip())
            if key in seen:
                continue
            seen.add(key)
            out.append(self._ground_target(me.type, me.value, "style_reference"))
        return out

    def _ground_target(
        self,
        kind: str,
        value: str,
        resolution_role: str = "exact_target",
        *,
        exact_artist_ids: set[str] | None = None,
        exact_artist_names: set[str] | None = None,
    ) -> ResolvedTarget:
        topk = self.artist_match_topk if kind == "artist" else self.track_match_topk
        matches = self.matcher.match(
            value, kind, topk=topk, score_cutoff=self.score_cutoff
        )
        if (
            kind == "track"
            and resolution_role == "exact_target"
            and (exact_artist_ids or exact_artist_names)
        ):
            constrained_matcher = getattr(self.matcher, "match_track_by_artist", None)
            constrained = (
                constrained_matcher(
                    value,
                    artist_ids=exact_artist_ids or set(),
                    artist_names=exact_artist_names or set(),
                    topk=max(topk, 20),
                    score_cutoff=max(
                        self.score_cutoff,
                        _EXACT_TRACK_ARTIST_CONSTRAINED_MIN_SCORE,
                    ),
                )
                if callable(constrained_matcher)
                else []
            )
            if constrained:
                matches = constrained
            else:
                return ResolvedTarget(
                    kind=kind,
                    source_text=value,
                    entity_id=None,
                    confidence=0.0,
                    candidates=tuple((eid, float(s)) for eid, s in matches),
                    resolution_role=resolution_role,
                )
        best_id, best_score = matches[0] if matches else (None, 0.0)
        return ResolvedTarget(
            kind=kind,
            source_text=value,
            entity_id=best_id,
            confidence=float(best_score),
            candidates=tuple((eid, float(s)) for eid, s in matches),
            resolution_role=resolution_role,
        )

    @staticmethod
    def _enum_value(value: Any) -> str:
        return str(getattr(value, "value", value) or "")

    @classmethod
    def _request_type_value(cls, state: ConversationStateV0Plus) -> str:
        current_request = getattr(state, "current_request", None)
        request_type = getattr(current_request, "request_type", None)
        return cls._enum_value(request_type)

    def _exact_artist_constraints(
        self,
        state: ConversationStateV0Plus,
    ) -> tuple[set[str], set[str]]:
        values: list[str] = []
        for fact in getattr(state, "facts", []) or []:
            if self._enum_value(getattr(fact, "type", None)) != "artist":
                continue
            if self._enum_value(getattr(fact, "role", None)) != "current_target":
                continue
            anchor_use = self._enum_value(getattr(fact, "anchor_use", None))
            relation = self._enum_value(getattr(fact, "relation", None))
            reuse = self._enum_value(getattr(fact, "reuse", None))
            if (
                anchor_use != "must_use"
                and relation != "exact_target"
                and reuse != "must_reuse"
            ):
                continue
            value = str(getattr(fact, "value", "") or "").strip()
            if value:
                values.append(value)
        if not values and self._request_type_value(state) == "exact_track":
            values.extend(
                me.value
                for me in state.mentioned_entities
                if me.sentiment > 0 and me.type == "artist" and me.value
            )
        names = {value.casefold().strip() for value in values if value.strip()}
        ids: set[str] = set()
        for value in values:
            ids.update(
                entity_id
                for entity_id, _ in self.matcher.match(
                    value,
                    "artist",
                    topk=self.artist_match_topk,
                    score_cutoff=self.score_cutoff,
                )
            )
        return ids, names

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
