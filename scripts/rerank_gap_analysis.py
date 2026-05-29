"""Gap analysis: where does the reranker help, where does it not, and where
is the achievable headroom from a perfect reranker on this retrieval pool?
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset

D = Path("evaluator/exp/inference/devset")
BASE = D / "v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.json"
RERK = D / "v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.rerank_Qwen_Qwen3-Reranker-0.6B_structured_rrf_w0.5-1.0.json"
GT = Path("evaluator/exp/ground_truth/devset.json")


def _norm_artist(a):
    if isinstance(a, list):
        return tuple(sorted(a))
    return a


def load_track_to_artist():
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks")
    return {r["track_id"]: _norm_artist(r["artist_name"]) for r in ds}


def dcg(rel):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rel))


def ndcg_at_k(predicted, gt, k):
    rel = [1 if t == gt else 0 for t in predicted[:k]]
    idcg = dcg([1] + [0] * (k - 1))
    return dcg(rel) / idcg if idcg else 0.0


def main():
    print("loading metadata, gt, predictions...")
    t2a = load_track_to_artist()
    gt_rows = json.loads(GT.read_text())
    gt_map = {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"] for r in gt_rows}
    base = json.loads(BASE.read_text())
    rerk = json.loads(RERK.read_text())
    # Index by (sid, tn)
    base_by_key = {(r["session_id"], r["turn_number"]): r["predicted_track_ids"] for r in base}
    rerk_by_key = {(r["session_id"], r["turn_number"]): r["predicted_track_ids"] for r in rerk}

    # Walk sessions in order to compute prior-artists per turn
    print("building per-turn prior-artists set...")
    by_session = defaultdict(list)
    for r in base:
        by_session[r["session_id"]].append(r)
    for sid in by_session:
        by_session[sid].sort(key=lambda r: r["turn_number"])

    rows = []
    for sid, turns in by_session.items():
        prior_artists = set()
        for r in turns:
            tn = r["turn_number"]
            g = gt_map.get((sid, tn))
            if not g:
                continue
            gt_artist = t2a.get(g)
            base_pred = base_by_key.get((sid, tn)) or []
            rerk_pred = rerk_by_key.get((sid, tn)) or []
            novel = gt_artist not in prior_artists if gt_artist else None
            # rank-of-GT in each
            try:
                base_rank = base_pred.index(g) + 1
            except ValueError:
                base_rank = None
            try:
                rerk_rank = rerk_pred.index(g) + 1
            except ValueError:
                rerk_rank = None
            rows.append({
                "sid": sid,
                "turn": tn,
                "novel": novel,
                "n_prior_artists": len(prior_artists),
                "gt_artist": gt_artist,
                "base_rank": base_rank,
                "rerk_rank": rerk_rank,
            })
            if gt_artist:
                prior_artists.add(gt_artist)

    n = len(rows)
    print(f"\nscored {n} turns")

    # Headline metrics
    def metrics(rows, key):
        hit20 = sum(1 for r in rows if r[key] is not None and r[key] <= 20) / len(rows)
        hit100 = sum(1 for r in rows if r[key] is not None and r[key] <= 100) / len(rows)
        hit200 = sum(1 for r in rows if r[key] is not None and r[key] <= 200) / len(rows)
        ndcg20 = sum(1.0 / math.log2(r[key] + 1) if (r[key] is not None and r[key] <= 20) else 0 for r in rows) / len(rows)
        mrr = sum(1.0 / r[key] if r[key] is not None else 0 for r in rows) / len(rows)
        return {"Hit@20": hit20, "Hit@100": hit100, "Hit@200": hit200, "NDCG@20": ndcg20, "MRR": mrr, "n": len(rows)}

    print("\n=== HEADLINE (all turns) ===")
    base_m = metrics(rows, "base_rank")
    rerk_m = metrics(rows, "rerk_rank")
    print(f"  {'metric':<10} {'base':>10} {'reranked':>10} {'delta':>10} {'rel':>6}")
    for k in ["Hit@20", "Hit@100", "Hit@200", "NDCG@20", "MRR"]:
        d = rerk_m[k] - base_m[k]
        rel = d / base_m[k] * 100 if base_m[k] else 0
        print(f"  {k:<10} {base_m[k]:>10.4f} {rerk_m[k]:>10.4f} {d:>+10.4f} {rel:>+5.1f}%")

    # Cohort: novel-artist vs continuation
    print("\n=== COHORT: novel-artist vs continuation ===")
    novel = [r for r in rows if r["novel"] is True]
    cont = [r for r in rows if r["novel"] is False]
    print(f"  novel-artist: {len(novel)} ({len(novel)/n:.1%})  |  continuation: {len(cont)} ({len(cont)/n:.1%})")
    for label, rs in [("novel-artist", novel), ("continuation", cont)]:
        bm = metrics(rs, "base_rank")
        rm = metrics(rs, "rerk_rank")
        print(f"\n  --- {label} (n={len(rs)}) ---")
        print(f"  {'metric':<10} {'base':>10} {'reranked':>10} {'delta':>10} {'rel':>6}")
        for k in ["Hit@20", "Hit@100", "NDCG@20", "MRR"]:
            d = rm[k] - bm[k]
            rel = d / bm[k] * 100 if bm[k] else 0
            print(f"  {k:<10} {bm[k]:>10.4f} {rm[k]:>10.4f} {d:>+10.4f} {rel:>+5.1f}%")

    # Per-turn breakdown
    print("\n=== PER-TURN BREAKDOWN ===")
    print(f"  {'turn':<5} {'n':>6} {'base@20':>10} {'rerk@20':>10} {'Δ@20':>10} {'baseN20':>10} {'rerkN20':>10} {'ΔN20':>10}")
    for tn in range(1, 9):
        rs = [r for r in rows if r["turn"] == tn]
        if not rs:
            continue
        bm = metrics(rs, "base_rank")
        rm = metrics(rs, "rerk_rank")
        print(f"  {tn:<5} {len(rs):>6} {bm['Hit@20']:>10.4f} {rm['Hit@20']:>10.4f} {rm['Hit@20']-bm['Hit@20']:>+10.4f} {bm['NDCG@20']:>10.4f} {rm['NDCG@20']:>10.4f} {rm['NDCG@20']-bm['NDCG@20']:>+10.4f}")

    # Headroom analysis: where is the GT in the pool?
    print("\n=== HEADROOM: rank-of-GT distribution (base) ===")
    buckets = [("top-1", 1, 1), ("top-5", 2, 5), ("top-20", 6, 20), ("top-50", 21, 50),
               ("top-100", 51, 100), ("top-200", 101, 200), ("201-1000", 201, 1000), ("not in pool", 1001, 999999)]
    for label, lo, hi in buckets:
        n_in = sum(1 for r in rows if r["base_rank"] is not None and lo <= r["base_rank"] <= hi)
        n_in_lost = sum(1 for r in rows if r["base_rank"] is None and label == "not in pool")
        if label == "not in pool":
            n_in = sum(1 for r in rows if r["base_rank"] is None)
        print(f"  {label:<15} {n_in:>5} ({n_in/n:.1%})")

    # Reranker contribution: of turns where GT was in top-200, did we promote it to top-20?
    print("\n=== RERANKER EFFECTIVENESS (turns where GT in base top-200) ===")
    in_top200 = [r for r in rows if r["base_rank"] is not None and r["base_rank"] <= 200]
    print(f"  turns with GT in base top-200: {len(in_top200)} ({len(in_top200)/n:.1%})")
    promoted = sum(1 for r in in_top200 if r["rerk_rank"] is not None and r["rerk_rank"] <= 20)
    base_top20 = sum(1 for r in in_top200 if r["base_rank"] <= 20)
    rerk_top20 = sum(1 for r in in_top200 if r["rerk_rank"] is not None and r["rerk_rank"] <= 20)
    print(f"  base @20:     {base_top20} ({base_top20/len(in_top200):.1%}) — what we had before reranking")
    print(f"  reranked @20: {rerk_top20} ({rerk_top20/len(in_top200):.1%}) — what we got")
    print(f"  perfect rerank @20 ceiling: {len(in_top200)} (100%) — if reranker were perfect")
    print(f"  reranker captured: {(rerk_top20 - base_top20) / (len(in_top200) - base_top20) * 100:.1f}% of the achievable @20 lift on this cohort")

    # Where did GT MOVE (base rank → reranked rank)
    print("\n=== MOVEMENT: base rank → reranked rank (turns where GT in base top-200) ===")
    promoted_into_top20 = sum(1 for r in in_top200 if r["base_rank"] > 20 and r["rerk_rank"] is not None and r["rerk_rank"] <= 20)
    demoted_out_top20 = sum(1 for r in in_top200 if r["base_rank"] <= 20 and (r["rerk_rank"] is None or r["rerk_rank"] > 20))
    held_in_top20 = sum(1 for r in in_top200 if r["base_rank"] <= 20 and r["rerk_rank"] is not None and r["rerk_rank"] <= 20)
    held_below_top20 = sum(1 for r in in_top200 if r["base_rank"] > 20 and (r["rerk_rank"] is None or r["rerk_rank"] > 20))
    print(f"  promoted into top-20 (was 21-200, now ≤20):  {promoted_into_top20}")
    print(f"  demoted out of top-20 (was ≤20, now 21-200): {demoted_out_top20}")
    print(f"  held in top-20:                              {held_in_top20}")
    print(f"  held below top-20:                           {held_below_top20}")
    print(f"  NET top-20 change: {promoted_into_top20 - demoted_out_top20:+d}")


if __name__ == "__main__":
    main()
