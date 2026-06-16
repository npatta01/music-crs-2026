"""Merge sharded inference outputs into a single per-tid JSON.

Usage:
    python scripts/merge_shard_results.py --tid v0plus_compiler_all_retrievers_devset --num_shards 5 --run_id 20260603T074512Z-a3f91c --exp-dir exp

Behavior:
  - Reads prediction shards 0..num_shards-1 into memory.
  - Streams trace JSONL shards in two passes so full-devset traces do not need
    to fit in memory.
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

    Devset writes a `_trace.jsonl` per shard; blindset writes none. A partial
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


def _trace_shard_paths(base: Path, tid: str, run_scope: str, num_shards: int) -> list[Path]:
    return [base / f"{tid}{run_scope}.shard_{i}_trace.jsonl" for i in range(num_shards)]


def _iter_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _print_conflict_warning(
    *,
    label: str,
    tid: str,
    raw_total: int,
    unique_count: int,
    conflicts: list[tuple[tuple, int, int]],
    raw_counts: dict[int, int],
    owner_by_key: dict[tuple, int],
) -> None:
    contrib: dict[int, int] = {sid: 0 for sid in raw_counts}
    for owner_sid in owner_by_key.values():
        contrib[owner_sid] += 1

    lines = [
        f"[{label}] WARNING: shards for tid={tid!r} have overlapping (session_id, turn_number) keys.",
        f"  Raw total rows:   {raw_total}",
        f"  Unique keys:      {unique_count}",
        f"  Overlapping rows: {len(conflicts)}  (dedup: kept the row from the highest shard index)",
        "  Per-shard contribution after dedup:",
    ]
    for sid, raw_count in raw_counts.items():
        lines.append(f"    shard_{sid}: {raw_count:5d} raw rows -> {contrib[sid]:5d} kept")
    lines.append("  First 3 conflicting keys (key, earlier_shard -> later_shard):")
    for k, prev_sid, new_sid in conflicts[:3]:
        lines.append(f"    {k}  shard_{prev_sid} -> shard_{new_sid}")
    print("\n".join(lines), file=sys.stderr)


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
        _print_conflict_warning(
            label=label,
            tid=tid,
            raw_total=raw_total,
            unique_count=len(merged),
            conflicts=conflicts,
            raw_counts={sid: len(rows) for sid, _path, rows in shards},
            owner_by_key=seen,
        )

    return list(merged.values())


def _merge_trace_shards_streaming(
    paths: list[Path],
    *,
    label: str,
    tid: str,
    out_path: Path,
) -> int:
    """Merge trace JSONL shards without materializing trace rows.

    Full devset traces can be several GB. This keeps only per-turn ownership
    metadata in memory, then streams rows from the owning shard into the output.
    """
    owner_by_key: dict[tuple, int] = {}
    owner_row_index_by_key: dict[tuple, int] = {}
    raw_counts: dict[int, int] = {}
    conflicts: list[tuple[tuple, int, int]] = []

    for shard_id, path in enumerate(paths):
        raw_counts[shard_id] = 0
        for row in _iter_jsonl(path):
            raw_counts[shard_id] += 1
            row_index = raw_counts[shard_id]
            k = _key(row)
            if k in owner_by_key and owner_by_key[k] != shard_id:
                conflicts.append((k, owner_by_key[k], shard_id))
            owner_by_key[k] = shard_id
            owner_row_index_by_key[k] = row_index

    if conflicts:
        _print_conflict_warning(
            label=label,
            tid=tid,
            raw_total=sum(raw_counts.values()),
            unique_count=len(owner_by_key),
            conflicts=conflicts,
            raw_counts=raw_counts,
            owner_by_key=owner_by_key,
        )

    written_keys: set[tuple] = set()
    with open(out_path, "w", encoding="utf-8") as f:
        for shard_id, path in enumerate(paths):
            row_index = 0
            for row in _iter_jsonl(path):
                row_index += 1
                k = _key(row)
                if (
                    owner_by_key.get(k) != shard_id
                    or owner_row_index_by_key.get(k) != row_index
                    or k in written_keys
                ):
                    continue
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                written_keys.add(k)
    return len(written_keys)


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
        trace_out = base / f"{args.tid}_trace.jsonl"
        trace_rows = _merge_trace_shards_streaming(
            _trace_shard_paths(base, args.tid, run_scope, args.num_shards),
            label="traces",
            tid=args.tid,
            out_path=trace_out,
        )
        print(f"Wrote {trace_out}  ({trace_rows} unique rows from {args.num_shards} shards)")
    else:
        print(f"No trace shards for {args.tid} — skipping trace merge.")


if __name__ == "__main__":
    main()
