"""
Batch inference script for Music CRS.
"""

import os
import json
import logging
import shutil
import torch
import argparse
from mcrs import load_crs_baseline
from datasets import load_dataset
from tqdm import tqdm
from omegaconf import OmegaConf
from mcrs.inference_utils import chat_history_parser, resolve_qu_kwargs_placeholders


def _setup_logging() -> None:
    """Surface logger.warning/info calls from mcrs.* in stderr.

    Without basicConfig, Python's last-resort handler writes WARNING+ to
    stderr but with no timestamp/level prefix, and INFO is dropped. That
    let v0+ extractor failures and empty-compile cases vanish silently in
    Modal logs. Configure once at startup so all submodules surface.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,  # override any prior config (e.g., from imported libs)
    )
    # Quiet the chatty libraries — we only care about our own warnings here.
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _to_plain_dict(value):
    if value is None:
        return None
    return OmegaConf.to_container(value, resolve=True)


def _setup_litellm_cache() -> None:
    """Configure LiteLLM cache when MCRS_LITELLM_CACHE_DIR is set.

    The Modal inference container sets this env var to the path of the shared
    litellm-cache volume (same volume used by ModalLiteLLMService).  Caching
    here means repeated LLM extraction calls on identical conversations are
    served locally — no OpenRouter round-trip, no cost.
    """
    from mcrs.litellm_cache import setup_litellm_cache

    cache_dir = os.environ.get("MCRS_LITELLM_CACHE_DIR")
    if setup_litellm_cache(cache_dir=cache_dir):
        backend = os.environ.get("MCRS_LITELLM_CACHE_BACKEND", "file")
        print(f"LiteLLM {backend} cache enabled at: {cache_dir}")


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
        - Loads model configuration from configs/{tid}.yaml
        - Processes all sessions × 8 turns in batches
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
    if args.session_ids_file is not None:
        with open(args.session_ids_file) as f:
            keep = set(json.load(f)["session_ids"])
        db = db.filter(lambda x: x["session_id"] in keep)
    if args.num_sessions > 0:
        import random
        n = min(args.num_sessions, len(db))
        db = db.select(random.sample(range(len(db)), n))
        print(f"Running on {n} randomly sampled sessions.")
    # Sharding kwargs were added later; programmatic callers (e.g. tests using
    # SimpleNamespace) may not set them. Read defensively so the script stays
    # backward-compatible with the pre-sharding arg surface.
    num_shards = getattr(args, "num_shards", 1)
    shard_id = getattr(args, "shard_id", 0)
    if num_shards > 1:
        if args.num_sessions > 0:
            # Both knobs together would silently overlap: each shard process
            # independently random-samples N sessions (no seed), then slices
            # its window out of THAT random pool — so shards work on different
            # random samples of the corpus, not a single partition. The
            # documented sharded entry point (modal/app.py::run_inference_sharded)
            # always passes num_sessions=0, so this only fires for direct CLI
            # callers who combine both flags.
            raise ValueError(
                "Cannot combine --num_sessions > 0 with --num_shards > 1: "
                "each shard would independently random-sample the corpus, "
                "producing overlapping pools rather than a clean partition. "
                "Use --num_sessions for quick smoke tests OR --num_shards for "
                "parallel full-devset runs, not both."
            )
        if not (0 <= shard_id < num_shards):
            raise ValueError(
                f"shard_id={shard_id} out of range for num_shards={num_shards}"
            )
        # Contiguous slicing: shard k gets session indices [k*N/S, (k+1)*N/S).
        total = len(db)
        start = (shard_id * total) // num_shards
        end   = ((shard_id + 1) * total) // num_shards
        db = db.select(range(start, end))
        print(f"Shard {shard_id}/{num_shards}: {len(db)} sessions "
              f"(indices [{start}, {end}))")
    # Prepare all batch data at once
    batch_data, metadata = [], []
    for item in db:
        user_id = item['user_id']
        session_id = item['session_id']
        for target_turn_number in range(1, 9):
            chat_history, user_query = chat_history_parser(item['conversations'], music_crs, target_turn_number)
            batch_data.append({
                'user_query': user_query,
                'user_id': user_id,
                'session_memory': chat_history
            })
            metadata.append({
                'session_id': session_id,
                'user_id': user_id,
                'turn_number': target_turn_number
            })
    inference_results = []
    trace_results = []
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
            # V0PlusCompilerQU populates `result["trace"]`; other QUs leave it
            # as None. Save in a sibling file so the main predictions JSON
            # stays small and easy to diff between runs.
            trace_results.append({
                "session_id": batch_metadata[j]['session_id'],
                "user_id": batch_metadata[j]['user_id'],
                "turn_number": batch_metadata[j]['turn_number'],
                "trace": result.get("trace"),
            })
    os.makedirs(f"{args.exp_dir}/inference/devset", exist_ok=True)
    # `output_suffix` is sharding-time metadata; programmatic callers may not set it.
    output_suffix = getattr(args, "output_suffix", "")
    out_path = f"{args.exp_dir}/inference/devset/{args.tid}{output_suffix}.json"
    # Trace sidecar — JSONL (one record per line) so it streams/diffs cheaply
    # and shards concatenate by appending lines. `default=str` handles
    # datetime.date fields inside the extracted v0+ state's hard_filters.start/end
    # without a custom encoder.
    trace_path = f"{args.exp_dir}/inference/devset/{args.tid}{output_suffix}_trace.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(inference_results, f, ensure_ascii=False)
    with open(trace_path, "w", encoding="utf-8") as f:
        for record in trace_results:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run batch inference on TalkPlayData-2 test dataset for Music CRS evaluation."
    )
    parser.add_argument(
        "--tid",
        type=str,
        default="v0plus_compiler_image_devset",
        help="Task identifier matching a config file (e.g., 'v0plus_compiler_image_devset' loads configs/v0plus_compiler_image_devset.yaml)"
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=16,
        help="Number of queries to process in parallel. Reduce if encountering GPU memory issues."
    )
    parser.add_argument(
        "--session_ids_file",
        type=str,
        default=None,
        help="Path to JSON file with session_ids list (e.g. data/local_eval_split.json)"
    )
    parser.add_argument(
        "--num_sessions",
        type=int,
        default=0,
        help="Randomly sample N sessions for a quick smoke test (0 = all sessions)"
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
        help="Optional suffix appended to the output filenames "
             "(e.g. '.shard_3' -> '{tid}.shard_3.json'). Empty = '{tid}.json'.",
    )
    args = parser.parse_args()
    main(args)
