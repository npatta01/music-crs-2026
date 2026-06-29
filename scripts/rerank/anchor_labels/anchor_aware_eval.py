"""Anchor-aware evaluation (Phase 1).

Scores a devset prediction against the clean anchor labels (anchor-labels-v1.1),
joined by (sid, tn). Two metrics:

1. anchoring_violation_rate@k — among `asked_for_different_artist` turns, the
   fraction where the model's top-k recs repeat the `just_played` artist. The
   same-artist test is a deterministic catalog name match on the MODEL's recs
   (not the LLM, not limited to the GT). Lower is better. This is the metric the
   raw-GT NDCG cannot express (raw GT rewards anchoring).

2. cleaned_ndcg@k — single-gold NDCG averaged over turns whose clean label is NOT
   a NEGATIVE (artist_anchoring / content_violation). Guards against breaking the
   legitimately-gold turns; the poisoned golds are excluded rather than scored.

The labels carry only artist NAMES (`just_played`) and a display `candidate_track`
string — no track ids — so anchoring is measured by artist-name match against the
catalog artist of each predicted track id.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

NEGATIVE_REASONS = {"artist_anchoring", "content_violation"}


def norm_artist(name: str | None) -> str:
    """Casefolded, whitespace-trimmed artist key for deterministic matching."""
    return str(name or "").strip().casefold()


def anchoring_hit(
    pred_artist_sets: list[set[str]], just_played: str, k: int
) -> bool | None:
    """True if any of the top-k predicted tracks is by `just_played`.

    Returns None when `just_played` is empty (turn-1 / no prior artist) — those
    turns are not measurable pivots and are excluded from the rate.
    """
    jp = norm_artist(just_played)
    if not jp:
        return None
    for arts in pred_artist_sets[:k]:
        if jp in arts:
            return True
    return False


def single_gold_ndcg(ranked_ids: list[str], gold_id: str, k: int) -> float:
    """Single-gold NDCG@k: 1/log2(rank+1) if the gold is in the top-k else 0."""
    for i, tid in enumerate(ranked_ids[:k]):
        if tid == gold_id:
            return 1.0 / math.log2(i + 2)
    return 0.0


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-turn results into the headline metrics.

    Each row: {pivot: bool, hit: bool|None, neg: bool, ndcg: float}.
    """
    pivot = [r for r in rows if r["pivot"] and r["hit"] is not None]
    viol = sum(1 for r in pivot if r["hit"])
    clean = [r for r in rows if not r["neg"]]
    clean_ndcg = sum(r["ndcg"] for r in clean) / len(clean) if clean else 0.0
    return {
        "anchoring_violation_rate": (viol / len(pivot)) if pivot else 0.0,
        "n_pivot": len(pivot),
        "n_violations": viol,
        "cleaned_ndcg": clean_ndcg,
        "n_clean": len(clean),
        "n_excluded_poisoned": len(rows) - len(clean),
    }


# ---------------------------------------------------------------------------
# IO + join (not unit-tested; exercised by the CLI / integration run)
# ---------------------------------------------------------------------------

def _load_labels(path: str) -> dict[tuple[str, int], dict]:
    opener = gzip.open if str(path).endswith(".gz") else open
    out: dict[tuple[str, int], dict] = {}
    with opener(path, "rt") as fh:
        for line in fh:
            r = json.loads(line)
            out[(str(r["sid"]), int(r["tn"]))] = r
    return out


def _load_predictions(path: str) -> dict[tuple[str, int], list[str]]:
    data = json.load(open(path))
    return {
        (str(r["session_id"]), int(r["turn_number"])): [str(t) for t in r["predicted_track_ids"]]
        for r in data
    }


def _load_ground_truth(path: str) -> dict[tuple[str, int], str]:
    data = json.load(open(path))
    return {
        (str(r["session_id"]), int(r["turn_number"])): str(r["ground_truth_track_id"])
        for r in data
    }


def _load_artist_map(db_uri: str, table: str) -> dict[str, set[str]]:
    import lancedb

    db = lancedb.connect(db_uri)
    tbl = db.open_table(table)
    amap: dict[str, set[str]] = {}
    for batch in tbl.to_lance().to_batches(columns=["track_id", "artist_name"]):
        d = batch.to_pydict()
        for tid, anm in zip(d["track_id"], d["artist_name"]):
            names = anm if isinstance(anm, list) else ([anm] if anm is not None else [])
            amap[str(tid)] = {norm_artist(n) for n in names if n}
    return amap


def evaluate(
    predictions: dict[tuple[str, int], list[str]],
    labels: dict[tuple[str, int], dict],
    ground_truth: dict[tuple[str, int], str],
    artist_of: dict[str, set[str]],
    k_violation: int = 20,
    k_ndcg: int = 20,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    per_k = {1: 0, 5: 0, 20: 0}
    per_k_n = 0
    for key, lab in labels.items():
        preds = predictions.get(key)
        if preds is None:
            continue
        pred_arts = [artist_of.get(t, set()) for t in preds]
        is_pivot = bool(lab.get("asked_for_different_artist"))
        hit = anchoring_hit(pred_arts, lab.get("just_played", ""), k_violation) if is_pivot else None
        neg = str(lab.get("label")) == "NEGATIVE" and str(lab.get("label_reason")) in NEGATIVE_REASONS
        gold = ground_truth.get(key)
        ndcg = single_gold_ndcg(preds, gold, k_ndcg) if gold else 0.0
        rows.append({"pivot": is_pivot, "hit": hit, "neg": neg, "ndcg": ndcg})
        if is_pivot and norm_artist(lab.get("just_played", "")):
            per_k_n += 1
            for kk in per_k:
                if anchoring_hit(pred_arts, lab.get("just_played", ""), kk):
                    per_k[kk] += 1
    agg = aggregate(rows)
    agg["violation_rate_at_k"] = {kk: (per_k[kk] / per_k_n if per_k_n else 0.0) for kk in per_k}
    agg["n_turns_scored"] = len(rows)
    agg["label_dist"] = dict(Counter(str(l.get("label")) for l in labels.values()))
    return agg


def main() -> None:
    ap = argparse.ArgumentParser(description="Anchor-aware devset eval (Phase 1).")
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--dev-labels", required=True)
    ap.add_argument("--ground-truth", required=True)
    ap.add_argument("--catalog-db-uri", default="cache/lancedb")
    ap.add_argument("--catalog-table", default="music_track_catalog")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    preds = _load_predictions(a.predictions)
    labels = _load_labels(a.dev_labels)
    gt = _load_ground_truth(a.ground_truth)
    artist_of = _load_artist_map(a.catalog_db_uri, a.catalog_table)
    metrics = evaluate(preds, labels, gt, artist_of)
    text = json.dumps(metrics, indent=2)
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
