"""Branch-trace JSON -> per-(session, turn, candidate) rerank dataset.

Streams the (multi-GB) ``v0plus_compiler_all_retrievers_*`` branch trace with ijson, builds
the **deduped union of all branch pools** per turn (recall-only; no RRF gating), joins the
single golden track as the binary label, and writes two artifacts:

* ``candidates.parquet`` -- one row per (session, turn, candidate): group keys, ``label``,
  and the *raw* per-branch ``rank`` / ``score`` (NaN where a branch did not surface it).
* ``groups.jsonl`` -- one record per (session, turn): per-branch ``pool_depth`` / ``top_score``
  plus the as-of-turn query-side state (blocks D/E/G) needed by ``features.py``. Small
  (<=8k rows on devset), so nested list fields are kept verbatim.

Everything *derived* (norm_rank, aggregates, catalog joins, match features, centroids) lives
in ``features.py`` -- this module only extracts raw signals so the expensive stream runs once.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

# ijson / pyarrow are imported lazily (inside the functions that use them) so the online
# serving path (mcrs.rerank.online imports _parse_pools/_candidate_rows/build_group_record
# from here) doesn't drag the offline-only trace/parquet toolchain into the Modal image.

from mcrs.rerank.branches import (
    BRANCH_KEYS,
    canonical_branch_key,
    raw_rank_col,
    raw_score_col,
)

DEFAULT_TRACE = "exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.json"
DEFAULT_GROUND_TRUTH = "evaluator/exp/ground_truth/devset.json"

# How deep to record the existing RRF orderings (the reranker baseline). Top-50 is ample for
# NDCG@20 / MRR@20 / hit@20.
BASELINE_TOPK = 50


# --------------------------------------------------------------------------- IO helpers

def load_ground_truth(path: str | Path) -> dict[tuple[str, int], str]:
    """Map (session_id, turn_number) -> golden track_id."""
    with open(path) as fh:
        rows = json.load(fh)
    gt: dict[tuple[str, int], str] = {}
    for r in rows:
        gt[(r["session_id"], int(r["turn_number"]))] = r["ground_truth_track_id"]
    return gt


def iter_trace(path: str | Path) -> Iterator[dict[str, Any]]:
    """Stream branch-trace entries one at a time, from **JSONL or a JSON array**.

    The current harness writes traces as JSONL (one object per line); older artifacts are a
    single JSON array. Format is auto-detected from the first non-whitespace byte (``{`` =
    JSONL, ``[`` = array). Both tolerate a truncated tail: a malformed final line / dangling
    array fragment is dropped with a warning rather than failing the run.
    """
    import sys

    p = str(path)
    with open(p, "rb") as fh:
        head = fh.read(64).lstrip()
    is_jsonl = p.endswith(".jsonl") or head[:1] == b"{"

    if is_jsonl:
        with open(p) as fh:
            for i, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    print(f"[build_dataset] warning: skipping malformed/truncated JSONL line {i}.",
                          file=sys.stderr)
        return

    import ijson  # offline-only; lazy so serving doesn't require it

    with open(p, "rb") as fh:  # legacy JSON array
        items = ijson.items(fh, "item", use_float=True)
        n = 0
        while True:
            try:
                entry = next(items)
            except StopIteration:
                break
            except ijson.common.IncompleteJSONError:
                print(f"[build_dataset] warning: trace truncated after {n} complete entries; "
                      "dropping the dangling fragment.", file=sys.stderr)
                break
            n += 1
            yield entry


# --------------------------------------------------------------------- per-turn extraction

def _parse_pools(branches: dict[str, Any]) -> dict[str, list[tuple[str, float]]]:
    """Canonicalised {branch_key: [(track_id, score), ...]} in rank order.

    Later duplicate pool names for the same canonical key are ignored (first wins);
    unknown pool names are dropped (counted by the caller via the returned 'unknown' key).
    """
    pools: dict[str, list[tuple[str, float]]] = {}
    unknown: list[str] = []
    for pool in branches.get("pools", []):
        key = canonical_branch_key(pool.get("name", ""))
        if key is None:
            unknown.append(pool.get("name", ""))
            continue
        if key in pools:
            continue
        pools[key] = [(str(t), float(s)) for t, s in pool.get("hits", [])]
    if unknown:
        pools["__unknown__"] = unknown  # type: ignore[assignment]
    return pools


def _mention_counts(mentioned: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"artists": 0, "albums": 0, "tracks": 0, "tags": 0}
    plural = {"artist": "artists", "album": "albums", "track": "tracks", "tag": "tags"}
    for m in mentioned or []:
        key = plural.get(m.get("type"))
        if key:
            counts[key] += 1
    return counts


def build_group_record(entry: dict[str, Any], gt_tid: str | None) -> dict[str, Any]:
    """Per-(session,turn) state record for blocks D/E/G (no per-candidate expansion)."""
    tr = entry["trace"]
    state = tr.get("state", {}) or {}
    resolver = tr.get("resolver", {}) or {}
    routing = state.get("routing_tags", {}) or {}
    ryr = state.get("release_year_range") or {}
    targets = tr.get("resolved_targets", []) or []
    mentions = _mention_counts(state.get("mentioned_entities", []))
    track_feedback = state.get("track_feedback", []) or []
    branches = tr.get("branches", {}) or {}
    # Per-branch query/centroid vectors for dense cross-scoring (block H). Carried through
    # verbatim — base64 float32 from a serialized trace, or plain float lists from the online
    # entry; features.py decodes both via vec_codec. Empty dict when capture was off.
    branch_query_vectors = branches.get("branch_query_vectors") or {}

    return {
        "session_id": entry["session_id"],
        "user_id": entry.get("user_id"),
        "turn_number": int(entry["turn_number"]),
        "gt_track_id": gt_tid,
        # --- D: query-side scalars ---
        "intent_mode": state.get("intent_mode"),
        "exploration_policy": (state.get("process_constraints") or {}).get("exploration_policy"),
        "routing_tags": {k: bool(routing.get(k, False)) for k in (
            "exact_entity_probe", "lyric_search", "feature_articulation",
            "image_or_visual_search", "hidden_target_search")},
        "turn_intent": state.get("turn_intent") or "",
        "has_lyrical_theme": bool(state.get("lyrical_theme")),
        "release_year_range": {"start": ryr.get("start"), "end": ryr.get("end")} if ryr else None,
        "n_mentioned_artists": mentions["artists"],
        "n_mentioned_albums": mentions["albums"],
        "n_mentioned_tracks": mentions["tracks"],
        "n_mentioned_tags": mentions["tags"],
        "n_anchors": len(resolver.get("anchor_track_ids", []) or []),
        "has_seed": any((tf.get("role") == "seed") for tf in track_feedback),
        "n_rejections": len(state.get("explicit_rejections", []) or []),
        # --- E/G: as-of-turn resolved state ---
        "anchor_track_ids": list(resolver.get("anchor_track_ids", []) or []),
        "rejected_track_ids": list(resolver.get("rejected_track_ids", []) or []),
        "rejected_artist_ids": list(resolver.get("rejected_artist_ids", []) or []),
        "rejected_tags": list(resolver.get("rejected_tags", []) or []),
        "positive_tags": list(resolver.get("positive_tags", []) or []),
        "played_track_ids": list(resolver.get("played_track_ids", []) or []),
        "resolved_targets": [
            {"kind": t.get("kind"), "entity_id": t.get("entity_id"),
             "confidence": t.get("confidence")} for t in targets
        ],
        "track_feedback": [
            {"track_id": tf.get("track_id"), "role": tf.get("role"),
             "overall_sentiment": tf.get("overall_sentiment")} for tf in track_feedback
        ],
        # --- H: dense cross-scoring query vectors (branch_name -> base64 float32 or list) ---
        "branch_query_vectors": branch_query_vectors,
    }


# ------------------------------------------------------------------------- candidate rows

def _cand_schema():
    """Parquet schema for candidates.parquet. Built lazily (imports pyarrow)."""
    import pyarrow as pa

    return pa.schema(
        [pa.field("session_id", pa.string()),
         pa.field("turn_number", pa.int32()),
         pa.field("track_id", pa.string()),
         pa.field("label", pa.int8())]
        + [pa.field(raw_rank_col(k), pa.int32()) for k in BRANCH_KEYS]
        + [pa.field(raw_score_col(k), pa.float32()) for k in BRANCH_KEYS]
    )


def _candidate_rows(
    session_id: str,
    turn_number: int,
    pools: dict[str, list[tuple[str, float]]],
    gt_tid: str | None,
    max_pool_depth: int | None,
    max_neg_per_group: int | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build candidate rows for one turn plus per-group pool stats.

    The golden track is always retained even when negatives are capped, and its raw
    ranks/scores are read at *full* pool depth so the label's positive carries true signal.
    """
    branch_keys = [k for k in pools if k != "__unknown__"]
    # tid -> {branch_key: (rank, score)} at FULL depth (true ranks)
    idx: dict[str, dict[str, tuple[int, float]]] = {}
    pool_depth: dict[str, int] = {}
    top_score: dict[str, float | None] = {}
    for key in branch_keys:
        hits = pools[key]
        pool_depth[key] = len(hits)
        top_score[key] = hits[0][1] if hits else None
        for rank, (tid, score) in enumerate(hits, start=1):
            idx.setdefault(tid, {})[key] = (rank, score)

    # Union membership (optionally depth-capped per branch), golden always kept.
    union: dict[str, None] = {}
    for key in branch_keys:
        hits = pools[key] if max_pool_depth is None else pools[key][:max_pool_depth]
        for tid, _ in hits:
            union.setdefault(tid, None)
    if gt_tid is not None and gt_tid in idx:
        union.setdefault(gt_tid, None)

    # Optional negative cap: keep golden + best-min-rank negatives.
    candidates = list(union)
    if max_neg_per_group is not None:
        def min_rank(tid: str) -> int:
            return min((r for r, _ in idx[tid].values()), default=10**9)
        negs = sorted((t for t in candidates if t != gt_tid), key=min_rank)[:max_neg_per_group]
        candidates = ([gt_tid] if (gt_tid is not None and gt_tid in idx) else []) + negs

    rows: list[dict[str, Any]] = []
    gt_min_rank: int | None = None
    for tid in candidates:
        hit = idx.get(tid, {})
        row: dict[str, Any] = {
            "session_id": session_id,
            "turn_number": turn_number,
            "track_id": tid,
            "label": 1 if tid == gt_tid else 0,
        }
        for key in BRANCH_KEYS:
            rank_score = hit.get(key)
            row[raw_rank_col(key)] = rank_score[0] if rank_score else None
            row[raw_score_col(key)] = rank_score[1] if rank_score else None
        rows.append(row)
        if tid == gt_tid and hit:
            gt_min_rank = min(r for r, _ in hit.values())

    stats = {
        "pool_depth": pool_depth,
        "top_score": top_score,
        "union_size": len(union),
        "n_candidates": len(rows),
        "gt_in_union": gt_tid is not None and gt_tid in idx,
        "gt_min_rank": gt_min_rank,
        "unknown_pools": pools.get("__unknown__", []),
    }
    return rows, stats


# ------------------------------------------------------------------------------- driver

def build_dataset(
    trace_path: str | Path = DEFAULT_TRACE,
    ground_truth_path: str | Path = DEFAULT_GROUND_TRUTH,
    out_dir: str | Path = "exp/rerank/dataset",
    limit: int | None = None,
    max_pool_depth: int | None = None,
    max_neg_per_group: int | None = None,
    flush_rows: int = 500_000,
) -> dict[str, Any]:
    import pyarrow as pa
    import pyarrow.parquet as pq

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    gt = load_ground_truth(ground_truth_path)

    cand_schema = _cand_schema()
    writer = pq.ParquetWriter(out / "candidates.parquet", cand_schema)
    groups_fh = open(out / "groups.jsonl", "w")

    buffer: list[dict[str, Any]] = []
    n_groups = 0
    n_rows = 0
    n_gt_in_union = 0
    n_gt_known = 0
    unknown_pool_names: set[str] = set()

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        cols = {f.name: [r.get(f.name) for r in buffer] for f in cand_schema}
        writer.write_table(pa.table(cols, schema=cand_schema))
        buffer = []

    try:
        for entry in iter_trace(trace_path):
            sid = entry["session_id"]
            turn = int(entry["turn_number"])
            gt_tid = gt.get((sid, turn))
            branches = entry["trace"].get("branches", {}) or {}
            pools = _parse_pools(branches)

            rows, stats = _candidate_rows(
                sid, turn, pools, gt_tid, max_pool_depth, max_neg_per_group)
            buffer.extend(rows)
            n_rows += len(rows)

            grp = build_group_record(entry, gt_tid)
            fused = [str(t) for t, _ in (branches.get("fused") or [])][:BASELINE_TOPK]
            final = list((branches.get("final") or {}).get("track_ids", []))[:BASELINE_TOPK]
            grp.update({
                "pool_depth": stats["pool_depth"],
                "top_score": stats["top_score"],
                "union_size": stats["union_size"],
                "n_candidates": stats["n_candidates"],
                "gt_in_union": stats["gt_in_union"],
                "gt_min_rank": stats["gt_min_rank"],
                "rrf_fused_topk": fused,
                "final_topk": final,
            })
            groups_fh.write(json.dumps(grp) + "\n")

            if gt_tid is not None:
                n_gt_known += 1
                n_gt_in_union += int(stats["gt_in_union"])
            unknown_pool_names.update(stats["unknown_pools"])

            n_groups += 1
            if len(buffer) >= flush_rows:
                flush()
            if limit is not None and n_groups >= limit:
                break
        flush()
    finally:
        writer.close()
        groups_fh.close()

    summary = {
        "n_groups": n_groups,
        "n_candidate_rows": n_rows,
        "n_groups_with_gt": n_gt_known,
        "gt_in_union": n_gt_in_union,
        "gt_in_union_rate": (n_gt_in_union / n_gt_known) if n_gt_known else None,
        "avg_candidates_per_group": (n_rows / n_groups) if n_groups else 0,
        "unknown_pool_names": sorted(unknown_pool_names),
        "max_pool_depth": max_pool_depth,
        "max_neg_per_group": max_neg_per_group,
        "out_dir": str(out),
    }
    with open(out / "build_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build the rerank candidate dataset from a branch trace.")
    p.add_argument("--trace", default=DEFAULT_TRACE)
    p.add_argument("--ground-truth", default=DEFAULT_GROUND_TRUTH)
    p.add_argument("--out-dir", default="exp/rerank/dataset")
    p.add_argument("--limit", type=int, default=None, help="Max (session,turn) groups to process.")
    p.add_argument("--max-pool-depth", type=int, default=None,
                   help="Cap each branch pool to top-K when forming the negative union "
                        "(golden always kept; ranks recorded at full depth).")
    p.add_argument("--max-neg-per-group", type=int, default=None,
                   help="Keep golden + N best-min-rank negatives per group.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = build_dataset(
        trace_path=args.trace,
        ground_truth_path=args.ground_truth,
        out_dir=args.out_dir,
        limit=args.limit,
        max_pool_depth=args.max_pool_depth,
        max_neg_per_group=args.max_neg_per_group,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
