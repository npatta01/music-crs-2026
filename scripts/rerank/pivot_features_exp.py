"""Pivot-feature experiment: train on pivot rows with the existing 148 features
PLUS new pivot-specific features (embedding cosines to toward/away reference
centroids, same-artist-as-anchor, positive-tag overlap, fused-RRF, magnitude
flags). Evaluate ONLY on pivot turns vs v10, then dump gain importances.

Reuses the committed build matrix (X.npy) for the 148 existing features and the
saved RRF trace for the new reference features. Pivot-only training uses a fixed
round budget (no noisy early stopping). Round 2 will add artist_transition_prior
(leakage-safe per-fold) if these features show signal.
"""
from __future__ import annotations
import json, math, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb

sys.path.insert(0, "scripts/rerank")
import train_v9 as T
from build_features import Catalog
from features_v9 import catalog_tag_key

ROOT = Path(".")
BASE = ROOT / "exp/analysis/rerank/train_v9"
TRACE = ROOT / "exp/analysis/rerank/pruned_c63958_trace.jsonl"
DB_URI = ROOT / "cache/lancedb"
FIXED_ROUNDS = 200
EMB_FIELDS = ["cf_bpr", "audio_laion_clap", "image_siglip2"]
ART_CAP = 30  # cap tracks per reference artist when building centroids


def _centroid(cat, field, track_ids):
    vs = [cat.v(field, str(t)) for t in track_ids]
    vs = [v for v in vs if v is not None]
    if not vs:
        return None
    c = np.mean(vs, axis=0)
    nrm = np.linalg.norm(c)
    return c / nrm if nrm > 0 else None


def main():
    meta = json.load(open(BASE / "meta.json"))
    cols = meta["cols"]; cat_idx = meta["cat_idx"]
    cm = json.load(open(BASE / "cat_maps_v9.json"))
    X = np.load(str(BASE / "X.npy"), mmap_mode="r")
    y = np.load(BASE / "y.npy"); n = len(y)
    turn = np.load(BASE / "turn_arr.npy"); sid_codes = np.load(BASE / "sid_codes.npy")
    trk_codes = np.load(BASE / "trk_codes.npy"); sid_fold = np.load(BASE / "sid_fold.npy")
    row_w = np.load(BASE / "row_weights.npy")
    sid_uniq = json.load(open(BASE / "sid_uniq.json"))
    trk_uniq = json.load(open(BASE / "trk_uniq.json"))
    pmask = T.pivot_mask_from_codes(X, cols, cm)
    print(f"pivot rows: {int(pmask.sum()):,}", flush=True)

    cat = Catalog(str(DB_URI), "music_track_catalog")
    fields = [f for f in EMB_FIELDS if f in cat.vec]
    print(f"embedding fields available: {fields}", flush=True)
    # artist -> track ids (for abandoned/anchor artist centroids)
    art_tracks = defaultdict(list)
    for tid, m in cat.meta.items():
        for a in m["artists"]:
            if len(art_tracks[a]) < ART_CAP:
                art_tracks[a].append(tid)

    # new feature columns
    new_cols = []
    for f in fields:
        new_cols += [f"toward_anchor_cos__{f}", f"away_rejected_cos__{f}", f"away_abandoned_artist_cos__{f}"]
    new_cols += ["same_artist_as_anchor", "tag_overlap_positive_idf",
                 "fused_rrf_rank", "fused_rrf_score",
                 "n_abandoned_artists", "n_rejected_tracks", "n_anchor_tracks",
                 "has_contrast", "has_style_reference"]
    NEW = np.full((n, len(new_cols)), np.nan, dtype=np.float32)
    cidx = {c: j for j, c in enumerate(new_cols)}

    # pivot rows grouped by (sid_code, turn): list of (row_idx, track_id)
    pivot_idx = np.flatnonzero(pmask)
    by_turn = defaultdict(list)
    for r in pivot_idx:
        by_turn[(int(sid_codes[r]), int(turn[r]))].append(r)
    sid_of = {i: str(s) for i, s in enumerate(sid_uniq)}
    want = set(by_turn.keys())
    # map sid string -> code for trace lookup
    sid_to_code = {str(s): i for i, s in enumerate(sid_uniq)}

    processed = 0
    with open(TRACE) as fh:
        for line in fh:
            rec = json.loads(line)
            sc = sid_to_code.get(str(rec.get("session_id")))
            if sc is None:
                continue
            tn = int(rec.get("turn_number"))
            key = (sc, tn)
            if key not in want:
                continue
            rows = by_turn[key]
            tr = rec.get("trace") or {}
            res = tr.get("resolver") or {}; st = tr.get("state") or {}
            anchor_tracks = list(res.get("anchor_track_ids") or [])
            rejected_tracks = list(res.get("rejected_track_ids") or [])
            anchor_artists = set(str(a) for a in (res.get("anchor_artist_ids") or []))
            abandoned_artists = set(str(a) for a in (res.get("rejected_artist_ids") or []))
            for t in rejected_tracks:
                m = cat.meta.get(str(t))
                if m:
                    abandoned_artists.update(str(a) for a in m["artists"])
            pos_tags = set(catalog_tag_key(str(t)) for t in (res.get("positive_tags") or [])) - {""}
            tf = st.get("track_feedback") or []
            has_contrast = float(any(str(x.get("role")) == "contrast" for x in tf))
            has_styleref = float(any(str(fct.get("relation")) == "style_reference"
                                     for fct in (st.get("facts") or [])))
            abandoned_tracks = [t for a in abandoned_artists for t in art_tracks.get(a, [])]
            cent = {}
            cent["anchor"] = {f: _centroid(cat, f, anchor_tracks + [t for a in anchor_artists for t in art_tracks.get(a, [])]) for f in fields}
            cent["rej"] = {f: _centroid(cat, f, rejected_tracks) for f in fields}
            cent["aband"] = {f: _centroid(cat, f, abandoned_tracks) for f in fields}
            # fused rank/score
            fused = (tr.get("branches") or {}).get("fused") or []
            fpos = {str(t): (i + 1, float(s)) for i, (t, s) in enumerate(fused)}
            for r in rows:
                tid = str(trk_uniq[int(trk_codes[r])])
                m = cat.meta.get(tid)
                for f in fields:
                    cv = cat.v(f, tid)
                    if cv is not None:
                        for ref, key2 in [("anchor", "toward_anchor_cos"), ("rej", "away_rejected_cos"), ("aband", "away_abandoned_artist_cos")]:
                            c = cent[ref][f]
                            if c is not None:
                                NEW[r, cidx[f"{key2}__{f}"]] = float(np.dot(cv, c))
                if m:
                    NEW[r, cidx["same_artist_as_anchor"]] = float(bool(set(m["artists"]) & anchor_artists))
                    NEW[r, cidx["tag_overlap_positive_idf"]] = float(sum(cat.tag_idf.get(t, 0.0) for t in (m["tag_keys"] & pos_tags)))
                fr = fpos.get(tid)
                if fr:
                    NEW[r, cidx["fused_rrf_rank"]] = fr[0]; NEW[r, cidx["fused_rrf_score"]] = fr[1]
                NEW[r, cidx["n_abandoned_artists"]] = len(abandoned_artists)
                NEW[r, cidx["n_rejected_tracks"]] = len(rejected_tracks)
                NEW[r, cidx["n_anchor_tracks"]] = len(anchor_tracks)
                NEW[r, cidx["has_contrast"]] = has_contrast
                NEW[r, cidx["has_style_reference"]] = has_styleref
            processed += 1
            if processed % 200 == 0:
                print(f"  processed {processed} pivot turns", flush=True)
    print(f"processed {processed} pivot turns total", flush=True)

    # assemble training matrix: 148 existing (pivot rows) + new
    all_cols = cols + new_cols
    row_fold = sid_fold[sid_codes]
    depths = FIXED_ROUNDS
    oof = np.full(n, np.nan, dtype=np.float64)
    mono = [(-1 if c == "is_played_track" else 0) for c in all_cols]
    params = dict(T.LGB_PARAMS, monotone_constraints=mono)
    gains = np.zeros(len(all_cols))
    for fold in range(5):
        tr_i = np.flatnonzero((row_fold != fold) & (row_fold != -1) & pmask)
        te_i = np.flatnonzero((row_fold == fold) & pmask)
        tr_i, trg = T._grouped(tr_i, sid_codes, turn)
        Xtr = np.hstack([np.ascontiguousarray(X[tr_i]), NEW[tr_i]])
        d = lgb.Dataset(Xtr, label=y[tr_i], group=trg, weight=row_w[tr_i],
                        feature_name=all_cols, categorical_feature=cat_idx, free_raw_data=True)
        d.construct(); del Xtr
        bst = lgb.train(params, d, num_boost_round=depths, callbacks=[lgb.log_evaluation(0)])
        Xte = np.hstack([np.ascontiguousarray(X[te_i]), NEW[te_i]])
        oof[te_i] = bst.predict(Xte, num_iteration=depths); del Xte
        gains += bst.feature_importance(importance_type="gain")
        print(f"fold {fold} done", flush=True)

    cv = pmask & (row_fold != -1) & ~np.isnan(oof)
    df = pd.DataFrame({"sid": sid_codes, "turn": turn.astype(int), "y": y, "score": oof})[cv]
    denom = df.groupby(["sid", "turn"]).ngroups; nd = 0.0
    for _, g in df.groupby(["sid", "turn"], sort=False):
        gt = g[g.y == 1]
        if not len(gt):
            continue
        r = T.gt_tie_averaged_rank(g.score.to_numpy(), float(gt.score.iloc[0]))
        nd += (1 / math.log2(r + 1)) if r <= 20 else 0
    print(f"\nNEW MODEL (148+{len(new_cols)} feat) pivot-slice NDCG@20 = {nd/denom:.4f}  ({denom} CV pivot turns)", flush=True)
    print("v10 baseline on same turns = 0.2351\n", flush=True)
    order = np.argsort(gains)[::-1]
    print("=== gain importance (all features, top 40) ===", flush=True)
    for j in order[:40]:
        tag = " <== NEW" if all_cols[j] in set(new_cols) else ""
        print(f"  {gains[j]:12.1f}  {all_cols[j]}{tag}", flush=True)
    print("\n=== NEW features only, by gain ===", flush=True)
    for c in new_cols:
        j = all_cols.index(c)
        print(f"  {gains[j]:12.1f}  {c}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
