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

See: experiments/analysis/conversation_state_compiler_v0plus/README.md
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    ConversationStateV0Plus,
)
from mcrs.embeddings.base import EmbeddingClient
from mcrs.qu_modules.resolver_v0plus import ResolvedConversationState
from mcrs.qu_modules.v0plus_catalog import CompilerCatalog
from mcrs.retrieval_modules.base import FieldQuery, Retriever


@dataclass
class BranchPool:
    """One retriever branch's contribution to fusion, retained for tracing.

    A branch appears in `CompileResult.branch_pools` if and only if it FIRED
    (issued a retrieval call) on this turn. A fired branch whose hits are all
    removed by the mask / hard-drop is still included as an empty pool.
    Branches that did not fire (e.g. a dense branch when there is no encoded
    query, or a centroid branch whose centroid is None) are omitted entirely.

    `hits` is post-mask, post-hard-drop, capped at the compiler's final_topk.
    Rank is the list index.
    """

    name: str
    hits: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class CompileResult:
    """Structured output of `V0PlusCompiler._compile()`.

    `ranked` is the exact list `compile()` returns (top-final_topk). The other
    fields are the per-branch / fused / provenance artifacts the devset trace
    persists for downstream rerank / explanation pickup.

    `fused` is the RRF-fused list BEFORE soft (de)promotes; `ranked` is the
    final list AFTER soft adjustments AND popularity backfill.
    """

    ranked: list[str]
    branch_pools: list[BranchPool] = field(default_factory=list)
    fused: list[tuple[str, float]] = field(default_factory=list)
    n_from_fusion: int = 0
    n_from_backfill: int = 0
    depth: int = 1000

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
        }


@dataclass
class DenseBranch:
    """One dense retrieval branch — a vector column to ANN-query against.

    The Compiler issues one `search_embedding(...)` call per enabled branch,
    each with the SAME encoded query text but a branch-specific anchor
    centroid (from `catalog.vector(track_id, vector_field)`).
    """

    vector_field: str
    weight: float = 1.0
    distance_type: str = "cosine"


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
        default_factory=lambda: {
            "track_name": 3.0,
            "artist_name": 3.0,
            "album_name": 2.0,
            "tag_list": 1.5,
        }
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


class V0PlusCompiler:
    """Turn a ResolvedConversationState into top-N ranked track_ids."""

    def __init__(
        self,
        catalog: CompilerCatalog,
        retriever: Retriever,
        encoder: EmbeddingClient,
        config: CompilerConfig | None = None,
        user_embeddings: "UserEmbeddings | None" = None,
    ) -> None:
        self.catalog = catalog
        self.retriever = retriever
        self.encoder = encoder
        self.cfg = config or CompilerConfig()
        # Optional user-side embeddings lookup. Required only when a config
        # uses `centroid_only_branches` with `centroid_source="user"`. None
        # otherwise, and the user branch is silently skipped.
        self.user_embeddings = user_embeddings

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def compile(self, rs: ResolvedConversationState, user_id: str | None = None) -> list[str]:
        """Public entry point. Returns top-final_topk track_ids (unchanged
        output contract). Internally delegates to `_compile`, which also
        retains the per-branch pools for tracing."""
        return self._compile(rs, user_id=user_id).ranked

    def _compile(
        self, rs: ResolvedConversationState, user_id: str | None = None
    ) -> CompileResult:
        state = rs.state

        # 1. Pre-fusion catalog mask from hard_filters.release_date
        candidate_mask = self._release_date_mask(state)

        # 2. Build queries
        bm25_clauses = self._build_bm25_clauses(rs)
        encoded_query = self._build_dense_query_text(rs) if self.cfg.enable_dense else None

        # 3. Retrieval — 1 BM25 call + 1 search_embedding per enabled dense branch.
        #    Track (name, hits) per branch so we can retain pools for tracing.
        bm25_hits = self.retriever.search(bm25_clauses, topk=self.cfg.bm25_k)
        named_pools: list[tuple[str, list[tuple[str, float]]]] = [("bm25", bm25_hits)]

        dense_branch_results: list[list[tuple[str, float]]] = []
        if encoded_query is not None:
            for branch in self.cfg.dense_branches:
                vec = self._mix_for_branch(rs, encoded_query, branch)
                hits = self.retriever.search_embedding(
                    query_vector=vec,
                    vector_field=branch.vector_field,
                    topk=self.cfg.dense_k,
                    distance_type=branch.distance_type,
                )
                dense_branch_results.append(hits)
                named_pools.append((f"dense:{branch.vector_field}", hits))

        # 3b. Centroid-only branches — one search_embedding call per entry.
        centroid_branches = self._resolve_centroid_only_branches()
        centroid_branch_results: list[tuple[list[tuple[str, float]], float]] = []
        for cb in centroid_branches:
            centroid = self._centroid_for_branch(rs, user_id, cb)
            if centroid is None:
                continue
            hits = self.retriever.search_embedding(
                query_vector=centroid,
                vector_field=cb.vector_field,
                topk=cb.topk,
                distance_type=cb.distance_type,
            )
            centroid_branch_results.append((hits, cb.weight))
            prefix = "centroid_user" if cb.centroid_source == "user" else "centroid"
            named_pools.append((f"{prefix}:{cb.vector_field}", hits))

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

        # 5b. Re-apply mask + hard-drop to the retained named pools, then cap
        #     each at final_topk. `named_pools` contains exactly the branches
        #     that fired (issued a search), so we keep all of them — a fired
        #     branch left empty after filtering stays as an empty pool; only
        #     non-firing branches are absent (they were never appended).
        def _filter_and_cap(hits: list[tuple[str, float]]) -> list[tuple[str, float]]:
            return [
                (t, s) for t, s in hits if t in candidate_mask and t not in hard_drop
            ][: self.cfg.final_topk]

        branch_pools = [
            BranchPool(name=name, hits=_filter_and_cap(hits)) for name, hits in named_pools
        ]

        # 6. Weighted RRF fusion (compiler-owned, cross-modal)
        weighted_pools: list[tuple[list[tuple[str, float]], float]] = [(bm25_hits, 1.0)]
        for hits, branch in zip(dense_branch_results, self.cfg.dense_branches):
            weighted_pools.append((hits, branch.weight))
        for hits, weight in centroid_branch_results:
            if hits:
                weighted_pools.append((hits, weight))
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
            branch_pools=branch_pools,
            fused=fused[: self.cfg.final_topk],
            n_from_fusion=n_from_fusion,
            n_from_backfill=n_from_backfill,
            depth=self.cfg.final_topk,
        )

    # ------------------------------------------------------------------
    # Query construction
    # ------------------------------------------------------------------

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

        # turn_intent: free text routed where mood/title vocabulary fits.
        # Avoid artist_name (prevents "Beat" verb → "Beatles" false pos) and
        # album_name (rarely contains mood/era words).
        intent = state.turn_intent.strip()
        if intent:
            per_field.setdefault("track_name", []).append(intent)
            per_field.setdefault("tag_list", []).append(intent)

        return [
            FieldQuery(
                field=field_name,
                query=" ".join(terms).strip(),
                boost=self.cfg.field_boosts.get(field_name, 1.0),
            )
            for field_name, terms in per_field.items()
            if " ".join(terms).strip()
        ]

    def _build_dense_query_text(self, rs: ResolvedConversationState) -> list[float] | None:
        """Encode the dense query string ONCE. Returns the normalized encoded
        vector, or None when turn_intent / positive entities / tags are all
        empty (so the dense modality is skipped entirely).

        Centroid mixing is per-branch and happens in `_mix_for_branch` so
        each dense field can mix its own anchor centroid.
        """
        state = rs.state
        text_parts: list[str] = []
        if state.turn_intent.strip():
            text_parts.append(state.turn_intent.strip())

        artists = [
            me.value for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == "artist"
        ]
        tags = [
            me.value for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == "tag"
        ]
        if artists:
            text_parts.append("like: " + ", ".join(artists))
        if tags:
            text_parts.append("tags: " + ", ".join(tags))

        if not text_parts:
            return None

        query_string = "; ".join(text_parts)
        query_vec = self.encoder.embed_batch([query_string])[0]
        return _normalize(query_vec)

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

        for i, rej in rs.resolved_rejections.items():
            er = state.explicit_rejections[i]
            if er.kind == "track":
                drop.update(rej.track_ids)
            elif er.kind == "artist":
                for aid in rej.artist_ids:
                    drop.update(self.catalog.tracks_by_artist_id(aid))

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
        state = rs.state
        rejected_tags = {
            er.value.lower()
            for er in state.explicit_rejections
            if er.kind == "tag" and er.value
        }
        positive_tags = {
            me.value.lower()
            for me in state.mentioned_entities
            if me.sentiment > 0 and me.type == "tag" and me.value
        }
        # Soft rejection: artists inferred from `track_feedback` (user rejected a
        # specific track, so we infer the artist is unwelcome). Multiplied, not
        # excluded, because the artist signal here is indirect.
        soft_rejected_artist_ids = {
            rs.track_feedback_artist_ids.get(tf.track_id)
            for tf in state.track_feedback
            if tf.role == "rejected"
        }
        soft_rejected_artist_ids.discard(None)

        # HARD rejection: `explicit_rejections` resolved by the resolver. These
        # are the user's direct "no more X" statements — we drop matching
        # tracks entirely, not just demote. Resolver may attach BOTH track_ids
        # and artist_ids per rejection (e.g. kind="track" still resolves the
        # owning artist; kind="artist" resolves all that artist's track_ids).
        hard_excluded_track_ids: set[str] = set()
        hard_excluded_artist_ids: set[str] = set()
        for rj in rs.resolved_rejections.values():
            hard_excluded_track_ids.update(rj.track_ids)
            hard_excluded_artist_ids.update(rj.artist_ids)

        adjusted: list[tuple[str, float]] = []
        for tid, score in fused:
            if tid in hard_excluded_track_ids:
                continue
            artist_id = self.catalog.artist_id_of(tid)
            if artist_id is not None and artist_id in hard_excluded_artist_ids:
                continue
            tags = {t.lower() for t in self.catalog.tag_list(tid)}
            mult = 1.0
            if rejected_tags:
                mult *= self.cfg.rejected_tag_multiplier ** len(tags & rejected_tags)
            if positive_tags:
                mult *= (1.0 + self.cfg.positive_tag_multiplier_step) ** len(
                    tags & positive_tags
                )
            if artist_id is not None and artist_id in soft_rejected_artist_ids:
                mult *= self.cfg.same_artist_demote
            adjusted.append((tid, score * mult))
        adjusted.sort(key=lambda x: -x[1])
        return adjusted

    # ------------------------------------------------------------------
    # Backfill
    # ------------------------------------------------------------------

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
            if tf.role in ("accepted", "seed") and tf.overall_sentiment > 0:
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
        field (common for `lyrics_qwen3` since coverage is sparse)."""
        vectors: list[list[float]] = []
        for tid in self._anchor_track_ids(rs.state):
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
