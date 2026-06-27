"""M0c — fine-tune Qwen3-Embedding-0.6B as a conversation->track bi-encoder (MNRL).

Custom torch loop (NOT sentence-transformers) so pooling is byte-identical to the serving
`Qwen3EmbeddingClient`: left-padding + `_last_token_pool` + L2 normalize (reused directly from
`mcrs/embeddings/qwen3_embedding.py`). This makes train/serve pooling parity true by construction.

Query side gets the instruction prefix; doc side is raw (Qwen3 asymmetric convention). Known-for
field-dropout (~30%) randomly swaps the doc for its no-known-for variant so tracks keep their own
identity and the model doesn't over-rely on the artist blurb.

Label variants (the (a)/(b)/(c) ablation applied here from the variant-agnostic pairs file):
  a = all turns positive
  b = only MOVES_TOWARD_GOAL positive
  c = b + each MOVES turn's negatives augmented with its session's DOES_NOT played tracks
      (soft, session-local negatives)
FN-filter ablation via --negs {filt,raw}.

Saves an HF-format checkpoint loadable by `Qwen3EmbeddingClient(model_name=<out>)`.

Run from the main checkout. Example (smoke):
    python scripts/rerank/train_biencoder.py --variant b --limit 4000 --epochs 1 --out models/biencoder_qwen06_smoke
Full:
    python scripts/rerank/train_biencoder.py --variant b --negs filt --epochs 2 --out models/biencoder_qwen06_v1
"""
from __future__ import annotations
import argparse, json, os, random, sys, time
sys.path.insert(0, "scripts/rerank")
import torch
from transformers import AutoModel, AutoTokenizer
from mcrs.embeddings.qwen3_embedding import _last_token_pool, DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS

BASE = "Qwen/Qwen3-Embedding-0.6B"
PAIRS = "exp/analysis/retrieval_exploration/retriever_pairs.jsonl"
DOCS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
MOVES = "MOVES_TOWARD_GOAL"
INSTRUCT = DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS  # "Instruct: ...\nQuery: "


def load_docs(path):
    kf, nokf = {}, {}
    if not os.path.exists(path):  # fall back to the base (no-known-for) corpus
        path = path.replace("doc_corpus.jsonl", "doc_corpus_base.jsonl")
        print(f"[docs] {DOCS} absent, using {path}", flush=True)
    for line in open(path):
        d = json.loads(line)
        kf[d["track_id"]] = d["doc"]; nokf[d["track_id"]] = d.get("doc_nokf", d["doc"])
    return kf, nokf


def build_examples(pairs_path, variant, neg_field, valid):
    rows = [json.loads(l) for l in open(pairs_path)]
    rows = [r for r in rows if r["pos_id"] in valid]
    does_not_by_sess = {}
    for r in rows:
        if r["gpa"] and r["gpa"] != MOVES:
            does_not_by_sess.setdefault(r["sid"], []).append(r["pos_id"])
    ex = []
    for r in rows:
        if variant in ("b", "c") and r["gpa"] != MOVES:
            continue
        negs = [n for n in r[neg_field] if n in valid]
        if variant == "c":
            extra = [t for t in does_not_by_sess.get(r["sid"], []) if t in valid and t != r["pos_id"]]
            negs = negs + extra[:3]  # soft session-local negatives
        ex.append({"q": r["q"], "pos": r["pos_id"], "negs": negs})
    return ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["a", "b", "c"], default="b")
    ap.add_argument("--negs", choices=["filt", "raw"], default="filt")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--bs", type=int, default=64)
    ap.add_argument("--n-hardneg", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--kf-dropout", type=float, default=0.3)
    ap.add_argument("--max-len", type=int, default=512)  # was 96 → truncated ~90% of queries (req dropped)
    ap.add_argument("--scale", type=float, default=20.0)
    ap.add_argument("--limit", type=int, default=0, help="subsample N examples (smoke test)")
    ap.add_argument("--pairs", default=PAIRS, help="training pairs jsonl (override for refinement experiments)")
    ap.add_argument("--grad-ckpt", action="store_true", help="gradient checkpointing (slower, less mem)")
    ap.add_argument("--freeze-bottom", type=int, default=0, help="freeze embeddings + bottom-N layers (fast ablation)")
    ap.add_argument("--log-every", type=int, default=50)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    random.seed(0); torch.manual_seed(0)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    neg_field = "negs_filt" if a.negs == "filt" else "negs_raw"

    doc_kf, doc_nokf = load_docs(DOCS)
    valid = set(doc_kf)
    all_tids = list(valid)
    ex = build_examples(a.pairs, a.variant, neg_field, valid)
    random.shuffle(ex)
    if a.limit:
        ex = ex[: a.limit]
    print(f"variant={a.variant} negs={a.negs} examples={len(ex)} docs={len(valid)}", flush=True)

    tok = AutoTokenizer.from_pretrained(BASE, padding_side="left")
    # fp32 master weights (stable AdamW) + bf16 autocast forward
    model = AutoModel.from_pretrained(BASE, dtype=torch.float32).to(dev).train()
    if a.grad_ckpt:
        model.gradient_checkpointing_enable()
        model.config.use_cache = False
    if a.freeze_bottom > 0:
        if hasattr(model, "embed_tokens"):
            model.embed_tokens.requires_grad_(False)
        for i, layer in enumerate(model.layers):
            if i < a.freeze_bottom:
                layer.requires_grad_(False)
        n_tr = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"froze embeddings + bottom {a.freeze_bottom}/{len(model.layers)} layers; "
              f"trainable params {n_tr/1e6:.0f}M", flush=True)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr)

    def encode(texts):
        b = tok(texts, padding=True, truncation=True, max_length=a.max_len, return_tensors="pt")
        b = {k: v.to(dev) for k, v in b.items()}
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            out = model(**b)
        pooled = _last_token_pool(out.last_hidden_state, b["attention_mask"], torch=torch)
        return torch.nn.functional.normalize(pooled.float(), p=2, dim=1)

    def render(tid):
        return doc_nokf[tid] if random.random() < a.kf_dropout else doc_kf[tid]

    steps = 0; t0 = time.time()
    for epoch in range(a.epochs):
        random.shuffle(ex)
        for i in range(0, len(ex) - a.bs + 1, a.bs):
            batch = ex[i : i + a.bs]
            q_texts = [INSTRUCT + b["q"] for b in batch]
            pos_texts = [render(b["pos"]) for b in batch]
            neg_texts = []
            for b in batch:
                ns = b["negs"][: a.n_hardneg]
                while len(ns) < a.n_hardneg:  # pad with random easy negs for uniform shape
                    ns = ns + [random.choice(all_tids)]
                neg_texts.extend(render(t) for t in ns)
            Q = encode(q_texts)                          # B x d
            D = encode(pos_texts + neg_texts)            # (B + B*k) x d
            cand = D                                      # columns 0..B-1 are the positives
            logits = (Q @ cand.t()) * a.scale            # B x (B + B*k)
            labels = torch.arange(len(batch), device=dev)
            loss = torch.nn.functional.cross_entropy(logits, labels)
            opt.zero_grad(); loss.backward(); opt.step()
            steps += 1
            if steps % a.log_every == 0:
                print(f"  ep{epoch} step{steps} loss={loss.item():.3f} "
                      f"({steps*a.bs/ max(1e-9, time.time()-t0):.0f} ex/s)", flush=True)
    os.makedirs(a.out, exist_ok=True)
    model.save_pretrained(a.out); tok.save_pretrained(a.out)
    json.dump({"variant": a.variant, "negs": a.negs, "epochs": a.epochs, "bs": a.bs,
               "n_hardneg": a.n_hardneg, "lr": a.lr, "kf_dropout": a.kf_dropout,
               "instruct": INSTRUCT, "base": BASE, "examples": len(ex)},
              open(os.path.join(a.out, "train_meta.json"), "w"), indent=2)
    print(f"DONE saved {a.out} ({steps} steps, {time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
