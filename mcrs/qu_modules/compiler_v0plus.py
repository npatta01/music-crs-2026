"""v0+ ConversationState Compiler.

Takes a `ResolvedConversationState` (from `V0PlusResolver`) plus the catalog
plus a `Retriever` (LanceDB), and produces the top-1000 ranked track_ids the
TalkPlayData challenge requires.

Architecture (one call per branch, compiler-owned cross-modal fusion):

    state + resolver → ResolvedConversationState
                       │
                       ▼
              Pre-fusion catalog mask (release_date)
                       │
              ┌────────┴────────┐
              ▼                 ▼
       BM25 search        Dense ANN
       (1 call, N fields)  (1 call, vector_field)
              │                 │
              └────────┬────────┘
                       ▼
              RRF fusion (uniform weights)
                       │
                       ▼
              Hard drops + soft (de)promotes
                       │
                       ▼
              Backfill to topk (popularity-sorted, mask-respecting)
                       │
                       ▼
              top-1000 track_ids

See: docs/architectures/v0plus_retrieval.md
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# Word-boundary tokenizer for lyric-hint detection. Splits on any
# non-word character so substring matches like `"story" in "history"` or
# `"deep" in "deepfake"` don't accidentally fire the lyric branch.
_LYRIC_TOKEN_RE = re.compile(r"\w+")

from mcrs.conversation_state.schema import (
    ConversationStateV0Plus,
)
from mcrs.embeddings.base import EmbeddingClient
from mcrs.qu_modules.resolver_v0plus import ResolvedConversationState
from mcrs.qu_modules.v0plus_catalog import CompilerCatalog
from mcrs.retrieval_modules.base import FieldQuery, Retriever


DEFAULT_FIELD_BOOSTS = {
    "track_name": 3.0,
    "artist_name": 3.0,
    "album_name": 2.0,
    "tag_list": 1.5,
    # Disabled until a reindexed devset run proves neutral-or-better impact.
    "release_year": 0.0,
    "release_decade": 0.0,
}


@dataclass
class BranchPool:
    """One retriever branch's contribution, retained for tracing.

    A branch appears in `CompileResult.branch_pools` only when it FIRED
    (issued a retrieval call) on this turn AND per-branch tracing is enabled
    (`CompilerConfig.branch_trace_topk > 0`). Branches that did not fire
    (e.g. a dense branch with no query, or a centroid branch whose centroid
    is None) are omitted.

    `hits` are the branch's RAW top-`branch_trace_topk` `(track_id, score)`
    pairs — captured BEFORE the release-date mask and hard-drop set are
    applied, matching the per-retriever "did this branch surface the GT at
    all" semantics. Rank is the list index.
    """

    name: str
    hits: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class CompileResult:
    """Structured output of `V0PlusCompiler._compile()`.

    `ranked` is the exact list `compile()` returns (top-final_topk). The other
    fields are the per-branch / fused / provenance artifacts the devset trace
    persists for downstream rerank / explanation pickup. They are only
    populated when `CompilerConfig.branch_trace_topk > 0`; otherwise
    `branch_pools` / `fused` are empty and `compile()` behaves exactly as
    before (submission path unaffected).

    `fused` is the RRF-fused list BEFORE soft (de)promotes; `ranked` is the
    final list AFTER soft adjustments AND popularity backfill.

    `n_from_fusion` counts how many of `ranked` came through the fusion
    pipeline (RRF + soft (de)promotes, which also hard-drops resolved
    rejections), NOT only the raw RRF step; `n_from_backfill` counts the
    popularity-backfill remainder. The two always sum to `len(ranked)`.
    """

    ranked: list[str]
    branch_pools: list[BranchPool] = field(default_factory=list)
    fused: list[tuple[str, float]] = field(default_factory=list)
    n_from_fusion: int = 0
    n_from_backfill: int = 0
    depth: int = 0
    branch_queries: dict[str, dict] = field(default_factory=dict)
    branch_status: dict[str, dict] = field(default_factory=dict)
    candidate_filter_summary: dict[str, int] = field(default_factory=dict)

    def to_trace_dict(self) -> dict:
        """Serialize to the `branches` trace schema (JSON-friendly)."""
        return {
            "depth": self.depth,
            "pools": [
                {"name": p.name, "hits": [[t, float(s)] for t, s in p.hits]}
                for p in self.branch_pools
            ],
            "fused": [[t, float(s)] for t, s in self.fused],
            "final": {
                "track_ids": list(self.ranked),
                "n_from_fusion": self.n_from_fusion,
                "n_from_backfill": self.n_from_backfill,
            },
            "recommended": {
                "top1_track_id": self.ranked[0] if self.ranked else None,
            },
            "branch_queries": self.branch_queries,
            "branch_status": self.branch_status,
            "candidate_filter_summary": self.candidate_filter_summary,
        }


@dataclass
class DenseBranch:
    """One dense retrieval branch — a vector column to ANN-query against.

    The Compiler issues one `search_embedding(...)` call per enabled branch.

    Two strings address what gets encoded against what:
    - `encoder_id` picks which `EmbeddingClient` from the compiler's
      `encoders` map encodes this branch's query. Default is `"default"`
      for back-compat with single-encoder configs (today's Qwen3-only setup).
      New text-side branches set this to e.g. `"siglip2_text"` / `"clap_text"`.
    - `query_id` picks which query string template to use. Default `"intent"`
      uses the standard turn_intent + entities + tags concatenation. Future
      per-modality templates (visual-style, sonic) can be added without
      touching code by defining new entries in the CompilerConfig.queries
      mapping.

    The encoded vector is cached per (encoder_id, query_id) tuple so multiple
    branches sharing an encoder/query pay one encode call.
    """

    vector_field: str
    weight: float = 1.0
    distance_type: str = "cosine"
    encoder_id: str = "default"
    query_id: str = "intent"


@dataclass
class CentroidOnlyBranch:
    """A vector branch whose query is a precomputed centroid (no encoded
    query text). Two centroid sources are supported:

    - `centroid_source="anchor_tracks"` (default): centroid = mean of the
      positive-anchor track vectors in `vector_field`. Skipped when there
      are no anchors (turn 1, pure pivot, zero-positive-feedback turns).
      Used for cf_bpr (co-listening), audio_laion_clap (sonic),
      image_siglip2 (cover art).

    - `centroid_source="user"`: centroid = the current user's precomputed
      vector in `vector_field` (loaded from the user-embeddings catalog).
      Fires every turn including turn 1, so long as a `user_id` is provided
      and the user has a vector in that field. Used for user_cf_bpr — the
      only user-side modality available in TalkPlayData. Provides a per-user
      "always-on" preference prior that complements per-turn anchor signals.
    """

    vector_field: str
    weight: float = 1.0
    topk: int = 1000
    distance_type: str = "cosine"
    centroid_source: str = "anchor_tracks"  # or "user"


@dataclass
class CompilerConfig:
    """Configuration for the v0+ Compiler.

    Defaults are the rev-7 design's recommended starting values. Each is
    an obvious ablation target if eval shows we need to tune."""

    bm25_k: int = 1000
    dense_k: int = 1000
    rrf_k: int = 60
    final_topk: int = 1000

    field_boosts: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_FIELD_BOOSTS)
    )

    # Anchor centroid mix α per intent_mode. 0 = no mixing. The same α is
    # applied per dense branch (each branch uses its own field's centroid).
    centroid_alpha: dict[str, float] = field(
        default_factory=lambda: {
            "refinement": 0.4,
            "playlist_build": 0.5,
            "pivot": 0.0,
            "open_explore": 0.0,
        }
    )

    # Top-N anchor tags appended to the tag_list BM25 channel.
    anchor_tag_expansion_n: int = 5

    # Soft-demote per overlapping rejected tag (multiplier^count).
    rejected_tag_multiplier: float = 0.5

    # Soft-promote per overlapping positive tag (additive multiplier^count).
    positive_tag_multiplier_step: float = 0.15

    # Same-artist-as-rejected demote.
    same_artist_demote: float = 0.7

    # Dense branches — one search_embedding call per entry. Default fans across
    # the three text-derived Qwen3 columns in the talkpl-ai catalog (metadata
    # + attributes + lyrics). The audio/image/CF columns aren't ANN-queryable
    # in the current LanceDB index, see docs/talkplay_embedding_specs.md.
    dense_branches: list[DenseBranch] = field(
        default_factory=lambda: [
            DenseBranch(vector_field="metadata_qwen3_embedding_0_6b", weight=1.0),
            DenseBranch(vector_field="attributes_qwen3_embedding_0_6b", weight=1.0),
            DenseBranch(vector_field="lyrics_qwen3_embedding_0_6b", weight=1.0),
        ]
    )

    # Master kill-switch for the dense modality. When False, all dense branches
    # are skipped and the compiler runs BM25-only.
    enable_dense: bool = True

    # Centroid-only branches: behavioral / sonic / visual signals with no
    # encoded query text. Each entry fires one `retriever.search_embedding`
    # call with the anchor-track centroid in the branch's vector space. Used
    # for `cf_bpr` (co-listening), `audio_laion_clap` (sonic), `image_siglip2`
    # (cover art). Branches skip when there are no positive anchors.
    centroid_only_branches: list[CentroidOnlyBranch] = field(default_factory=list)

    # Legacy single-cf_bpr knobs. If `enable_cf_bpr=True` and
    # `centroid_only_branches` is empty, the compiler synthesizes a 1-entry
    # centroid_only_branches list from these. Kept for back-compat with
    # configs/v0plus_compiler_cfbpr_devset.yaml.
    enable_cf_bpr: bool = False
    cf_bpr_topk: int = 1000
    cf_bpr_weight: float = 1.0
    cf_bpr_vector_field: str = "cf_bpr"
    cf_bpr_distance_type: str = "cosine"

    # Per-branch diagnostic depth. When > 0, `_compile()` retains each branch's
    # RAW top-K `(track_id, score)` pool on the CompileResult (and the QU writes
    # it to the trace's `branches` key — see scripts/branch_diagnostics.py).
    # Covers BM25 + each dense + each centroid-only + lookup pools. 0 means off
    # (no trace cost; submission path unchanged). Use for offline diagnostics
    # like "where does the GT rank inside each retriever?" and the fusion
    # coverage ceiling. Costs ~K * branches * turns of trace when on.
    branch_trace_topk: int = 0

    # Resolved-artist discography branch (issue #74 Stage A). Off by default.
    enable_resolved_artist_discography: bool = False
    disco_weight: float = 1.0
    disco_cap: int = 150
    disco_confidence_threshold: float = 90.0
    disco_gated_intents: tuple[str, ...] = ("pivot",)

    # Similar-artist anchoring (issue #74 Fix 1). Off by default => baseline is
    # byte-identical. When on, a few representative tracks of each RESOLVED
    # reference artist ("similar to X", "like X") are fed as ADDITIONAL anchors
    # into the centroid-only vector branches (audio/cf_bpr/image), so the
    # centroid points at "tracks like X" and pulls related artists toward the
    # top — even on turn-1 / pivot turns with no played tracks. These anchors
    # affect ONLY the vector centroid; tag expansion stays on played anchors.
    enable_similar_artist_anchors: bool = False
    similar_artist_anchor_topk: int = 3
    similar_artist_confidence_threshold: float = 90.0
    similar_artist_max_artists: int = 5
    # Intent gate (Fix 1b): inject similar-artist anchors ONLY when the named
    # artist is actually the retrieval target this turn. Measured on the slice,
    # the injection is a clean win when the turn is an exact-entity probe
    # (improved 43 / worsened 17) or open_explore (17/1) / pivot (8/0), and
    # churns or hurts on refinement (77/60) / playlist_build (5/9, negative) —
    # where the artist is a "more like X but different" comparison, so forcing
    # X's own tracks into the centroid fights the request. Gate on the
    # exact_entity_probe routing tag plus this intent allowlist.
    similar_artist_anchor_intents: tuple[str, ...] = ("open_explore", "pivot")
    similar_artist_anchor_on_exact_entity: bool = True

    # Era/popularity branch (#3). When the extractor emits a release_year_range,
    # return the top-N most-popular catalog tracks whose release year falls in
    # that range. Targets canonical era classics (a-ha, Boston, New Order) that
    # no content/CF branch reaches. Off by default.
    enable_era_popularity: bool = False
    era_pop_weight: float = 1.0
    era_pop_cap: int = 200
    # Deprecated release-year pre-filter config. v1 hard release-date asks are
    # represented as hard_filters via temporal_constraint.apply_as_filter=true;
    # soft release_year_range/style-era hints do not gate candidates here. Keep
    # the fields so older configs still parse.
    enable_release_year_filter: bool = False
    release_year_filter_min_keep: int = 50
    routing_boost: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Partial config dicts inherit standard boosts without mutating the
        # caller-owned mapping passed to the dataclass constructor.
        self.field_boosts = {**DEFAULT_FIELD_BOOSTS, **self.field_boosts}


class V0PlusCompiler:
    """Turn a ResolvedConversationState into top-N ranked track_ids."""

    def __init__(
        self,
        catalog: CompilerCatalog,
        retriever: Retriever,
        encoder: EmbeddingClient | None = None,
        config: CompilerConfig | None = None,
        user_embeddings: "UserEmbeddings | None" = None,
        encoders: dict[str, EmbeddingClient] | None = None,
    ) -> None:
        self.catalog = catalog
        self.retriever = retriever
        # Encoder registry. Back-compat: a single `encoder=` becomes the
        # "default" entry. New configs may pass `encoders=` directly with
        # additional named encoders (e.g. "siglip2_text", "clap_text").
        if encoder is None and not encoders:
            raise ValueError(
                "V0PlusCompiler requires either `encoder` or a non-empty `encoders` map"
            )
        self.encoders: dict[str, EmbeddingClient] = dict(encoders or {})
        if encoder is not None:
            self.encoders.setdefault("default", encoder)
        # Legacy single-encoder accessor kept for any external caller that
        # still references `compiler.encoder` directly.
        self.encoder: EmbeddingClient | None = self.encoders.get("default", encoder)
        self._pop_rank: dict[str, int] | None = None
        self.cfg = config or CompilerConfig()
        # Optional user-side embeddings lookup. Required only when a config
        # uses `centroid_only_branches` with `centroid_source="user"`. None
        # otherwise, and the user branch is silently skipped.
        self.user_embeddings = user_embeddings
        self._catalog_release_year_bounds_cached = False
        self._catalog_release_year_bounds_cache: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def compile(self, rs: ResolvedConversationState, user_id: str | None = None) -> list[str]:
        """Public entry point. Returns top-final_topk track_ids (unchanged
        output contract). Delegates to `_compile`, which also retains the
        per-branch pools + fused/final funnel for tracing when
        `CompilerConfig.branch_trace_topk > 0`."""
        return self._compile(rs, user_id=user_id).ranked

    def _compile(
        self, rs: ResolvedConversationState, user_id: str | None = None
    ) -> CompileResult:
        """Compile a resolved state into a CompileResult.

        When `self.cfg.branch_trace_topk > 0`, each retriever branch's RAW
        top-K `(track_id, score)` pool is retained on the result under a stable
        name ("bm25", "dense.<encoder_id>.<query_id>.<vector_field>",
        "centroid.<source>.<vector_field>", "lookup.resolved_artist_discography",
        "lookup.era_popularity"), along with the pre-soft-adjust `fused` list,
        the `final` recommendation (+ provenance), and the headline track. When
        the knob is 0 those fields stay empty and only `ranked` is meaningful.
        """
        state = rs.state
        _trace_k = self.cfg.branch_trace_topk
        named_pools: list[tuple[str, list[tuple[str, float]]]] = []
        trace_enabled = _trace_k > 0
        branch_queries: dict[str, dict] = {}
        branch_status: dict[str, dict] = {}

        # 1. Pre-fusion catalog mask from hard_filters.release_date
        candidate_mask = self._release_date_mask(state)

        # 2. Build queries
        bm25_clauses = self._build_bm25_clauses(rs)
        if trace_enabled:
            branch_queries["bm25"] = {
                "kind": "bm25",
                "clauses": [self._field_query_to_trace(c) for c in bm25_clauses],
            }
        # query_id -> query string (None when the state has no positive signal
        # for that template). Only build templates referenced by some branch
        # so unused builders never run. Reject unknown query_ids early.
        query_strings: dict[str, str | None] = {}
        if self.cfg.enable_dense:
            referenced_query_ids = {b.query_id for b in self.cfg.dense_branches}
            builders = self._query_builders
            for qid in referenced_query_ids:
                if qid not in builders:
                    raise KeyError(
                        f"DenseBranch references unknown query_id={qid!r}. "
                        f"Available templates: {sorted(builders)}"
                    )
                query_strings[qid] = builders[qid](rs)

        # 3. Retrieval — 1 BM25 call + 1 search_embedding per enabled dense branch
        bm25_hits = self.retriever.search(bm25_clauses, topk=self.cfg.bm25_k)
        if trace_enabled:
            branch_status["bm25"] = {
                "configured": True,
                "fired": True,
                "n_raw_hits": len(bm25_hits),
            }
            named_pools.append(("bm25", list(bm25_hits[:_trace_k])))
        # Cache encoded vectors by (encoder_id, query_id) so branches sharing
        # an encoder/query pair pay one encode call total.
        encoded_cache: dict[tuple[str, str], list[float]] = {}
        dense_branch_results: list[list[tuple[str, float]]] = []
        if trace_enabled and not self.cfg.enable_dense:
            for branch in self.cfg.dense_branches:
                name = self._dense_branch_trace_name(branch)
                branch_queries[name] = self._dense_branch_query_trace(branch)
                branch_status[name] = {
                    "configured": True,
                    "fired": False,
                    "skip_reason": "disabled",
                }
        if self.cfg.enable_dense:
            supported_vector_fields = getattr(
                self.retriever,
                "supported_vector_fields",
                frozenset(),
            )
            for branch in self.cfg.dense_branches:
                branch_name = self._dense_branch_trace_name(branch)
                q_text = query_strings.get(branch.query_id)
                if trace_enabled:
                    query_trace = self._dense_branch_query_trace(branch)
                    if q_text is not None:
                        query_trace["query_text"] = q_text
                    branch_queries[branch_name] = query_trace
                if branch.vector_field not in supported_vector_fields:
                    dense_branch_results.append([])
                    if trace_enabled:
                        branch_status[branch_name] = {
                            "configured": True,
                            "fired": False,
                            "skip_reason": "unsupported_vector_field",
                        }
                    continue
                if q_text is None:
                    # Either query_id unknown OR state had no positive signal.
                    # Append empty hits to keep dense_branch_results aligned
                    # with self.cfg.dense_branches for the RRF fusion zip().
                    dense_branch_results.append([])
                    if trace_enabled:
                        branch_status[branch_name] = {
                            "configured": True,
                            "fired": False,
                            "skip_reason": "no_query",
                        }
                    continue
                cache_key = (branch.encoder_id, branch.query_id)
                if cache_key not in encoded_cache:
                    enc = self.encoders.get(branch.encoder_id)
                    if enc is None:
                        raise KeyError(
                            f"DenseBranch(vector_field={branch.vector_field!r}) "
                            f"references unknown encoder_id={branch.encoder_id!r}. "
                            f"Available encoders: {sorted(self.encoders)}"
                        )
                    raw = enc.embed_batch([q_text])[0]
                    encoded_cache[cache_key] = _normalize(raw)
                vec = self._mix_for_branch(rs, encoded_cache[cache_key], branch)
                hits = self.retriever.search_embedding(
                    query_vector=vec,
                    vector_field=branch.vector_field,
                    topk=self.cfg.dense_k,
                    distance_type=branch.distance_type,
                )
                dense_branch_results.append(hits)
                if trace_enabled:
                    branch_status[branch_name] = {
                        "configured": True,
                        "fired": True,
                        "n_raw_hits": len(hits),
                    }
                    # Include `query_id` so multiple branches sharing
                    # encoder_id + vector_field (e.g. v4's 3xCLAP) get
                    # distinct names instead of overwriting each other.
                    named_pools.append((
                        branch_name,
                        list(hits[:_trace_k]),
                    ))

        # 3b. Centroid-only branches — one `search_embedding` call per entry.
        # Two centroid sources:
        #  - "anchor_tracks": mean of positive-anchor track vectors. Skipped
        #    when there are no anchors (turn 1, pure pivot turns).
        #  - "user": the current user's precomputed vector. Fires every turn
        #    so long as a user_id is supplied AND the user has a vector in
        #    this field. Used for user_cf_bpr (only user-side modality in
        #    TalkPlayData).
        centroid_branches = self._resolve_centroid_only_branches()
        centroid_branch_results: list[tuple[list[tuple[str, float]], float]] = []
        supported_vector_fields = getattr(
            self.retriever,
            "supported_vector_fields",
            frozenset(),
        )
        for cb in centroid_branches:
            branch_name = self._centroid_branch_trace_name(cb)
            source_track_ids: list[str] = []
            if trace_enabled:
                query_trace = {
                    "kind": "centroid",
                    "centroid_source": cb.centroid_source,
                    "vector_field": cb.vector_field,
                    "distance_type": cb.distance_type,
                    "weight": float(cb.weight),
                }
                if cb.centroid_source == "anchor_tracks":
                    source_track_ids = self._centroid_source_track_ids(rs)
                    query_trace["source_track_ids"] = list(source_track_ids)
                elif cb.centroid_source == "user":
                    query_trace["user_id_present"] = user_id is not None
                branch_queries[branch_name] = query_trace
            if cb.vector_field not in supported_vector_fields:
                if trace_enabled:
                    branch_status[branch_name] = {
                        "configured": True,
                        "fired": False,
                        "skip_reason": "unsupported_vector_field",
                    }
                continue
            # On pivot turns the anchor set is intentionally cleared (the user
            # changed direction), so an anchor-sourced centroid would be stale
            # — skip it. Exception (issue #74 Fix 1): when similar-artist
            # anchoring is on AND the turn resolved reference artists, we DO
            # want the centroid (it points at "tracks like X"), so bypass the
            # pivot-skip in that case only.
            if (
                cb.centroid_source == "anchor_tracks"
                and state.intent_mode.value == "pivot"
                and not (
                    self.cfg.enable_similar_artist_anchors
                    and self._similar_artist_anchor_track_ids(rs)
                )
            ):
                if trace_enabled:
                    branch_status[branch_name] = {
                        "configured": True,
                        "fired": False,
                        "skip_reason": "pivot_skip",
                    }
                continue
            centroid = self._centroid_for_branch(rs, user_id, cb)
            if centroid is None:
                if trace_enabled:
                    if cb.centroid_source == "anchor_tracks":
                        skip_reason = (
                            "no_anchors"
                            if not source_track_ids
                            else "missing_embedding"
                        )
                    elif cb.centroid_source == "user":
                        skip_reason = (
                            "missing_user_id"
                            if user_id is None
                            else "missing_user_vector"
                        )
                    else:
                        skip_reason = "no_query"
                    branch_status[branch_name] = {
                        "configured": True,
                        "fired": False,
                        "skip_reason": skip_reason,
                    }
                continue
            hits = self.retriever.search_embedding(
                query_vector=centroid,
                vector_field=cb.vector_field,
                topk=cb.topk,
                distance_type=cb.distance_type,
            )
            kind = ("centroid.image" if "image" in cb.vector_field
                    else "centroid.audio" if "audio" in cb.vector_field
                    else "centroid.other")
            centroid_branch_results.append(
                (hits, cb.weight * self._routing_multiplier(kind, rs))
            )
            if trace_enabled:
                branch_status[branch_name] = {
                    "configured": True,
                    "fired": True,
                    "n_raw_hits": len(hits),
                }
                named_pools.append((
                    branch_name,
                    list(hits[:_trace_k]),
                ))

        # 4. Apply pre-fusion mask (post-hoc until the retriever supports masks)
        bm25_hits = [(t, s) for t, s in bm25_hits if t in candidate_mask]
        dense_branch_results = [
            [(t, s) for t, s in hits if t in candidate_mask]
            for hits in dense_branch_results
        ]
        centroid_branch_results = [
            ([(t, s) for t, s in hits if t in candidate_mask], w)
            for hits, w in centroid_branch_results
        ]

        # 5. Hard-drop set (played + rejections + tf.rejected)
        hard_drop = self._hard_drop_set(rs)
        bm25_hits = [(t, s) for t, s in bm25_hits if t not in hard_drop]
        dense_branch_results = [
            [(t, s) for t, s in hits if t not in hard_drop]
            for hits in dense_branch_results
        ]
        centroid_branch_results = [
            ([(t, s) for t, s in hits if t not in hard_drop], w)
            for hits, w in centroid_branch_results
        ]

        # 5b. Resolved-artist discography pool. Trace the RAW pool (pre-mask/
        # hard-drop) to match bm25/dense/centroid trace semantics, then filter
        # for fusion.
        disco_branch_name = "lookup.resolved_artist_discography"
        if trace_enabled and self.cfg.enable_resolved_artist_discography:
            branch_queries[disco_branch_name] = self._discography_query_trace(rs)
        disco_hits = self._resolved_artist_discography_pool(rs)
        if trace_enabled and self.cfg.enable_resolved_artist_discography:
            if disco_hits:
                branch_status[disco_branch_name] = {
                    "configured": True,
                    "fired": True,
                    "n_raw_hits": len(disco_hits),
                }
            else:
                reason = (
                    "gated_by_intent"
                    if rs.state.intent_mode.value in self.cfg.disco_gated_intents
                    else "no_query"
                )
                branch_status[disco_branch_name] = {
                    "configured": True,
                    "fired": False,
                    "skip_reason": reason,
                }
        if trace_enabled and disco_hits:
            named_pools.append((
                disco_branch_name,
                list(disco_hits[:_trace_k]),
            ))
        disco_hits = [
            (t, s) for t, s in disco_hits if t in candidate_mask and t not in hard_drop
        ]

        # 6. Weighted RRF fusion (compiler-owned, cross-modal). Each pool's
        # weight is scaled by its routing multiplier so active routing_tags
        # up-weight the matching branches (1.0 for unmapped/inert kinds).
        weighted_pools: list[tuple[list[tuple[str, float]], float]] = [
            (bm25_hits, 1.0 * self._routing_multiplier("bm25", rs))
        ]
        for hits, branch in zip(dense_branch_results, self.cfg.dense_branches):
            if branch.query_id == "lyric":
                kind = "dense.lyric"
            elif "metadata" in branch.vector_field:
                kind = "dense.metadata"
            else:
                kind = "dense.other"
            weighted_pools.append((hits, branch.weight * self._routing_multiplier(kind, rs)))
        for hits, weight in centroid_branch_results:
            if hits:
                weighted_pools.append((hits, weight))
        if disco_hits:
            weighted_pools.append(
                (disco_hits, self.cfg.disco_weight * self._routing_multiplier("lookup.discography", rs))
            )
        era_hits = self._era_popularity_pool(rs)
        era_branch_name = "lookup.era_popularity"
        if trace_enabled and self.cfg.enable_era_popularity:
            branch_queries[era_branch_name] = self._era_popularity_query_trace(rs)
            if era_hits:
                branch_status[era_branch_name] = {
                    "configured": True,
                    "fired": True,
                    "n_raw_hits": len(era_hits),
                }
            else:
                branch_status[era_branch_name] = {
                    "configured": True,
                    "fired": False,
                    "skip_reason": "no_query",
                }
        if trace_enabled and era_hits:
            named_pools.append((era_branch_name, list(era_hits[:_trace_k])))
        candidate_filter_summary = (
            self._candidate_filter_summary(named_pools, candidate_mask, hard_drop, rs)
            if trace_enabled
            else {}
        )
        era_hits = [
            (t, s) for t, s in era_hits if t in candidate_mask and t not in hard_drop
        ]
        if era_hits:
            weighted_pools.append(
                (era_hits, self.cfg.era_pop_weight * self._routing_multiplier("lookup.era_popularity", rs))
            )
        fused = self._rrf_fuse_weighted(weighted_pools, k=self.cfg.rrf_k)

        # 7. Soft (de)promotes
        adjusted = self._apply_soft_adjustments(fused, rs)

        # 8. Backfill to topk (popularity-sorted, mask + hard-drop-respecting)
        ranked = [tid for tid, _ in adjusted]
        n_from_fusion = min(len(ranked), self.cfg.final_topk)
        if len(ranked) < self.cfg.final_topk:
            ranked = self._backfill(ranked, candidate_mask, hard_drop)
        ranked = ranked[: self.cfg.final_topk]
        n_from_backfill = len(ranked) - n_from_fusion

        return CompileResult(
            ranked=ranked,
            branch_pools=[BranchPool(name=n, hits=h) for n, h in named_pools],
            fused=fused[: self.cfg.final_topk] if _trace_k else [],
            n_from_fusion=n_from_fusion,
            n_from_backfill=n_from_backfill,
            depth=_trace_k,
            branch_queries=branch_queries,
            branch_status=branch_status,
            candidate_filter_summary=candidate_filter_summary,
        )

    # ------------------------------------------------------------------
    # Query construction
    # ------------------------------------------------------------------

    @staticmethod
    def _field_query_to_trace(clause: FieldQuery) -> dict:
        return {
            "field": clause.field,
            "query": clause.query,
            "boost": float(clause.boost),
        }

    @staticmethod
    def _dense_branch_trace_name(branch: DenseBranch) -> str:
        return f"dense.{branch.encoder_id}.{branch.query_id}.{branch.vector_field}"

    @staticmethod
    def _centroid_branch_trace_name(branch: CentroidOnlyBranch) -> str:
        return f"centroid.{branch.centroid_source}.{branch.vector_field}"

    @staticmethod
    def _dense_branch_query_trace(branch: DenseBranch) -> dict:
        return {
            "kind": "dense",
            "query_id": branch.query_id,
            "encoder_id": branch.encoder_id,
            "vector_field": branch.vector_field,
            "distance_type": branch.distance_type,
            "weight": float(branch.weight),
        }

    def _centroid_source_track_ids(self, rs: ResolvedConversationState) -> list[str]:
        """Track ids that will be used to build an anchor-sourced centroid.

        Mirrors `_anchor_centroid_for_field`: played/reference anchors first,
        then optional similar-artist anchor tracks. This trace helper returns
        ids only; it never serializes vectors.
        """
        ids = list(self._anchor_track_ids(rs.state))
        seen = set(ids)
        for tid in self._similar_artist_anchor_track_ids(rs):
            if tid not in seen:
                seen.add(tid)
                ids.append(tid)
        return ids

    def _discography_query_trace(self, rs: ResolvedConversationState) -> dict:
        targets = [
            {
                "source_text": t.source_text,
                "entity_id": t.entity_id,
                "confidence": float(t.confidence),
                "resolution_role": getattr(t, "resolution_role", "exact_target"),
            }
            for t in rs.resolved_targets
            if t.kind == "artist"
            and getattr(t, "resolution_role", "exact_target") == "exact_target"
        ]
        return {
            "kind": "lookup",
            "lookup_type": "resolved_artist_discography",
            "confidence_threshold": float(self.cfg.disco_confidence_threshold),
            "targets": targets,
        }

    @staticmethod
    def _era_popularity_query_trace(rs: ResolvedConversationState) -> dict:
        ryr = rs.state.release_year_range
        return {
            "kind": "lookup",
            "lookup_type": "era_popularity",
            "release_year_range": (
                None
                if ryr is None
                else {"start": ryr.start, "end": ryr.end}
            ),
        }

    def _resolved_rejection_drop_set(
        self,
        rs: ResolvedConversationState,
    ) -> set[str]:
        """Tracks dropped by resolved explicit rejections.

        Expand both track_ids and artist_ids for every resolved rejection,
        regardless of `er.kind`. The resolver may attach owning-artist ids to
        a kind="track" rejection (and vice versa); honoring only one side lets
        backfill silently re-admit tracks that soft adjustments excluded.
        """
        drop: set[str] = set()
        for rej in rs.resolved_rejections.values():
            drop.update(rej.track_ids)
            for aid in rej.artist_ids:
                drop.update(self.catalog.tracks_by_artist_id(aid))
        return drop

    def _candidate_filter_summary(
        self,
        named_pools: list[tuple[str, list[tuple[str, float]]]],
        candidate_mask: set[str],
        hard_drop: set[str],
        rs: ResolvedConversationState,
    ) -> dict[str, int]:
        """Compact filter counts over the traced top-k branch pools.

        `named_pools` has already been bounded by `branch_trace_topk`; this is
        a summary of what the trace carries, not the full fusion candidate set.
        """
        raw_union = {
            track_id
            for _name, hits in named_pools
            for track_id, _score in hits
        }
        after_mask = raw_union & candidate_mask
        played = set(rs.played_track_ids)
        explicit_rejections = self._resolved_rejection_drop_set(rs)
        played_dropped = after_mask & played
        explicit_dropped = (after_mask - played_dropped) & explicit_rejections
        other_hard_dropped = (
            after_mask - played_dropped - explicit_dropped
        ) & hard_drop
        return {
            "raw_union_size": len(raw_union),
            "eligible_union_size": len(after_mask - hard_drop),
            "release_date_mask_dropped": len(raw_union - candidate_mask),
            "played_track_dropped": len(played_dropped),
            "explicit_rejection_dropped": len(explicit_dropped),
            "other_hard_drop_dropped": len(other_hard_dropped),
        }

    def _build_bm25_clauses(self, rs: ResolvedConversationState) -> list[FieldQuery]:
        """Build the Solr-style multi-field BM25 query. Blank-query clauses are
        dropped by the retriever; we keep the structure predictable here."""
        state = rs.state
        per_field: dict[str, list[str]] = {}

        for me in state.mentioned_entities:
            if me.sentiment < 0:
                continue
            target = {
                "artist": "artist_name",
                "album": "album_name",
                "track": "track_name",
                "tag": "tag_list",
            }.get(me.type)
            if target is None:
                continue
            per_field.setdefault(target, []).append(me.value)

        # Anchor tag expansion → tag_list (skip on pivot — anchors are gone)
        if state.intent_mode.value != "pivot":
            anchor_tags = self._top_anchor_tags(rs, n=self.cfg.anchor_tag_expansion_n)
            if anchor_tags:
                per_field.setdefault("tag_list", []).extend(anchor_tags)

        release_range = state.release_year_range
        if release_range is not None:
            supported_text_fields = getattr(
                self.retriever,
                "supported_text_fields",
                frozenset(DEFAULT_FIELD_BOOSTS),
            )
            year_boost = self.cfg.field_boosts.get("release_year", 0.0)
            decade_boost = self.cfg.field_boosts.get("release_decade", 0.0)
            exact_year = (
                release_range.start is not None
                and release_range.end is not None
                and release_range.start == release_range.end
            )
            if (exact_year and year_boost > 0.0) or (not exact_year and decade_boost > 0.0):
                for field_name, term in self._release_year_range_bm25_terms(state):
                    if (
                        field_name in supported_text_fields
                        and self.cfg.field_boosts.get(field_name, 0.0) > 0.0
                    ):
                        per_field.setdefault(field_name, []).append(term)

        # turn_intent: free text routed where mood/title vocabulary fits.
        # Avoid artist_name (prevents "Beat" verb → "Beatles" false pos) and
        # album_name (rarely contains mood/era words).
        intent = state.turn_intent.strip()
        if intent:
            per_field.setdefault("track_name", []).append(intent)
            per_field.setdefault("tag_list", []).append(intent)

        # Emit one FieldQuery per term so each entity contributes a separate
        # MatchQuery to tantivy's Boolean SHOULD. Joining all terms into a
        # single space-joined query biases BM25 toward documents that happen
        # to match more tokens of a multi-word entity name regardless of user
        # intent (e.g. "Rolling Stones" out-scores "Beatles" purely on
        # token-count grounds).
        return [
            FieldQuery(
                field=field_name,
                query=term.strip(),
                boost=self.cfg.field_boosts.get(field_name, 1.0),
            )
            for field_name, terms in per_field.items()
            for term in terms
            if term.strip()
        ]

    def _release_year_range_bm25_terms(
        self,
        state: ConversationStateV0Plus,
    ) -> list[tuple[str, str]]:
        """Map soft year hints to coarse FTS clauses.

        Exact closed ranges emit one `release_year` token. All wider closed or
        open-ended ranges emit one `release_decade` token per overlapped decade.
        Open-ended ranges are clamped to the catalog's observed min/max release
        year. Ranges with no catalog-year overlap emit no FTS clauses; the
        post-fusion `release_year_range` feature still handles their soft score.
        """
        release_range = state.release_year_range
        if release_range is None:
            return []

        start = release_range.start
        end = release_range.end
        if start is not None and end is not None and start == end:
            return [("release_year", str(start))]

        if start is None or end is None:
            catalog_bounds = self._catalog_release_year_bounds()
            if catalog_bounds is None:
                return []
            min_year, max_year = catalog_bounds
            start = min_year if start is None else start
            end = max_year if end is None else end

        if start is None or end is None or start > end:
            return []

        start_decade = (start // 10) * 10
        end_decade = (end // 10) * 10
        return [
            ("release_decade", f"{decade}s")
            for decade in range(start_decade, end_decade + 10, 10)
        ]

    def _catalog_release_year_bounds(self) -> tuple[int, int] | None:
        if self._catalog_release_year_bounds_cached:
            return self._catalog_release_year_bounds_cache

        years = [
            year
            for track_id in self.catalog.all_track_ids()
            if (year := self.catalog.release_year_of(track_id)) is not None
        ]
        if not years:
            self._catalog_release_year_bounds_cache = None
        else:
            self._catalog_release_year_bounds_cache = (min(years), max(years))
        self._catalog_release_year_bounds_cached = True
        return self._catalog_release_year_bounds_cache

    # -- Dense query templates --------------------------------------------
    # Each builder takes the resolved state and returns a query STRING (or
    # None to skip the branch). Branches reference templates by `query_id`.
    # New `query_id`s are added by writing a `_build_<name>_query_string`
    # method and registering it in `_query_builders` below.

    @staticmethod
    def _positive_mention_values(
        state: ConversationStateV0Plus,
        entity_type: str,
    ) -> list[str]:
        return [
            me.value
            for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == entity_type and me.value
        ]

    @staticmethod
    def _style_reference_values(
        state: ConversationStateV0Plus,
        entity_type: str,
    ) -> list[str]:
        return [
            me.value
            for me in state.style_reference_entities
            if me.sentiment >= 0 and me.type == entity_type and me.value
        ]

    @classmethod
    def _artist_reference_values(cls, state: ConversationStateV0Plus) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for value in (
            cls._positive_mention_values(state, "artist")
            + cls._style_reference_values(state, "artist")
        ):
            key = value.casefold().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(value)
        return out

    def _build_dense_query_string(self, rs: ResolvedConversationState) -> str | None:
        """`query_id="intent"` — canonical Qwen3/BM25-shaped query string.

        Joins turn_intent + positive artist mentions + positive tags. Matches
        the literal surface forms in the catalog's metadata column and the
        qwen3 text encoder's natural language. Used by qwen3 dense branches
        when present; default for any branch that doesn't override `query_id`.
        """
        state = rs.state
        text_parts: list[str] = []
        if state.turn_intent.strip():
            text_parts.append(state.turn_intent.strip())

        artists = self._artist_reference_values(state)
        tags = self._positive_mention_values(state, "tag")
        if artists:
            text_parts.append("like: " + ", ".join(artists))
        if tags:
            text_parts.append("tags: " + ", ".join(tags))

        if not text_parts:
            return None
        return "; ".join(text_parts)

    def _build_metadata_query_string(self, rs: ResolvedConversationState) -> str | None:
        """`query_id="metadata"` — metadata-column query string.

        Matches catalog metadata documents (track title, artist, album) while
        keeping explicit extracted tags out of this branch. Tags stay in the
        attributes branch, whose item documents are tag-list based.
        """
        state = rs.state
        text_parts: list[str] = []
        if state.turn_intent.strip():
            text_parts.append(state.turn_intent.strip())

        artists = self._positive_mention_values(state, "artist")
        albums = self._positive_mention_values(state, "album")
        tracks = self._positive_mention_values(state, "track")
        if artists:
            text_parts.append("artists: " + ", ".join(artists))
        if albums:
            text_parts.append("albums: " + ", ".join(albums))
        if tracks:
            text_parts.append("tracks: " + ", ".join(tracks))

        if not text_parts:
            return None
        return "; ".join(text_parts)

    def _build_sonic_query_string(self, rs: ResolvedConversationState) -> str | None:
        """`query_id="sonic"` — CLAP-music-shaped query string.

        CLAP music was trained on (audio, caption) pairs over music + AudioSet,
        so its text encoder aligns best with sonic/musical descriptors:
        genre, mood, instrumentation, vocal style, era. Artist names and
        narrative themes ("overcoming struggles") do NOT align with audio
        features.

        Template:
          - Positive tag mentions joined as comma list (genre/mood/instrument).
          - If positive tags are present, prepend any sonic-style turn_intent
            text for richer description; otherwise fall back to turn_intent
            alone so the branch still fires when extraction is tag-poor.
        """
        state = rs.state
        tags = self._positive_mention_values(state, "tag")
        intent = state.turn_intent.strip()
        if tags:
            joined_tags = ", ".join(tags)
            # Keep turn_intent too — it often contains sonic descriptors
            # ("intense", "high-energy") that aren't captured as discrete
            # tag mentions. Artist names within it are accepted noise.
            return f"music: {joined_tags}" + (f"; {intent}" if intent else "")
        if intent:
            return f"music: {intent}"
        return None

    def _build_visual_query_string(self, rs: ResolvedConversationState) -> str | None:
        """`query_id="visual"` — SigLIP-2-shaped query string.

        SigLIP-2's text branch was trained on (image, caption) pairs from
        the general web. It aligns best with visual descriptions. For music
        retrieval over cover-art embeddings, the most useful framing is
        "album cover, <genre/era/mood>" — pushes the encoder toward the
        cover-art subspace of its training distribution rather than
        generic photographic content.

        Template:
          - "album cover, {positive_tags}" when tags are present.
          - Falls back to "album cover, {turn_intent}" otherwise.
        """
        state = rs.state
        tags = self._positive_mention_values(state, "tag")
        if tags:
            return "album cover, " + ", ".join(tags)
        intent = state.turn_intent.strip()
        if intent:
            return f"album cover, {intent}"
        return None

    def _build_sonic_nl_query_string(self, rs: ResolvedConversationState) -> str | None:
        """`query_id="sonic_nl"` — natural-language sonic description for CLAP.

        Round 3 query for CLAP music's text-side encoder. Phase B measured
        this template on 499 novel-artist turns and saw +120% CLAP Hit@20
        and +14% CLAP Hit@1000 vs the Round 2 `sonic` template, including
        recovering 14% of the previously "unreachable" A4 bucket.

        CLAP music was trained on (audio, caption) pairs where captions are
        full-sentence music descriptions ("A song with distorted electric
        guitars and aggressive vocals"). This template builds a sentence
        from the state's tag list and positive artist references, which
        matches that training distribution more closely than the Round 2
        "music: {tags}; {turn_intent}" comma-list template.

        Template:
          - "A song with {tags} sound, similar to {artists}"
          - Falls back to turn_intent alone when both tags and artists
            are empty (preserves any signal at all).
        """
        state = rs.state
        tags = self._positive_mention_values(state, "tag")
        artists = self._artist_reference_values(state)
        parts: list[str] = []
        if tags:
            parts.append(f"A song with {', '.join(tags)} sound")
        if artists:
            parts.append(f"similar to {', '.join(artists)}")
        if parts:
            return ", ".join(parts)
        intent = state.turn_intent.strip()
        return intent or None

    # Lexicon for detecting turns where the user's intent is at least
    # partly about LYRICS / THEMES / NARRATIVE rather than just sound.
    # Hand-curated from A4 deep-dive samples — kept small and specific so
    # the lyric branch fires only when there's real lyric signal to retrieve.
    _LYRIC_HINT_WORDS = frozenset({
        "lyric", "lyrics", "lyrical", "words", "story", "stories",
        "storytelling", "narrative", "narratives", "theme", "themes",
        "meaning", "meaningful", "message", "introspective", "deep",
        "emotional", "feels", "feelings", "soul", "heart", "heartbreak",
        "loneliness", "struggle", "struggles", "overcoming", "resilience",
        "personal", "journey", "journeys", "reflective", "reflection",
        "melancholic", "melancholy", "longing", "saudade",
    })

    def _build_sonic_nl_enriched_query_string(
        self, rs: ResolvedConversationState
    ) -> str | None:
        """`query_id="sonic_nl_enriched"` — natural-language CLAP query
        enriched with anchor tracks' catalog-canonical tag vocabulary.

        Phase B+v4 (499 novel turns): +11% Hit@1000 on the A3 "text-side
        hero" bucket and +4% on A2 "BM25-deep" turns. Useful complement
        in a multi-query CLAP recall stack — catches turns where the user
        wants "more like the anchors but different artist" by exposing
        the catalog's vocabulary for the anchor tracks' genres.

        Same NL framing as sonic_nl; the difference is that the tag list
        is the UNION of the state's positive tags + top-N anchor-track
        tags (deduped, source-order preserved).
        """
        state = rs.state
        state_tags = self._positive_mention_values(state, "tag")
        artists = self._artist_reference_values(state)
        # Top-N catalog-canonical tags from positive anchors (reuses the
        # same machinery BM25 uses for anchor_tag_expansion).
        anchor_tags = self._top_anchor_tags(rs, n=5)
        # Preserve order, dedup (case-insensitive on the dedup key but
        # keep the original casing in the final query for richer signal).
        seen = set()
        all_tags: list[str] = []
        for t in state_tags + list(anchor_tags):
            key = t.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            all_tags.append(t)
        parts: list[str] = []
        if all_tags:
            parts.append(f"A song with {', '.join(all_tags)} sound")
        if artists:
            parts.append(f"similar to {', '.join(artists)}")
        if parts:
            return ", ".join(parts)
        intent = (state.turn_intent or "").strip()
        return intent or None

    def _build_lyric_query_string(self, rs: ResolvedConversationState) -> str | None:
        """`query_id="lyric"` — matches the catalog's lyrics column, which
        talkpl-ai built as Qwen3 embeddings of `"music lyrics :{pseudo_lyrics}"`
        (talkpl-ai/talkplay-environment::talkenv/dataset/lyrics.py; lyrics are
        pseudo-lyrics from talkpl-ai/spotify_pseudo_lyrics). We mirror that
        document prefix so the query lands in the same subspace. Fires only when
        the extractor emitted `lyrical_theme`; returns None otherwise (the
        compiler appends an empty hit list to keep branch ordering aligned)."""
        theme = (rs.state.lyrical_theme or "").strip()
        if not theme:
            return None
        return f"music lyrics :{theme}"

    def _build_attributes_query_string(self, rs: ResolvedConversationState) -> str | None:
        """`query_id="attributes"` — matches the catalog's attributes column,
        which talkpl-ai built as Qwen3 embeddings of
        `"music attributes, tags :{tags}"` (talkenv/dataset/attributes.py). We
        mirror that document prefix so the query lands in the same subspace.
        Built from positive tag mentions (genre/mood/instrument). Returns None
        when there are no positive tags (branch is skipped on tag-poor turns)."""
        state = rs.state
        tags = [value.strip() for value in self._positive_mention_values(state, "tag")]
        if not tags:
            return None
        return "music attributes, tags :" + ", ".join(tags)

    def _build_attributes_enriched_query_string(
        self, rs: ResolvedConversationState
    ) -> str | None:
        """`query_id="attributes_enriched"` — attributes-column query string
        with current positive tags plus catalog-canonical tags from accepted
        anchor tracks.

        This is the Qwen-attributes analogue of `sonic_nl_enriched`: it keeps
        the document prefix expected by the attributes embedding column, while
        exposing useful anchor-track vocabulary when the state is tag-poor or
        uses a synonym not present in the catalog tag list.
        """
        state = rs.state
        seen: set[str] = set()
        tags: list[str] = []
        for value in self._positive_mention_values(state, "tag") + self._top_anchor_tags(rs, n=5):
            tag = value.strip()
            key = tag.casefold()
            if not tag or key in seen:
                continue
            seen.add(key)
            tags.append(tag)
        if not tags:
            return None
        return "music attributes, tags :" + ", ".join(tags)

    @property
    def _query_builders(self):
        """Registry mapping `query_id` -> builder method.

        Extending Round 2 with a new template requires a new method here
        plus a YAML branch referencing it via `query_id`. No further code
        changes needed.
        """
        return {
            "intent": self._build_dense_query_string,
            "metadata": self._build_metadata_query_string,
            "sonic": self._build_sonic_query_string,
            "visual": self._build_visual_query_string,
            "sonic_nl": self._build_sonic_nl_query_string,
            "sonic_nl_enriched": self._build_sonic_nl_enriched_query_string,
            "lyric": self._build_lyric_query_string,
            "attributes": self._build_attributes_query_string,
            "attributes_enriched": self._build_attributes_enriched_query_string,
        }

    def _mix_for_branch(
        self,
        rs: ResolvedConversationState,
        encoded_query: list[float],
        branch: "DenseBranch",
    ) -> list[float]:
        """Compute the per-branch query vector: encoded query mixed with the
        anchor centroid computed in the BRANCH's vector space."""
        alpha = self.cfg.centroid_alpha.get(rs.state.intent_mode.value, 0.0)
        if alpha <= 0:
            return encoded_query
        centroid = self._anchor_centroid_for_field(rs, branch.vector_field)
        if centroid is None:
            return encoded_query
        return _normalize(_mix(encoded_query, centroid, alpha))

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def _release_date_mask(self, state: ConversationStateV0Plus) -> set[str]:
        """Intersect every release_date hard_filter; if no filters, all tracks
        are valid candidates."""
        all_ids = set(self.catalog.all_track_ids())
        valid = all_ids
        for hf in state.hard_filters:
            if hf.field != "release_date":
                continue
            # Skip non-actionable filters (LLM sometimes emits these — e.g. an
            # `op="between"` with both bounds missing). Without this, the
            # catalog's `release_date_filter_mask` returns `set()` for the
            # malformed filter and we'd intersect the entire candidate pool
            # away. Treat them as no-ops — the rest of the state still drives
            # retrieval.
            if hf.op == "<" and hf.end is None:
                continue
            if hf.op == ">" and hf.start is None:
                continue
            if hf.op == "between" and (hf.start is None or hf.end is None):
                continue
            try:
                step_mask = self.catalog.release_date_filter_mask(hf)
            except Exception:
                # Permissive: a broken filter doesn't blank the result
                continue
            valid = valid & step_mask

        return valid

    def _hard_drop_set(self, rs: ResolvedConversationState) -> set[str]:
        state = rs.state
        drop: set[str] = set(rs.played_track_ids)

        for tf in state.track_feedback:
            if tf.role == "rejected":
                drop.add(tf.track_id)

        drop.update(self._resolved_rejection_drop_set(rs))

        return drop

    # ------------------------------------------------------------------
    # Fusion + post-rank
    # ------------------------------------------------------------------

    @staticmethod
    def _rrf_fuse(
        ranked_lists: list[list[tuple[str, float]]],
        k: int,
    ) -> list[tuple[str, float]]:
        """Uniform-weight RRF over N pools (legacy two-branch helper)."""
        return V0PlusCompiler._rrf_fuse_weighted(
            [(ranked, 1.0) for ranked in ranked_lists], k=k
        )

    @staticmethod
    def _rrf_fuse_weighted(
        weighted_pools: list[tuple[list[tuple[str, float]], float]],
        k: int,
    ) -> list[tuple[str, float]]:
        """Weighted RRF over N pools. Each pool is (list[(id, score)], weight).
        Per-clause RRF contribution is `weight / (k + rank)`."""
        scores: dict[str, float] = {}
        first_seen: dict[str, int] = {}
        order = 0
        for ranked, weight in weighted_pools:
            for rank, (tid, _score) in enumerate(ranked, start=1):
                if tid not in first_seen:
                    first_seen[tid] = order
                    order += 1
                scores[tid] = scores.get(tid, 0.0) + float(weight) / (k + rank)
        ranked_ids = sorted(
            scores, key=lambda t: (-scores[t], first_seen[t])
        )
        return [(tid, scores[tid]) for tid in ranked_ids]

    def _apply_soft_adjustments(
        self,
        fused: list[tuple[str, float]],
        rs: ResolvedConversationState,
    ) -> list[tuple[str, float]]:
        """Post-fusion rerank — delegates to `PostFusionReranker` with the
        two-feature config (UserFeedback + SessionAnchor). Existing knobs
        (`rejected_tag_multiplier`, `positive_tag_multiplier_step`,
        `same_artist_demote`) are threaded through to feature multipliers,
        so this is behavior-preserving when `exploration_policy=balanced`
        (the default).

        Adds: policy-driven anchor-artist demote when the LLM extracts
        `exploration_policy=diversify_artists` on a turn. See
        `post_fusion_features.ANCHOR_ARTIST_DEMOTE_BY_POLICY`.
        """
        from mcrs.qu_modules.post_fusion_features import (
            PostFusionReranker,
            build_features_for_state,
        )

        features = build_features_for_state(
            rs,
            self.catalog,
            tag_rejection_per_overlap=self.cfg.rejected_tag_multiplier,
            positive_tag_per_overlap=1.0 + self.cfg.positive_tag_multiplier_step,
            inferred_artist_rejection_mult=self.cfg.same_artist_demote,
        )
        reranker = PostFusionReranker(features=features)
        return reranker.rerank(fused, self.catalog)

    # ------------------------------------------------------------------
    # Backfill
    # ------------------------------------------------------------------

    # branch-kind -> the routing_tags that boost it
    _ROUTING_MAP: dict[str, tuple[str, ...]] = {
        "bm25": ("exact_entity_probe",),
        "lookup.discography": ("exact_entity_probe",),
        "dense.lyric": ("lyric_search",),
        "dense.metadata": ("feature_articulation",),
        "centroid.audio": ("feature_articulation",),
        "centroid.image": ("image_or_visual_search",),
    }

    def _routing_multiplier(self, branch_kind: str, rs: ResolvedConversationState) -> float:
        """Product of configured routing_boost values for the routing_tags that
        are active on this turn AND boost `branch_kind`. 1.0 when unconfigured or
        for unmapped branch kinds (e.g. 'dense.other')."""
        tags = rs.state.routing_tags
        mult = 1.0
        for tag in self._ROUTING_MAP.get(branch_kind, ()):
            if getattr(tags, tag, False):
                mult *= float(self.cfg.routing_boost.get(tag, 1.0))
        return mult

    def _popularity_rank(self) -> dict[str, int]:
        """track_id -> global popularity rank (0 = most popular). Built once."""
        if self._pop_rank is None:
            self._pop_rank = {
                tid: i for i, tid in enumerate(self.catalog.popularity_sorted_track_ids())
            }
        return self._pop_rank

    def _resolved_artist_discography_pool(
        self, rs: ResolvedConversationState
    ) -> list[tuple[str, float]]:
        """Popularity-ordered, capped catalog tracks for each high-confidence
        resolved artist. Returns a ranked (track_id, score) pool for RRF, or []
        when disabled / gated / nothing qualifies. No protected slots — this
        competes in RRF like any other branch."""
        cfg = self.cfg
        if not cfg.enable_resolved_artist_discography:
            return []
        if rs.state.intent_mode.value in cfg.disco_gated_intents:
            return []
        artist_ids: list[str] = []
        seen_artists: set[str] = set()
        for tgt in rs.resolved_targets:
            if (
                tgt.kind == "artist"
                and getattr(tgt, "resolution_role", "exact_target") == "exact_target"
                and tgt.entity_id is not None
                and tgt.confidence >= cfg.disco_confidence_threshold
                and tgt.entity_id not in seen_artists
            ):
                seen_artists.add(tgt.entity_id)
                artist_ids.append(tgt.entity_id)
        if not artist_ids:
            return []
        pop_rank = self._popularity_rank()
        sentinel = len(pop_rank)
        track_ids: list[str] = []
        seen_tracks: set[str] = set()
        for aid in artist_ids:
            ranked = sorted(
                self.catalog.tracks_by_artist_id(aid),
                key=lambda t: pop_rank.get(t, sentinel),
            )[: cfg.disco_cap]
            for t in ranked:
                if t not in seen_tracks:
                    seen_tracks.add(t)
                    track_ids.append(t)
        n = len(track_ids)
        return [(t, float(n - i)) for i, t in enumerate(track_ids)]

    def _era_popularity_pool(
        self, rs: ResolvedConversationState
    ) -> list[tuple[str, float]]:
        """Popularity-ordered catalog tracks whose release year falls in the
        extracted `release_year_range`. Returns a ranked (track_id, score) pool
        for RRF, or [] when disabled or no usable year range. Open-ended bounds
        allowed (start or end may be None). Targets canonical era classics that
        content/CF branches miss; competes in RRF like any other branch."""
        cfg = self.cfg
        if not cfg.enable_era_popularity:
            return []
        ryr = rs.state.release_year_range
        if ryr is None:
            return []
        start, end = ryr.start, ryr.end
        if start is None and end is None:
            return []
        lo = start if start is not None else -(10**9)
        hi = end if end is not None else 10**9
        track_ids: list[str] = []
        for tid in self.catalog.popularity_sorted_track_ids():
            yr = self.catalog.release_year_of(tid)
            if yr is None or yr < lo or yr > hi:
                continue
            track_ids.append(tid)
            if len(track_ids) >= cfg.era_pop_cap:
                break
        n = len(track_ids)
        return [(t, float(n - i)) for i, t in enumerate(track_ids)]

    def _similar_artist_anchor_track_ids(self, rs) -> list[str]:
        """Representative tracks of each RESOLVED reference artist, used as
        ADDITIONAL vector-centroid anchors (issue #74 Fix 1).

        Mirrors the disco pool's artist collection: takes resolved artist
        targets with confidence >= similar_artist_confidence_threshold,
        dedupes by entity_id, caps the number of artists at
        similar_artist_max_artists, then for each artist takes the top
        similar_artist_anchor_topk catalog tracks ordered by popularity.
        Returns a flat, deduped list. Returns [] when the feature is off or
        no artist qualifies (so the baseline is unchanged)."""
        cfg = self.cfg
        if not cfg.enable_similar_artist_anchors:
            return []
        # Intent gate: only inject when the named artist is the retrieval target
        # this turn (exact-entity probe) or the turn is in the allowed intent set
        # (open_explore / pivot). On refinement / playlist_build the artist is a
        # "more like X but different" comparison, where injecting X's own tracks
        # dilutes the centroid and hurts coverage — so skip it there.
        state = rs.state
        eep = bool(
            cfg.similar_artist_anchor_on_exact_entity
            and getattr(state.routing_tags, "exact_entity_probe", False)
        )
        intent_ok = state.intent_mode.value in cfg.similar_artist_anchor_intents
        if not (eep or intent_ok):
            return []
        artist_ids: list[str] = []
        seen_artists: set[str] = set()
        for tgt in rs.resolved_targets:
            if (
                tgt.kind == "artist"
                and getattr(tgt, "resolution_role", "exact_target")
                in {"exact_target", "style_reference"}
                and tgt.entity_id is not None
                and tgt.confidence >= cfg.similar_artist_confidence_threshold
                and tgt.entity_id not in seen_artists
            ):
                seen_artists.add(tgt.entity_id)
                artist_ids.append(tgt.entity_id)
                if len(artist_ids) >= cfg.similar_artist_max_artists:
                    break
        if not artist_ids:
            return []
        pop_rank = self._popularity_rank()
        sentinel = len(pop_rank)
        track_ids: list[str] = []
        seen_tracks: set[str] = set()
        for aid in artist_ids:
            ranked = sorted(
                self.catalog.tracks_by_artist_id(aid),
                key=lambda t: pop_rank.get(t, sentinel),
            )[: cfg.similar_artist_anchor_topk]
            for t in ranked:
                if t not in seen_tracks:
                    seen_tracks.add(t)
                    track_ids.append(t)
        return track_ids

    def _backfill(
        self,
        ranked: list[str],
        candidate_mask: set[str],
        hard_drop: set[str],
    ) -> list[str]:
        """Pad the ranked list to final_topk with popularity-sorted track_ids,
        respecting both the release-date mask and the hard-drop set."""
        seen = set(ranked)
        for tid in self.catalog.popularity_sorted_track_ids():
            if len(ranked) >= self.cfg.final_topk:
                break
            if tid in seen or tid in hard_drop or tid not in candidate_mask:
                continue
            ranked.append(tid)
            seen.add(tid)
        return ranked

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _centroid_for_branch(
        self,
        rs: ResolvedConversationState,
        user_id: str | None,
        cb: CentroidOnlyBranch,
    ) -> list[float] | None:
        """Dispatch on centroid_source. Returns None when the branch should
        be skipped (no anchors / no user_id / user has no vector in this
        field / user-embeddings catalog not configured)."""
        if cb.centroid_source == "anchor_tracks":
            return self._anchor_centroid_for_field(rs, cb.vector_field)
        if cb.centroid_source == "user":
            if user_id is None or self.user_embeddings is None:
                return None
            vec = self.user_embeddings.vector(user_id, cb.vector_field)
            if vec is None or not vec:
                return None
            return _normalize(list(vec))
        # Unknown source — fail silently to skip rather than crash inference.
        return None

    def _resolve_centroid_only_branches(self) -> list[CentroidOnlyBranch]:
        """Either an explicit `centroid_only_branches` list or — for back-compat
        with the older `enable_cf_bpr` knobs — a 1-entry synthesized list. If
        both are empty/false, returns []."""
        if self.cfg.centroid_only_branches:
            return list(self.cfg.centroid_only_branches)
        if self.cfg.enable_cf_bpr:
            return [
                CentroidOnlyBranch(
                    vector_field=self.cfg.cf_bpr_vector_field,
                    weight=self.cfg.cf_bpr_weight,
                    topk=self.cfg.cf_bpr_topk,
                    distance_type=self.cfg.cf_bpr_distance_type,
                )
            ]
        return []

    def _anchor_track_ids(
        self, state: ConversationStateV0Plus
    ) -> list[str]:
        """Tracks that count as positive anchors for centroid / tag expansion."""
        ids: list[str] = []
        for tf in state.track_feedback:
            if tf.role in ("accepted", "seed", "satisfied") and tf.overall_sentiment > 0:
                ids.append(tf.track_id)
        ids.extend(state.referenced_track_ids)
        # Dedupe, preserve order
        seen: set[str] = set()
        out: list[str] = []
        for tid in ids:
            if tid not in seen:
                seen.add(tid)
                out.append(tid)
        return out

    def _top_anchor_tags(
        self, rs: ResolvedConversationState, n: int
    ) -> list[str]:
        anchor_ids = self._anchor_track_ids(rs.state)
        if not anchor_ids:
            return []
        counter: Counter[str] = Counter()
        for tid in anchor_ids:
            counter.update(t.lower() for t in self.catalog.tag_list(tid))
        return [tag for tag, _ in counter.most_common(n)]

    def _anchor_centroid(
        self, rs: ResolvedConversationState
    ) -> list[float] | None:
        """Back-compat: metadata-field centroid via the convenience wrapper."""
        return self._anchor_centroid_for_field(rs, "metadata_qwen3_embedding_0_6b")

    def _anchor_centroid_for_field(
        self,
        rs: ResolvedConversationState,
        vector_field: str,
    ) -> list[float] | None:
        """Mean of accepted-anchor track vectors in the given field's space.
        Returns None when no anchor track has a non-empty vector for this
        field (common for `lyrics_qwen3` since coverage is sparse).

        The anchor set is the played/accepted/referenced anchors PLUS, when
        similar-artist anchoring is enabled AND the intent gate allows it (see
        `_similar_artist_anchor_track_ids`), a few representative tracks of each
        resolved reference artist (deduped, played-anchor-first). The
        similar-artist anchors are vector-centroid-only — tag expansion stays
        on played anchors (see `_top_anchor_tags`)."""
        anchor_ids = list(self._anchor_track_ids(rs.state))
        seen = set(anchor_ids)
        for tid in self._similar_artist_anchor_track_ids(rs):
            if tid not in seen:
                seen.add(tid)
                anchor_ids.append(tid)
        vectors: list[list[float]] = []
        for tid in anchor_ids:
            vec = self.catalog.vector(tid, vector_field)
            if vec is not None and vec:
                vectors.append(vec)
        if not vectors:
            return None
        dim = len(vectors[0])
        mean = [0.0] * dim
        for vec in vectors:
            for i in range(dim):
                mean[i] += vec[i]
        for i in range(dim):
            mean[i] /= len(vectors)
        return _normalize(mean)


# ----------------------------------------------------------------------
# Pure-python vector ops (small enough that adding numpy would be silly).
# ----------------------------------------------------------------------


def _normalize(vec: list[float]) -> list[float]:
    norm = sum(x * x for x in vec) ** 0.5
    if norm == 0.0:
        return list(vec)
    return [x / norm for x in vec]


def _mix(a: list[float], b: list[float], alpha: float) -> list[float]:
    """Linear interpolation: (1 - alpha) * a + alpha * b. Assumes same dim."""
    return [(1.0 - alpha) * x + alpha * y for x, y in zip(a, b)]
