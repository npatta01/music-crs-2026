"""Agentic retrieval pipeline with native tool calling."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Literal

import torch
import torch.nn.functional as F
from datasets import concatenate_datasets, load_dataset
from pydantic import BaseModel, ConfigDict, create_model, model_validator

from mcrs.db_item import MusicCatalogDB
from mcrs.db_user import UserProfileDB
from mcrs.litellm_utils import normalize_openai_client_model_name, normalize_proxy_model_name
from mcrs.retrieval_modules import load_retrieval_module

DEFAULT_ENABLED_TOOLS = [
    "sql_filter",
    "bm25_search",
    "text_to_item_similarity",
    "item_to_item_similarity",
    "user_to_item_similarity",
]

TRACK_EMBEDDING_FIELDS = {
    "audio": "audio-laion_clap",
    "image": "image-siglip2",
    "cf": "cf-bpr",
}

TRACKS_SQL_SCHEMA_LINES = [
    "tracks schema for sql_filter:",
    "- track_id TEXT PRIMARY KEY",
    "- track_name TEXT",
    "- artist_name TEXT",
    "- album_name TEXT",
    "- tag_list TEXT",
    "- popularity REAL",
    "- release_date TEXT",
    "- duration INTEGER",
]

ALLOWED_SQL_COLUMNS = {
    "track_id",
    "track_name",
    "artist_name",
    "album_name",
    "tag_list",
    "popularity",
    "release_date",
    "duration",
}


def _rows_from_splits(dataset_name: str, split_types: list[str]) -> list[dict[str, Any]]:
    dataset = load_dataset(dataset_name)
    rows: list[dict[str, Any]] = []
    for split_type in split_types:
        split_rows = dataset[split_type]
        rows.extend(list(split_rows))
    return rows


def _join_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _normalize_text(value: Any) -> str:
    return _join_text(value).strip().lower()


def _dedupe_track_ids(track_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for track_id in track_ids:
        if not track_id or track_id in seen:
            continue
        seen.add(track_id)
        deduped.append(track_id)
    return deduped


def _normalize_sql_query(sql_query: str) -> str:
    query = sql_query.strip()
    if query.endswith(";"):
        query = query[:-1].strip()
    return query


def validate_sql_filter_query(sql_query: str) -> str:
    query = _normalize_sql_query(sql_query)
    lowered = re.sub(r"\s+", " ", query).strip().lower()

    if not lowered.startswith("select "):
        raise ValueError("sql_filter only supports SELECT queries.")
    if ";" in query:
        raise ValueError("sql_filter only supports a single SELECT statement.")
    if len(re.findall(r"\bselect\b", lowered)) != 1:
        raise ValueError("sql_filter does not allow nested queries or multiple SELECT clauses.")
    if re.search(r"\b(join|union|intersect|except|with)\b", lowered):
        raise ValueError("sql_filter only supports single-table queries over tracks.")
    if re.search(r"\bin\s+tag_list\b", lowered):
        raise ValueError(
            "sql_filter treats tag_list as a text column. Use LOWER(tag_list) LIKE '%instrumental%' style filters."
        )

    select_match = re.match(r"^select\s+(.*?)\s+from\s+tracks\b", lowered)
    if not select_match:
        raise ValueError("sql_filter queries must start with `SELECT track_id FROM tracks`.")

    projection = re.sub(r"\s+", " ", select_match.group(1).strip())
    if projection != "track_id":
        raise ValueError("sql_filter must project exactly `track_id`.")

    referenced_tables = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w]*)", lowered)
    if any(table_name != "tracks" for table_name in referenced_tables):
        raise ValueError("sql_filter only allows the `tracks` table.")

    referenced_columns = re.findall(
        r"\b(track_id|track_name|artist_name|album_name|tag_list|popularity|release_date|duration)\b",
        lowered,
    )
    identifier_scan_text = re.sub(r"'[^']*'|\"[^\"]*\"", " ", lowered)
    unknown_identifier_match = re.findall(r"\b([a-z_][a-z0-9_]*)\b", identifier_scan_text)
    reserved_tokens = {
        "select",
        "from",
        "where",
        "order",
        "by",
        "asc",
        "desc",
        "and",
        "or",
        "not",
        "like",
        "lower",
        "upper",
        "tracks",
        "limit",
        "between",
        "is",
        "null",
        "in",
    }
    unknown_columns = sorted(
        {
            token
            for token in unknown_identifier_match
            if token not in reserved_tokens
            and token not in ALLOWED_SQL_COLUMNS
            and not token.isdigit()
        }
    )
    if unknown_columns:
        raise ValueError(
            "sql_filter referenced unsupported identifiers: "
            + ", ".join(unknown_columns[:5])
            + "."
        )

    if not referenced_columns:
        raise ValueError("sql_filter query must reference at least `track_id`.")

    return query


def classify_fallback_reason(error_message: str) -> str:
    if "tool call" in error_message.lower():
        return "tool_call_missing"
    if "fewer than" in error_message.lower() or "unable to normalize" in error_message.lower():
        return "short_or_invalid_ranking"
    if "no track recommendations" in error_message.lower():
        return "empty_tool_result"
    return "runtime_error"


def normalize_final_ranking(
    track_ids: list[str],
    prediction_depth: int,
    catalog_track_ids: list[str],
    allow_prediction_backfill: bool,
) -> tuple[list[str], dict[str, Any]]:
    raw_final_count = len(track_ids)
    deduped = _dedupe_track_ids(track_ids)
    unique_final_count = len(deduped)
    backfilled_count = 0

    if len(deduped) < prediction_depth:
        if not allow_prediction_backfill:
            raise ValueError(
                f"Final ranking returned fewer than {prediction_depth} ids ({raw_final_count})."
            )
        seen = set(deduped)
        for catalog_track_id in catalog_track_ids:
            if catalog_track_id in seen:
                continue
            deduped.append(catalog_track_id)
            seen.add(catalog_track_id)
            if len(deduped) >= prediction_depth:
                break
        backfilled_count = len(deduped) - unique_final_count

    if len(deduped) < prediction_depth:
        raise ValueError(
            f"Unable to normalize TalkPlay output to {prediction_depth} unique ids (got {len(deduped)})."
        )

    return deduped[:prediction_depth], {
        "raw_final_count": raw_final_count,
        "unique_final_count": unique_final_count,
        "backfilled_count": backfilled_count,
    }


def build_fallback_result(
    prediction_depth: int,
    catalog_track_ids: list[str],
    tool_names: list[str],
    error_message: str,
    final_tool_name: str | None = None,
    final_tool_topk: int | None = None,
    steps: list[dict[str, Any]] | None = None,
    repair_retry_used: bool = False,
) -> dict[str, Any]:
    ranked_ids, ranking_meta = normalize_final_ranking(
        track_ids=[],
        prediction_depth=prediction_depth,
        catalog_track_ids=catalog_track_ids,
        allow_prediction_backfill=True,
    )
    return {
        "retrieval_items": ranked_ids,
        "response": "",
        "tool_trace": {
            "tool_names": tool_names,
            "final_tool_name": final_tool_name,
            "final_tool_topk": final_tool_topk,
            **ranking_meta,
            "repair_retry_used": repair_retry_used,
            "steps": list(steps or []),
            "fallback_used": True,
            "fallback_strategy": "fixed_pool",
            "fallback_reason": classify_fallback_reason(error_message),
            "error_message": error_message,
        },
    }


def _object_get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, BaseModel):
        return arguments.model_dump()
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        return json.loads(arguments) if arguments.strip() else {}
    raise TypeError(f"Unsupported tool arguments type: {type(arguments)!r}")


def _tool_call_arguments(tool_call: Any) -> dict[str, Any]:
    function = _object_get(tool_call, "function")
    parsed_arguments = _object_get(function, "parsed_arguments")
    if parsed_arguments is not None:
        return _parse_tool_arguments(parsed_arguments)
    return _parse_tool_arguments(_object_get(function, "arguments", "{}"))


def _message_to_tool_calls(message: Any) -> list[Any]:
    tool_calls = _object_get(message, "tool_calls", [])
    return list(tool_calls or [])


def _message_finish_reason(choice: Any, tool_calls: list[Any]) -> str:
    finish_reason = _object_get(choice, "finish_reason")
    if finish_reason:
        return str(finish_reason)
    if tool_calls:
        return "tool_calls"
    return "unknown"


def _assistant_message_from_tool_calls(tool_calls: list[Any]) -> dict[str, Any]:
    payload_tool_calls = []
    for tool_call in tool_calls:
        function = _object_get(tool_call, "function")
        payload_tool_calls.append(
            {
                "id": _object_get(tool_call, "id"),
                "type": "function",
                "function": {
                    "name": _object_get(function, "name"),
                    "arguments": _object_get(function, "arguments", "{}"),
                },
            }
        )
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": payload_tool_calls,
    }


def _assistant_content_message(message: Any) -> dict[str, Any] | None:
    content = _object_get(message, "content", "")
    if not content:
        return None
    return {"role": "assistant", "content": str(content)}


def _json_tool_content(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _missing_tool_call_repair_message(prediction_depth: int) -> dict[str, str]:
    return {
        "role": "user",
        "content": "Return exactly two tool calls. First retrieval from the full catalog, then reranking over that candidate pool. No prose.",
    }


def _structured_plan_repair_message(error_message: str) -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            "Previous structured plan was invalid: "
            f"{error_message} "
            "Return a full structured two-step plan only. "
            "Both step1 and step2 are required. "
            "Keep topk only in tool arguments, never inside sql_query. "
            "Use only valid tool names and valid SQL over real track columns."
        ),
    }


def normalize_history_for_planner(chat_history: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in chat_history:
        role = message.get("role", "assistant")
        content = message.get("content", "")
        if role == "music":
            normalized.append(
                {
                    "role": "assistant",
                    "content": f"Previously recommended track: {content}",
                }
            )
        elif role in {"user", "assistant", "system", "tool", "developer"}:
            normalized.append({"role": role, "content": content})
        else:
            normalized.append({"role": "assistant", "content": f"Previous {role} message: {content}"})
    return normalized


class LiteLLMChatCompletionsPlanner:
    def __init__(
        self,
        model_name: str,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        self.model_name = normalize_proxy_model_name(model_name)
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE", "http://localhost:4001")
        self.api_key = api_key or os.environ.get("LITELLM_PROXY_KEY", "sk-anything")
        self.temperature = temperature
        self.max_tokens = int(max_tokens)

    def create_completion(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        import litellm

        return litellm.completion(
            model=self.model_name,
            api_base=self.api_base,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=messages,
            tools=tools,
            tool_choice="required",
            parallel_tool_calls=False,
        )


class SQLFilterArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql_query: str
    topk: int


class BM25SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    corpus_type: Literal["title", "artist", "album", "attributes", "metadata"]
    topk: int


class TextToItemSimilarityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    corpus_type: Literal["metadata", "attributes"]
    topk: int


class ItemToItemSimilarityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_id: str
    modality_type: Literal["audio", "image", "cf"]
    topk: int


class UserToItemSimilarityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    topk: int


class StructuredRetrievalBoostPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_mode: Literal["bm25_search", "text_to_item_similarity", "item_to_item_similarity", "user_to_item_similarity"]
    retrieval_query: str | None = None
    retrieval_corpus_type: Literal["title", "artist", "album", "attributes", "metadata"] | None = None
    retrieval_track_id: str | None = None
    retrieval_modality_type: Literal["audio", "image", "cf"] | None = None
    retrieval_user_id: str | None = None
    use_bm25_boost: bool = False
    boost_query: str | None = None
    boost_corpus_type: Literal["title", "artist", "album", "attributes", "metadata"] | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "StructuredRetrievalBoostPlan":
        if self.retrieval_mode == "bm25_search":
            if not self.retrieval_query or self.retrieval_corpus_type is None:
                raise ValueError("bm25_search requires retrieval_query and retrieval_corpus_type.")
        if self.retrieval_mode == "text_to_item_similarity":
            if not self.retrieval_query or self.retrieval_corpus_type not in {"metadata", "attributes"}:
                raise ValueError("text_to_item_similarity requires retrieval_query and retrieval_corpus_type in {metadata, attributes}.")
        if self.retrieval_mode == "item_to_item_similarity":
            if not self.retrieval_track_id or self.retrieval_modality_type is None:
                raise ValueError("item_to_item_similarity requires retrieval_track_id and retrieval_modality_type.")
        if self.retrieval_mode == "user_to_item_similarity" and not self.retrieval_user_id:
            raise ValueError("user_to_item_similarity requires retrieval_user_id.")
        if self.use_bm25_boost and (not self.boost_query or self.boost_corpus_type is None):
            raise ValueError("BM25 boost requires boost_query and boost_corpus_type.")
        return self


class StructuredToolStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any]


class StructuredTwoStepPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step1: StructuredToolStep
    step2: StructuredToolStep


OPENAI_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "sql_filter": SQLFilterArgs,
    "bm25_search": BM25SearchArgs,
    "text_to_item_similarity": TextToItemSimilarityArgs,
    "item_to_item_similarity": ItemToItemSimilarityArgs,
    "user_to_item_similarity": UserToItemSimilarityArgs,
}


def _openai_tool_model_from_schema(tool_schema: dict[str, Any]) -> type[BaseModel]:
    function = tool_schema["function"]
    tool_name = function["name"]
    if tool_name in OPENAI_TOOL_MODELS:
        return OPENAI_TOOL_MODELS[tool_name]

    parameters = function["parameters"]
    properties = parameters.get("properties", {})
    required = set(parameters.get("required", []))
    field_defs: dict[str, tuple[Any, Any]] = {}
    for field_name, field_schema in properties.items():
        field_type = field_schema.get("type")
        annotation: Any
        if field_type == "string":
            annotation = str
        elif field_type == "integer":
            annotation = int
        elif field_type == "array" and field_schema.get("items", {}).get("type") == "string":
            annotation = list[str]
        else:
            annotation = Any
        default = ... if field_name in required else None
        field_defs[field_name] = (annotation, default)

    return create_model(
        "".join(part.capitalize() for part in tool_name.split("_")) + "Args",
        __base__=BaseModel,
        __config__=ConfigDict(extra="forbid"),
        **field_defs,
    )


def build_openai_pydantic_tools(tool_schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from openai import pydantic_function_tool

    tools: list[dict[str, Any]] = []
    for tool_schema in tool_schemas:
        function = tool_schema["function"]
        model = _openai_tool_model_from_schema(tool_schema)
        tools.append(
            pydantic_function_tool(
                model,
                name=function["name"],
                description=function.get("description"),
            )
        )
    return tools


class OpenAIChatCompletionsPlanner:
    def __init__(
        self,
        model_name: str,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        client: Any | None = None,
    ) -> None:
        self.model_name = normalize_openai_client_model_name(model_name)
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE", "http://localhost:4001")
        self.api_key = api_key or os.environ.get("LITELLM_PROXY_KEY", "sk-anything")
        self.temperature = temperature
        self.max_tokens = int(max_tokens)
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, base_url=f"{self.api_base.rstrip('/')}/v1")
        self.client = client

    def create_completion(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        return self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=messages,
            tools=build_openai_pydantic_tools(tools),
            tool_choice="required",
            parallel_tool_calls=True,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def create_structured_plan(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        tool_summaries = []
        for tool_schema in tools:
            function = tool_schema["function"]
            tool_summaries.append(
                {
                    "name": function["name"],
                    "description": function.get("description", ""),
                    "parameters": function.get("parameters", {}),
                }
            )
        structured_messages = list(messages)
        structured_messages.append(
            {
                "role": "user",
                "content": (
                    "Return only a structured two-step tool plan. "
                    "step1 must retrieve from the full catalog. "
                    "step2 must rerank or filter the step1 candidate pool. "
                    "Use exactly these available tools and argument schemas:\n"
                    + json.dumps(tool_summaries, ensure_ascii=False)
                ),
            }
        )
        return self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=structured_messages,
            response_format=StructuredTwoStepPlan,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def create_specialized_retrieval_plan(
        self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Any:
        return self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=messages,
            response_format=StructuredRetrievalBoostPlan,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )


class SQLFilterTool:
    def __init__(self, dataset_name: str, split_types: list[str], cache_dir: str) -> None:
        self.dataset_name = dataset_name
        self.split_types = list(split_types)
        self.cache_dir = cache_dir
        self.db_path = os.path.join(cache_dir, "agentic_sql", "tracks.sqlite3")
        self._ensure_db()

    def _ensure_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if os.path.exists(self.db_path):
            return
        rows = _rows_from_splits(self.dataset_name, self.split_types)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE tracks (
                    track_id TEXT PRIMARY KEY,
                    track_name TEXT,
                    artist_name TEXT,
                    album_name TEXT,
                    tag_list TEXT,
                    popularity REAL,
                    release_date TEXT,
                    duration INTEGER
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO tracks (
                    track_id, track_name, artist_name, album_name, tag_list,
                    popularity, release_date, duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["track_id"],
                        _normalize_text(row.get("track_name")),
                        _normalize_text(row.get("artist_name")),
                        _normalize_text(row.get("album_name")),
                        _normalize_text(row.get("tag_list")),
                        float(row.get("popularity") or 0.0),
                        str(row.get("release_date") or ""),
                        int(row.get("duration") or 0),
                    )
                    for row in rows
                ],
            )
            conn.commit()

    def search(self, sql_query: str, topk: int, track_pool: list[str]) -> list[str]:
        query = validate_sql_filter_query(sql_query)
        with sqlite3.connect(self.db_path) as conn:
            try:
                rows = conn.execute(query).fetchall()
            except sqlite3.Error as exc:
                raise ValueError(f"sql_filter query failed validation or execution: {exc}") from exc
        ranked_ids = [str(row[0]) for row in rows if row]
        if track_pool:
            allowed = set(track_pool)
            ranked_ids = [track_id for track_id in ranked_ids if track_id in allowed]
        return _dedupe_track_ids(ranked_ids)[: int(topk)]


class BM25SearchTool:
    CORPUS_MAP = {
        "title": ["track_name"],
        "artist": ["artist_name"],
        "album": ["album_name"],
        "attributes": ["tag_list"],
        "metadata": ["track_name", "artist_name", "album_name", "tag_list"],
    }

    def __init__(self, dataset_name: str, split_types: list[str], cache_dir: str) -> None:
        self.dataset_name = dataset_name
        self.split_types = list(split_types)
        self.cache_dir = cache_dir
        self._retrievers: dict[str, Any] = {}

    def _get_retriever(self, corpus_type: str) -> Any:
        if corpus_type not in self.CORPUS_MAP:
            raise ValueError(f"Unsupported BM25 corpus_type: {corpus_type}")
        if corpus_type not in self._retrievers:
            self._retrievers[corpus_type] = load_retrieval_module(
                retrieval_type="bm25",
                dataset_name=self.dataset_name,
                track_split_types=self.split_types,
                corpus_types=self.CORPUS_MAP[corpus_type],
                cache_dir=self.cache_dir,
            )
        return self._retrievers[corpus_type]

    def search(self, query: str, corpus_type: str, topk: int, track_pool: list[str]) -> list[str]:
        ranked_ids = self._get_retriever(corpus_type).text_to_item_retrieval(query, int(topk))
        if track_pool:
            allowed = set(track_pool)
            ranked_ids = [track_id for track_id in ranked_ids if track_id in allowed]
        return _dedupe_track_ids(ranked_ids)[: int(topk)]

    def score_track_pool(self, query: str, corpus_type: str, track_pool: list[str]) -> dict[str, float]:
        if not track_pool:
            return {}
        return self._get_retriever(corpus_type).score_track_pool(query, track_pool)


class TextToItemSimilarityTool:
    CORPUS_MAP = {
        "metadata": ["track_name", "artist_name", "album_name", "tag_list"],
        "attributes": ["tag_list"],
    }

    def __init__(
        self,
        dataset_name: str,
        split_types: list[str],
        cache_dir: str,
        retrieval_type: str,
        retrieval_config: dict[str, Any] | None,
    ) -> None:
        self.dataset_name = dataset_name
        self.split_types = list(split_types)
        self.cache_dir = cache_dir
        self.retrieval_type = retrieval_type
        self.retrieval_config = dict(retrieval_config or {})
        self._retrievers: dict[str, Any] = {}

    def _get_retriever(self, corpus_type: str) -> Any:
        if corpus_type not in self.CORPUS_MAP:
            raise ValueError(f"Unsupported text_to_item_similarity corpus_type: {corpus_type}")
        if corpus_type not in self._retrievers:
            self._retrievers[corpus_type] = load_retrieval_module(
                retrieval_type=self.retrieval_type,
                dataset_name=self.dataset_name,
                track_split_types=self.split_types,
                corpus_types=self.CORPUS_MAP[corpus_type],
                cache_dir=self.cache_dir,
                retrieval_config=self.retrieval_config,
            )
        return self._retrievers[corpus_type]

    def search(self, query: str, corpus_type: str, topk: int, track_pool: list[str]) -> list[str]:
        ranked_ids = self._get_retriever(corpus_type).text_to_item_retrieval(query, int(topk))
        if track_pool:
            allowed = set(track_pool)
            ranked_ids = [track_id for track_id in ranked_ids if track_id in allowed]
        return _dedupe_track_ids(ranked_ids)[: int(topk)]


class EmbeddingSimilarityIndex:
    def __init__(
        self,
        track_dataset_name: str,
        track_split_types: list[str],
        user_dataset_name: str,
        user_split_types: list[str],
    ) -> None:
        track_rows = _rows_from_splits(track_dataset_name, track_split_types)
        self.track_ids_by_modality: dict[str, list[str]] = {}
        self.track_index_by_modality: dict[str, dict[str, int]] = {}
        self.track_embeddings_by_modality: dict[str, torch.Tensor] = {}

        for modality, field_name in TRACK_EMBEDDING_FIELDS.items():
            track_ids: list[str] = []
            vectors: list[torch.Tensor] = []
            for row in track_rows:
                values = row.get(field_name) or []
                if not values:
                    continue
                track_ids.append(row["track_id"])
                vectors.append(torch.tensor(values, dtype=torch.float32))
            if vectors:
                matrix = F.normalize(torch.stack(vectors, dim=0), p=2, dim=1)
                self.track_ids_by_modality[modality] = track_ids
                self.track_index_by_modality[modality] = {
                    track_id: idx for idx, track_id in enumerate(track_ids)
                }
                self.track_embeddings_by_modality[modality] = matrix

        user_rows = _rows_from_splits(user_dataset_name, user_split_types)
        self.user_embeddings: dict[str, torch.Tensor] = {}
        for row in user_rows:
            values = row.get("cf-bpr") or []
            if values:
                self.user_embeddings[row["user_id"]] = F.normalize(
                    torch.tensor(values, dtype=torch.float32), p=2, dim=0
                )

    def has_user(self, user_id: str | None) -> bool:
        return bool(user_id) and user_id in self.user_embeddings

    def item_to_item(self, track_id: str, modality_type: str, topk: int, track_pool: list[str]) -> list[str]:
        if modality_type not in self.track_embeddings_by_modality:
            raise ValueError(f"Unsupported item_to_item modality_type: {modality_type}")
        index_lookup = self.track_index_by_modality[modality_type]
        if track_id not in index_lookup:
            return []
        matrix = self.track_embeddings_by_modality[modality_type]
        query_index = index_lookup[track_id]
        scores = torch.matmul(matrix, matrix[query_index])
        ranked_indices = torch.argsort(scores, descending=True).tolist()
        allowed = set(track_pool) if track_pool else None
        ranked_ids: list[str] = []
        for idx in ranked_indices:
            candidate = self.track_ids_by_modality[modality_type][idx]
            if candidate == track_id:
                continue
            if allowed is not None and candidate not in allowed:
                continue
            ranked_ids.append(candidate)
            if len(ranked_ids) >= int(topk):
                break
        return ranked_ids

    def user_to_item(self, user_id: str, topk: int, track_pool: list[str]) -> list[str]:
        if user_id not in self.user_embeddings or "cf" not in self.track_embeddings_by_modality:
            return []
        matrix = self.track_embeddings_by_modality["cf"]
        scores = torch.matmul(matrix, self.user_embeddings[user_id])
        ranked_indices = torch.argsort(scores, descending=True).tolist()
        allowed = set(track_pool) if track_pool else None
        ranked_ids: list[str] = []
        for idx in ranked_indices:
            candidate = self.track_ids_by_modality["cf"][idx]
            if allowed is not None and candidate not in allowed:
                continue
            ranked_ids.append(candidate)
            if len(ranked_ids) >= int(topk):
                break
        return ranked_ids


class NativeToolExecutor:
    def __init__(
        self,
        *,
        sql_tool: SQLFilterTool,
        bm25_tool: BM25SearchTool,
        text_similarity_tool: TextToItemSimilarityTool,
        embedding_index: EmbeddingSimilarityIndex,
    ) -> None:
        self.sql_tool = sql_tool
        self.bm25_tool = bm25_tool
        self.text_similarity_tool = text_similarity_tool
        self.embedding_index = embedding_index
        self.tool_schemas = self._build_tool_schemas()

    @staticmethod
    def _build_tool_schemas() -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "sql_filter",
                    "description": (
                        "Filter or rerank the current candidate pool using a single-table SQL query. "
                        "Only query the `tracks` table. The query must be exactly `SELECT track_id FROM tracks ...`. "
                        "Valid columns: track_id, track_name, artist_name, album_name, tag_list, popularity, release_date, duration. "
                        "tag_list is a TEXT column, not a table. For tag matching use patterns like "
                        "`LOWER(tag_list) LIKE '%instrumental%'`."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql_query": {"type": "string"},
                            "topk": {"type": "integer", "minimum": 1, "maximum": 1000},
                        },
                        "required": ["sql_query", "topk"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bm25_search",
                    "description": (
                        "Lexical retrieval for exact or near-exact text matches over title, artist, album, tags, "
                        "or combined metadata. Use this for named entities, artist mentions, album mentions, or precise keywords."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "corpus_type": {
                                "type": "string",
                                "enum": ["title", "artist", "album", "attributes", "metadata"],
                            },
                            "topk": {"type": "integer", "minimum": 1, "maximum": 1000},
                        },
                        "required": ["query", "corpus_type", "topk"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "text_to_item_similarity",
                    "description": (
                        "Semantic retrieval from free text into metadata or tag space. "
                        "Use this for mood, vibe, instrumentation, genre, activity, or paraphrased intent."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "corpus_type": {
                                "type": "string",
                                "enum": ["metadata", "attributes"],
                            },
                            "topk": {"type": "integer", "minimum": 1, "maximum": 1000},
                        },
                        "required": ["query", "corpus_type", "topk"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "item_to_item_similarity",
                    "description": (
                        "Find tracks similar to a known seed track in audio, image, or collaborative-filtering space. "
                        "Use this when the conversation already names or implies a specific reference track."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "track_id": {"type": "string"},
                            "modality_type": {"type": "string", "enum": ["audio", "image", "cf"]},
                            "topk": {"type": "integer", "minimum": 1, "maximum": 1000},
                        },
                        "required": ["track_id", "modality_type", "topk"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "user_to_item_similarity",
                    "description": (
                        "Personalized collaborative-filtering retrieval for warm-start users with known embeddings. "
                        "Use this to personalize after you understand the user request."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string"},
                            "topk": {"type": "integer", "minimum": 1, "maximum": 1000},
                        },
                        "required": ["user_id", "topk"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def execute_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        track_pool: list[str],
    ) -> dict[str, Any]:
        topk = int(arguments.get("topk", 20))
        try:
            if tool_name == "sql_filter":
                track_ids = self.sql_tool.search(
                    sql_query=arguments["sql_query"],
                    topk=topk,
                    track_pool=track_pool,
                )
            elif tool_name == "bm25_search":
                track_ids = self.bm25_tool.search(
                    query=arguments["query"],
                    corpus_type=arguments["corpus_type"],
                    topk=topk,
                    track_pool=track_pool,
                )
            elif tool_name == "text_to_item_similarity":
                track_ids = self.text_similarity_tool.search(
                    query=arguments["query"],
                    corpus_type=arguments["corpus_type"],
                    topk=topk,
                    track_pool=track_pool,
                )
            elif tool_name == "item_to_item_similarity":
                track_ids = self.embedding_index.item_to_item(
                    track_id=arguments["track_id"],
                    modality_type=arguments["modality_type"],
                    topk=topk,
                    track_pool=track_pool,
                )
            elif tool_name == "user_to_item_similarity":
                track_ids = self.embedding_index.user_to_item(
                    user_id=arguments["user_id"],
                    topk=topk,
                    track_pool=track_pool,
                )
            else:
                raise ValueError(f"Unsupported tool call: {tool_name}")
        except Exception as exc:
            error_message = str(exc)
            return {
                "ok": False,
                "tool_name": tool_name,
                "tool_args": arguments,
                "track_ids": list(track_pool),
                "content": {
                    "error": error_message,
                    "result_count": 0,
                    "track_ids": [],
                },
                "error_message": error_message,
            }

        return {
            "ok": True,
            "tool_name": tool_name,
            "tool_args": arguments,
            "track_ids": track_ids,
            "content": {
                "track_ids": track_ids[: min(len(track_ids), 50)],
                "result_count": len(track_ids),
            },
        }

    def rerank_with_bm25_boost(
        self,
        *,
        query: str,
        corpus_type: str,
        track_pool: list[str],
        weight: float,
    ) -> dict[str, Any]:
        if not track_pool:
            return {
                "ok": True,
                "track_ids": [],
                "content": {
                    "track_ids": [],
                    "result_count": 0,
                    "boost_match_count": 0,
                    "max_bm25_score": 0.0,
                    "mean_bm25_score": 0.0,
                },
            }

        bm25_scores = self.bm25_tool.score_track_pool(query, corpus_type, track_pool)
        max_score = max(bm25_scores.values(), default=0.0)
        min_score = min(bm25_scores.values(), default=0.0)
        if max_score > min_score:
            normalized_bm25_scores = {
                track_id: (score - min_score) / (max_score - min_score)
                for track_id, score in bm25_scores.items()
            }
        else:
            normalized_bm25_scores = {track_id: 0.0 for track_id in track_pool}

        combined: list[tuple[float, int, str]] = []
        for rank_index, track_id in enumerate(track_pool):
            retrieval_rank_score = 1.0 / (rank_index + 1)
            bm25_score = normalized_bm25_scores.get(track_id, 0.0)
            combined_score = (1.0 - weight) * retrieval_rank_score + weight * bm25_score
            combined.append((combined_score, rank_index, track_id))

        combined.sort(key=lambda item: (-item[0], item[1]))
        reranked_track_ids = [track_id for _, _, track_id in combined]
        positive_scores = [score for score in bm25_scores.values() if score > 0]
        return {
            "ok": True,
            "track_ids": reranked_track_ids,
            "content": {
                "track_ids": reranked_track_ids[: min(len(reranked_track_ids), 50)],
                "result_count": len(reranked_track_ids),
                "boost_match_count": len(positive_scores),
                "max_bm25_score": max_score,
                "mean_bm25_score": float(sum(bm25_scores.values()) / len(bm25_scores)),
            },
            "bm25_scores": bm25_scores,
            "normalized_bm25_scores": normalized_bm25_scores,
        }


@dataclass
class AgenticSession:
    planner: Any
    tool_executor: Any
    catalog_track_ids: list[str]
    prediction_depth: int
    max_planning_steps: int
    allow_prediction_backfill: bool
    retrieval_topk: int = 20
    planner_protocol: str = "native_tool_calls"
    bm25_boost_weight: float = 0.35

    def _retrieval_tool_schemas(self) -> list[dict[str, Any]]:
        tool_schemas = list(getattr(self.tool_executor, "tool_schemas", []))
        return list(tool_schemas)

    def _create_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[Any, Any, Any, list[Any], str]:
        response = self.planner.create_completion(
            messages=messages,
            tools=tools if tools is not None else getattr(self.tool_executor, "tool_schemas", []),
        )
        choice = _object_get(response, "choices", [None])[0]
        message = _object_get(choice, "message")
        tool_calls = _message_to_tool_calls(message)
        finish_reason = _message_finish_reason(choice, tool_calls)
        return response, choice, message, tool_calls, finish_reason

    def _parse_two_tool_calls(
        self,
        *,
        messages: list[dict[str, Any]],
        message: Any,
        tool_calls: list[Any],
        finish_reason: str,
        repair_prompt: dict[str, str] | None = None,
    ) -> tuple[list[Any], dict[str, Any]]:
        repair_used = False
        initial_finish_reason = finish_reason
        initial_content = _object_get(message, "content", "")

        if not tool_calls and repair_prompt is not None:
            messages.append(repair_prompt)
            repair_used = True
            _response, choice, message, tool_calls, finish_reason = self._create_completion(messages)

        step_meta = {
            "planner_finish_reason": finish_reason,
            "repair_retry_used": repair_used,
            "repair_reason": "missing_tool_call" if repair_used else None,
            "initial_finish_reason": initial_finish_reason,
            "initial_response_content": initial_content,
        }

        if len(tool_calls) != 2:
            raise ValueError(f"TalkPlay result must include exactly two tool calls; got {len(tool_calls)}.")

        return list(tool_calls), step_meta

    def _parse_structured_two_step_plan(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        working_messages = list(messages)
        repair_used = False
        initial_error: str | None = None

        for attempt in range(2):
            try:
                response = self.planner.create_structured_plan(messages=working_messages, tools=tools)
                choice = _object_get(response, "choices", [None])[0]
                message = _object_get(choice, "message")
                parsed = _object_get(message, "parsed")
                if parsed is None:
                    raise ValueError("TalkPlay structured planner did not return parsed output.")
                if isinstance(parsed, BaseModel):
                    payload = parsed.model_dump()
                elif hasattr(parsed, "model_dump"):
                    payload = parsed.model_dump()
                elif isinstance(parsed, dict):
                    payload = parsed
                else:
                    payload = dict(parsed)
                steps = [payload.get("step1"), payload.get("step2")]
                if any(step is None for step in steps):
                    raise ValueError("TalkPlay structured planner must return both step1 and step2.")
                return list(steps), {
                    "planner_finish_reason": "structured_output",
                    "repair_retry_used": repair_used,
                    "repair_reason": "structured_plan_repair" if repair_used else None,
                    "initial_finish_reason": "structured_output",
                    "initial_response_content": initial_error,
                }, working_messages
            except Exception as exc:
                if attempt == 1:
                    raise
                initial_error = str(exc)
                working_messages.append(_structured_plan_repair_message(initial_error))
                repair_used = True

        raise ValueError("TalkPlay structured planner could not produce a valid plan after repair.")

    def _parse_specialized_retrieval_plan(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        working_messages = list(messages)
        repair_used = False
        initial_error: str | None = None

        for attempt in range(2):
            try:
                start_time = time.time()
                response = self.planner.create_specialized_retrieval_plan(
                    messages=working_messages,
                    tools=tools,
                )
                elapsed_seconds = time.time() - start_time
                choice = _object_get(response, "choices", [None])[0]
                message = _object_get(choice, "message")
                parsed = _object_get(message, "parsed")
                if parsed is None:
                    raise ValueError("TalkPlay specialized planner did not return parsed output.")
                if isinstance(parsed, BaseModel):
                    payload = parsed.model_dump()
                elif hasattr(parsed, "model_dump"):
                    payload = parsed.model_dump()
                elif isinstance(parsed, dict):
                    payload = parsed
                else:
                    payload = dict(parsed)
                if payload.get("retrieval") is None:
                    retrieval = {
                        "mode": payload["retrieval_mode"],
                        "query": payload.get("retrieval_query"),
                        "corpus_type": payload.get("retrieval_corpus_type"),
                        "track_id": payload.get("retrieval_track_id"),
                        "modality_type": payload.get("retrieval_modality_type"),
                        "user_id": payload.get("retrieval_user_id"),
                    }
                    boost = None
                    if payload.get("use_bm25_boost"):
                        boost = {
                            "query": payload.get("boost_query"),
                            "corpus_type": payload.get("boost_corpus_type"),
                        }
                    payload = {
                        "retrieval": retrieval,
                        "bm25_boost": boost,
                    }
                return payload, {
                    "planner_finish_reason": "structured_output",
                    "planner_elapsed_seconds": elapsed_seconds,
                    "repair_retry_used": repair_used,
                    "repair_reason": "structured_plan_repair" if repair_used else None,
                    "initial_finish_reason": "structured_output",
                    "initial_response_content": initial_error,
                }, working_messages
            except Exception as exc:
                if attempt == 1:
                    raise
                initial_error = str(exc)
                working_messages.append(_structured_plan_repair_message(initial_error))
                repair_used = True

        raise ValueError("TalkPlay specialized planner could not produce a valid plan after repair.")

    def _execute_planner_steps(
        self,
        *,
        planner_steps: list[dict[str, Any]],
        planner_step_meta: dict[str, Any],
        messages: list[dict[str, Any]],
        retrieval_tools: list[dict[str, Any]],
        current_track_pool: list[str],
        tool_names: list[str],
        steps: list[dict[str, Any]],
    ) -> tuple[list[str], str | None]:
        tool_names_seen = {schema["function"]["name"] for schema in retrieval_tools}

        for step_index, planner_step in enumerate(planner_steps, start=1):
            tool_name = str(planner_step.get("tool_name"))
            tool_args = dict(planner_step.get("arguments") or {})
            tool_call_id = planner_step.get("tool_call_id")
            if tool_name not in tool_names_seen:
                raise ValueError(f"Unsupported tool in planner output: {tool_name}")
            tool_names.append(tool_name)
            execution = self.tool_executor.execute_tool_call(
                tool_name,
                tool_args,
                current_track_pool,
            )
            current_track_pool = list(execution.get("track_ids", current_track_pool))
            steps.append(
                {
                    "planning_step": step_index,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "tool_result_count": int(_object_get(execution.get("content", {}), "result_count", 0)),
                    "tool_error": execution.get("error_message"),
                    **planner_step_meta,
                }
            )
            if not execution.get("ok", False):
                raise ValueError(execution.get("error_message") or f"{tool_name} failed")
            if tool_call_id is not None:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": _json_tool_content(execution.get("content", {})),
                    }
                )

        return current_track_pool, tool_names[-1] if tool_names else None

    def _retrieval_arguments_from_step(self, retrieval_step: dict[str, Any], user_message: str) -> tuple[str, dict[str, Any]]:
        mode = str(retrieval_step.get("mode"))
        topk = max(self.prediction_depth, int(self.retrieval_topk or self.prediction_depth))
        if mode in {"bm25_search", "text_to_item_similarity"}:
            return mode, {
                "query": retrieval_step.get("query") or user_message,
                "corpus_type": retrieval_step["corpus_type"],
                "topk": topk,
            }
        if mode == "item_to_item_similarity":
            return mode, {
                "track_id": retrieval_step["track_id"],
                "modality_type": retrieval_step["modality_type"],
                "topk": topk,
            }
        if mode == "user_to_item_similarity":
            return mode, {
                "user_id": retrieval_step["user_id"],
                "topk": topk,
            }
        raise ValueError(f"Unsupported retrieval mode in specialized plan: {mode}")

    def _execute_specialized_retrieval_plan(
        self,
        *,
        plan: dict[str, Any],
        planner_step_meta: dict[str, Any],
        user_message: str,
        tool_names: list[str],
        steps: list[dict[str, Any]],
    ) -> tuple[list[str], str, dict[str, Any]]:
        retrieval_step = dict(plan.get("retrieval") or {})
        boost_step = plan.get("bm25_boost")
        retrieval_mode, retrieval_args = self._retrieval_arguments_from_step(retrieval_step, user_message)
        tool_names.append(retrieval_mode)
        retrieval_execution = self.tool_executor.execute_tool_call(
            retrieval_mode,
            retrieval_args,
            self.catalog_track_ids,
        )
        retrieval_track_pool = list(retrieval_execution.get("track_ids", []))
        steps.append(
            {
                "planning_step": 1,
                "tool_name": retrieval_mode,
                "tool_args": retrieval_args,
                "tool_result_count": int(_object_get(retrieval_execution.get("content", {}), "result_count", 0)),
                "tool_error": retrieval_execution.get("error_message"),
                **planner_step_meta,
            }
        )
        if not retrieval_execution.get("ok", False):
            raise ValueError(retrieval_execution.get("error_message") or f"{retrieval_mode} failed")

        final_track_ids = list(retrieval_track_pool)
        final_tool_name = retrieval_mode
        boost_trace = {
            "boost_used": False,
            "boost_query": None,
            "boost_corpus_type": None,
            "boost_match_count": 0,
            "pre_rerank_top_ids": retrieval_track_pool[:10],
            "post_rerank_top_ids": retrieval_track_pool[:10],
            "final_ranking_source": "retrieval_only",
        }

        if boost_step is not None:
            boost_args = dict(boost_step)
            tool_names.append("bm25_boost")
            rerank_execution = self.tool_executor.rerank_with_bm25_boost(
                query=boost_args["query"],
                corpus_type=boost_args["corpus_type"],
                track_pool=retrieval_track_pool,
                weight=self.bm25_boost_weight,
            )
            final_track_ids = list(rerank_execution.get("track_ids", retrieval_track_pool))
            final_tool_name = "bm25_boost"
            boost_content = rerank_execution.get("content", {})
            steps.append(
                {
                    "planning_step": 2,
                    "tool_name": "bm25_boost",
                    "tool_args": boost_args,
                    "tool_result_count": int(_object_get(boost_content, "result_count", 0)),
                    "tool_error": rerank_execution.get("error_message"),
                    "boost_match_count": int(_object_get(boost_content, "boost_match_count", 0)),
                    "max_bm25_score": float(_object_get(boost_content, "max_bm25_score", 0.0)),
                    "mean_bm25_score": float(_object_get(boost_content, "mean_bm25_score", 0.0)),
                    **planner_step_meta,
                }
            )
            if not rerank_execution.get("ok", False):
                raise ValueError(rerank_execution.get("error_message") or "bm25_boost failed")
            boost_trace = {
                "boost_used": True,
                "boost_query": boost_args["query"],
                "boost_corpus_type": boost_args["corpus_type"],
                "boost_match_count": int(_object_get(boost_content, "boost_match_count", 0)),
                "pre_rerank_top_ids": retrieval_track_pool[:10],
                "post_rerank_top_ids": final_track_ids[:10],
                "final_ranking_source": "retrieval_plus_bm25_boost",
            }

        trace_meta = {
            "retrieval_mode": retrieval_mode,
            "retrieval_topk": retrieval_args.get("topk"),
            "retrieval_query": retrieval_args.get("query"),
            "retrieval_corpus_type": retrieval_args.get("corpus_type"),
            "retrieval_track_id": retrieval_args.get("track_id"),
            "retrieval_user_id": retrieval_args.get("user_id"),
            "retrieval_pool_size": len(retrieval_track_pool),
            "retrieval_track_ids": retrieval_track_pool,
            **boost_trace,
            "planner_output": plan,
        }
        return final_track_ids, final_tool_name, trace_meta

    def run_turn(
        self,
        *,
        system_prompt: str,
        chat_history: list[dict[str, Any]],
        user_message: str,
    ) -> dict[str, Any]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(normalize_history_for_planner(chat_history))
        messages.append({"role": "user", "content": user_message})

        repair_retry_used = False
        final_tool_name: str | None = None
        final_tool_topk: int | None = None
        retrieval_tools = self._retrieval_tool_schemas()
        tool_names: list[str] = []
        steps: list[dict[str, Any]] = []
        plan_trace_meta: dict[str, Any] = {}

        try:
            if self.planner_protocol == "structured_retrieval_bm25_boost":
                plan_payload, planner_step_meta, _working_messages = self._parse_specialized_retrieval_plan(
                    messages=messages,
                    tools=retrieval_tools,
                )
                repair_retry_used = repair_retry_used or bool(planner_step_meta["repair_retry_used"])
                final_track_ids, final_tool_name, plan_trace_meta = self._execute_specialized_retrieval_plan(
                    plan=plan_payload,
                    planner_step_meta=planner_step_meta,
                    user_message=user_message,
                    tool_names=tool_names,
                    steps=steps,
                )
                final_tool_topk = self.prediction_depth
                retrieval_track_pool = list(plan_trace_meta.get("retrieval_track_ids") or final_track_ids)
                ranked_ids, ranking_meta = normalize_final_ranking(
                    track_ids=list(final_track_ids),
                    prediction_depth=self.prediction_depth,
                    catalog_track_ids=retrieval_track_pool if retrieval_track_pool else self.catalog_track_ids,
                    allow_prediction_backfill=self.allow_prediction_backfill,
                )
                return {
                    "retrieval_items": ranked_ids,
                    "response": "",
                    "tool_trace": {
                        "tool_names": tool_names,
                        "final_tool_name": final_tool_name,
                        "final_tool_topk": final_tool_topk,
                        **ranking_meta,
                        "repair_retry_used": repair_retry_used,
                        "steps": steps,
                        **plan_trace_meta,
                    },
                }
            if self.planner_protocol == "structured_two_step_plan":
                planner_steps, planner_step_meta, working_messages = self._parse_structured_two_step_plan(
                    messages=messages,
                    tools=retrieval_tools,
                )
                repair_retry_used = repair_retry_used or bool(planner_step_meta["repair_retry_used"])
            else:
                _response, _choice, message, tool_calls, finish_reason = self._create_completion(
                    messages,
                    retrieval_tools,
                )
                planner_tool_calls, planner_step_meta = self._parse_two_tool_calls(
                    messages=messages,
                    message=message,
                    tool_calls=tool_calls,
                    finish_reason=finish_reason,
                    repair_prompt=_missing_tool_call_repair_message(self.prediction_depth),
                )
                planner_steps = []
                for tool_call in planner_tool_calls:
                    function = _object_get(tool_call, "function")
                    planner_steps.append(
                        {
                            "tool_name": str(_object_get(function, "name")),
                            "arguments": _tool_call_arguments(tool_call),
                            "tool_call_id": _object_get(tool_call, "id"),
                        }
                    )
                repair_retry_used = repair_retry_used or bool(planner_step_meta["repair_retry_used"])
                working_messages = list(messages)
                working_messages.append(_assistant_message_from_tool_calls(planner_tool_calls))

            current_track_pool = list(self.catalog_track_ids)
            current_track_pool, final_tool_name = self._execute_planner_steps(
                planner_steps=planner_steps,
                planner_step_meta=planner_step_meta,
                messages=working_messages,
                retrieval_tools=retrieval_tools,
                current_track_pool=current_track_pool,
                tool_names=tool_names,
                steps=steps,
            )

            final_tool_name = tool_names[-1]
            final_tool_topk = self.prediction_depth
            ranked_ids, ranking_meta = normalize_final_ranking(
                track_ids=list(current_track_pool),
                prediction_depth=self.prediction_depth,
                catalog_track_ids=self.catalog_track_ids,
                allow_prediction_backfill=self.allow_prediction_backfill,
            )
            return {
                "retrieval_items": ranked_ids,
                "response": "",
                "tool_trace": {
                    "tool_names": tool_names,
                    "final_tool_name": final_tool_name,
                    "final_tool_topk": final_tool_topk,
                    **ranking_meta,
                    "repair_retry_used": repair_retry_used,
                    "steps": steps,
                    **plan_trace_meta,
                },
            }
        except Exception as exc:
            if self.planner_protocol in {"structured_two_step_plan", "structured_retrieval_bm25_boost"} and not repair_retry_used:
                try:
                    repaired_messages = list(messages)
                    repaired_messages.append(_structured_plan_repair_message(str(exc)))
                    if self.planner_protocol == "structured_retrieval_bm25_boost":
                        plan_payload, planner_step_meta, _working_messages = self._parse_specialized_retrieval_plan(
                            messages=repaired_messages,
                            tools=retrieval_tools,
                        )
                        repair_retry_used = True
                        planner_step_meta["repair_retry_used"] = True
                        planner_step_meta["repair_reason"] = "structured_plan_repair"
                        tool_names = []
                        steps = []
                        final_track_ids, final_tool_name, plan_trace_meta = self._execute_specialized_retrieval_plan(
                            plan=plan_payload,
                            planner_step_meta=planner_step_meta,
                            user_message=user_message,
                            tool_names=tool_names,
                            steps=steps,
                        )
                        final_tool_topk = self.prediction_depth
                        retrieval_track_pool = list(plan_trace_meta.get("retrieval_track_ids") or final_track_ids)
                        ranked_ids, ranking_meta = normalize_final_ranking(
                            track_ids=list(final_track_ids),
                            prediction_depth=self.prediction_depth,
                            catalog_track_ids=retrieval_track_pool if retrieval_track_pool else self.catalog_track_ids,
                            allow_prediction_backfill=self.allow_prediction_backfill,
                        )
                        return {
                            "retrieval_items": ranked_ids,
                            "response": "",
                            "tool_trace": {
                                "tool_names": tool_names,
                                "final_tool_name": final_tool_name,
                                "final_tool_topk": final_tool_topk,
                                **ranking_meta,
                                "repair_retry_used": repair_retry_used,
                                "steps": steps,
                                **plan_trace_meta,
                            },
                        }
                    else:
                        planner_steps, planner_step_meta, working_messages = self._parse_structured_two_step_plan(
                            messages=repaired_messages,
                            tools=retrieval_tools,
                        )
                        repair_retry_used = True
                        planner_step_meta["repair_retry_used"] = True
                        planner_step_meta["repair_reason"] = "structured_plan_repair"
                        current_track_pool = list(self.catalog_track_ids)
                        tool_names = []
                        steps = []
                        current_track_pool, final_tool_name = self._execute_planner_steps(
                            planner_steps=planner_steps,
                            planner_step_meta=planner_step_meta,
                            messages=working_messages,
                            retrieval_tools=retrieval_tools,
                            current_track_pool=current_track_pool,
                            tool_names=tool_names,
                            steps=steps,
                        )
                        final_tool_topk = self.prediction_depth
                        ranked_ids, ranking_meta = normalize_final_ranking(
                            track_ids=list(current_track_pool),
                            prediction_depth=self.prediction_depth,
                            catalog_track_ids=self.catalog_track_ids,
                            allow_prediction_backfill=self.allow_prediction_backfill,
                        )
                        return {
                            "retrieval_items": ranked_ids,
                            "response": "",
                            "tool_trace": {
                                "tool_names": tool_names,
                                "final_tool_name": final_tool_name,
                                "final_tool_topk": final_tool_topk,
                                **ranking_meta,
                                "repair_retry_used": repair_retry_used,
                                "steps": steps,
                            },
                        }
                except Exception as repair_exc:
                    error_message = str(repair_exc)
                    return build_fallback_result(
                        prediction_depth=self.prediction_depth,
                        catalog_track_ids=self.catalog_track_ids,
                        tool_names=tool_names,
                        error_message=error_message,
                        final_tool_name=final_tool_name,
                        final_tool_topk=final_tool_topk,
                        steps=steps,
                        repair_retry_used=True,
                    )
            error_message = str(exc)
            return build_fallback_result(
                prediction_depth=self.prediction_depth,
                catalog_track_ids=self.catalog_track_ids,
                tool_names=tool_names,
                error_message=error_message,
                final_tool_name=final_tool_name,
                final_tool_topk=final_tool_topk,
                steps=steps,
                repair_retry_used=repair_retry_used,
            )


class AgenticToolCallingCRS:
    def __init__(
        self,
        *,
        planner_model_name: str,
        item_db_name: str,
        user_db_name: str,
        track_split_types: list[str],
        user_split_types: list[str],
        cache_dir: str,
        corpus_types: list[str],
        retrieval_topk: int,
        toolcalling_config: dict[str, Any] | None = None,
    ) -> None:
        config = dict(toolcalling_config or {})
        self.cache_dir = cache_dir
        self.prediction_depth = int(config.get("prediction_depth", retrieval_topk))
        self.max_planning_steps = int(config.get("max_planning_steps", 4))
        self.allow_prediction_backfill = bool(config.get("allow_prediction_backfill", True))
        self.planner_protocol = str(config.get("planner_protocol", "native_tool_calls"))
        self.bm25_boost_weight = float(config.get("bm25_boost_weight", 0.35))
        self.item_db = MusicCatalogDB(item_db_name, track_split_types, corpus_types)
        self.user_db = UserProfileDB(user_db_name, user_split_types)
        self.catalog_track_ids = list(self.item_db.metadata_dict.keys())

        planner = OpenAIChatCompletionsPlanner(
            model_name=planner_model_name,
            api_base=config.get("api_base"),
            api_key=config.get("api_key"),
            temperature=float(config.get("temperature", 0.0)),
            max_tokens=int(config.get("planner_max_tokens", 1024)),
        )
        text_similarity_retrieval_type = config.get("text_similarity_retrieval_type", "litellm_embedding")
        text_similarity_retrieval_config = dict(config.get("text_similarity_retrieval_config") or {})

        embedding_index = EmbeddingSimilarityIndex(
            track_dataset_name=config.get(
                "track_embeddings_dataset_name",
                "talkpl-ai/TalkPlayData-Challenge-Track-Embeddings",
            ),
            track_split_types=list(
                config.get("track_embeddings_split_types")
                or config.get("track_embeddings_split")
                or ["all_tracks"]
            ),
            user_dataset_name=config.get(
                "user_embeddings_dataset_name",
                "talkpl-ai/TalkPlayData-Challenge-User-Embeddings",
            ),
            user_split_types=list(
                config.get("user_embeddings_split_types")
                or ["train", "test_warm", "test_cold"]
            ),
        )
        self.embedding_index = embedding_index
        tool_executor = NativeToolExecutor(
            sql_tool=SQLFilterTool(item_db_name, track_split_types, cache_dir),
            bm25_tool=BM25SearchTool(item_db_name, track_split_types, cache_dir),
            text_similarity_tool=TextToItemSimilarityTool(
                dataset_name=item_db_name,
                split_types=track_split_types,
                cache_dir=cache_dir,
                retrieval_type=text_similarity_retrieval_type,
                retrieval_config=text_similarity_retrieval_config,
            ),
            embedding_index=embedding_index,
        )
        enabled_tools = list(config.get("enabled_tools", DEFAULT_ENABLED_TOOLS))
        tool_executor.tool_schemas = [
            schema
            for schema in tool_executor.tool_schemas
            if schema["function"]["name"] in enabled_tools
        ]
        self.planner = planner
        self.tool_executor = tool_executor

    def _build_system_prompt(self, user_id: str | None) -> str:
        if self.planner_protocol == "structured_retrieval_bm25_boost":
            prompt_lines = [
                "You are a music retrieval planner.",
                "You are given the conversation history and the current user request.",
                "Use the conversation history to resolve context, carry over entities, and infer the retrieval need for this turn.",
                "Return only the structured retrieval plan.",
                "Choose exactly one retrieval mode in the retrieval block.",
                "Do not include unused fields.",
                "Do not explain your reasoning.",
                "Use optional bm25_boost only to rerank the retrieval pool.",
                "Prefer bm25_search for explicit names, titles, artists, albums, dates, tags, or other lexical constraints.",
                "Prefer text_to_item_similarity for mood, vibe, activity, instrumentation, or paraphrased intent.",
            ]
        else:
            prompt_lines = [
                "You are a music retrieval planner.",
                "Do not write a natural language answer.",
                "Return exactly two tool calls for this turn.",
                "The first tool call retrieves from the full catalog.",
                "The second tool call reranks or filters the first tool's candidate pool.",
                f"Use retrieval topk at least {self.prediction_depth} whenever possible.",
                "Tool usage guidance:",
                "- Use text_to_item_similarity for mood, vibe, instrumentation, genre, activity, and paraphrased intent.",
                "- Use bm25_search for exact artists, titles, albums, tags, and other lexical cues.",
                "- Use item_to_item_similarity when a specific seed track is available from the conversation history.",
                "- Use user_to_item_similarity only for warm-start users, and only after you understand the request.",
                "- Use sql_filter only to filter or rerank candidates using the real tracks schema below.",
                *TRACKS_SQL_SCHEMA_LINES,
                "sql_filter constraints:",
                "- Query only the `tracks` table.",
                "- Query shape must be `SELECT track_id FROM tracks ...`.",
                "- tag_list is a TEXT column, not a table.",
                "- For tag matching use examples like `LOWER(tag_list) LIKE '%instrumental%'`.",
                "- Never put `topk` inside the SQL query. Pass `topk` only as the tool argument.",
                "- Never use free descriptive words as SQL identifiers.",
                "- For semantic concepts, express them only inside quoted LIKE patterns over real columns such as tag_list, track_name, artist_name, or album_name.",
            ]
        if user_id:
            profile = self.user_db.id_to_profile(user_id)
            user_type = "warm_start" if self.embedding_index.has_user(user_id) else "cold_start"
            prompt_lines.append(f"user_id: {user_id}")
            prompt_lines.append(f"user_type: {user_type}")
            prompt_lines.append(f"age_group: {profile.get('age_group', 'unknown')}")
            prompt_lines.append(f"gender: {profile.get('gender', 'unknown')}")
            prompt_lines.append(f"country_name: {profile.get('country_name', 'unknown')}")
            if user_type == "cold_start":
                prompt_lines.append("Do not use user_to_item_similarity for cold-start users.")
        return "\n".join(prompt_lines)

    def chat(
        self,
        user_query: str,
        user_id: str | None = None,
        session_memory: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        session = AgenticSession(
            planner=self.planner,
            tool_executor=self.tool_executor,
            catalog_track_ids=self.catalog_track_ids,
            prediction_depth=self.prediction_depth,
            max_planning_steps=self.max_planning_steps,
            allow_prediction_backfill=self.allow_prediction_backfill,
            retrieval_topk=self.prediction_depth,
            planner_protocol=self.planner_protocol,
            bm25_boost_weight=self.bm25_boost_weight,
        )
        history = list(session_memory or [])
        result = session.run_turn(
            system_prompt=self._build_system_prompt(user_id),
            chat_history=history,
            user_message=user_query,
        )
        recommend_item = ""
        if result["retrieval_items"]:
            recommend_item = self.item_db.id_to_metadata(result["retrieval_items"][0])
        return {
            "user_id": user_id,
            "user_query": user_query,
            "retrieval_items": result["retrieval_items"],
            "recommend_item": recommend_item,
            "response": "",
            "tool_trace": result["tool_trace"],
        }

    def batch_chat(self, batch_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for row in batch_data:
            results.append(
                self.chat(
                    user_query=row["user_query"],
                    user_id=row.get("user_id"),
                    session_memory=row.get("session_memory") or [],
                )
            )
        return results
