"""Add b1_cos (4B v_struct_pt b1 cosine) to a feature dataset using the CACHED 4B embeddings.

No model reload: b1_cos[(turn, candidate)] = Q[turn] . D[candidate], where Q/D are the cached
L2-normed v_struct_pt 4B query/doc embeddings (exact same query construction the 4B was evaluated with).
Query order = trace turns WITH gt, in fresh-trace order (matches retrieval_diagnostic_4b / inject_4b).
"""
from __future__ import annotations
import argparse, json, os
import numpy as np
import pyarrow as pa
import pyarrow.dataset as pds
import pyarrow.parquet as pq

DOCS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
DOCEMB = "exp/analysis/retrieval_exploration/_emb_cache/docs_vstructpt_4b.npy"
QEMB = "exp/analysis/retrieval_exploration/_emb_cache/q_vstructpt_4b.npy"
GT_FILE = "exp/ground_truth/devset.json"
TRACE = "exp/inference/devset/state_ranker_v10_lgbm_devset_fastlocal_trace.jsonl"
CHUNK = 100_000


def l2(a):
    return a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    tids = [json.loads(l)["track_id"] for l in open(DOCS)]
    tidx = {str(t): i for i, t in enumerate(tids)}
    gt = {(str(r["session_id"]), int(r["turn_number"])) for r in json.load(open(GT_FILE))}
    keys = []
    for line in open(TRACE):
        if not line.strip():
            continue
        r = json.loads(line); k = (str(r["session_id"]), int(r["turn_number"]))
        if k in gt:
            keys.append(k)
    D = l2(np.load(DOCEMB).astype(np.float32))
    Q = l2(np.load(QEMB).astype(np.float32))
    assert len(keys) == Q.shape[0], f"keys {len(keys)} != Q {Q.shape[0]}"
    qidx = {k: i for i, k in enumerate(keys)}
    print(f"docs {D.shape} queries {Q.shape} keys {len(keys)}", flush=True)

    ds = pds.dataset(a.features)
    os.makedirs(a.out, exist_ok=True)
    n_rows = n_miss_q = n_miss_d = 0
    for fi, frag in enumerate(ds.get_fragments()):
        df = frag.to_table().to_pandas()
        sid = df["session_id"].astype(str).values
        tn = df["turn_number"].astype("int64").values
        trk = df["track_id"].astype(str).values
        qi = np.fromiter((qidx.get((s, int(t)), -1) for s, t in zip(sid, tn)), dtype=np.int64, count=len(df))
        ti = np.fromiter((tidx.get(t, -1) for t in trk), dtype=np.int64, count=len(df))
        valid = (qi >= 0) & (ti >= 0)
        n_miss_q += int((qi < 0).sum()); n_miss_d += int((ti < 0).sum())
        sc = np.full(len(df), np.nan, dtype=np.float32)
        qg = np.where(qi < 0, 0, qi); tg = np.where(ti < 0, 0, ti)
        for s0 in range(0, len(df), CHUNK):
            e = min(s0 + CHUNK, len(df))
            sc[s0:e] = np.einsum("ij,ij->i", Q[qg[s0:e]], D[tg[s0:e]]).astype(np.float32)
        sc[~valid] = np.nan
        df["b1_cos"] = sc
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False),
                       os.path.join(a.out, f"part-{fi:05d}.parquet"))
        n_rows += len(df)
        print(f"  frag {fi}: {len(df)} rows  b1_cos mean={np.nanmean(sc):.4f}", flush=True)
    print(f"DONE {a.out}: {n_rows} rows, missing_q={n_miss_q} missing_d={n_miss_d}", flush=True)


if __name__ == "__main__":
    main()
