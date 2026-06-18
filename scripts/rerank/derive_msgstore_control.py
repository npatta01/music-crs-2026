"""Derive the empty-msg-store CONTROL parquet from the populated-store TREATMENT.

The only feature columns that depend on the raw_msg_store embeddings are the
five below (everything else — branch scores, catalog cosines, text/lexical
features, session history — is store-independent). Setting these five to NaN
reproduces *exactly* what build_features.py emits when the store is empty, so
the resulting control differs from the treatment in nothing but the revived
message/context features. This makes the A/B single-variable by construction.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

STORE_COLS = [
    "msg_meta_cos",
    "msg_attr_cos",
    "msg_lyr_cos",
    "ctx_meta_cos",
    "pct_msg_meta_cos",  # within-pool pct of msg_meta_cos -> NaN when msg_meta_cos is NaN
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", required=True, help="treatment parquet (populated store)")
    ap.add_argument("--out", required=True, help="control parquet (store cols -> NaN)")
    args = ap.parse_args()

    pf = pq.ParquetFile(args.inp)
    schema = pf.schema_arrow
    names = schema.names
    present = [c for c in STORE_COLS if c in names]
    missing = [c for c in STORE_COLS if c not in names]
    print(f"in: {args.inp}  rows={pf.metadata.num_rows:,} cols={len(names)}")
    print(f"NaN-ing columns: {present}" + (f"  (absent: {missing})" if missing else ""))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    writer = None
    nan_idx = {names.index(c): c for c in present}
    n_done = 0
    for batch in pf.iter_batches(batch_size=1_000_000):
        cols = list(batch.columns)
        for j, c in nan_idx.items():
            cols[j] = pa.array(np.full(batch.num_rows, np.nan, dtype=np.float64),
                               type=batch.schema.field(j).type)
        out_batch = pa.RecordBatch.from_arrays(cols, schema=batch.schema)
        if writer is None:
            writer = pq.ParquetWriter(args.out, batch.schema)
        writer.write_batch(out_batch)
        n_done += batch.num_rows
        print(f"  {n_done:,} rows", flush=True)
    if writer:
        writer.close()
    print(f"wrote control -> {args.out}")


if __name__ == "__main__":
    main()
