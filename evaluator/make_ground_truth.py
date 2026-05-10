import os
import json
from typing import List, Dict, Any, Tuple
from pathlib import Path
import pandas as pd
import argparse
from datasets import load_dataset
from tqdm import tqdm

def parsing_groundtruth(conversations: List[Dict[str, Any]], target_turn_number: int) -> Tuple[str, str]:
    """
    Extract ground truth track ID and response from conversation data.
    Args:
        conversations: List of conversation dictionaries containing turn information
        target_turn_number: The specific turn number to extract data from
    Returns:
        Tuple containing:
            - recommend_music: The ground truth track ID
            - response: The ground truth response text
    """
    df_conversations = pd.DataFrame(conversations)
    df_current_turn = df_conversations[df_conversations['turn_number'] == target_turn_number]
    recommend_music = df_current_turn.iloc[1]['content']
    response = df_current_turn.iloc[2]['content']
    return recommend_music, response

def _resolve_exp_dir(exp_dir: str | Path | None) -> Path:
    if exp_dir is None:
        return Path("exp")
    return Path(exp_dir)


def make_ground_truth(dataset_name: str, split: str, exp_dir: str | Path = "exp"):
    db = load_dataset(dataset_name, split=split)
    ground_truth_tracks = []
    for item in tqdm(db):
        for target_turn_number in range(1, 9):
            gt_track_id, _ = parsing_groundtruth(item['conversations'], target_turn_number)
            ground_truth_tracks.append({
                "session_id": item["session_id"],
                "user_id": item["user_id"],
                "turn_number": target_turn_number,
                "ground_truth_track_id": gt_track_id,
            })
    output_dir = _resolve_exp_dir(exp_dir) / "ground_truth"
    os.makedirs(output_dir, exist_ok=True)
    with open(output_dir / "devset.json", "w") as f:
        json.dump(ground_truth_tracks, f, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", type=str, default="talkpl-ai/TalkPlayData-Challenge-Dataset")
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--exp_dir", type=str, default="exp")
    args = parser.parse_args()
    make_ground_truth(args.dataset_name, args.split, exp_dir=args.exp_dir)
