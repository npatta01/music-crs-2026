#!/usr/bin/env python3
"""Where does the GT track sit in the pool on visual turns? (issue #127)

Answers WHY Lever B lifts union but not top-20: for every visual turn it locates
the ground-truth track's rank in (a) each retrieval branch — especially the new
`dense.siglip2_text.visual.image_siglip2` branch, (b) the fused candidate pool,
and (c) the LGBM output. The LGBM only *scores* the top `pool_k` fused
candidates (v10: 500); anything deeper is appended below and can never reach
top-20. Comparing baseline vs treatment shows whether the SigLIP branch's
contributions land where the reranker can use them.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

POOL_K = 500  # lgbm scores the top-POOL_K fused candidates (v10 config)
SIGLIP = "dense.siglip2_text.visual.image_siglip2"


def load_gt(path: Path) -> dict[tuple[str, int], str]:
    return {
        (str(r["session_id"]), int(r["turn_number"])): str(r["ground_truth_track_id"])
        for r in json.loads(path.read_text(encoding="utf-8"))
    }


def _routing(tr: dict) -> dict:
    t = (tr.get("compiled_state") or {}).get("routing_tags") or tr.get("routing_tags")
    return t if isinstance(t, dict) else {}


def _rank_in(ids: list[str], gt: str) -> int | None:
    try:
        return ids.index(gt) + 1
    except ValueError:
        return None


def _stage_rank(tr: dict, name: str, gt: str) -> int | None:
    for s in (tr.get("ranking") or {}).get("stages") or []:
        if s.get("name") == name:
            return _rank_in([str(t) for t in (s.get("track_ids") or [])], gt)
    return None


def _branch_ranks(tr: dict, gt: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for b in (tr.get("retrieval") or {}).get("branches") or []:
        r = _rank_in([str(h[0]) for h in (b.get("hits") or []) if h], gt)
        if r is not None:
            out[str(b.get("name"))] = r
    return out


def scan(trace_path: Path, gt: dict, sessions: set[str]):
    """{(sid,turn): {branch_ranks, fusion, lgbm}} for visual turns."""
    out: dict[tuple, dict] = {}
    with trace_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            o = json.loads(line)
            sid = str(o["session_id"])
            if sid not in sessions:
                continue
            tr = o.get("trace") or {}
            if not _routing(tr).get("image_or_visual_search"):
                continue
            key = (sid, int(o["turn_number"]))
            g = gt.get(key)
            if not g:
                continue
            out[key] = {
                "branch": _branch_ranks(tr, g),
                "fusion": _stage_rank(tr, "candidate_fusion", g),
                "lgbm": _stage_rank(tr, "lgbm_v10", g),
            }
    return out


def bucket(r: int | None) -> str:
    if r is None:
        return "absent"
    for hi, name in [(20, "1-20"), (100, "21-100"), (POOL_K, f"101-{POOL_K}"), (1000, f"{POOL_K+1}-1000")]:
        if r <= hi:
            return name
    return ">1000"


def pct(n, d):
    return f"{(100*n/d):.1f}%" if d else "-"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-trace", required=True, type=Path)
    ap.add_argument("--treatment-trace", required=True, type=Path)
    ap.add_argument("--ground-truth", required=True, type=Path)
    ap.add_argument("--sessions-file", required=True, type=Path)
    args = ap.parse_args()

    gt = load_gt(args.ground_truth)
    sessions = set(json.loads(args.sessions_file.read_text())["session_ids"])
    base = scan(args.baseline_trace, gt, sessions)
    treat = scan(args.treatment_trace, gt, sessions)
    keys = sorted(set(base) | set(treat))
    n = len(keys)
    print(f"visual turns: {n}\n")

    # 1. SigLIP branch coverage depth (treatment) — where the new branch finds GT.
    sig = [t["branch"].get(SIGLIP) for k, t in treat.items()]
    sig_cov = [r for r in sig if r is not None]
    print("SigLIP visual branch — GT coverage depth (treatment):")
    for lab, lo, hi in [("<=100", 1, 100), ("101-500", 101, 500), ("501-1000", 501, 1000)]:
        c = sum(1 for r in sig_cov if lo <= r <= hi)
        print(f"  {lab:<10} {c:>4}  ({pct(c, n)} of visual turns)")
    print(f"  covered@1000 total: {len(sig_cov)} ({pct(len(sig_cov), n)}); absent: {n-len(sig_cov)}\n")

    # 2. Funnel: where the GT is across stages (treatment).
    print("Treatment funnel (GT presence over the 253 visual turns):")
    any_branch = sum(1 for k in keys if treat.get(k, {}).get("branch"))
    fus = [treat.get(k, {}).get("fusion") for k in keys]
    lg = [treat.get(k, {}).get("lgbm") for k in keys]
    in_pool = sum(1 for r in fus if r is not None and r <= POOL_K)
    lgbm20 = sum(1 for r in lg if r is not None and r <= 20)
    print(f"  GT in ANY branch@1000 : {any_branch:>4}  ({pct(any_branch, n)})")
    print(f"  GT in fused pool@{POOL_K} (lgbm-scorable): {in_pool:>4}  ({pct(in_pool, n)})")
    print(f"  GT in lgbm top-20     : {lgbm20:>4}  ({pct(lgbm20, n)})\n")

    # 3. The crux: GTs that SigLIP newly contributes vs baseline union — where do they land?
    #    "newly reachable" = GT absent from every baseline branch@1000 but present in treatment.
    def base_covered(k):
        return bool(base.get(k, {}).get("branch"))
    newly = [k for k in keys if not base_covered(k) and treat.get(k, {}).get("branch")]
    sig_newly = [k for k in newly if treat[k]["branch"].get(SIGLIP) is not None]
    print(f"GT newly reachable in treatment (absent from all baseline branches): {len(newly)}")
    print(f"  ...of which SigLIP contributes: {len(sig_newly)}")
    if newly:
        print("  fusion-rank bucket of newly-reachable GTs:")
        from collections import Counter
        cf = Counter(bucket(treat[k]["fusion"]) for k in newly)
        cl = Counter(bucket(treat[k]["lgbm"]) for k in newly)
        for b in ["1-20", "21-100", f"101-{POOL_K}", f"{POOL_K+1}-1000", "absent"]:
            print(f"    fusion {b:<10} {cf.get(b,0):>3}   |  lgbm {b:<10} {cl.get(b,0):>3}")

    # 4. Did adding SigLIP move ANY visual GT's final lgbm rank? (net hit@20 is flat —
    #    check churn: into-top20 vs out-of-top20.)
    into = out = 0
    for k in keys:
        b = base.get(k, {}).get("lgbm"); t = treat.get(k, {}).get("lgbm")
        b20 = b is not None and b <= 20
        t20 = t is not None and t <= 20
        if t20 and not b20:
            into += 1
        elif b20 and not t20:
            out += 1
    print(f"\nlgbm top-20 churn (treatment vs baseline): +{into} entered / -{out} dropped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
