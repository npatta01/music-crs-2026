"""Add the 9 LIVE new features to the MAIN model (all rows), v10's exact training
protocol (user-grouped folds + 10% ES holdout + early stopping). Compare to v10
on the full devset AND the pivot slice; dump gain importances.

Live features kept (from the pivot experiment's importances): fused_rrf_rank,
fused_rrf_score, away_abandoned_artist_cos__{cf,clap,siglip}, tag_overlap_positive_idf,
has_style_reference, has_contrast, n_abandoned_artists. The 6 dead ones are dropped.

Saves new_features_all.npy for reuse (lean-pivot rerun).
"""
from __future__ import annotations
import json, math, random, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb

sys.path.insert(0, "scripts/rerank")
import train_v9 as T
from build_features import Catalog
from features_v9 import catalog_tag_key

BASE = Path("exp/analysis/rerank/train_v9")
TRACE = Path("exp/analysis/rerank/pruned_c63958_trace.jsonl")
DB_URI = Path("cache/lancedb")
GT_PATH = Path("exp/ground_truth/devset.json")
NEWPATH = Path("exp/analysis/rerank/new_features_all.npy")
EMB_FIELDS = ["cf_bpr", "audio_laion_clap", "image_siglip2"]
ART_CAP = 30
NEW_COLS = (["fused_rrf_rank", "fused_rrf_score"]
            + [f"away_abandoned_artist_cos__{f}" for f in EMB_FIELDS]
            + ["tag_overlap_positive_idf", "has_style_reference", "has_contrast",
               "n_abandoned_artists"])


def _centroid(cat, field, track_ids):
    vs = [cat.v(field, str(t)) for t in track_ids]
    vs = [v for v in vs if v is not None]
    if not vs:
        return None
    c = np.mean(vs, axis=0); nrm = np.linalg.norm(c)
    return c / nrm if nrm > 0 else None


def compute_new(cat, sid_codes, turn, trk_codes, sid_uniq, trk_uniq, n):
    NEW = np.full((n, len(NEW_COLS)), np.nan, dtype=np.float32)
    ci = {c: j for j, c in enumerate(NEW_COLS)}
    art_tracks = defaultdict(list)
    for tid, m in cat.meta.items():
        for a in m["artists"]:
            if len(art_tracks[a]) < ART_CAP:
                art_tracks[a].append(tid)
    by_turn = defaultdict(list)
    for r in range(n):
        by_turn[(int(sid_codes[r]), int(turn[r]))].append(r)
    sid_to_code = {str(s): i for i, s in enumerate(sid_uniq)}
    want = set(by_turn.keys())
    fields = [f for f in EMB_FIELDS if f in cat.vec]
    done = 0
    with open(TRACE) as fh:
        for line in fh:
            rec = json.loads(line)
            sc = sid_to_code.get(str(rec.get("session_id")))
            if sc is None:
                continue
            key = (sc, int(rec.get("turn_number")))
            if key not in want:
                continue
            rows = by_turn[key]
            tr = rec.get("trace") or {}; res = tr.get("resolver") or {}; st = tr.get("state") or {}
            rejected_tracks = list(res.get("rejected_track_ids") or [])
            abandoned = set(str(a) for a in (res.get("rejected_artist_ids") or []))
            for t in rejected_tracks:
                m = cat.meta.get(str(t))
                if m:
                    abandoned.update(str(a) for a in m["artists"])
            pos_tags = set(catalog_tag_key(str(t)) for t in (res.get("positive_tags") or [])) - {""}
            tf = st.get("track_feedback") or []
            has_contrast = float(any(str(x.get("role")) == "contrast" for x in tf))
            has_styleref = float(any(str(f.get("relation")) == "style_reference" for f in (st.get("facts") or [])))
            ab_tracks = [t for a in abandoned for t in art_tracks.get(a, [])]
            cent = {f: _centroid(cat, f, ab_tracks) for f in fields}
            fused = (tr.get("branches") or {}).get("fused") or []
            fpos = {str(t): (i + 1, float(s)) for i, (t, s) in enumerate(fused)}
            for r in rows:
                tid = str(trk_uniq[int(trk_codes[r])]); m = cat.meta.get(tid)
                for f in fields:
                    cv = cat.v(f, tid); c = cent[f]
                    if cv is not None and c is not None:
                        NEW[r, ci[f"away_abandoned_artist_cos__{f}"]] = float(np.dot(cv, c))
                if m:
                    NEW[r, ci["tag_overlap_positive_idf"]] = float(sum(cat.tag_idf.get(t, 0.0) for t in (m["tag_keys"] & pos_tags)))
                fr = fpos.get(tid)
                if fr:
                    NEW[r, ci["fused_rrf_rank"]] = fr[0]; NEW[r, ci["fused_rrf_score"]] = fr[1]
                NEW[r, ci["has_style_reference"]] = has_styleref
                NEW[r, ci["has_contrast"]] = has_contrast
                NEW[r, ci["n_abandoned_artists"]] = len(abandoned)
            done += 1
            if done % 5000 == 0:
                print(f"  processed {done} turns", flush=True)
    print(f"processed {done} turns total", flush=True)
    return NEW


def ndcg(df_rows):
    denom = df_rows.groupby(["sid", "turn"]).ngroups; nd = 0.0
    for _, g in df_rows.groupby(["sid", "turn"], sort=False):
        gt = g[g.y == 1]
        if not len(gt):
            continue
        r = T.gt_tie_averaged_rank(g.score.to_numpy(), float(gt.score.iloc[0]))
        nd += (1 / math.log2(r + 1)) if r <= 20 else 0
    return nd / denom, denom


def main():
    meta = json.load(open(BASE / "meta.json")); cols = meta["cols"]; cat_idx = meta["cat_idx"]
    cm = json.load(open(BASE / "cat_maps_v9.json"))
    X = np.load(str(BASE / "X.npy"), mmap_mode="r"); y = np.load(BASE / "y.npy"); n = len(y)
    turn = np.load(BASE / "turn_arr.npy"); sid_codes = np.load(BASE / "sid_codes.npy")
    trk_codes = np.load(BASE / "trk_codes.npy"); sid_fold = np.load(BASE / "sid_fold.npy")
    row_w = np.load(BASE / "row_weights.npy"); sid_uniq = json.load(open(BASE / "sid_uniq.json"))
    trk_uniq = json.load(open(BASE / "trk_uniq.json"))
    pmask = T.pivot_mask_from_codes(X, cols, cm)

    if NEWPATH.exists():
        NEW = np.load(NEWPATH)
        print(f"loaded cached new features {NEW.shape}", flush=True)
    else:
        cat = Catalog(str(DB_URI), "music_track_catalog")
        print(f"catalog loaded; emb fields {[f for f in EMB_FIELDS if f in cat.vec]}", flush=True)
        NEW = compute_new(cat, sid_codes, turn, trk_codes, sid_uniq, trk_uniq, n)
        np.save(NEWPATH, NEW)
    all_cols = cols + NEW_COLS
    mono = [(-1 if c == "is_played_track" else 0) for c in all_cols]
    params = dict(T.LGB_PARAMS, monotone_constraints=mono)

    sess_user = {str(r["session_id"]): str(r["user_id"]) for r in json.load(open(GT_PATH))}
    row_fold = sid_fold[sid_codes]
    oof = np.full(n, np.nan, dtype=np.float64); gains = np.zeros(len(all_cols))
    for fold in range(5):
        train_users = sorted({sess_user.get(s, s) for i, s in enumerate(sid_uniq) if sid_fold[i] not in (fold, -1)})
        rng = random.Random(1000 + fold); rng.shuffle(train_users)
        es_users = set(train_users[: max(1, len(train_users) // 10)])
        sid_es = np.array([sess_user.get(s, s) in es_users for s in sid_uniq]); row_es = sid_es[sid_codes]
        tr_i = np.flatnonzero((row_fold != fold) & (row_fold != -1) & (~row_es))
        es_i = np.flatnonzero((row_fold != fold) & (row_fold != -1) & row_es)
        tr_i, trg = T._grouped(tr_i, sid_codes, turn); es_i, esg = T._grouped(es_i, sid_codes, turn)
        Xtr = np.hstack([np.ascontiguousarray(X[tr_i]), NEW[tr_i]])
        d = lgb.Dataset(Xtr, label=y[tr_i], group=trg, weight=row_w[tr_i], feature_name=all_cols,
                        categorical_feature=cat_idx, free_raw_data=True); d.construct(); del Xtr
        Xes = np.hstack([np.ascontiguousarray(X[es_i]), NEW[es_i]])
        dv = lgb.Dataset(Xes, label=y[es_i], group=esg, weight=row_w[es_i], reference=d, free_raw_data=False)
        dv.construct(); del Xes
        bst = lgb.train(params, d, num_boost_round=T.MAX_ROUNDS, valid_sets=[dv], valid_names=["es"],
                        callbacks=[lgb.early_stopping(T.ES_ROUNDS, verbose=False), lgb.log_evaluation(0)])
        best = bst.best_iteration or T.MAX_ROUNDS
        te_i = np.flatnonzero(row_fold == fold)
        for lo in range(0, len(te_i), 2_000_000):
            sl = te_i[lo:lo + 2_000_000]
            oof[sl] = bst.predict(np.hstack([np.ascontiguousarray(X[sl]), NEW[sl]]), num_iteration=best)
        gains += bst.feature_importance(importance_type="gain")
        print(f"fold {fold} done (best_iter {best})", flush=True)

    gt_rows = json.load(open(GT_PATH)); denom_full = len(gt_rows)
    cov = ~np.isnan(oof)
    full = pd.DataFrame({"sid": sid_codes, "turn": turn.astype(int), "y": y, "score": oof})[cov]
    # full devset uses denom = 8000 (matches train_v9 finalize convention)
    nd_full = 0.0
    for _, g in full.groupby(["sid", "turn"], sort=False):
        gt = g[g.y == 1]
        if not len(gt):
            continue
        r = T.gt_tie_averaged_rank(g.score.to_numpy(), float(gt.score.iloc[0]))
        nd_full += (1 / math.log2(r + 1)) if r <= 20 else 0
    nd_full /= denom_full
    piv = full[pmask[full.index] & (row_fold[full.index] != -1)] if False else \
        pd.DataFrame({"sid": sid_codes, "turn": turn.astype(int), "y": y, "score": oof})[pmask & (row_fold != -1) & cov]
    nd_piv, denom_piv = ndcg(piv)
    print("\n================ RESULT ================", flush=True)
    print(f"v10 baseline:           full-devset 0.19305   pivot-slice 0.2351", flush=True)
    print(f"main + 9 new features:  full-devset {nd_full:.5f}   pivot-slice {nd_piv:.4f} ({denom_piv} CV pivot turns)", flush=True)
    order = np.argsort(gains)[::-1]
    print("\n=== top-25 gain importance ===", flush=True)
    for j in order[:25]:
        tag = " <== NEW" if all_cols[j] in set(NEW_COLS) else ""
        print(f"  {gains[j]:12.1f}  {all_cols[j]}{tag}", flush=True)
    print("\n=== new features by gain ===", flush=True)
    for c in NEW_COLS:
        print(f"  {gains[all_cols.index(c)]:12.1f}  {c}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
