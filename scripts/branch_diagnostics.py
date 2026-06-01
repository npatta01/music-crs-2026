"""Branch-level retrieval diagnostics for v0+ devset trace files.

Reads a trace sidecar (exp/inference/devset/{tid}_trace.json) plus the
evaluator ground truth (evaluator/exp/ground_truth/devset.json) and reports:

  - hit@{1,20,50,100,200,1000}     over the FINAL recommendation
  - unionhit@{20,50,100,200}       over the union of every branch's top-k
  - recall@{100,200,1000} per branch (denominator = turns the branch fired)
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
UNION_KS = [20, 50, 100, 200]
BRANCH_KS = [100, 200, 1000]


def final_hit_at_k(branches: dict, gt: str, k: int) -> bool:
    if k == 1:
        return branches.get("recommended", {}).get("top1_track_id") == gt
    final_ids = branches.get("final", {}).get("track_ids", [])
    return gt in set(final_ids[:k])


def _branch_topk_ids(pool: dict, k: int) -> set[str]:
    return {t for t, _ in (h[:2] for h in pool.get("hits", [])[:k])}


def union_at_k(branches: dict, k: int) -> set[str]:
    out: set[str] = set()
    for pool in branches.get("pools", []):
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
        for pool in branches.get("pools", []):
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


def compute_metrics(turns: list[tuple[dict, str]]) -> dict:
    """turns: list of (branches_dict, gt_track_id). Turns with gt is None or
    no `branches` are excluded from the scored denominator."""
    scored = [(b, gt) for b, gt in turns if gt is not None and b]
    n = len(scored)
    m: dict = {"n_turns": n}
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
    return m


def load_trace(path: str, require_branches: bool = True) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    if require_branches:
        has_any = any(
            isinstance(r.get("trace"), dict) and "branches" in r["trace"]
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
    `branches` payload AND a ground-truth entry. Turns missing either are
    skipped (counted by the caller)."""
    out: list[tuple[dict, str]] = []
    for r in trace_records:
        tr = r.get("trace")
        if not isinstance(tr, dict) or "branches" not in tr:
            continue
        key = (r["session_id"], int(r["turn_number"]))
        if key not in gt:
            continue
        out.append((tr["branches"], gt[key]))
    return out


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
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="v0+ branch retrieval diagnostics")
    ap.add_argument("--trace", required=True, help="path to {tid}_trace.json")
    ap.add_argument(
        "--ground-truth",
        required=True,
        help="path to evaluator/exp/ground_truth/devset.json",
    )
    ap.add_argument("--out", default=None, help="optional path to dump metrics JSON")
    args = ap.parse_args(argv)

    trace = load_trace(args.trace, require_branches=True)
    gt = load_ground_truth_file(args.ground_truth)
    aligned = align_turns(trace, gt)
    skipped = sum(
        1
        for r in trace
        if isinstance(r.get("trace"), dict) and "branches" in r["trace"]
    ) - len(aligned)

    metrics = compute_metrics(aligned)
    metrics["n_skipped_no_gt"] = skipped
    print(_format_report(metrics))
    if skipped:
        print(f"\n({skipped} traced turns skipped: no ground-truth entry)")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
