"""
Batch inference script for TalkPlay devset smoke tests.
"""

import argparse
import json
import os
import random
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

from datasets import load_dataset
from omegaconf import OmegaConf
import torch
from tqdm import tqdm

from mcrs.inference_utils import chat_history_parser


DEFAULT_ENABLED_TOOLS = ["sql", "bm25", "text_to_item_similarity"]
DEFAULT_EMBEDDING_RETRIEVERS = ["text"]
DEFAULT_EMBEDDING_CORPORA = ["metadata", "attributes", "lyrics"]
TOOL_CALL_FAILURE_PATTERNS = (
    " is not in list",
    "No tool call results were produced.",
    "TalkPlay result did not include any tool call results.",
)


def load_talkplay_agent(model_name: str, cache_dir: str, **kwargs):
    """Load the vendored TalkPlay agent lazily so tests can monkeypatch it."""
    repo_root = Path(__file__).resolve().parent
    talkplay_root = repo_root / "talkplay-tools"
    if str(talkplay_root) not in sys.path:
        sys.path.insert(0, str(talkplay_root))
    from tpa.agents import load_talkplay_agent as _load_talkplay_agent

    return _load_talkplay_agent(cache_dir=cache_dir, model_name=model_name, **kwargs)


def extract_prediction_row(result: dict, prediction_depth: int) -> tuple[list[str], str]:
    """Extract evaluator-ready ranked IDs and response from a TalkPlay result."""
    tool_call_results = result.get("tool_call_results") or []
    if not tool_call_results:
        raise ValueError("TalkPlay result did not include any tool call results.")
    final_ranked_ids = tool_call_results[-1].get("recommend_track_ids") or []
    if len(final_ranked_ids) < prediction_depth:
        raise ValueError(
            f"Final TalkPlay tool call returned fewer than {prediction_depth} ids "
            f"({len(final_ranked_ids)})."
        )
    predicted_track_ids = final_ranked_ids[:prediction_depth]
    if len(set(predicted_track_ids)) != prediction_depth:
        raise ValueError(
            f"Final TalkPlay tool call did not return {prediction_depth} unique ids."
        )
    return predicted_track_ids, result.get("answer_response") or ""


def _dedupe_track_ids(track_ids: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for track_id in track_ids:
        if track_id not in seen:
            seen.add(track_id)
            deduped.append(track_id)
    return deduped


def classify_talkplay_failure(error_message: str, result: dict | None = None) -> str:
    """Classify TalkPlay failures so logs and traces reflect the real fallback reason."""
    tool_call_results = (result or {}).get("tool_call_results") or []
    if any(pattern in error_message for pattern in TOOL_CALL_FAILURE_PATTERNS):
        return "tool_call_missing"
    if not tool_call_results:
        return "runtime_error"
    if "Final tool call returned no track recommendations." in error_message:
        return "empty_tool_result"
    if "fewer than" in error_message or "Unable to normalize" in error_message:
        return "short_or_invalid_ranking"
    return "runtime_error"


def normalize_prediction_row(
    result: dict,
    prediction_depth: int,
    catalog_track_ids: list[str],
    allow_backfill: bool = False,
) -> tuple[list[str], str, dict]:
    """Normalize TalkPlay output into an evaluator-compatible ranked list."""
    tool_call_results = result.get("tool_call_results") or []
    if not tool_call_results:
        raise ValueError("TalkPlay result did not include any tool call results.")

    final_ranked_ids = tool_call_results[-1].get("recommend_track_ids") or []
    deduped_track_ids = _dedupe_track_ids(final_ranked_ids)
    backfilled_count = 0

    if len(deduped_track_ids) < prediction_depth:
        if not allow_backfill:
            raise ValueError(
                f"Final TalkPlay tool call returned fewer than {prediction_depth} ids "
                f"({len(final_ranked_ids)})."
            )
        seen = set(deduped_track_ids)
        for track_id in catalog_track_ids:
            if track_id not in seen:
                deduped_track_ids.append(track_id)
                seen.add(track_id)
            if len(deduped_track_ids) >= prediction_depth:
                break
        backfilled_count = len(deduped_track_ids) - len(_dedupe_track_ids(final_ranked_ids))

    if len(deduped_track_ids) < prediction_depth:
        raise ValueError(
            f"Unable to normalize TalkPlay output to {prediction_depth} unique ids "
            f"(got {len(deduped_track_ids)})."
        )

    return (
        deduped_track_ids[:prediction_depth],
        result.get("answer_response") or "",
        {
            "tool_names": [call.get("tool_name") for call in tool_call_results],
            "final_tool_name": tool_call_results[-1].get("tool_name"),
            "final_tool_topk": tool_call_results[-1].get("tool_args", {}).get("topk"),
            "raw_final_count": len(final_ranked_ids),
            "unique_final_count": len(_dedupe_track_ids(final_ranked_ids)),
            "backfilled_count": backfilled_count,
        },
    )


def build_fallback_prediction_row(
    result: dict | None,
    prediction_depth: int,
    catalog_track_ids: list[str],
    error_message: str,
    fallback_reason: str,
) -> tuple[list[str], str, dict]:
    """Return a deterministic fallback ranking when TalkPlay fails for a row."""
    deduped_catalog_ids = _dedupe_track_ids(catalog_track_ids)
    if len(deduped_catalog_ids) < prediction_depth:
        raise ValueError(
            f"Catalog does not contain {prediction_depth} unique track ids for fallback "
            f"(got {len(deduped_catalog_ids)})."
        )
    tool_call_results = (result or {}).get("tool_call_results") or []
    return (
        deduped_catalog_ids[:prediction_depth],
        (result or {}).get("answer_response") or "",
        {
            "tool_names": [call.get("tool_name") for call in tool_call_results],
            "final_tool_name": tool_call_results[-1].get("tool_name") if tool_call_results else None,
            "final_tool_topk": (
                tool_call_results[-1].get("tool_args", {}).get("topk")
                if tool_call_results
                else None
            ),
            "raw_final_count": len(tool_call_results[-1].get("recommend_track_ids") or [])
            if tool_call_results
            else 0,
            "unique_final_count": len(
                _dedupe_track_ids(tool_call_results[-1].get("recommend_track_ids") or [])
            )
            if tool_call_results
            else 0,
            "backfilled_count": 0,
            "fallback_used": True,
            "fallback_strategy": "fixed_pool",
            "fallback_reason": fallback_reason,
            "error_message": error_message,
        },
    )


def _build_explicit_user_profile(item: dict, user_mode: str) -> dict:
    user_profile = item.get("user_profile") or {}
    return {
        "user_id": item["user_id"],
        "age_group": user_profile.get("age_group", "unknown"),
        "gender": user_profile.get("gender", "unknown"),
        "country_name": user_profile.get("country_name", "unknown"),
        "user_type": user_mode,
        "previous_history": [],
    }


def prepare_talkplay_smoke_cache(config) -> list[str]:
    """Create the minimal TalkPlay cache assets needed for the devset smoke test."""
    cache_dir = Path(config.cache_dir)
    metadata_dir = cache_dir / "metadata"
    encoder_dir = cache_dir / "encoder"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    encoder_dir.mkdir(parents=True, exist_ok=True)

    track_split = config.get("track_split", "all_tracks")
    user_split = config.get("user_split", "all_users")
    embedding_split = config.get("track_embeddings_split", track_split)

    track_rows = load_dataset(config.track_dataset_name, split=track_split)
    track_metadata = {}
    for item in track_rows:
        fallback_lyrics = " ".join(
            item.get("tag_list") or item.get("track_name") or ["unknown"]
        )
        track_metadata[item["track_id"]] = {
            "track_id": item["track_id"],
            "track_name": item.get("track_name") or [],
            "artist_name": item.get("artist_name") or [],
            "album_name": item.get("album_name") or [],
            "tag_list": item.get("tag_list") or [],
            "lyrics": fallback_lyrics,
            "popularity": item.get("popularity", 0),
            "track_release_date_spotify": item.get("release_date"),
            "release_date": item.get("release_date"),
            "tempo": [],
            "key": [],
        }

    (metadata_dir / "test_metadata.json").write_text(
        json.dumps(track_metadata, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "item_metadata.json").write_text(
        json.dumps(track_metadata, ensure_ascii=False),
        encoding="utf-8",
    )

    user_rows = load_dataset(config.user_dataset_name, split=user_split)
    user_profiles = {}
    for item in user_rows:
        user_profiles[item["user_id"]] = {
            "user_id": item["user_id"],
            "user_type": "cold_start",
            "age_group": item.get("age_group", "unknown"),
            "gender": item.get("gender", "unknown"),
            "country_name": item.get("country_name", "unknown"),
            "last_track_ids": [],
        }
    (metadata_dir / "user_profiles.json").write_text(
        json.dumps(user_profiles, ensure_ascii=False),
        encoding="utf-8",
    )

    embedding_rows = load_dataset(config.track_embeddings_dataset_name, split=embedding_split)
    embedding_columns = {
        "metadata": "metadata-qwen3_embedding_0.6b",
        "attributes": "attributes-qwen3_embedding_0.6b",
        "lyrics": "lyrics-qwen3_embedding_0.6b",
    }
    vector_db = {name: {} for name in embedding_columns}
    for item in embedding_rows:
        track_id = item["track_id"]
        metadata_values = item.get("metadata-qwen3_embedding_0.6b") or []
        attributes_values = item.get("attributes-qwen3_embedding_0.6b") or []
        lyrics_values = (
            item.get("lyrics-qwen3_embedding_0.6b")
            or attributes_values
            or metadata_values
        )
        for target_name, source_name in embedding_columns.items():
            if target_name == "metadata":
                values = metadata_values
            elif target_name == "attributes":
                values = attributes_values or metadata_values
            else:
                values = lyrics_values
            if values:
                vector_db[target_name][track_id] = torch.tensor(values, dtype=torch.float32)
    torch.save(vector_db, encoder_dir / "vector_db.pt")
    return list(track_metadata.keys())


def configure_talkplay_smoke_agent(agent, prediction_depth: int) -> None:
    """Tighten the tool-calling prompt for evaluator-compatible smoke runs."""
    depth_instruction = (
        f"\nSMOKE TEST REQUIREMENT:\n"
        f"- Use topk={prediction_depth} for both retrieval and reranking.\n"
        f"- Ensure the final tool output contains at least {prediction_depth} track recommendations.\n"
    )
    if depth_instruction not in agent.prompts["goal_tool_calling"]:
        agent.prompts["goal_tool_calling"] += depth_instruction


def _load_devset(config, args):
    db = load_dataset(config.test_dataset_name, split="test")
    if args.session_ids_file is not None:
        with open(args.session_ids_file) as f:
            keep = set(json.load(f)["session_ids"])
        if hasattr(db, "filter"):
            db = db.filter(lambda x: x["session_id"] in keep)
        else:
            db = [item for item in db if item["session_id"] in keep]

    requested_sessions = args.num_sessions or int(config.get("num_sessions", 0))
    if requested_sessions > 0:
        n = min(requested_sessions, len(db))
        sampled_indices = random.sample(range(len(db)), n)
        if hasattr(db, "select"):
            db = db.select(sampled_indices)
        else:
            db = [db[idx] for idx in sampled_indices]
        print(f"Running on {n} randomly sampled sessions.")
    return db


def main(args):
    config = OmegaConf.load(f"config/{args.tid}.yaml")
    if args.clear_cache and os.path.exists(config.cache_dir):
        shutil.rmtree(config.cache_dir)
    catalog_track_ids = prepare_talkplay_smoke_cache(config)
    enabled_tools = list(config.get("enabled_tools", DEFAULT_ENABLED_TOOLS))
    embedding_enabled_retrievers = list(
        config.get("embedding_enabled_retrievers", DEFAULT_EMBEDDING_RETRIEVERS)
    )
    embedding_enabled_corpora = list(
        config.get("embedding_enabled_corpora", DEFAULT_EMBEDDING_CORPORA)
    )
    talkplay_agent = load_talkplay_agent(
        model_name=config.model_name,
        cache_dir=config.cache_dir,
        device=getattr(args, "device", None) or config.get("device", "cpu"),
        llm_backend=config.get("llm_backend", "local"),
        llm_kwargs=dict(config.get("llm_kwargs", {}) or {}),
        enabled_tools=enabled_tools,
        embedding_enabled_retrievers=embedding_enabled_retrievers,
        embedding_enabled_corpora=embedding_enabled_corpora,
        load_semantic_ids=False,
        tool_calling_max_new_tokens=int(config.get("tool_calling_max_new_tokens", 8192 * 8)),
        response_max_new_tokens=int(config.get("response_max_new_tokens", 2048)),
        generate_response=bool(config.get("generate_response", True)),
    )
    parser_context = SimpleNamespace(
        item_db=getattr(
            talkplay_agent,
            "item_db",
            SimpleNamespace(id_to_metadata=lambda track_id: f"track:{track_id}"),
        )
    )
    catalog_track_ids = list(getattr(talkplay_agent, "track_pool", [])) or catalog_track_ids
    prediction_depth = int(config.get("prediction_depth", 1000))
    user_mode = config.get("user_mode", "cold_start")
    allow_prediction_backfill = bool(config.get("allow_prediction_backfill", False))
    configure_talkplay_smoke_agent(talkplay_agent, prediction_depth)

    db = _load_devset(config, args)
    inference_results = []
    trace_rows = []
    fallback_rows = 0
    for item in tqdm(db, desc="TalkPlay devset inference"):
        explicit_user_info = _build_explicit_user_profile(item, user_mode=user_mode)
        for target_turn_number in range(1, 9):
            chat_history, user_query = chat_history_parser(
                item["conversations"],
                parser_context,
                target_turn_number,
            )
            talkplay_agent._reset_session_memory()
            talkplay_agent.session_memory = chat_history.copy()
            talkplay_agent._load_user_profile(explicit_user_info=explicit_user_info)
            try:
                result = talkplay_agent.chat(user_query)
            except Exception as exc:
                fallback_rows += 1
                fallback_reason = classify_talkplay_failure(str(exc))
                predicted_track_ids, predicted_response, trace_summary = build_fallback_prediction_row(
                    result=None,
                    prediction_depth=prediction_depth,
                    catalog_track_ids=catalog_track_ids,
                    error_message=f"agent chat failed: {exc}",
                    fallback_reason=fallback_reason,
                )
                if fallback_reason == "tool_call_missing":
                    print(
                        "Used fixed-pool fallback after TalkPlay tool-call failure:",
                        f"session={item['session_id']}",
                        f"turn={target_turn_number}",
                        f"error={exc}",
                    )
                else:
                    print(
                        "Fell back after TalkPlay chat failure:",
                        f"session={item['session_id']}",
                        f"turn={target_turn_number}",
                        f"error={exc}",
                    )
                inference_results.append(
                    {
                        "session_id": item["session_id"],
                        "user_id": item["user_id"],
                        "turn_number": target_turn_number,
                        "predicted_track_ids": predicted_track_ids,
                        "predicted_response": predicted_response,
                    }
                )
                trace_rows.append(
                    {
                        "session_id": item["session_id"],
                        "user_id": item["user_id"],
                        "turn_number": target_turn_number,
                        "user_query": user_query,
                        "tool_trace": trace_summary,
                    }
                )
                continue
            try:
                predicted_track_ids, predicted_response, trace_summary = normalize_prediction_row(
                    result,
                    prediction_depth=prediction_depth,
                    catalog_track_ids=catalog_track_ids,
                    allow_backfill=allow_prediction_backfill,
                )
                if trace_summary["backfilled_count"] > 0:
                    print(
                        "Backfilled TalkPlay ranking:",
                        f"session={item['session_id']}",
                        f"turn={target_turn_number}",
                        f"tool={trace_summary['final_tool_name']}",
                        f"raw={trace_summary['raw_final_count']}",
                        f"backfilled={trace_summary['backfilled_count']}",
                    )
            except Exception as exc:
                fallback_rows += 1
                fallback_reason = classify_talkplay_failure(str(exc), result=result)
                predicted_track_ids, predicted_response, trace_summary = build_fallback_prediction_row(
                    result=result,
                    prediction_depth=prediction_depth,
                    catalog_track_ids=catalog_track_ids,
                    error_message=str(exc),
                    fallback_reason=fallback_reason,
                )
                if fallback_reason == "tool_call_missing":
                    print(
                        "Used fixed-pool fallback after missing TalkPlay tool output:",
                        f"session={item['session_id']}",
                        f"turn={target_turn_number}",
                        f"error={exc}",
                    )
                else:
                    print(
                        "Fell back to catalog ranking:",
                        f"session={item['session_id']}",
                        f"turn={target_turn_number}",
                        f"error={exc}",
                    )
            inference_results.append(
                {
                    "session_id": item["session_id"],
                    "user_id": item["user_id"],
                    "turn_number": target_turn_number,
                    "predicted_track_ids": predicted_track_ids,
                    "predicted_response": predicted_response,
                }
            )
            trace_rows.append(
                {
                    "session_id": item["session_id"],
                    "user_id": item["user_id"],
                    "turn_number": target_turn_number,
                    "user_query": user_query,
                    "tool_trace": trace_summary,
                }
            )

    output_dir = Path(args.exp_dir) / "inference" / "devset"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_stem = args.tid
    output_suffix = getattr(args, "output_suffix", None)
    if output_suffix:
        output_stem = f"{output_stem}.{output_suffix}"
    output_path = output_dir / f"{output_stem}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(inference_results, f, ensure_ascii=False)
    trace_path = output_dir / f"{output_stem}_trace.json"
    with trace_path.open("w", encoding="utf-8") as f:
        json.dump(trace_rows, f, ensure_ascii=False)
    print(f"Completed TalkPlay inference with {fallback_rows} fallback rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run TalkPlay smoke-test inference on the Music CRS devset."
    )
    parser.add_argument(
        "--tid",
        type=str,
        default="talkplay_qwen3_4b_devset_smoke",
        help="Task identifier matching a config file in config/.",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=1,
        help="Unused placeholder for CLI consistency with the baseline runner.",
    )
    parser.add_argument(
        "--session_ids_file",
        type=str,
        default=None,
        help="Path to JSON file with a session_ids list for targeted runs.",
    )
    parser.add_argument(
        "--num_sessions",
        type=int,
        default=0,
        help="Randomly sample N sessions for a quick smoke test (0 = use config value).",
    )
    parser.add_argument(
        "--exp_dir",
        type=str,
        default="exp",
        help="Base directory for saving results (default: ./exp).",
    )
    parser.add_argument(
        "--output_suffix",
        type=str,
        default=None,
        help="Optional suffix for shard outputs before the .json extension.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Optional device override (for example: cuda, cpu).",
    )
    parser.add_argument(
        "--clear_cache",
        action="store_true",
        default=False,
        help="Reserved for interface parity; TalkPlay cache clearing is not implemented here.",
    )
    main(parser.parse_args())
