"""Scout-as-reranker (PRIMARY, no reranker retrain).

For each devset turn, re-score the DEPLOYED candidate pool (the `candidate_fusion` 1000-pool) by
the scout's query·doc cosine, and compare the GT's rank to the deployed reranker (`lgbm_v10`).
Answers: does the scout rank the GT HIGHER than what we currently suggest? — split by lane.

Also re-scores the pool with the BASE (un-fine-tuned) model → the zero-shot-base delta (if base
also jumps, the gain is lexical, not learned). Reports on GT-in-pool turns (the re-rankable set);
the never-retrieved GTs are a separate full-catalog question (eval_biencoder_offline.py).

Reuses cached doc embeddings in _emb_cache/ when present. Run from main checkout:
    python scripts/rerank/eval_scout_as_reranker.py --ckpt models/biencoder_qwen06_b1
"""
from __future__ import annotations
import argparse, ast, json, math, os, sys
import numpy as np, torch
sys.path.insert(0, "scripts/rerank")
from datasets import load_dataset
from mcrs.embeddings.qwen3_embedding import Qwen3EmbeddingClient, DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS
from build_retriever_pairs import build_q

INSTRUCT = DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS
BASE = "Qwen/Qwen3-Embedding-0.6B"
DOCS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
LANES = "exp/analysis/rerank/devset_lanes_v10.jsonl"
GT_FILE = "exp/ground_truth/devset.json"
TRACE = "exp/inference/devset/state_ranker_v10_lgbm_devset_fastlocal_trace.jsonl"
CACHE = "exp/analysis/retrieval_exploration/_emb_cache"
MOVES = "MOVES_TOWARD_GOAL"
KS = [20, 50, 100]


def load_test():
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    um, goal, gpa = {}, {}, {}
    for r in ds:
        conv = r.get("conversations")
        if isinstance(conv, str): conv = ast.literal_eval(conv)
        cg = r.get("conversation_goal")
        if isinstance(cg, str): cg = ast.literal_eval(cg)
        sid = str(r["session_id"]); u = {}
        for m in conv:
            tn = int(m["turn_number"])
            if m["role"] == "user": u[tn] = str(m["content"])
        um[sid] = u; goal[sid] = (cg or {}).get("listener_goal", "")
        g = r.get("goal_progress_assessments")
        if isinstance(g, str): g = ast.literal_eval(g)
        for a in (g or []): gpa[(sid, int(a["turn_number"]))] = a.get("goal_progress_assessment")
    return um, goal, gpa


def docemb(model_name, texts, tag, bs, dev, max_len=96):
    cp = f"{CACHE}/{tag}_l{max_len}.npy"   # encode max_len (docs >96 tok differ by truncation)
    if os.path.exists(cp):
        V = np.load(cp)
    else:
        cl = Qwen3EmbeddingClient(model_name=model_name, device=dev, batch_size=bs,
                                  query_instruct="", max_length=max_len, torch_dtype_name="float32")
        V = np.asarray(cl.embed_batch(texts), dtype=np.float32); np.save(cp, V)
    return V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)


def qemb(model_name, texts, bs, dev, max_len=96):
    cl = Qwen3EmbeddingClient(model_name=model_name, device=dev, batch_size=bs,
                              query_instruct=INSTRUCT, max_length=max_len, torch_dtype_name="float32")
    V = np.asarray(cl.embed_batch(texts), dtype=np.float32)
    return V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)


def ids(s):
    return [str(x) for x in s["track_ids"]] if s.get("track_ids") else [str(x[0]) for x in (s.get("scores") or [])]


def ndcg(rank, k):
    return (1.0 / math.log2(rank + 1)) if rank <= k else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--bs", type=int, default=128)
    ap.add_argument("--max-eval", type=int, default=0)
    ap.add_argument("--max-len", type=int, default=96)
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tag = os.path.basename(a.ckpt.rstrip("/"))

    tids, doc_texts = [], []
    for line in open(DOCS):
        d = json.loads(line); tids.append(d["track_id"]); doc_texts.append(d["doc"])
    tidx = {t: i for i, t in enumerate(tids)}
    print(f"corpus {len(tids)} docs; embedding docs (scout + base)...", flush=True)
    Ds = torch.tensor(docemb(a.ckpt, doc_texts, f"docs_ft_{tag}", a.bs, dev, a.max_len), device=dev)
    Db = torch.tensor(docemb(BASE, doc_texts, "docs_base", a.bs, dev, a.max_len), device=dev)

    lanes = {}
    for line in open(LANES):
        r = json.loads(line); lanes[(r["session_id"], int(r["turn_number"]))] = r.get("lane", "?")
    gt = {}
    for r in json.load(open(GT_FILE)):
        gt[(r["session_id"], int(r["turn_number"]))] = str(r["ground_truth_track_id"])
    print("loading test split...", flush=True)
    um, goal, gpa = load_test()

    ev = []  # (sid,tn,gt,lane,pool_idx[list], dep_rank)
    for line in open(TRACE):
        row = json.loads(line); sid = row["session_id"]; tn = int(row["turn_number"]); g = gt.get((sid, tn))
        if not g or gpa.get((sid, tn)) != MOVES or g not in tidx or not um.get(sid):
            continue
        st = {s.get("name"): s for s in ((row.get("trace") or {}).get("ranking") or {}).get("stages") or [] if isinstance(s, dict)}
        if "candidate_fusion" not in st or "lgbm_v10" not in st:
            continue
        pool = [c for c in ids(st["candidate_fusion"]) if c in tidx]
        if g not in pool:
            ev.append((sid, tn, g, lanes.get((sid, tn), "?"), None, None)); continue  # GT not in pool (retrieval miss)
        dep = ids(st["lgbm_v10"]); dep_rank = (dep.index(g) + 1) if g in dep else 10**6
        ev.append((sid, tn, g, lanes.get((sid, tn), "?"), [tidx[c] for c in pool], (g, pool, dep_rank)))
    if a.max_eval:
        ev = ev[: a.max_eval]
    inpool = [e for e in ev if e[4] is not None]
    print(f"MOVES turns: {len(ev)} ; GT-in-pool (re-rankable): {len(inpool)} "
          f"({100*len(inpool)/max(1,len(ev)):.0f}%)", flush=True)

    q_texts = [build_q(um[sid], goal[sid], tn) for sid, tn, g, ln, pi, meta in ev]
    print("embedding queries (scout + base)...", flush=True)
    Qs = torch.tensor(qemb(a.ckpt, q_texts, a.bs, dev, a.max_len), device=dev)
    Qb = torch.tensor(qemb(BASE, q_texts, a.bs, dev, a.max_len), device=dev)

    # per-turn ranks for scout / base / deployed (GT-in-pool only)
    rows = []  # (lane, scout_rank, base_rank, dep_rank)
    for i, (sid, tn, g, ln, pi, meta) in enumerate(ev):
        if pi is None:
            continue
        _, pool, dep_rank = meta
        gpos = pool.index(g)
        di = torch.tensor(pi, device=dev)
        ss = (Ds[di] @ Qs[i]); sr = int((ss > ss[gpos]).sum().item()) + 1
        bs_ = (Db[di] @ Qb[i]); br = int((bs_ > bs_[gpos]).sum().item()) + 1
        rows.append((ln, sr, br, dep_rank))

    def agg(rs, name):
        n = len(rs)
        if not n: return
        out = f"  {name:<16}"
        for k in KS:
            hit = 100 * np.mean([r <= k for r in rs])
            nd = 100 * np.mean([ndcg(r, k) for r in rs])
            out += f"  H@{k}={hit:4.1f} nDCG@{k}={nd:4.1f}"
        print(out + f"  medrank={int(np.median(rs))}")

    def report(name, mask):
        sel = [r for r in rows if mask(r)]
        if not sel: return
        print(f"\n[{name}] n={len(sel)} (GT-in-pool)")
        agg([r[1] for r in sel], "scout")
        agg([r[2] for r in sel], "zero-shot base")
        agg([r[3] for r in sel], "deployed (judge)")

    report("ALL MOVES", lambda r: True)
    for ln in sorted({r[0] for r in rows}):
        report(f"lane={ln}", lambda r, ln=ln: r[0] == ln)

    # === RETRIEVAL RECOVERY: GTs NOT in the deployed pool — does the scout find them full-catalog? ===
    # This is the scout's REAL job (the missed set is where the 0.45->0.65 gap lives), evaluated as
    # retrieval (full-catalog rank), not reranking.
    notin = [(i, e) for i, e in enumerate(ev) if e[4] is None]
    print(f"\n=== RETRIEVAL RECOVERY (GT NOT in the deployed 1000-pool — n={len(notin)}) ===")
    RKS = [20, 100, 1000]

    def rec_report(name, mask):
        sel = [(i, e) for i, e in notin if mask(e)]
        if not sel:
            return
        sr, br = [], []
        for i, e in sel:
            gi = tidx[e[2]]
            s = Ds @ Qs[i]; sr.append(int((s > s[gi]).sum().item()) + 1)
            b = Db @ Qb[i]; br.append(int((b > b[gi]).sum().item()) + 1)
        print(f"[{name}] n={len(sel)}")
        for rs, nm in [(sr, "scout"), (br, "zero-shot base")]:
            print(f"  {nm:<16}" + "".join(f"  r@{k}={100*np.mean([r<=k for r in rs]):5.1f}" for k in RKS)
                  + f"  medrank={int(np.median(rs))}")

    rec_report("ALL not-in-pool", lambda e: True)
    for ln in sorted({e[3] for i, e in notin}):
        rec_report(f"lane={ln}", lambda e, ln=ln: e[3] == ln)


if __name__ == "__main__":
    main()
