"""Targeted download of specific run-id shard artifacts from the music-crs-results volume.

Bypasses download_results.py's full-volume discovery (which was hanging) by reading exactly
the known remote paths. Streams each file chunk-by-chunk with progress.
"""
import sys
import time
from pathlib import Path

import modal

RESULTS_VOLUME = "music-crs-results"
RUN_ID = "20260606T232126Z-9d5571"
TID = "v0plus_compiler_all_retrievers_devset"
OUT = Path("exp/inference/devset")
OUT.mkdir(parents=True, exist_ok=True)

vol = modal.Volume.from_name(RESULTS_VOLUME)

names = []
for i in range(5):
    base = f"{TID}.run_{RUN_ID}.shard_{i}"
    names.append(f"{base}.json")
    names.append(f"{base}_trace.jsonl")

for name in names:
    remote = f"inference/devset/{name}"
    local = OUT / name
    part = local.with_suffix(local.suffix + ".part")
    t0 = time.time()
    n = 0
    try:
        with open(part, "wb") as fh:
            for chunk in vol.read_file(remote):
                fh.write(chunk)
                n += len(chunk)
        part.rename(local)
        print(f"OK  {name}  {n/1e6:.1f} MB  {time.time()-t0:.1f}s", flush=True)
    except Exception as exc:
        print(f"ERR {name}: {type(exc).__name__}: {exc}", flush=True)
        if part.exists():
            part.unlink()
        sys.exit(1)

print("DONE all 10 files", flush=True)
