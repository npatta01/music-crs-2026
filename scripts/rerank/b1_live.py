"""Live b1 (4B v_struct_pt) serving: build the goal-free v_struct_pt query from the
session (raw turns), encode with the local 4B model, and retrieve top-k over the
in-memory catalog b1 doc matrix (cat.vec["b1_vstructpt_4b"]). Produces the dense.b1
branch hits + the query vec for scout_cos — the LIVE equivalent of inject_4b, used
by both lgbm_reranker (online) and replay_lgbm (offline sim).

Single source of truth for the query: scripts.rerank.v_struct_pt_query (the modal-free,
training-exact goal-free renderer). The prev_track 'artist — title' text is derived
straight from the catalog (no doc_corpus.jsonl needed at serving).
"""
from __future__ import annotations
import os
import json
import numpy as np

B1_FIELD = "b1_vstructpt_4b"
# Env-overridable so a cache MISS can load the encoder from the Modal models volume
# (the relative default resolves to /app/models, which is excluded from the image —
# unwarmed/blindset queries would otherwise fail to load and fall back). On Modal set
# MCRS_B1_MODEL_DIR=/root/models/biencoder_variant_v_struct_pt_l2048_qwen3-embedding-4b
# and upload the weights there. (PR #160 review P1)
B1_MODEL = os.environ.get(
    "MCRS_B1_MODEL_DIR", "models/biencoder_variant_v_struct_pt_l2048_qwen3-embedding-4b")
DOC_CORPUS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
# Namespace pins the b1 model identity in the shared embedding cache. Pre-warm
# (prewarm_b1_cache.py) and serving MUST use the same namespace + query text.
B1_CACHE_NAMESPACE = "ft_qwen3_embedding_4b_v_struct_pt_l2048"


def _titles_from_catalog(db_uri: str, table_name: str, VQ) -> dict:
    """{track_id: 'artist — title'} read straight from the lance catalog, byte-identical
    to the b1 doc-corpus rendering (mirrors build_doc_corpus head + short_track; verified
    0/47071 mismatches). Lets serving skip the 23M doc_corpus.jsonl entirely."""
    import lancedb
    tbl = lancedb.connect(db_uri).open_table(table_name)
    df = tbl.search().select(["track_id", "artist_name", "track_name", "release_date"]).limit(0).to_pandas()

    def first(x):
        if isinstance(x, (list, tuple, np.ndarray)):
            return x[0] if len(x) else ""
        return x if x is not None else ""

    out = {}
    for _, r in df.iterrows():
        ar = str(first(r["artist_name"]) or "")
        nm = str(first(r["track_name"]) or "")
        yr = str(r["release_date"] or "")[:4]
        # store the doc HEAD (not the pre-short_track'd title) so prev_track_str's
        # short_track runs exactly once, matching the prewarm/full-doc path even for
        # titles ending in '(YYYY)' (PR #160 review P2).
        out[str(r["track_id"])] = VQ.track_doc_head(ar, nm, yr)
    return out


class B1Live:
    def __init__(self, cat, *, model_name: str = B1_MODEL, device: str = "auto",
                 topk: int = 1000, db_uri: str | None = None,
                 table_name: str = "music_track_catalog", doc_corpus: str = DOC_CORPUS,
                 inner=None):
        import os
        import v_struct_pt_query as VQ  # build_q / short_track / prev_track_str (modal-free, training-exact)
        if device == "auto":  # don't crash on a CPU box (e.g. a cache-miss without a GPU)
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"
        from mcrs.embeddings.embedding_cache import DiskVectorCache, CachedTextEmbedder
        self._mbd = VQ
        self.cat = cat
        self.topk = topk
        # prev_track 'artist — title' map. Primary: derive from the catalog (db_uri) so
        # serving needs NO doc_corpus file (and doesn't crash on Modal, where exp/ is
        # excluded). Fallback: the legacy doc_corpus.jsonl if present locally; else empty
        # (the query just omits [prev_track] — graceful, no crash). short_track is applied
        # at lookup (idempotent on the already-short titles).
        if db_uri:
            # Serving: the catalog MUST yield titles. Fail HARD on error/empty rather
            # than silently degrading — an empty map changes build_q (drops [prev_track])
            # -> different cache key -> cache MISS -> tries to load the 16GB encoder,
            # which is excluded from the Modal image -> crash. A clear error beats a
            # silent wrong-key serve. (codex review)
            self.doc_by = _titles_from_catalog(db_uri, table_name, VQ)
            if not self.doc_by:
                raise RuntimeError(
                    f"b1 catalog title map is empty for {db_uri}/{table_name} — "
                    "refusing to serve (would change cache keys)")
        elif os.path.exists(doc_corpus):
            self.doc_by = {json.loads(l)["track_id"]: json.loads(l)["doc"] for l in open(doc_corpus)}
        else:
            self.doc_by = {}  # offline/tests only (no db_uri, no corpus)
        # Cache-first encoder: the 16GB inner model lazy-loads ONLY on a cache miss.
        # With the devset pre-warmed in this namespace, serving = pure cache hits ->
        # no in-process load, no OOM. `inner` defaults to the local 4B; for Modal/blindset
        # pass a Modal-served b1 client (same v_struct_pt query, same namespace).
        if inner is None:
            from mcrs.embeddings.qwen3_embedding import (
                Qwen3EmbeddingClient, DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS)
            inner = Qwen3EmbeddingClient(
                model_name=model_name, device=device, torch_dtype_name="bfloat16",
                max_length=2048, query_instruct=DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS, batch_size=8)
        cache_dir = os.environ.get("MCRS_EMBEDDING_CACHE_DIR", "cache/embeddings")
        self.enc = CachedTextEmbedder(inner, DiskVectorCache(cache_dir), B1_CACHE_NAMESPACE)
        self.D = cat.vec.get(B1_FIELD)            # (n_docs, 2560), L2-normed
        self.vidx = cat.vec_idx.get(B1_FIELD, {})  # track_id -> row
        self.ids = [None] * len(self.vidx)
        for t_, i in self.vidx.items():
            self.ids[i] = t_

    def query_text(self, sess_entry: dict, tn: int) -> str:
        ut = sess_entry.get("user_text_by_turn", {})
        pl = sess_entry.get("played_by_turn", {})
        return self._mbd.build_q("v_struct_pt", ut.get(tn - 1, ""), ut.get(tn, ""),
                                 self._mbd.prev_track_str(pl, tn, self.doc_by))

    def query_vecs(self, texts: list[str]) -> np.ndarray:
        V = np.asarray(self.enc.embed_batch(texts), dtype=np.float32)
        return V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)

    def branch_hits(self, qvec: np.ndarray, hard_drop=None) -> list[list]:
        s = self.D @ qvec
        if hard_drop:
            for tid in hard_drop:
                i = self.vidx.get(str(tid))
                if i is not None:
                    s[i] = -1e9
        k = min(self.topk, len(s))
        top = np.argpartition(-s, k - 1)[:k]
        top = top[np.argsort(-s[top])]
        return [[self.ids[i], float(s[i])] for i in top]
