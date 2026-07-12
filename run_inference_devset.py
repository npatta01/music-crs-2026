"""
Batch inference script for Music CRS.
"""

import os
import json
import hashlib
import logging
import shutil
import subprocess
import time
import torch
import argparse
from mcrs import load_crs_baseline
from datasets import load_dataset
from tqdm import tqdm
from omegaconf import OmegaConf
from mcrs.inference_utils import chat_history_parser, resolve_qu_kwargs_placeholders


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(os.getcwd(), ".env"))
    except Exception:
        pass


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


def _encoder_has_vllm_endpoint(value) -> bool:
    return isinstance(value, dict) and bool(value.get("vllm_endpoint"))


def _qu_kwargs_has_vllm_endpoint(qu_kwargs: dict) -> bool:
    if _encoder_has_vllm_endpoint(qu_kwargs.get("encoder")):
        return True
    encoders = qu_kwargs.get("encoders")
    if not isinstance(encoders, dict):
        return False
    return any(_encoder_has_vllm_endpoint(value) for value in encoders.values())


def _config_hash(config) -> str | None:
    try:
        plain = OmegaConf.to_container(config, resolve=True)
    except Exception:
        return None
    encoded = json.dumps(plain, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _build_trace_run_metadata(tid: str, config) -> dict:
    return {
        "tid": tid,
        "git_sha": _git_sha(),
        "config_hash": _config_hash(config),
    }


def _with_trace_run_metadata(trace, run_metadata: dict):
    if isinstance(trace, dict):
        trace = dict(trace)
        trace["run"] = dict(run_metadata)
    return trace


def _setup_litellm_cache(*, require: bool = False) -> bool:
    """Configure LiteLLM cache when MCRS_LITELLM_CACHE_DIR is set.

    The Modal inference container sets this env var to the path of the shared
    litellm-cache volume (same volume used by ModalLiteLLMService).  Caching
    here means repeated LLM extraction calls on identical conversations are
    served locally — no OpenRouter round-trip, no cost.
    """
    from mcrs.litellm_cache import setup_litellm_cache

    cache_dir = os.environ.get("MCRS_LITELLM_CACHE_DIR")
    enabled = setup_litellm_cache(cache_dir=cache_dir)
    if enabled:
        backend = os.environ.get("MCRS_LITELLM_CACHE_BACKEND", "file")
        print(f"LiteLLM {backend} cache enabled at: {cache_dir}")
        return True
    if require:
        raise RuntimeError(
            "MCRS_LITELLM_CACHE_DIR must be set for configs with a LiteLLM "
            "state extractor. Source .env or export MCRS_LITELLM_CACHE_DIR="
            "cache/litellm-state before running."
        )
    return False


def _truthy_env(name: str) -> bool:
    value = os.environ.get(name)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _config_requires_litellm_cache(config, qu_kwargs: dict) -> bool:
    if str(config.get("qu_type", "")) != "state_ranker":
        return False
    extractor = qu_kwargs.get("extractor")
    return isinstance(extractor, dict) and bool(extractor.get("model_name"))


def _litellm_cache_required(args, config, qu_kwargs: dict) -> bool:
    if getattr(args, "allow_uncached_litellm", False):
        return False
    if getattr(args, "require_litellm_cache", False):
        return True
    if _truthy_env("MCRS_REQUIRE_LITELLM_CACHE"):
        return True
    return _config_requires_litellm_cache(config, qu_kwargs)


def _add_elapsed(timings: dict[str, float], key: str, start: float) -> None:
    timings[key] = timings.get(key, 0.0) + (time.perf_counter() - start)


def _flush_runtime_caches(runtime: dict, timings: dict[str, float]) -> None:
    flush = getattr(runtime.get("music_crs"), "flush_caches", None)
    if not callable(flush):
        return
    start = time.perf_counter()
    flush()
    _add_elapsed(timings, "flush_caches", start)


def _print_timings(label: str, timings: dict[str, float]) -> None:
    body = " ".join(f"{key}={value:.2f}s" for key, value in timings.items())
    print(f"[timing] {label} {body}", flush=True)


def _add_timing_snapshot(
    timings: dict[str, float],
    prefix: str,
    snapshot: dict | None,
) -> None:
    if not isinstance(snapshot, dict):
        return
    for key, value in snapshot.items():
        if isinstance(value, (int, float)):
            timings[f"{prefix}{key}"] = timings.get(f"{prefix}{key}", 0.0) + float(value)


def _config_qu_kwargs(config) -> dict:
    raw_qu_kwargs = config.get("qu_kwargs")
    if raw_qu_kwargs is None:
        return {}
    if OmegaConf.is_config(raw_qu_kwargs):
        return OmegaConf.to_container(raw_qu_kwargs, resolve=True) or {}
    return dict(raw_qu_kwargs)


def _resolve_vllm_endpoints_if_needed(qu_kwargs: dict) -> None:
    # Resolve logical vLLM endpoints into live Modal web URLs. No-op when absent;
    # only loads modal/vllm_serve.py (and Modal SDK) when a vllm_endpoint is
    # declared on either the legacy top-level encoder or a named encoder.
    if not _qu_kwargs_has_vllm_endpoint(qu_kwargs):
        return
    if os.environ.get("MCRS_LAZY_VLLM_ENDPOINT", "1") != "0":
        # Default: leave `vllm_endpoint` in place so LiteLLMEmbeddingClient
        # resolves it lazily on the first genuine cache miss instead of here,
        # eagerly, before any cache is even checked. Set
        # MCRS_LAZY_VLLM_ENDPOINT=0 to force eager resolution up front.
        return
    import importlib.util
    from pathlib import Path as _Path

    _vs_path = _Path(__file__).resolve().parent / "modal" / "vllm_serve.py"
    _vs_spec = importlib.util.spec_from_file_location("mcrs_vllm_serve", _vs_path)
    _vs_mod = importlib.util.module_from_spec(_vs_spec)
    _vs_spec.loader.exec_module(_vs_mod)
    _vs_mod.resolve_vllm_endpoints_in_qu_kwargs(qu_kwargs)


def _load_runtime(args) -> dict:
    _load_dotenv()
    _setup_logging()
    timings: dict[str, float] = {}
    start = time.perf_counter()
    config = OmegaConf.load(f"configs/{args.tid}.yaml")
    trace_run_metadata = _build_trace_run_metadata(args.tid, config)
    _add_elapsed(timings, "load_config", start)
    qu_kwargs = _config_qu_kwargs(config)
    if args.clear_cache:
        cache_dir = config.get("cache_dir", "./cache")
        if os.path.exists(cache_dir):
            print(f"Clearing cache directory: {cache_dir}")
            shutil.rmtree(cache_dir)
    litellm_cache_required = _litellm_cache_required(args, config, qu_kwargs)
    litellm_cache_enabled = _setup_litellm_cache(require=litellm_cache_required)
    if litellm_cache_required and not litellm_cache_enabled:
        raise RuntimeError(
            "MCRS_LITELLM_CACHE_DIR must be set for configs with a LiteLLM "
            "state extractor. Source .env or export MCRS_LITELLM_CACHE_DIR="
            "cache/litellm-state before running."
        )

    start = time.perf_counter()
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
    if getattr(args, "session_ids_file", None) is not None:
        with open(args.session_ids_file) as f:
            keep = set(json.load(f)["session_ids"])
        db = db.filter(lambda x: x["session_id"] in keep)
    if getattr(args, "num_sessions", 0) > 0:
        import random
        n = min(args.num_sessions, len(db))
        db = db.select(random.sample(range(len(db)), n))
        print(f"Running on {n} randomly sampled sessions.")
    _add_elapsed(timings, "load_dataset", start)
    _print_timings(f"devset startup tid={args.tid}", timings)
    return {
        "config": config,
        "music_crs": music_crs,
        "db": db,
        "trace_run_metadata": trace_run_metadata,
    }


def _select_shard(db, args, shard_id: int, num_shards: int):
    # Sharding kwargs were added later; programmatic callers (e.g. tests using
    # SimpleNamespace) may not set them. Read defensively so the script stays
    # backward-compatible with the pre-sharding arg surface.
    if num_shards > 1:
        if getattr(args, "num_sessions", 0) > 0:
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
    return db


def _build_batch_data(db, music_crs):
    batch_data, metadata = [], []
    for item in db:
        user_id = item['user_id']
        session_id = item['session_id']
        for target_turn_number in range(1, 9):
            chat_history, user_query = chat_history_parser(item['conversations'], music_crs, target_turn_number)
            batch_data.append({
                'user_query': user_query,
                'user_id': user_id,
                'session_memory': chat_history,
                # raw dataset row for the online reranker's session-history
                # block (raw track ids; chat_history holds metadata strings)
                'session_meta': {
                    'session_id': session_id,
                    'turn_number': target_turn_number,
                    'conversations': item['conversations'],
                    'user_profile': item.get('user_profile'),
                    'conversation_goal': item.get('conversation_goal'),
                    'session_date': item.get('session_date'),
                },
            })
            metadata.append({
                'session_id': session_id,
                'user_id': user_id,
                'turn_number': target_turn_number
            })
    return batch_data, metadata


def _run_shard(args, runtime: dict, shard_id: int, num_shards: int, output_suffix: str) -> None:
    timings: dict[str, float] = {}
    start = time.perf_counter()
    db = _select_shard(runtime["db"], args, shard_id, num_shards)
    _add_elapsed(timings, "select_shard", start)

    start = time.perf_counter()
    music_crs = runtime["music_crs"]
    batch_data, metadata = _build_batch_data(db, music_crs)
    _add_elapsed(timings, "prepare_batches", start)

    os.makedirs(f"{args.exp_dir}/inference/devset", exist_ok=True)
    out_path = f"{args.exp_dir}/inference/devset/{args.tid}{output_suffix}.json"
    # Trace sidecar — JSONL (one record per line) so it streams/diffs cheaply
    # and shards concatenate by appending lines. `default=str` handles
    # datetime.date fields inside the extracted v0+ state's hard_filters.start/end
    # without a custom encoder.
    trace_path = f"{args.exp_dir}/inference/devset/{args.tid}{output_suffix}_trace.jsonl"
    inference_results = []
    trace_records = 0

    desc = f"Shard {shard_id}/{num_shards} inference" if num_shards > 1 else "Batch inference"
    try:
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
                    # V0PlusCompilerQU populates `result["trace"]`; other QUs leave
                    # it as None. Save in a sibling file so the main predictions JSON
                    # stays small and easy to diff between runs.
                    trace_record = {
                        "session_id": batch_metadata[j]['session_id'],
                        "user_id": batch_metadata[j]['user_id'],
                        "turn_number": batch_metadata[j]['turn_number'],
                        "trace": _with_trace_run_metadata(
                            result.get("trace"),
                            runtime["trace_run_metadata"],
                        ),
                    }
                    trace_file.write(json.dumps(trace_record, ensure_ascii=False, default=str) + "\n")
                    trace_records += 1
                trace_file.flush()
                _add_elapsed(timings, "trace_write", start)
    finally:
        _flush_runtime_caches(runtime, timings)

    start = time.perf_counter()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(inference_results, f, ensure_ascii=False)
    _add_elapsed(timings, "write_predictions", start)
    complete_path = f"{args.exp_dir}/inference/devset/{args.tid}{output_suffix}_complete.json"
    with open(complete_path, "w", encoding="utf-8") as f:
        json.dump(
            _completion_marker_payload(
                args,
                shard_id=shard_id,
                num_shards=num_shards,
                output_suffix=output_suffix,
                prediction_count=len(inference_results),
                trace_records=trace_records,
                out_path=out_path,
                trace_path=trace_path,
            ),
            f,
            indent=2,
        )
    _print_timings(
        f"devset shard={shard_id}/{num_shards} sessions={len(db)} turns={len(batch_data)}",
        timings,
    )


def run_grouped(args, shard_ids, output_suffixes: dict[int, str] | None = None) -> None:
    """Run multiple logical shards after loading the CRS/runtime once."""
    runtime = _load_runtime(args)
    num_shards = getattr(args, "num_shards", 1)
    output_suffixes = output_suffixes or {}
    base_output_suffix = getattr(args, "output_suffix", "")
    if len(shard_ids) > 1 and num_shards <= 1 and not base_output_suffix and not output_suffixes:
        raise ValueError(
            "Grouped local inference with multiple --shard_ids requires --num_shards > 1 "
            "or explicit output suffixes to avoid overwriting outputs."
        )
    for shard_id in shard_ids:
        output_suffix = output_suffixes.get(shard_id)
        if output_suffix is None:
            output_suffix = (
                f"{base_output_suffix}.shard_{shard_id}"
                if len(shard_ids) > 1 and base_output_suffix
                else (f".shard_{shard_id}" if num_shards > 1 else base_output_suffix)
            )
        _run_shard(args, runtime, int(shard_id), num_shards, output_suffix)


def _parse_shard_ids(value) -> list[int]:
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        return [int(part.strip()) for part in value.split(",") if part.strip()]
    return [int(part) for part in value]


def _parse_output_suffixes_json(value) -> dict[int, str]:
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("--output_suffixes_json must be a JSON object")
    return {int(shard_id): str(suffix) for shard_id, suffix in value.items()}


def _completion_marker_payload(
    args,
    *,
    shard_id: int,
    num_shards: int,
    output_suffix: str,
    prediction_count: int,
    trace_records: int,
    out_path: str,
    trace_path: str,
) -> dict:
    return {
        "tid": args.tid,
        "shard_id": shard_id,
        "num_shards": num_shards,
        "output_suffix": output_suffix,
        "predictions": prediction_count,
        "trace_records": trace_records,
        "prediction_path": os.path.basename(out_path),
        "trace_path": os.path.basename(trace_path),
    }


def main(args):
    """
    Run batch inference on the devset (TalkPlayData-2 test) split.

    Args:
        args: Namespace object containing:
            - tid (str): Task/configuration identifier
            - batch_size (int): Batch size for inference
            - session_ids_file (str | None): Optional explicit session subset
            - num_sessions (int): Optional random-sample size for a smoke test (0 = all)
            - exp_dir (str): Base directory for saving results (default 'exp')
            - clear_cache (bool): Wipe the cache directory before running
            - shard_ids (str | None): If set, dispatches to run_grouped() for a
              multi-shard batch instead of running a single shard below --
              programmatic/Modal-only, not exposed by build_parser()
            - num_shards / shard_id / output_suffix: single-shard sharding,
              read with getattr defaults so callers (tests, Modal) that omit
              them still work

    Returns:
        None. Results are saved to {exp_dir}/inference/devset/{tid}{output_suffix}.json

    Processing:
        - Loads model configuration from configs/{tid}.yaml
        - Processes every session's 8 turns (turn_number 1-8, hardcoded) in batches
        - Tracks progress with tqdm progress bar
        - Saves comprehensive results for evaluation
    """
    shard_ids = _parse_shard_ids(getattr(args, "shard_ids", None))
    if shard_ids:
        run_grouped(
            args,
            shard_ids=shard_ids,
            output_suffixes=_parse_output_suffixes_json(
                getattr(args, "output_suffixes_json", None)
            ),
        )
        return

    runtime = _load_runtime(args)
    num_shards = getattr(args, "num_shards", 1)
    shard_id = getattr(args, "shard_id", 0)
    output_suffix = getattr(args, "output_suffix", "")
    _run_shard(args, runtime, shard_id, num_shards, output_suffix)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run batch inference on TalkPlayData-2 test dataset for Music CRS evaluation."
    )
    parser.add_argument(
        "--tid",
        type=str,
        default="state_ranker_v10_lgbm_devset",
        help=(
            "Task identifier matching a config file. Defaults to the v10 LGBM "
            "devset config; use 'state_ranker_v10_rrf_devset' for the explicit "
            "RRF/candidate-fusion baseline."
        )
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
        "--allow_uncached_litellm",
        action="store_true",
        default=False,
        help=(
            "Allow state-ranker LiteLLM extraction without a configured cache. "
            "Intended only for tiny debug runs."
        ),
    )
    parser.add_argument(
        "--require_litellm_cache",
        action="store_true",
        default=False,
        help=(
            "Fail unless LiteLLM cache setup succeeds, even for configs that "
            "do not require it automatically."
        ),
    )
    parser.add_argument(
        "--num_shards",
        type=int,
        default=1,
        help="Total number of shards. >1 enables sharded mode with --shard_id or --shard_ids.",
    )
    parser.add_argument(
        "--shard_id",
        type=int,
        default=0,
        help="0-based shard index. Only this shard's slice of sessions is processed.",
    )
    parser.add_argument(
        "--shard_ids",
        type=str,
        default=None,
        help="Comma-separated shard IDs for a grouped local worker, e.g. '0,2,4'.",
    )
    parser.add_argument(
        "--output_suffix",
        type=str,
        default="",
        help="Optional suffix appended to the output filenames "
             "(e.g. '.shard_3' -> '{tid}.shard_3.json'). Empty = '{tid}.json'.",
    )
    parser.add_argument(
        "--output_suffixes_json",
        type=str,
        default=None,
        help="JSON object mapping shard id to output suffix for --shard_ids.",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    main(args)
