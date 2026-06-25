"""Exp A (corrected): add `scout_cos` (fine-tuned b1 query·doc cosine) AND `scout_base_cos`
(zero-shot base cosine, the control) to a reranker features parquet — so a held-out LightGBM A/B
shows whether the scout helps the DEPLOYED 148-feature judge, and whether any lift is from
fine-tuning (scout_cos) vs a lexical cosine the judge may already have (scout_base_cos).

Use the deployed 148-feature parquet (exp/analysis/rerank/v10/features = devset, --split test),
NOT the 78-feature pool-free deep30k set.

    python scripts/rerank/add_scout_feature.py --features exp/analysis/rerank/v10/features \
        --ckpt models/biencoder_qwen06_b1 --split test \
        --out exp/analysis/rerank/v10/features_scoutb1
"""
from __future__ import annotations
import argparse, ast, json, os, sys
import numpy as np, torch
import pyarrow as pa, pyarrow.parquet as pq, pyarrow.dataset as pds
sys.path.insert(0, "scripts/rerank")
from datasets import load_dataset
from mcrs.embeddings.qwen3_embedding import Qwen3EmbeddingClient, DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS
from build_retriever_pairs import build_q

INSTRUCT = DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS
BASE = "Qwen/Qwen3-Embedding-0.6B"
DOCS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
CACHE = "exp/analysis/retrieval_exploration/_emb_cache"


def load_split(split):
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split=split)
    um, goal = {}, {}
    for r in ds:
        conv = r.get("conversations")
        if isinstance(conv, str): conv = ast.literal_eval(conv)
        cg = r.get("conversation_goal")
        if isinstance(cg, str): cg = ast.literal_eval(cg)
        sid = str(r["session_id"]); u = {}
        for m in conv:
            if m["role"] == "user": u[int(m["turn_number"])] = str(m["content"])
        um[sid] = u; goal[sid] = (cg or {}).get("listener_goal", "")
    return um, goal


def docemb(model_name, texts, tag, dev, max_len=96):
    cp = f"{CACHE}/{tag}_l{max_len}.npy"   # encode max_len: docs >96 tok (5.2%) differ by truncation
    if os.path.exists(cp):  # reuse precomputed (e.g. Modal-embedded b1@256 docs placed here)
        V = np.load(cp)
    else:
        cl = Qwen3EmbeddingClient(model_name=model_name, device=dev, batch_size=128, query_instruct="",
                                  max_length=max_len, torch_dtype_name="float32")
        V = np.asarray(cl.embed_batch(texts), dtype=np.float32); np.save(cp, V)
    return (V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)).astype(np.float32)


def qemb(model_name, texts, dev, max_len=96):
    cl = Qwen3EmbeddingClient(model_name=model_name, device=dev, batch_size=128, query_instruct=INSTRUCT,
                              max_length=max_len, torch_dtype_name="float32")
    V = np.asarray(cl.embed_batch(texts), dtype=np.float32)
    return (V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--max-len", type=int, default=96)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tag = os.path.basename(a.ckpt.rstrip("/"))

    tids, doc_texts = [], []
    for line in open(DOCS):
        d = json.loads(line); tids.append(d["track_id"]); doc_texts.append(d["doc"])
    tidx = {t: i for i, t in enumerate(tids)}
    DOCs = docemb(a.ckpt, doc_texts, f"docs_ft_{tag}", dev, a.max_len)   # scout (b1) doc embs
    DOCb = docemb(BASE, doc_texts, "docs_base", dev, a.max_len)          # base doc embs (control)
    print(f"doc embs scout{DOCs.shape} base{DOCb.shape}", flush=True)

    ds = pds.dataset(a.features)
    kt = ds.to_table(columns=["session_id", "turn_number"])
    keys = sorted(set(zip(kt.column("session_id").to_pylist(), [int(x) for x in kt.column("turn_number").to_pylist()])))
    print(f"turns: {len(keys)} (split={a.split}) — embedding scout + base queries...", flush=True)
    um, goal = load_split(a.split)
    qtexts = [build_q(um.get(sid, {}), goal.get(sid, ""), tn) for sid, tn in keys]
    Qs = torch.tensor(qemb(a.ckpt, qtexts, dev, a.max_len), device=dev)
    Qb = torch.tensor(qemb(BASE, qtexts, dev, a.max_len), device=dev)
    qmap = {k: i for i, k in enumerate(keys)}
    DSt = torch.tensor(DOCs, device=dev); DBt = torch.tensor(DOCb, device=dev)

    os.makedirs(a.out, exist_ok=True)
    files = sorted([f for f in os.listdir(a.features) if f.endswith(".parquet")])
    NAN = float("nan"); tot = 0; nan = 0
    for fn in files:
        t = pq.read_table(os.path.join(a.features, fn))
        sids = t.column("session_id").to_pylist(); tns = [int(x) for x in t.column("turn_number").to_pylist()]
        trk = t.column("track_id").to_pylist()
        qi = np.array([qmap.get((s, n), -1) for s, n in zip(sids, tns)], dtype=np.int64)
        di = np.array([tidx.get(str(x), -1) for x in trk], dtype=np.int64)
        cs = np.full(len(qi), NAN, np.float32); cb = np.full(len(qi), NAN, np.float32)
        ok = (qi >= 0) & (di >= 0); idx = np.flatnonzero(ok)
        for s in range(0, len(idx), 500000):
            c = idx[s:s + 500000]
            qsi = torch.tensor(qi[c], device=dev); dii = torch.tensor(di[c], device=dev)
            cs[c] = (Qs[qsi] * DSt[dii]).sum(1).cpu().numpy()
            cb[c] = (Qb[qsi] * DBt[dii]).sum(1).cpu().numpy()
        tot += len(cs); nan += int((~ok).sum())
        t = t.append_column("scout_cos", pa.array(cs, pa.float32()))
        t = t.append_column("scout_base_cos", pa.array(cb, pa.float32()))
        pq.write_table(t, os.path.join(a.out, fn))
        print(f"  {fn}: {t.num_rows} rows, NaN {100*float((~ok).mean()):.1f}%", flush=True)
    print(f"DONE -> {a.out} ({tot} rows, {100*nan/max(1,tot):.1f}% NaN). Now: eval_scout_feature.py", flush=True)


if __name__ == "__main__":
    main()
