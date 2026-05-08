"""
Batch inference script for Music CRS.
"""

import os
import json
import torch
import argparse
from mcrs import load_crs_baseline
from datasets import load_dataset
from tqdm import tqdm
from omegaconf import OmegaConf
from mcrs.inference_utils import chat_history_parser, resolve_qu_kwargs_placeholders


def _to_plain_dict(value):
    if value is None:
        return None
    return OmegaConf.to_container(value, resolve=True)


def main(args):
    """
    Run batch inference on TalkPlayData-2 test dataset.

    Args:
        args: Namespace object containing:
            - tid (str): Task/configuration identifier
            - batch_size (int): Batch size for inference
            - save_path (str): Output directory (currently unused)

    Returns:
        None. Results are saved to exp/inference/{tid}.json

    Processing:
        - Loads model configuration from config/{tid}.yaml
        - Processes all sessions × 8 turns in batches
        - Tracks progress with tqdm progress bar
        - Saves comprehensive results for evaluation
    """
    config = OmegaConf.load(f"config/{args.tid}.yaml")
    if args.clear_cache:
        cache_dir = config.get("cache_dir", "./cache")
        if os.path.exists(cache_dir):
            print(f"Clearing cache directory: {cache_dir}")
            import shutil
            shutil.rmtree(cache_dir)
    raw_qu_kwargs = config.get("qu_kwargs")
    if raw_qu_kwargs is None:
        qu_kwargs = {}
    elif OmegaConf.is_config(raw_qu_kwargs):
        qu_kwargs = OmegaConf.to_container(raw_qu_kwargs, resolve=True) or {}
    else:
        qu_kwargs = dict(raw_qu_kwargs)
    music_crs = load_crs_baseline(
        lm_type=config.lm_type,
        retrieval_type=config.retrieval_type,
        qu_type=config.get("qu_type", "passthrough"),
        pipeline_type=config.get("pipeline_type", "baseline"),
        planner_backend=config.get("planner_backend"),
        planner_model_name=config.get("planner_model_name"),
        qu_kwargs=resolve_qu_kwargs_placeholders(
            qu_kwargs,
            args.tid,
            args.exp_dir,
        ),
        item_db_name=config.item_db_name,
        user_db_name=config.user_db_name,
        track_split_types=config.track_split_types,
        user_split_types=config.user_split_types,
        corpus_types=config.corpus_types,
        cache_dir=config.cache_dir,
        device=config.device,
        attn_implementation=config.attn_implementation,
        dtype=getattr(torch, config.get("dtype", "bfloat16")),
        retrieval_topk=int(config.get("retrieval_topk", 20)),
        retrieval_config=_to_plain_dict(config.get("retrieval_config")),
        lm_kwargs=_to_plain_dict(config.get("lm_kwargs")),
        toolcalling_config=_to_plain_dict(config.get("toolcalling_config")),
    )
    db = load_dataset(config.test_dataset_name, split="test")
    # Prepare all batch data at once
    batch_data, metadata = [], []
    for item in db:
        user_id = item['user_id']
        session_id = item['session_id']
        turn_number = item["conversations"][-1]["turn_number"]
        chat_history, user_query = chat_history_parser(item["conversations"], music_crs, turn_number)
        batch_data.append({
            'user_query': user_query,
            'user_id': user_id,
            'session_memory': chat_history
        })
        metadata.append({
            'session_id': session_id,
            'user_id': user_id,
            'turn_number': turn_number
        })
    inference_results = []
    trace_rows = []
    for i in tqdm(range(0, len(batch_data), args.batch_size), desc="Batch inference"):
        batch = batch_data[i:i+args.batch_size]
        batch_metadata = metadata[i:i+args.batch_size]
        results = music_crs.batch_chat(batch)
        for j, result in enumerate(results):
            inference_results.append({
                "session_id": batch_metadata[j]['session_id'],
                "user_id": batch_metadata[j]['user_id'],
                "turn_number": batch_metadata[j]['turn_number'],
                "predicted_track_ids": result['retrieval_items'],
                "predicted_response": result["response"]
            })
            if result.get("tool_trace") is not None:
                trace_rows.append({
                    "session_id": batch_metadata[j]["session_id"],
                    "user_id": batch_metadata[j]["user_id"],
                    "turn_number": batch_metadata[j]["turn_number"],
                    "user_query": batch[j]["user_query"],
                    "tool_trace": result["tool_trace"],
                })
    os.makedirs(f"{args.exp_dir}/inference/{args.eval_dataset}", exist_ok=True)
    with open(f"{args.exp_dir}/inference/{args.eval_dataset}/{args.tid}.json", "w", encoding="utf-8") as f:
        json.dump(inference_results, f, ensure_ascii=False)
    if trace_rows:
        with open(f"{args.exp_dir}/inference/{args.eval_dataset}/{args.tid}_trace.json", "w", encoding="utf-8") as f:
            json.dump(trace_rows, f, ensure_ascii=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run batch inference on TalkPlayData-2 test dataset for Music CRS evaluation."
    )
    parser.add_argument(
        "--tid",
        type=str,
        default="llama1b_bm25_blindset_A",
        help="Task identifier matching a config file (e.g., 'llama1b_bm25' loads config/llama1b_bm25.yaml)"
    )
    parser.add_argument(
        "--eval_dataset",
        type=str,
        default="blindset_A",
        help="Evaluation dataset name"
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=16,
        help="Number of queries to process in parallel. Reduce if encountering GPU memory issues."
    )
    parser.add_argument(
        "--exp_dir",
        type=str,
        default="exp",
        help="Base directory for saving results (default: ./exp)"
    )
    parser.add_argument(
        "--clear_cache",
        action="store_true",
        default=False,
        help="Wipe the cache directory before running (forces re-indexing)"
    )
    args = parser.parse_args()
    main(args)
