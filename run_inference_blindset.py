"""
Batch inference script for Music CRS.
"""

import os
import re
import json
import time
import torch
import argparse
from mcrs import load_crs_baseline
from datasets import load_dataset
from tqdm import tqdm
from omegaconf import OmegaConf
from mcrs.inference_utils import chat_history_parser, resolve_qu_kwargs_placeholders
from run_inference_devset import (
    _add_elapsed,
    _add_timing_snapshot,
    _config_qu_kwargs,
    _print_timings,
    _resolve_vllm_endpoints_if_needed,
    _setup_litellm_cache,
    _setup_logging,
)


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


def _assert_eval_dataset_matches_config(eval_dataset: str, test_dataset_name: str) -> None:
    """Guard against writing predictions under a split that doesn't match the
    dataset the config actually loads.

    The dataset is selected solely by ``config.test_dataset_name`` (e.g.
    ``...-Blind-A``), while ``--eval_dataset`` only names the output directory and
    the packaged submission. If they reference different blind splits, the run
    would write Blind-A predictions into a ``blindset_B/`` folder and silently
    mislabel the submission. Catch that early, before the expensive model load.

    The check only fires when both names carry an unambiguous blind-split marker
    (``...Blind-X`` and ``blindset_Y``); otherwise it stays silent so unusual
    naming or future splits are not blocked.
    """
    ds_match = re.search(r"Blind[-_]?([A-Za-z0-9]+)$", test_dataset_name or "")
    ev_match = re.fullmatch(r"blindset_([A-Za-z0-9]+)", eval_dataset or "")
    if ds_match and ev_match and ds_match.group(1).lower() != ev_match.group(1).lower():
        raise ValueError(
            f"--eval_dataset='{eval_dataset}' does not match the config's "
            f"test_dataset_name='{test_dataset_name}' (blind split "
            f"'{ds_match.group(1)}' vs '{ev_match.group(1)}'). The dataset that "
            f"actually loads is fixed by the config; --eval_dataset only names the "
            f"output directory, so predictions would be written under the wrong "
            f"split and mislabel the submission. Fix --eval_dataset or the config."
        )


def _load_runtime(args) -> dict:
    _setup_logging()
    _setup_litellm_cache()
    timings: dict[str, float] = {}
    start = time.perf_counter()
    config = OmegaConf.load(f"configs/{args.tid}.yaml")
    _add_elapsed(timings, "load_config", start)
    _assert_eval_dataset_matches_config(
        args.eval_dataset, config.get("test_dataset_name", "")
    )
    if args.clear_cache:
        cache_dir = config.get("cache_dir", "./cache")
        if os.path.exists(cache_dir):
            print(f"Clearing cache directory: {cache_dir}")
            import shutil
            shutil.rmtree(cache_dir)

    start = time.perf_counter()
    qu_kwargs = _config_qu_kwargs(config)
    _resolve_vllm_endpoints_if_needed(qu_kwargs)
    music_crs = load_crs_baseline(
        lm_type=config.get("explanation_lm_type", "dummy"),
        retrieval_type=config.get("retrieval_type", "unused"),
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
        lm_kwargs=_to_plain_dict(config.get("explanation_lm_kwargs")),
        response_kwargs=_to_plain_dict(config.get("explanation_kwargs")),
    )
    _add_elapsed(timings, "load_crs", start)

    start = time.perf_counter()
    db = load_dataset(config.test_dataset_name, split="test")
    _add_elapsed(timings, "load_dataset", start)
    _print_timings(f"blindset startup tid={args.tid} split={args.eval_dataset}", timings)
    return {
        "config": config,
        "music_crs": music_crs,
        "db": db,
    }


def _select_shard(db, shard_id: int, num_shards: int):
    # Sharding kwargs were added later; programmatic callers (tests, Modal) may
    # not set them. Read defensively so the script stays backward-compatible.
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
    return db


def _build_batch_data(db, music_crs):
    batch_data, metadata = [], []
    for item in db:
        user_id = item['user_id']
        session_id = item['session_id']
        turn_number = item["conversations"][-1]["turn_number"]
        chat_history, user_query = chat_history_parser(item["conversations"], music_crs, turn_number)
        batch_data.append({
            'user_query': user_query,
            'user_id': user_id,
            'session_memory': chat_history,
            # raw dataset row for the online reranker's session-history block
            # (conversations keep RAW track ids; chat_history converts them to
            # metadata strings, which would zero those features)
            'session_meta': {
                'session_id': session_id,
                'turn_number': turn_number,
                'conversations': item['conversations'],
                'user_profile': item.get('user_profile'),
                'conversation_goal': item.get('conversation_goal'),
                'session_date': item.get('session_date'),
            },
        })
        metadata.append({
            'session_id': session_id,
            'user_id': user_id,
            'turn_number': turn_number
        })
    return batch_data, metadata


def _run_shard(args, runtime: dict, shard_id: int, num_shards: int, output_suffix: str) -> None:
    timings: dict[str, float] = {}
    start = time.perf_counter()
    db = _select_shard(runtime["db"], shard_id, num_shards)
    _add_elapsed(timings, "select_shard", start)

    start = time.perf_counter()
    music_crs = runtime["music_crs"]
    batch_data, metadata = _build_batch_data(db, music_crs)
    _add_elapsed(timings, "prepare_batches", start)

    os.makedirs(f"{args.exp_dir}/inference/{args.eval_dataset}", exist_ok=True)
    out_path = f"{args.exp_dir}/inference/{args.eval_dataset}/{args.tid}{output_suffix}.json"
    trace_path = (
        f"{args.exp_dir}/inference/{args.eval_dataset}/"
        f"{args.tid}{output_suffix}_trace.jsonl")
    inference_results = []
    saw_trace = False

    desc = f"Shard {shard_id}/{num_shards} inference" if num_shards > 1 else "Batch inference"
    with open(trace_path, "w", encoding="utf-8") as trace_file:
        for i in tqdm(range(0, len(batch_data), args.batch_size), desc=desc):
            batch = batch_data[i:i+args.batch_size]
            batch_metadata = metadata[i:i+args.batch_size]
            start = time.perf_counter()
            results = music_crs.batch_chat(batch)
            _add_elapsed(timings, "batch_chat", start)
            _add_timing_snapshot(
                timings,
                "batch_chat.",
                getattr(music_crs, "last_batch_timings", None),
            )

            start = time.perf_counter()
            for j, result in enumerate(results):
                inference_results.append({
                    "session_id": batch_metadata[j]['session_id'],
                    "user_id": batch_metadata[j]['user_id'],
                    "turn_number": batch_metadata[j]['turn_number'],
                    "predicted_track_ids": result['retrieval_items'],
                    "predicted_response": result["response"]
                })
                trace = result.get("trace")
                saw_trace = saw_trace or bool(trace)
                # V0PlusCompilerQU populates result["trace"] (per-branch pools,
                # state, resolver). Needed for reranker/debug runs.
                trace_file.write(json.dumps({
                    "session_id": batch_metadata[j]['session_id'],
                    "user_id": batch_metadata[j]['user_id'],
                    "turn_number": batch_metadata[j]['turn_number'],
                    "trace": trace,
                }, ensure_ascii=False, default=str) + "\n")
            trace_file.flush()
            _add_elapsed(timings, "trace_write", start)

    start = time.perf_counter()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(inference_results, f, ensure_ascii=False)
    _add_elapsed(timings, "write_predictions", start)
    if not saw_trace and os.path.exists(trace_path):
        os.remove(trace_path)
    _print_timings(
        f"blindset shard={shard_id}/{num_shards} sessions={len(db)} turns={len(batch_data)}",
        timings,
    )


def run_grouped(args, shard_ids, output_suffixes: dict[int, str] | None = None) -> None:
    """Run multiple logical shards after loading the CRS/runtime once."""
    runtime = _load_runtime(args)
    num_shards = getattr(args, "num_shards", 1)
    output_suffixes = output_suffixes or {}
    for shard_id in shard_ids:
        output_suffix = output_suffixes.get(shard_id, getattr(args, "output_suffix", ""))
        _run_shard(args, runtime, int(shard_id), num_shards, output_suffix)


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
    runtime = _load_runtime(args)
    num_shards = getattr(args, "num_shards", 1)
    shard_id = getattr(args, "shard_id", 0)
    output_suffix = getattr(args, "output_suffix", "")
    _run_shard(args, runtime, shard_id, num_shards, output_suffix)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run batch inference on TalkPlayData-2 test dataset for Music CRS evaluation."
    )
    parser.add_argument(
        "--tid",
        type=str,
        default="state_ranker_v10_lgbm_blindset_A",
        help="Task identifier matching a config file (e.g., 'state_ranker_v10_lgbm_blindset_A' loads configs/state_ranker_v10_lgbm_blindset_A.yaml)"
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
