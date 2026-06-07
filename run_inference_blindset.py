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
from run_inference_devset import _setup_logging, _setup_litellm_cache


def _to_plain_dict(value):
    if value is None:
        return None
    return OmegaConf.to_container(value, resolve=True)


def _encoder_has_vllm_endpoint(value) -> bool:
    return isinstance(value, dict) and bool(value.get("vllm_endpoint"))


def _qu_kwargs_has_vllm_endpoint(qu_kwargs: dict) -> bool:
    if _encoder_has_vllm_endpoint(qu_kwargs.get("encoder")):
        return True
    encoders = qu_kwargs.get("encoders")
    if not isinstance(encoders, dict):
        return False
    return any(_encoder_has_vllm_endpoint(value) for value in encoders.values())


def main(args):
    """
    Run batch inference on a blindset split of TalkPlayData-2.

    Args:
        args: Namespace object containing:
            - tid (str): Task/configuration identifier
            - eval_dataset (str): Evaluation dataset name (e.g. 'blindset_A')
            - batch_size (int): Batch size for inference
            - exp_dir (str): Base directory for saving results
            - clear_cache (bool): Wipe cache before running
            - num_shards (int): Total shards (1 = no sharding)
            - shard_id (int): 0-based shard index
            - output_suffix (str): Optional suffix appended to output filename

    Returns:
        None. Results are saved to {exp_dir}/inference/{eval_dataset}/{tid}{output_suffix}.json

    Processing:
        - Loads model configuration from configs/{tid}.yaml
        - Processes each session's final turn in batches
        - Tracks progress with tqdm progress bar
        - Saves comprehensive results for evaluation
    """
    _setup_logging()
    _setup_litellm_cache()
    config = OmegaConf.load(f"configs/{args.tid}.yaml")
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
    # Resolve logical vLLM endpoints into live Modal web URLs. No-op when absent;
    # only loads modal/vllm_serve.py (and Modal SDK) when a vllm_endpoint is
    # declared on either the legacy top-level encoder or a named encoder.
    if _qu_kwargs_has_vllm_endpoint(qu_kwargs):
        import importlib.util
        from pathlib import Path as _Path

        _vs_path = _Path(__file__).resolve().parent / "modal" / "vllm_serve.py"
        _vs_spec = importlib.util.spec_from_file_location("mcrs_vllm_serve", _vs_path)
        _vs_mod = importlib.util.module_from_spec(_vs_spec)
        _vs_spec.loader.exec_module(_vs_mod)
        _vs_mod.resolve_vllm_endpoints_in_qu_kwargs(qu_kwargs)
    music_crs = load_crs_baseline(
        lm_type=config.lm_type,
        retrieval_type=config.retrieval_type,
        qu_type=config.get("qu_type", "passthrough"),
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
    )
    db = load_dataset(config.test_dataset_name, split="test")
    # Sharding kwargs were added later; programmatic callers (tests, Modal) may
    # not set them. Read defensively so the script stays backward-compatible.
    num_shards = getattr(args, "num_shards", 1)
    shard_id = getattr(args, "shard_id", 0)
    if num_shards > 1:
        if not (0 <= shard_id < num_shards):
            raise ValueError(
                f"shard_id={shard_id} out of range for num_shards={num_shards}"
            )
        # Each blindset row IS one session — contiguous index slicing partitions
        # the session list. Turn selection (last turn) happens below, after the
        # partition, so a session's turns never split across shards.
        total = len(db)
        start = (shard_id * total) // num_shards
        end = ((shard_id + 1) * total) // num_shards
        db = db.select(range(start, end))
        print(f"Shard {shard_id}/{num_shards}: {len(db)} sessions "
              f"(indices [{start}, {end}))")
    # Prepare all batch data at once
    from mcrs.rerank.session_meta import flatten_session_row
    batch_data, metadata = [], []
    for item in db:
        user_id = item['user_id']
        session_id = item['session_id']
        turn_number = item["conversations"][-1]["turn_number"]
        chat_history, user_query = chat_history_parser(item["conversations"], music_crs, turn_number)
        # Session-level context for the reranker's block-U features (serve-time, non-NaN).
        session_context = {
            'user_profile': item.get('user_profile'),
            'conversation_goal': item.get('conversation_goal'),
            'session_date': item.get('session_date'),
        }
        batch_data.append({
            'user_query': user_query,
            'user_id': user_id,
            'session_memory': chat_history,
            'session_context': session_context,
        })
        metadata.append({
            'session_id': session_id,
            'user_id': user_id,
            'turn_number': turn_number,
            'session_meta': flatten_session_row(session_context),
        })
    inference_results = []
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
    output_suffix = getattr(args, "output_suffix", "")
    os.makedirs(f"{args.exp_dir}/inference/{args.eval_dataset}", exist_ok=True)
    out_path = f"{args.exp_dir}/inference/{args.eval_dataset}/{args.tid}{output_suffix}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(inference_results, f, ensure_ascii=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run batch inference on TalkPlayData-2 test dataset for Music CRS evaluation."
    )
    parser.add_argument(
        "--tid",
        type=str,
        default="v0plus_compiler_blindset_A",
        help="Task identifier matching a config file (e.g., 'v0plus_compiler_blindset_A' loads configs/v0plus_compiler_blindset_A.yaml)"
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
    parser.add_argument(
        "--num_shards",
        type=int,
        default=1,
        help="Total number of shards. >1 enables sharded mode (must pair with --shard_id).",
    )
    parser.add_argument(
        "--shard_id",
        type=int,
        default=0,
        help="0-based shard index. Only this shard's slice of sessions is processed.",
    )
    parser.add_argument(
        "--output_suffix",
        type=str,
        default="",
        help="Optional suffix appended to the output filename "
             "(e.g. '.run_RID.shard_3' -> '{tid}.run_RID.shard_3.json').",
    )
    args = parser.parse_args()
    main(args)
