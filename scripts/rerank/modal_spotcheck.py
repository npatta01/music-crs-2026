"""Spot-check hard_pivot retrieval: for a sample of hard_pivot devset turns, print the query, the
GT track + its full-catalog rank, and the TOP-8 tracks the 4B v_struct_pt retriever returns instead.
Shows WHY the lane is hard (the retrieved alternatives are plausible; the single GT is under-determined).

    modal run scripts/rerank/modal_spotcheck.py
"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.9.1", index_url="https://download.pytorch.org/whl/cu130")
    .pip_install("transformers>=4.51.0", "numpy", "huggingface_hub", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}))
app = modal.App("scout-spotcheck", image=image)
data_vol = modal.Volume.from_name("biencoder-data")
model_vol = modal.Volume.from_name("scout-models")
hf_vol = modal.Volume.from_name("hf-cache", create_if_missing=True)
INSTRUCT = ("Instruct: Given a music recommendation conversation, retrieve relevant track "
            "metadata passages that match the listener request and prior music preferences.\nQuery: ")
CKPT = "biencoder_variant_v_struct_pt_l2048_qwen3-embedding-4b"


@app.function(gpu="H100", volumes={"/data": data_vol, "/models": model_vol,
              "/root/.cache/huggingface": hf_vol},
              secrets=[modal.Secret.from_name("huggingface")], timeout=3600)
def spotcheck(n_each=3):
    import json, numpy as np, torch
    from transformers import AutoModel, AutoTokenizer

    tids, docs = [], []
    for line in open("/data/doc_corpus.jsonl"):
        d = json.loads(line); tids.append(d["track_id"]); docs.append(d["doc"])
    tidx = {t: i for i, t in enumerate(tids)}

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

    print(f"embedding {len(tids)} docs with 4B v_struct_pt ...", flush=True)
    DOC = torch.cat([enc(docs[i:i+128]) for i in range(0, len(docs), 128)])

    lane = {}
    for l in open("/data/devset_lanes_v10.jsonl"):
        d = json.loads(l); lane[(str(d["session_id"]), int(d["turn_number"]))] = d.get("lane", "?")
    hp = []
    for l in open("/data/input_variants/eval_v_struct_pt.jsonl"):
        e = json.loads(l)
        if lane.get((str(e["sid"]), int(e["tn"]))) == "hard_pivot" and e["gt"] in tidx:
            hp.append(e)
    print(f"hard_pivot eval turns: {len(hp)}; embedding queries ...", flush=True)
    Q = torch.cat([enc([INSTRUCT + e["q"] for e in hp[i:i+128]]) for i in range(0, len(hp), 128)])

    short = lambda i: docs[i].replace("Music track: ", "").split(" | known for")[0][:96]
    rows = []
    for i, e in enumerate(hp):
        s = Q[i] @ DOC.t()
        gi = tidx[e["gt"]]
        rank = int((s > s[gi]).sum().item()) + 1
        top = torch.topk(s, 8).indices.tolist()
        rows.append((rank, e, gi, top))

    rows.sort(key=lambda r: r[0])
    bands = [("GOOD (GT in top-50)", [r for r in rows if r[0] <= 50]),
             ("MID (GT rank 100-1500)", [r for r in rows if 100 <= r[0] <= 1500]),
             ("DEEP (GT rank > 3000)", [r for r in rows if r[0] > 3000])]
    for name, band in bands:
        print(f"\n{'='*90}\n### {name}  (n={len(band)} of {len(hp)})\n{'='*90}", flush=True)
        step = max(1, len(band) // n_each)
        for rank, e, gi, top in band[::step][:n_each]:
            print(f"\nQUERY: {e['q'][:200]}", flush=True)
            print(f"  GT  (rank {rank}): {short(gi)}", flush=True)
            print(f"  TOP-8 retrieved:", flush=True)
            for r_, ti in enumerate(top, 1):
                mark = "  <-- GT" if ti == gi else ""
                print(f"    {r_}. {short(ti)}{mark}", flush=True)


@app.local_entrypoint()
def main():
    spotcheck.remote()
