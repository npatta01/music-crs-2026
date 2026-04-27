import os
import json
from typing import List, Dict, Any, Tuple
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

def make_ground_truth(dataset_name: str, split: str):
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
    os.makedirs(f"exp/ground_truth", exist_ok=True)
    with open(f"exp/ground_truth/devset.json", "w") as f:
        json.dump(ground_truth_tracks, f, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", type=str, default="talkpl-ai/TalkPlayData-Challenge-Dataset")
    parser.add_argument("--split", type=str, default="test")
    args = parser.parse_args()
    make_ground_truth(args.dataset_name, args.split)
