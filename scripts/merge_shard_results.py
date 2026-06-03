"""Merge sharded inference outputs into a single per-tid JSON.

Usage:
    python scripts/merge_shard_results.py --tid v0plus_compiler_all_retrievers_devset --num_shards 5 --run_id 20260603T074512Z-a3f91c --exp-dir exp

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
    base: Path, tid: str, run_scope: str, num_shards: int, suffix: str, jsonl: bool
) -> list[tuple[int, Path, list[dict]]]:
    out = []
    for shard_id in range(num_shards):
        shard_path = base / f"{tid}{run_scope}.shard_{shard_id}{suffix}"
        if not shard_path.exists():
            raise FileNotFoundError(f"Missing shard output: {shard_path}")
        with open(shard_path) as f:
            if jsonl:
                rows = [json.loads(line) for line in f if line.strip()]
            else:
                rows = json.load(f)
        out.append((shard_id, shard_path, rows))
    return out


def _traces_present(base: Path, tid: str, run_scope: str, num_shards: int) -> bool:
    """True if every shard has a trace sidecar; False if none do.

    Devset writes a `_trace.json` per shard; blindset writes none. A partial
    set (some shards have traces, some don't) means a corrupt/incomplete run,
    so fail loudly rather than silently merging a subset.
    """
    paths = [base / f"{tid}{run_scope}.shard_{i}_trace.jsonl" for i in range(num_shards)]
    present = [p for p in paths if p.exists()]
    if not present:
        return False
    if len(present) != num_shards:
        missing = [str(p) for p in paths if not p.exists()]
        raise FileNotFoundError(
            "Partial trace shards (some present, some missing): " + ", ".join(missing)
        )
    return True


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


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--tid", required=True, help="Experiment id (matches the shard prefix).")
    parser.add_argument("--num_shards", type=int, required=True)
    parser.add_argument(
        "--run_id",
        default=None,
        help="Run id scoping the shard files: {tid}.run_{run_id}.shard_N.json. "
             "Omit for legacy unscoped {tid}.shard_N.json files.",
    )
    parser.add_argument("--exp-dir", default="exp")
    parser.add_argument("--split", default="devset")
    args = parser.parse_args(argv)

    base = Path(args.exp_dir) / "inference" / args.split
    run_scope = f".run_{args.run_id}" if args.run_id else ""

    # Predictions are always required (a JSON array per shard).
    pred_shards = _load_shards(base, args.tid, run_scope, args.num_shards, ".json", False)
    pred_rows = _merge(pred_shards, label="predictions", tid=args.tid)
    pred_out = base / f"{args.tid}.json"
    with open(pred_out, "w", encoding="utf-8") as f:
        json.dump(pred_rows, f, ensure_ascii=False)
    print(f"Wrote {pred_out}  ({len(pred_rows)} unique rows from {args.num_shards} shards)")

    # Traces are optional: devset writes a JSONL sidecar per shard; blindset
    # writes none. Merge them as JSONL when present.
    if _traces_present(base, args.tid, run_scope, args.num_shards):
        trace_shards = _load_shards(base, args.tid, run_scope, args.num_shards, "_trace.jsonl", True)
        trace_rows = _merge(trace_shards, label="traces", tid=args.tid)
        trace_out = base / f"{args.tid}_trace.jsonl"
        with open(trace_out, "w", encoding="utf-8") as f:
            for row in trace_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Wrote {trace_out}  ({len(trace_rows)} unique rows from {args.num_shards} shards)")
    else:
        print(f"No trace shards for {args.tid} — skipping trace merge.")


if __name__ == "__main__":
    main()
