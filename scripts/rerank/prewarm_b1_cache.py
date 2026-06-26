"""Pre-warm the shared embedding cache with the devset b1 (4B v_struct_pt) query
embeddings, keyed by (B1_CACHE_NAMESPACE, build_q text) — exactly the key B1Live's
CachedTextEmbedder looks up at serving. After this, the reranker serves the devset
as pure cache hits (no 16GB model load). Source: q_vstructpt_4b.npy (already the
4B embeddings of INSTRUCT+build_q, in devset.json order).
"""
from __future__ import annotations
import sys, os, json
sys.path.insert(0, "scripts/rerank")
import numpy as np
import build_features as BF
import modal_build_data as MBD
from mcrs.embeddings.embedding_cache import DiskVectorCache, make_key
from b1_live import B1_CACHE_NAMESPACE

QEMB = "exp/analysis/retrieval_exploration/_emb_cache/q_vstructpt_4b.npy"
GT = "exp/ground_truth/devset.json"
DOC_CORPUS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"


def main():
    Q = np.load(QEMB).astype(np.float32)
    Q /= np.maximum(np.linalg.norm(Q, axis=1, keepdims=True), 1e-9)
    order = [(str(r["session_id"]), int(r["turn_number"])) for r in json.load(open(GT))]
    assert len(order) == Q.shape[0], f"order {len(order)} != Q {Q.shape[0]}"
    doc_by = {json.loads(l)["track_id"]: json.loads(l)["doc"] for l in open(DOC_CORPUS)}
    sess = BF.load_sessions()
    store = DiskVectorCache(os.environ.get("MCRS_EMBEDDING_CACHE_DIR", "cache/embeddings"))
    n = miss = 0
    for i, (sid, tn) in enumerate(order):
        s = sess.get(sid)
        if not s:
            miss += 1; continue
        ut = s["user_text_by_turn"]; pl = s["played_by_turn"]
        qt = MBD.build_q("v_struct_pt", ut.get(tn - 1, ""), ut.get(tn, ""),
                         MBD.prev_track_str(pl, tn, doc_by))
        store.set(make_key(B1_CACHE_NAMESPACE, qt), Q[i].tolist())
        n += 1
    print(f"pre-warmed {n} b1 query embeddings (namespace={B1_CACHE_NAMESPACE}); {miss} sessions missing")


if __name__ == "__main__":
    main()
