"""3-tower history-gate scout (the highest-EV architecture per the advisor panel).

Shared Qwen3-Embedding-0.6B encoder for three roles:
  - REQUEST tower : encode the request text (plain delimiters: [goal] + last 1-2 user turns).
                    NO previously-played-track in the request — history is its own tower.
  - SONG tower    : encode the unified song doc.
  - HISTORY tower : encode each recently-played song's doc, recency-weighted-pool -> history vec.
Learned gate g = sigmoid(MLP(request)) -> a per-turn scalar that can turn history OFF on a pivot:
  query = normalize(request + g * history)   (g learns ~0 on pivots, ~1 on continuations)
  score = query . song   (MNRL: in-batch + mined hard negatives)

Pooling = the serving last-token pool (parity by construction). Plain-text request input (advisors:
new learned special tokens unlikely to beat plain delimiters on ~54k examples).

Run from the main checkout (paths relative). Smoke:
    python scripts/rerank/train_3tower.py --variant b --limit 4000 --epochs 1 --freeze-bottom 20 --out models/scout_3tower_smoke
"""
from __future__ import annotations
import argparse, ast, json, os, random, sys, time
sys.path.insert(0, "scripts/rerank")
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer
from datasets import load_dataset
from mcrs.embeddings.qwen3_embedding import _last_token_pool, DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS

BASE = "Qwen/Qwen3-Embedding-0.6B"
PAIRS = "exp/analysis/retrieval_exploration/retriever_pairs.jsonl"
DOCS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
MOVES = "MOVES_TOWARD_GOAL"
INSTRUCT = DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS


def load_docs(path):
    if not os.path.exists(path):
        path = path.replace("doc_corpus.jsonl", "doc_corpus_base.jsonl")
    kf = {}
    for line in open(path):
        d = json.loads(line); kf[d["track_id"]] = d["doc"]
    return kf


def load_doc_emb(docs_path, tags=("docs_base", "docs_ft_biencoder_qwen06_b1")):
    """Cached doc embeddings in doc_corpus order -> (normalized V, tid->row). Departure flag uses BASE
    first (zero-shot) to avoid leaking b1's fine-tuned geometry into which turns get flagged."""
    cache = "exp/analysis/retrieval_exploration/_emb_cache"
    tids = [json.loads(l)["track_id"] for l in open(docs_path)]
    for tag in tags:
        p = f"{cache}/{tag}.npy"
        if os.path.exists(p):
            V = np.load(p).astype(np.float32)
            V = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)
            print(f"hist-neg departure score uses {tag} ({V.shape})", flush=True)
            return V, {t: i for i, t in enumerate(tids)}
    raise FileNotFoundError("no cached doc embeddings for hist-neg departure score (run add_scout_feature first)")


def flag_history_departures(ex, k_hist, frac, docs_path):
    """Content-based (NOT label-based) trigger: flag turns where the actual next track DEPARTS from
    recent history (low cos) -> there history misleads, so its tracks are valid hard negatives. Robust
    to gpa noise: a MOVES-labeled real pivot still gets flagged; a DOES_NOT turn similar to history does not."""
    V, idx = load_doc_emb(docs_path)
    recw = np.array([0.6 ** (k_hist - 1 - i) for i in range(k_hist)], dtype=np.float32)
    coss = []
    for e in ex:
        h = e["hist"][-k_hist:]
        if not h or e["pos"] not in idx or any(t not in idx for t in h):
            e["hist_cos"] = None; continue
        w = recw[-len(h):]
        hv = (V[[idx[t] for t in h]] * w[:, None]).sum(0)
        hv = hv / (np.linalg.norm(hv) + 1e-9)
        e["hist_cos"] = float(V[idx[e["pos"]]] @ hv); coss.append(e["hist_cos"])
    thr = float(np.quantile(coss, frac)) if coss else 0.0
    ndep = nmoves = 0
    for e in ex:
        e["hist_dep"] = e["hist_cos"] is not None and e["hist_cos"] < thr
        if e["hist_dep"]:
            ndep += 1; nmoves += 0 if e["pivot"] else 1
    print(f"hist-neg: {ndep} turns flagged as departures (cos<{thr:.3f}, frac={frac}); "
          f"{nmoves}/{ndep} ({100*nmoves/max(1,ndep):.0f}%) were gpa=MOVES — label-only would MISS these", flush=True)
    return ex


def load_played(split):
    """per (sid): {turn: [played track_ids]} — for the history tower."""
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split=split)
    played = {}
    for r in ds:
        conv = r.get("conversations")
        if isinstance(conv, str): conv = ast.literal_eval(conv)
        sid = str(r["session_id"]); p = {}
        for m in conv:
            if m["role"] == "music":
                p.setdefault(int(m["turn_number"]), []).append(str(m["content"]))
        played[sid] = p
    return played


def build_examples(pairs_path, variant, neg_field, valid, played, k_hist):
    rows = [json.loads(l) for l in open(pairs_path)]
    rows = [r for r in rows if r["pos_id"] in valid]
    does_not = {}
    for r in rows:
        if r["gpa"] and r["gpa"] != MOVES:
            does_not.setdefault(r["sid"], []).append(r["pos_id"])
    ex = []
    for r in rows:
        if variant in ("b", "c") and r["gpa"] != MOVES:
            continue
        negs = [n for n in r[neg_field] if n in valid]
        if variant == "c":
            negs += [t for t in does_not.get(r["sid"], []) if t in valid and t != r["pos_id"]][:3]
        # history = tracks played strictly before this turn (most-recent last), capped to k
        hist = [x for tn in range(1, r["tn"]) for x in played.get(r["sid"], {}).get(tn, []) if x in valid][-k_hist:]
        ex.append({"q": r["q"], "pos": r["pos_id"], "negs": negs, "hist": hist,
                   "pivot": bool(r["gpa"]) and r["gpa"] != MOVES})
    return ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["a", "b", "c"], default="b")
    ap.add_argument("--negs", choices=["filt", "raw"], default="filt")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--bs", type=int, default=48)
    ap.add_argument("--n-hardneg", type=int, default=3)
    ap.add_argument("--k-hist", type=int, default=3, help="max recently-played songs in the history tower")
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=96)
    ap.add_argument("--scale", type=float, default=20.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pairs", default=PAIRS)
    ap.add_argument("--freeze-bottom", type=int, default=0)
    ap.add_argument("--hist-neg", action="store_true", help="content-gated history negatives on departure turns")
    ap.add_argument("--n-histneg", type=int, default=3)
    ap.add_argument("--hist-neg-frac", type=float, default=0.33, help="flag the lowest-cos (most-departing) fraction")
    ap.add_argument("--gate-aux", type=float, default=0.3, help="weight of the BCE aux loss on g (g->0 dep, g->1 cont)")
    ap.add_argument("--log-every", type=int, default=50)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    random.seed(0); torch.manual_seed(0)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    neg_field = "negs_filt" if a.negs == "filt" else "negs_raw"

    doc = load_docs(DOCS); valid = set(doc); all_tids = list(valid)
    print("loading played history...", flush=True)
    played = load_played("train")
    ex = build_examples(a.pairs, a.variant, neg_field, valid, played, a.k_hist)
    random.shuffle(ex)
    if a.limit:
        ex = ex[: a.limit]
    nh = sum(1 for e in ex if e["hist"])
    print(f"variant={a.variant} examples={len(ex)} with-history={nh} ({100*nh/max(1,len(ex)):.0f}%) "
          f"docs={len(valid)}", flush=True)
    if a.hist_neg:
        ex = flag_history_departures(ex, a.k_hist, a.hist_neg_frac, DOCS)

    tok = AutoTokenizer.from_pretrained(BASE, padding_side="left")
    model = AutoModel.from_pretrained(BASE, dtype=torch.float32, attn_implementation="sdpa").to(dev).train()
    if a.freeze_bottom > 0:
        if hasattr(model, "embed_tokens"):
            model.embed_tokens.requires_grad_(False)
        for i, layer in enumerate(model.layers):
            if i < a.freeze_bottom:
                layer.requires_grad_(False)
    d = model.config.hidden_size
    gate = torch.nn.Sequential(torch.nn.Linear(d, 256), torch.nn.ReLU(), torch.nn.Linear(256, 1)).to(dev)
    params = [p for p in model.parameters() if p.requires_grad] + list(gate.parameters())
    opt = torch.optim.AdamW(params, lr=a.lr)
    rec_w = torch.tensor([0.6 ** (a.k_hist - 1 - i) for i in range(a.k_hist)], device=dev)  # recency weights

    def encode(texts):
        b = tok(texts, padding=True, truncation=True, max_length=a.max_len, return_tensors="pt")
        b = {k: v.to(dev) for k, v in b.items()}
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            out = model(**b)
        return torch.nn.functional.normalize(
            _last_token_pool(out.last_hidden_state, b["attention_mask"], torch=torch).float(), p=2, dim=1)

    def hist_vec(batch):
        # encode each example's last-k history docs (pad to k), recency-weighted pool, masked
        flat, mask = [], []
        for e in batch:
            h = e["hist"][-a.k_hist:]
            m = [1.0] * len(h) + [0.0] * (a.k_hist - len(h))
            h = h + [all_tids[0]] * (a.k_hist - len(h))  # pad (masked out)
            flat += [doc[t] for t in h]; mask.append(m)
        H = encode(flat).view(len(batch), a.k_hist, -1)          # B x k x d
        w = (rec_w * torch.tensor(mask, device=dev)).unsqueeze(-1)  # B x k x 1
        hv = (H * w).sum(1)
        return torch.nn.functional.normalize(hv + 1e-8, p=2, dim=1), (w.sum(1) > 0).float()  # B x d, B x 1

    steps = 0; t0 = time.time()
    for epoch in range(a.epochs):
        random.shuffle(ex)
        for i in range(0, len(ex) - a.bs + 1, a.bs):
            batch = ex[i:i + a.bs]
            R = encode([INSTRUCT + e["q"] for e in batch])              # B x d (request)
            Hv, hmask = hist_vec(batch)                                  # B x d, B x 1
            g_raw = torch.sigmoid(gate(R))                               # B x 1 (pre-mask)
            g = g_raw * hmask                                            # B x 1 (0 if no history)
            Q = torch.nn.functional.normalize(R + g * Hv, p=2, dim=1)    # combined query
            pos = [doc[e["pos"]] for e in batch]; negs = []
            for e in batch:
                ns = e["negs"][: a.n_hardneg]
                while len(ns) < a.n_hardneg:
                    ns = ns + [random.choice(all_tids)]
                if a.hist_neg:
                    # content-gated: on a history-departure turn the recently-played tracks are the
                    # tempting-WRONG answers -> as negatives they force the gate to turn history off.
                    hn = list(e["hist"]) if e.get("hist_dep") else []
                    while len(hn) < a.n_histneg:
                        hn = hn + [random.choice(all_tids)]
                    ns = ns + hn[: a.n_histneg]
                negs += [doc[t] for t in ns]
            D = encode(pos + negs)                                       # (B + B*k) x d
            logits = (Q @ D.t()) * a.scale
            loss = torch.nn.functional.cross_entropy(logits, torch.arange(len(batch), device=dev))
            aux_val = 0.0
            if a.hist_neg and a.gate_aux > 0:
                # direct supervision so the GATE learns (not the encoder dodging): g->0 on departures,
                # g->1 on continuations — only over turns that actually have history (hmask=1).
                hm = hmask.squeeze(-1).bool()
                if hm.any():
                    tgt = torch.tensor([0.0 if e.get("hist_dep") else 1.0 for e in batch], device=dev)
                    aux = torch.nn.functional.binary_cross_entropy(g_raw.squeeze(-1)[hm], tgt[hm])
                    loss = loss + a.gate_aux * aux; aux_val = aux.item()
            opt.zero_grad(); loss.backward(); opt.step(); steps += 1
            if steps % a.log_every == 0:
                gh = g_raw.squeeze(-1)[hmask.squeeze(-1).bool()]
                dep = torch.tensor([bool(e.get("hist_dep")) for e in batch], device=dev)[hmask.squeeze(-1).bool()]
                gd = gh[dep].mean().item() if dep.any() else float("nan")
                gc = gh[~dep].mean().item() if (~dep).any() else float("nan")
                print(f"  ep{epoch} step{steps} loss={loss.item():.3f} aux={aux_val:.3f} "
                      f"g_dep={gd:.2f} g_cont={gc:.2f} sep={gc-gd:+.2f} "
                      f"({steps*a.bs/max(1e-9,time.time()-t0):.0f} ex/s)", flush=True)
    os.makedirs(a.out, exist_ok=True)
    model.save_pretrained(a.out); tok.save_pretrained(a.out)
    torch.save(gate.state_dict(), os.path.join(a.out, "gate.pt"))
    json.dump({"variant": a.variant, "k_hist": a.k_hist, "n_hardneg": a.n_hardneg, "epochs": a.epochs,
               "bs": a.bs, "instruct": INSTRUCT, "base": BASE, "examples": len(ex), "arch": "3tower-gate"},
              open(os.path.join(a.out, "train_meta.json"), "w"), indent=2)
    print(f"DONE saved {a.out} ({steps} steps, {time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
