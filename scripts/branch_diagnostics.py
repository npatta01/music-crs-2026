"""Branch-level retrieval diagnostics for v0+ devset trace files.

Reads a trace sidecar (exp/inference/devset/{tid}_trace.jsonl) plus the
evaluator ground truth (evaluator/exp/ground_truth/devset.json) and reports:

  - hit@{1,20,50,100,200,1000}     over the FINAL recommendation
  - unionhit@{20,50,100,200}       over the union of every branch's top-k
  - recall@{100,200,1000} per branch (denominator = turns the branch fired)
  - hit@{1,20,50,100,200,1000} per ranking stage (denominator = turns stage fired)
  - union_size@{20,50,100,200}     mean distinct candidates in the union
  - fusion_efficiency@{20,50,100,200}  hit@k(final) / unionhit@k

Single GT track per turn, so recall@k == hit@k. The evaluator submodule is
not touched; this is an adjacent standalone tool.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

FINAL_KS = [1, 20, 50, 100, 200, 1000]
UNION_KS = [20, 50, 100, 200, 1000]
BRANCH_KS = [100, 200, 1000]


def final_hit_at_k(branches: dict, gt: str, k: int) -> bool:
    final_ids = _final_track_ids(branches)
    return gt in set(final_ids[:k])


def _final_track_ids(payload: dict) -> list[str]:
    final = payload.get("final_recommendation")
    if isinstance(final, dict):
        return [str(t) for t in (final.get("track_ids") or [])]
    ranking = payload.get("ranking")
    if isinstance(ranking, dict):
        final_stage = ranking.get("final_stage")
        for stage in ranking.get("stages") or []:
            if isinstance(stage, dict) and stage.get("name") == final_stage:
                return [str(t) for t in (stage.get("track_ids") or [])]
    served = payload.get("served")
    if isinstance(served, dict):
        return [str(t) for t in (served.get("track_ids") or [])]
    return [str(t) for t in (payload.get("final", {}).get("track_ids", []) or [])]


def _branch_pools(payload: dict) -> list[dict]:
    retrieval = payload.get("retrieval")
    if isinstance(retrieval, dict):
        return list(retrieval.get("branches") or [])
    return list(payload.get("pools", []) or [])


def _ranking_stages(payload: dict) -> list[dict]:
    ranking = payload.get("ranking")
    if not isinstance(ranking, dict):
        return []
    return [stage for stage in ranking.get("stages") or [] if isinstance(stage, dict)]


def _branch_topk_ids(pool: dict, k: int) -> set[str]:
    return {t for t, _ in (h[:2] for h in pool.get("hits", [])[:k])}


def _stage_topk_ids(stage: dict, k: int) -> set[str]:
    return {str(t) for t in (stage.get("track_ids") or [])[:k]}


def union_at_k(branches: dict, k: int) -> set[str]:
    out: set[str] = set()
    for pool in _branch_pools(branches):
        out |= _branch_topk_ids(pool, k)
    return out


def union_hit_at_k(branches: dict, gt: str, k: int) -> bool:
    return gt in union_at_k(branches, k)


def per_branch_recall(turns: list[tuple[dict, str]], ks: list[int]) -> dict:
    """turns: list of (branches_dict, gt_track_id). Denominator per branch is
    the number of turns that branch FIRED (appeared in pools)."""
    fired: dict[str, int] = defaultdict(int)
    hits: dict[str, dict[int, int]] = defaultdict(lambda: {k: 0 for k in ks})
    for branches, gt in turns:
        if gt is None:
            continue
        for pool in _branch_pools(branches):
            name = pool["name"]
            fired[name] += 1
            for k in ks:
                if gt in _branch_topk_ids(pool, k):
                    hits[name][k] += 1
    out: dict[str, dict] = {}
    for name, n in fired.items():
        row = {"fired": n}
        for k in ks:
            row[f"recall@{k}"] = (hits[name][k] / n) if n else 0.0
        out[name] = row
    return out


def per_stage_recall(turns: list[tuple[dict, str]], ks: list[int]) -> dict:
    """Ranking-stage hit rates. Denominator per stage is turns the stage fired."""
    fired: dict[str, int] = defaultdict(int)
    hits: dict[str, dict[int, int]] = defaultdict(lambda: {k: 0 for k in ks})
    for branches, gt in turns:
        if gt is None:
            continue
        for stage in _ranking_stages(branches):
            name = stage.get("name")
            if not name:
                continue
            fired[name] += 1
            for k in ks:
                if gt in _stage_topk_ids(stage, k):
                    hits[name][k] += 1
    out: dict[str, dict] = {}
    for name, n in fired.items():
        row = {"fired": n}
        for k in ks:
            row[f"hit@{k}"] = (hits[name][k] / n) if n else 0.0
        out[name] = row
    return out


def compute_metrics(turns: list[tuple[dict, str]]) -> dict:
    """turns: list of (branches_dict, gt_track_id). Every turn with a non-None
    GT is scored. A turn whose `branches` is empty/falsy (e.g. an extractor
    failure that produced no candidates) is kept in the denominator and scores
    as a MISS for every hit@k / unionhit@k — dropping it would overstate the
    metrics. Turns with gt is None (no ground truth) are excluded."""
    scored = [(b, gt) for b, gt in turns if gt is not None]
    n = len(scored)
    n_failed = sum(1 for b, _ in scored if not b)
    m: dict = {"n_turns": n, "n_failed_no_branches": n_failed}
    if n == 0:
        return m

    for k in FINAL_KS:
        m[f"hit@{k}"] = sum(final_hit_at_k(b, gt, k) for b, gt in scored) / n
    for k in UNION_KS:
        m[f"unionhit@{k}"] = sum(union_hit_at_k(b, gt, k) for b, gt in scored) / n
        m[f"union_size@{k}"] = sum(len(union_at_k(b, k)) for b, _ in scored) / n
        uh = m[f"unionhit@{k}"]
        m[f"fusion_efficiency@{k}"] = (m[f"hit@{k}"] / uh) if uh > 0 else None

    m["per_branch"] = per_branch_recall(scored, BRANCH_KS)
    m["per_stage"] = per_stage_recall(scored, FINAL_KS)
    return m


def iter_trace(path: str):
    """Yield trace records one at a time (streaming; O(1) memory).

    The full-devset trace is multiple GB (per-turn top-1000 branch pools), so
    loading it all into memory (`load_trace`) OOMs. This reads line-by-line.
    """
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def compute_metrics_streaming(trace_path: str, gt: dict[tuple[str, int], str]) -> dict:
    """Single-pass equivalent of compute_metrics(align_turns(trace, gt)).

    Reads the trace via iter_trace and accumulates hit@k / unionhit@k /
    union_size@k / per-branch recall without materializing the trace or the
    aligned-turn list — so it scales to the full-devset trace. Returns the same
    metric keys as compute_metrics plus `n_skipped_no_gt` and `saw_branches`.
    """
    n = 0
    n_failed = 0
    n_skipped = 0
    saw_branches = False
    hit = {k: 0 for k in FINAL_KS}
    uhit = {k: 0 for k in UNION_KS}
    usize = {k: 0 for k in UNION_KS}
    fired: dict[str, int] = defaultdict(int)
    bhits: dict[str, dict[int, int]] = defaultdict(lambda: {k: 0 for k in BRANCH_KS})
    stage_fired: dict[str, int] = defaultdict(int)
    stage_hits: dict[str, dict[int, int]] = defaultdict(lambda: {k: 0 for k in FINAL_KS})

    for r in iter_trace(trace_path):
        key = (r["session_id"], int(r["turn_number"]))
        g = gt.get(key)
        if key not in gt or g is None:
            n_skipped += 1
            continue
        tr = r.get("trace")
        branches = _metric_payload(tr)
        if branches:
            saw_branches = True
        branches = branches or {}
        n += 1
        if not branches:
            n_failed += 1
        for k in FINAL_KS:
            if final_hit_at_k(branches, g, k):
                hit[k] += 1
        for k in UNION_KS:
            u = union_at_k(branches, k)
            if g in u:
                uhit[k] += 1
            usize[k] += len(u)
        for pool in _branch_pools(branches):
            name = pool["name"]
            fired[name] += 1
            for k in BRANCH_KS:
                if g in _branch_topk_ids(pool, k):
                    bhits[name][k] += 1
        for stage in _ranking_stages(branches):
            name = stage.get("name")
            if not name:
                continue
            stage_fired[name] += 1
            for k in FINAL_KS:
                if g in _stage_topk_ids(stage, k):
                    stage_hits[name][k] += 1

    m: dict = {"n_turns": n, "n_failed_no_branches": n_failed, "n_skipped_no_gt": n_skipped,
               "saw_branches": saw_branches}
    if n == 0:
        return m
    for k in FINAL_KS:
        m[f"hit@{k}"] = hit[k] / n
    for k in UNION_KS:
        m[f"unionhit@{k}"] = uhit[k] / n
        m[f"union_size@{k}"] = usize[k] / n
        uh = m[f"unionhit@{k}"]
        m[f"fusion_efficiency@{k}"] = (m[f"hit@{k}"] / uh) if uh > 0 else None
    per: dict[str, dict] = {}
    for name, nf in fired.items():
        row = {"fired": nf}
        for k in BRANCH_KS:
            row[f"recall@{k}"] = (bhits[name][k] / nf) if nf else 0.0
        per[name] = row
    m["per_branch"] = per
    stages: dict[str, dict] = {}
    for name, nf in stage_fired.items():
        row = {"fired": nf}
        for k in FINAL_KS:
            row[f"hit@{k}"] = (stage_hits[name][k] / nf) if nf else 0.0
        stages[name] = row
    m["per_stage"] = stages
    return m


def load_trace(path: str, require_branches: bool = True) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    if require_branches:
        has_any = any(
            isinstance(r.get("trace"), dict)
            and ("branches" in r["trace"] or "retrieval" in r["trace"])
            for r in records
        )
        if not has_any:
            sys.stderr.write(
                f"ERROR: no per-turn `branches` found in {path}. This trace was "
                "produced by a non-v0+ run or before branch tracing was added. "
                "Re-run devset inference with the v0+ compiler QU.\n"
            )
            raise SystemExit(2)
    return records


def load_ground_truth(records: list[dict]) -> dict[tuple[str, int], str]:
    """(session_id, turn_number) -> ground_truth_track_id. Accepts an already
    loaded list (tests) or use load_ground_truth_file for a path."""
    return {
        (r["session_id"], int(r["turn_number"])): r.get("ground_truth_track_id")
        for r in records
    }


def load_ground_truth_file(path: str) -> dict[tuple[str, int], str]:
    with open(path, encoding="utf-8") as f:
        return load_ground_truth(json.load(f))


def align_turns(
    trace_records: list[dict], gt: dict[tuple[str, int], str]
) -> list[tuple[dict, str]]:
    """Return [(branches_dict, gt_track_id)] for every trace turn that has a
    ground-truth entry. Turns whose trace lacks a `branches` payload (e.g. an
    extractor failure that returned no candidates) are INCLUDED with an empty
    `{}` so they score as misses — they are real evaluator misses and dropping
    them would inflate hit@k / unionhit@k. Turns with no GT entry (or GT None)
    are skipped (counted by the caller as n_skipped_no_gt)."""
    out: list[tuple[dict, str]] = []
    for r in trace_records:
        key = (r["session_id"], int(r["turn_number"]))
        if key not in gt or gt[key] is None:
            continue
        tr = r.get("trace")
        branches = _metric_payload(tr)
        out.append((branches or {}, gt[key]))
    return out


def _metric_payload(trace: dict | None) -> dict | None:
    if not isinstance(trace, dict):
        return None
    if "final_recommendation" in trace or "retrieval" in trace:
        return trace
    return trace.get("branches") if isinstance(trace.get("branches"), dict) else None


def _format_report(metrics: dict) -> str:
    lines = [f"n_turns scored: {metrics['n_turns']}", ""]
    lines.append("FINAL recommendation:")
    for k in FINAL_KS:
        lines.append(f"  hit@{k:<4} = {metrics.get(f'hit@{k}', 0.0):.4f}")
    lines.append("")
    lines.append("UNION of branches:")
    for k in UNION_KS:
        eff = metrics.get(f"fusion_efficiency@{k}")
        eff_s = "n/a" if eff is None else f"{eff:.3f}"
        lines.append(
            f"  unionhit@{k} = {metrics.get(f'unionhit@{k}', 0.0):.4f}"
            f"  (mean union size {metrics.get(f'union_size@{k}', 0.0):.0f},"
            f" fusion_efficiency {eff_s})"
        )
    lines.append("")
    lines.append("PER-BRANCH recall (denominator = turns fired):")
    for name, row in sorted(metrics.get("per_branch", {}).items()):
        cells = "  ".join(f"r@{k}={row.get(f'recall@{k}', 0.0):.4f}" for k in BRANCH_KS)
        lines.append(f"  {name:<32} fired={row['fired']:<5} {cells}")
    per_stage = metrics.get("per_stage") or {}
    if per_stage:
        lines.append("")
        lines.append("PER-STAGE recall (denominator = turns stage fired):")
        for name, row in per_stage.items():
            cells = "  ".join(f"h@{k}={row.get(f'hit@{k}', 0.0):.4f}" for k in FINAL_KS)
            lines.append(f"  {name:<32} fired={row['fired']:<5} {cells}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="v0+ branch retrieval diagnostics")
    ap.add_argument("--trace", required=True, help="path to {tid}_trace.jsonl")
    ap.add_argument(
        "--ground-truth",
        required=True,
        help="path to evaluator/exp/ground_truth/devset.json",
    )
    ap.add_argument("--out", default=None, help="optional path to dump metrics JSON")
    args = ap.parse_args(argv)

    gt = load_ground_truth_file(args.ground_truth)
    # Streaming single pass — the full-devset trace is multi-GB and won't fit in
    # memory. compute_metrics_streaming returns the same keys as compute_metrics.
    metrics = compute_metrics_streaming(args.trace, gt)
    if metrics.get("n_turns", 0) > 0 and not metrics.get("saw_branches"):
        sys.stderr.write(
            f"ERROR: no per-turn `branches` found in {args.trace}. This trace was "
            "produced by a non-v0+ run or before branch tracing was added. "
            "Re-run devset inference with the v0+ compiler QU.\n"
        )
        raise SystemExit(2)
    n_skipped_no_gt = metrics.get("n_skipped_no_gt", 0)
    print(_format_report(metrics))
    n_failed = metrics.get("n_failed_no_branches", 0)
    if n_failed:
        print(
            f"\n({n_failed} of {metrics['n_turns']} scored turns had no branch "
            "trace — extractor failure / empty candidates — counted as misses)"
        )
    if n_skipped_no_gt:
        print(f"({n_skipped_no_gt} traced turns skipped: no ground-truth entry)")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
