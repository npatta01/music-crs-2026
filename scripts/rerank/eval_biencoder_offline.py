"""M0d — offline confirmation eval for the bi-encoder (in-memory exact matmul, no DB / no ANN).

Question: does the fine-tuned conversation->track encoder rank the GT higher than (i) the SAME
base model zero-shot and (ii) the deployed history-centroid? Full-catalog ranking (47k), so
ranks are inherently padded (the GT is always somewhere in the catalog).

Embeds the doc corpus with the fine-tuned ckpt AND the base model (same doc text + query text,
only the weights differ -> isolates the fine-tuning effect). History-centroid baseline uses the
precomputed `metadata_qwen3_embedding_0_6b` catalog column (the deployed-style signal).

Pooling parity HARD check: serving Qwen3EmbeddingClient (fp32) vs the trainer's bf16-autocast
path on 20 docs, cosine >= 0.999.

Reports recall@{20,100,1000} for ft / zero-shot-base / history-centroid on: all-MOVES turns,
the lost-GT subset (deployed missed @20), and per lane.

Run from main checkout. Example:
    python scripts/rerank/eval_biencoder_offline.py --ckpt models/biencoder_qwen06_v1
"""
from __future__ import annotations
import argparse, ast, json, os, sys
import numpy as np, torch, lancedb
sys.path.insert(0, "scripts/rerank")
from datasets import load_dataset
from mcrs.embeddings.qwen3_embedding import (
    Qwen3EmbeddingClient, _last_token_pool, DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS,
)
from build_retriever_pairs import build_q

BASE = "Qwen/Qwen3-Embedding-0.6B"
INSTRUCT = DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS
DOCS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
LANES = "exp/analysis/rerank/devset_lanes_v10.jsonl"
GT_FILE = "exp/ground_truth/devset.json"
CACHE = "exp/analysis/retrieval_exploration/_emb_cache"
MOVES = "MOVES_TOWARD_GOAL"


def load_test():
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    um, goal, gpa, played = {}, {}, {}, {}
    for r in ds:
        conv = r.get("conversations")
        if isinstance(conv, str): conv = ast.literal_eval(conv)
        cg = r.get("conversation_goal")
        if isinstance(cg, str): cg = ast.literal_eval(cg)
        sid = str(r["session_id"]); u = {}; p = {}
        for m in conv:
            tn = int(m["turn_number"])
            if m["role"] == "user": u[tn] = str(m["content"])
            elif m["role"] == "music": p.setdefault(tn, []).append(str(m["content"]))
        um[sid] = u; goal[sid] = (cg or {}).get("listener_goal", ""); played[sid] = p
        g = r.get("goal_progress_assessments")
        if isinstance(g, str): g = ast.literal_eval(g)
        for a in (g or []): gpa[(sid, int(a["turn_number"]))] = a.get("goal_progress_assessment")
    return um, goal, gpa, played


def embed(model_name, texts, instruct, tag, bs, dev):
    os.makedirs(CACHE, exist_ok=True)
    cp = f"{CACHE}/{tag}.npy"
    if os.path.exists(cp):
        return np.load(cp)
    cl = Qwen3EmbeddingClient(model_name=model_name, device=dev, batch_size=bs,
                              query_instruct=instruct, max_length=96, torch_dtype_name="float32")
    V = np.asarray(cl.embed_batch(texts), dtype=np.float32)
    np.save(cp, V)
    return V


def ranks_full(Q, D, gt_idx, dev, chunk=512):
    """Full-catalog 1-based rank of each query's GT track (Q,D normalized)."""
    Dt = torch.tensor(D, device=dev)
    out = np.empty(len(Q), dtype=np.int64)
    for i in range(0, len(Q), chunk):
        q = torch.tensor(Q[i:i + chunk], device=dev)
        s = q @ Dt.t()                                   # (c x N)
        gi = torch.tensor(gt_idx[i:i + chunk], device=dev)
        gt_score = s[torch.arange(len(gi), device=dev), gi].unsqueeze(1)
        out[i:i + chunk] = (s > gt_score).sum(1).cpu().numpy() + 1
    return out


def recall(ranks, k):
    return 100.0 * np.mean(ranks <= k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--bs", type=int, default=128)
    ap.add_argument("--max-eval", type=int, default=0)
    ap.add_argument("--no-kf", action="store_true", help="embed docs WITHOUT the known-for line")
    ap.add_argument("--no-goal", action="store_true", help="strip listener_goal from the query (oracle-goal ablation)")
    ap.add_argument("--within-artist", action="store_true", help="probe GT rank among its OWN artist's tracks (collapse impact)")
    ap.add_argument("--recent-context", type=int, default=0, help="prepend last-N recently-played artists (must match training)")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    rc = f"_rc{a.recent_context}" if a.recent_context else ""
    # doc cache depends on ckpt + kf; query cache also on goal + recent-context. base caches keyed independently.
    doc_tag = os.path.basename(a.ckpt.rstrip("/")) + ("_nokf" if a.no_kf else "")
    q_tag = doc_tag + ("_nogoal" if a.no_goal else "") + rc
    base_doc_tag = "_nokf" if a.no_kf else ""
    base_q_tag = ("_nogoal" if a.no_goal else "") + rc
    docs_path = DOCS if os.path.exists(DOCS) else DOCS.replace("doc_corpus.jsonl", "doc_corpus_base.jsonl")

    # corpus
    tids, doc_texts, artists = [], [], []
    for line in open(docs_path):
        d = json.loads(line); tids.append(d["track_id"]); artists.append(d.get("artist", ""))
        doc_texts.append(d.get("doc_nokf", d["doc"]) if a.no_kf else d["doc"])
    tidx = {t: i for i, t in enumerate(tids)}
    print(f"corpus: {len(tids)} docs from {docs_path}", flush=True)

    # pooling parity check (serving fp32 vs trainer bf16-autocast) on 20 docs
    parity_check(a.ckpt, doc_texts[:20], dev)

    # doc embeddings: fine-tuned + zero-shot base (doc side raw, instruct="")
    print("embedding docs (fine-tuned)...", flush=True)
    Dft = embed(a.ckpt, doc_texts, "", f"docs_ft_{doc_tag}", a.bs, dev)
    print("embedding docs (zero-shot base)...", flush=True)
    Dzs = embed(BASE, doc_texts, "", f"docs_base{base_doc_tag}", a.bs, dev)
    # history-centroid baseline rep: precomputed metadata_0_6b, aligned to tids
    CM = load_catmeta(tids)

    # eval turns (MOVES, GT in corpus)
    lanes = {}
    for line in open(LANES):
        r = json.loads(line); lanes[(r["session_id"], int(r["turn_number"]))] = r
    gt = {}
    for r in json.load(open(GT_FILE)):
        gt[(r["session_id"], int(r["turn_number"]))] = str(r["ground_truth_track_id"])
    print("loading test split...", flush=True)
    um, goal, gpa, played = load_test()

    ev = []  # (sid,tn,gt,lane,deployed_missed)
    for (sid, tn), g in gt.items():
        if gpa.get((sid, tn)) != MOVES or g not in tidx or not um.get(sid):
            continue
        ln = lanes.get((sid, tn), {})
        missed = not bool(ln.get("hit", 0))
        ev.append((sid, tn, g, ln.get("lane", "?"), missed))
    if a.max_eval:
        ev = ev[: a.max_eval]
    print(f"eval MOVES turns: {len(ev)} ({sum(e[4] for e in ev)} deployed-missed)", flush=True)

    def recent_arts(sid, tn):
        if not a.recent_context:
            return ""
        seen = []
        for k in range(1, tn):
            for x in played.get(sid, {}).get(k, []):
                ai = tidx.get(x); ar = artists[ai] if ai is not None else ""
                if ar and ar not in seen:
                    seen.append(ar)
        return "; ".join(seen[-a.recent_context:])
    q_texts = [build_q(um[sid], "" if a.no_goal else goal[sid], tn, recent_arts(sid, tn))
               for sid, tn, g, ln, m in ev]
    gt_idx = np.array([tidx[g] for sid, tn, g, ln, m in ev])
    print(f"embedding queries (fine-tuned + base){' [GOAL STRIPPED]' if a.no_goal else ''}...", flush=True)
    Qft = embed(a.ckpt, q_texts, INSTRUCT, f"q_ft_{q_tag}", a.bs, dev)
    Qzs = embed(BASE, q_texts, INSTRUCT, f"q_base{base_q_tag}", a.bs, dev)
    # history centroids (mean of played metadata embeddings up to the turn), normalized
    Hc = np.zeros((len(ev), CM.shape[1]), dtype=np.float32)
    for i, (sid, tn, g, ln, m) in enumerate(ev):
        idxs = [tidx[x] for k in range(1, tn) for x in played.get(sid, {}).get(k, []) if x in tidx]
        if idxs:
            v = CM[idxs].mean(0); Hc[i] = v / max(np.linalg.norm(v), 1e-9)

    r_ft = ranks_full(Qft, Dft, gt_idx, dev)
    r_zs = ranks_full(Qzs, Dzs, gt_idx, dev)
    r_e4 = ranks_full(Hc, CM, gt_idx, dev)

    lane_of = np.array([e[3] for e in ev]); missed = np.array([e[4] for e in ev])
    def report(name, mask):
        n = int(mask.sum())
        if not n: return
        print(f"\n[{name}] n={n}")
        print(f"  {'method':<18} r@20   r@100  r@1000  medrank")
        for label, r in [("fine-tuned", r_ft), ("zero-shot base", r_zs), ("history-centroid", r_e4)]:
            rr = r[mask]
            print(f"  {label:<18} {recall(rr,20):5.1f}  {recall(rr,100):5.1f}  {recall(rr,1000):6.1f}  {int(np.median(rr))}")
    report("ALL MOVES", np.ones(len(ev), bool))
    report("LOST-GT (deployed missed@20)", missed)
    for ln in sorted(set(lane_of)):
        report(f"lane={ln}", lane_of == ln)

    if a.within_artist:
        # GT rank among ONLY its own artist's tracks (collapse impact on track selection)
        from collections import defaultdict
        by_artist = defaultdict(list)
        for i, ar in enumerate(artists):
            if ar:
                by_artist[ar].append(i)
        Dt = torch.tensor(Dft, device=dev)
        r1 = nn = 0; wranks = []
        for i, (sid, tn, g, ln, m) in enumerate(ev):
            sib = by_artist.get(artists[gt_idx[i]], [])
            if len(sib) < 2:
                continue
            nn += 1
            q = torch.tensor(Qft[i:i + 1], device=dev)
            s = (q @ Dt[sib].t()).cpu().numpy()[0]
            gpos = sib.index(int(gt_idx[i]))
            rank = int((s > s[gpos]).sum()) + 1
            wranks.append(rank); r1 += rank == 1
        print(f"\n[WITHIN-ARTIST PRECISION] n={nn} (GT artists with >=2 tracks); "
              f"doc={'nokf' if a.no_kf else 'kf'}{' nogoal' if a.no_goal else ''}")
        print(f"  GT is rank-1 among its artist's tracks: {100*r1/max(1,nn):.1f}%  "
              f"median within-artist rank={int(np.median(wranks))}  "
              f"(mean #tracks/artist={np.mean([len(by_artist[artists[gt_idx[i]]]) for i in range(len(ev)) if len(by_artist.get(artists[gt_idx[i]],[]))>=2]):.1f})")


def load_catmeta(tids):
    t = lancedb.connect("cache/lancedb").open_table("music_track_catalog")
    vecs = {}
    for r in t.search().select(["track_id", "metadata_qwen3_embedding_0_6b"]).limit(60000).to_list():
        v = r.get("metadata_qwen3_embedding_0_6b")
        if v is not None and len(v): vecs[str(r["track_id"])] = np.asarray(v, dtype=np.float32)
    CM = np.zeros((len(tids), 1024), dtype=np.float32)
    miss = 0
    for i, t_ in enumerate(tids):
        v = vecs.get(t_)
        if v is None: miss += 1; continue
        CM[i] = v / max(np.linalg.norm(v), 1e-9)
    print(f"catmeta aligned: {len(tids)-miss}/{len(tids)} (missing {miss})", flush=True)
    return CM


def parity_check(ckpt, texts, dev):
    from transformers import AutoModel, AutoTokenizer
    cl = Qwen3EmbeddingClient(model_name=ckpt, device=dev, batch_size=8,
                              query_instruct="", max_length=96, torch_dtype_name="float32")
    A = np.asarray(cl.embed_batch(texts), dtype=np.float32)
    tok = AutoTokenizer.from_pretrained(ckpt, padding_side="left")
    mod = AutoModel.from_pretrained(ckpt, dtype=torch.float32).to(dev).eval()
    b = tok(texts, padding=True, truncation=True, max_length=96, return_tensors="pt")
    b = {k: v.to(dev) for k, v in b.items()}
    with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        out = mod(**b)
    pooled = _last_token_pool(out.last_hidden_state, b["attention_mask"], torch=torch)
    B = torch.nn.functional.normalize(pooled.float(), p=2, dim=1).cpu().numpy()
    cos = float(np.mean(np.sum(A * B, axis=1)))
    print(f"POOLING PARITY (serving fp32 vs trainer bf16): mean cos={cos:.4f} "
          f"-> {'OK' if cos >= 0.999 else 'FAIL (<0.999)'}", flush=True)


if __name__ == "__main__":
    main()
