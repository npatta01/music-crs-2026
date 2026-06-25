"""Quantify 'named-artist fixation' on hard_pivot: how often does the 4B v_struct_pt retriever's
top-k come back as the JUST-PLAYED artist instead of pivoting? And how often is the GT a genuinely
different artist (the curatorial pivot a text retriever can't see)?

    modal run scripts/rerank/modal_fixation.py
"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.9.1", index_url="https://download.pytorch.org/whl/cu130")
    .pip_install("transformers>=4.51.0", "numpy", "huggingface_hub", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}))
app = modal.App("scout-fixation", image=image)
data_vol = modal.Volume.from_name("biencoder-data")
model_vol = modal.Volume.from_name("scout-models")
hf_vol = modal.Volume.from_name("hf-cache", create_if_missing=True)
INSTRUCT = ("Instruct: Given a music recommendation conversation, retrieve relevant track "
            "metadata passages that match the listener request and prior music preferences.\nQuery: ")
CKPT = "biencoder_variant_v_struct_pt_l2048_qwen3-embedding-4b"


@app.function(gpu="H100", volumes={"/data": data_vol, "/models": model_vol,
              "/root/.cache/huggingface": hf_vol},
              secrets=[modal.Secret.from_name("huggingface")], timeout=3600)
def fixation():
    import json, numpy as np, torch
    from transformers import AutoModel, AutoTokenizer

    tids, artist = [], []
    for line in open("/data/doc_corpus.jsonl"):
        d = json.loads(line); tids.append(d["track_id"]); artist.append((d.get("artist") or "").strip().lower())
    tidx = {t: i for i, t in enumerate(tids)}
    docs = [json.loads(l)["doc"] for l in open("/data/doc_corpus.jsonl")]

    tok = AutoTokenizer.from_pretrained(f"/models/{CKPT}", padding_side="left")
    model = AutoModel.from_pretrained(f"/models/{CKPT}", dtype=torch.float32, attn_implementation="sdpa").cuda().eval()
    model.config.use_cache = False

    def lastpool(h, m):
        if bool((m[:, -1].sum() == m.shape[0]).item()): return h[:, -1]
        i = m.sum(1) - 1; return h[torch.arange(h.shape[0], device=h.device), i]

    def enc(texts):
        b = tok(texts, padding=True, truncation=True, max_length=2048, return_tensors="pt")
        b = {k: v.cuda() for k, v in b.items()}
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            o = model(**b)
        return torch.nn.functional.normalize(lastpool(o.last_hidden_state, b["attention_mask"]).float(), p=2, dim=1)

    print(f"embedding {len(tids)} docs ...", flush=True)
    DOC = torch.cat([enc(docs[i:i+128]) for i in range(0, len(docs), 128)])

    lane = {}
    for l in open("/data/devset_lanes_v10.jsonl"):
        d = json.loads(l); lane[(str(d["session_id"]), int(d["turn_number"]))] = d.get("lane", "?")
    hp = [json.loads(l) for l in open("/data/input_variants/eval_v_struct_pt.jsonl")
          if lane.get((str(json.loads(l)["sid"]), int(json.loads(l)["tn"]))) == "hard_pivot"
          and json.loads(l)["gt"] in tidx]
    print(f"hard_pivot turns: {len(hp)}; embedding queries ...", flush=True)
    Q = torch.cat([enc([INSTRUCT + e["q"] for e in hp[i:i+128]]) for i in range(0, len(hp), 128)])

    def pt_artist(q):
        if "[prev_track]" not in q: return ""
        return q.split("[prev_track]", 1)[1].strip().split(" — ")[0].strip().lower()

    K = 10
    rows = []  # (gt_rank, pt_a, gt_a, top_artists[K])
    for i, e in enumerate(hp):
        s = Q[i] @ DOC.t()
        gi = tidx[e["gt"]]
        rank = int((s > s[gi]).sum().item()) + 1
        top = torch.topk(s, K).indices.tolist()
        rows.append((rank, pt_artist(e["q"]), artist[gi], [artist[t] for t in top]))

    def frac_same(ta, a): return np.mean([x == a and a != "" for x in ta]) if a else 0.0
    real_pivot = [r for r in rows if r[1] and r[1] != r[2]]      # prev_track artist != GT artist
    same_artist = [r for r in rows if r[1] and r[1] == r[2]]     # GT IS the just-played artist
    print(f"\n=== hard_pivot artist analysis (n={len(rows)}, 4B v_struct_pt) ===")
    print(f"  GT artist == just-played artist (not a real artist-pivot): {len(same_artist)} ({100*len(same_artist)/len(rows):.1f}%)")
    print(f"  GT artist != just-played artist (REAL pivot):              {len(real_pivot)} ({100*len(real_pivot)/len(rows):.1f}%)")

    def report(name, band):
        if not band: return
        top1_fix = 100*np.mean([r[3][0] == r[1] for r in band])
        mean_fix = 100*np.mean([frac_same(r[3], r[1]) for r in band])
        gt_in_top = 100*np.mean([r[2] in r[3] for r in band])   # right ARTIST anywhere in top-10
        print(f"\n  [{name}] n={len(band)}")
        print(f"    top-1 retrieved == just-played artist:     {top1_fix:.1f}%   (model 'stays' on the prev artist)")
        print(f"    mean % of top-10 == just-played artist:    {mean_fix:.1f}%")
        print(f"    GT's artist appears anywhere in top-10:    {gt_in_top:.1f}%")

    report("ALL real pivots", real_pivot)
    report("real pivot & GT in top-100", [r for r in real_pivot if r[0] <= 100])
    report("real pivot & GT deep (>1000)", [r for r in real_pivot if r[0] > 1000])


@app.local_entrypoint()
def main():
    fixation.remote()
