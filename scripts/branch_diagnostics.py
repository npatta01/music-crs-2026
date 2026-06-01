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
