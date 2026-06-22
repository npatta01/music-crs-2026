"""Step 1 — cross-encoder label-quality KILL-SWITCH for bi-encoder data mining.

See plans: indexed-wishing-steele.md / exp/analysis/retrieval_exploration/xenc_zeroshot_probe_plan.md

Validates whether the off-the-shelf Qwen3-Reranker can serve as a TRAINING-DATA LABELER for the
conv->track bi-encoder:
  (1) flag FALSE NEGATIVES in the mined negs (cross-encoder ranks a "negative" >= the GT for that
      query) -> drop / treat as soft positive,
  (2) surface SOFT-POSITIVE candidates for a SEPARATE independent judge (non-circular).
This is NOT a retrieval/rerank test.

Per advisor review:
  - Kill-switch = AUC(GT vs RANDOM) with bootstrap CI. ~0.5 => the model can't beat the floor, stop.
  - DOES_NOT is request-relevant (system showed it), NOT a clean negative -> reported as a
    DIAGNOSTIC only (expected lower AUC), never the gate.
  - Per-query RANK thresholds (score is per-(query,doc) softmax over {yes,no}; not comparable
    across queries) -> FN-flag iff a neg outranks the GT for its own query.
  - Query carries prev-recommended-track context (reconstructed from the prior turn's pos_id).

Run from the MAIN checkout:
    .venv/bin/python scripts/rerank/probe_xenc_mining.py --limit 300
"""
from __future__ import annotations
import argparse, bisect, json, os, random, sys, time
from collections import defaultdict

sys.path.insert(0, "scripts/rerank")
from probe_xenc_zeroshot import Qwen3Reranker, load_catalog, BASE_MODEL  # reuse model + catalog

PAIRS = "exp/analysis/retrieval_exploration/retriever_pairs.jsonl"
OUT = "exp/analysis/retrieval_exploration/xenc_mining_results.json"
CAND_OUT = "exp/analysis/retrieval_exploration/xenc_softpos_candidates.jsonl"
MOVES = "MOVES_TOWARD_GOAL"
DOES_NOT = "DOES_NOT_MOVE_TOWARD_GOAL"


def load_pairs():
    rows = []                       # MOVES rows we may sample
    pos_at = {}                     # (sid,tn) -> played track id (for prev-track ctx + DOES_NOT)
    dn_by_sess = defaultdict(list)  # sid -> [DOES_NOT played track ids]
    for line in open(PAIRS):
        d = json.loads(line)
        sid, tn = d["sid"], int(d["tn"]); g = d.get("gpa")
        pid = str(d["pos_id"])
        pos_at[(sid, tn)] = pid
        if g == DOES_NOT:
            dn_by_sess[sid].append(pid)
        if g == MOVES:
            rows.append({"sid": sid, "tn": tn, "q": d["q"], "pos": pid,
                         "negs": [str(x) for x in (d.get("negs_filt") or [])]})
    return rows, pos_at, dn_by_sess


def auc(pos, neg):
    """P(score(pos) > score(neg)) with 0.5 for ties (Mann-Whitney)."""
    if not pos or not neg:
        return float("nan")
    negs = sorted(neg); n = len(negs); s = 0.0
    for p in pos:
        lo = bisect.bisect_left(negs, p); hi = bisect.bisect_right(negs, p)
        s += lo + (hi - lo) * 0.5
    return s / (len(pos) * n)


def pct(a, p):
    a = sorted(a)
    if not a:
        return float("nan")
    return a[min(len(a) - 1, int(round(p / 100 * (len(a) - 1))))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300, help="MOVES turns to sample")
    ap.add_argument("--n-random", type=int, default=20, help="random easy-negatives per turn")
    ap.add_argument("--model", default=BASE_MODEL)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--prev-ctx", action="store_true", default=True,
                    help="append prev-recommended-track to the query (default on)")
    ap.add_argument("--no-prev-ctx", dest="prev_ctx", action="store_false")
    ap.add_argument("--boot", type=int, default=1000, help="bootstrap resamples for CI")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    random.seed(0)

    print("loading pairs + catalog ...", flush=True)
    rows, pos_at, dn_by_sess = load_pairs()
    meta = load_catalog()
    all_tids = list(meta)
    moves = [r for r in rows if r["pos"] in meta]
    random.shuffle(moves); moves = moves[: a.limit]
    print(f"MOVES turns sampled: {len(moves)}; catalog={len(meta)}", flush=True)

    print(f"loading model {a.model} on {dev} ...", flush=True)
    model = Qwen3Reranker(a.model, dev, a.batch_size)

    per_turn = []   # {sid,tn,gt,negs:[(tid,score)],dn:[score],rand:[score]}
    t0 = time.time()
    for i, r in enumerate(moves):
        sid, tn = r["sid"], r["tn"]
        q = r["q"]
        if a.prev_ctx:
            prev = pos_at.get((sid, tn - 1))
            if prev and prev in meta:
                q = f"{q}\n[previously recommended] {meta[prev]['artist']} - {meta[prev]['title']}"
        negs = [n for n in r["negs"] if n in meta]
        dn = [t for t in dn_by_sess.get(sid, []) if t in meta and t != r["pos"]]
        forbidden = {r["pos"], *negs, *dn}
        rnd = []
        while len(rnd) < a.n_random:
            t = random.choice(all_tids)
            if t not in forbidden:
                rnd.append(t); forbidden.add(t)
        order = [r["pos"]] + negs + dn + rnd
        docs = [meta[t]["text"] for t in order]
        sc = model.score([(q, d) for d in docs])
        k = 0
        gt_s = sc[k]; k += 1
        neg_s = sc[k:k + len(negs)]; k += len(negs)
        dn_s = sc[k:k + len(dn)]; k += len(dn)
        rnd_s = sc[k:k + len(rnd)]
        per_turn.append({"sid": sid, "tn": tn, "q": q, "gt": r["pos"], "gt_score": gt_s,
                         "negs": list(zip(negs, neg_s)), "dn": dn_s, "rand": rnd_s})
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(moves)} ({(i+1)/max(1e-9,time.time()-t0):.1f} turns/s)", flush=True)

    # -------- pooled metrics --------
    gt_all = [t["gt_score"] for t in per_turn]
    rand_all = [s for t in per_turn for s in t["rand"]]
    dn_all = [s for t in per_turn for s in t["dn"]]
    neg_all = [s for t in per_turn for (_, s) in t["negs"]]

    def boot_auc(neg_pool_key):
        """bootstrap AUC(GT vs <pool>) resampling TURNS."""
        vals = []
        idx = list(range(len(per_turn)))
        for b in range(a.boot):
            rs = [per_turn[random.choice(idx)] for _ in idx]
            pos = [t["gt_score"] for t in rs]
            neg = [s for t in rs for s in (t["rand"] if neg_pool_key == "rand"
                   else t["dn"] if neg_pool_key == "dn"
                   else [s for (_, s) in t["negs"]])]
            v = auc(pos, neg)
            if v == v:  # not nan
                vals.append(v)
        vals.sort()
        return (pct(vals, 2.5), pct(vals, 97.5)) if vals else (float("nan"), float("nan"))

    auc_rand = auc(gt_all, rand_all)
    auc_dn = auc(gt_all, dn_all)
    auc_neg = auc(gt_all, neg_all)
    ci_rand = boot_auc("rand")

    # -------- per-query FN flags (neg outranks its own GT) --------
    fn_turns = 0; fn_negs = 0; tot_negs = 0; cand_rows = []
    for t in per_turn:
        flagged = [(tid, s) for (tid, s) in t["negs"] if s > t["gt_score"]]
        tot_negs += len(t["negs"]); fn_negs += len(flagged)
        if flagged:
            fn_turns += 1
            cand_rows.append({"sid": t["sid"], "tn": t["tn"], "q": t["q"],
                              "gt": t["gt"], "gt_score": t["gt_score"],
                              "flagged": [{"tid": tid, "text": meta[tid]["text"], "score": s,
                                           "artist": meta[tid]["artist"]} for tid, s in flagged]})

    # -------- report --------
    print("\n================= MINING LABEL-QUALITY (Qwen3-Reranker) =================")
    print(f"turns={len(per_turn)}  prev_ctx={a.prev_ctx}  model={a.model}")
    print("\n[KILL-SWITCH] AUC(GT vs RANDOM) = %.3f  (95%% CI %.3f-%.3f)  %s" %
          (auc_rand, ci_rand[0], ci_rand[1],
           "PASS (>0.5)" if auc_rand > 0.55 else "WEAK/FAIL"))
    print("[diagnostic] AUC(GT vs DOES_NOT) = %.3f  (expected LOWER; DOES_NOT is request-relevant)" % auc_dn)
    print("[diagnostic] AUC(GT vs mined-negs) = %.3f" % auc_neg)
    print("\nscore percentiles            p10    p50    p90")
    for name, arr in [("GT", gt_all), ("mined-neg", neg_all), ("DOES_NOT", dn_all), ("random", rand_all)]:
        print(f"  {name:<12} {pct(arr,10):.3f}  {pct(arr,50):.3f}  {pct(arr,90):.3f}  (n={len(arr)})")
    print(f"\n[FN-FLAG] negs the CE ranks ABOVE their own GT: {fn_negs}/{tot_negs} "
          f"({100*fn_negs/max(1,tot_negs):.1f}% of mined negs); "
          f"{fn_turns}/{len(per_turn)} turns ({100*fn_turns/max(1,len(per_turn)):.1f}%) have >=1.")
    print("   -> these are the false-negative / soft-positive candidates (need INDEPENDENT judge).")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({"config": vars(a), "n_turns": len(per_turn),
               "auc": {"gt_vs_random": auc_rand, "gt_vs_random_ci95": ci_rand,
                       "gt_vs_does_not": auc_dn, "gt_vs_mined_neg": auc_neg},
               "score_pct": {n: {"p10": pct(x, 10), "p50": pct(x, 50), "p90": pct(x, 90), "n": len(x)}
                             for n, x in [("gt", gt_all), ("neg", neg_all), ("dn", dn_all), ("rand", rand_all)]},
               "fn_flag": {"negs_flagged": fn_negs, "negs_total": tot_negs,
                           "turns_with_flag": fn_turns, "turns": len(per_turn)},
               "per_turn": per_turn},
              open(a.out, "w"), indent=1, default=str)
    with open(CAND_OUT, "w") as f:
        for c in cand_rows:
            f.write(json.dumps(c, default=str) + "\n")
    print(f"\nsaved -> {a.out}")
    print(f"soft-positive/FN candidates ({len(cand_rows)} turns) -> {CAND_OUT} (for independent judge)")


if __name__ == "__main__":
    main()
