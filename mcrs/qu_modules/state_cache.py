"""File-per-turn cache for extracted conversation state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydantic import ValidationError

from mcrs.conversation_state.schema import ConversationStateV0Plus


class StateCacheError(RuntimeError):
    """Raised when a state cache file exists but cannot be used."""

    def __init__(self, message: str, *, source: str, path: Path | None = None):
        super().__init__(message)
        self.source = source
        self.path = path


@dataclass(frozen=True)
class StateCacheHit:
    state: ConversationStateV0Plus
    source: str
    path: Path


def _safe_path_component(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty path component")
    return quote(text, safe="-_.")


def state_cache_file_path(
    root: str | Path,
    *,
    session_id: Any,
    turn_number: Any,
    override: bool = False,
) -> Path:
    session_component = _safe_path_component(session_id)
    try:
        turn = int(turn_number)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid turn_number for state cache: {turn_number!r}") from exc
    if turn < 0:
        raise ValueError(f"invalid turn_number for state cache: {turn_number!r}")
    suffix = "_override" if override else ""
    return Path(root) / session_component / f"turn_{turn}{suffix}.json"


class FilePerTurnStateCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "FilePerTurnStateCache | None":
        if not isinstance(config, dict) or not config.get("enabled"):
            return None
        mode = str(config.get("mode", "file_per_turn"))
        if mode != "file_per_turn":
            raise ValueError(f"unsupported state_cache.mode: {mode!r}")
        directory = config.get("dir")
        if not directory:
            raise ValueError("state_cache.dir is required when state_cache is enabled")
        return cls(directory)

    def load(self, context: dict[str, Any] | None) -> StateCacheHit | None:
        if not isinstance(context, dict):
            return None
        session_id = context.get("session_id")
        turn_number = context.get("turn_number")
        if session_id is None or turn_number is None:
            return None

        override = state_cache_file_path(
            self.root,
            session_id=session_id,
            turn_number=turn_number,
            override=True,
        )
        original = state_cache_file_path(
            self.root,
            session_id=session_id,
            turn_number=turn_number,
        )
        if override.exists():
            return StateCacheHit(
                state=self._load_state(override, source="override"),
                source="override",
                path=override,
            )
        if original.exists():
            return StateCacheHit(
                state=self._load_state(original, source="original"),
                source="original",
                path=original,
            )
        return None

    def _load_state(self, path: Path, *, source: str) -> ConversationStateV0Plus:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StateCacheError(
                f"{source} state cache file could not be read: {path}: {type(exc).__name__}: {exc}",
                source=source,
                path=path,
            ) from exc
        if not isinstance(payload, dict) or "state" not in payload:
            raise StateCacheError(
                f"{source} state cache file must contain a top-level 'state': {path}",
                source=source,
                path=path,
            )
        try:
            return ConversationStateV0Plus.model_validate(payload["state"])
        except ValidationError as exc:
            raise StateCacheError(
                f"{source} state cache file has invalid state: {path}: {exc}",
                source=source,
                path=path,
            ) from exc
