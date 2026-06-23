"""Reproduce the phase-3 serving-reranker NET ΔnDCG@20 table from saved raw scores — NO GPU.

Reads the per-turn cross-encoder scores saved by probe_xenc_zeroshot.py
(`*_rawscores.jsonl`: one row per turn with {group, before, gt_idx, sc:[~100]}) and recomputes,
for every reranking mode + threshold, the population-weighted net ΔnDCG@20 over
recoverable-misses vs controls. This is the headline result of
docs/research/cross_encoder_exploration.md, regenerated offline in seconds.

Usage (from repo root):
    python scripts/rerank/sweep_phase3_offline.py \
        docs/research/cross_encoder_artifacts/xenc_phase3_4b_v2_rawscores.jsonl
"""
from __future__ import annotations
import json, math, sys
from collections import defaultdict

# Devset pool populations (lanes hit/oracle): recoverable-misses vs controls. The sampled raw
# file is a subset; we weight the per-group means by the true population to get the serving net.
W = {"miss": 1709, "ctrl": 4865}


def ndcg20(rank):
    return 1.0 / math.log2(rank + 1) if rank and rank <= 20 else 0.0


def after_rank(order, gt):           # order = reordered candidate indices; gt = index or -1
    return (order.index(gt) + 1) if gt in order else None


def orderings(sc, gt, fusion_k=60, taus=(0.0005, 0.001, 0.005, 0.01, 0.02, 0.05),
              ptaus=(0.8, 0.9, 0.95, 0.97, 0.99)):
    n = len(sc); cand = list(range(n)); out = {}
    od = sorted(cand, key=lambda i: -sc[i])
    out["replace"] = after_rank(od, gt)
    xr = {i: r for r, i in enumerate(od)}
    out["rrf"] = after_rank(sorted(cand, key=lambda i: -(1/(fusion_k+i) + 1/(fusion_k+xr[i]))), gt)
    for t in taus:
        out[f"filter{t}"] = after_rank([i for i in cand if sc[i] >= t] + [i for i in cand if sc[i] < t], gt)
    for p in ptaus:
        prom = sorted([i for i in cand if sc[i] >= p], key=lambda i: -sc[i])
        out[f"promote{p}"] = after_rank(prom + [i for i in cand if sc[i] < p], gt)
    return out


def main(path):
    rows = [json.loads(l) for l in open(path)]
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        nb = ndcg20(r["before"])
        for mode, after in orderings(r["sc"], r["gt_idx"]).items():
            acc[mode][r["group"]].append(ndcg20(after) - nb)
    mean = lambda x: sum(x) / len(x) if x else 0.0
    res = []
    for mode, g in acc.items():
        m, c = mean(g["miss"]), mean(g["ctrl"])
        res.append(((W["miss"] * m + W["ctrl"] * c) / sum(W.values()), mode, m, c))
    res.sort(reverse=True)
    print(f"rows={len(rows)}  (pop-weighted net over {W['miss']} miss : {W['ctrl']} ctrl)\n")
    print(f"{'mode':<14}{'NET':>10}{'miss':>10}{'ctrl':>10}")
    for net, mode, m, c in res:
        print(f"{mode:<14}{net:>+10.4f}{m:>+10.4f}{c:>+10.4f}")
    print(f"\nbest net = {res[0][1]} ({res[0][0]:+.4f}); any mode net>0 and non-trivial? "
          f"{'see filter@0.0005 = a no-op' if res[0][0] < 0.01 else 'CHECK'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else "docs/research/cross_encoder_artifacts/xenc_phase3_4b_v2_rawscores.jsonl")
