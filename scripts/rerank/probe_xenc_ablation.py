"""Corrected cross-encoder labeler ablation (advisor-reviewed).

Question: does (1) a better PROMPT, (2) more ORGANIZER context, or (3) a LARGER MODEL improve
the cross-encoder's usefulness as a bi-encoder data labeler — measured by MINING YIELD, not
"recognition"?

HEADLINE metric = clean-negative rate = mean per-turn fraction of mined hard-negs scoring BELOW
the trusted GT (rank-based -> comparable across local 0.6B P(yes) and DeepInfra 4B scores).
Reported OVERALL and STRATIFIED by whether the 0.6B-base run already recognized the GT
(recognized = base P(yes) >= 0.05) — the key question is whether anything RESCUES the
currently-unrecognized turns.

Guards (per advisor panel):
  - placebo arm: base query padded with matched-length irrelevant boilerplate. If a "rich" gain is
    matched by placebo, it's token-inflation, not signal.
  - thought arm: FLAGGED LEAKY oracle ceiling (prior-turn assistant `thought` can name the GT);
    never a production label source. Reports a GT-in-thought leak-match rate.
  - DOES_NOT: diagnostic AUC only (it is request-relevant, not a clean negative).
  - secondary rank metrics: AUC(GT vs random), AUC(GT vs mined-neg), %GT top-1.

Run from MAIN checkout (DeepInfra arms need DEEPINFRA_API_KEY in .env):
  .venv/bin/python scripts/rerank/probe_xenc_ablation.py --limit 150
"""
from __future__ import annotations
import argparse, ast, json, os, random, sys, time
from collections import defaultdict

sys.path.insert(0, "scripts/rerank")
from probe_xenc_zeroshot import Qwen3Reranker, INSTRUCT as GENERIC_INSTRUCT
from probe_xenc_mining import load_pairs, auc, pct, MOVES, DOES_NOT

OUT = "exp/analysis/retrieval_exploration/xenc_ablation_results.json"
MUSIC_INSTRUCT = (
    "You are a music recommendation engine. Decide whether the candidate track is one this "
    "specific listener would want played NEXT given their request and listening context. Reward "
    "a track that matches the requested genre / mood / era / artist intent; do not reward a track "
    "that is merely generally popular or loosely on-topic."
)
PLACEBO = (" Please consider the request carefully and apply general music knowledge and good "
           "judgment when assessing whether the track is an appropriate selection here.") * 3


def load_env():
    if os.path.exists(".env"):
        for line in open(".env"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_train_ctx():
    """sid -> rich context from the TRAIN split (no current-turn music/assistant leak at use time)."""
    from datasets import load_dataset
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="train")
    ctx = {}
    for r in ds:
        conv = r.get("conversations")
        if isinstance(conv, str): conv = ast.literal_eval(conv)
        cg = r.get("conversation_goal")
        if isinstance(cg, str): cg = ast.literal_eval(cg)
        up = r.get("user_profile")
        if isinstance(up, str): up = ast.literal_eval(up)
        up = up or {}
        sid = str(r["session_id"]); u, asst, th, pl = {}, {}, {}, defaultdict(list)
        for m in conv:
            tn = int(m["turn_number"]); role = m["role"]
            if role == "user": u[tn] = str(m["content"])
            elif role == "assistant":
                asst[tn] = str(m["content"]); th[tn] = str(m.get("thought") or "")
            elif role == "music": pl[tn].append(str(m["content"]))
        prof = (f"listener: {up.get('age_group','?')} {up.get('gender','')} "
                f"{up.get('country_name','')}, prefers {up.get('preferred_musical_culture','')} "
                f"({up.get('preferred_language','')})").strip()
        ctx[sid] = {"u": u, "asst": asst, "th": th, "pl": pl, "prof": prof,
                    "goal_cat": (cg or {}).get("category", ""), "goal_spec": (cg or {}).get("specificity", ""),
                    "goal_text": (cg or {}).get("listener_goal", "")}
    return ctx


def load_catalog_rich():
    import lancedb
    t = lancedb.connect("cache/lancedb").open_table("music_track_catalog")
    rows = t.search().select(["track_id", "artist_name", "track_name", "album_name",
                              "tag_list", "release_date", "popularity"]).limit(60000).to_list()
    meta = {}
    def first(x): return str(x[0]) if isinstance(x, (list, tuple)) and x else (str(x) if x else "")
    for r in rows:
        tid = str(r["track_id"]); ar = first(r.get("artist_name")); ti = first(r.get("track_name"))
        al = first(r.get("album_name")); tags = [str(x) for x in (r.get("tag_list") or [])]
        yr = ""
        rd = r.get("release_date")
        if rd is not None:
            yr = str(rd)[:4]
        pop = r.get("popularity") or 0.0
        base = f"{ar} - {ti} | {al} | {', '.join(tags[:5])}".strip()
        popb = "very popular" if pop >= 60 else "popular" if pop >= 30 else "niche"
        rich = f"{ar} - {ti} ({yr}) | {al} | {', '.join(tags[:10])} | {popb}".strip()
        meta[tid] = {"artist": ar, "title": ti, "base": base, "rich": rich}
    return meta


# ----------------------------------------------------------------- query/doc builders
def q_base(pairs_q, sid, tn, pos_at, meta):
    q = pairs_q
    prev = pos_at.get((sid, tn - 1))
    if prev and prev in meta:
        q += f"\n[previously recommended] {meta[prev]['artist']} - {meta[prev]['title']}"
    return q


def q_rich(pairs_q, sid, tn, pos_at, meta, ctx):
    c = ctx.get(sid, {})
    parts = [f"[{c.get('prof','')}]", f"[goal:{c.get('goal_cat','')}/{c.get('goal_spec','')}] {c.get('goal_text','')}"]
    for k in range(1, tn):  # full prior conversation (user + assistant text; NO thought, NO music ids)
        if c.get("u", {}).get(k): parts.append(f"user: {c['u'][k]}")
        if c.get("asst", {}).get(k): parts.append(f"assistant: {c['asst'][k]}")
        for ptid in c.get("pl", {}).get(k, []):
            if ptid in meta: parts.append(f"played: {meta[ptid]['artist']} - {meta[ptid]['title']}")
    parts.append(f"user (current request): {c.get('u', {}).get(tn, '')}")
    return "\n".join(p for p in parts if p.strip())


def q_thought(pairs_q, sid, tn, pos_at, meta, ctx):
    """LEAKY oracle: prior-turn assistant thought (generator's justification). NOT for production."""
    q = q_base(pairs_q, sid, tn, pos_at, meta)
    c = ctx.get(sid, {})
    th = c.get("th", {}).get(tn - 1, "")
    if th: q += f"\n[notes] {th}"
    return q


VARIANTS = {
    # name: (query_mode, doc_mode, instruct)
    "base":         ("base",    "base", GENERIC_INSTRUCT),
    "betterprompt": ("base",    "base", MUSIC_INSTRUCT),
    "richdoc":      ("base",    "rich", GENERIC_INSTRUCT),
    "richquery":    ("rich",    "base", GENERIC_INSTRUCT),
    "placebo":      ("placebo", "base", GENERIC_INSTRUCT),
    "all":          ("rich",    "rich", MUSIC_INSTRUCT),
    "thought":      ("thought", "base", GENERIC_INSTRUCT),   # FLAGGED LEAKY
}


def build_query(mode, r, pos_at, meta, ctx):
    if mode == "base":    return q_base(r["q"], r["sid"], r["tn"], pos_at, meta)
    if mode == "placebo": return q_base(r["q"], r["sid"], r["tn"], pos_at, meta) + PLACEBO
    if mode == "rich":    return q_rich(r["q"], r["sid"], r["tn"], pos_at, meta, ctx)
    if mode == "thought": return q_thought(r["q"], r["sid"], r["tn"], pos_at, meta, ctx)
    raise ValueError(mode)


# ----------------------------------------------------------------- scoring backends
class LocalScorer:
    def __init__(self, model_name, dev, bs):
        self.m = Qwen3Reranker(model_name, dev, bs)
    def score(self, instruct, pairs):
        self.m.instruct = instruct
        return self.m.score(pairs)


class DeepInfraScorer:
    """Direct, ALIGNMENT-SAFE DeepInfra reranker. The shared DeepInfraRerankerBackend's
    concurrent path can silently shorten/scramble the score list on a failed batch -> AUC~0.5.
    Here every batch is serial with a strict len(scores)==len(docs) assertion + retries."""
    def __init__(self, model_name, bs, in_flight):
        import os
        self.model = model_name; self.bs = min(bs, 32)
        self.key = os.environ["DEEPINFRA_API_KEY"]
        self.url = f"https://api.deepinfra.com/v1/inference/{model_name}"
    def _post(self, queries, docs):
        import requests, time
        for attempt in range(4):
            try:
                r = requests.post(self.url, json={"queries": queries, "documents": docs},
                                  headers={"Authorization": f"bearer {self.key}"}, timeout=90)
                if r.status_code == 200:
                    s = r.json()["scores"]
                    if len(s) != len(docs):
                        raise RuntimeError(f"score len {len(s)} != {len(docs)}")
                    return s
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(1.5 * (attempt + 1)); continue
                raise RuntimeError(f"{r.status_code}: {r.text[:150]}")
            except Exception:
                if attempt == 3: raise
                time.sleep(1.5 * (attempt + 1))
    def score(self, instruct, pairs):
        # DeepInfra reranker scores N documents against ONE query, NOT 1:1 across mixed
        # queries. pairs are emitted turn-by-turn so identical queries are contiguous ->
        # group each run of same-query pairs into a single request (query repeated x its docs).
        out = []; i = 0; n = len(pairs)
        while i < n:
            q = pairs[i][0]; j = i
            while j < n and pairs[j][0] == q:
                j += 1
            docs = [d for _, d in pairs[i:j]]
            qf = f"Instruct: {instruct}\nQuery: {q}"
            for c in range(0, len(docs), self.bs):
                chunk = docs[c:c + self.bs]
                out.extend(self._post([qf] * len(chunk), chunk))
            i = j
        assert len(out) == len(pairs), (len(out), len(pairs))
        return out


# ----------------------------------------------------------------- metrics
def metrics(turns):
    """turns: list of {gt, negs:[..], dn:[..], rand:[..]} scores."""
    if not turns: return None
    cn = [sum(1 for s in t["negs"] if s < t["gt"]) / len(t["negs"]) for t in turns if t["negs"]]
    gt_all = [t["gt"] for t in turns]
    neg_all = [s for t in turns for s in t["negs"]]
    rand_all = [s for t in turns for s in t["rand"]]
    dn_all = [s for t in turns for s in t["dn"]]
    top1 = [1 if t["gt"] > max(t["negs"] + t["rand"] + [-1e9]) else 0 for t in turns]
    return {"n": len(turns), "clean_neg_rate": (sum(cn) / len(cn)) if cn else float("nan"),
            "auc_gt_rand": auc(gt_all, rand_all), "auc_gt_neg": auc(gt_all, neg_all),
            "auc_gt_dn": auc(gt_all, dn_all) if dn_all else float("nan"),
            "gt_top1_pct": 100 * sum(top1) / len(top1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--n-random", type=int, default=10)
    ap.add_argument("--variants", default="base,betterprompt,richdoc,richquery,placebo,all,thought")
    ap.add_argument("--local-model", default="Qwen/Qwen3-Reranker-0.6B")
    ap.add_argument("--big-model", default="Qwen/Qwen3-Reranker-4B")
    ap.add_argument("--big-variants", default="base,richquery,all,placebo", help="variants to also run on the big (DeepInfra) model")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--in-flight", type=int, default=8)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    load_env()
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    random.seed(0)
    variants = [v for v in a.variants.split(",") if v in VARIANTS]
    big_variants = [v for v in a.big_variants.split(",") if v in VARIANTS]

    print("loading pairs, catalog, train ctx ...", flush=True)
    rows, pos_at, dn_by_sess = load_pairs()
    meta = load_catalog_rich()
    ctx = load_train_ctx()
    moves = [r for r in rows if r["pos"] in meta and r["sid"] in ctx]
    random.shuffle(moves); moves = moves[: a.limit]
    print(f"sample MOVES turns={len(moves)}  variants={variants}  big={a.big_model}:{big_variants}", flush=True)

    # fixed candidate sets per turn (same negs/dn/random across ALL variants+models)
    cand = []
    for r in moves:
        negs = [n for n in r["negs"] if n in meta]
        dn = [t for t in dn_by_sess.get(r["sid"], []) if t in meta and t != r["pos"]]
        forb = {r["pos"], *negs, *dn}; rnd = []
        while len(rnd) < a.n_random:
            t = random.choice(list(meta))
            if t not in forb: rnd.append(t); forb.add(t)
        cand.append({"r": r, "pos": r["pos"], "negs": negs, "dn": dn, "rand": rnd})

    # GT-in-thought leak match (for the thought arm caveat)
    def gt_in_thought(c):
        th = ctx.get(c["r"]["sid"], {}).get("th", {}).get(c["r"]["tn"] - 1, "").lower()
        m = meta[c["pos"]]
        return bool(th) and (m["artist"].lower() in th or m["title"].lower() in th)
    leak = sum(gt_in_thought(c) for c in cand)

    def score_variant(scorer, vname):
        qmode, dmode, instruct = VARIANTS[vname]
        flat = []; idx = []  # pair list + (turn_i, group, j)
        for ti, c in enumerate(cand):
            q = build_query(qmode, c["r"], pos_at, meta, ctx)
            dk = "rich" if dmode == "rich" else "base"
            groups = [("gt", [c["pos"]]), ("negs", c["negs"]), ("dn", c["dn"]), ("rand", c["rand"])]
            for g, ids in groups:
                for j, tid in enumerate(ids):
                    flat.append((q, meta[tid][dk])); idx.append((ti, g, j))
        sc = scorer.score(instruct, flat)
        out = [{"gt": 0.0, "negs": [0.0] * len(c["negs"]), "dn": [0.0] * len(c["dn"]),
                "rand": [0.0] * len(c["rand"])} for c in cand]
        for (ti, g, j), s in zip(idx, sc):
            if g == "gt": out[ti]["gt"] = s
            else: out[ti][g][j] = s
        return out

    results = {}  # (model,variant) -> per-turn scores
    base_recog = None

    # ---- local 0.6B ----
    print(f"\n=== LOCAL {a.local_model} ===", flush=True)
    local = LocalScorer(a.local_model, dev, a.batch_size)
    for v in variants:
        t0 = time.time(); results[("0.6B", v)] = score_variant(local, v)
        if v == "base":
            base_recog = [t["gt"] >= 0.05 for t in results[("0.6B", "base")]]
        print(f"  0.6B/{v} done ({time.time()-t0:.0f}s)", flush=True)

    # ---- big model via DeepInfra ----
    if big_variants and os.environ.get("DEEPINFRA_API_KEY"):
        print(f"\n=== DEEPINFRA {a.big_model} ===", flush=True)
        big = DeepInfraScorer(a.big_model, a.batch_size, a.in_flight)
        for v in big_variants:
            t0 = time.time(); results[("4B", v)] = score_variant(big, v)
            print(f"  4B/{v} done ({time.time()-t0:.0f}s)", flush=True)
    else:
        print("skipping big-model arms (no DEEPINFRA_API_KEY or none requested)", flush=True)

    # ---- report ----
    recog = base_recog or [True] * len(cand)
    print("\n================ ABLATION (headline = clean-neg rate; higher=better) ================")
    print(f"sample={len(cand)} turns | recognized(0.6B base P(yes)>=0.05)={sum(recog)} "
          f"({100*sum(recog)/len(recog):.0f}%) | thought GT-leak={leak}/{len(cand)} "
          f"({100*leak/len(cand):.0f}%)")
    hdr = f"{'model/variant':<22}{'clean-neg':>10}{'  on-RECOG':>11}{'  on-UNRECOG':>13}{'aucGTrand':>11}{'aucGTneg':>10}{'aucGTdn':>9}{'GTtop1%':>9}"
    print(hdr)
    summ = {}
    for key in results:
        per = results[key]
        allm = metrics(per)
        rec = metrics([t for t, b in zip(per, recog) if b])
        unr = metrics([t for t, b in zip(per, recog) if not b])
        summ["/".join(key)] = {"all": allm, "recognized": rec, "unrecognized": unr}
        tag = "/".join(key) + (" *LEAK*" if key[1] == "thought" else "")
        print(f"{tag:<22}{allm['clean_neg_rate']:>10.3f}{rec['clean_neg_rate']:>11.3f}"
              f"{(unr['clean_neg_rate'] if unr else float('nan')):>13.3f}"
              f"{allm['auc_gt_rand']:>11.3f}{allm['auc_gt_neg']:>10.3f}"
              f"{allm['auc_gt_dn']:>9.3f}{allm['gt_top1_pct']:>9.1f}")
    print("\nRead: a real win must raise clean-neg rate on the UNRECOG half WITHOUT placebo matching "
          "it, and lift auc_gt_neg (not just auc_gt_rand). thought=LEAK ceiling, not usable.")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({"config": vars(a), "n": len(cand), "recognized": sum(recog), "thought_leak": leak,
               "summary": summ}, open(a.out, "w"), indent=1, default=str)
    print(f"\nsaved -> {a.out}")


if __name__ == "__main__":
    main()
