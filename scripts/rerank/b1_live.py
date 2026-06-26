"""Live b1 (4B v_struct_pt) serving: build the goal-free v_struct_pt query from the
session (raw turns), encode with the local 4B model, and retrieve top-k over the
in-memory catalog b1 doc matrix (cat.vec["b1_vstructpt_4b"]). Produces the dense.b1
branch hits + the query vec for scout_cos — the LIVE equivalent of inject_4b, used
by both lgbm_reranker (online) and replay_lgbm (offline sim).

Single source of truth for the query: scripts.rerank.modal_build_data.build_q (the
exact goal-free renderer the 4B was trained on).
"""
from __future__ import annotations
import json
import numpy as np

B1_FIELD = "b1_vstructpt_4b"
B1_MODEL = "models/biencoder_variant_v_struct_pt_l2048_qwen3-embedding-4b"
DOC_CORPUS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
# Namespace pins the b1 model identity in the shared embedding cache. Pre-warm
# (prewarm_b1_cache.py) and serving MUST use the same namespace + query text.
B1_CACHE_NAMESPACE = "ft_qwen3_embedding_4b_v_struct_pt_l2048"


class B1Live:
    def __init__(self, cat, *, model_name: str = B1_MODEL, device: str = "cuda",
                 topk: int = 1000, doc_corpus: str = DOC_CORPUS, inner=None):
        import os
        import modal_build_data as MBD  # build_q / short_track / prev_track_str (training-exact)
        from mcrs.embeddings.embedding_cache import DiskVectorCache, CachedTextEmbedder
        self._mbd = MBD
        self.cat = cat
        self.topk = topk
        self.doc_by = {json.loads(l)["track_id"]: json.loads(l)["doc"] for l in open(doc_corpus)}
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
