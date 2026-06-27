"""Modal 2-tower bi-encoder trainer (the b1 recipe) — fast A100 iteration for the epochs/input sweeps.

Mirrors scripts/rerank/train_biencoder.py EXACTLY (variant b MOVES-only, kf-dropout 0.3, MNRL,
INSTRUCT prefix, left-pad + last-token pool for serving parity). Saves a checkpoint after EACH epoch
so one run yields e1/e2/e3 to compare via the judge A/B (eval_scout_feature). cu130 image, A100-80GB.

Reads /data/retriever_pairs.jsonl + /data/doc_corpus.jsonl from the `biencoder-data` volume,
writes checkpoints to the `scout-models` volume.

    modal run scripts/rerank/modal_train_biencoder.py
    modal volume get scout-models /biencoder_qwen06_eN ./models/   # N = 1,2,3
"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.9.1", index_url="https://download.pytorch.org/whl/cu130")
    .pip_install("transformers>=4.51.0", "numpy", "huggingface_hub", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}))
app = modal.App("scout-biencoder", image=image)
data_vol = modal.Volume.from_name("biencoder-data", create_if_missing=True)
model_vol = modal.Volume.from_name("scout-models", create_if_missing=True)
hf_vol = modal.Volume.from_name("hf-cache", create_if_missing=True)
INSTRUCT = ("Instruct: Given a music recommendation conversation, retrieve relevant track "
            "metadata passages that match the listener request and prior music preferences.\nQuery: ")
BASE = "Qwen/Qwen3-Embedding-0.6B"
MOVES = "MOVES_TOWARD_GOAL"


@app.function(gpu="H100", volumes={"/data": data_vol, "/models": model_vol,
              "/root/.cache/huggingface": hf_vol}, timeout=14400)
def train(variant="b", negs="filt", epochs=3, bs=64, n_hardneg=4, lr=2e-5, kf_dropout=0.3,
          max_len=512, scale=20.0, limit=0, out_prefix="biencoder_qwen06", grad_ckpt=True):
    import json, os, random, time, torch
    from transformers import AutoModel, AutoTokenizer
    random.seed(0); torch.manual_seed(0)
    print("torch", torch.__version__, "|", torch.cuda.get_device_name(0), flush=True)

    doc_kf, doc_nokf = {}, {}
    for line in open("/data/doc_corpus.jsonl"):
        d = json.loads(line); doc_kf[d["track_id"]] = d["doc"]; doc_nokf[d["track_id"]] = d.get("doc_nokf", d["doc"])
    valid = set(doc_kf); all_tids = list(valid)
    neg_field = "negs_filt" if negs == "filt" else "negs_raw"
    rows = [json.loads(l) for l in open("/data/retriever_pairs.jsonl")]
    rows = [r for r in rows if r["pos_id"] in valid]
    does_not = {}
    for r in rows:
        if r["gpa"] and r["gpa"] != MOVES:
            does_not.setdefault(r["sid"], []).append(r["pos_id"])
    ex = []
    for r in rows:
        if variant in ("b", "c") and r["gpa"] != MOVES:
            continue
        ns = [n for n in r[neg_field] if n in valid]
        if variant == "c":
            ns = ns + [t for t in does_not.get(r["sid"], []) if t in valid and t != r["pos_id"]][:3]
        ex.append({"q": r["q"], "pos": r["pos_id"], "negs": ns})
    random.shuffle(ex)
    if limit:
        ex = ex[:limit]
    print(f"variant={variant} negs={negs} examples={len(ex)} docs={len(valid)}", flush=True)

    tok = AutoTokenizer.from_pretrained(BASE, padding_side="left")
    model = AutoModel.from_pretrained(BASE, dtype=torch.float32, attn_implementation="sdpa").cuda().train()
    model.config.use_cache = False  # MUST be off for training — leaving it True builds a KV cache that
    # the autograd graph retains and OOMs 80GB. With it off, bs64 fits in ~40GB even WITHOUT grad-ckpt.
    if grad_ckpt:
        model.gradient_checkpointing_enable()
    opt = torch.optim.AdamW(model.parameters(), lr=lr)

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

    def render(tid):
        return doc_nokf[tid] if random.random() < kf_dropout else doc_kf[tid]

    def save(name, ep):
        out = f"/models/{name}"; os.makedirs(out, exist_ok=True)
        model.save_pretrained(out); tok.save_pretrained(out)
        json.dump({"variant": variant, "negs": negs, "epochs": ep, "bs": bs, "n_hardneg": n_hardneg,
                   "lr": lr, "kf_dropout": kf_dropout, "instruct": INSTRUCT, "base": BASE, "examples": len(ex)},
                  open(f"{out}/train_meta.json", "w"), indent=2)
        model_vol.commit(); print(f"  saved {out} (epoch {ep})", flush=True)

    t0 = time.time(); steps = 0
    for epoch in range(epochs):
        random.shuffle(ex)
        for i in range(0, len(ex) - bs + 1, bs):
            batch = ex[i:i + bs]
            Q = enc([INSTRUCT + e["q"] for e in batch])
            pos = [render(e["pos"]) for e in batch]; ne = []
            for e in batch:
                ns = e["negs"][:n_hardneg]
                while len(ns) < n_hardneg: ns = ns + [random.choice(all_tids)]
                ne += [render(t) for t in ns]
            D = enc(pos + ne)
            logits = (Q @ D.t()) * scale
            loss = torch.nn.functional.cross_entropy(logits, torch.arange(len(batch), device="cuda"))
            opt.zero_grad(); loss.backward(); opt.step(); steps += 1
            if steps % 50 == 0:
                print(f"  ep{epoch} step{steps} loss={loss.item():.3f} {steps*bs/(time.time()-t0):.0f} ex/s", flush=True)
        save(f"{out_prefix}_e{epoch + 1}", epoch + 1)   # checkpoint after every epoch
    print(f"DONE ({steps} steps, {time.time()-t0:.0f}s)", flush=True)


@app.local_entrypoint()
def main():
    # epochs sweep: identical to b1 (variant b, kf-dropout 0.3, n_hardneg 4) but 3 epochs, saving e1/e2/e3.
    # e1 should reproduce b1 (+0.0087); the question is whether e2/e3 beat it on the judge A/B.
    # grad_ckpt=True REQUIRED at bs64 full-FT on 80GB (use_cache=False alone is NOT enough — verified OOM).
    train.remote(variant="b", negs="filt", epochs=3, bs=64, n_hardneg=4, kf_dropout=0.3,
                 grad_ckpt=True, out_prefix="biencoder_qwen06")
