"""Add the b1 (4B v_struct_pt) doc embeddings to the catalog LanceDB as a real
vector column `b1_vstructpt_4b`, joined on track_id. lancedb-native:
`add_columns` (create fixed-size-list column) + batched `merge_insert` (fill by
track_id; batched to stay under lance's external-sort memory pool).

Idempotent: no-op if the column is already present AND filled. Source: precomputed,
L2-normed doc embeddings (docs_vstructpt_4b.npy) ordered by doc_corpus.jsonl track_ids.
Stored normed so scout_cos = cat.v(.) . b1_query is a true cosine.
"""
from __future__ import annotations
import argparse, json
import numpy as np
import pyarrow as pa
import lancedb

FIELD = "b1_vstructpt_4b"
DOCEMB = "exp/analysis/retrieval_exploration/_emb_cache/docs_vstructpt_4b.npy"
DOC_CORPUS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"


def _is_vec(v, dim):
    return isinstance(v, (list, np.ndarray)) and len(v) == dim and not np.isnan(np.asarray(v, dtype=np.float32)).all()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-uri", default="cache/lancedb")
    ap.add_argument("--table", default="music_track_catalog")
    ap.add_argument("--batch", type=int, default=2000)
    a = ap.parse_args()

    db = lancedb.connect(a.db_uri)
    t = db.open_table(a.table)
    names = [f.name for f in t.schema]
    n_rows = t.count_rows()
    pre_ver = getattr(t, "version", "?")
    print(f"table {a.table}: {n_rows} rows, {len(names)} cols, version={pre_ver}", flush=True)

    tids = [json.loads(l)["track_id"] for l in open(DOC_CORPUS)]
    D = np.load(DOCEMB).astype(np.float32)
    D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-9)  # store normed
    dim = D.shape[1]
    assert len(tids) == D.shape[0], f"corpus {len(tids)} != emb {D.shape[0]}"
    vidx = {str(tt): i for i, tt in enumerate(tids)}

    if FIELD in names:
        # Check ALL rows, not a 5-row sample — a crash mid-fill leaves a partially
        # filled column that a sampled check would falsely call idempotent. (codex review)
        s = t.search().select(["track_id", FIELD]).limit(0).to_pandas()
        bad = sum(0 if _is_vec(r[FIELD], dim) else 1 for _, r in s.iterrows())
        if bad == 0:
            print(f"IDEMPOTENT: {FIELD} fully filled ({len(s)} rows) -> no-op")
            return
        print(f"{FIELD} present but {bad}/{len(s)} unfilled -> filling", flush=True)
    else:
        print(f"creating column {FIELD} (fixed_size_list<float32>[{dim}])", flush=True)
        t.add_columns(pa.schema([pa.field(FIELD, pa.list_(pa.float32(), dim))]))

    cat_tids = t.search().select(["track_id"]).limit(0).to_pandas()["track_id"].astype(str).tolist()
    # Refuse to write all-zero vectors for catalog tracks missing from the doc corpus:
    # b1_cos would then be float(cv @ 0)=0.0 (a fake in-distribution score), not NaN. (codex review)
    missing = [tt for tt in cat_tids if tt not in vidx]
    if missing:
        raise SystemExit(f"{len(missing)} catalog tracks missing from the doc corpus "
                         f"(e.g. {missing[:3]}) -> would be all-zero vectors. Rebuild doc_corpus first.")
    n_filled = 0
    for s0 in range(0, len(cat_tids), a.batch):
        chunk = cat_tids[s0:s0 + a.batch]
        rows = np.zeros((len(chunk), dim), dtype=np.float32)
        for i, tt in enumerate(chunk):
            j = vidx.get(tt)
            if j is not None:
                rows[i] = D[j]; n_filled += 1
        fsl = pa.FixedSizeListArray.from_arrays(pa.array(rows.reshape(-1), type=pa.float32()), dim)
        src = pa.table({"track_id": pa.array(chunk), FIELD: fsl})
        t.merge_insert("track_id").when_matched_update_all().execute(src)
        if (s0 // a.batch) % 5 == 0:
            print(f"  filled {s0 + len(chunk)}/{len(cat_tids)}", flush=True)

    t2 = db.open_table(a.table)
    assert FIELD in [f.name for f in t2.schema] and t2.count_rows() == n_rows, "post-merge schema/rows mismatch"
    chk = t2.search().select(["track_id", FIELD]).where(f"track_id = '{cat_tids[0]}'").limit(0).to_pandas()
    v = np.asarray(chk.iloc[0][FIELD], dtype=np.float32)
    print(f"VERIFY: {FIELD} rows={t2.count_rows()} sample dim={len(v)} norm={np.linalg.norm(v):.4f} filled={n_filled}/{len(cat_tids)}")
    print(f"rollback if needed: db.open_table('{a.table}').restore({pre_ver}); DONE")


if __name__ == "__main__":
    main()
