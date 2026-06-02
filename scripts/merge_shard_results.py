"""Merge sharded inference outputs into a single per-tid JSON.

Usage:
    python scripts/merge_shard_results.py --tid v0plus_compiler_all_retrievers_devset --num_shards 5 --exp-dir exp

Behavior:
  - Reads shards 0..num_shards-1 for both predictions and traces.
  - Each row is keyed by (session_id, turn_number); output is always unique
    by that key.
  - If shards have overlapping keys (e.g. a leftover shard from a prior run
    with different --num_shards), deduplicates by keeping the row from the
    highest shard index (last-shard-index wins) and prints a warning with
    the per-shard contribution and example conflicts. The merge proceeds —
    it does not abort.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _key(row: dict) -> tuple:
    return (row["session_id"], row["turn_number"])


def _load_shards(
    base: Path, tid: str, num_shards: int, suffix: str, jsonl: bool
) -> list[tuple[int, Path, list[dict]]]:
    out = []
    for shard_id in range(num_shards):
        shard_path = base / f"{tid}.shard_{shard_id}{suffix}"
        if not shard_path.exists():
            raise FileNotFoundError(f"Missing shard output: {shard_path}")
        with open(shard_path) as f:
            if jsonl:
                rows = [json.loads(line) for line in f if line.strip()]
            else:
                rows = json.load(f)
        out.append((shard_id, shard_path, rows))
    return out


def _merge(
    shards: list[tuple[int, Path, list[dict]]],
    *,
    label: str,
    tid: str,
) -> list[dict]:
    raw_total = sum(len(rows) for _, _, rows in shards)
    seen: dict[tuple, int] = {}  # key -> shard_id that currently owns it
    merged: dict[tuple, dict] = {}
    conflicts: list[tuple[tuple, int, int]] = []  # (key, prev_shard, new_shard)

    for shard_id, _path, rows in shards:
        for row in rows:
            k = _key(row)
            if k in seen and seen[k] != shard_id:
                conflicts.append((k, seen[k], shard_id))
            seen[k] = shard_id
            merged[k] = row  # last shard index wins on conflict

    if conflicts:
        n_conflicts = len(conflicts)
        contrib: dict[int, int] = {sid: 0 for sid, _, _ in shards}
        for _k, owner_sid in seen.items():
            contrib[owner_sid] += 1

        lines = [
            f"[{label}] WARNING: shards for tid={tid!r} have overlapping (session_id, turn_number) keys.",
            f"  Raw total rows:   {raw_total}",
            f"  Unique keys:      {len(merged)}",
            f"  Overlapping rows: {n_conflicts}  (dedup: kept the row from the highest shard index)",
            "  Per-shard contribution after dedup:",
        ]
        for sid, _path, rows in shards:
            lines.append(f"    shard_{sid}: {len(rows):5d} raw rows -> {contrib[sid]:5d} kept")
        lines.append("  First 3 conflicting keys (key, earlier_shard -> later_shard):")
        for k, prev_sid, new_sid in conflicts[:3]:
            lines.append(f"    {k}  shard_{prev_sid} -> shard_{new_sid}")
        print("\n".join(lines), file=sys.stderr)

    return list(merged.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tid", required=True, help="Experiment id (matches the shard prefix).")
    parser.add_argument("--num_shards", type=int, required=True)
    parser.add_argument("--exp-dir", default="exp")
    parser.add_argument("--split", default="devset", choices=("devset", "blindset_A", "blindset_B"))
    args = parser.parse_args()

    base = Path(args.exp_dir) / "inference" / args.split
    # (output_suffix, label, jsonl): predictions are a JSON array; the trace
    # sidecar is JSONL (one record per line).
    for suffix, label, jsonl in ((".json", "predictions", False), ("_trace.jsonl", "traces", True)):
        shards = _load_shards(base, args.tid, args.num_shards, suffix, jsonl)
        rows = _merge(shards, label=label, tid=args.tid)
        out_path = base / f"{args.tid}{suffix}"
        with open(out_path, "w", encoding="utf-8") as f:
            if jsonl:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            else:
                json.dump(rows, f, ensure_ascii=False)
        print(f"Wrote {out_path}  ({len(rows)} unique rows from {args.num_shards} shards)")


if __name__ == "__main__":
    main()
