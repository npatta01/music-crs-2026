"""Exp A read-out: paired held-out LightGBM A/B (baseline judge vs +scout) + importance.

Trains LambdaMART rankers on the SAME session-held-out split of an augmented features parquet:
a baseline (scout dropped) and one "+form" model per requested scout FORM. Reports held-out
nDCG@20 / Hit@20 and the per-seed delta vs baseline + the scout gain-importance rank.

Scout FORMS (the advisor's point: the judge's top features are within-pool RANKS, so a raw
cosine scalar may under-power the encoder — test the rank/percentile forms too):
  raw  = scout_cos                              (raw query.doc cosine)
  rank = pct_scout_cos + scout_rank_in_pool     (within-turn percentile + integer rank of scout_cos)
  both = scout_cos + pct_scout_cos + scout_rank_in_pool
  base = scout_base_cos                         (un-fine-tuned control)
pct_scout_cos / scout_rank_in_pool are computed here per turn from scout_cos (not stored).

    python scripts/rerank/eval_scout_feature.py --features exp/analysis/rerank/v10/features_b1_l2048 \
        --forms raw,rank,both --seed 0 --max-turns 4000
"""
from __future__ import annotations
import argparse, math
import numpy as np, pyarrow.dataset as pds, lightgbm as lgb

ID = {"session_id", "turn_number", "track_id", "label"}  # keep rrf_* as features (match deployed set)
SCOUT_ALL = ["scout_cos", "scout_base_cos", "pct_scout_cos", "scout_rank_in_pool"]
FORMS = {
    "raw": ["scout_cos"],
    "rank": ["pct_scout_cos", "scout_rank_in_pool"],
    "both": ["scout_cos", "pct_scout_cos", "scout_rank_in_pool"],
    "base": ["scout_base_cos"],
}


def groups(df):
    df = df.sort_values(["session_id", "turn_number"], kind="stable").reset_index(drop=True)
    k = (df.session_id.astype(str) + "|" + df.turn_number.astype(str)).to_numpy()
    ch = np.concatenate([[True], k[1:] != k[:-1]]); st = np.flatnonzero(ch)
    return df, np.diff(np.append(st, len(k)))


def main():
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--forms", default="raw", help="comma list of scout forms: raw,rank,both,base")
    ap.add_argument("--drop", default="", help="comma list of base features to BLACKLIST (e.g. artist_best_rank_in_union)")
    ap.add_argument("--drop-prefixes", default="", help="comma list of prefixes; any base feature starting with one is BLACKLISTED (retriever-coupling: rank__,score__,z__score__,margin__,ratio__,hit__,rrf,pct_)")
    ap.add_argument("--max-turns", type=int, default=4000)
    ap.add_argument("--rounds", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--num-threads", type=int, default=4)  # cap CPU so local runs aren't killed
    a = ap.parse_args()
    forms = [f for f in a.forms.split(",") if f]
    for f in forms:
        assert f in FORMS, f"unknown form {f}; choose from {list(FORMS)}"
    ds = pds.dataset(a.features); names = ds.schema.names
    assert "scout_cos" in names, f"scout_cos not in {a.features}"
    feat_all = [c for c in names if c not in ID]
    cols = feat_all + ["session_id", "turn_number", "label"]

    keep = []; seen = set(); done = False
    for b in ds.to_batches(columns=cols, batch_size=300000):
        d = b.to_pandas(); d["k"] = list(zip(d.session_id, d.turn_number.astype(int)))
        for k in d["k"].unique():
            seen.add(k)
            if len(seen) > a.max_turns: done = True; break
        keep.append(d[d["k"].isin(list(seen)[: a.max_turns])])
        if done: break
    df = pd.concat(keep, ignore_index=True); df = df[df["k"].isin(list(seen)[: a.max_turns])]
    g = df.groupby("k").label.max(); ok = set(g[g > 0].index); df = df[df["k"].isin(ok)].reset_index(drop=True)

    # within-turn rank forms of the scout cosine (computed here, not stored)
    df["scout_rank_in_pool"] = df.groupby("k")["scout_cos"].rank(ascending=False, method="average")
    df["pct_scout_cos"] = df.groupby("k")["scout_cos"].rank(pct=True, method="average")

    base_feats = [c for c in feat_all if c not in SCOUT_ALL]
    for c in base_feats:  # rank/pct/scout cols are numeric; only categoricals need factorizing
        if not pd.api.types.is_numeric_dtype(df[c]): df[c] = pd.factorize(df[c].fillna("").astype(str))[0]
    sess = pd.unique(df.session_id); rng = np.random.default_rng(a.seed); rng.shuffle(sess)
    te = set(sess[: max(1, len(sess) // 5)])
    trd = df[~df.session_id.isin(te)]; ted = df[df.session_id.isin(te)]
    trd, trg = groups(trd); ted2, teg = groups(ted)
    print(f"base_feats={len(base_feats)} train_turns={len(trg)} heldout_turns={len(teg)} seed={a.seed}", flush=True)

    def run(feats, label):
        dtr = lgb.Dataset(trd[feats].to_numpy(np.float32), label=trd.label.to_numpy(), group=trg)
        bo = lgb.train(dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[20], num_leaves=63,
                            learning_rate=0.05, min_data_in_leaf=50, lambdarank_truncation_level=200,
                            num_threads=a.num_threads, verbosity=-1), dtr, num_boost_round=a.rounds)
        sc = bo.predict(ted2[feats].to_numpy(np.float32)); ted = ted2.assign(s=sc)
        nd = hit = nt = 0
        for k, gg in ted.groupby((ted.session_id + "|" + ted.turn_number.astype(str))):
            gt = gg[gg.label == 1]
            if len(gt) == 0: continue
            nt += 1; r = int((gg.s > gt.s.iloc[0]).sum()) + 1
            nd += 1 / math.log2(r + 1) if r <= 20 else 0; hit += 1 if r <= 20 else 0
        nd /= nt; hit /= nt
        print(f"  [{label:<26}] nDCG@20={nd:.4f}  Hit@20={hit:.4f}", flush=True)
        return nd, hit, bo

    drop_list = [c for c in a.drop.split(",") if c]
    missing = [c for c in drop_list if c not in base_feats]
    assert not missing, f"--drop features not in base: {missing}"
    prefixes = tuple(p for p in a.drop_prefixes.split(",") if p)
    if prefixes:
        pref_hits = [c for c in base_feats if c.startswith(prefixes) and c not in drop_list]
        drop_list += pref_hits
        print(f"--drop-prefixes {prefixes} -> blacklisting {len(pref_hits)} more (e.g. {pref_hits[:6]})", flush=True)
    if drop_list:
        kept = [c for c in base_feats if c not in drop_list]
        print(f"BLACKLIST {len(drop_list)} features; KEEP {len(kept)} (e.g. {kept[:10]})", flush=True)
    print("=== held-out LightGBM A/B (deployed feature set) ===", flush=True)
    nd_full, _, _ = run(base_feats, "FULL base (no scout)")            # the reference judge
    if drop_list:
        dropped = [c for c in base_feats if c not in drop_list]
        nd_drop, _, _ = run(dropped, f"DROP {drop_list} (no scout)")
        print(f"COST[drop] seed={a.seed} nDCG@20 = {nd_drop - nd_full:+.4f}  (dropped={nd_drop:.4f} full={nd_full:.4f})", flush=True)
        base_for_forms = dropped; nd_base = nd_drop; tag = "drop+"
    else:
        base_for_forms = base_feats; nd_base = nd_full; tag = "+"
    for f in forms:
        wf = base_for_forms + FORMS[f]
        nd, _, bo = run(wf, f"{tag}{f} ({'+'.join(FORMS[f])})")
        # delta vs the LOCAL base (drop or full), plus recovery vs the FULL reference when dropping
        rec = f"  RECOVER vs full = {nd - nd_full:+.4f}" if drop_list else ""
        print(f"DELTA[{tag}{f}] seed={a.seed} nDCG@20 = {nd - nd_base:+.4f}  (with={nd:.4f} base={nd_base:.4f}){rec}", flush=True)
        imp = bo.feature_importance(importance_type="gain")
        order = np.argsort(-imp); ranklist = list(np.array(wf)[order])
        for s in FORMS[f]:
            if s in ranklist:
                print(f"    {s:<20} gain rank: {ranklist.index(s)+1} / {len(wf)}", flush=True)


if __name__ == "__main__":
    main()
