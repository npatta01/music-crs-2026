"""Run a small snapshot-query-understanding pilot against BM25.

The pilot compares passthrough BM25 with a structured state snapshot extracted
by an OpenAI-compatible LiteLLM chat model. Extraction failures are abandoned
for the snapshot arm and counted separately.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import load_dataset
from omegaconf import OmegaConf
from dotenv import load_dotenv

from mcrs import load_crs_baseline
from mcrs.analysis.retrieval_analysis import evaluate_run
from mcrs.inference_utils import chat_history_parser


REQUIRED_SNAPSHOT_KEYS = (
    "intent",
    "positive_preferences",
    "negative_preferences",
    "active_constraints",
    "sparse_query",
    "dense_query",
)
PILOT_K_VALUES = [10, 20, 100, 1000]


PREFERENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "artists",
        "tracks",
        "albums",
        "tags",
        "moods",
        "eras",
        "lyrics_or_story",
        "instrumentation",
        "other",
    ],
    "properties": {
        "artists": {"type": "array", "items": {"type": "string"}},
        "tracks": {"type": "array", "items": {"type": "string"}},
        "albums": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "moods": {"type": "array", "items": {"type": "string"}},
        "eras": {"type": "array", "items": {"type": "string"}},
        "lyrics_or_story": {"type": "array", "items": {"type": "string"}},
        "instrumentation": {"type": "array", "items": {"type": "string"}},
        "other": {"type": "array", "items": {"type": "string"}},
    },
}


SNAPSHOT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(REQUIRED_SNAPSHOT_KEYS),
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "refinement",
                "pivot",
                "more_like_this",
                "direct_lookup",
                "forgotten_item_recovery",
                "metadata_rich_search",
                "exploratory_browsing",
            ],
        },
        "positive_preferences": PREFERENCE_SCHEMA,
        "negative_preferences": PREFERENCE_SCHEMA,
        "active_constraints": {
            "type": "object",
            "additionalProperties": False,
            "required": ["must_have", "nice_to_have", "avoid", "relaxation_order", "null_result_strategy"],
            "properties": {
                "must_have": {"type": "array", "items": {"type": "string"}},
                "nice_to_have": {"type": "array", "items": {"type": "string"}},
                "avoid": {"type": "array", "items": {"type": "string"}},
                "relaxation_order": {"type": "array", "items": {"type": "string"}},
                "null_result_strategy": {"type": "string"},
            },
        },
        "sparse_query": {"type": "string"},
        "dense_query": {"type": "string"},
    },
}


EXTRACTION_SYSTEM_PROMPT = """You extract the latest retrieval state for a music recommendation conversation.

Use only observable conversation text and prior music metadata. Do not use hidden goals.
Return strict JSON matching the requested schema.

Rules:
- Preserve useful prior artists, tracks, albums, tags, moods, eras, lyrics/story cues, and instrumentation.
- Later explicit user preferences supersede conflicting earlier ones.
- If the user says "same vibe" or "more like that", preserve relevant prior positive anchors.
- If the user rejects a recommendation, add exact rejected track ids or salient traits to negative_preferences.
- Treat constraints as ranking guidance. Use active_constraints.must_have for strongest signals, nice_to_have for relaxable signals, and avoid for demotions/exclusions.
- Put lower-priority nice_to_have constraints first in active_constraints.relaxation_order.
- sparse_query must be compact catalog/entity language for BM25.
- dense_query must describe the semantic/vibe target.
"""


class SnapshotExtractionError(ValueError):
    """Raised when the snapshot arm must abandon an item."""


@dataclass
class SnapshotExtractionResult:
    snapshot: dict[str, Any]
    generated_text: str
    extraction_status: str = "success"


@dataclass
class RetrievalResult:
    track_ids: list[str]
    query: str
    query_field: str
    relaxed_constraints: list[str]
    attempts: list[dict[str, Any]]


class LiteLLMSnapshotAdapter:
    def __init__(
        self,
        model_name: str,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.model_name = model_name
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE")
        self.api_key = (
            api_key
            or os.environ.get("LITELLM_PROXY_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
        )
        self.temperature = temperature

    def _litellm_model_name(self) -> str:
        if self.api_base or os.environ.get("OPENAI_API_KEY") or not os.environ.get("OPENROUTER_API_KEY"):
            return self.model_name
        if self.model_name.startswith("openrouter/"):
            return self.model_name
        return f"openrouter/{self.model_name}"

    def generate_batch(self, messages_list: list[list[dict[str, str]]], max_new_tokens: int) -> list[str]:
        import litellm

        kwargs: dict[str, Any] = {
            "model": self._litellm_model_name(),
            "messages": messages_list,
            "temperature": self.temperature,
            "max_tokens": max_new_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "snapshot_query_state",
                    "schema": SNAPSHOT_JSON_SCHEMA,
                    "strict": True,
                },
            },
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key

        responses = litellm.batch_completion(**kwargs)
        outputs: list[str] = []
        for response in responses:
            if isinstance(response, Exception):
                raise response
            try:
                content = response.choices[0].message.content
            except Exception as exc:
                raise SnapshotExtractionError(f"missing_response_content: {exc}") from exc
            if not content:
                raise SnapshotExtractionError("empty_response_content")
            outputs.append(content)
        return outputs


class SnapshotExtractor:
    def __init__(
        self,
        model_name: str = "openai/gpt-5.4-mini",
        adapter: Any | None = None,
        max_new_tokens: int = 1024,
    ) -> None:
        self.model_name = model_name
        self.adapter = adapter or LiteLLMSnapshotAdapter(model_name=model_name)
        self.max_new_tokens = max_new_tokens

    def _build_messages(self, session_memory: list[dict[str, Any]], user_query: str) -> list[dict[str, str]]:
        payload = {
            "prior_session_memory": session_memory,
            "latest_user_query": user_query,
        }
        return [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    def extract_one(self, session_memory: list[dict[str, Any]], user_query: str) -> SnapshotExtractionResult:
        return self.extract_batch([(session_memory, user_query)])[0]

    def extract_batch(
        self,
        examples: list[tuple[list[dict[str, Any]], str]],
    ) -> list[SnapshotExtractionResult]:
        messages_list = [self._build_messages(memory, query) for memory, query in examples]
        try:
            generated_outputs = self.adapter.generate_batch(messages_list, self.max_new_tokens)
        except Exception as exc:
            raise SnapshotExtractionError(f"generation_error: {exc}") from exc

        results: list[SnapshotExtractionResult] = []
        for generated_text in generated_outputs:
            snapshot = parse_snapshot_json(generated_text)
            results.append(SnapshotExtractionResult(snapshot=snapshot, generated_text=generated_text))
        return results


def parse_snapshot_json(generated_text: str) -> dict[str, Any]:
    try:
        snapshot = json.loads(generated_text)
    except json.JSONDecodeError as exc:
        raise SnapshotExtractionError(f"invalid_json: {exc}") from exc

    if not isinstance(snapshot, dict):
        raise SnapshotExtractionError("invalid_json: root must be an object")

    missing = sorted(set(REQUIRED_SNAPSHOT_KEYS) - set(snapshot))
    if missing:
        raise SnapshotExtractionError(f"missing_keys: {missing}")

    if not isinstance(snapshot["sparse_query"], str) or not snapshot["sparse_query"].strip():
        raise SnapshotExtractionError("invalid_sparse_query")
    if not isinstance(snapshot["active_constraints"], dict):
        raise SnapshotExtractionError("invalid_active_constraints")
    return snapshot


def _drop_constraint_from_query(query: str, constraint: str) -> str:
    cleaned = query
    if constraint:
        cleaned = re.sub(re.escape(constraint), " ", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split())


def _constraint_values(snapshot: dict[str, Any]) -> list[str]:
    constraints = snapshot.get("active_constraints") or {}
    relaxation_order = constraints.get("relaxation_order") or []
    nice_to_have = constraints.get("nice_to_have") or []
    values = [str(item) for item in relaxation_order if str(item).strip()]
    for item in nice_to_have:
        value = str(item)
        if value.strip() and value not in values:
            values.append(value)
    return values


def retrieve_with_relaxation(
    snapshot: dict[str, Any],
    retriever: Any,
    topk: int,
    query_field: str = "sparse_query",
) -> RetrievalResult:
    query = str(snapshot.get(query_field, "")).strip()
    if not query:
        raise SnapshotExtractionError(f"invalid_{query_field}")
    attempts: list[dict[str, Any]] = []
    relaxed: list[str] = []

    track_ids = retriever.text_to_item_retrieval(query, topk=topk)
    attempts.append(
        {
            "query": query,
            "query_field": query_field,
            "relaxed_constraints": [],
            "result_count": len(track_ids),
        }
    )
    if track_ids:
        return RetrievalResult(
            track_ids=track_ids,
            query=query,
            query_field=query_field,
            relaxed_constraints=relaxed,
            attempts=attempts,
        )

    retry_query = query
    for constraint in _constraint_values(snapshot):
        retry_query = _drop_constraint_from_query(retry_query, constraint)
        if retry_query == attempts[-1]["query"]:
            continue
        relaxed.append(constraint)
        track_ids = retriever.text_to_item_retrieval(retry_query, topk=topk)
        attempts.append(
            {
                "query": retry_query,
                "query_field": query_field,
                "relaxed_constraints": list(relaxed),
                "result_count": len(track_ids),
            }
        )
        if track_ids:
            return RetrievalResult(
                track_ids=track_ids,
                query=retry_query,
                query_field=query_field,
                relaxed_constraints=relaxed,
                attempts=attempts,
            )

    return RetrievalResult(
        track_ids=track_ids,
        query=retry_query,
        query_field=query_field,
        relaxed_constraints=relaxed,
        attempts=attempts,
    )


def _gold_track_id(conversations: list[dict[str, Any]], turn_number: int) -> str:
    for turn in conversations:
        if turn["turn_number"] == turn_number and turn["role"] == "music":
            return turn["content"]
    raise KeyError(f"No music turn found for turn {turn_number}")


def _prediction_row(
    session_id: str,
    user_id: str,
    turn_number: int,
    predicted_track_ids: list[str],
    predicted_response: str = "",
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "user_id": user_id,
        "turn_number": turn_number,
        "predicted_track_ids": predicted_track_ids,
        "predicted_response": predicted_response,
    }


def _rank_of(track_ids: list[str], gold_track_id: str) -> int | None:
    try:
        return track_ids.index(gold_track_id) + 1
    except ValueError:
        return None


def deterministic_sample(dataset: Any, num_sessions: int, seed: int) -> list[Any]:
    if num_sessions <= 0 or num_sessions >= len(dataset):
        return list(dataset)
    indices = random.Random(seed).sample(range(len(dataset)), num_sessions)
    return [dataset[index] for index in sorted(indices)]


def _safe_k_values(rows: pd.DataFrame, desired_k_values: list[int]) -> list[int]:
    if rows.empty:
        return desired_k_values
    min_depth = min(len(ids) for ids in rows["predicted_track_ids"])
    safe = [k for k in desired_k_values if k <= min_depth]
    return safe or [min_depth]


def _mean_found_rank(instances: pd.DataFrame) -> float | None:
    found = instances["gt_rank"].dropna()
    if found.empty:
        return None
    return float(found.mean())


def compute_pilot_metrics(
    baseline_rows: pd.DataFrame,
    snapshot_rows: pd.DataFrame,
    ground_truth: pd.DataFrame,
    debug_records: list[dict[str, Any]],
    k_values: list[int] | None = None,
    extra_prediction_sets: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    k_values = k_values or PILOT_K_VALUES
    baseline_k = _safe_k_values(baseline_rows, k_values)
    baseline_instances, baseline_aggregate = evaluate_run(baseline_rows, ground_truth, k_values=baseline_k)
    baseline_aggregate["mean_gt_rank_when_found"] = _mean_found_rank(baseline_instances)

    failures = [record for record in debug_records if record.get("extraction_status") != "success"]
    metrics: dict[str, Any] = {
        "turns_total": int(len(debug_records)),
        "snapshot_valid_turns": int(len(snapshot_rows)),
        "extraction_failure_count": int(len(failures)),
        "extraction_failure_rate": float(len(failures) / len(debug_records)) if debug_records else 0.0,
        "baseline": baseline_aggregate,
        "snapshot": None,
    }

    if not snapshot_rows.empty:
        snapshot_keys = snapshot_rows[["session_id", "turn_number"]]
        snapshot_gt = ground_truth.merge(snapshot_keys, on=["session_id", "turn_number"], how="inner")
        snapshot_k = _safe_k_values(snapshot_rows, k_values)
        snapshot_instances, snapshot_aggregate = evaluate_run(snapshot_rows, snapshot_gt, k_values=snapshot_k)
        snapshot_aggregate["mean_gt_rank_when_found"] = _mean_found_rank(snapshot_instances)
        metrics["snapshot"] = snapshot_aggregate

    for name, rows in (extra_prediction_sets or {}).items():
        metrics[name] = None
        if rows.empty:
            continue
        prediction_keys = rows[["session_id", "turn_number"]]
        prediction_gt = ground_truth.merge(prediction_keys, on=["session_id", "turn_number"], how="inner")
        prediction_k = _safe_k_values(rows, k_values)
        prediction_instances, prediction_aggregate = evaluate_run(rows, prediction_gt, k_values=prediction_k)
        prediction_aggregate["mean_gt_rank_when_found"] = _mean_found_rank(prediction_instances)
        metrics[name] = prediction_aggregate

    return metrics


def _plain_dict(config_value: Any) -> dict[str, Any] | None:
    if config_value is None:
        return None
    if OmegaConf.is_config(config_value):
        return OmegaConf.to_container(config_value, resolve=True) or {}
    return dict(config_value)


def _load_crs_from_config(config_path: str):
    config = OmegaConf.load(config_path)
    return load_crs_baseline(
        lm_type=config.lm_type,
        retrieval_type=config.retrieval_type,
        qu_type=config.get("qu_type", "passthrough"),
        item_db_name=config.item_db_name,
        user_db_name=config.user_db_name,
        track_split_types=config.track_split_types,
        user_split_types=config.user_split_types,
        corpus_types=config.corpus_types,
        cache_dir=config.cache_dir,
        device=config.device,
        attn_implementation=config.attn_implementation,
        retrieval_topk=int(config.get("retrieval_topk", 1000)),
        retrieval_config=_plain_dict(config.get("retrieval_config")),
        qu_kwargs=_plain_dict(config.get("qu_kwargs")),
        lm_kwargs=_plain_dict(config.get("lm_kwargs")),
    )


def run_pilot(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv()
    music_crs = _load_crs_from_config(args.config)
    dense_crs = _load_crs_from_config(args.dense_config) if args.dense_config else None
    extractor = SnapshotExtractor(
        model_name=args.model,
        adapter=LiteLLMSnapshotAdapter(
            model_name=args.model,
            api_base=args.api_base,
            api_key=args.api_key,
            temperature=args.temperature,
        ),
        max_new_tokens=args.max_new_tokens,
    )

    dataset = load_dataset(args.dataset_name, split=args.dataset_split)
    sessions = deterministic_sample(dataset, args.num_sessions, args.seed)

    baseline_rows: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []
    snapshot_dense_rows: list[dict[str, Any]] = []
    ground_truth_rows: list[dict[str, Any]] = []
    debug_records: list[dict[str, Any]] = []

    for item in sessions:
        user_id = item["user_id"]
        session_id = item["session_id"]
        for turn_number in range(1, 9):
            chat_history, user_query = chat_history_parser(item["conversations"], music_crs, turn_number)
            gold_track_id = _gold_track_id(item["conversations"], turn_number)
            ground_truth_rows.append(
                {
                    "session_id": session_id,
                    "turn_number": turn_number,
                    "ground_truth_track_id": gold_track_id,
                }
            )

            baseline_query_memory = chat_history.copy()
            baseline_query_memory.append({"role": "user", "content": user_query})
            baseline_query = music_crs.qu.transform_query(baseline_query_memory)
            baseline_ids = music_crs.retrieval.text_to_item_retrieval(baseline_query, topk=args.topk)
            baseline_rows.append(_prediction_row(session_id, user_id, turn_number, baseline_ids))

            debug_record: dict[str, Any] = {
                "session_id": session_id,
                "user_id": user_id,
                "turn_number": turn_number,
                "user_query": user_query,
                "raw_session_memory": chat_history,
                "gold_track_id": gold_track_id,
                "baseline_query": baseline_query,
                "baseline_track_ids": baseline_ids,
                "baseline_gold_rank": _rank_of(baseline_ids, gold_track_id),
            }

            try:
                extraction = extractor.extract_one(chat_history, user_query)
                retrieval = retrieve_with_relaxation(
                    extraction.snapshot,
                    music_crs.retrieval,
                    topk=args.topk,
                    query_field="sparse_query",
                )
                dense_retrieval = None
                if dense_crs is not None:
                    dense_retrieval = retrieve_with_relaxation(
                        extraction.snapshot,
                        dense_crs.retrieval,
                        topk=args.topk,
                        query_field=args.dense_query_field,
                    )
            except SnapshotExtractionError as exc:
                debug_record.update(
                    {
                        "extraction_status": "failure",
                        "failure_reason": str(exc),
                        "snapshot": None,
                        "snapshot_track_ids": [],
                        "snapshot_gold_rank": None,
                        "snapshot_dense_track_ids": [],
                        "snapshot_dense_gold_rank": None,
                    }
                )
                debug_records.append(debug_record)
                continue

            snapshot_rows.append(_prediction_row(session_id, user_id, turn_number, retrieval.track_ids))
            if dense_retrieval is not None:
                snapshot_dense_rows.append(
                    _prediction_row(session_id, user_id, turn_number, dense_retrieval.track_ids)
                )
            debug_record.update(
                {
                    "extraction_status": extraction.extraction_status,
                    "failure_reason": None,
                    "snapshot": extraction.snapshot,
                    "generated_text": extraction.generated_text,
                    "snapshot_query": retrieval.query,
                    "snapshot_query_field": retrieval.query_field,
                    "relaxed_constraints": retrieval.relaxed_constraints,
                    "relaxation_attempts": retrieval.attempts,
                    "snapshot_track_ids": retrieval.track_ids,
                    "snapshot_gold_rank": _rank_of(retrieval.track_ids, gold_track_id),
                }
            )
            if dense_retrieval is not None:
                debug_record.update(
                    {
                        "snapshot_dense_query": dense_retrieval.query,
                        "snapshot_dense_query_field": dense_retrieval.query_field,
                        "snapshot_dense_relaxed_constraints": dense_retrieval.relaxed_constraints,
                        "snapshot_dense_relaxation_attempts": dense_retrieval.attempts,
                        "snapshot_dense_track_ids": dense_retrieval.track_ids,
                        "snapshot_dense_gold_rank": _rank_of(dense_retrieval.track_ids, gold_track_id),
                    }
                )
            debug_records.append(debug_record)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline_df = pd.DataFrame(baseline_rows)
    snapshot_df = pd.DataFrame(snapshot_rows)
    snapshot_dense_df = pd.DataFrame(snapshot_dense_rows)
    ground_truth_df = pd.DataFrame(ground_truth_rows)
    extra_prediction_sets = {}
    if dense_crs is not None:
        extra_prediction_sets["snapshot_dense"] = snapshot_dense_df
    metrics = compute_pilot_metrics(
        baseline_df,
        snapshot_df,
        ground_truth_df,
        debug_records,
        extra_prediction_sets=extra_prediction_sets,
    )

    (out_dir / "baseline_predictions.json").write_text(
        json.dumps(baseline_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "snapshot_predictions.json").write_text(
        json.dumps(snapshot_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if dense_crs is not None:
        (out_dir / "snapshot_dense_predictions.json").write_text(
            json.dumps(snapshot_dense_rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    (out_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "debug_records.jsonl").write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in debug_records) + "\n",
        encoding="utf-8",
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metrics


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the 5-session snapshot QU pilot.")
    parser.add_argument("--num-sessions", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260509)
    parser.add_argument("--topk", type=int, default=1000)
    parser.add_argument("--model", default="openai/gpt-5.4-mini")
    parser.add_argument("--api-base", default=os.environ.get("LITELLM_PROXY_BASE"))
    parser.add_argument("--api-key", default=os.environ.get("LITELLM_PROXY_KEY") or os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--dataset-name", default="talkpl-ai/TalkPlayData-Challenge-Dataset")
    parser.add_argument("--dataset-split", default="test")
    parser.add_argument("--config", default="config/bm25_devset_retrieval_only_tag_list_no_release_date.yaml")
    parser.add_argument(
        "--dense-config",
        default=None,
        help="Optional dense retriever config. When set, snapshot_dense uses the extracted state dense query.",
    )
    parser.add_argument(
        "--dense-query-field",
        default="dense_query",
        choices=["dense_query", "sparse_query"],
        help="Snapshot field to send to the optional dense retriever.",
    )
    parser.add_argument("--out-dir", default="experiments/analysis/snapshot_qu_pilot_gpt54mini_5sessions")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    metrics = run_pilot(args)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
