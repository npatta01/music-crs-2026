#!/usr/bin/env python
"""Extract ConversationState for a configured set of sessions.

Usage:
  python scripts/extract_state.py --tid v0plus_compiler_ollama_state \
    --sessions-file data/local_sessions.json

  python scripts/extract_state.py --config configs/local_state.yaml \
    --sessions-file data/local_sessions.json --output exp/state/local_state.jsonl

  python scripts/extract_state.py --tid state_ranker_v10_lgbm_blindset_B \
    --turn-scope final --output-dir cache/state_extraction/blindset_B \
    --skip-existing

The sessions file may be either {"session_ids": ["..."]} or a JSON list of
session ids. Model/provider/cache settings come from the config.

For non-Ollama local LiteLLM providers, set qu_kwargs.extractor.api_key: "" to
avoid falling back to LITELLM_PROXY_KEY.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from datasets import load_dataset

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEST_DATASET = "talkpl-ai/TalkPlayData-Challenge-Dataset"
DEFAULT_METADATA_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
DEFAULT_OLLAMA_API_BASE = "http://localhost:11434"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcrs.litellm_cache import setup_litellm_cache  # noqa: E402
from mcrs.conversation_state.schema import ConversationStateV0Plus  # noqa: E402
from mcrs.qu_modules.compiler_qu import (  # noqa: E402
    LiteLLMExtractor,
    extract_with_cache_context,
)
from mcrs.qu_modules.state_cache import state_cache_file_path  # noqa: E402


def _load_dotenv() -> None:
    dotenv_path = PROJECT_ROOT / ".env"
    if not dotenv_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path)
    except Exception:
        pass


@dataclass(frozen=True)
class ExtractionCase:
    session_id: str
    turn_number: int
    conversation: list[dict[str, Any]]
    played_track_ids: list[str]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    config = parser.add_mutually_exclusive_group(required=True)
    config.add_argument("--tid", help="Task id matching configs/{tid}.yaml.")
    config.add_argument("--config", help="Path to an explicit YAML config.")
    parser.add_argument(
        "--config-dir",
        default=str(PROJECT_ROOT / "configs"),
        help="Directory used with --tid. Defaults to repo configs/.",
    )
    parser.add_argument(
        "--sessions-file",
        help='JSON list or object with "session_ids".',
    )
    parser.add_argument(
        "--output",
        help="Optional JSONL output path. Without --output or state_extraction.output_path, writes file-per-turn JSON under cache/state_extraction/<name>/.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for file-per-turn JSON output. Defaults to cache/state_extraction/<name>/ when --output is not set.",
    )
    parser.add_argument(
        "--turn-scope",
        choices=("all", "final"),
        default="all",
        help="Which user turns to extract per selected session. Defaults to all.",
    )
    parser.add_argument(
        "--litellm-cache-only",
        action="store_true",
        help="Read existing LiteLLM cache entries only; never make live provider calls.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="For file-per-turn output, reuse valid existing turn files and only extract missing turns.",
    )
    return parser


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        from omegaconf import OmegaConf

        raw = OmegaConf.to_container(OmegaConf.load(path), resolve=True) or {}
    except ModuleNotFoundError:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config at {path} must be a YAML object")
    return raw


def load_config(
    *,
    config_path: str | os.PathLike[str] | None,
    tid: str | None,
    config_dir: str | os.PathLike[str],
) -> dict[str, Any]:
    if config_path:
        path = Path(config_path)
    elif tid:
        path = Path(config_dir) / f"{tid}.yaml"
    else:
        raise ValueError("Provide --config or --tid")
    if not path.exists():
        raise FileNotFoundError(f"No config found at {path}")
    config = _load_yaml(path)
    config["_state_extraction_config_path"] = str(path)
    config["_state_extraction_name"] = tid or path.stem
    return config


def load_session_ids(path: str | os.PathLike[str] | None) -> set[str] | None:
    if path is None:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("session_ids")
    if not isinstance(data, list):
        raise ValueError("sessions file must be a JSON list or contain session_ids")
    session_ids = {str(item) for item in data if str(item).strip()}
    if not session_ids:
        raise ValueError("sessions file did not contain any session ids")
    return session_ids


def _state_cfg(config: dict[str, Any]) -> dict[str, Any]:
    value = config.get("state_extraction") or {}
    if not isinstance(value, dict):
        raise ValueError("state_extraction must be a mapping when present")
    return value


def _extractor_cfg(config: dict[str, Any]) -> dict[str, Any]:
    qu_kwargs = config.get("qu_kwargs") or {}
    if not isinstance(qu_kwargs, dict):
        return {}
    extractor = qu_kwargs.get("extractor") or {}
    if not isinstance(extractor, dict):
        return {}
    return dict(extractor)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "EMPTY", "NONE", "None", "null"}:
        return None
    return text


def _is_ollama_model(model_name: str) -> bool:
    return model_name.startswith("ollama/") or model_name.startswith("ollama_chat/")


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def extractor_config_from_config(
    config: dict[str, Any],
    *,
    litellm_cache_only: bool = False,
) -> dict[str, Any]:
    raw = _extractor_cfg(config)
    model_name = str(raw.get("model_name", "openrouter/google/gemma-3-12b-it"))
    api_base = _optional_text(raw.get("api_base"))
    if api_base is None and _is_ollama_model(model_name):
        api_base = DEFAULT_OLLAMA_API_BASE

    if "api_key" in raw:
        api_key = _optional_text(raw.get("api_key"))
    elif _is_ollama_model(model_name):
        api_key = None
    else:
        # Non-Ollama local providers can set `api_key: ""` in config to opt out
        # of the proxy-key fallback while keeping cloud/proxy configs unchanged.
        api_key = _optional_text(os.environ.get("LITELLM_PROXY_KEY"))

    return {
        "model_name": model_name,
        "api_base": api_base,
        "api_key": api_key,
        "temperature": float(raw.get("temperature", 0.0)),
        "max_tokens": int(raw.get("max_tokens", 1500)),
        "timeout_s": int(raw.get("timeout_s", 90)),
        "prompt_version": str(raw.get("prompt_version", "v1")),
        "retry_temperature": float(raw.get("retry_temperature", 0.3)),
        "extra_params": dict(raw.get("extra_params") or {}),
        "litellm_cache_only": _truthy(raw.get("litellm_cache_only")) or litellm_cache_only,
        # This script creates the file-per-turn state cache, so it must not read
        # from the same cache while generating raw extraction artifacts.
        "state_cache": {},
    }


def build_extractor(config: dict[str, Any]) -> LiteLLMExtractor:
    return LiteLLMExtractor(
        model_name=config["model_name"],
        api_base=config.get("api_base"),
        api_key=config.get("api_key"),
        temperature=float(config.get("temperature", 0.0)),
        max_tokens=int(config.get("max_tokens", 1500)),
        timeout_s=int(config.get("timeout_s", 90)),
        prompt_version=str(config.get("prompt_version", "v1")),
        retry_temperature=float(config.get("retry_temperature", 0.3)),
        extra_params=dict(config.get("extra_params") or {}),
        state_cache=dict(config.get("state_cache") or {}),
        litellm_cache_only=_truthy(config.get("litellm_cache_only")),
    )


def _first(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return str(value[0]).strip() if value else ""
    return str(value).strip() if value is not None else ""


def _track_label(row: dict[str, Any]) -> str:
    artist = _first(row.get("artist_name")) or "?"
    track = _first(row.get("track_name")) or row.get("track_id") or "?"
    return f"{artist} - {track}"


def load_track_labels(config: dict[str, Any]) -> dict[str, str]:
    state_cfg = _state_cfg(config)
    catalog_cfg = (config.get("qu_kwargs") or {}).get("catalog") or {}
    dataset_name = (
        state_cfg.get("metadata_dataset")
        or catalog_cfg.get("metadata_dataset")
        or DEFAULT_METADATA_DATASET
    )
    split = (
        state_cfg.get("metadata_split")
        or catalog_cfg.get("metadata_split")
        or "all_tracks"
    )
    rows = load_dataset(str(dataset_name), split=str(split))
    return {str(row["track_id"]): _track_label(row) for row in rows if row.get("track_id")}


def _conversation_for_turn(
    conversations: Iterable[dict[str, Any]],
    target_turn_number: int,
    track_labels: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str]]:
    out: list[dict[str, Any]] = []
    played: list[str] = []
    for message in conversations:
        turn_number = message.get("turn_number")
        role = message.get("role")
        if turn_number is None or role is None:
            continue
        turn_number = int(turn_number)
        if turn_number > target_turn_number:
            break
        if role == "user":
            out.append(
                {
                    "turn": turn_number,
                    "role": "user",
                    "text": str(message.get("content", "") or ""),
                }
            )
            if turn_number == target_turn_number:
                break
        elif role == "assistant":
            out.append(
                {
                    "turn": turn_number,
                    "role": "assistant",
                    "text": str(message.get("content", "") or ""),
                }
            )
        elif role == "music":
            track_id = str(message.get("content", "") or "")
            if not track_id:
                continue
            played.append(track_id)
            out.append(
                {
                    "turn": turn_number,
                    "role": "music",
                    "track_id": track_id,
                    "label": track_labels.get(track_id, track_id),
                }
            )
    return out, played


def build_extraction_cases(
    dataset: Iterable[dict[str, Any]],
    *,
    session_ids: set[str] | None,
    track_labels: dict[str, str],
    turn_scope: str = "all",
) -> list[ExtractionCase]:
    if turn_scope not in {"all", "final"}:
        raise ValueError(f"turn_scope must be 'all' or 'final'; got {turn_scope!r}")
    cases: list[ExtractionCase] = []
    for session in dataset:
        session_id = str(session.get("session_id", ""))
        if session_ids is not None and session_id not in session_ids:
            continue
        conversations = list(session.get("conversations") or [])
        turn_numbers = sorted(
            {
                int(message["turn_number"])
                for message in conversations
                if message.get("role") == "user" and message.get("turn_number") is not None
            }
        )
        if turn_scope == "final" and turn_numbers:
            turn_numbers = [turn_numbers[-1]]
        for turn_number in turn_numbers:
            conversation, played = _conversation_for_turn(
                conversations,
                turn_number,
                track_labels,
            )
            if conversation:
                cases.append(
                    ExtractionCase(
                        session_id=session_id,
                        turn_number=turn_number,
                        conversation=conversation,
                        played_track_ids=played,
                    )
                )
    return cases


def _resolve_project_path(path: str | os.PathLike[str]) -> Path:
    out = Path(path)
    if out.is_absolute():
        return out
    return PROJECT_ROOT / out


def _output_path(args: argparse.Namespace, config: dict[str, Any]) -> Path:
    if args.output:
        return _resolve_project_path(args.output)
    state_cfg = _state_cfg(config)
    if state_cfg.get("output_path"):
        return _resolve_project_path(str(state_cfg["output_path"]))
    name = str(config.get("_state_extraction_name") or "state_extraction")
    return PROJECT_ROOT / "exp" / "state_extraction" / f"{name}.jsonl"


def _output_dir(args: argparse.Namespace, config: dict[str, Any]) -> Path:
    if getattr(args, "output_dir", None):
        return _resolve_project_path(str(args.output_dir))
    state_cfg = _state_cfg(config)
    if state_cfg.get("output_dir"):
        return _resolve_project_path(str(state_cfg["output_dir"]))
    name = str(config.get("_state_extraction_name") or "state_extraction")
    return PROJECT_ROOT / "cache" / "state_extraction" / name


def _setup_cache(config: dict[str, Any]) -> None:
    state_cfg = _state_cfg(config)
    if "cache_dir" in state_cfg:
        cache_dir = _optional_text(state_cfg.get("cache_dir"))
    else:
        cache_dir = _optional_text(os.environ.get("MCRS_LITELLM_CACHE_DIR")) or "cache/litellm-state"
    if not cache_dir:
        return
    cache_backend = _optional_text(state_cfg.get("cache_backend")) or os.environ.get(
        "MCRS_LITELLM_CACHE_BACKEND",
        "file",
    )
    cache_path = str(_resolve_project_path(cache_dir))
    if setup_litellm_cache(backend=cache_backend, cache_dir=cache_path):
        print(f"LiteLLM {cache_backend} cache enabled at: {cache_path}", file=sys.stderr)


def _dataset_name(config: dict[str, Any]) -> str:
    return str(_state_cfg(config).get("dataset_name") or config.get("test_dataset_name") or DEFAULT_TEST_DATASET)


def _dataset_split(config: dict[str, Any]) -> str:
    return str(_state_cfg(config).get("split") or "test")


def _row_for_result(
    case: ExtractionCase,
    state,
    error: str | None,
) -> dict[str, Any]:
    return {
        "session_id": case.session_id,
        "turn_number": case.turn_number,
        "state": state.model_dump(mode="json") if state is not None else None,
        "error": error,
    }


def _cache_context(case: ExtractionCase) -> dict[str, Any]:
    return {"session_id": case.session_id, "turn_number": case.turn_number}


def _existing_file_row(root: Path, case: ExtractionCase) -> dict[str, Any] | None:
    path = state_cache_file_path(
        root,
        session_id=case.session_id,
        turn_number=case.turn_number,
    )
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("state"), dict):
            return None
        state = ConversationStateV0Plus.model_validate(payload["state"])
    except Exception:
        return None
    return {
        "session_id": case.session_id,
        "turn_number": case.turn_number,
        "state": state.model_dump(mode="json"),
        "error": None,
    }


def _write_jsonl_output(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_file_output(root: Path, rows: list[dict[str, Any]]) -> int:
    written = 0
    for row in rows:
        if row.get("state") is None:
            continue
        path = state_cache_file_path(
            root,
            session_id=row["session_id"],
            turn_number=row["turn_number"],
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written += 1
    return written


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    _load_dotenv()
    config = load_config(
        config_path=args.config,
        tid=args.tid,
        config_dir=args.config_dir,
    )
    if getattr(args, "output", None) and getattr(args, "output_dir", None):
        raise ValueError("Use --output for JSONL or --output-dir for file output, not both")
    write_jsonl = bool(getattr(args, "output", None)) or (
        not getattr(args, "output_dir", None)
        and bool(_state_cfg(config).get("output_path"))
    )
    output_dir = None if write_jsonl else _output_dir(args, config)
    skip_existing = bool(getattr(args, "skip_existing", False)) and output_dir is not None
    _setup_cache(config)
    extractor = build_extractor(
        extractor_config_from_config(
            config,
            litellm_cache_only=bool(getattr(args, "litellm_cache_only", False)),
        )
    )
    session_ids = load_session_ids(getattr(args, "sessions_file", None))
    dataset = load_dataset(_dataset_name(config), split=_dataset_split(config))
    track_labels = load_track_labels(config)
    cases = build_extraction_cases(
        dataset,
        session_ids=session_ids,
        track_labels=track_labels,
        turn_scope=str(getattr(args, "turn_scope", "all")),
    )
    if not cases:
        raise ValueError("No extraction cases found for requested sessions")

    rows: list[dict[str, Any]] = []
    for case in cases:
        if skip_existing and output_dir is not None:
            existing = _existing_file_row(output_dir, case)
            if existing is not None:
                rows.append(existing)
                continue
        try:
            state = extract_with_cache_context(
                extractor,
                case.conversation,
                case.played_track_ids,
                cache_context=_cache_context(case),
            )
            if state is None:
                rows.append(_row_for_result(case, None, "extractor returned None"))
            else:
                rows.append(_row_for_result(case, state, None))
        except Exception as exc:
            rows.append(_row_for_result(case, None, f"{type(exc).__name__}: {exc}"))

    if write_jsonl:
        output_path = _output_path(args, config)
        _write_jsonl_output(output_path, rows)
        print(f"Wrote {len(rows)} state rows to {output_path}", file=sys.stderr)
    else:
        assert output_dir is not None
        written = _write_file_output(output_dir, rows)
        skipped = len(rows) - written
        suffix = f" (skipped {skipped} error rows)" if skipped else ""
        print(f"Wrote {written} state files to {output_dir}{suffix}", file=sys.stderr)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except Exception as exc:
        print(f"extract_state failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
