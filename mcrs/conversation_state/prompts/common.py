"""Shared helpers for ConversationState extractor prompts."""

from __future__ import annotations

from typing import Any


def render_conversation(conversation: list[dict[str, Any]], played_track_ids: list[str]) -> str:
    """Render the conversation as a compact text block the extractor can read.

    Music turns use a 1-indexed marker `#M` that maps to
    `played_track_ids[M-1]`. The raw UUID is listed once in the header, not
    repeated on every music line.
    """
    lines = ["played_track_ids:"]
    for idx, tid in enumerate(played_track_ids, start=1):
        lines.append(f"  #{idx}: {tid}")
    if not played_track_ids:
        lines.append("  (none yet)")
    lines.extend(["", "conversation:"])

    music_idx = 0
    for turn in conversation:
        role = turn.get("role")
        if role == "music":
            music_idx += 1
            label = turn.get("label", "")
            label_part = f" ({label})" if label else ""
            lines.append(f"  [turn {turn['turn']}] music: #{music_idx}{label_part}")
        else:
            text = turn.get("text", "").strip()
            lines.append(f"  [turn {turn['turn']}] {role}: {text}")
    return "\n".join(lines)


def harden_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Patch a Pydantic schema for strict JSON-schema response_format hosts."""

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            if "$ref" in node:
                for key in list(node.keys()):
                    if key != "$ref":
                        node.pop(key)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return schema


def strip_schema_annotations(node: Any) -> Any:
    """Strip schema annotations rejected by some strict-mode providers."""
    if isinstance(node, dict):
        node.pop("$comment", None)
        for value in node.values():
            strip_schema_annotations(value)
    elif isinstance(node, list):
        for value in node:
            strip_schema_annotations(value)
    return node
