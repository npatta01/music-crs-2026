"""Zero-shot cross-encoder probe on recoverable misses.

See exp/analysis/retrieval_exploration/xenc_zeroshot_probe_plan.md (advisor-reviewed).

Question: on devset turns the deployed v10 pipeline got WRONG (hit=0) but where the GT is
still in the candidate pool (oracle=1), does an OFF-THE-SHELF Qwen3-Reranker, given a better
conversational prompt, rescue the GT into the top-20 when it reranks the top-K of the deployed
final candidate list?

- before_rank = GT's position in the deployed final (lgbm) 1000-list  (lanes.rank is null for
  misses, so we recompute it here from the trace).
- after_rank  = GT's position after reranking the top-K by the cross-encoder (tail kept in place).
- primary metric = ΔnDCG@20 (single GT: nDCG@20(r) = 1/log2(r+1) if r<=20 else 0).
- baselines the cross-encoder MUST beat: BM25-on-track_text and random shuffle (else a "win" is
  a lexical shortcut, not reasoning).

Self-contained model scoring (replicates the Qwen3-Reranker yes/no template) so it does not
depend on the committed backend's transformers version assumptions.

Run from the MAIN checkout, e.g.:
    .venv/bin/python scripts/rerank/probe_xenc_zeroshot.py --k 200 --arms A,B --limit 0
Smoke:
    .venv/bin/python scripts/rerank/probe_xenc_zeroshot.py --k 200 --arms A,B --limit 20
"""
from __future__ import annotations
import argparse, ast, json, math, os, random, re, sys, time
from collections import Counter, defaultdict

LANES = "exp/analysis/rerank/devset_lanes_v10.jsonl"
GT_FILE = "exp/ground_truth/devset.json"
TRACE = "exp/inference/devset/state_ranker_v10_lgbm_devset_fastlocal_trace.jsonl"
OUT = "exp/analysis/retrieval_exploration/xenc_probe_results.json"
BASE_MODEL = "Qwen/Qwen3-Reranker-0.6B"
MOVES = "MOVES_TOWARD_GOAL"

INSTRUCT = (
    "You are evaluating candidate tracks for a music recommendation system. Judge whether the "
    "candidate track satisfies the user's CURRENT (last) request; use any earlier context only "
    "to resolve references."
)


# --------------------------------------------------------------------------- data loaders
def load_lanes():
    miss, ctrl, lane_of = [], [], {}
    for l in open(LANES):
        r = json.loads(l); key = (r["session_id"], int(r["turn_number"]))
        lane_of[key] = r.get("lane")
        if r.get("oracle") == 1:
            (miss if r.get("hit") == 0 else ctrl).append(key)
    return miss, ctrl, lane_of


def load_gt():
    gt = {}
    for r in json.load(open(GT_FILE)):
        gt[(r["session_id"], int(r["turn_number"]))] = str(r["ground_truth_track_id"])
    return gt


def load_test():
    """devset conversations -> user turns, played track-ids (per turn), goal."""
    from datasets import load_dataset
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    um, played, goal = {}, {}, {}
    for r in ds:
        conv = r.get("conversations")
        if isinstance(conv, str): conv = ast.literal_eval(conv)
        cg = r.get("conversation_goal")
        if isinstance(cg, str): cg = ast.literal_eval(cg)
        sid = str(r["session_id"]); u, p = {}, {}
        for m in conv:
            tn = int(m["turn_number"])
            if m["role"] == "user": u[tn] = str(m["content"])
            elif m["role"] == "music": p.setdefault(tn, []).append(str(m["content"]))
        um[sid] = u; played[sid] = p; goal[sid] = (cg or {}).get("listener_goal", "")
    return um, played, goal


def load_catalog():
    """track_id -> dict(artist,title,album,tags,text). Matches catalog.track_text format."""
    import lancedb
    t = lancedb.connect("cache/lancedb").open_table("music_track_catalog")
    rows = t.search().select(
        ["track_id", "artist_name", "track_name", "album_name", "tag_list"]
    ).limit(60000).to_list()
    meta = {}
    def first(x):
        if isinstance(x, (list, tuple)): return str(x[0]) if x else ""
        return str(x) if x is not None else ""
    for r in rows:
        tid = str(r["track_id"])
        artist = first(r.get("artist_name")); title = first(r.get("track_name"))
        album = first(r.get("album_name"))
        tags = r.get("tag_list") or []
        tags = [str(x) for x in (tags if isinstance(tags, (list, tuple)) else [])][:5]
        text = f"{artist} - {title} | {album} | {', '.join(tags)}".strip()
        meta[tid] = {"artist": artist, "title": title, "album": album, "tags": tags, "text": text}
    return meta


def load_trace_for(keys, gt):
    """Stream trace; for selected keys return per-turn: final 1000 ids, before_rank, turn_intent."""
    keys = set(keys); out = {}
    for line in open(TRACE):
        d = json.loads(line); key = (d["session_id"], int(d["turn_number"]))
        if key not in keys: continue
        g = gt.get(key)
        if not g: continue
        tr = d.get("trace") or {}; rk = tr.get("ranking") or {}; stages = rk.get("stages") or []
        sd = {s.get("name"): s for s in stages}
        final = sd.get("lgbm_v10") or (stages[-1] if stages else None)
        if not final: continue
        ids = final.get("track_ids") or []
        try: before = ids.index(g) + 1
        except ValueError: continue  # GT not in final list -> skip (can't define before-rank)
        ti = ((tr.get("extracted_state") or {}).get("turn_intent") or "").strip()
        out[key] = {"final_ids": ids, "before": before, "turn_intent": ti}
    return out


# --------------------------------------------------------------------------- query builders
def build_query(arm, key, rec, um, played, meta, n_turns):
    sid, tn = key
    if arm == "A":
        return rec["turn_intent"] or (um.get(sid, {}).get(tn, ""))
    # B / C : chronological context, prev recommended tracks (turns < tn only), current request last
    lines = []
    start = max(1, tn - n_turns)
    for k in range(start, tn):  # strictly-prior turns
        if um.get(sid, {}).get(k):
            lines.append(f"user (previous): {um[sid][k]}")
        for ptid in played.get(sid, {}).get(k, []):  # tracks played at prior turns
            m = meta.get(ptid)
            if m: lines.append(f"recommended: {m['artist']} - {m['title']}")
    cur = um.get(sid, {}).get(tn, "")
    lines.append(f"user (current request): {cur}")
    return "\n".join(lines)


def artist_in_convo(key, gt_tid, um, played, meta):
    sid, tn = key
    art = (meta.get(gt_tid, {}).get("artist") or "").lower().strip()
    if not art: return False
    hay = " ".join(um.get(sid, {}).get(k, "") for k in range(1, tn + 1)).lower()
    if art and art in hay: return True
    for k in range(1, tn):  # prior played artists
        for ptid in played.get(sid, {}).get(k, []):
            if (meta.get(ptid, {}).get("artist") or "").lower().strip() == art:
                return True
    return False


# --------------------------------------------------------------------------- baselines
def bm25_order(query, docs):
    def tok(s): return re.findall(r"[a-z0-9]+", s.lower())
    qd = set(tok(query)); dts = [tok(d) for d in docs]
    N = len(docs); avgdl = (sum(len(d) for d in dts) / N) if N else 1.0
    df = Counter()
    for d in dts:
        for w in set(d): df[w] += 1
    k1, b = 1.5, 0.75; scores = []
    for d in dts:
        tf = Counter(d); s = 0.0
        for w in qd:
            if w not in tf: continue
            idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(d) / avgdl))
        scores.append(s)
    return sorted(range(N), key=lambda i: -scores[i])


# --------------------------------------------------------------------------- model
class Qwen3Reranker:
    def __init__(self, model_name, device, batch_size, dtype="float16", instruct=INSTRUCT):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch; self.bs = batch_size; self.instruct = instruct
        self.tok = AutoTokenizer.from_pretrained(model_name, padding_side="left")
        td = getattr(torch, dtype) if device == "cuda" else torch.float32
        try:
            self.model = AutoModelForCausalLM.from_pretrained(model_name, dtype=td)
        except TypeError:
            self.model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=td)
        self.model = self.model.to(device).eval()
        self.device = device
        self.yes = self.tok.convert_tokens_to_ids("yes")
        self.no = self.tok.convert_tokens_to_ids("no")
        pre = ('<|im_start|>system\nJudge whether the Document meets the requirements based on '
               'the Query and the Instruct provided. Note that the answer can only be "yes" or '
               '"no".<|im_end|>\n<|im_start|>user\n')
        suf = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        self.pre = self.tok.encode(pre, add_special_tokens=False)
        self.suf = self.tok.encode(suf, add_special_tokens=False)

    def _fmt(self, q, d):
        return f"<Instruct>: {self.instruct}\n<Query>: {q}\n<Document>: {d}"

    def score(self, pairs):
        torch = self.torch; out = []
        for i in range(0, len(pairs), self.bs):
            batch = pairs[i:i + self.bs]
            texts = [self._fmt(q, d) for q, d in batch]
            enc = self.tok(texts, truncation=True, max_length=1024, add_special_tokens=False)
            ids_list = [self.pre + ids + self.suf for ids in enc["input_ids"]]
            mx = max(len(x) for x in ids_list)
            pad = self.tok.pad_token_id or self.tok.eos_token_id
            padded = [[pad] * (mx - len(x)) + x for x in ids_list]
            attn = [[0] * (mx - len(x)) + [1] * len(x) for x in ids_list]
            ii = torch.tensor(padded, device=self.device)
            am = torch.tensor(attn, device=self.device)
            with torch.no_grad():
                lg = self.model(ii, attention_mask=am).logits[:, -1]
            yn = torch.softmax(torch.stack([lg[:, self.no], lg[:, self.yes]], -1), -1)[:, 1]
            out.extend(yn.float().cpu().tolist())
        return out


# --------------------------------------------------------------------------- metrics
def ndcg20(rank):
    return 1.0 / math.log2(rank + 1) if rank and rank <= 20 else 0.0


def after_rank(order_ids, tail_ids, gt):
    if gt in order_ids:
        return order_ids.index(gt) + 1
    if gt in tail_ids:
        return len(order_ids) + tail_ids.index(gt) + 1
    return None


MODES = ("replace", "rrf", "filter0.05", "filter0.2", "promote0.8", "promote0.9")


def orderings(cand, tail, sc, gt, fusion_k=60, taus=(0.05, 0.2), ptaus=(0.8, 0.9)):
    """Ways to USE the same xenc scores (free reordering of one scoring pass):
       replace = sort head by xenc; rrf = RRF-fuse xenc rank with LightGBM rank;
       filter  = keep LightGBM order but demote candidates scoring < tau;
       promote = PROMOTE-ONLY: pull candidates scoring >= ptau to the front (by score), keep
                 everything else in LightGBM order. Never demotes a non-promoted item below its
                 lgbm peers -> protects already-correct (control) turns by construction."""
    n = len(cand); out = {}
    od = sorted(range(n), key=lambda i: -sc[i])
    out["replace"] = after_rank([cand[i] for i in od], tail, gt)
    xrank = {i: r for r, i in enumerate(od)}                       # xenc rank of each lgbm position
    rrf = sorted(range(n), key=lambda i: -(1.0 / (fusion_k + i) + 1.0 / (fusion_k + xrank[i])))
    out["rrf"] = after_rank([cand[i] for i in rrf], tail, gt)
    for tau in taus:
        keep = [cand[i] for i in range(n) if sc[i] >= tau]         # lgbm order preserved
        drop = [cand[i] for i in range(n) if sc[i] < tau]
        out[f"filter{tau}"] = after_rank(keep + drop, tail, gt)
    for ptau in ptaus:
        promoted = sorted([i for i in range(n) if sc[i] >= ptau], key=lambda i: -sc[i])
        rest = [i for i in range(n) if sc[i] < ptau]               # lgbm order preserved
        out[f"promote{ptau}"] = after_rank([cand[i] for i in promoted + rest], tail, gt)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=200)
    ap.add_argument("--arms", default="A,B")
    ap.add_argument("--model", default=BASE_MODEL)
    ap.add_argument("--n-turns", type=int, default=1, help="prior turns of context for arm B (C uses 2)")
    ap.add_argument("--limit", type=int, default=0, help="subsample misses (smoke)")
    ap.add_argument("--controls", type=int, default=0, help="also score N control turns (hit=1)")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--max-pairs", type=int, default=0, help="hard cap on cross-encoder pairs (budget)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    random.seed(0)

    miss, ctrl, lane_of = load_lanes()
    gt = load_gt()
    if a.limit:
        # stratified-ish subsample: keep lane proportions
        random.shuffle(miss); miss = miss[: a.limit]
    if a.controls:
        random.shuffle(ctrl); ctrl = ctrl[: a.controls]
    else:
        ctrl = []
    print(f"misses={len(miss)} controls={len(ctrl)} arms={arms} k={a.k}", flush=True)

    print("loading catalog + test split + trace ...", flush=True)
    meta = load_catalog()
    um, played, goal = load_test()
    recs = load_trace_for(miss + ctrl, gt)
    miss = [k for k in miss if k in recs]; ctrl = [k for k in ctrl if k in recs]
    print(f"with trace before-rank: misses={len(miss)} controls={len(ctrl)}", flush=True)

    model = None  # lazy
    pairs_used = 0
    # results[group][arm] = list of per-turn dicts
    results = {"miss": defaultdict(list), "ctrl": defaultdict(list)}
    raw_rows = []  # per-turn full candidate scores -> offline threshold sweeps without re-scoring

    def process(group, keys):
        nonlocal model, pairs_used
        t0 = time.time()
        for n, key in enumerate(keys):
            rec = recs[key]; g = gt[key]
            cand = rec["final_ids"][: a.k]; tail = rec["final_ids"][a.k:]
            docs = [meta.get(c, {}).get("text", "") for c in cand]
            novel = not artist_in_convo(key, g, um, played, meta)
            base = {"key": list(key), "lane": lane_of.get(key), "before": rec["before"],
                    "reachable": rec["before"] <= a.k, "novel_artist": novel}
            # --- baselines (free) ---
            for bname, order in (("bm25", None), ("random", None)):
                if bname == "bm25":
                    q = rec["turn_intent"] or um.get(key[0], {}).get(key[1], "")
                    od = bm25_order(q, docs)
                else:
                    od = list(range(len(cand))); random.Random(hash(key) & 0xffffffff).shuffle(od)
                oids = [cand[i] for i in od]
                ar = after_rank(oids, tail, g)
                results["miss" if group == "miss" else "ctrl"][bname].append(
                    {**base, "after": ar, "dndcg": ndcg20(ar) - ndcg20(rec["before"])})
            # --- cross-encoder arms ---
            for arm in arms:
                if a.max_pairs and pairs_used + len(cand) > a.max_pairs:
                    continue
                if model is None:
                    print(f"loading model {a.model} on {dev} ...", flush=True)
                    model = Qwen3Reranker(a.model, dev, a.batch_size)
                q = build_query(arm, key, rec, um, played, meta, a.n_turns if arm != "C" else 2)
                sc = model.score([(q, d) for d in docs]); pairs_used += len(cand)
                gt_sc = sc[cand.index(g)] if g in cand else None
                raw_rows.append({"group": group, "key": list(key), "lane": lane_of.get(key),
                                 "before": rec["before"], "reachable": rec["before"] <= a.k,
                                 "novel": base["novel_artist"],
                                 "gt_idx": cand.index(g) if g in cand else -1,
                                 "sc": [round(float(x), 5) for x in sc]})
                for mode, ar in orderings(cand, tail, sc, g).items():
                    results[group][f"{arm}:{mode}"].append(
                        {**base, "after": ar, "gt_score": gt_sc,
                         "dndcg": ndcg20(ar) - ndcg20(rec["before"])})
            if (n + 1) % 50 == 0:
                rate = (n + 1) / max(1e-9, time.time() - t0)
                print(f"  [{group}] {n+1}/{len(keys)} ({rate:.1f} turns/s, pairs={pairs_used})", flush=True)

    process("miss", miss)
    if ctrl: process("ctrl", ctrl)

    # --------------------------------------------------------------- summarize
    def agg(rows):
        if not rows: return None
        n = len(rows); rec_rate = 100 * sum(r["after"] and r["after"] <= 20 for r in rows) / n
        return {"n": n, "mean_dndcg": sum(r["dndcg"] for r in rows) / n, "recovery_pct": rec_rate}

    summary = {}
    print("\n================= SUMMARY (mean ΔnDCG@20 / recovery%@20) =================")
    for group in ("miss", "ctrl"):
        if not results[group]: continue
        print(f"\n### {group} ###")
        summary[group] = {}
        methods = ["bm25", "random"] + [f"{arm}:{m}" for arm in arms for m in MODES]
        for m_ in methods:
            rows = results[group][m_]
            if not rows: continue
            allr = agg(rows)
            novel = agg([r for r in rows if r["novel_artist"]])
            reach = agg([r for r in rows if r["reachable"]])
            summary[group][m_] = {"all": allr, "novel_artist": novel, "reachable": reach,
                                  "by_lane": {ln: agg([r for r in rows if r["lane"] == ln])
                                              for ln in sorted(set(r["lane"] for r in rows))}}
            print(f"  {m_:<14} all: dNDCG={allr['mean_dndcg']:+.4f} rec={allr['recovery_pct']:.1f}% (n={allr['n']})"
                  + (f" | novel-artist dNDCG={novel['mean_dndcg']:+.4f} rec={novel['recovery_pct']:.1f}%" if novel else ""))
            for ln, v in summary[group][m_]["by_lane"].items():
                if v: print(f"        lane={ln:<13} dNDCG={v['mean_dndcg']:.4f} rec={v['recovery_pct']:.1f}% (n={v['n']})")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({"config": vars(a), "summary": summary,
               "raw": {g: {m_: results[g][m_] for m_ in results[g]} for g in results}},
              open(a.out, "w"), indent=1, default=str)
    raw_path = a.out.replace(".json", "_rawscores.jsonl")
    with open(raw_path, "w") as f:
        for r in raw_rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nsaved -> {a.out}  (cross-encoder pairs scored: {pairs_used})")
    print(f"raw scores ({len(raw_rows)} turns) -> {raw_path} (for offline threshold sweeps)")


if __name__ == "__main__":
    main()
