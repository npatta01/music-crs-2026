"""
Creates a difficulty-stratified local eval split from the devset.

Difficulty proxy: mean popularity of ground-truth tracks across all 8 turns in a session.
High popularity = easy (BM25 can retrieve popular/mainstream tracks more easily).

Output: data/local_eval_split.json
"""

import argparse
import json
import os
import random
from collections import defaultdict

from datasets import load_dataset


def main(args):
    print("Loading devset...")
    devset = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")

    print("Loading track metadata...")
    track_meta = load_dataset("talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks")
    popularity = {row["track_id"]: row["popularity"] for row in track_meta}

    print("Scoring sessions by difficulty...")
    session_scores = []
    for item in devset:
        gt_track_ids = [
            turn["content"]
            for turn in item["conversations"]
            if turn["role"] == "music"
        ]
        pops = [popularity.get(tid, 0.0) for tid in gt_track_ids]
        mean_pop = sum(pops) / len(pops) if pops else 0.0
        session_scores.append((item["session_id"], mean_pop))

    session_scores.sort(key=lambda x: x[1], reverse=True)
    n = len(session_scores)
    tier_size = n // 3

    tiers = {
        "easy":   session_scores[:tier_size],
        "medium": session_scores[tier_size: 2 * tier_size],
        "hard":   session_scores[2 * tier_size:],
    }

    rng = random.Random(args.seed)
    sampled_ids = []
    session_meta = {}

    for tier, sessions in tiers.items():
        chosen = rng.sample(sessions, min(args.n_per_tier, len(sessions)))
        for sid, pop in chosen:
            sampled_ids.append(sid)
            session_meta[sid] = {"difficulty": tier, "mean_popularity": round(pop, 4)}

    result = {"session_ids": sampled_ids, "session_meta": session_meta}

    os.makedirs("data", exist_ok=True)
    out_path = args.output
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    counts = defaultdict(int)
    for v in session_meta.values():
        counts[v["difficulty"]] += 1
    print(f"Saved {len(sampled_ids)} sessions to {out_path}")
    for tier in ("easy", "medium", "hard"):
        print(f"  {tier}: {counts[tier]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create difficulty-stratified local eval split.")
    parser.add_argument("--n_per_tier", type=int, default=3, help="Sessions per difficulty tier")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="data/local_eval_split.json")
    main(parser.parse_args())
