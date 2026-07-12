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
import time
from collections import Counter
from dataclasses import dataclass, field

# Word-boundary tokenizer for lyric-hint detection. Splits on any
# non-word character so substring matches like `"story" in "history"` or
# `"deep" in "deepfake"` don't accidentally fire the lyric branch.
_LYRIC_TOKEN_RE = re.compile(r"\w+")
_ARTIST_CREDIT_SPLIT_RE = re.compile(
    r"\s*(?:&|,|\b(?:and|with|feat|featuring|ft)\.?\b)\s*",
    re.IGNORECASE,
)

from mcrs.conversation_state.schema import (
    AnchorUse,
    AttributeFacet,
    ConversationStateV0Plus,
    FactRelation,
    FactRole,
    FactType,
)
from mcrs.embeddings.base import EmbeddingClient
from mcrs.qu_modules.resolver import ResolvedConversationState
from mcrs.qu_modules.catalog import CompilerCatalog
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
    # resolved hard-drops (rejections/replays): the online reranker must
    # exclude these from its reordered pool union (branch pools are
    # release-date-masked but NOT hard-drop-filtered)
    hard_drop: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)

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
    # When set, names a `RoutingTags` boolean field; the branch fires ONLY on
    # turns where that flag is True (e.g. "image_or_visual_search"). None (the
    # default) means always-on — the branch fires on every turn as before.
    gated_on: str | None = None


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
    # When set, names a `RoutingTags` boolean field; the branch fires ONLY on
    # turns where that flag is True (mirrors DenseBranch.gated_on). None (the
    # default) means always-on. Used to keep the cover-art (image_siglip2)
    # centroid consistent with its gated dense counterpart so it does not inject
    # visual-space neighbors on non-visual turns.
    gated_on: str | None = None


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

    # Strict new/different-artist policy (#152): hard-drops every track by a
    # blocked artist on pivot/novelty/different-artist turns. Devset audit (2026-06)
    # found it hard-drops the ground-truth track in 47.6% of the turns it fires
    # (8% of all turns; 100% of all GT hard-drops), costing ~0.04 nDCG@20. Active
    # deploy configs set this False. Default stays True to preserve legacy behavior,
    # but new deploy configs SHOULD set it False explicitly.
    enable_strict_artist_policy: bool = True

    # Dense branches — one search_embedding call per entry. Default fans across
    # the three text-derived Qwen3 columns in the talkpl-ai catalog (metadata
    # + attributes + lyrics). The audio/image/CF columns have no natural text
    # query to encode against them, so they aren't reachable via this
    # text-dense mechanism -- they're searched instead via the separate
    # centroid_only_branches mechanism below (query = mean of anchor-track
    # vectors, not encoded text). See docs/architectures/v0plus_retrieval.md
    # section 2 for the full branch-family breakdown.
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
    # a2 (recall recovery): also seed the discography pool from the artists of
    # tracks PLAYED earlier in the session, not just current-turn resolved
    # artists. On continuation turns the user often says "another by them"
    # without naming the artist, so it never gets resolved and its catalog is
    # never fetched — the played GT (a top track of an already-liked artist) is
    # dropped from recall. Folded into the SAME discography branch so the
    # reranker feature schema is unchanged (no retrain). Still subject to
    # disco_gated_intents, so it stays OFF on pivot turns (correct: don't fetch
    # the just-played artist when the user is pivoting away). Default off.
    disco_include_session_artists: bool = False

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

    # Diagnostic A/B switches for V1 fact consumption. Defaults preserve the
    # current served behavior: V1 attribute facts projected as legacy tag
    # mentions are eligible for BM25 `tag_list`, and `turn_intent` still fans
    # out to both track_name and tag_list. Variant configs can route generated
    # attribute phrases to dense attribute retrieval without letting them spam
    # exact lexical tag clauses.
    # Audit 2026-06-12: kind-insensitive rejection expansion hard-dropped whole
    # fuzzy-matched artist discographies (228 GT kills / 8000 turns). Policy:
    #   "expanded"   - legacy: drop track_ids AND every track of artist_ids
    #   "track_only" - drop only the directly-matched track_ids (artist-level
    #                  rejections stay soft; the generator recycles rejected
    #                  artists, so hard-dropping executes correct answers)
    rejection_drop_policy: str = "expanded"
    # Release-date hard filter is wrong on 43% of the turns it fires (48 GT
    # kills). False disables the hard mask (era branches/features still carry
    # the soft signal).
    enable_release_date_hard_filter: bool = True
    # Post-fusion soft adjustments destroyed 20/37 pivot-turn GT hits; allows
    # gating them off on pivot turns.
    soft_adjust_skip_intents: tuple[str, ...] = field(default_factory=tuple)
    # Scrub negated spans ("not X", "no X", "without X") from turn_intent
    # before it joins the BM25 tag clause (negation was inverting into
    # positive tag signal on ~4% of turns).
    scrub_negated_intent_tags: bool = False

    bm25_include_v1_attribute_facets: bool = True
    bm25_include_turn_intent_tag_clause: bool = True
    bm25_v1_attribute_tag_policy: str = "all"
    attribute_query_source: str = "legacy_tags"
    attribute_query_allowed_facets: tuple[str, ...] = field(default_factory=tuple)

    # Tiered tag resolution for the BM25 tag clause (policy "resolved"):
    # attribute phrases that ground to catalog tags emit those tags; phrases
    # that don't resolve keep the raw text (fallback, never worse than "all").
    # The embedding tier needs an offline index (scripts/
    # build_tag_embedding_index.py) plus a query-side encoder; without either,
    # the lexical tiers (exact/alias/substring) still run.
    tag_resolver_embedding_index_path: str = ""
    tag_resolver_encoder_id: str = "qwen_0_6b"
    tag_resolver_embedding_min_score: float = 0.60
    tag_resolver_embedding_topk: int = 3
    tag_resolver_max_tags_per_phrase: int = 3
    tag_resolver_min_track_count: int = 5

    # Optional additive branch-local candidate-quality pass. When enabled, each
    # fired branch can emit a second `.state_features` branch whose order is
    # based on structured state facts plus catalog-derived features. This is a
    # candidate-recall diagnostic/promotable branch, not an LLM prompt change.
    enable_branch_local_feature_rerank: bool = False
    branch_local_feature_rerank_mode: str = "additive"
    branch_local_feature_weight: float = 1.0
    branch_local_feature_score_weight: float = 1.0
    enable_state_feature_selector_branch: bool = False
    state_feature_selector_weight: float = 1.0
    state_feature_selector_score_weight: float = 1.0
    state_feature_selector_grouping: str = "global"
    enable_state_feature_survivor_branch: bool = False
    state_feature_survivor_weight: float = 1.0
    state_feature_survivor_score_weight: float = 1.0
    state_feature_survivor_rank_weight: float = 0.2
    state_feature_survivor_support_weight: float = 0.05
    state_feature_survivor_min_rank: int = 21
    state_feature_survivor_max_rank: int = 120
    state_feature_survivor_min_feature_score: float = 0.0

    def __post_init__(self) -> None:
        # Partial config dicts inherit standard boosts without mutating the
        # caller-owned mapping passed to the dataclass constructor.
        self.field_boosts = {**DEFAULT_FIELD_BOOSTS, **self.field_boosts}
        if self.branch_local_feature_rerank_mode not in {"additive", "in_place"}:
            raise ValueError(
                "branch_local_feature_rerank_mode must be 'additive' or "
                f"'in_place'; got {self.branch_local_feature_rerank_mode!r}"
            )
        if self.state_feature_selector_grouping not in {"global", "family"}:
            raise ValueError(
                "state_feature_selector_grouping must be 'global' or "
                f"'family'; got {self.state_feature_selector_grouping!r}"
            )
        if self.state_feature_survivor_min_rank < 1:
            raise ValueError("state_feature_survivor_min_rank must be >= 1")
        if self.state_feature_survivor_max_rank < self.state_feature_survivor_min_rank:
            raise ValueError(
                "state_feature_survivor_max_rank must be >= "
                "state_feature_survivor_min_rank"
            )


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
        self._catalog_tag_keys_cache: set[str] | None = None
        self._catalog_tag_df_cache: dict[str, int] | None = None
        self._tracks_by_artist_name_key_cache: dict[str, list[str]] | None = None
        self._track_tag_keys_cache: dict[str, set[str]] = {}
        self._track_text_key_cache: dict[str, str] = {}
        self._track_cf_bpr_cache: dict[str, list[float] | None] = {}
        # Optional user-side embeddings lookup. Required only when a config
        # uses `centroid_only_branches` with `centroid_source="user"`. None
        # otherwise, and the user branch is silently skipped.
        self.user_embeddings = user_embeddings
        self._catalog_release_year_bounds_cached = False
        self._catalog_release_year_bounds_cache: tuple[int, int] | None = None
        self._tag_resolver_cache = None
        # phrase -> [(tag, score, tier)] from the latest _build_bm25_clauses
        # call; surfaced for tracing/ranker features.
        self._last_tag_resolutions: dict[str, list[tuple[str, float, str]]] = {}

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
        timings: dict[str, float] = {}
        total_start = time.perf_counter()

        def add_elapsed(key: str, start: float) -> None:
            timings[key] = timings.get(key, 0.0) + (time.perf_counter() - start)

        def replace_named_pool(
            name: str,
            hits: list[tuple[str, float]],
        ) -> None:
            if not trace_enabled:
                return
            traced = list(hits[:_trace_k])
            for idx, (pool_name, _pool_hits) in enumerate(named_pools):
                if pool_name == name:
                    named_pools[idx] = (name, traced)
                    return
            named_pools.append((name, traced))

        # 1. Pre-fusion catalog mask from hard_filters.release_date
        start = time.perf_counter()
        candidate_mask = self._release_date_mask(state)
        add_elapsed("release_date_mask", start)

        # 2. Build queries
        start = time.perf_counter()
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
            # Validate gated_on references a real RoutingTags field. A typo would
            # otherwise silently disable the branch on every turn (getattr
            # default False) — fail loudly at compile time instead, matching how
            # unknown encoder_id / query_id raise.
            routing_fields = set(type(rs.state.routing_tags).model_fields)
            for b in self.cfg.dense_branches:
                if b.gated_on is not None and b.gated_on not in routing_fields:
                    raise KeyError(
                        f"DenseBranch(vector_field={b.vector_field!r}) "
                        f"gated_on={b.gated_on!r} is not a RoutingTags field. "
                        f"Available: {sorted(routing_fields)}"
                    )
        add_elapsed("build_queries", start)

        # 3. Retrieval — 1 BM25 call + 1 search_embedding per enabled dense branch
        start = time.perf_counter()
        bm25_hits = self.retriever.search(bm25_clauses, topk=self.cfg.bm25_k)
        add_elapsed("bm25_search", start)
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
                if branch.gated_on is not None and not getattr(
                    rs.state.routing_tags, branch.gated_on, False
                ):
                    # Branch is gated on a routing flag that is off this turn.
                    # Skip BEFORE encoding: no wasted encode RPC and no
                    # candidates injected into the pool on non-matching turns.
                    # Append empty hits to keep dense_branch_results aligned
                    # with self.cfg.dense_branches for the RRF fusion zip().
                    dense_branch_results.append([])
                    if trace_enabled:
                        branch_status[branch_name] = {
                            "configured": True,
                            "fired": False,
                            "skip_reason": "gated_off",
                        }
                    continue
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
                    start = time.perf_counter()
                    raw = enc.embed_batch([q_text])[0]
                    add_elapsed("dense_encode", start)
                    add_elapsed(f"dense_encode.{branch.encoder_id}.{branch.query_id}", start)
                    encoded_cache[cache_key] = _normalize(raw)
                vec = self._mix_for_branch(rs, encoded_cache[cache_key], branch)
                start = time.perf_counter()
                hits = self.retriever.search_embedding(
                    query_vector=vec,
                    vector_field=branch.vector_field,
                    topk=self.cfg.dense_k,
                    distance_type=branch.distance_type,
                )
                add_elapsed("dense_search", start)
                add_elapsed(f"dense_search.{branch_name}", start)
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
        start = time.perf_counter()
        centroid_branches = self._resolve_centroid_only_branches()
        add_elapsed("centroid_resolve_branches", start)
        centroid_branch_results: list[tuple[list[tuple[str, float]], float, str]] = []
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
            # Routing gate (mirrors the dense-branch gate): when gated_on is set,
            # fire only on turns where that RoutingTags flag is True. Validate the
            # field name first so a typo fails loudly instead of silently
            # disabling the branch on every turn (getattr default False).
            if cb.gated_on is not None:
                routing_fields = type(rs.state.routing_tags).model_fields
                if cb.gated_on not in routing_fields:
                    raise KeyError(
                        f"CentroidOnlyBranch(vector_field={cb.vector_field!r}) "
                        f"gated_on={cb.gated_on!r} is not a RoutingTags field. "
                        f"Available: {sorted(routing_fields)}"
                    )
                if not getattr(rs.state.routing_tags, cb.gated_on, False):
                    if trace_enabled:
                        branch_status[branch_name] = {
                            "configured": True,
                            "fired": False,
                            "skip_reason": "gated_off",
                        }
                    continue
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
            start = time.perf_counter()
            centroid = self._centroid_for_branch(rs, user_id, cb)
            add_elapsed("centroid_build", start)
            add_elapsed(f"centroid_build.{branch_name}", start)
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
            start = time.perf_counter()
            hits = self.retriever.search_embedding(
                query_vector=centroid,
                vector_field=cb.vector_field,
                topk=cb.topk,
                distance_type=cb.distance_type,
            )
            add_elapsed("centroid_search", start)
            add_elapsed(f"centroid_search.{branch_name}", start)
            kind = ("centroid.image" if "image" in cb.vector_field
                    else "centroid.audio" if "audio" in cb.vector_field
                    else "centroid.other")
            centroid_branch_results.append(
                (hits, cb.weight * self._routing_multiplier(kind, rs), branch_name)
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
        start = time.perf_counter()
        bm25_hits = [(t, s) for t, s in bm25_hits if t in candidate_mask]
        dense_branch_results = [
            [(t, s) for t, s in hits if t in candidate_mask]
            for hits in dense_branch_results
        ]
        centroid_branch_results = [
            ([(t, s) for t, s in hits if t in candidate_mask], w, n)
            for hits, w, n in centroid_branch_results
        ]

        # 5. Hard-drop set (played + rejections + tf.rejected)
        hard_drop = self._hard_drop_set(rs)
        artist_policy_drop, artist_policy_trace = self._artist_policy_drop_set(rs)
        effective_hard_drop = hard_drop | artist_policy_drop
        bm25_hits = [(t, s) for t, s in bm25_hits if t not in effective_hard_drop]
        dense_branch_results = [
            [(t, s) for t, s in hits if t not in effective_hard_drop]
            for hits in dense_branch_results
        ]
        centroid_branch_results = [
            ([(t, s) for t, s in hits if t not in effective_hard_drop], w, n)
            for hits, w, n in centroid_branch_results
        ]
        add_elapsed("apply_filters", start)

        # 5b. Resolved-artist discography pool. Trace the RAW pool (pre-mask/
        # hard-drop) to match bm25/dense/centroid trace semantics, then filter
        # for fusion.
        disco_branch_name = "lookup.resolved_artist_discography"
        if trace_enabled and self.cfg.enable_resolved_artist_discography:
            branch_queries[disco_branch_name] = self._discography_query_trace(rs)
        start = time.perf_counter()
        disco_hits = self._resolved_artist_discography_pool(rs)
        add_elapsed("discography_pool", start)
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
            (t, s)
            for t, s in disco_hits
            if t in candidate_mask and t not in effective_hard_drop
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
        feature_branch_inputs: list[tuple[str, list[tuple[str, float]], float]] = [
            ("bm25", bm25_hits, 1.0 * self._routing_multiplier("bm25", rs))
        ]
        for hits, branch in zip(dense_branch_results, self.cfg.dense_branches):
            if branch.query_id == "lyric":
                kind = "dense.lyric"
            elif "metadata" in branch.vector_field:
                kind = "dense.metadata"
            else:
                kind = "dense.other"
            feature_branch_inputs.append(
                (
                    self._dense_branch_trace_name(branch),
                    hits,
                    branch.weight * self._routing_multiplier(kind, rs),
                )
            )
        for hits, weight, branch_name in centroid_branch_results:
            feature_branch_inputs.append((branch_name, hits, weight))

        for hits, weight, _branch_name in centroid_branch_results:
            if hits:
                weighted_pools.append((hits, weight))
        if disco_hits:
            weighted_pools.append(
                (disco_hits, self.cfg.disco_weight * self._routing_multiplier("lookup.discography", rs))
            )
            feature_branch_inputs.append(
                (
                    disco_branch_name,
                    disco_hits,
                    self.cfg.disco_weight * self._routing_multiplier("lookup.discography", rs),
                )
            )
        start = time.perf_counter()
        era_hits = self._era_popularity_pool(rs)
        add_elapsed("era_pool", start)
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
        era_hits = [
            (t, s)
            for t, s in era_hits
            if t in candidate_mask and t not in effective_hard_drop
        ]
        if era_hits:
            weighted_pools.append(
                (era_hits, self.cfg.era_pop_weight * self._routing_multiplier("lookup.era_popularity", rs))
            )
            feature_branch_inputs.append(
                (
                    era_branch_name,
                    era_hits,
                    self.cfg.era_pop_weight * self._routing_multiplier("lookup.era_popularity", rs),
                )
            )

        start = time.perf_counter()
        feature_context = (
            self._branch_local_feature_context(rs)
            if (
                self.cfg.enable_branch_local_feature_rerank
                or self.cfg.enable_state_feature_selector_branch
                or self.cfg.enable_state_feature_survivor_branch
            )
            else None
        )
        add_elapsed("feature_context", start)
        if self.cfg.enable_state_feature_survivor_branch:
            survivor_name = "state_feature_survivor"
            start = time.perf_counter()
            survivor_hits = self._state_feature_survivor_hits(
                rs,
                feature_branch_inputs,
                context=feature_context,
            )
            add_elapsed("feature_survivor", start)
            if trace_enabled:
                branch_queries[survivor_name] = self._state_feature_survivor_query_trace(
                    rs,
                    feature_branch_inputs,
                    context=feature_context,
                    top_hits=survivor_hits,
                )
                if survivor_hits:
                    branch_status[survivor_name] = {
                        "configured": True,
                        "fired": True,
                        "n_raw_hits": len(survivor_hits),
                    }
                    named_pools.append((survivor_name, list(survivor_hits[:_trace_k])))
                else:
                    branch_status[survivor_name] = {
                        "configured": True,
                        "fired": False,
                        "skip_reason": "no_midrank_feature_signal",
                    }
            if survivor_hits:
                weighted_pools.append(
                    (survivor_hits, self.cfg.state_feature_survivor_weight)
                )
        if self.cfg.enable_state_feature_selector_branch:
            for selector_name, source_group, selector_inputs in (
                self._state_feature_selector_branch_inputs(feature_branch_inputs)
            ):
                start = time.perf_counter()
                selector_hits = self._state_feature_selector_hits(
                    rs,
                    selector_inputs,
                    context=feature_context,
                )
                add_elapsed("feature_selector", start)
                add_elapsed(f"feature_selector.{selector_name}", start)
                if trace_enabled:
                    branch_queries[selector_name] = self._state_feature_selector_query_trace(
                        rs,
                        selector_inputs,
                        context=feature_context,
                        top_hits=selector_hits,
                        source_group=source_group,
                    )
                    if selector_hits:
                        branch_status[selector_name] = {
                            "configured": True,
                            "fired": True,
                            "n_raw_hits": len(selector_hits),
                        }
                        named_pools.append((selector_name, list(selector_hits[:_trace_k])))
                    else:
                        branch_status[selector_name] = {
                            "configured": True,
                            "fired": False,
                            "skip_reason": "no_feature_signal",
                        }
                if selector_hits:
                    weighted_pools.append(
                        (selector_hits, self.cfg.state_feature_selector_weight)
                    )
        if self.cfg.enable_branch_local_feature_rerank:
            in_place_inputs: list[tuple[str, list[tuple[str, float]], float]] = []
            for source_name, hits, source_weight in feature_branch_inputs:
                start = time.perf_counter()
                reranked = self._branch_local_feature_rerank_hits(
                    rs,
                    hits,
                    context=feature_context,
                )
                add_elapsed("feature_rerank", start)
                add_elapsed(f"feature_rerank.{source_name}", start)
                feature_name = f"{source_name}.state_features"
                if trace_enabled:
                    branch_queries[feature_name] = self._branch_local_feature_query_trace(
                        source_name,
                        rs,
                        context=feature_context,
                        top_hits=reranked,
                        source_hits=hits,
                    )
                    branch_queries[feature_name]["applied_mode"] = (
                        self.cfg.branch_local_feature_rerank_mode
                    )
                    if reranked:
                        branch_status[feature_name] = {
                            "configured": True,
                            "fired": True,
                            "n_raw_hits": len(reranked),
                        }
                        if self.cfg.branch_local_feature_rerank_mode == "additive":
                            named_pools.append((feature_name, list(reranked[:_trace_k])))
                    else:
                        branch_status[feature_name] = {
                            "configured": True,
                            "fired": False,
                            "skip_reason": "no_feature_signal",
                        }
                if self.cfg.branch_local_feature_rerank_mode == "in_place":
                    next_hits = reranked if reranked else hits
                    if reranked:
                        replace_named_pool(source_name, next_hits)
                    in_place_inputs.append((source_name, next_hits, source_weight))
                elif reranked:
                    weighted_pools.append(
                        (
                            reranked,
                            source_weight * self.cfg.branch_local_feature_weight,
                        )
                    )
            if self.cfg.branch_local_feature_rerank_mode == "in_place":
                weighted_pools = [
                    (hits, source_weight)
                    for _source_name, hits, source_weight in in_place_inputs
                    if hits
                ]

        start = time.perf_counter()
        candidate_filter_summary = (
            self._candidate_filter_summary(
                named_pools,
                candidate_mask,
                effective_hard_drop,
                rs,
                artist_policy_drop=artist_policy_drop,
            )
            if trace_enabled
            else {}
        )
        if trace_enabled:
            candidate_filter_summary["artist_policy_filter_enabled"] = int(
                bool(artist_policy_trace.get("enabled"))
            )
        add_elapsed("filter_summary", start)
        start = time.perf_counter()
        fused = self._rrf_fuse_weighted(weighted_pools, k=self.cfg.rrf_k)
        add_elapsed("fuse", start)

        # 7. Soft (de)promotes (gated: destroys GT hits on pivot turns)
        start = time.perf_counter()
        if rs.state.intent_mode.value in self.cfg.soft_adjust_skip_intents:
            adjusted = fused
        else:
            adjusted = self._apply_soft_adjustments(fused, rs)
        add_elapsed("soft_adjust", start)

        # 8. Backfill to topk (popularity-sorted, mask + hard-drop-respecting)
        start = time.perf_counter()
        ranked = [tid for tid, _ in adjusted]
        n_from_fusion = min(len(ranked), self.cfg.final_topk)
        if len(ranked) < self.cfg.final_topk:
            ranked = self._backfill(ranked, candidate_mask, effective_hard_drop)
        ranked = ranked[: self.cfg.final_topk]
        n_from_backfill = len(ranked) - n_from_fusion
        add_elapsed("backfill", start)
        add_elapsed("total", total_start)

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
            hard_drop=sorted(effective_hard_drop) if _trace_k else [],
            timings=timings,
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
        explicit_rejections = list(rs.state.explicit_rejections)
        for index, rej in rs.resolved_rejections.items():
            drop.update(rej.track_ids)
            rejection_kind = (
                explicit_rejections[index].kind
                if 0 <= index < len(explicit_rejections)
                else None
            )
            if self.cfg.rejection_drop_policy == "track_only":
                continue
            for aid in rej.artist_ids:
                drop.update(self.catalog.tracks_by_artist_id(aid))
            if rejection_kind == "artist" and 0 <= index < len(explicit_rejections):
                drop.update(
                    self._tracks_by_artist_name(
                        explicit_rejections[index].value
                    )
                )
        return drop

    @staticmethod
    def _surface_key(value: str) -> str:
        return value.casefold().strip()

    @staticmethod
    def _iter_catalog_strings(raw: object) -> list[str]:
        if raw is None:
            return []
        if hasattr(raw, "tolist"):
            raw = raw.tolist()
        if isinstance(raw, (list, tuple, set)):
            return [str(item) for item in raw if str(item or "").strip()]
        text = str(raw)
        return [text] if text.strip() else []

    @staticmethod
    def _iter_artist_names(raw: object) -> list[str]:
        return V0PlusCompiler._iter_catalog_strings(raw)

    @classmethod
    def _artist_name_lookup_keys(cls, artist_name: str) -> set[str]:
        keys: set[str] = set()
        full_key = cls._catalog_tag_key(artist_name)
        if full_key:
            keys.add(full_key)
        for part in _ARTIST_CREDIT_SPLIT_RE.split(artist_name):
            part_key = cls._catalog_tag_key(part)
            if part_key:
                keys.add(part_key)
        return keys

    def _tracks_by_artist_name(self, artist_name: str) -> list[str]:
        key = self._catalog_tag_key(artist_name)
        if not key:
            return []
        if self._tracks_by_artist_name_key_cache is None:
            by_name: dict[str, list[str]] = {}
            for track_id, row in self.catalog.feature_rows().items():
                if not isinstance(row, dict):
                    continue
                for name in self._iter_artist_names(row.get("artist_name")):
                    for name_key in self._artist_name_lookup_keys(name):
                        by_name.setdefault(name_key, []).append(str(track_id))
            self._tracks_by_artist_name_key_cache = by_name
        return list(self._tracks_by_artist_name_key_cache.get(key, []))

    @staticmethod
    def _enum_value(value) -> str:
        return str(getattr(value, "value", value) or "")

    def _strict_artist_policy_active(self, rs: ResolvedConversationState) -> bool:
        if not self.cfg.enable_strict_artist_policy:
            return False
        state = rs.state
        mode = self._enum_value(getattr(state, "target_artist_mode", ""))
        profile = self._enum_value(getattr(state, "retrieval_profile", ""))
        intent_mode = self._enum_value(getattr(state, "intent_mode", ""))
        turn_intent = str(getattr(state, "turn_intent", "") or "")

        if profile == "exact_probe" or mode == "same_artist":
            return False
        if self._STRICT_DIFFERENT_ARTIST_RE.search(turn_intent):
            return True
        if mode in {"new_artist", "different_artist"}:
            return True
        return intent_mode == "pivot" or profile == "novelty"

    def _artist_policy_drop_set(
        self,
        rs: ResolvedConversationState,
    ) -> tuple[set[str], dict[str, object]]:
        """Tracks blocked by explicit new/different-artist policy."""
        strict = self._strict_artist_policy_active(rs)
        if not strict:
            return set(), {"enabled": False, "strict": False, "blocked_artist_ids": []}

        blocked_artist_ids: set[str] = set()
        for target in rs.resolved_targets:
            if target.kind == "artist" and target.entity_id:
                blocked_artist_ids.add(target.entity_id)

        for track_id in rs.played_track_ids:
            artist_id = self.catalog.artist_id_of(track_id)
            if artist_id:
                blocked_artist_ids.add(artist_id)

        for feedback in rs.state.track_feedback:
            if feedback.overall_sentiment <= 0 or feedback.role == "rejected":
                continue
            artist_id = rs.track_feedback_artist_ids.get(feedback.track_id)
            if artist_id:
                blocked_artist_ids.add(artist_id)

        for rejection in rs.resolved_rejections.values():
            blocked_artist_ids.update(rejection.artist_ids)

        if not blocked_artist_ids:
            return set(), {"enabled": False, "strict": True, "blocked_artist_ids": []}

        drop: set[str] = set()
        for artist_id in blocked_artist_ids:
            drop.update(self.catalog.tracks_by_artist_id(artist_id))
        return drop, {
            "enabled": bool(drop),
            "strict": True,
            "blocked_artist_ids": sorted(blocked_artist_ids),
        }

    def _candidate_filter_summary(
        self,
        named_pools: list[tuple[str, list[tuple[str, float]]]],
        candidate_mask: set[str],
        hard_drop: set[str],
        rs: ResolvedConversationState,
        *,
        artist_policy_drop: set[str] | None = None,
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
        artist_policy_drop = artist_policy_drop or set()
        played_dropped = after_mask & played
        explicit_dropped = (after_mask - played_dropped) & explicit_rejections
        artist_policy_dropped = (
            after_mask - played_dropped - explicit_dropped
        ) & artist_policy_drop
        other_hard_dropped = (
            after_mask - played_dropped - explicit_dropped - artist_policy_dropped
        ) & hard_drop
        return {
            "raw_union_size": len(raw_union),
            "eligible_union_size": len(after_mask - hard_drop),
            "release_date_mask_dropped": len(raw_union - candidate_mask),
            "played_track_dropped": len(played_dropped),
            "explicit_rejection_dropped": len(explicit_dropped),
            "artist_policy_dropped": len(artist_policy_dropped),
            "other_hard_drop_dropped": len(other_hard_dropped),
        }

    def _build_bm25_clauses(self, rs: ResolvedConversationState) -> list[FieldQuery]:
        """Build the Solr-style multi-field BM25 query. Blank-query clauses are
        dropped by the retriever; we keep the structure predictable here."""
        state = rs.state
        per_field: dict[str, list[str]] = {}
        v1_attribute_facet_keys = self._v1_attribute_query_facet_keys(state)
        self._last_tag_resolutions = {}

        for me in state.mentioned_entities:
            if me.sentiment < 0:
                continue
            is_v1_attribute_tag = (
                me.type == "tag"
                and self._catalog_tag_key(me.value) in v1_attribute_facet_keys
            )
            if is_v1_attribute_tag:
                if not self.cfg.bm25_include_v1_attribute_facets:
                    continue
                if self.cfg.bm25_v1_attribute_tag_policy == "resolved":
                    resolution = self._tag_resolver().resolve(me.value)
                    self._last_tag_resolutions[me.value] = [
                        (m.tag, m.score, m.tier) for m in resolution.matches
                    ]
                    clause = per_field.setdefault("tag_list", [])
                    if resolution.resolved:
                        clause.extend(
                            tag for tag in resolution.tags() if tag not in clause
                        )
                    else:
                        # Unresolved phrase: keep the raw text so BM25 token
                        # matching still contributes recall (never worse than
                        # policy "all" for this phrase).
                        clause.append(me.value)
                    continue
                if not self._should_include_v1_attribute_tag_in_bm25(me.value):
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
            if self.cfg.bm25_include_turn_intent_tag_clause:
                tag_intent = (self._strip_negated_spans(intent)
                              if self.cfg.scrub_negated_intent_tags else intent)
                if tag_intent:
                    per_field.setdefault("tag_list", []).append(tag_intent)

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

    @staticmethod
    def _catalog_tag_key(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9&]+", " ", value.casefold())).strip()

    def _catalog_tag_keys(self) -> set[str]:
        if self._catalog_tag_keys_cache is not None:
            return self._catalog_tag_keys_cache
        keys: set[str] = set()
        for track_id in self.catalog.all_track_ids():
            for tag in self.catalog.tag_list(track_id):
                key = self._catalog_tag_key(str(tag))
                if key:
                    keys.add(key)
        self._catalog_tag_keys_cache = keys
        return keys

    def _catalog_tag_document_frequency(self) -> dict[str, int]:
        if self._catalog_tag_df_cache is not None:
            return self._catalog_tag_df_cache
        counts: Counter[str] = Counter()
        for track_id in self.catalog.all_track_ids():
            keys = {
                self._catalog_tag_key(str(tag))
                for tag in self.catalog.tag_list(track_id)
            }
            for key in keys:
                if key:
                    counts[key] += 1
        self._catalog_tag_df_cache = dict(counts)
        return self._catalog_tag_df_cache

    _NEGATION_SCRUB_RE = __import__("re").compile(
        r"\b(?:not|no|without|don'?t want|nothing|never|avoid(?:ing)?|"
        r"other than|except|besides|instead of)\b"
        r"(?:\s+\S+){0,4}", __import__("re").I)

    _STRICT_DIFFERENT_ARTIST_RE = __import__("re").compile(
        r"\b(?:different|new|other|another)\s+"
        r"(?:artists?|bands?|composers?|acts?|performers?)\b"
        r"|\bnot\s+(?:by|from)\b",
        __import__("re").I,
    )

    @classmethod
    def _strip_negated_spans(cls, text: str) -> str:
        """Remove negation cues plus their 4-token window so negated concepts
        don't become positive BM25 tag signal ("not experimental" was matching
        the tag `experimental`)."""
        return " ".join(cls._NEGATION_SCRUB_RE.sub(" ", text).split())

    def _should_include_v1_attribute_tag_in_bm25(self, value: str) -> bool:
        if not self.cfg.bm25_include_v1_attribute_facets:
            return False
        policy = self.cfg.bm25_v1_attribute_tag_policy
        if policy == "all":
            return True
        if policy == "none":
            return False
        if policy == "catalog_exact":
            return self._catalog_tag_key(value) in self._catalog_tag_keys()
        if policy == "resolved":
            # Inclusion is always true under "resolved"; the clause builder
            # substitutes the grounded tags (or keeps the raw phrase as
            # fallback) instead of gating on a boolean.
            return True
        raise ValueError(
            "bm25_v1_attribute_tag_policy must be one of 'all', 'none', "
            f"'catalog_exact', or 'resolved'; got {policy!r}"
        )

    def _tag_resolver(self):
        """Lazily build the tiered phrase->tag resolver (policy "resolved").

        Vocabulary and frequencies come from the catalog caches; the alias
        table is shared with the branch-feature scorer so both paths ground
        phrases identically. The embedding tier activates only when the
        offline index exists AND the configured encoder is registered —
        otherwise the lexical tiers still run and unresolved phrases fall
        back to raw text in the clause builder.
        """
        if self._tag_resolver_cache is None:
            from pathlib import Path as _Path

            from .tag_resolver import (
                TagEmbeddingIndex,
                TieredTagResolver,
                filtered_tag_vocab,
            )

            embedding_index = None
            embed_fn = None
            index_path = self.cfg.tag_resolver_embedding_index_path
            if index_path and _Path(index_path).exists():
                embedding_index = TagEmbeddingIndex.load(index_path)
                client = self.encoders.get(self.cfg.tag_resolver_encoder_id)
                if client is not None:
                    embed_fn = client.embed_batch
            self._tag_resolver_cache = TieredTagResolver(
                catalog_tag_keys=frozenset(self._catalog_tag_keys()),
                aliases=self._BRANCH_FEATURE_TAG_ALIASES,
                substring_vocab=filtered_tag_vocab(
                    self._catalog_tag_document_frequency(),
                    self.cfg.tag_resolver_min_track_count,
                ),
                embedding_index=embedding_index,
                embed_fn=embed_fn,
                embedding_min_score=self.cfg.tag_resolver_embedding_min_score,
                embedding_topk=self.cfg.tag_resolver_embedding_topk,
                max_matches=self.cfg.tag_resolver_max_tags_per_phrase,
                normalize_fn=self._catalog_tag_key,
            )
        return self._tag_resolver_cache

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
    def _v1_attribute_query_facts(
        state: ConversationStateV0Plus,
    ) -> list:
        """Return V1 attribute facts that are usable as descriptive facets.

        This is deliberately structural. It does not inspect the raw user text
        or repair phrases; it just consumes the fact-first state contract.
        """
        facts = getattr(state, "facts", None) or []
        out: list = []
        for fact in facts:
            if getattr(fact, "type", None) != FactType.attribute:
                continue
            if getattr(fact, "role", None) != FactRole.current_target:
                continue
            if getattr(fact, "anchor_use", None) == AnchorUse.do_not_use:
                continue
            if getattr(fact, "relation", None) == FactRelation.exclude:
                continue
            value = str(getattr(fact, "value", "") or "").strip()
            if value:
                out.append(fact)
        return out

    @staticmethod
    def _v1_attribute_query_facet_keys(
        state: ConversationStateV0Plus,
    ) -> set[str]:
        return {
            V0PlusCompiler._catalog_tag_key(str(getattr(fact, "value", "") or ""))
            for fact in V0PlusCompiler._v1_attribute_query_facts(state)
            if str(getattr(fact, "value", "") or "").strip()
        }

    def _v1_attribute_query_values(
        self,
        state: ConversationStateV0Plus,
    ) -> list[str]:
        allowed = {
            str(facet).strip()
            for facet in self.cfg.attribute_query_allowed_facets
            if str(facet).strip()
        }
        seen: set[str] = set()
        values: list[str] = []
        for fact in self._v1_attribute_query_facts(state):
            facet = getattr(fact, "facet", None)
            facet_value = getattr(facet, "value", facet)
            if allowed and str(facet_value) not in allowed:
                continue
            value = str(getattr(fact, "value", "") or "").strip()
            key = value.casefold()
            if not value or key in seen:
                continue
            seen.add(key)
            values.append(value)
        return values

    def _attribute_query_values(
        self,
        state: ConversationStateV0Plus,
    ) -> list[str]:
        source = self.cfg.attribute_query_source
        legacy_tags = [
            value.strip()
            for value in self._positive_mention_values(state, "tag")
            if value.strip()
        ]
        v1_values = self._v1_attribute_query_values(state)

        if source == "legacy_tags":
            raw_values = legacy_tags
        elif source == "v1_attribute_facts":
            raw_values = v1_values
        elif source == "legacy_tags_plus_v1_attribute_facts":
            raw_values = legacy_tags + v1_values
        else:
            raise ValueError(
                "attribute_query_source must be one of "
                "'legacy_tags', 'v1_attribute_facts', or "
                "'legacy_tags_plus_v1_attribute_facts'; got "
                f"{source!r}"
            )

        seen: set[str] = set()
        values: list[str] = []
        for value in raw_values:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(value)
        return values

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

    def _build_visual_nl_query_string(self, rs: ResolvedConversationState) -> str | None:
        """`query_id="visual_nl"` — natural-language caption for SigLIP-2's text
        branch.

        SigLIP-2's text encoder was trained on (image, web-caption) pairs, so a
        caption sentence aligns better than the Round-1 `"album cover, {comma
        tags}"` list — mirroring the `sonic_nl`->CLAP query-framing win. Redundant
        container words (cover / art / album / artwork / image) are stripped
        because the caption frame already implies them; what's left is the
        concrete visual content, which the visual-slice pool diagnostic showed is
        what ranks GT shallow in the cover-art space (vague filler like
        "distinctive cover art" misses).

        Template:
          - "an album cover with {cleaned tags} artwork"
          - Falls back to "album cover artwork, {turn_intent}" when no usable
            tags survive, or None when there is no signal at all.
        """
        import re

        state = rs.state
        tags = self._positive_mention_values(state, "tag")
        filler = re.compile(
            r"\b(?:album covers?|cover art|album art|artworks?|covers?|art|imagery|images?)\b",
            re.IGNORECASE,
        )
        cleaned: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            c = re.sub(r"\s+", " ", filler.sub("", tag)).strip(" ,").strip()
            key = c.casefold()
            if c and key not in seen:
                seen.add(key)
                cleaned.append(c)
        if cleaned:
            return "an album cover with " + ", ".join(cleaned) + " artwork"
        intent = state.turn_intent.strip()
        return f"album cover artwork, {intent}" if intent else None

    def _build_visual_concrete_query_string(self, rs: ResolvedConversationState) -> str | None:
        """`query_id="visual_concrete"` — bare visual descriptors for SigLIP-2.

        The 6-example probe (`modal/app.py::probe_visual`) showed the
        `"album cover,"` frame is non-discriminative — every catalog item IS a
        cover, so the frame pulls the query toward a generic centroid and buries
        the concrete description. Stripping the frame + redundant container words
        ("cover art" / "imagery" / ...) ranked the GT cover 3-28x higher in the
        image-siglip2 space. Emits ONLY the concrete visual descriptors — no
        frame, no caption boilerplate.

        Template:
          - "{cleaned tags}" (comma-joined visual descriptors)
          - Falls back to the filler-stripped turn_intent, or None when there is
            no signal at all.
        """
        import re

        filler = re.compile(
            r"\b(?:album covers?|cover art|album art|artworks?|covers?|art|imagery|images?)\b",
            re.IGNORECASE,
        )

        def _clean(value: str) -> str:
            return re.sub(r"\s+", " ", filler.sub("", value)).strip(" ,").strip()

        state = rs.state
        cleaned: list[str] = []
        seen: set[str] = set()
        for tag in self._positive_mention_values(state, "tag"):
            c = _clean(tag)
            key = c.casefold()
            if c and key not in seen:
                seen.add(key)
                cleaned.append(c)
        if cleaned:
            return ", ".join(cleaned)
        intent = _clean(state.turn_intent)
        return intent or None

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
        mirror that document prefix so the query lands in the same subspace."""
        state = rs.state
        tags = self._attribute_query_values(state)
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
            "visual_nl": self._build_visual_nl_query_string,
            "visual_concrete": self._build_visual_concrete_query_string,
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
        if not self.cfg.enable_release_date_hard_filter:
            return valid
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

    _BRANCH_FEATURE_GENERIC_TERMS: frozenset[str] = frozenset({
        "alternative",
        "classic",
        "dance",
        "electronic",
        "funk",
        "hip hop",
        "hip-hop",
        "metal",
        "pop",
        "popular",
        "rap",
        "rock",
    })

    _BRANCH_FEATURE_TAG_ALIASES: dict[str, tuple[str, ...]] = {
        "hip hop": ("hip-hop", "rap"),
        "hip-hop": ("hip hop", "rap"),
        "r&b": ("rnb", "rhythm and blues", "soul"),
        "rnb": ("r&b", "rhythm and blues", "soul"),
        "pop punk": ("pop-punk", "punk-pop", "emo"),
        "pop-punk": ("pop punk", "punk-pop", "emo"),
        "edm": ("electronic", "electronica", "dance"),
        "electronic": ("electronica", "edm"),
        "alt rock": ("alternative rock", "alternative"),
        "alternative rock": ("alt rock", "alternative"),
        "classic": ("popular", "hit"),
        "popular": ("classic", "hit"),
        "soundtrack": ("movie score", "score", "ost"),
        "orchestral": ("orchestra", "classical"),
        "latin pop": ("latin", "pop"),
        "funk carioca": ("brazilian funk", "baile funk", "funk"),
        "emo": ("emo rock", "pop-punk", "punk-pop"),
        "technical death metal": ("death metal", "progressive death metal", "metal"),
        "underground hip hop": ("underground hip-hop", "underground rap", "hip hop"),
        "jazz rap": ("jazzy hip hop", "jazz hop", "hip hop"),
        "country": ("americana", "folk country"),
        "disco": ("dance", "funk"),
    }

    def _branch_feature_query_text(self, state: ConversationStateV0Plus) -> str:
        parts: list[str] = []
        current_request = getattr(state, "current_request", None)
        if current_request is not None:
            for attr in ("summary", "evidence_text"):
                value = str(getattr(current_request, attr, "") or "").strip()
                if value:
                    parts.append(value)
        if state.turn_intent.strip():
            parts.append(state.turn_intent.strip())
        parts.extend(self._attribute_query_values(state))
        if state.lyrical_theme:
            parts.append(state.lyrical_theme)
        seen: set[str] = set()
        out: list[str] = []
        for part in parts:
            text = " ".join(part.split())
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                out.append(text)
        return "; ".join(out)

    def _branch_feature_terms_from_text(self, text: str) -> set[str]:
        key = self._catalog_tag_key(text)
        if not key:
            return set()
        terms: set[str] = set()
        for part in re.split(r"[,;/|]+", text):
            part_key = self._catalog_tag_key(part)
            if part_key:
                terms.add(part_key)
        padded = f" {key} "
        for catalog_key in self._catalog_tag_keys():
            if catalog_key and f" {catalog_key} " in padded:
                terms.add(catalog_key)
        expanded = set(terms)
        for term in list(terms):
            expanded.update(
                self._catalog_tag_key(alias)
                for alias in self._BRANCH_FEATURE_TAG_ALIASES.get(term, ())
            )
        return {term for term in expanded if term}

    def _track_tag_keys(self, track_id: str) -> set[str]:
        cached = self._track_tag_keys_cache.get(track_id)
        if cached is not None:
            return cached
        keys = {
            self._catalog_tag_key(str(tag))
            for tag in self.catalog.tag_list(track_id)
        }
        keys = {key for key in keys if key}
        expanded = set(keys)
        for key in list(keys):
            expanded.update(
                self._catalog_tag_key(alias)
                for alias in self._BRANCH_FEATURE_TAG_ALIASES.get(key, ())
            )
        out = {term for term in expanded if term}
        self._track_tag_keys_cache[track_id] = out
        return out

    def _track_text_key(self, track_id: str) -> str:
        cached = self._track_text_key_cache.get(track_id)
        if cached is not None:
            return cached
        text = ""
        try:
            text = self.catalog.track_text(track_id)
        except AttributeError:
            text = self.catalog.track_label(track_id)
        out = self._catalog_tag_key(text)
        self._track_text_key_cache[track_id] = out
        return out

    @staticmethod
    def _cosine(a: list[float] | None, b: list[float] | None) -> float:
        if a is None or b is None or len(a) != len(b):
            return 0.0
        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        an = sum(float(x) * float(x) for x in a) ** 0.5
        bn = sum(float(y) * float(y) for y in b) ** 0.5
        if an == 0.0 or bn == 0.0:
            return 0.0
        return dot / (an * bn)

    def _track_cf_bpr(self, track_id: str) -> list[float] | None:
        if track_id in self._track_cf_bpr_cache:
            return self._track_cf_bpr_cache[track_id]
        vec = self.catalog.vector(track_id, "cf_bpr")
        out = _normalize([float(x) for x in vec]) if vec else None
        self._track_cf_bpr_cache[track_id] = out
        return out

    def _anchor_cf_bpr_centroid(
        self,
        state: ConversationStateV0Plus,
    ) -> list[float] | None:
        vectors = [
            self._track_cf_bpr(track_id)
            for track_id in self._anchor_track_ids(state)
        ]
        clean = [vec for vec in vectors if vec]
        if not clean:
            return None
        width = len(clean[0])
        aligned = [vec for vec in clean if len(vec) == width]
        if not aligned:
            return None
        return _normalize([
            sum(vec[idx] for vec in aligned) / len(aligned)
            for idx in range(width)
        ])

    @staticmethod
    def _release_year_compatibility(
        state: ConversationStateV0Plus,
        year: int | None,
    ) -> int:
        release_range = state.release_year_range
        if release_range is None or year is None:
            return 0
        lo = release_range.start
        hi = release_range.end
        if lo is not None and year < lo:
            return -1
        if hi is not None and year > hi:
            return -1
        return 1 if lo is not None or hi is not None else 0

    @staticmethod
    def _branch_feature_negative_terms(state: ConversationStateV0Plus) -> set[str]:
        terms: set[str] = set()
        for rejection in state.explicit_rejections:
            if rejection.kind == "tag" and rejection.value.strip():
                terms.add(V0PlusCompiler._catalog_tag_key(rejection.value))
        for fact in getattr(state, "facts", None) or []:
            if getattr(fact, "type", None) != FactType.attribute:
                continue
            if getattr(fact, "role", None) != FactRole.rejected:
                continue
            value = str(getattr(fact, "value", "") or "").strip()
            if value:
                terms.add(V0PlusCompiler._catalog_tag_key(value))
        return {term for term in terms if term}

    def _branch_local_feature_context(
        self,
        rs: ResolvedConversationState,
    ) -> dict[str, object]:
        state = rs.state
        query_text = self._branch_feature_query_text(state)
        query_terms = self._branch_feature_terms_from_text(query_text)
        negative_terms = self._branch_feature_negative_terms(state)
        anchor_cf = self._anchor_cf_bpr_centroid(state)
        anchor_artist_ids = {
            self.catalog.artist_id_of(track_id)
            for track_id in self._anchor_track_ids(state)
            if self.catalog.artist_id_of(track_id)
        }
        popularity_requested = bool(
            {
                "popular",
                "classic",
                "hit",
                "hits",
                "iconic",
                "well known",
            } & query_terms
        )
        return {
            "query_text": query_text,
            "query_terms": query_terms,
            "negative_terms": negative_terms,
            "anchor_cf": anchor_cf,
            "anchor_artist_ids": anchor_artist_ids,
            "popularity_requested": popularity_requested,
        }

    def _branch_local_feature_score(
        self,
        rs: ResolvedConversationState,
        track_id: str,
        context: dict[str, object],
    ) -> float:
        parts = self._branch_local_feature_score_breakdown(rs, track_id, context)
        return float(parts["state_feature_score"])

    def _branch_local_feature_score_breakdown(
        self,
        rs: ResolvedConversationState,
        track_id: str,
        context: dict[str, object],
    ) -> dict[str, object]:
        query_terms = context["query_terms"]
        if not isinstance(query_terms, set):
            query_terms = set()
        tags = self._track_tag_keys(track_id)
        tag_overlap = query_terms & tags
        specific_overlap = {
            term for term in tag_overlap if term not in self._BRANCH_FEATURE_GENERIC_TERMS
        }
        generic_overlap = tag_overlap - specific_overlap
        text = self._track_text_key(track_id)
        phrase_hits = {
            term for term in query_terms if isinstance(term, str) and " " in term and term in text
        }
        negative_terms = context["negative_terms"]
        if not isinstance(negative_terms, set):
            negative_terms = set()
        negative_overlap = negative_terms & tags

        tag_overlap_score = min(0.060, 0.015 * len(specific_overlap))
        generic_tag_overlap_score = min(0.020, 0.004 * len(generic_overlap))
        phrase_hit_score = min(0.024, 0.008 * len(phrase_hits))
        tag_df = self._catalog_tag_document_frequency()
        rarity_tag_overlap_score = min(
            0.024,
            sum(
                0.012 if tag_df.get(term, 10**9) <= 10
                else 0.008 if tag_df.get(term, 10**9) <= 100
                else 0.004 if tag_df.get(term, 10**9) <= 1000
                else 0.0
                for term in specific_overlap
            ),
        )

        year_match = self._release_year_compatibility(
            rs.state,
            self.catalog.release_year_of(track_id),
        )
        year_compatibility_score = 0.0
        if year_match > 0:
            year_compatibility_score = 0.014
        elif year_match < 0:
            year_compatibility_score = -0.014

        popularity_score = 0.0
        if context.get("popularity_requested"):
            pop_rank = self._popularity_rank().get(track_id)
            if pop_rank is not None:
                if pop_rank <= 200:
                    popularity_score = 0.040
                elif pop_rank <= 1000:
                    popularity_score = 0.030
                elif pop_rank <= 3000:
                    popularity_score = 0.015

        negative_tag_score = 0.0
        if negative_overlap:
            negative_tag_score = -min(0.060, 0.030 * len(negative_overlap))

        anchor_cf_score = 0.0
        anchor_cf = context.get("anchor_cf")
        if isinstance(anchor_cf, list):
            anchor_cf_score = 0.036 * max(
                0.0,
                self._cosine(anchor_cf, self._track_cf_bpr(track_id)),
            )

        new_artist_demote_score = 0.0
        target_artist_mode = getattr(rs.state.target_artist_mode, "value", str(rs.state.target_artist_mode))
        anchor_artist_ids = context.get("anchor_artist_ids")
        if (
            target_artist_mode == "new_artist"
            and isinstance(anchor_artist_ids, set)
            and self.catalog.artist_id_of(track_id) in anchor_artist_ids
        ):
            new_artist_demote_score = -0.030

        state_feature_score = (
            tag_overlap_score
            + generic_tag_overlap_score
            + rarity_tag_overlap_score
            + phrase_hit_score
            + year_compatibility_score
            + popularity_score
            + negative_tag_score
            + anchor_cf_score
            + new_artist_demote_score
        )
        return {
            "state_feature_score": state_feature_score,
            "tag_overlap_score": tag_overlap_score,
            "generic_tag_overlap_score": generic_tag_overlap_score,
            "rarity_tag_overlap_score": rarity_tag_overlap_score,
            "phrase_hit_score": phrase_hit_score,
            "year_compatibility_score": year_compatibility_score,
            "popularity_requested_score": popularity_score,
            "negative_tag_demotion": negative_tag_score,
            "anchor_cf_contribution": anchor_cf_score,
            "same_anchor_novelty_demotion": new_artist_demote_score,
            "specific_tag_overlap": sorted(specific_overlap),
            "generic_tag_overlap": sorted(generic_overlap),
            "phrase_hits": sorted(phrase_hits),
            "negative_tag_overlap": sorted(negative_overlap),
        }

    def _branch_local_feature_rerank_hits(
        self,
        rs: ResolvedConversationState,
        hits: list[tuple[str, float]],
        context: dict[str, object] | None = None,
    ) -> list[tuple[str, float]]:
        if not hits:
            return []
        context = context or self._branch_local_feature_context(rs)
        has_signal = bool(context["query_terms"]) or context.get("anchor_cf") is not None
        if not has_signal:
            return []
        adjusted: list[tuple[str, float, int]] = []
        seen: set[str] = set()
        for rank, (track_id, _score) in enumerate(hits, start=1):
            if track_id in seen:
                continue
            seen.add(track_id)
            feature_score = self._branch_local_feature_score(rs, track_id, context)
            score = (1.0 / (self.cfg.rrf_k + rank)) + (
                self.cfg.branch_local_feature_score_weight * feature_score
            )
            adjusted.append((track_id, score, rank))
        adjusted.sort(key=lambda item: (-item[1], item[2], item[0]))
        return [(track_id, score) for track_id, score, _rank in adjusted]

    def _state_feature_selector_hits(
        self,
        rs: ResolvedConversationState,
        branch_inputs: list[tuple[str, list[tuple[str, float]], float]],
        context: dict[str, object] | None = None,
    ) -> list[tuple[str, float]]:
        context = context or self._branch_local_feature_context(rs)
        has_signal = bool(context["query_terms"]) or context.get("anchor_cf") is not None
        if not has_signal:
            return []
        branch_support: dict[str, float] = {}
        first_seen_rank: dict[str, int] = {}
        for source_name, hits, source_weight in branch_inputs:
            seen_in_source: set[str] = set()
            for rank, (track_id, _score) in enumerate(hits, start=1):
                if track_id in seen_in_source:
                    continue
                seen_in_source.add(track_id)
                branch_support[track_id] = branch_support.get(track_id, 0.0) + (
                    source_weight / (self.cfg.rrf_k + rank)
                )
                first_seen_rank[track_id] = min(
                    first_seen_rank.get(track_id, rank),
                    rank,
                )
        scored: list[tuple[str, float, int]] = []
        for track_id, support_score in branch_support.items():
            feature_score = self._branch_local_feature_score(rs, track_id, context)
            score = support_score + (
                self.cfg.state_feature_selector_score_weight * feature_score
            )
            scored.append((track_id, score, first_seen_rank.get(track_id, 10**9)))
        scored.sort(key=lambda item: (-item[1], item[2], item[0]))
        return [(track_id, score) for track_id, score, _rank in scored]

    @staticmethod
    def _state_feature_selector_group_key(source_name: str) -> str:
        if source_name == "bm25":
            return "lexical"
        if source_name.startswith("lookup."):
            return "lookup"
        if source_name.startswith("dense."):
            parts = source_name.split(".")
            if len(parts) >= 3 and parts[2]:
                return f"dense.{parts[2]}"
            return "dense"
        if source_name.startswith("centroid."):
            parts = source_name.split(".")
            if len(parts) >= 2 and parts[1]:
                return f"centroid.{parts[1]}"
            return "centroid"
        return source_name.split(".", 1)[0] or "other"

    def _state_feature_selector_branch_inputs(
        self,
        branch_inputs: list[tuple[str, list[tuple[str, float]], float]],
    ) -> list[tuple[str, str, list[tuple[str, list[tuple[str, float]], float]]]]:
        non_empty_inputs = [
            (source_name, hits, source_weight)
            for source_name, hits, source_weight in branch_inputs
            if hits
        ]
        if self.cfg.state_feature_selector_grouping == "global":
            return [("state_feature_selector", "global", non_empty_inputs)]

        grouped: dict[str, list[tuple[str, list[tuple[str, float]], float]]] = {}
        for source_name, hits, source_weight in non_empty_inputs:
            grouped.setdefault(
                self._state_feature_selector_group_key(source_name),
                [],
            ).append((source_name, hits, source_weight))
        return [
            (f"state_feature_selector.{group}", group, inputs)
            for group, inputs in sorted(grouped.items())
        ]

    def _state_feature_survivor_hits(
        self,
        rs: ResolvedConversationState,
        branch_inputs: list[tuple[str, list[tuple[str, float]], float]],
        context: dict[str, object] | None = None,
    ) -> list[tuple[str, float]]:
        context = context or self._branch_local_feature_context(rs)
        has_signal = bool(context["query_terms"]) or context.get("anchor_cf") is not None
        if not has_signal:
            return []

        min_rank = int(self.cfg.state_feature_survivor_min_rank)
        max_rank = int(self.cfg.state_feature_survivor_max_rank)
        first_seen_rank: dict[str, int] = {}
        branch_support: dict[str, float] = {}
        for _source_name, hits, source_weight in branch_inputs:
            seen_in_source: set[str] = set()
            for rank, (track_id, _score) in enumerate(hits[:max_rank], start=1):
                if rank < min_rank or track_id in seen_in_source:
                    continue
                seen_in_source.add(track_id)
                first_seen_rank[track_id] = min(
                    first_seen_rank.get(track_id, rank),
                    rank,
                )
                branch_support[track_id] = branch_support.get(track_id, 0.0) + (
                    source_weight / (self.cfg.rrf_k + rank)
                )

        scored: list[tuple[str, float, int]] = []
        for track_id, support_score in branch_support.items():
            best_rank = first_seen_rank.get(track_id, max_rank)
            feature_score = self._branch_local_feature_score(rs, track_id, context)
            if feature_score < self.cfg.state_feature_survivor_min_feature_score:
                continue
            score = (
                self.cfg.state_feature_survivor_score_weight * feature_score
                + self.cfg.state_feature_survivor_rank_weight
                / (self.cfg.rrf_k + best_rank)
                + self.cfg.state_feature_survivor_support_weight * support_score
            )
            scored.append((track_id, score, best_rank))
        scored.sort(key=lambda item: (-item[1], item[2], item[0]))
        return [(track_id, score) for track_id, score, _rank in scored]

    def _state_feature_selector_source_ranks(
        self,
        branch_inputs: list[tuple[str, list[tuple[str, float]], float]],
    ) -> dict[str, list[dict[str, object]]]:
        by_track: dict[str, list[dict[str, object]]] = {}
        for source_name, hits, source_weight in branch_inputs:
            seen_in_source: set[str] = set()
            for rank, (track_id, _score) in enumerate(hits, start=1):
                if track_id in seen_in_source:
                    continue
                seen_in_source.add(track_id)
                by_track.setdefault(track_id, []).append(
                    {
                        "branch": source_name,
                        "rank": rank,
                        "weight": float(source_weight),
                    }
                )
        for ranks in by_track.values():
            ranks.sort(key=lambda item: (int(item["rank"]), str(item["branch"])))
        return by_track

    def _state_feature_survivor_query_trace(
        self,
        rs: ResolvedConversationState,
        branch_inputs: list[tuple[str, list[tuple[str, float]], float]],
        context: dict[str, object] | None = None,
        top_hits: list[tuple[str, float]] | None = None,
    ) -> dict:
        context = context or self._branch_local_feature_context(rs)
        query_terms = context["query_terms"]
        trace = {
            "kind": "state_feature_survivor",
            "source_branches": [name for name, hits, _weight in branch_inputs if hits],
            "source_rank_window": [
                int(self.cfg.state_feature_survivor_min_rank),
                int(self.cfg.state_feature_survivor_max_rank),
            ],
            "query_text": context["query_text"],
            "query_terms": sorted(query_terms) if isinstance(query_terms, set) else [],
            "uses_anchor_cf": context.get("anchor_cf") is not None,
        }
        if top_hits is not None:
            source_ranks = self._state_feature_selector_source_ranks(branch_inputs)
            trace["top_feature_scores"] = []
            for track_id, score in top_hits[:20]:
                ranks = [
                    rank
                    for rank in source_ranks.get(track_id, [])
                    if self.cfg.state_feature_survivor_min_rank
                    <= int(rank["rank"])
                    <= self.cfg.state_feature_survivor_max_rank
                ]
                best_rank = ranks[0] if ranks else {}
                trace["top_feature_scores"].append(
                    {
                        "track_id": track_id,
                        "survivor_score": float(score),
                        "best_source_branch": best_rank.get("branch"),
                        "best_source_rank": best_rank.get("rank"),
                        "source_ranks": ranks[:5],
                        **self._branch_local_feature_score_breakdown(
                            rs,
                            track_id,
                            context,
                        ),
                    }
                )
        return trace

    def _state_feature_selector_query_trace(
        self,
        rs: ResolvedConversationState,
        branch_inputs: list[tuple[str, list[tuple[str, float]], float]],
        context: dict[str, object] | None = None,
        top_hits: list[tuple[str, float]] | None = None,
        source_group: str = "global",
    ) -> dict:
        context = context or self._branch_local_feature_context(rs)
        query_terms = context["query_terms"]
        trace = {
            "kind": "state_feature_selector",
            "source_group": source_group,
            "source_branches": [name for name, hits, _weight in branch_inputs if hits],
            "query_text": context["query_text"],
            "query_terms": sorted(query_terms) if isinstance(query_terms, set) else [],
            "uses_anchor_cf": context.get("anchor_cf") is not None,
        }
        if top_hits is not None:
            source_ranks = self._state_feature_selector_source_ranks(branch_inputs)
            trace["top_feature_scores"] = []
            for track_id, score in top_hits[:20]:
                ranks = source_ranks.get(track_id, [])
                best_rank = ranks[0] if ranks else {}
                trace["top_feature_scores"].append(
                    {
                        "track_id": track_id,
                        "selector_score": float(score),
                        "best_source_branch": best_rank.get("branch"),
                        "best_source_rank": best_rank.get("rank"),
                        "source_ranks": ranks[:5],
                        **self._branch_local_feature_score_breakdown(
                            rs,
                            track_id,
                            context,
                        ),
                    }
                )
        return trace

    def _branch_local_feature_query_trace(
        self,
        source_branch: str,
        rs: ResolvedConversationState,
        context: dict[str, object] | None = None,
        top_hits: list[tuple[str, float]] | None = None,
        source_hits: list[tuple[str, float]] | None = None,
    ) -> dict:
        context = context or self._branch_local_feature_context(rs)
        query_terms = context["query_terms"]
        trace = {
            "kind": "branch_local_feature_rerank",
            "source_branch": source_branch,
            "query_text": context["query_text"],
            "query_terms": sorted(query_terms) if isinstance(query_terms, set) else [],
            "uses_anchor_cf": context.get("anchor_cf") is not None,
        }
        if top_hits is not None:
            source_rank = {
                track_id: rank
                for rank, (track_id, _score) in enumerate(source_hits or [], start=1)
            }
            trace["top_feature_scores"] = [
                {
                    "track_id": track_id,
                    "original_branch_rank": source_rank.get(track_id),
                    **self._branch_local_feature_score_breakdown(rs, track_id, context),
                }
                for track_id, _score in top_hits[:20]
            ]
        return trace

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
        artist_names: list[str] = []
        seen_artists: set[str] = set()
        seen_artist_names: set[str] = set()
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
                source_text = str(getattr(tgt, "source_text", "") or "").strip()
                source_key = self._surface_key(source_text)
                if source_key and source_key not in seen_artist_names:
                    seen_artist_names.add(source_key)
                    artist_names.append(source_text)
        # a2: also seed from artists of tracks played earlier in the session.
        if cfg.disco_include_session_artists:
            for tid in rs.played_track_ids:
                aid = self.catalog.artist_id_of(tid)
                if aid is not None and aid not in seen_artists:
                    seen_artists.add(aid)
                    artist_ids.append(aid)
        if not artist_ids and not artist_names:
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
        for artist_name in artist_names:
            ranked = sorted(
                self._tracks_by_artist_name(artist_name),
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
