# v0+ ConversationState Compiler — Design

Status: `planned` — design doc; LanceDB now implements a shared `Retriever` Protocol, Compiler/Resolver code still to come. **Revision 7** introduces a unified retriever interface shared across all v0+-facing backends.

Changes from rev-6:
- **New `Retriever` Protocol** in [`mcrs/retrieval_modules/base.py`](/mcrs/retrieval_modules/base.py) with `FieldQuery` dataclass, `search(clauses, *, topk)`, `search_embedding(query_vector, *, vector_field, topk, distance_type, filter_missing)`, plus `supported_text_fields` / `supported_vector_fields` introspection properties.
- **BM25 takes a structured query** (`list[FieldQuery]`) instead of per-call atomic primitives. The compiler issues **exactly two retrieval calls per turn**: one `search` with N field clauses + one `search_embedding`. Solr-style. Backend chooses native multi-field execution vs internal weighted-RRF (LanceDB: simulates via per-field FTS + weighted RRF; future Milvus impl could use `_Bm25FieldsSearch` natively).
- **Score normalization at the backend boundary**: every retriever returns "higher = better". Cosine: `similarity = 1 - distance`. L2: `1/(1+distance)`. Inner product: pass-through. The compiler never has to remember which convention each backend uses.
- **`field` is always required** — no defaults. Backends raise `ValueError` if asked for an unsupported field, and callers can introspect via the `supported_*_fields` properties.
- **Milvus retriever left alone** — deprecated per user direction, untouched. Its tests still pass against the legacy API.
- **LanceDB satisfies `Retriever`** as a runtime-checkable Protocol (asserted by a test).

Tests: 17 LanceDB-Protocol unit tests (FieldQuery validation, supported-fields introspection, single-clause and multi-clause search, weighted-RRF dominance, all three distance flips, unknown-field rejection, blank-clause handling, isinstance check). 40/40 retrieval tests pass.

Rev-4 changes (kept): removed stale rev-2 references, resolved pivot/centroid ambiguity (pivot wins, α=0), hedged the "<5%" claim, linked baselines, switched "tested" → "expected", specified popularity-backfill contract, added Evidence/Assumptions/Configs sections.

Rev-3 decisions (kept): (a) LanceDB FTS for BM25, (b) no seed branch, (c) Qwen3-0.6B precomputed for dense text, (d) uniform RRF weights, (e) `qu_modules/` location, (f) LLM caching via existing litellm proxy, no Resolver caching.

Follow-on to [`conversation_state_extraction_bakeoff`](../conversation_state_extraction_bakeoff/README.md) (which picked `gemma-3-12b-it` as the extractor). Pipeline:

```
LLM extractor → ConversationStateV0Plus            (litellm proxy caches the LLM call)
                       ▼
                Resolver                            (deterministic; rejections + same-artist annotation)
                       ▼
                ResolvedConversationState
                       ▼
                Compiler                            (BM25 + dense text, RRF fused with uniform weights)
                       ▼
                top-1000 track_ids
```

Two retrieval branches, not three. The Resolver's role narrowed: it resolves `explicit_rejections` to IDs (so the Compiler's hard-drop is deterministic) and annotates `track_feedback` with `artist_id` (for the same-artist demote). It no longer resolves positive `mentioned_entities` — those go directly into BM25 field channels and into the dense query string, and that's enough.

## Scope

- **In scope**: BM25 with per-field boosts (LanceDB FTS / tantivy), dense-text retrieval (`metadata-qwen3_embedding_0.6b` precomputed), structured catalog filters, deterministic rejection resolution.
- **Out of scope (deferred to v1)**: CLAP audio NN, SigLIP image NN, CF-BPR personalization, attribute / lyrics dense branches, reranker, positive-mention seed inclusion as a third branch.

The deferred items are confirmed-defer per the design doc in [`iteration_1_minimal_schema.md`](../conversation_state_design_v2/iteration_1_minimal_schema.md), per the user's direction to skip audio/image embeddings, and per the rev-3 decision to drop the seed branch.

## Why 2 branches, not 3 or 4

The schema doc's iteration-1 plan proposes BM25 + dense text + CLAP audio + CF-BPR. Rev-2 of this design substituted a `resolved-seed` branch for CLAP + CF. Rev-3 drops the seed branch entirely.

**Why drop the seed branch**: it's largely redundant with **BM25 field-boosting on `artist_name` / `album_name` / `track_name`**. If the user names "Morphine" in the BM25 query and we apply a high field weight on `artist_name`, Morphine tracks land at the top of the BM25 ranking. The dense text branch reinforces this. Adding a third branch that injects Morphine tracks at high seed-rank duplicates a signal already captured by the first two — it would only matter for cases where BM25 *can't* find Morphine (fuzzy spelling, multi-token tokenization quirks).

**Note**: the doc previously claimed this miss rate was "<5% of sessions" — that number is **not backed by a measurement** and has been removed. Whether the seed branch is worth adding is an empirical question we'll answer with per-row diff after the first eval (compare candidate-set membership between the two-branch design and a three-branch ablation).

**If recall@1000 falls short** of the current RRF hybrid ceiling ([`Hit@1000=0.7210`, see retrieval_analysis_findings_2026-04-28.md](../../retrieval_analysis_findings_2026-04-28.md)), the seed branch is the cheapest first add — the Resolver only needs to fuzzy-resolve positive `mentioned_entities` (~30 LOC) and the Compiler adds a third RRF list. CLAP audio and CF-BPR remain the second-wave additions if text-only retrieval saturates.

---

## Resolver — narrowed responsibility

Takes `ConversationStateV0Plus` (surface forms from the LLM) and the catalog; returns a `ResolvedConversationState` with deterministic id annotations for the two things the Compiler needs them for:

1. **Rejection resolution**: surface form like "Fugazi" → list of `artist_id`s → list of `track_id`s to hard-drop.
2. **Same-artist annotation**: for each `track_feedback[i].track_id`, look up the `artist_id` so the Compiler can apply the same-artist demote on rejected tracks.

**Positive `mentioned_entities` are NOT resolved here.** They flow directly into the Compiler's BM25 field channels and dense query string — no Resolver step needed (rev-3 decision; consequence of dropping the seed branch).

**No caching.** Resolution is cheap (rapidfuzz over ~9k unique artists / 47k tracks) and recomputed per call. LLM caching is what matters — the extractor's LLM call is the expensive step, and the existing litellm proxy already caches it on disk per [`infra/litellm/litellm_proxy.openrouter.yaml`](/infra/litellm/litellm_proxy.openrouter.yaml) (`cache: true`, disk-backed under `artifacts/cache/litellm/`).

### `ResolvedConversationState` shape

A wrapper dataclass (not part of the Pydantic LLM schema):
```python
@dataclass
class ResolvedRejection:
    artist_ids: list[str]    # populated when kind == "artist"
    track_ids: list[str]     # populated when kind == "track"

@dataclass
class ResolvedConversationState:
    state: ConversationStateV0Plus                       # original LLM output, unchanged
    resolved_rejections: dict[int, ResolvedRejection]    # index into state.explicit_rejections
    track_feedback_artist_ids: dict[str, str | None]     # track_id -> artist_id
```

The Pydantic `ConversationStateV0Plus` is untouched; the resolution lives in a sidecar struct. LLM contract stays clean.

### Why not put resolved_ids directly on the LLM schema

The schema design doc explicitly defers resolved_ids to v1 to keep the LLM-extracted surface minimal. We honor that. The Resolver is a deterministic post-step that can grow the v0+ pipeline without growing the v0+ schema.

---

## Per-field mapping

How each v0+ field flows through Resolver → Compiler (2 branches now: BM25 + dense text):

| Field | Resolver action | BM25 contribution | Dense-text contribution | Filter contribution |
|---|---|---|---|---|
| `turn_intent` | — | `_default` channel (fans across all fields, weight 1.0) | encoded query vector | — |
| `intent_mode` | — | gates anchor tag expansion (skip on `pivot`) | gates anchor-centroid mixing (α=0 on `pivot`/`open_explore`) | — |
| `track_feedback.role=accepted/seed` (sent=1) | — | query-expand: append top tags from those tracks' `tag_list` | compute anchor centroid from those tracks' metadata vectors | — |
| `track_feedback.role=rejected` (sent=-1) | annotate `artist_id` | — | — | hard drop track_id; soft demote same-`artist_id` tracks |
| `track_feedback.role=neutral` (sent=0) | — | — | — | — (informational; no retrieval effect) |
| `referenced_track_ids` | — | same as accepted anchors | same as accepted anchors | — |
| `mentioned_entities.type=artist` (sent≥0) | — | **field boost** on `artist_name` (weight ×3) | append "artist: X" to encoded string | — |
| `mentioned_entities.type=album` (sent≥0) | — | **field boost** on `album_name` (weight ×2) | append "album: X" | — |
| `mentioned_entities.type=track` (sent≥0) | — | **field boost** on `track_name` (weight ×3) | append "track: X" | — |
| `mentioned_entities.type=tag` (sent≥0) | — | **field boost** on `tag_list` (weight ×1.5) | append "tags: X" | soft promote on tag overlap |
| `mentioned_entities.*` (sent=-1) | covered below | — | — | covered by `explicit_rejections` |
| `hard_filters.release_date` | — | pre-fusion mask | pre-fusion mask | structured WHERE on catalog |
| `explicit_rejections.kind=artist` | fuzzy → `artist_ids` → expand to `track_ids` | — | — | hard drop |
| `explicit_rejections.kind=track` | exact + fuzzy → `track_ids` | — | — | hard drop |
| `explicit_rejections.kind=tag` | — | — | — | soft demote on tag overlap |
| `played_track_ids` (mechanical, not LLM) | — | — | — | hard drop (challenge convention) |
| `user_id`, `user_profile` (mechanical) | — | — | — | unused in v0+ (deferred to CF-BPR branch in v1) |

**What intent_mode still does** (since RRF weights are now uniform): it gates two query-construction switches:
- **Anchor tag expansion in BM25**: skipped on `pivot` (no carryover from rejected direction).
- **Anchor centroid mixing in dense**: α=0 on `pivot` and `open_explore`, α=0.4 on `refinement`, α=0.5 on `playlist_build`.

The "intent_mode shapes the query, fusion is mechanical" split is intentional — keeps fusion debuggable.

---

## Architecture

```
            ConversationStateV0Plus      (LLM extractor output; cached at the litellm proxy)
                       │
                       ▼
              ┌────────────────────┐
              │      Resolver       │    ← rapidfuzz; resolves rejections + annotates tf artist_id
              └────────────────────┘
                       │
                       ▼
            ResolvedConversationState
                       │
                       ▼
              ┌──────────────────────────────────┐
              │   Pre-fusion catalog mask         │
              │   (hard_filters.release_date)     │
              └──────────────────────────────────┘
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
  BM25 branch (LanceDB FTS)      Dense-text branch
  field-weighted query           (Qwen3-0.6B precomputed ANN)
  + anchor tag expansion         + anchor centroid mix
       │                               │
       ▼                               ▼
   top-K=1000                     top-K=1000
       │                               │
       └───────────────┬───────────────┘
                       ▼
              ┌──────────────────────────────────┐
              │   RRF Fusion (k=60)               │
              │   uniform weights (1.0, 1.0)      │
              └──────────────────────────────────┘
                       │
                       ▼
              ┌──────────────────────────────────┐
              │   Post-filters                    │
              │   Hard drops:                     │
              │   - played_track_ids              │
              │   - resolved rejected artist tracks│
              │   - resolved rejected track_ids   │
              │   - track_feedback.role=rejected  │
              │   Soft demote:                    │
              │   - tag overlap with rejected tags│
              │   - same artist_id as rejected tf │
              │   Soft promote:                   │
              │   - tag overlap with positive tags│
              └──────────────────────────────────┘
                       │
                       ▼
                Top-1000 track_ids
                (for submission)
```

Both Resolver and Compiler are **stateless** given their inputs. Caller responsibility: extract state per turn (LLM call hits the proxy cache when the input is unchanged), run Resolver, then call the Compiler.

---

## Branch specifications

### Branch A — BM25 via LanceDB FTS (single structured-query call)

**Backend**: [`mcrs/lancedb/`](/mcrs/lancedb/) — `lancedb>=0.30.2` per [`pyproject.toml`](/pyproject.toml). Tantivy underneath. The retriever implements the shared `Retriever` Protocol from [`mcrs/retrieval_modules/base.py`](/mcrs/retrieval_modules/base.py); the compiler talks to it via `retriever.search(clauses, topk=...)`.

**One BM25 call per turn**: the compiler builds a `list[FieldQuery]` (Solr-style) and issues a single `search()`. The backend executes per-field FTS internally and fuses with weighted RRF (LanceDB) or runs a native multi-field BM25 query (future Milvus impl). Compiler doesn't care which.

**Document fields indexed** (per-track):
- `track_name` (text)
- `artist_name` (text)
- `album_name` (text)
- `tag_list` (text, space-joined)
- `release_date` (date — for filter, not BM25 scoring)

**Query construction** (compiler-side, single call):
```python
from mcrs.retrieval_modules.base import FieldQuery

clauses = [
    FieldQuery("artist_name", " ".join(positive_artist_mentions),                     boost=3.0),
    FieldQuery("album_name",  " ".join(positive_album_mentions),                      boost=2.0),
    FieldQuery("track_name",  " ".join(positive_track_mentions + [state.turn_intent]),boost=3.0),
    FieldQuery("tag_list",    " ".join(positive_tag_mentions
                                       + anchor_tag_expansion
                                       + [state.turn_intent]),                         boost=1.5),
]
# Blank-query clauses are silently dropped inside the retriever — no compiler-side filter needed.

bm25_hits = retriever.search(clauses, topk=1000)  # list[(track_id, score)], higher = better
```

One call, four field channels, backend-decided execution. Result is one ranked pool the compiler later RRF-fuses with the dense pool.

**Why route `turn_intent` to `track_name` and `tag_list`**: those are the fields where free-text vocabulary ("smoky", "80s", "anthemic", "Clair de lune") tends to find matches. Pushing `turn_intent` into `artist_name` would invite false positives ("Beat" the verb → "Beatles"). Pushing it into `album_name` adds noise (album titles rarely contain mood/era words). The split keeps the artist channel surgical.

**Anchor tag expansion**: from `track_feedback.role in {accepted, seed}` and `referenced_track_ids`, look up each track's `tag_list` in the catalog. Take the top-N most-frequent tags across the anchor set (N=5 default). These tags are appended to the `tag_list` channel.

**Pivot handling**: when `intent_mode == "pivot"`, **skip** the anchor tag expansion (the rejected direction's tags shouldn't carry over). The `mentioned_entities` channels still fire if the user re-named entities in the latest turn; the LLM extractor decides what to carry forward.

**Empty-channel handling**: the retriever's `text_to_item_retrieval_channels` silently skips channels with empty/whitespace queries. So if the user names no artist, the `artist_name` channel is just absent from fusion — no special-case needed in the compiler.

### Branch B — Dense text

Uses the precomputed `metadata-qwen3_embedding_0.6b` vectors from the challenge's [`TalkPlayData-Challenge-Track-Embeddings`](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Track-Embeddings) dataset (1024-dim, 47k tracks). These are wired into LanceDB as the `metadata_qwen3_embedding_0_6b` column (column-name dots → underscores, per [`milvus_safe_field_name`](/mcrs/milvus/indexing.py)) and accessible via the retriever's `dense_vector` search kind.

**Query encoding**:
```
{turn_intent}; like: {artist_1}, {artist_2}; tags: {tag_1}, {tag_2}
```
Encoded with the same Qwen3-Embedding-0.6B model used for the catalog (consistency matters; mixing 0.6B and 8B vectors won't work directly).

**Anchor centroid mixing**: when `intent_mode != "pivot"` and there are accepted-anchor tracks, compute the mean of their `metadata-qwen3` vectors and mix into the query:
```
final_query_vec = (1 - α) * encode(query_string) + α * normalize(centroid)
```
where `α = 0.4` for `refinement`, `α = 0.5` for `playlist_build`, `α = 0` for `pivot` and `open_explore`.

**ANN**: cosine similarity, top-K=1000.

### (Branch C dropped in rev-3)

The seed branch is intentionally not part of v0+ iteration 1. See [§ Why 2 branches](#why-2-branches-not-3-or-4) for the reasoning. If recall@1000 falls short of the current RRF hybrid ceiling (`Hit@1000=0.7210`), re-enabling it is the smallest first add — the Resolver only needs to fuzzy-resolve positive `mentioned_entities`, and the Compiler adds a third RRF list. ~30 lines of code.

---

## Fusion: RRF with uniform weights

Reciprocal Rank Fusion ([Cormack et al. 2009](https://www.cs.uic.edu/~ifc/courses/CS583/papers/cormack09rrf.pdf)), `k=60` (canonical default; not tuned). Two branches, **equal weights**:

```
score(track) = 1 / (k + rank_bm25(track)) + 1 / (k + rank_dense(track))
```

Rev-3 decision: **no intent_mode-conditioned RRF weights**. Reasons:

- The two-branch case has fewer degrees of freedom — weight differences matter less.
- intent_mode already shapes the query upstream (anchor tag expansion gated by mode; centroid α set by mode). Layering fusion-weight differentiation on top would double-count the same signal.
- Uniform weights are debuggable: per-branch rank for a given track is easy to inspect; weighted contributions are harder to reason about.

If devset eval shows one branch consistently dominating in a way that hurts a specific intent_mode, intent-conditioned weights are a small follow-up.

---

## Filters

### Pre-fusion (mask both retrieval pools)

- **`hard_filters.release_date`** — translate to catalog `release_date BETWEEN/_</_>` constraint. Applied as a candidate-id mask before BM25 and ANN, so each branch only ranks within the valid set.

### Post-fusion hard drops (remove from final list)

- `track_id in state.played_track_ids` — challenge convention: never re-recommend a played track.
- `track_id in {er.value for er in state.explicit_rejections if er.kind == "track"}` — direct title-resolved drops.
- `artist_id in resolved_rejected_artists` — from `explicit_rejections.kind == "artist"`, resolved via fuzzy match against catalog `artist_name`.
- `track_id in {tf.track_id for tf in state.track_feedback if tf.role == "rejected"}` — per-track negative anchor.

### Post-fusion soft demotes (multiplier on fused score)

- **Tag rejections**: for each track `t`, count overlap between `t.tag_list` and `{er.value for er in state.explicit_rejections if er.kind == "tag"}`. Multiplier: `0.5 ** overlap_count` (each overlapping tag halves the score).
- **Same-artist as rejected tracks**: tracks sharing `artist_id` with rejected `track_feedback` get a one-time `× 0.7` demote.

### Soft promotes (multiplier on fused score)

- **Tag overlap with positive `mentioned_entities[type=tag]`**: multiplier `1.0 + 0.15 * overlap_count` (each overlapping tag adds 15%).

The promote/demote multipliers are deliberately small (within 0.3–1.5×) so they re-rank within the top-1000 but don't pull obscure tracks up from the long tail (which would inflate false positives).

---

## Pseudocode

### Resolver (`mcrs/qu_modules/resolver_v0plus.py`)

```python
from dataclasses import dataclass, field
from rapidfuzz import process, fuzz
from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    ConversationStateV0Plus,
)


@dataclass
class ResolvedRejection:
    artist_ids: list[str] = field(default_factory=list)
    track_ids: list[str] = field(default_factory=list)


@dataclass
class ResolvedConversationState:
    state: ConversationStateV0Plus
    resolved_rejections: dict[int, ResolvedRejection]      # idx into state.explicit_rejections
    track_feedback_artist_ids: dict[str, str | None]       # track_id -> artist_id


class V0PlusResolver:
    """Resolves only what the Compiler needs: rejections + tf artist annotation."""

    def __init__(self, catalog, score_cutoff: int = 80):
        self.catalog = catalog
        self.cutoff = score_cutoff

    def resolve(self, state: ConversationStateV0Plus) -> ResolvedConversationState:
        resolved_rejections = {
            i: self._resolve_rejection(er.kind, er.value)
            for i, er in enumerate(state.explicit_rejections)
            if er.kind in ("artist", "track")
        }
        tf_artists = {
            tf.track_id: self.catalog.artist_id_of(tf.track_id)
            for tf in state.track_feedback
        }
        return ResolvedConversationState(
            state=state,
            resolved_rejections=resolved_rejections,
            track_feedback_artist_ids=tf_artists,
        )

    def _resolve_rejection(self, kind: str, value: str) -> ResolvedRejection:
        out = ResolvedRejection()
        if kind == "artist":
            for name, _score, _ in process.extract(
                value, self.catalog.artist_names,
                scorer=fuzz.token_set_ratio, limit=20, score_cutoff=self.cutoff,
            ):
                out.artist_ids.append(self.catalog.artist_id_of_name(name))
        elif kind == "track":
            for name, _score, _ in process.extract(
                value, self.catalog.track_names,
                scorer=fuzz.token_set_ratio, limit=5, score_cutoff=self.cutoff,
            ):
                out.track_ids.append(self.catalog.track_id_of_name(name))
        return out
```

### Compiler (`mcrs/qu_modules/compiler_v0plus.py`)

```python
@dataclass
class CompilerConfig:
    bm25_k: int = 1000
    dense_k: int = 1000
    rrf_k: int = 60
    centroid_alpha: dict[str, float] = field(default_factory=lambda: {
        "refinement": 0.4, "playlist_build": 0.5, "pivot": 0.0, "open_explore": 0.0,
    })
    field_boosts: dict[str, float] = field(default_factory=lambda: {
        "track_name": 3.0, "artist_name": 3.0, "album_name": 2.0, "tag_list": 1.5,
    })


class V0PlusCompiler:
    def __init__(self, catalog, bm25_index, ann_index, encoder, config=CompilerConfig()):
        self.catalog = catalog
        self.bm25 = bm25_index       # LanceDB FTS with per-field weights
        self.ann = ann_index         # ANN over precomputed metadata-qwen3_embedding_0.6b
        self.encoder = encoder       # Qwen3-Embedding-0.6B (matches the catalog vectors)
        self.cfg = config

    def compile(self, rs: ResolvedConversationState) -> list[str]:
        state = rs.state

        # 1. Pre-fusion catalog mask from hard_filters
        candidate_mask = self._release_date_mask(state.hard_filters)

        # 2. Build queries
        bm25_clauses = self._build_bm25_clauses(rs)          # list[FieldQuery]
        dense_vec    = self._build_dense_query(rs)           # encoded + centroid-mixed

        # 3. Exactly TWO retrieval calls per turn
        bm25_hits  = self.retriever.search(bm25_clauses, topk=self.cfg.bm25_k)
        dense_hits = self.retriever.search_embedding(
            query_vector=dense_vec,
            vector_field="metadata_qwen3_embedding_0_6b",
            topk=self.cfg.dense_k,
        )

        # Post-hoc filter to candidate_mask (current retriever doesn't accept ID masks)
        bm25_hits  = [(t, s) for t, s in bm25_hits  if t in candidate_mask]
        dense_hits = [(t, s) for t, s in dense_hits if t in candidate_mask]

        scored_lists = [(bm25_hits, 1.0), (dense_hits, 1.0)]

        # 4. Hard-drop set (uses resolved IDs from Resolver — no fuzzy match here)
        hard_drop = self._hard_drop_set(rs)

        # 5. Filter each pool of (track_id, score) tuples
        scored_lists = [
            ([(t, s) for t, s in lst if t not in hard_drop], w)
            for lst, w in scored_lists
        ]

        # 6. Weighted RRF fusion — compiler-owned, retriever stays atomic
        fused = self._rrf_fuse(scored_lists, k=self.cfg.rrf_k)

        # 7. Soft demotes / promotes
        fused = self._apply_soft_adjustments(fused, rs)

        # 8. Return top-1000
        return [tid for tid, _score in fused[:1000]]

    def _build_bm25_clauses(self, rs) -> list[FieldQuery]:
        """Build the Solr-style list of (field, query, boost) clauses for the
        single BM25 call. Blank clauses are dropped inside the retriever; we
        include them here so the structure stays predictable."""
        state = rs.state
        from collections import defaultdict
        per_field: dict[str, list[str]] = defaultdict(list)

        for me in state.mentioned_entities:
            if me.sentiment < 0:
                continue
            if me.type == "artist":
                per_field["artist_name"].append(me.value)
            elif me.type == "album":
                per_field["album_name"].append(me.value)
            elif me.type == "track":
                per_field["track_name"].append(me.value)
            elif me.type == "tag":
                per_field["tag_list"].append(me.value)

        if state.intent_mode.value != "pivot":
            per_field["tag_list"].extend(self._top_anchor_tags(rs, n=5))

        # turn_intent: route where mood/title vocabulary tends to match;
        # avoid artist_name ("Beat" → "Beatles" false pos) and album_name.
        intent = state.turn_intent.strip()
        if intent:
            per_field["track_name"].append(intent)
            per_field["tag_list"].append(intent)

        return [
            FieldQuery(
                field=field,
                query=" ".join(terms).strip(),
                boost=self.cfg.field_boosts.get(field, 1.0),
            )
            for field, terms in per_field.items()
        ]

    def _build_dense_query(self, rs):
        state = rs.state
        text_parts = [state.turn_intent]
        artists = [me.value for me in state.mentioned_entities
                   if me.sentiment >= 0 and me.type == "artist"]
        tags = [me.value for me in state.mentioned_entities
                if me.sentiment >= 0 and me.type == "tag"]
        if artists:
            text_parts.append("like: " + ", ".join(artists))
        if tags:
            text_parts.append("tags: " + ", ".join(tags))
        query_vec = self.encoder.encode("; ".join(text_parts))

        # anchor centroid mixing (intent_mode controls α)
        anchor_tids = self._anchor_track_ids(state)
        alpha = self.cfg.centroid_alpha[state.intent_mode.value]
        if alpha > 0 and anchor_tids:
            centroid = self.catalog.metadata_vector_mean(anchor_tids)
            query_vec = (1 - alpha) * query_vec + alpha * normalize(centroid)
        return normalize(query_vec)

    def _hard_drop_set(self, rs):
        state = rs.state
        drop = set(state.played_track_ids)
        for tf in state.track_feedback:
            if tf.role == "rejected":
                drop.add(tf.track_id)
        # use Resolver's resolved IDs
        for i, rej in rs.resolved_rejections.items():
            er = state.explicit_rejections[i]
            if er.kind == "track":
                drop.update(rej.track_ids)
            elif er.kind == "artist":
                for aid in rej.artist_ids:
                    drop.update(self.catalog.tracks_by_artist_id(aid))
        return drop

    def _apply_soft_adjustments(self, fused, rs):
        state = rs.state
        rejected_tags = {er.value.lower() for er in state.explicit_rejections if er.kind == "tag"}
        positive_tags = {me.value.lower() for me in state.mentioned_entities
                         if me.sentiment > 0 and me.type == "tag"}
        rejected_artist_ids = {
            rs.track_feedback_artist_ids[tf.track_id]
            for tf in state.track_feedback if tf.role == "rejected"
            if rs.track_feedback_artist_ids.get(tf.track_id) is not None
        }

        adjusted = []
        for tid, score in fused:
            tags = {t.lower() for t in self.catalog.tag_list(tid)}
            mult = 0.5 ** len(tags & rejected_tags)
            mult *= 1.0 + 0.15 * len(tags & positive_tags)
            if self.catalog.artist_id_of(tid) in rejected_artist_ids:
                mult *= 0.7
            adjusted.append((tid, score * mult))
        adjusted.sort(key=lambda x: -x[1])
        return adjusted

    def _rrf_fuse(self, scored_lists_with_weights, k):
        """Weighted RRF over N pools. Each pool is (list[(id, score)], weight)."""
        scores = {}
        for ranked, w in scored_lists_with_weights:
            for rank, (tid, _score) in enumerate(ranked):
                scores[tid] = scores.get(tid, 0.0) + w / (k + rank + 1)
        return sorted(scores.items(), key=lambda x: -x[1])
```

Key behavioral differences vs rev-2: dropped seed branch and its Resolver work; Compiler `_rrf_fuse` takes plain lists (no weights); CompilerConfig drops `fusion_weights`.

---

## Edge cases and failure modes

| Case | Behavior | Mitigation |
|---|---|---|
| Empty `turn_intent` | BM25 has no query string | Should not happen — Pydantic field is required. If it slips through, fall back to a concatenation of `played_track_labels` + positive `mentioned_entities.value`. **Expected behavior**, not yet tested (no code). |
| All filters reject everything | Final list short of 1000 | Backfill from a popularity-sorted catalog list — **still respecting** `hard_filters.release_date` mask AND the hard-drop set (played + rejected). Backfill never bypasses filters; it only fills gaps. Log warning if the post-filter mask is itself < 1000 tracks (means user's constraints are unsatisfiable; we return the largest valid subset followed by `null`-padded entries flagged as filler). |
| `mentioned_entities` empty AND `track_feedback` empty | Compiler degenerates to "BM25 + dense text on `turn_intent` only" | Expected behavior for cold-start turns. Will be smoke-tested in unit tests on synthetic states. |
| `intent_mode == pivot` AND `referenced_track_ids` populated | The user is pivoting away from a direction while still pointing at a specific prior track | **Pivot wins** (rev-4 decision). Dense centroid α=0; BM25 anchor tag expansion skipped. The `referenced_track_ids` annotation in this case is treated as informational — the compiler does not use it as an anchor. Rationale: if the user wanted to keep the track as an anchor, they wouldn't have signaled pivot. If post-eval shows this is the wrong call (e.g. extractor mis-labels mode as pivot when user is actually referencing), we revisit. |
| Centroid computation when some anchor tracks have empty metadata vectors | Mean over remaining; if all empty, skip mixing | Handled by `metadata_vector_mean` returning None |
| `hard_filters.release_date` value parsing error | Skip filter | Catalog interface is permissive — invalid filter logged and dropped, query proceeds without it |
| Resolver fuzzy match misfires (e.g. "Beat" → "Beatles") | Bad track-id gets hard-dropped | Resolver uses `score_cutoff=80` token-set ratio; should be high enough to reject most cross-token false positives. Worth a sample-based audit on the dev split. |

---

## Validation plan (Step 1)

Once code lands, validate on `test` split (1000 sessions × 8 turns = 8000 retrieval calls).

| Metric | Bar | Source for the bar |
|---|---|---|
| `Hit@1000` ≥ 0.7210 | floor — anything lower regresses | [retrieval_analysis_findings_2026-04-28.md](../../retrieval_analysis_findings_2026-04-28.md) — RRF(bm25_with_tags, dense_qwen3_8b) |
| `Hit@1000` ≥ 0.75 | target — meaningful lift from anchor preservation | aspirational, no prior baseline |
| `NDCG@20` ≥ 0.1092 | floor | [bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md](../../bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md) — best LLM rewrite |
| `NDCG@20` ≥ 0.12 | target | aspirational |
| Per-branch ablation: BM25-only vs dense-only vs fused | sanity — fused should beat both individuals | — |
| Per-intent_mode slice: `pivot` turns | diagnostic — `pivot` is where rewrite wave was breaking | per [`iteration_1_minimal_schema.md`](../conversation_state_design_v2/iteration_1_minimal_schema.md) (~11% prevalence) |
| Resolver fuzzy-match audit | spot-check 50 resolutions for false positives ("Beat"→"Beatles" type) | — |

Failure modes to watch:
- Anchor centroid drifts queries toward over-similar tracks (low diversity).
- Resolver fuzzy match over-fires (resolves a partial word to a famous artist).
- Soft demotes over-penalize neutral tracks (a popular track shares a rejected tag and disappears unfairly).
- BM25 single-query-string approach causes turn_intent vocabulary to leak into wrong fields (e.g. "Beat" the verb matches `artist_name`).

## Evidence referenced

This is everything in the doc that's claimed with a number or a strong assertion:

| Claim | Source |
|---|---|
| Current RRF hybrid `Hit@1000 = 0.7210` | [retrieval_analysis_findings_2026-04-28.md](../../retrieval_analysis_findings_2026-04-28.md) and [`experiments/README.md` Current Bests](../../README.md) |
| Best LLM rewrite `NDCG@20 = 0.1092` | [bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md](../../bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md) |
| Best dense baseline `NDCG@20 = 0.1025` (Qwen3-Embedding-8B) | [dense_qwen3_embedding_8b_devset.md](../../dense_qwen3_embedding_8b_devset.md) |
| Best sparse baseline `Hit@1000 = 0.6311` (bm25 + tag_list) | [bm25_devset_retrieval_only_with_tag_list.md](../../bm25_devset_retrieval_only_with_tag_list.md) |
| LanceDB FTS is the chosen BM25 backend | [`mcrs/lancedb/retriever.py`](/mcrs/lancedb/retriever.py); `lancedb_fts_with_tag_list_devset` (`done`) status in [`experiments/README.md`](../../README.md) |
| `metadata-qwen3_embedding_0.6b` available precomputed (1024-dim, 47k tracks) | [TalkPlayData-Challenge-Track-Embeddings](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Track-Embeddings) per [`docs/data.md`](../../../docs/data.md) |
| Extractor pick `gemma-3-12b-it` | [`conversation_state_extraction_bakeoff/README.md`](../conversation_state_extraction_bakeoff/README.md) (`analyzed`) |
| `intent_mode` distributions and ~11% pivot prevalence | [`iteration_1_minimal_schema.md`](../conversation_state_design_v2/iteration_1_minimal_schema.md) |
| `<5% of sessions` BM25-misses-fuzzy claim | **Removed** in rev-4 — no measured artifact backs it |

## Known assumptions (worth verifying before code)

| Assumption | Why it might be wrong | Verification |
|---|---|---|
| The new `text_to_item_retrieval_channels` correctly routes each channel's query to ONLY that field | Implementation bug or tantivy quirk could leak | Covered by `test_channel_retrieval_routes_queries_to_correct_fields`; also spot-check on 10 real turns post-implementation |
| Qwen3-Embedding-0.6B is callable at query time with the same tokenizer/normalization as the precomputed catalog vectors | If query encoding differs from catalog encoding, cosine similarity is meaningless | Encode 5 catalog track strings and compare to their precomputed vectors; cosine should be ≥0.99 |
| `mcrs/lancedb/retriever.py` accepts a candidate-id mask for pre-filtering | Current retriever may only support `where` clauses, not arbitrary id sets | Read the retriever or write a 10-line probe. If unsupported, fall back to post-filter (more wasted top-K slots but functional) |
| Popularity backfill respects all hard drops + filters | Easy to write a buggy backfill that bypasses filters | Unit test: confirm backfill output ⊆ (mask ∖ hard_drop) |
| `track_feedback.role=neutral` correctly has no retrieval effect | Could leak into BM25/dense expansion logic by accident | Unit test: state with only neutral feedback yields the same compile output as state with no feedback |

---

## Decisions made (rev-3)

| Question | Decision |
|---|---|
| BM25 backend | LanceDB FTS (tantivy underneath, per-field weights via `query_builder.weights`) |
| Seed branch | Dropped — redundant with BM25 field-boosting; reinstate if recall@1000 falls short |
| Encoder for dense branch | Precomputed `metadata-qwen3_embedding_0.6b` (no re-index, free) |
| Code location | `mcrs/qu_modules/resolver_v0plus.py` + `mcrs/qu_modules/compiler_v0plus.py` |
| RRF weights | Uniform (1.0, 1.0) — intent_mode shapes query, not fusion |
| Resolver caching | None — rapidfuzz is cheap, recompute per call |
| LLM caching | Handled by the existing litellm proxy (`cache: true`, disk-backed at `artifacts/cache/litellm/`) |

## Remaining open questions

1. **Stage B response generation — separate module or part of compiler?** Recommend separate (`mcrs/lm_modules/response_v0plus.py`) since it consumes the Compiler's output + the resolved state, not the raw LLM state. Single-responsibility.

2. **Multi-segment sessions (intent_mode changed mid-conversation).** v0+ uses last-turn `intent_mode` only. A pivot in turn 4 followed by a refinement in turn 5 means `intent_mode=refinement` keeps all prior anchors — including the ones the user pivoted away from. Open: do we need a hidden "segment id" tracking the most recent pivot? Or live with it for iteration 1 and revisit if multi-pivot sessions evaluate poorly?

3. **Reranker.** Per the iteration-1 plan, deferred until we know NDCG@20 is the bottleneck. Confirm.

---

## What I'll build next (if you greenlight this design)

1. `mcrs/qu_modules/resolver_v0plus.py` — the Resolver per the pseudocode above.
2. `mcrs/qu_modules/compiler_v0plus.py` — the Compiler per the pseudocode above.
3. `tests/test_resolver_v0plus.py` — unit tests on synthetic states (rejection resolution, fuzzy-match cutoff behavior, track-feedback artist annotation).
4. `tests/test_compiler_v0plus.py` — unit tests on synthetic states (pivot disables centroid, BM25 query construction handles all field types, hard-drop set is correct, backfill respects filters).
5. `configs/v0plus_compiler_devset.yaml` — config for the unified `run_experiment.py` runner.
6. `experiments/analysis/conversation_state_compiler_v0plus/results.md` — devset eval with per-branch ablation and per-intent_mode slice.

### Concrete run + eval commands (target)

```bash
# Local devset run with the Gemma 3 12B extractor + LanceDB BM25 + Qwen 0.6B dense
python run_experiment.py --backend modal --tid v0plus_compiler_devset --batch_size 16

# Predictions land at:
#   exp/inference/devset/v0plus_compiler_devset.json

# Score:
python evaluator/evaluate_devset.py --tid v0plus_compiler_devset
# Writes:
#   evaluator/exp/scores/devset/v0plus_compiler_devset.json
```

### Skeleton of `configs/v0plus_compiler_devset.yaml`

```yaml
lm_type: "litellm"
lm_kwargs:
  model_name: "openai/gpt-5.4-nano"  # response generation only; extraction handled separately
qu_type: "v0plus_compiler"
qu_kwargs:
  extractor_model: "openrouter/google/gemma-3-12b-it"  # winner of the extraction bakeoff
  resolver:
    score_cutoff: 80
  compiler:
    bm25_k: 1000
    dense_k: 1000
    rrf_k: 60
    field_boosts:
      track_name: 3.0
      artist_name: 3.0
      album_name: 2.0
      tag_list: 1.5
    centroid_alpha:
      refinement: 0.4
      playlist_build: 0.5
      pivot: 0.0
      open_explore: 0.0
retrieval_type: "lancedb"
retrieval_config:
  searches:
    - { name: "bm25_fields", kind: "fts_fields", weight: 1.0, topk: 1000,
        fields: [
          { name: "track_name",  weight: 3.0 },
          { name: "artist_name", weight: 3.0 },
          { name: "album_name",  weight: 2.0 },
          { name: "tag_list",    weight: 1.5 },
        ] }
    - { name: "dense_metadata", kind: "dense_vector", weight: 1.0, topk: 1000,
        vector_field: "metadata_qwen3_embedding_0_6b", distance_type: "cosine" }
test_dataset_name: "talkpl-ai/TalkPlayData-Challenge-Dataset"
item_db_name:      "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
user_db_name:      "talkpl-ai/TalkPlayData-Challenge-User-Metadata"
track_split_types: ["all_tracks"]
user_split_types:  ["all_users"]
retrieval_topk: 1000
```

### Expected artifacts (paths a reviewer can verify after the run)

| Path | What |
|---|---|
| `exp/inference/devset/v0plus_compiler_devset.json` | Predictions per (session_id, turn_number) |
| `evaluator/exp/scores/devset/v0plus_compiler_devset.json` | Hit@1000, NDCG@20, MRR, MAP |
| `experiments/v0plus_compiler_devset.md` | Per-run report (per the experiments/CLAUDE.md convention) |
| `experiments/analysis/conversation_state_compiler_v0plus/results.md` | This package's analysis: per-branch ablation, per-intent_mode slice, Resolver false-positive audit |
| `experiments/analysis/conversation_state_compiler_v0plus/artifacts/branch_ablation.json` | Per-branch metrics for ablation discussion |

Estimated effort: ~1 day for Resolver + Compiler + tests; eval run is ~1 hour on Modal.

---

## Files in this package

```
conversation_state_compiler_v0plus/
└── README.md                  this file — design doc
```

Will accrue:
- `decisions.md` (open questions resolved → here)
- `results.md` (after first devset run)
- `artifacts/` (per-branch scores, ablation tables)
