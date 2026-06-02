"""Post-fusion rerank features.

Design: each Feature returns a per-candidate multiplier in [0, +inf). The
reranker combines them as `final = fused_score * product(f_i.value ** weight_i)`.

Equal weights = pure multiplicative composition. Weight=0 disables a feature
without removing it. Weight=2 amplifies. log-space additive form:
`log_score += weight * log(feature_value)` is the standard LTR shape.

The framework is intentionally small — TWO features now, each internally
rich. The per-rule contributions inside each feature are preserved on
`FeatureValue.breakdown` for diagnostics + future LTR weight learning.

Why two features and not seven atomic ones: the signal-source axis is the
right cut — features differ by where the data comes from, not by which
candidate-attribute they look at. User-declared feedback (rejections,
positive mentions) is one source; session history + policy-driven anchor
demote is another. Sub-rules inside each feature can have their own
multipliers and are exposed individually via `breakdown` so a future
learned reranker can recover atomic-feature granularity from trace data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from mcrs.conversation_state.schema import (
    ExplorationPolicy,
)
from mcrs.qu_modules.resolver_v0plus import ResolvedConversationState


class CatalogProtocol(Protocol):
    """Minimal catalog interface a feature needs. Both `LanceDbCatalog`
    and `HFTalkPlayCatalog` implement these."""

    def artist_id_of(self, track_id: str) -> str | None: ...
    def album_id_of(self, track_id: str) -> str | None: ...
    def tag_list(self, track_id: str) -> list[str]: ...
    def release_year_of(self, track_id: str) -> int | None: ...


@dataclass
class FeatureValue:
    """Output of a single feature evaluation on one candidate.

    `value` is the rolled-up multiplier (product of all sub-rules within
    this feature). `breakdown` is the per-sub-rule decomposition for
    diagnostics + future training. A future LTR step can `breakdown`
    back out into atomic-feature columns.
    """

    name: str
    value: float
    breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class FeatureTrace:
    """Per-candidate diagnostic: feature values + final multiplier."""

    track_id: str
    fused_score_in: float
    final_score_out: float
    values: list[FeatureValue] = field(default_factory=list)


class Feature(Protocol):
    """A single rerank feature. Stateless across candidates; closes over any
    precomputed sets at construction so `compute()` is O(1) per candidate."""

    name: str

    def compute(self, track_id: str, catalog: CatalogProtocol) -> FeatureValue: ...


# ----------------------------------------------------------------------
# Feature 1: user-declared feedback (everything the LLM extracted from
# what the user explicitly said — rejections + positive mentions)
# ----------------------------------------------------------------------


@dataclass
class UserFeedbackFeature:
    """Aggregates all signals the user explicitly told us.

    Sub-rules (applied multiplicatively):
      - explicit track rejection: track_id in rejected_track_ids
        (kind=track in explicit_rejections, resolver-matched)
      - explicit artist rejection: artist_id in rejected_artist_ids
        (kind=artist in explicit_rejections, resolver-matched)
      - explicit tag rejection: per overlapping rejected tag
        (kind=tag in explicit_rejections)
      - inferred artist rejection: artist_id in inferred_rejected_artist_ids
        (artist of a track_feedback.role=rejected entry — softer than
        explicit_rejections because the signal is indirect)
      - positive tag boost: per overlapping positive tag

    Defaults match the legacy `_apply_soft_adjustments` semantics:
    explicit track / artist rejection are hard (multiplier=0.0).
    A future learned reranker can pull each sub-rule out of `breakdown`
    and weight them independently if needed.
    """

    name: str
    rejected_track_ids: frozenset[str] = frozenset()
    rejected_artist_ids: frozenset[str] = frozenset()
    rejected_tags: frozenset[str] = frozenset()
    positive_tags: frozenset[str] = frozenset()
    inferred_rejected_artist_ids: frozenset[str] = frozenset()

    # Sub-rule multipliers — tunable knobs (defaults match legacy behavior)
    track_rejection_mult: float = 0.0
    artist_rejection_mult: float = 0.0
    inferred_artist_rejection_mult: float = 0.7   # legacy `same_artist_demote`
    tag_rejection_per_overlap: float = 0.5        # legacy `rejected_tag_multiplier`
    positive_tag_per_overlap: float = 1.15        # legacy 1 + `positive_tag_multiplier_step`

    def compute(self, track_id: str, catalog: CatalogProtocol) -> FeatureValue:
        breakdown: dict[str, float] = {}
        m = 1.0

        if track_id in self.rejected_track_ids:
            breakdown["track_rejection"] = self.track_rejection_mult
            m *= self.track_rejection_mult
            if m == 0.0:
                return FeatureValue(self.name, m, breakdown=breakdown)

        artist_id = catalog.artist_id_of(track_id)
        if artist_id is not None and artist_id in self.rejected_artist_ids:
            breakdown["artist_rejection"] = self.artist_rejection_mult
            m *= self.artist_rejection_mult
            if m == 0.0:
                return FeatureValue(self.name, m, breakdown=breakdown)

        if artist_id is not None and artist_id in self.inferred_rejected_artist_ids:
            breakdown["inferred_artist_rejection"] = self.inferred_artist_rejection_mult
            m *= self.inferred_artist_rejection_mult

        tags = {t.lower() for t in catalog.tag_list(track_id)} if (self.rejected_tags or self.positive_tags) else set()
        if self.rejected_tags and tags:
            overlap = len(tags & self.rejected_tags)
            if overlap:
                v = self.tag_rejection_per_overlap ** overlap
                breakdown["tag_rejection"] = v
                m *= v
        if self.positive_tags and tags:
            overlap = len(tags & self.positive_tags)
            if overlap:
                v = self.positive_tag_per_overlap ** overlap
                breakdown["positive_tag"] = v
                m *= v

        return FeatureValue(self.name, m, breakdown=breakdown)


# ----------------------------------------------------------------------
# Feature 2: session anchor / history (replay prevention + policy-driven
# anchor demote — everything we infer from `played_track_ids` and the
# exploration policy)
# ----------------------------------------------------------------------


# Per-policy multiplier for anchor-artist demote. Defaults preserve legacy
# behavior: only `diversify_artists` introduces a demote. `balanced` is 1.0
# so existing devset numbers are unchanged when the LLM extracts the (now
# default) `balanced` policy on a turn.
ANCHOR_ARTIST_DEMOTE_BY_POLICY: dict[ExplorationPolicy, float] = {
    ExplorationPolicy.exploit: 1.0,
    ExplorationPolicy.balanced: 1.0,            # legacy: no demote
    ExplorationPolicy.diversify_artists: 0.4,
    ExplorationPolicy.diversify_albums: 1.0,    # album-level handles it (see album table)
}


# Per-policy multiplier for anchor-album demote. Only fires under
# `diversify_albums` policy.
ANCHOR_ALBUM_DEMOTE_BY_POLICY: dict[ExplorationPolicy, float] = {
    ExplorationPolicy.exploit: 1.0,
    ExplorationPolicy.balanced: 1.0,
    ExplorationPolicy.diversify_artists: 1.0,   # artist-level handles it
    ExplorationPolicy.diversify_albums: 0.6,
}


@dataclass
class SessionAnchorFeature:
    """Aggregates all signals derived from session history + exploration policy.

    Sub-rules (applied multiplicatively):
      - already-played: factual replay prevention (multiplier=0 → hard drop)
      - anchor-artist demote: track's artist is in prior-played artists,
        strength depends on `exploration_policy`
      - anchor-album demote: track's album is in prior-played albums,
        fires under `diversify_albums`
    """

    name: str
    played_track_ids: frozenset[str] = frozenset()
    anchor_artist_ids: frozenset[str] = frozenset()
    anchor_album_ids: frozenset[str] = frozenset()

    already_played_mult: float = 0.0          # factual; hard drop
    anchor_artist_mult: float = 1.0           # set per policy at construction
    anchor_album_mult: float = 1.0            # set per policy at construction

    def compute(self, track_id: str, catalog: CatalogProtocol) -> FeatureValue:
        breakdown: dict[str, float] = {}
        m = 1.0

        if track_id in self.played_track_ids:
            breakdown["already_played"] = self.already_played_mult
            m *= self.already_played_mult
            return FeatureValue(self.name, m, breakdown=breakdown)

        if self.anchor_artist_ids and self.anchor_artist_mult != 1.0:
            artist_id = catalog.artist_id_of(track_id)
            if artist_id is not None and artist_id in self.anchor_artist_ids:
                breakdown["anchor_artist"] = self.anchor_artist_mult
                m *= self.anchor_artist_mult

        if self.anchor_album_ids and self.anchor_album_mult != 1.0:
            album_id = catalog.album_id_of(track_id)
            if album_id is not None and album_id in self.anchor_album_ids:
                breakdown["anchor_album"] = self.anchor_album_mult
                m *= self.anchor_album_mult

        return FeatureValue(self.name, m, breakdown=breakdown)


# ----------------------------------------------------------------------
# Feature 3: release-year soft preference (from state.release_year_range)
# ----------------------------------------------------------------------


@dataclass
class ReleaseYearRangeFeature:
    """Soft date-boosting from the LLM-extracted `release_year_range`.

    A SOFT preference, not a hard filter: a track inside the requested era is
    boosted; one outside is gently demoted with linear decay by how many years
    it falls outside the [start, end] interval, floored so it's never zeroed.
    Open-ended bounds (start or end is None) only constrain the side that's set.

    No-op (multiplier 1.0) when the turn has no era (`start`/`end` both None) or
    the candidate has no known release year — so it touches only the ~16% of
    turns that mention a time period.
    """

    name: str
    start_year: int | None = None
    end_year: int | None = None
    in_range_mult: float = 1.10          # gentle boost for in-era tracks
    per_year_outside_penalty: float = 0.05
    floor_mult: float = 0.6              # never demote below this

    def _active(self) -> bool:
        return self.start_year is not None or self.end_year is not None

    def compute(self, track_id: str, catalog: CatalogProtocol) -> FeatureValue:
        if not self._active():
            return FeatureValue(self.name, 1.0)
        year = catalog.release_year_of(track_id)
        if year is None:
            return FeatureValue(self.name, 1.0)
        lo = self.start_year if self.start_year is not None else year
        hi = self.end_year if self.end_year is not None else year
        if lo <= year <= hi:
            return FeatureValue(self.name, self.in_range_mult, breakdown={"in_range": self.in_range_mult})
        distance = (lo - year) if year < lo else (year - hi)
        m = max(self.floor_mult, 1.0 - self.per_year_outside_penalty * distance)
        return FeatureValue(self.name, m, breakdown={"outside_by_years": float(distance), "mult": m})


# ----------------------------------------------------------------------
# Builder: pull all the precomputed sets out of a ResolvedConversationState
# ----------------------------------------------------------------------


def build_features_for_state(
    rs: ResolvedConversationState,
    catalog: CatalogProtocol,
    *,
    # Tunable multipliers — defaults match legacy behavior. The compiler
    # passes its cfg-derived values here so existing knobs stay live.
    tag_rejection_per_overlap: float = 0.5,
    positive_tag_per_overlap: float = 1.15,
    inferred_artist_rejection_mult: float = 0.7,
    explicit_track_rejection_mult: float = 0.0,
    explicit_artist_rejection_mult: float = 0.0,
    anchor_artist_demote_by_policy: dict[ExplorationPolicy, float] | None = None,
    anchor_album_demote_by_policy: dict[ExplorationPolicy, float] | None = None,
    release_year_in_range_mult: float = 1.10,
    release_year_per_year_outside_penalty: float = 0.05,
    release_year_floor_mult: float = 0.6,
) -> list[Feature]:
    """Construct the feature set from a resolved state. Pre-computes
    the relevant id-sets so per-candidate `compute()` calls are O(1)."""
    state = rs.state
    policy = state.process_constraints.exploration_policy

    # --- explicit feedback sets (LLM-extracted, resolver-matched) ---
    rejected_track_ids: set[str] = set()
    rejected_artist_ids: set[str] = set()
    for rj in rs.resolved_rejections.values():
        rejected_track_ids.update(rj.track_ids)
        rejected_artist_ids.update(rj.artist_ids)

    rejected_tags = frozenset(
        er.value.lower()
        for er in state.explicit_rejections
        if er.kind == "tag" and er.value
    )
    positive_tags = frozenset(
        me.value.lower()
        for me in state.mentioned_entities
        if me.sentiment > 0 and me.type == "tag" and me.value
    )

    # --- inferred artist rejection from track_feedback (role=rejected) ---
    inferred_rejected_artist_ids: set[str] = set()
    for tf in state.track_feedback:
        if tf.role == "rejected":
            aid = rs.track_feedback_artist_ids.get(tf.track_id)
            if aid:
                inferred_rejected_artist_ids.add(aid)

    # --- session-history sets (factual + policy-conditional) ---
    played = frozenset(rs.played_track_ids)
    artist_table = anchor_artist_demote_by_policy or ANCHOR_ARTIST_DEMOTE_BY_POLICY
    album_table = anchor_album_demote_by_policy or ANCHOR_ALBUM_DEMOTE_BY_POLICY
    anchor_artist_mult = artist_table.get(policy, 1.0)
    anchor_album_mult = album_table.get(policy, 1.0)

    anchor_artist_ids: set[str] = set()
    anchor_album_ids: set[str] = set()
    # Only materialize anchor sets when the policy will actually use them
    if anchor_artist_mult != 1.0:
        for tid in rs.played_track_ids:
            aid = catalog.artist_id_of(tid)
            if aid:
                anchor_artist_ids.add(aid)
    if anchor_album_mult != 1.0:
        for tid in rs.played_track_ids:
            alb = catalog.album_id_of(tid)
            if alb:
                anchor_album_ids.add(alb)

    return [
        UserFeedbackFeature(
            name="user_feedback",
            rejected_track_ids=frozenset(rejected_track_ids),
            rejected_artist_ids=frozenset(rejected_artist_ids),
            rejected_tags=rejected_tags,
            positive_tags=positive_tags,
            inferred_rejected_artist_ids=frozenset(inferred_rejected_artist_ids),
            track_rejection_mult=explicit_track_rejection_mult,
            artist_rejection_mult=explicit_artist_rejection_mult,
            inferred_artist_rejection_mult=inferred_artist_rejection_mult,
            tag_rejection_per_overlap=tag_rejection_per_overlap,
            positive_tag_per_overlap=positive_tag_per_overlap,
        ),
        SessionAnchorFeature(
            name="session_anchor",
            played_track_ids=played,
            anchor_artist_ids=frozenset(anchor_artist_ids),
            anchor_album_ids=frozenset(anchor_album_ids),
            anchor_artist_mult=anchor_artist_mult,
            anchor_album_mult=anchor_album_mult,
        ),
        ReleaseYearRangeFeature(
            name="release_year_range",
            start_year=(state.release_year_range.start if state.release_year_range else None),
            end_year=(state.release_year_range.end if state.release_year_range else None),
            in_range_mult=release_year_in_range_mult,
            per_year_outside_penalty=release_year_per_year_outside_penalty,
            floor_mult=release_year_floor_mult,
        ),
    ]


# ----------------------------------------------------------------------
# Reranker
# ----------------------------------------------------------------------


@dataclass
class PostFusionReranker:
    """Applies a list of features to fused candidates.

    Score composition: `final = fused * product(value_i ** weight_i)`.
    Default weight per feature is 1.0 (pure multiplicative composition).
    `weight = 0` disables a feature without removing it from the pipeline
    (useful for ablation). `weight = 2` amplifies.

    When `record_trace=True`, every per-candidate feature value + breakdown
    is captured in `traces` so we can later learn weights from real data.
    """

    features: list[Feature]
    weights: dict[str, float] | None = None
    record_trace: bool = False
    traces: list[FeatureTrace] = field(default_factory=list)

    def __post_init__(self):
        if self.weights is None:
            self.weights = {f.name: 1.0 for f in self.features}

    def rerank(
        self,
        fused: list[tuple[str, float]],
        catalog: CatalogProtocol,
    ) -> list[tuple[str, float]]:
        self.traces = []
        adjusted: list[tuple[str, float]] = []
        for tid, fused_score in fused:
            multiplier = 1.0
            trace_values: list[FeatureValue] = []
            for f in self.features:
                fv = f.compute(tid, catalog)
                w = self.weights.get(f.name, 1.0)
                if w == 0.0:
                    contrib = 1.0
                elif fv.value == 0.0:
                    contrib = 0.0
                else:
                    contrib = fv.value ** w
                multiplier *= contrib
                trace_values.append(fv)
                if multiplier == 0.0 and not self.record_trace:
                    break
            final = fused_score * multiplier
            if self.record_trace:
                self.traces.append(
                    FeatureTrace(
                        track_id=tid,
                        fused_score_in=fused_score,
                        final_score_out=final,
                        values=trace_values,
                    )
                )
            if final > 0.0:
                adjusted.append((tid, final))
        adjusted.sort(key=lambda x: -x[1])
        return adjusted
