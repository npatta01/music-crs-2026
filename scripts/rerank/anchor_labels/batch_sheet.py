"""Slice a full judge sheet into batches of N whole sessions, for incremental (validate-between) runs.

Sessions are kept intact (all turns of a session land in the same batch) and in first-seen order, so
batches are deterministic and reproducible.

  python scripts/rerank/anchor_labels/batch_sheet.py --sheet <sheet_full_train.jsonl> --out-dir <dir>/batches \
      --sessions-per-batch 1000
  -> writes <dir>/batches/batch_00.jsonl ... and prints a manifest (turns + sessions per batch).
"""
from __future__ import annotations
import argparse, json, os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sessions-per-batch", type=int, default=1000)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    rows = [json.loads(l) for l in open(a.sheet)]
    order, seen = [], set()
    for r in rows:
        if r["sid"] not in seen:
            seen.add(r["sid"]); order.append(r["sid"])
    n = a.sessions_per_batch
    sid2b = {sid: i // n for i, sid in enumerate(order)}
    buckets = {}
    for r in rows:
        buckets.setdefault(sid2b[r["sid"]], []).append(r)

    print(f"{len(order)} sessions / {len(rows)} turns -> {len(buckets)} batches of <= {n} sessions")
    for bi in sorted(buckets):
        p = os.path.join(a.out_dir, f"batch_{bi:02d}.jsonl")
        with open(p, "w") as f:
            for r in buckets[bi]:
                f.write(json.dumps(r) + "\n")
        nsess = len({r["sid"] for r in buckets[bi]})
        print(f"  batch_{bi:02d}: {nsess} sessions, {len(buckets[bi])} turns -> {os.path.basename(p)}")


if __name__ == "__main__":
    main()
