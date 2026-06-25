"""Print exact size + sha256 of fine-tuned checkpoints on the scout-models volume (for promotion)."""
import modal

app = modal.App("ckpt-info", image=modal.Image.debian_slim(python_version="3.12"))
model_vol = modal.Volume.from_name("scout-models")
CKPTS = [
    "biencoder_variant_v_struct_pt_l2048",
    "biencoder_variant_v_struct_pt_l2048_qwen3-embedding-4b",
    "biencoder_variant_baseline_l2048",
    "biencoder_variant_baseline_l2048_qwen3-embedding-4b",
]


@app.function(volumes={"/models": model_vol}, timeout=1800)
def info():
    import os, hashlib
    for ck in CKPTS:
        d = f"/models/{ck}"
        if not os.path.isdir(d):
            print(f"\n=== {ck} === MISSING", flush=True); continue
        total = 0; st_size = 0; st_sha = ""
        for f in sorted(os.listdir(d)):
            fp = os.path.join(d, f)
            if not os.path.isfile(fp):
                continue
            sz = os.path.getsize(fp); total += sz
            if f == "model.safetensors":
                st_size = sz
                h = hashlib.sha256()
                with open(fp, "rb") as fh:
                    for chunk in iter(lambda: fh.read(8 << 20), b""):
                        h.update(chunk)
                st_sha = h.hexdigest()
        print(f"\n=== {ck} ===", flush=True)
        print(f"  total dir         : {total/1e9:.2f} GB ({total:,} bytes)", flush=True)
        print(f"  model.safetensors : {st_size/1e9:.2f} GB ({st_size:,} bytes)", flush=True)
        print(f"  sha256            : {st_sha}", flush=True)


@app.local_entrypoint()
def main():
    info.remote()
