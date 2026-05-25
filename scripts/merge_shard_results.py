"""Merge sharded inference outputs into a single per-tid JSON.

Usage:
    python scripts/merge_shard_results.py --tid v0plus_compiler_devset --num_shards 4 --exp-dir exp
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tid", required=True, help="Experiment id (matches the shard prefix).")
    parser.add_argument("--num_shards", type=int, required=True)
    parser.add_argument("--exp-dir", default="exp")
    parser.add_argument("--split", default="devset", choices=("devset", "blindset_A", "blindset_B"))
    args = parser.parse_args()

    base = Path(args.exp_dir) / "inference" / args.split
    for kind in ("", "_trace"):
        rows: list = []
        for shard_id in range(args.num_shards):
            shard_path = base / f"{args.tid}.shard_{shard_id}{kind}.json"
            if not shard_path.exists():
                raise FileNotFoundError(f"Missing shard output: {shard_path}")
            with open(shard_path) as f:
                rows.extend(json.load(f))
        out_path = base / f"{args.tid}{kind}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        print(f"Wrote {out_path}  ({len(rows)} rows from {args.num_shards} shards)")


if __name__ == "__main__":
    main()
