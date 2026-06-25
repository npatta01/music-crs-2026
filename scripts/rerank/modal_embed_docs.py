"""Modal: embed the 47k-doc corpus with a saved checkpoint -> docemb_<checkpoint>.npy on the
scout-models volume. Keeps the HEAVY doc embedding off the local box; the local feature A/B then
loads these (cache) and only embeds the ~6.6k queries.

    modal run scripts/rerank/modal_embed_docs.py
    modal volume get scout-models /docemb_biencoder_variant_baseline.npy ./
"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.9.1", index_url="https://download.pytorch.org/whl/cu130")
    .pip_install("transformers>=4.51.0", "numpy", "huggingface_hub", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}))
app = modal.App("scout-embeddocs", image=image)
data_vol = modal.Volume.from_name("biencoder-data", create_if_missing=True)
model_vol = modal.Volume.from_name("scout-models", create_if_missing=True)
hf_vol = modal.Volume.from_name("hf-cache", create_if_missing=True)


@app.function(gpu="H100", volumes={"/data": data_vol, "/models": model_vol,
              "/root/.cache/huggingface": hf_vol}, timeout=3600)
def embed(checkpoint, max_len=256):
    import json, numpy as np, torch
    from transformers import AutoModel, AutoTokenizer
    ck = checkpoint if "/" in checkpoint else f"/models/{checkpoint}"   # "/" => HF model id (e.g. base), else volume ckpt
    tok = AutoTokenizer.from_pretrained(ck, padding_side="left")
    model = AutoModel.from_pretrained(ck, dtype=torch.float32, attn_implementation="sdpa").cuda().eval()
    model.config.use_cache = False
    docs = [json.loads(l)["doc"] for l in open("/data/doc_corpus.jsonl")]

    def lastpool(h, m):
        if bool((m[:, -1].sum() == m.shape[0]).item()): return h[:, -1]
        i = m.sum(1) - 1; return h[torch.arange(h.shape[0], device=h.device), i]

    def enc(texts):
        b = tok(texts, padding=True, truncation=True, max_length=max_len, return_tensors="pt")
        b = {k: v.cuda() for k, v in b.items()}
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            o = model(**b)
        return torch.nn.functional.normalize(lastpool(o.last_hidden_state, b["attention_mask"]).float(), p=2, dim=1)

    V = torch.cat([enc(docs[i:i+256]) for i in range(0, len(docs), 256)]).cpu().numpy().astype("float32")
    name = checkpoint.replace("/", "_")   # HF ids contain "/" — sanitize for the save path
    np.save(f"/models/docemb_{name}.npy", V); model_vol.commit()
    print(f"[{checkpoint}] saved doc embeddings {V.shape} -> docemb_{name}.npy", flush=True)


@app.local_entrypoint()
def main(checkpoint: str = "biencoder_variant_baseline_l2048", max_len: int = 2048):
    # modal run scripts/rerank/modal_embed_docs.py --checkpoint <name> --max-len 2048
    embed.remote(checkpoint=checkpoint, max_len=max_len)
