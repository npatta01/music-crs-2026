"""Print exact size + sha256 of fine-tuned checkpoints on the scout-models volume (for promotion)."""
import modal

app = modal.App("ckpt-info", image=modal.Image.debian_slim(python_version="3.12"))
model_vol = modal.Volume.from_name("scout-models")
CKPTS = [
    "biencoder_variant_v_struct_pt_l2048_qwen3-embedding-4b",
    "biencoder_variant_baseline_l2048",
    "biencoder_variant_baseline_l2048_qwen3-embedding-4b",
]


@app.function(volumes={"/models": model_vol}, timeout=1800)
def info():
    import os, glob, hashlib
    for ck in CKPTS:
        d = f"/models/{ck}"
        if not os.path.isdir(d):
            print(f"\n=== {ck} === MISSING", flush=True); continue
        total = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)
                    if os.path.isfile(os.path.join(d, f)))
        shards = sorted(glob.glob(os.path.join(d, "*.safetensors")))   # handles sharded saves
        st_size = sum(os.path.getsize(s) for s in shards)
        h = hashlib.sha256()
        for s in shards:                       # sorted -> deterministic weight fingerprint
            with open(s, "rb") as fh:
                for chunk in iter(lambda: fh.read(8 << 20), b""):
                    h.update(chunk)
        st_sha = h.hexdigest() if shards else "(no safetensors)"
        print(f"\n=== {ck} ===", flush=True)
        print(f"  total dir : {total/1e9:.2f} GB ({total:,} bytes)", flush=True)
        print(f"  weights   : {st_size/1e9:.2f} GB ({st_size:,} bytes) over {len(shards)} shard(s)", flush=True)
        print(f"  sha256    : {st_sha}", flush=True)


@app.local_entrypoint()
def main():
    info.remote()
