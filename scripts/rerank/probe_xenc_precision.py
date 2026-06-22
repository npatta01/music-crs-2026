"""Precision-parity check for the 4B cross-encoder labeler (local GB10 / Blackwell).

Does fp8 / bf16 preserve the RANKING quality we depend on (AUC(GT vs random), clean-neg rate)
vs fp16, and is it faster? Run once per --precision and compare. The metric is rank-based, so
what matters is parity within noise, not absolute scores.

    .venv/bin/python scripts/rerank/probe_xenc_precision.py --precision fp16 --limit 100
    .venv/bin/python scripts/rerank/probe_xenc_precision.py --precision bf16 --limit 100
    .venv/bin/python scripts/rerank/probe_xenc_precision.py --precision fp8  --limit 100
"""
from __future__ import annotations
import argparse, json, random, sys, time

sys.path.insert(0, "scripts/rerank")
from probe_xenc_mining import load_pairs, auc, MOVES
from probe_xenc_zeroshot import load_catalog, INSTRUCT

MODEL = "Qwen/Qwen3-Reranker-4B"


def load_model(precision):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL, padding_side="left")
    kw = {}
    if precision == "fp16":
        kw["dtype"] = torch.float16
    elif precision == "bf16":
        kw["dtype"] = torch.bfloat16
    elif precision == "fp8":
        from transformers import FineGrainedFP8Config
        kw["quantization_config"] = FineGrainedFP8Config()
        kw["dtype"] = torch.bfloat16  # compute dtype around fp8 linears
    else:
        raise ValueError(precision)
    model = AutoModelForCausalLM.from_pretrained(MODEL, device_map="cuda", **kw).eval()
    return tok, model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--precision", choices=["fp16", "bf16", "fp8"], required=True)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--n-random", type=int, default=10)
    ap.add_argument("--bs", type=int, default=16)
    a = ap.parse_args()
    import torch
    dev = "cuda"; random.seed(0)
    rows, pos_at, _ = load_pairs(); meta = load_catalog()
    moves = [r for r in rows if r["pos"] in meta]
    random.shuffle(moves); moves = moves[: a.limit]
    all_tids = list(meta)

    print(f"loading 4B @ {a.precision} ...", flush=True)
    t_load = time.time()
    tok, model = load_model(a.precision)
    pre = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the '
           'Query and the Instruct provided. Note that the answer can only be "yes" or "no".'
           '<|im_end|>\n<|im_start|>user\n')
    suf = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    pre_ids = tok.encode(pre, add_special_tokens=False); suf_ids = tok.encode(suf, add_special_tokens=False)
    yes_id = tok.convert_tokens_to_ids("yes"); no_id = tok.convert_tokens_to_ids("no")
    print(f"  loaded in {time.time()-t_load:.0f}s; mem={torch.cuda.max_memory_allocated()/1e9:.1f}GB", flush=True)

    def score(pairs):
        out = []
        for i in range(0, len(pairs), a.bs):
            b = pairs[i:i + a.bs]
            texts = [f"<Instruct>: {INSTRUCT}\n<Query>: {q}\n<Document>: {d}" for q, d in b]
            enc = tok(texts, truncation=True, max_length=1024, add_special_tokens=False)
            ids = [pre_ids + x + suf_ids for x in enc["input_ids"]]
            mx = max(len(x) for x in ids); pad = tok.pad_token_id or tok.eos_token_id
            inp = torch.tensor([[pad] * (mx - len(x)) + x for x in ids], device=dev)
            am = torch.tensor([[0] * (mx - len(x)) + [1] * len(x) for x in ids], device=dev)
            with torch.no_grad():
                lg = model(inp, attention_mask=am).logits[:, -1]
            p = torch.softmax(torch.stack([lg[:, no_id], lg[:, yes_id]], -1), -1)[:, 1]
            out.extend(p.float().cpu().tolist())
        return out

    gt_all, rand_all, clean = [], [], []
    npairs = 0; t0 = time.time()
    for r in moves:
        q = r["q"]
        prev = pos_at.get((r["sid"], r["tn"] - 1))
        if prev and prev in meta:
            q += f"\n[previously recommended] {meta[prev]['artist']} - {meta[prev]['title']}"
        negs = [n for n in r["negs"] if n in meta]
        forb = {r["pos"], *negs}; rnd = []
        while len(rnd) < a.n_random:
            t = random.choice(all_tids)
            if t not in forb: rnd.append(t); forb.add(t)
        docs = [r["pos"]] + negs + rnd
        sc = score([(q, meta[t]["text"]) for t in docs]); npairs += len(docs)
        gt = sc[0]; ns = sc[1:1 + len(negs)]; rs = sc[1 + len(negs):]
        gt_all.append(gt); rand_all += rs
        if negs: clean.append(sum(1 for x in ns if x < gt) / len(negs))
    dt = time.time() - t0
    import statistics as st
    print(f"\n=== 4B @ {a.precision} (n={len(moves)}) ===")
    print(f"  AUC(GT vs random) = {auc(gt_all, rand_all):.4f}")
    print(f"  clean-neg rate    = {sum(clean)/len(clean):.4f}")
    print(f"  GT median P(yes)  = {st.median(gt_all):.4f}")
    print(f"  throughput        = {npairs/dt:.1f} pairs/s  ({npairs} pairs in {dt:.0f}s)")
    print(f"  peak GPU mem      = {torch.cuda.max_memory_allocated()/1e9:.1f} GB")


if __name__ == "__main__":
    main()
