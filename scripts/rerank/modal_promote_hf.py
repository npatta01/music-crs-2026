"""Promote a fine-tuned checkpoint from the scout-models volume to a PRIVATE HF repo, cast to bf16.

Reads the (fp32) checkpoint from the `scout-models` volume, casts to bf16 (~halves the size, lossless
enough for a retriever), creates a PRIVATE HF model repo, uploads + tags `v1`, and prints the bf16
size + sha256 (record it in MODEL_REGISTRY.md). Uses the `huggingface` Modal secret's HF_TOKEN (needs
WRITE scope). No 16GB local download — the cast + push happen on Modal.

    modal run scripts/rerank/modal_promote_hf.py \
        --ckpt biencoder_variant_v_struct_pt_l2048 --repo-id music-recsys-2026-retriever-0.6b
"""
import modal

image = (modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.9.1", index_url="https://download.pytorch.org/whl/cu130")
    .pip_install("transformers>=4.51.0", "huggingface_hub", "hf_transfer", "safetensors")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"}))
app = modal.App("ckpt-promote", image=image)
model_vol = modal.Volume.from_name("scout-models")
hf_vol = modal.Volume.from_name("hf-cache", create_if_missing=True)

CARD = """---
license: apache-2.0
base_model: {base}
library_name: transformers
tags: [sentence-transformers, retrieval, music-recommendation, qwen3-embedding]
---

# {repo}

Fine-tuned **{base}** conversation→track retriever (b1), Issue #153. PRIVATE.

- Input (goal-free): `[prev] <prev turn> [now] <current turn> [prev_track] <just-played artist—title>`
- Recipe: variant-b MOVES-only (off-by-one-corrected labels), kf-dropout 0.3, n_hardneg 4, bs64,
  1 epoch, MNRL, last-token pool, max_len 2048.
- fp32 source-of-truth sha256: `{fp32_sha}` (Modal `scout-models` `/{ckpt}`).
- Eval (devset, corrected labels): r@100 = {r100}.
"""


@app.function(volumes={"/models": model_vol, "/root/.cache/huggingface": hf_vol},
              secrets=[modal.Secret.from_name("huggingface")], cpu=4.0, memory=49152, timeout=5400)
def promote(ckpt, repo_id, private=True, fp32_sha="", r100="", base="Qwen/Qwen3-Embedding-0.6B"):
    import os, glob, hashlib, shutil, torch
    from transformers import AutoModel, AutoTokenizer
    from huggingface_hub import HfApi, create_repo
    src = f"/models/{ckpt}"
    assert os.path.isdir(src), f"missing {src}"
    if "/" not in repo_id:                       # land in the token's own namespace, private
        from huggingface_hub import whoami
        repo_id = f"{whoami()['name']}/{repo_id}"
        print(f"[{ckpt}] resolved repo_id -> {repo_id}", flush=True)

    out = "/tmp/bf16"
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    print(f"[{ckpt}] loading + casting to bf16 ...", flush=True)
    tok = AutoTokenizer.from_pretrained(src)
    model = AutoModel.from_pretrained(src, dtype=torch.bfloat16)
    model.save_pretrained(out, safe_serialization=True, max_shard_size="20GB")  # keep a single .safetensors
    tok.save_pretrained(out)
    open(f"{out}/README.md", "w").write(
        CARD.format(base=base, repo=repo_id, ckpt=ckpt, fp32_sha=fp32_sha or "(see registry)", r100=r100 or "(see registry)"))

    shards = sorted(glob.glob(f"{out}/*.safetensors"))   # single file via max_shard_size; glob is belt-and-suspenders
    sz = sum(os.path.getsize(s) for s in shards)
    h = hashlib.sha256()
    for s in shards:                                     # sorted -> deterministic weight fingerprint
        with open(s, "rb") as f:
            for c in iter(lambda: f.read(8 << 20), b""):
                h.update(c)
    bf16_sha = h.hexdigest()

    print(f"[{ckpt}] creating private repo {repo_id} + uploading bf16 ({sz/1e9:.2f} GB) ...", flush=True)
    create_repo(repo_id, private=private, repo_type="model", exist_ok=True)
    api = HfApi()
    api.upload_folder(folder_path=out, repo_id=repo_id, repo_type="model",
                      commit_message=f"promote {ckpt} (bf16)")
    try:
        api.create_tag(repo_id, tag="v1", repo_type="model")
    except Exception as e:
        print(f"  tag v1 skipped: {repr(e)[:120]}", flush=True)

    print(f"\nPROMOTED {ckpt} -> https://huggingface.co/{repo_id}  (private={private})", flush=True)
    print(f"  bf16 weights: {sz/1e9:.2f} GB ({sz:,} bytes) over {len(shards)} shard(s)", flush=True)
    print(f"  bf16 sha256: {bf16_sha}", flush=True)
    return {"repo": repo_id, "bf16_bytes": sz, "bf16_sha256": bf16_sha}


@app.local_entrypoint()
def main(ckpt: str, repo_id: str, private: bool = True, fp32_sha: str = "", r100: str = "",
         base: str = "Qwen/Qwen3-Embedding-0.6B"):
    promote.remote(ckpt, repo_id, private, fp32_sha, r100, base)
