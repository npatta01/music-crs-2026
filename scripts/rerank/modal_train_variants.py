"""Modal: train the bi-encoder INPUT-variants (GOAL-FREE) + retrieval eval ON MODAL.

Issue #153. Each variant = a fresh 1-epoch b1-recipe train (variant b MOVES-only, kf-drop 0.3,
n_hardneg 4) on its own GOAL-FREE input format (pairs_<v>.jsonl, built by modal_build_data.py),
then — GPU still warm — embeds the 47k docs + the devset eval queries and computes
recall@{20,100,1000} + medrank, OVERALL and PER LANE (continuation / hard_pivot / turn_1). Returns
a metrics dict so the LOCAL box does ZERO heavy work. v_tok adds learned special tokens
(<|prev|>/<|now|>, mean-init from the plain-marker subwords; resize embeddings).

Inputs (on the `biencoder-data` volume, produced by modal_build_data.py): doc_corpus.jsonl,
input_variants/{pairs,eval}_<v>.jsonl, devset_lanes_v10.jsonl.

    modal run scripts/rerank/modal_train_variants.py::main                        # Round 1: baseline + v_struct + v_tok @2048
    modal run scripts/rerank/modal_train_variants.py::four_b --variant <winner>   # 4B lift (PAUSED step)
"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.9.1", index_url="https://download.pytorch.org/whl/cu130")
    .pip_install("transformers>=4.51.0", "numpy", "huggingface_hub", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}))
app = modal.App("scout-variants", image=image)
data_vol = modal.Volume.from_name("biencoder-data", create_if_missing=True)
model_vol = modal.Volume.from_name("scout-models", create_if_missing=True)
hf_vol = modal.Volume.from_name("hf-cache", create_if_missing=True)
INSTRUCT = ("Instruct: Given a music recommendation conversation, retrieve relevant track "
            "metadata passages that match the listener request and prior music preferences.\nQuery: ")
BASE = "Qwen/Qwen3-Embedding-0.6B"
MOVES = "MOVES_TOWARD_GOAL"
# GOAL-FREE (Blind B drops conversation_goal). v_tok mirrors v_struct structure with learned tokens.
SPECIAL_TOKENS = ["<|prev|>", "<|now|>"]
MARKER = {"<|prev|>": "[prev]", "<|now|>": "[now]"}


def _train_eval(variant, base=BASE, special_tokens=None, epochs=1, bs=64, n_hardneg=4, lr=2e-5,
                kf_dropout=0.3, max_len=2048, scale=20.0, limit=0):
    import json, os, random, time, numpy as np, torch
    from transformers import AutoModel, AutoTokenizer
    random.seed(0); torch.manual_seed(0)
    print(f"[{variant}] base={base} torch {torch.__version__} | {torch.cuda.get_device_name(0)} | "
          f"special_tokens={special_tokens} max_len={max_len}", flush=True)

    doc_kf, doc_nokf, tids = {}, {}, []
    for line in open("/data/doc_corpus.jsonl"):
        d = json.loads(line); doc_kf[d["track_id"]] = d["doc"]; doc_nokf[d["track_id"]] = d.get("doc_nokf", d["doc"])
        tids.append(d["track_id"])
    valid = set(doc_kf); all_tids = list(valid); tidx = {t: i for i, t in enumerate(tids)}

    rows = [json.loads(l) for l in open(f"/data/input_variants/pairs_{variant}.jsonl")]
    ex = []
    for r in rows:
        if r["gpa"] != MOVES or r["pos_id"] not in valid:   # variant b (MOVES-only), like b1
            continue
        ns = [n for n in r["negs_filt"] if n in valid]
        ex.append({"q": r["q"], "pos": r["pos_id"], "negs": ns})
    random.shuffle(ex)
    if limit: ex = ex[:limit]
    print(f"[{variant}] examples={len(ex)} docs={len(valid)}", flush=True)

    tok = AutoTokenizer.from_pretrained(base, padding_side="left")
    model = AutoModel.from_pretrained(base, dtype=torch.float32, attn_implementation="sdpa").cuda().train()
    model.config.use_cache = False
    model.gradient_checkpointing_enable()   # REQUIRED at bs64 full-FT on 80GB (verified: OOMs without it)
    if special_tokens:
        # mean-init each new token from its plain-marker subwords (avoid random cold-start, advisor fix)
        emb0 = model.get_input_embeddings().weight.data
        inits = {st: emb0[tok(MARKER.get(st, st), add_special_tokens=False)["input_ids"]].mean(0).clone()
                 for st in special_tokens}
        tok.add_special_tokens({"additional_special_tokens": special_tokens})
        model.resize_token_embeddings(len(tok))
        emb = model.get_input_embeddings().weight.data
        for st in special_tokens:
            emb[tok.convert_tokens_to_ids(st)] = inits[st]
        print(f"[{variant}] added + mean-init {len(special_tokens)} special tokens; vocab now {len(tok)}", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)

    def lastpool(h, m):
        if bool((m[:, -1].sum() == m.shape[0]).item()): return h[:, -1]
        i = m.sum(1) - 1; return h[torch.arange(h.shape[0], device=h.device), i]

    def enc(texts, train_mode=True):
        b = tok(texts, padding=True, truncation=True, max_length=max_len, return_tensors="pt")
        b = {k: v.cuda() for k, v in b.items()}
        ctx = torch.enable_grad() if train_mode else torch.inference_mode()
        with ctx, torch.autocast("cuda", dtype=torch.bfloat16):
            o = model(**b)
        return torch.nn.functional.normalize(lastpool(o.last_hidden_state, b["attention_mask"]).float(), p=2, dim=1)

    def render(tid):
        return doc_nokf[tid] if random.random() < kf_dropout else doc_kf[tid]

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
            loss = torch.nn.functional.cross_entropy((Q @ D.t()) * scale, torch.arange(len(batch), device="cuda"))
            opt.zero_grad(); loss.backward(); opt.step(); steps += 1
            if steps % 100 == 0:
                print(f"[{variant}] ep{epoch} step{steps} loss={loss.item():.3f} {steps*bs/(time.time()-t0):.0f} ex/s", flush=True)
    # distinct tag per (variant, max_len, base) so a 4B run never clobbers the 0.6B checkpoint/ranks
    base_tag = "" if base == BASE else "_" + base.split("/")[-1].replace(".", "").lower()
    tag = f"{variant}_l{max_len}{base_tag}"
    out = f"/models/biencoder_variant_{tag}"; os.makedirs(out, exist_ok=True)
    model.save_pretrained(out); tok.save_pretrained(out)
    model_vol.commit()

    # --- retrieval eval ON MODAL (GPU warm): full-catalog GT rank on devset MOVES turns ---
    model.eval(); model.gradient_checkpointing_disable()
    DOC = torch.cat([enc([doc_kf[t] for t in tids[i:i+256]], train_mode=False) for i in range(0, len(tids), 256)])
    evals = []
    for l in open(f"/data/input_variants/eval_{variant}.jsonl"):
        e = json.loads(l)
        if e["gt"] in tidx:
            evals.append(e)
    Qe = torch.cat([enc([INSTRUCT + e["q"] for e in evals[i:i+256]], train_mode=False) for i in range(0, len(evals), 256)])
    ranks = []
    for i in range(0, len(evals), 256):
        S = Qe[i:i+256] @ DOC.t()                       # chunk x 47k
        for j, e in enumerate(evals[i:i+256]):
            gp = tidx[e["gt"]]; ranks.append(int((S[j] > S[j, gp]).sum().item()) + 1)
    ranks = np.array(ranks)

    # per-lane breakdown (lanes uploaded to the volume): continuation / hard_pivot / turn_1
    lane_by_key = {}
    if os.path.exists("/data/devset_lanes_v10.jsonl"):
        for l in open("/data/devset_lanes_v10.jsonl"):
            d = json.loads(l); lane_by_key[(str(d["session_id"]), int(d["turn_number"]))] = d.get("lane", "?")
    lane_of = [lane_by_key.get((str(e["sid"]), int(e["tn"])), "?") for e in evals]

    def _metrics(rk):
        rk = np.asarray(rk)
        n = int(len(rk))
        if not n:
            return {"n": 0, "r@20": 0.0, "r@100": 0.0, "r@1000": 0.0, "medrank": 0}
        return {"n": n, "r@20": float((rk <= 20).mean()), "r@100": float((rk <= 100).mean()),
                "r@1000": float((rk <= 1000).mean()), "medrank": int(np.median(rk))}

    by_lane = {ln: _metrics([rk for rk, l in zip(ranks.tolist(), lane_of) if l == ln])
               for ln in sorted(set(lane_of))}
    m = {"variant": variant, "base": base, "max_len": max_len, "tag": tag, "examples": len(ex),
         "special_tokens": bool(special_tokens), **_metrics(ranks), "by_lane": by_lane}
    json.dump(m, open(f"{out}/retrieval.json", "w"), indent=2)
    json.dump([{"sid": e["sid"], "tn": e["tn"], "gt": e["gt"], "rank": int(rk)}
               for e, rk in zip(evals, ranks.tolist())], open(f"/models/ranks_{tag}.json", "w"))
    model_vol.commit()
    print(f"[{variant}] RETRIEVAL n={m['n']} r@20={m['r@20']*100:.1f} r@100={m['r@100']*100:.1f} "
          f"r@1000={m['r@1000']*100:.1f} medrank={m['medrank']} ({time.time()-t0:.0f}s)", flush=True)
    for ln, lm in by_lane.items():
        if lm.get("n"):
            print(f"    lane={ln:<13} n={lm['n']:<5} r@20={lm['r@20']*100:5.1f} r@100={lm['r@100']*100:5.1f} "
                  f"r@1000={lm['r@1000']*100:5.1f} medrank={lm['medrank']}", flush=True)
    return m


_VOLS = {"/data": data_vol, "/models": model_vol, "/root/.cache/huggingface": hf_vol}
_SECRETS = [modal.Secret.from_name("huggingface")]


@app.function(gpu="H100", volumes=_VOLS, secrets=_SECRETS, timeout=10800)
def train_eval(variant, base=BASE, special_tokens=None, epochs=1, bs=64, n_hardneg=4, lr=2e-5,
               kf_dropout=0.3, max_len=2048, scale=20.0, limit=0):
    return _train_eval(variant, base, special_tokens, epochs, bs, n_hardneg, lr, kf_dropout, max_len, scale, limit)


@app.function(gpu="H200", volumes=_VOLS, secrets=_SECRETS, timeout=14400)
def train_eval_4b(variant, base="Qwen/Qwen3-Embedding-4B", special_tokens=None, epochs=1, bs=64,
                  n_hardneg=4, lr=2e-5, kf_dropout=0.3, max_len=2048, scale=20.0, limit=0):
    return _train_eval(variant, base, special_tokens, epochs, bs, n_hardneg, lr, kf_dropout, max_len, scale, limit)


def _print_grid(results):
    print("\n==== Round 1: baseline vs v_tok @ max_len=2048 (GOAL-FREE) ====")
    print(f"{'run':<12} {'medrank':>8} {'r@1000':>7} {'r@100':>6} {'r@20':>6}")
    for name, m in results.items():
        print(f"{name:<12} {m['medrank']:8d} {m['r@1000']*100:7.1f} {m['r@100']*100:6.1f} {m['r@20']*100:6.1f}", flush=True)
    lanes = sorted(set().union(*[set(m.get("by_lane", {})) for m in results.values()])) if results else []
    print("\n==== per-lane (medrank / r@100) ====")
    for ln in lanes:
        row = f"  {ln:<13}"
        for name, m in results.items():
            lm = m.get("by_lane", {}).get(ln, {})
            row += f"   {name}: med={lm.get('medrank', '-')} r@100={lm.get('r@100', 0) * 100:.1f}"
        print(row, flush=True)


@app.local_entrypoint()
def main():
    # Round 1 (Issue #153): baseline vs v_tok, GOAL-FREE, max_len=2048. Each H100 job trains the b1
    # recipe on its own goal-free input + on-Modal full-catalog retrieval eval (overall + per-lane).
    jobs = [
        ("baseline", dict(variant="baseline", special_tokens=None, max_len=2048)),
        ("v_struct", dict(variant="v_struct", special_tokens=None, max_len=2048)),
        ("v_tok", dict(variant="v_tok", special_tokens=SPECIAL_TOKENS, max_len=2048)),
    ]
    handles = [(name, train_eval.spawn(**kw)) for name, kw in jobs]
    results = {name: h.get() for name, h in handles}
    _print_grid(results)


@app.local_entrypoint()
def four_b(variant: str = "baseline"):
    # 4B lift on the WINNING goal-free input (run AFTER the grid, on go-ahead). H200 for the larger
    # optimizer/grad footprint; full bs64 in one forward (no grad-accum -> in-batch-negative parity
    # with the 0.6B run). Distinct base_tag so it does NOT clobber the 0.6B checkpoint/ranks.
    st = SPECIAL_TOKENS if variant == "v_tok" else None
    h = train_eval_4b.spawn(variant=variant, special_tokens=st, max_len=2048)
    m = h.get()
    print(f"\n[4B / {variant}] n={m['n']} r@20={m['r@20']*100:.1f} r@100={m['r@100']*100:.1f} "
          f"r@1000={m['r@1000']*100:.1f} medrank={m['medrank']}", flush=True)
    for ln, lm in m.get("by_lane", {}).items():
        if lm.get("n"):
            print(f"    lane={ln:<13} med={lm['medrank']} r@100={lm['r@100']*100:.1f}", flush=True)
