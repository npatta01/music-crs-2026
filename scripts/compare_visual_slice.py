#!/usr/bin/env python3
"""Compare baseline vs treatment on the VISUAL slice (issue #127, Lever B).

Computes ranking metrics (hit@20 / ndcg@20 / mrr over the top-20 submission)
and branch-union coverage (union@100 / union@1000 from the trace) restricted to
visual turns (routing_tags.image_or_visual_search == True) within a session
subset. Also reports the NON-visual turns in the same sessions as a regression
guard — the gated branch must leave them byte-for-byte identical.

Trace lines are {session_id, turn_number, user_id, trace:{...}} where the inner
trace carries retrieval.branches[*].hits and routing_tags. Streams traces line
by line (memory-safe) so the 5GB baseline trace is fine.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load_predictions(path: Path) -> dict[tuple[str, int], list[str]]:
    out: dict[tuple[str, int], list[str]] = {}
    for r in json.loads(path.read_text(encoding="utf-8")):
        out[(str(r["session_id"]), int(r["turn_number"]))] = [
            str(t) for t in (r.get("predicted_track_ids") or [])
        ]
    return out


def load_ground_truth(path: Path) -> dict[tuple[str, int], str]:
    out: dict[tuple[str, int], str] = {}
    for r in json.loads(path.read_text(encoding="utf-8")):
        out[(str(r["session_id"]), int(r["turn_number"]))] = str(r["ground_truth_track_id"])
    return out


def _routing_tags(tr: dict) -> dict:
    tags = (tr.get("compiled_state") or {}).get("routing_tags")
    if isinstance(tags, dict):
        return tags
    tags = tr.get("routing_tags")
    return tags if isinstance(tags, dict) else {}


def _union_hit(tr: dict, gt: str, k: int) -> bool:
    for pool in ((tr.get("retrieval") or {}).get("branches") or []):
        for hit in (pool.get("hits") or [])[:k]:
            if hit and str(hit[0]) == gt:
                return True
    return False


def iter_trace(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def turn_keys_and_visual(trace_path: Path, sessions: set[str]):
    """Return {(sid,turn): is_visual} for turns whose session is in `sessions`."""
    out: dict[tuple[str, int], bool] = {}
    for obj in iter_trace(trace_path):
        sid = str(obj["session_id"])
        if sid not in sessions:
            continue
        key = (sid, int(obj["turn_number"]))
        out[key] = bool(_routing_tags(obj.get("trace") or {}).get("image_or_visual_search"))
    return out


def union_by_turn(trace_path: Path, keys: set, gt: dict[tuple[str, int], str]):
    """{(sid,turn): {100: bool, 1000: bool}} for the requested keys."""
    out: dict[tuple, dict[int, bool]] = {}
    for obj in iter_trace(trace_path):
        key = (str(obj["session_id"]), int(obj["turn_number"]))
        if key not in keys:
            continue
        g = gt.get(key)
        tr = obj.get("trace") or {}
        out[key] = {
            100: bool(g) and _union_hit(tr, g, 100),
            1000: bool(g) and _union_hit(tr, g, 1000),
        }
    return out


def rank_metrics(preds: list[str], gt: str):
    """hit@20, ndcg@20, rr over the (top-20) submission list."""
    try:
        r = preds.index(gt) + 1  # 1-indexed
    except ValueError:
        return 0.0, 0.0, 0.0
    if r > 20:
        return 0.0, 0.0, 0.0
    return 1.0, 1.0 / math.log2(r + 1), 1.0 / r


def agg(keys, preds, gt):
    if not keys:
        return {"n": 0, "hit@20": 0.0, "ndcg@20": 0.0, "mrr": 0.0}
    h = n = m = 0.0
    for k in keys:
        hh, nn, mm = rank_metrics(preds.get(k, []), gt.get(k, ""))
        h += hh; n += nn; m += mm
    c = len(keys)
    return {"n": c, "hit@20": h / c, "ndcg@20": n / c, "mrr": m / c}


def agg_union(keys, union):
    if not keys:
        return {"union@100": 0.0, "union@1000": 0.0}
    u100 = sum(1 for k in keys if union.get(k, {}).get(100)) / len(keys)
    u1000 = sum(1 for k in keys if union.get(k, {}).get(1000)) / len(keys)
    return {"union@100": u100, "union@1000": u1000}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-preds", required=True, type=Path)
    ap.add_argument("--baseline-trace", required=True, type=Path)
    ap.add_argument("--treatment-preds", required=True, type=Path)
    ap.add_argument("--treatment-trace", required=True, type=Path)
    ap.add_argument("--ground-truth", required=True, type=Path)
    ap.add_argument("--sessions-file", required=True, type=Path)
    args = ap.parse_args()

    sessions = set(json.loads(args.sessions_file.read_text())["session_ids"])
    gt = load_ground_truth(args.ground_truth)

    # Visual / non-visual turn keys (from treatment trace — small + local).
    flags = turn_keys_and_visual(args.treatment_trace, sessions)
    visual = {k for k, v in flags.items() if v}
    nonvisual = {k for k, v in flags.items() if not v}

    bp = load_predictions(args.baseline_preds)
    tp = load_predictions(args.treatment_preds)
    b_union = union_by_turn(args.baseline_trace, visual, gt)
    t_union = union_by_turn(args.treatment_trace, visual, gt)

    def row(label, keys, preds, union):
        r = agg(keys, preds, gt)
        if union is not None:
            r.update(agg_union(keys, union))
        return label, r

    print(f"sessions={len(sessions)}  visual_turns={len(visual)}  nonvisual_turns={len(nonvisual)}\n")
    print(f"{'metric':<12}{'baseline':>12}{'treatment':>12}{'delta':>12}")
    bm = agg(visual, bp, gt); tm = agg(visual, tp, gt)
    bu = agg_union(visual, b_union); tu = agg_union(visual, t_union)
    bm.update(bu); tm.update(tu)
    for key in ("n", "hit@20", "ndcg@20", "mrr", "union@100", "union@1000"):
        bv, tv = bm[key], tm[key]
        d = "" if key == "n" else f"{tv - bv:+.4f}"
        bvs = f"{bv:.4f}" if key != "n" else str(int(bv))
        tvs = f"{tv:.4f}" if key != "n" else str(int(tv))
        print(f"{'VIS '+key:<12}{bvs:>12}{tvs:>12}{d:>12}")

    print()
    # Regression guard: non-visual turns must be unchanged.
    bn = agg(nonvisual, bp, gt); tn = agg(nonvisual, tp, gt)
    identical = sum(1 for k in nonvisual if bp.get(k) == tp.get(k))
    print(f"NON-VISUAL guard: n={len(nonvisual)}  identical_pred_lists={identical}/{len(nonvisual)}")
    print(f"  baseline  ndcg@20={bn['ndcg@20']:.4f} hit@20={bn['hit@20']:.4f}")
    print(f"  treatment ndcg@20={tn['ndcg@20']:.4f} hit@20={tn['hit@20']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
