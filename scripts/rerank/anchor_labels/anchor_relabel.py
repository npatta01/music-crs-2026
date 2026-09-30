"""Phase 2 — re-label the reranker training parquet with clean anchor labels.

The reranker trains on the devset feature parquet (features_fresh) where the GT
track has `label == 1`. The clean dev labels (anchor-labels-v1.1) re-judge that GT
candidate; on turns labelled NEGATIVE (`artist_anchoring` or `content_violation`)
the GT is a poisoned positive (e.g. liked-the-anchor-anyway). This transform flips
those GT positives to grade-0 (kept, not dropped), so the model is no longer
rewarded for ranking them — the existing `x_same_artist_wants_new` /
`same_artist_as_abandoned` features then learn a real (negative) weight from the
clean POSITIVE different-artist pivot turns.

It also emits an updated label-weights table: the existing per-turn weight times
the clean label's `confidence_weight` (Opus-arbitrated turns count 0.6, etc.).

Idempotent and post-hoc — no rebuild from the (Modal-only) train trace.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import pandas as pd

TARGET_REASONS = {"artist_anchoring", "content_violation"}


def load_labels(path: str) -> dict[tuple[str, int], dict]:
    opener = gzip.open if str(path).endswith(".gz") else open
    out: dict[tuple[str, int], dict] = {}
    with opener(path, "rt") as fh:
        for line in fh:
            r = json.loads(line)
            out[(str(r["sid"]), int(r["tn"]))] = r
    return out


def negative_turns(labels: dict[tuple[str, int], dict]) -> set[tuple[str, int]]:
    """Turns whose clean GT label is a targeted NEGATIVE (anchoring/content)."""
    return {
        k for k, r in labels.items()
        if str(r.get("label")) == "NEGATIVE" and str(r.get("label_reason")) in TARGET_REASONS
    }


def confidence_map(labels: dict[tuple[str, int], dict]) -> dict[tuple[str, int], float]:
    return {k: float(r.get("confidence_weight", 1.0)) for k, r in labels.items()}


def relabel_frame(df: pd.DataFrame, neg: set[tuple[str, int]]) -> tuple[pd.DataFrame, int]:
    """Flip GT-positive (label==1) rows to 0 on negative turns. Returns (df, n_flipped)."""
    df = df.copy()
    key = list(zip(df["session_id"].astype(str), df["turn_number"].astype(int)))
    mask = pd.Series([k in neg for k in key], index=df.index) & (df["label"] == 1)
    n = int(mask.sum())
    df.loc[mask, "label"] = 0
    return df, n


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-label reranker parquet with clean anchor labels.")
    ap.add_argument("--features-src", required=True, help="source features dir (parquet shards)")
    ap.add_argument("--features-dst", required=True, help="destination features dir")
    ap.add_argument("--labels", required=True, help="clean labels jsonl(.gz)")
    ap.add_argument("--weights-src", default=None, help="existing label_weights parquet")
    ap.add_argument("--weights-dst", default=None, help="output label_weights parquet")
    a = ap.parse_args()

    labels = load_labels(a.labels)
    neg = negative_turns(labels)
    print(f"clean labels: {len(labels)} | targeted-NEGATIVE turns: {len(neg)}", flush=True)

    src, dst = Path(a.features_src), Path(a.features_dst)
    dst.mkdir(parents=True, exist_ok=True)
    total_flip = 0
    for sh in sorted(src.glob("shard_*.parquet")):
        df = pd.read_parquet(sh)
        df, n = relabel_frame(df, neg)
        total_flip += n
        df.to_parquet(dst / sh.name, index=False)
        print(f"  {sh.name}: flipped {n}", flush=True)
    print(f"total GT positives flipped to grade-0: {total_flip}", flush=True)

    if a.weights_src and a.weights_dst:
        cm = confidence_map(labels)
        w = pd.read_parquet(a.weights_src)
        keys = list(zip(w["session_id"].astype(str), w["turn_number"].astype(int)))
        w["weight"] = [wt * cm.get(k, 1.0) for wt, k in zip(w["weight"], keys)]
        Path(a.weights_dst).parent.mkdir(parents=True, exist_ok=True)
        w.to_parquet(a.weights_dst, index=False)
        print(f"wrote weighted label_weights -> {a.weights_dst}", flush=True)


if __name__ == "__main__":
    main()
