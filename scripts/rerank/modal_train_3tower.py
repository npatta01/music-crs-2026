"""Modal training for the 3-tower history-gate scout (A100-80GB + SDPA, cu130 image).

Self-contained (mirrors train_3tower.py); reads /data/3tower_data.jsonl + /data/doc_corpus.jsonl
from the `biencoder-data` volume, saves the checkpoint (+ gate.pt) to the `scout-models` volume.

Setup + run:
    modal volume put --force biencoder-data exp/analysis/retrieval_exploration/3tower_data.jsonl /3tower_data.jsonl
    modal volume put --force biencoder-data exp/analysis/retrieval_exploration/doc_corpus.jsonl  /doc_corpus.jsonl
    modal run scripts/rerank/modal_train_3tower.py
Then fetch: modal volume get scout-models /scout_3tower_v1 ./models/
"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.9.1", index_url="https://download.pytorch.org/whl/cu130")
    .pip_install("transformers>=4.51.0", "numpy", "huggingface_hub", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}))
app = modal.App("scout-3tower", image=image)
data_vol = modal.Volume.from_name("biencoder-data", create_if_missing=True)
model_vol = modal.Volume.from_name("scout-models", create_if_missing=True)
hf_vol = modal.Volume.from_name("hf-cache", create_if_missing=True)
INSTRUCT = ("Instruct: Given a music recommendation conversation, retrieve relevant track "
            "metadata passages that match the listener request and prior music preferences.\nQuery: ")
BASE = "Qwen/Qwen3-Embedding-0.6B"
MOVES = "MOVES_TOWARD_GOAL"


@app.function(gpu="A100-80GB", volumes={"/data": data_vol, "/models": model_vol,
              "/root/.cache/huggingface": hf_vol}, timeout=7200)
def train(variant="b", negs="filt", epochs=2, bs=64, n_hardneg=3, k_hist=3, lr=2e-5,
          max_len=96, scale=20.0, freeze_bottom=0, limit=0, out_name="scout_3tower_v1",
          hist_neg=False, n_histneg=3, gate_aux=0.3, hist_neg_frac=0.33):
    import json, os, random, time, numpy as np, torch
    from transformers import AutoModel, AutoTokenizer
    random.seed(0); torch.manual_seed(0)
    print("torch", torch.__version__, "| arch", torch.cuda.get_arch_list(), "|", torch.cuda.get_device_name(0), flush=True)

    doc = {}
    for line in open("/data/doc_corpus.jsonl"):
        d = json.loads(line); doc[d["track_id"]] = d["doc"]
    valid = set(doc); all_tids = list(valid)
    neg_field = "negs_filt" if negs == "filt" else "negs_raw"
    rows = [json.loads(l) for l in open("/data/3tower_data.jsonl")]
    does_not = {}
    for r in rows:
        if r["gpa"] and r["gpa"] != MOVES:
            does_not.setdefault(r.get("sid"), []).append(r["pos"])
    ex = []
    for r in rows:
        if variant in ("b", "c") and r["gpa"] != MOVES:
            continue
        if r["pos"] not in valid:
            continue
        ns = [n for n in r[neg_field] if n in valid]
        hist = [t for t in r["hist"] if t in valid][-k_hist:]
        ex.append({"q": r["q"], "pos": r["pos"], "negs": ns, "hist": hist,
                   "pivot": bool(r["gpa"]) and r["gpa"] != MOVES})
    random.shuffle(ex)
    if limit:
        ex = ex[:limit]
    print(f"variant={variant} examples={len(ex)} docs={len(valid)}", flush=True)

    if hist_neg:
        # content-departure flag using BASE (zero-shot) doc embeddings — NOT the noisy gpa label and
        # NOT b1's fine-tuned geometry. Flag the lowest-cos(pos, recency-history) fraction as departures.
        DB = np.load("/data/docs_base.npy").astype("float32")
        DB = DB / np.maximum(np.linalg.norm(DB, axis=1, keepdims=True), 1e-9)
        didx = {t: i for i, t in enumerate(doc)}  # doc dict is in doc_corpus order == docs_base.npy order
        recw = np.array([0.6 ** (k_hist - 1 - i) for i in range(k_hist)], dtype="float32")
        coss = []
        for e in ex:
            h = e["hist"][-k_hist:]
            if not h or e["pos"] not in didx or any(t not in didx for t in h):
                e["hist_cos"] = None; continue
            w = recw[-len(h):]
            hv = (DB[[didx[t] for t in h]] * w[:, None]).sum(0)
            hv = hv / (np.linalg.norm(hv) + 1e-9)
            e["hist_cos"] = float(DB[didx[e["pos"]]] @ hv); coss.append(e["hist_cos"])
        thr = float(np.quantile(coss, hist_neg_frac)) if coss else 0.0
        nd = nm = 0
        for e in ex:
            e["hist_dep"] = e.get("hist_cos") is not None and e["hist_cos"] < thr
            if e["hist_dep"]:
                nd += 1; nm += 0 if e["pivot"] else 1
        print(f"hist-neg: {nd} departures (cos<{thr:.3f}, frac={hist_neg_frac}); "
              f"{nm}/{nd} ({100*nm/max(1,nd):.0f}%) were gpa=MOVES — label-only would MISS these", flush=True)

    tok = AutoTokenizer.from_pretrained(BASE, padding_side="left")
    model = AutoModel.from_pretrained(BASE, dtype=torch.float32, attn_implementation="sdpa").cuda().train()
    if freeze_bottom > 0:
        if hasattr(model, "embed_tokens"): model.embed_tokens.requires_grad_(False)
        for i, layer in enumerate(model.layers):
            if i < freeze_bottom: layer.requires_grad_(False)
    model.gradient_checkpointing_enable(); model.config.use_cache = False  # 3-tower encodes 512 seqs/step
    dd = model.config.hidden_size
    gate = torch.nn.Sequential(torch.nn.Linear(dd, 256), torch.nn.ReLU(), torch.nn.Linear(256, 1)).cuda()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad] + list(gate.parameters()), lr=lr)
    rec_w = torch.tensor([0.6 ** (k_hist - 1 - i) for i in range(k_hist)], device="cuda")

    def lastpool(h, m):
        left = bool((m[:, -1].sum() == m.shape[0]).item())
        if left: return h[:, -1]
        i = m.sum(1) - 1; return h[torch.arange(h.shape[0], device=h.device), i]

    def enc(texts):
        b = tok(texts, padding=True, truncation=True, max_length=max_len, return_tensors="pt")
        b = {k: v.cuda() for k, v in b.items()}
        with torch.autocast("cuda", dtype=torch.bfloat16):
            o = model(**b)
        return torch.nn.functional.normalize(lastpool(o.last_hidden_state, b["attention_mask"]).float(), p=2, dim=1)

    def hist_vec(batch):
        flat, mask = [], []
        for e in batch:
            h = e["hist"][-k_hist:]; m = [1.0] * len(h) + [0.0] * (k_hist - len(h))
            h = h + [all_tids[0]] * (k_hist - len(h))
            flat += [doc[t] for t in h]; mask.append(m)
        H = enc(flat).view(len(batch), k_hist, -1)
        w = (rec_w * torch.tensor(mask, device="cuda")).unsqueeze(-1)
        hv = (H * w).sum(1)
        return torch.nn.functional.normalize(hv + 1e-8, p=2, dim=1), (w.sum(1) > 0).float()

    t0 = time.time(); steps = 0
    for epoch in range(epochs):
        random.shuffle(ex)
        for i in range(0, len(ex) - bs + 1, bs):
            batch = ex[i:i + bs]
            R = enc([INSTRUCT + e["q"] for e in batch])
            Hv, hmask = hist_vec(batch)
            g_raw = torch.sigmoid(gate(R)); g = g_raw * hmask
            Q = torch.nn.functional.normalize(R + g * Hv, p=2, dim=1)
            pos = [doc[e["pos"]] for e in batch]; ne = []
            for e in batch:
                nn_ = e["negs"][:n_hardneg]
                while len(nn_) < n_hardneg: nn_ = nn_ + [random.choice(all_tids)]
                if hist_neg:
                    # content-gated: on a departure turn the recently-played tracks are the tempting-WRONG
                    # answers -> as hard negatives they force the gate to turn history off (g->0).
                    hn = list(e["hist"]) if e.get("hist_dep") else []
                    while len(hn) < n_histneg: hn = hn + [random.choice(all_tids)]
                    nn_ = nn_ + hn[:n_histneg]
                ne += [doc[t] for t in nn_]
            D = enc(pos + ne)
            logits = (Q @ D.t()) * scale
            loss = torch.nn.functional.cross_entropy(logits, torch.arange(len(batch), device="cuda"))
            av = 0.0
            if hist_neg and gate_aux > 0:
                # direct supervision so the GATE learns (not the 600M encoder dodging): g->0 dep, g->1 cont
                hm = hmask.squeeze(-1).bool()
                if hm.any():
                    tgt = torch.tensor([0.0 if e.get("hist_dep") else 1.0 for e in batch], device="cuda")
                    aux = torch.nn.functional.binary_cross_entropy(g_raw.squeeze(-1)[hm], tgt[hm])
                    loss = loss + gate_aux * aux; av = aux.item()
            opt.zero_grad(); loss.backward(); opt.step(); steps += 1
            if steps % 50 == 0:
                hm = hmask.squeeze(-1).bool(); gh = g_raw.squeeze(-1)[hm]
                dep = torch.tensor([bool(e.get("hist_dep")) for e in batch], device="cuda")[hm]
                gd = gh[dep].mean().item() if dep.any() else float("nan")
                gc = gh[~dep].mean().item() if (~dep).any() else float("nan")
                print(f"  ep{epoch} step{steps} loss={loss.item():.3f} aux={av:.3f} g_dep={gd:.2f} g_cont={gc:.2f} "
                      f"sep={gc-gd:+.2f} {steps*bs/(time.time()-t0):.0f} ex/s", flush=True)
    out = f"/models/{out_name}"; os.makedirs(out, exist_ok=True)
    model.save_pretrained(out); tok.save_pretrained(out); torch.save(gate.state_dict(), f"{out}/gate.pt")
    json.dump({"variant": variant, "k_hist": k_hist, "epochs": epochs, "arch": "3tower-gate",
               "hist_neg": hist_neg, "gate_aux": gate_aux, "hist_neg_frac": hist_neg_frac,
               "examples": len(ex), "instruct": INSTRUCT}, open(f"{out}/train_meta.json", "w"), indent=2)
    model_vol.commit()
    print(f"DONE saved {out} ({steps} steps, {time.time()-t0:.0f}s)", flush=True)


@app.local_entrypoint()
def main():
    # variant b (MOVES-only positives) to MATCH b1 — apples-to-apples + clean retrieval. The gate still
    # learns: 51% of content-departures are MOVES turns. Full-FT, content-gated history negatives
    # (base-emb departure flag) + auxiliary BCE loss directly on g. n_hardneg=4 matches b1.
    train.remote(variant="b", epochs=2, bs=32, n_hardneg=4, n_histneg=3, k_hist=3,
                 hist_neg=True, gate_aux=0.3, hist_neg_frac=0.33, out_name="scout_3tower_aux")
