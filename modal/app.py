"""
Modal cloud pipeline for Music CRS.

Volumes (create once):
    modal volume create music-crs-hf-cache
    modal volume create music-crs-results

Secret (.env in project root):
    HF_TOKEN=hf_...

Usage:
    # Smoke test (5 sessions)
    modal run modal/app.py::run_inference --num-sessions 5

    # Full devset
    modal run modal/app.py::run_inference --tid llama1b_bm25_devset --batch-size 16

    # Evaluate (after inference)
    modal run modal/app.py::run_evaluate --tid llama1b_bm25_devset
"""

import os
import modal

app = modal.App("music-crs")

hf_cache_vol = modal.Volume.from_name("music-crs-hf-cache", create_if_missing=True)
results_vol = modal.Volume.from_name("music-crs-results", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("uv")
    .copy_local_dir(
        ".",
        "/app",
        ignore=[".*", "__pycache__", "*.pyc", ".venv", "exp", "cache", "submission*", "evaluator"],
    )
    .run_commands("cd /app && uv pip install --system -e .")
)

EXP_DIR = "/root/exp"


@app.function(
    image=image,
    gpu=modal.gpu.A10G(),
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        EXP_DIR: results_vol,
    },
    secrets=[modal.Secret.from_dotenv()],
    timeout=7200,
)
def _inference(tid: str, batch_size: int, num_sessions: int):
    import subprocess
    import sys

    cmd = [
        sys.executable, "/app/run_inference_devset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
    ]
    if num_sessions > 0:
        cmd += ["--num_sessions", str(num_sessions)]

    env = os.environ.copy()
    env["EXP_DIR"] = EXP_DIR

    result = subprocess.run(cmd, cwd="/app", env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Inference failed with exit code {result.returncode}")

    results_vol.commit()
    print(f"Results saved to volume at inference/devset/{tid}.json")


@app.function(
    image=image,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        EXP_DIR: results_vol,
    },
    secrets=[modal.Secret.from_dotenv()],
    timeout=3600,
)
def _evaluate(tid: str, split: str) -> dict:
    import json
    import math

    import numpy as np
    from datasets import load_dataset

    pred_path = f"{EXP_DIR}/inference/{split}/{tid}.json"
    with open(pred_path) as f:
        raw = json.load(f)
    predictions = {(p["session_id"], p["turn_number"]): p["predicted_track_ids"] for p in raw}
    print(f"Loaded {len(raw):,} predictions from {pred_path}")

    hf_split = "test" if split == "devset" else split
    conv_ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split=hf_split)
    ground_truth = {
        (s["session_id"], t["turn_number"]): t["content"]
        for s in conv_ds
        for t in s["conversations"]
        if t["role"] == "music"
    }

    tracks_ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks")
    total_tracks = len(tracks_ds)

    def ndcg_at_k(predicted, gt, k):
        if not gt or not predicted:
            return 0.0
        for rank, track_id in enumerate(predicted[:k], start=1):
            if track_id == gt:
                return 1.0 / math.log2(rank + 1)
        return 0.0

    ndcg1_scores, ndcg10_scores, ndcg20_scores = [], [], []
    all_predicted_ids = set()

    for (sid, turn), ptids in predictions.items():
        gt = ground_truth.get((sid, turn))
        ndcg1_scores.append(ndcg_at_k(ptids, gt, 1))
        ndcg10_scores.append(ndcg_at_k(ptids, gt, 10))
        ndcg20_scores.append(ndcg_at_k(ptids, gt, 20))
        all_predicted_ids.update(ptids)

    scores = {
        "tid": tid,
        "split": split,
        "n_predictions": len(predictions),
        "NDCG@1": float(np.mean(ndcg1_scores)),
        "NDCG@10": float(np.mean(ndcg10_scores)),
        "NDCG@20": float(np.mean(ndcg20_scores)),
        "catalog_diversity": len(all_predicted_ids) / total_tracks,
    }

    scores_path = f"{EXP_DIR}/scores/{split}/{tid}.json"
    os.makedirs(os.path.dirname(scores_path), exist_ok=True)
    with open(scores_path, "w") as f:
        json.dump(scores, f, indent=2)

    results_vol.commit()
    return scores


@app.local_entrypoint()
def run_inference(
    tid: str = "llama1b_bm25_devset",
    batch_size: int = 16,
    num_sessions: int = 0,
):
    _inference.remote(tid=tid, batch_size=batch_size, num_sessions=num_sessions)


@app.local_entrypoint()
def run_evaluate(
    tid: str = "llama1b_bm25_devset",
    split: str = "devset",
):
    scores = _evaluate.remote(tid=tid, split=split)
    print(f"\n--- Results for {tid} ({split}) ---")
    for k, v in scores.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
    print(f"\nScores saved to volume at scores/{split}/{tid}.json")
