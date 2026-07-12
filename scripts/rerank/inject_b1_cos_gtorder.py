"""Inject real b1_cos into a feature dataset using CACHED 4B v_struct_pt embeddings,
keyed by GROUND-TRUTH-FILE order (the authoritative mapping used by
features.load_b1_query_vectors), NOT trace order.

Why not scripts/rerank/scout_from_cache.py: that script keys the cached query
matrix Q positionally against a specific trace's gt-filtered turns. When the
on-disk trace is a partial smoke (or simply a different run than the one Q was
built from), its `assert len(keys)==Q.shape[0]` fails or the per-row b1_cos gets
scrambled. The cached q_vstructpt_4b.npy was built in devset.json row order
(Q[i] <-> gt_rows[i]); this script honors that, so it is trace-order independent
and joins to feature rows by (session_id, turn_number).

b1_cos[(turn, candidate)] = Qn[(sid,tn)] . Dn[candidate]
  Qn/Dn = L2-normed cached 4B query/doc vectors. Missing turn or candidate -> NaN.
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
CHUNK = 100_000


def l2(a):
    return a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True, help="input feature dataset dir/parquet")
    ap.add_argument("--out", required=True, help="output dir for parquet shards")
    ap.add_argument("--docs", default=DOCS)
    ap.add_argument("--doc-emb", default=DOCEMB)
    ap.add_argument("--q-emb", default=QEMB)
    ap.add_argument("--gt-file", default=GT_FILE)
    a = ap.parse_args()

    tids = [json.loads(l)["track_id"] for l in open(a.docs)]
    tidx = {str(t): i for i, t in enumerate(tids)}
    D = l2(np.load(a.doc_emb).astype(np.float32))
    Q = l2(np.load(a.q_emb).astype(np.float32))

    # authoritative key order: devset.json row i <-> Q[i]
    gt_rows = json.load(open(a.gt_file))
    assert len(gt_rows) == Q.shape[0], f"gt rows {len(gt_rows)} != Q {Q.shape[0]}"
    qidx = {(str(r["session_id"]), int(r["turn_number"])): i for i, r in enumerate(gt_rows)}
    print(f"docs {D.shape} queries {Q.shape} gt_keys {len(qidx)}", flush=True)

    ds = pds.dataset(a.features)
    os.makedirs(a.out, exist_ok=True)
    n_rows = n_miss_q = n_miss_d = 0
    nan_cos_sum = 0.0
    n_valid = 0
    for fi, frag in enumerate(ds.get_fragments()):
        df = frag.to_table().to_pandas()
        sid = df["session_id"].astype(str).values
        tn = df["turn_number"].astype("int64").values
        trk = df["track_id"].astype(str).values
        qi = np.fromiter((qidx.get((s, int(t)), -1) for s, t in zip(sid, tn)),
                         dtype=np.int64, count=len(df))
        ti = np.fromiter((tidx.get(t, -1) for t in trk), dtype=np.int64, count=len(df))
        valid = (qi >= 0) & (ti >= 0)
        n_miss_q += int((qi < 0).sum())
        n_miss_d += int((ti < 0).sum())
        sc = np.full(len(df), np.nan, dtype=np.float32)
        qg = np.where(qi < 0, 0, qi)
        tg = np.where(ti < 0, 0, ti)
        for s0 in range(0, len(df), CHUNK):
            e = min(s0 + CHUNK, len(df))
            sc[s0:e] = np.einsum("ij,ij->i", Q[qg[s0:e]], D[tg[s0:e]]).astype(np.float32)
        sc[~valid] = np.nan
        df["b1_cos"] = sc
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False),
                       os.path.join(a.out, f"part-{fi:05d}.parquet"))
        n_rows += len(df)
        nan_cos_sum += float(np.nansum(sc))
        n_valid += int(valid.sum())
        print(f"  frag {fi}: {len(df)} rows  b1_cos mean={np.nanmean(sc):.4f}", flush=True)
    print(f"DONE {a.out}: {n_rows} rows, valid={n_valid} "
          f"missing_q={n_miss_q} missing_d={n_miss_d} "
          f"overall_b1_cos_mean={nan_cos_sum / max(n_valid, 1):.4f}", flush=True)


if __name__ == "__main__":
    main()
