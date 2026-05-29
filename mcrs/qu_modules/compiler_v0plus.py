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

import re
from collections import Counter
from dataclasses import dataclass, field

# Word-boundary tokenizer for lyric-hint detection. Splits on any
# non-word character so substring matches like `"story" in "history"` or
# `"deep" in "deepfake"` don't accidentally fire the lyric branch.
_LYRIC_TOKEN_RE = re.compile(r"\w+")

from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    ConversationStateV0Plus,
)
from mcrs.embeddings.base import EmbeddingClient
from mcrs.qu_modules.resolver_v0plus import ResolvedConversationState
from mcrs.qu_modules.v0plus_catalog import CompilerCatalog
from mcrs.retrieval_modules.base import FieldQuery, Retriever


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

    # Per-branch ranking diagnostic. When > 0, every `compile()` populates the
    # trace's `branch_rankings` map with each branch's top-K candidate IDs
    # (BM25 + each dense + each centroid-only). 0 means off (no trace cost).
    # Use for offline diagnostics like "where does the GT rank inside each
    # retriever?" Costs ~36 KB * branches * turns when on.
    branch_trace_topk: int = 0


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
        self.cfg = config or CompilerConfig()
        # Optional user-side embeddings lookup. Required only when a config
        # uses `centroid_only_branches` with `centroid_source="user"`. None
        # otherwise, and the user branch is silently skipped.
        self.user_embeddings = user_embeddings

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def compile(
        self,
        rs: ResolvedConversationState,
        user_id: str | None = None,
        branch_traces: dict[str, list[str]] | None = None,
    ) -> list[str]:
        """Compile a resolved state into top-N ranked track_ids.

        When `branch_traces` is a dict, it is populated with each retriever
        branch's top-K candidate IDs (K = self.cfg.branch_trace_topk).
        Keys are stable identifiers ("bm25",
        "dense.<encoder_id>.<query_id>.<vector_field>",
        "centroid.<source>.<vector_field>") so downstream analysis can match
        them across runs. No-op when branch_traces is None or topk is 0.
        """
        state = rs.state
        _trace_k = self.cfg.branch_trace_topk if branch_traces is not None else 0

        # 1. Pre-fusion catalog mask from hard_filters.release_date
        candidate_mask = self._release_date_mask(state)

        # 2. Build queries
        bm25_clauses = self._build_bm25_clauses(rs)
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
        if _trace_k:
            branch_traces["bm25"] = [t for t, _ in bm25_hits[:_trace_k]]
        # Cache encoded vectors by (encoder_id, query_id) so branches sharing
        # an encoder/query pair pay one encode call total.
        encoded_cache: dict[tuple[str, str], list[float]] = {}
        dense_branch_results: list[list[tuple[str, float]]] = []
        if self.cfg.enable_dense:
            for branch in self.cfg.dense_branches:
                q_text = query_strings.get(branch.query_id)
                if q_text is None:
                    # Either query_id unknown OR state had no positive signal.
                    # Append empty hits to keep dense_branch_results aligned
                    # with self.cfg.dense_branches for the RRF fusion zip().
                    dense_branch_results.append([])
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
                if _trace_k:
                    # Include `query_id` so multiple branches sharing
                    # encoder_id + vector_field (e.g. v4's 3xCLAP) get
                    # distinct trace keys instead of overwriting each other.
                    branch_traces[
                        f"dense.{branch.encoder_id}.{branch.query_id}.{branch.vector_field}"
                    ] = [t for t, _ in hits[:_trace_k]]

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
            if _trace_k:
                branch_traces[f"centroid.{cb.centroid_source}.{cb.vector_field}"] = (
                    [t for t, _ in hits[:_trace_k]]
                )

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

        # 6. Weighted RRF fusion (compiler-owned, cross-modal)
        weighted_pools: list[tuple[list[tuple[str, float]], float]] = [(bm25_hits, 1.0)]
        for hits, branch in zip(dense_branch_results, self.cfg.dense_branches):
            weighted_pools.append((hits, branch.weight))
        for hits, weight in centroid_branch_results:
            if hits:
                weighted_pools.append((hits, weight))
        fused = self._rrf_fuse_weighted(weighted_pools, k=self.cfg.rrf_k)

        # 7. Soft (de)promotes
        fused = self._apply_soft_adjustments(fused, rs)

        # 8. Backfill to topk (popularity-sorted, mask + hard-drop-respecting)
        ranked = [tid for tid, _ in fused]
        if len(ranked) < self.cfg.final_topk:
            ranked = self._backfill(ranked, candidate_mask, hard_drop)

        return ranked[: self.cfg.final_topk]

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

    # -- Dense query templates --------------------------------------------
    # Each builder takes the resolved state and returns a query STRING (or
    # None to skip the branch). Branches reference templates by `query_id`.
    # New `query_id`s are added by writing a `_build_<name>_query_string`
    # method and registering it in `_query_builders` below.

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
        tags = [
            me.value for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == "tag"
        ]
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
        tags = [
            me.value for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == "tag"
        ]
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
        tags = [
            me.value for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == "tag"
        ]
        artists = [
            me.value for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == "artist"
        ]
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
        state_tags = [
            me.value for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == "tag" and me.value
        ]
        artists = [
            me.value for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == "artist" and me.value
        ]
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
        """`query_id="lyric"` — qwen3-shaped query for the lyrics column.

        Fires only when the resolver/extractor signal contains lyric or
        thematic language. The conditional firing addresses the Wave-3
        finding that an always-on lyrics_qwen3 branch regressed macro
        NDCG@20 by -9% (the catalog lyrics column matched arbitrary intent
        text poorly when the intent had no lyric content).

        Returns None to skip the branch when no lyric signal is present.
        The compiler handles None by appending an empty hit list to keep
        branch ordering aligned with the dense_branches config — RRF then
        naturally ignores it.

        Template (when fired):
          - turn_intent + any lyric-relevant tag mentions, separated by ";".
          - Qwen3 encoder semantically aligns this with the catalog's
            full-song-lyric embeddings.
        """
        state = rs.state
        intent_text = (state.turn_intent or "").strip()
        # Access via class so call sites that bind only the methods (test
        # harnesses, doc-renderers) still see the lexicon.
        hints = V0PlusCompiler._LYRIC_HINT_WORDS
        # Token-level membership, not substring. Substring match would
        # false-positive on common English (`"story" in "history"`,
        # `"deep" in "deepfake"`, `"soul" in "souls"`) and fire the lyric
        # branch on non-lyric turns. Splits on any non-word char.
        intent_tokens = set(_LYRIC_TOKEN_RE.findall(intent_text.lower()))
        has_intent_signal = bool(intent_tokens & hints)

        tag_values = [
            me.value for me in state.mentioned_entities
            if me.sentiment >= 0 and me.type == "tag" and me.value
        ]
        lyric_tags = [
            t for t in tag_values
            if set(_LYRIC_TOKEN_RE.findall(t.lower())) & hints
        ]

        if not has_intent_signal and not lyric_tags:
            return None

        parts: list[str] = []
        if intent_text:
            parts.append(intent_text)
        if lyric_tags:
            parts.append("themes: " + ", ".join(lyric_tags))
        return "; ".join(parts) if parts else None

    @property
    def _query_builders(self):
        """Registry mapping `query_id` -> builder method.

        Extending Round 2 with a new template requires a new method here
        plus a YAML branch referencing it via `query_id`. No further code
        changes needed.
        """
        return {
            "intent": self._build_dense_query_string,
            "sonic": self._build_sonic_query_string,
            "visual": self._build_visual_query_string,
            "sonic_nl": self._build_sonic_nl_query_string,
            "sonic_nl_enriched": self._build_sonic_nl_enriched_query_string,
            "lyric": self._build_lyric_query_string,
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

        # Expand BOTH track_ids and artist_ids for every resolved rejection,
        # regardless of `er.kind`. The resolver may attach owning-artist ids
        # to a kind="track" rejection (and vice versa); honoring only one
        # side of that pairing here lets step-8 backfill silently re-admit
        # tracks that step-7 `_apply_soft_adjustments` excluded.
        for rej in rs.resolved_rejections.values():
            drop.update(rej.track_ids)
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
