"""Response-generation context helpers: structured-state block, XML track item,
and a metadata-echo guard.

Used by `CRS_BASELINE.batch_chat` when `response_kwargs` enable state-conditioning
and/or the XML item format (e.g. the Blind-A config). Kept independent of the
bake-off package so the production response path has no dev-only dependency.

Validated Blind-A response setup: state-conditioned input + XML track item
(<=10 tags) + role+goal "track explainer" prompt + profile. Phase 2 packaging
uses the `phase2_best_qwen` respgen alias; see
docs/research/2026-06-22-phase2-response-template-findings.md.
"""
from __future__ import annotations

from typing import Any, Callable


PHASE2_BEST_QWEN_STYLE = (
    "Write 1-2 concise sentences about only the selected track. "
    "Prioritize the latest user request and extracted state over older conversation history. "
    "If the track is reasonably aligned, explain the fit with one specific supported reason. "
    "If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it "
    "or blame the system; briefly frame the limitation and the closest supported reason."
)

RESPONSE_TEMPLATE_DEFAULTS: dict[str, dict[str, Any]] = {
    "phase2_best_qwen": {
        "conditioning": "latest_state",
        "item_format": "xml",
        "max_tags": 10,
        "echo_retries": 0,
        "style": PHASE2_BEST_QWEN_STYLE,
    },
}


def _first(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return str(value[0]).strip() if value else ""
    return str(value).strip() if value is not None else ""


def _esc(x: Any) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def xml_track_item(meta: dict | None, track_id: str = "", max_tags: int = 10) -> str:
    """Render a track as a delimited <recommended_track> block with capped tags.

    The XML delimiting + tag cap stop the model from echoing the raw metadata
    blob verbatim (a failure mode observed with the pipe-delimited string)."""
    meta = meta or {}
    if not meta:
        return f"<recommended_track>\n  <track_id>{_esc(track_id)}</track_id>\n</recommended_track>"
    tags = [str(t) for t in (meta.get("tag_list") or []) if t][:max_tags]
    return (
        "<recommended_track>\n"
        f"  <title>{_esc(_first(meta.get('track_name')))}</title>\n"
        f"  <artist>{_esc(_first(meta.get('artist_name')))}</artist>\n"
        f"  <album>{_esc(_first(meta.get('album_name')))}</album>\n"
        f"  <tags>{_esc(', '.join(tags))}</tags>\n"
        "</recommended_track>"
    )


def resolve_response_kwargs(response_kwargs: dict[str, Any] | None) -> dict[str, Any]:
    """Expand named response template defaults, with explicit kwargs winning."""
    raw = dict(response_kwargs or {})
    template = raw.get("template")
    if not template:
        return raw
    if template not in RESPONSE_TEMPLATE_DEFAULTS:
        allowed = ", ".join(sorted(RESPONSE_TEMPLATE_DEFAULTS))
        raise ValueError(f"Unknown response template {template!r}. Allowed: {allowed}")
    return {**RESPONSE_TEMPLATE_DEFAULTS[template], **raw}


def _nested_get(mapping: dict[str, Any] | None, key: str) -> Any:
    return mapping.get(key) if isinstance(mapping, dict) else None


def format_latest_state_context(
    session_meta: dict[str, Any] | None,
    latest_user: str,
    state: dict | None,
    track_label: Callable[[str], str] | None = None,
) -> str:
    """Render the Phase-2 response context: goal/language/latest request + state."""
    session_meta = session_meta if isinstance(session_meta, dict) else {}
    lines = ["[LISTENER CONTEXT]"]
    goal = _nested_get(_nested_get(session_meta, "conversation_goal"), "listener_goal")
    if goal:
        lines.append(f"Listener goal: {goal}")
    language = _nested_get(_nested_get(session_meta, "user_profile"), "preferred_language")
    if language:
        lines.append(f"Preferred language: {language}")
    if latest_user:
        lines.append(f"Latest user request: {latest_user}")
    lines.append(format_state_block(state, track_label))
    return "\n".join(lines)


def format_state_block(state: dict | None, track_label: Callable[[str], str] | None = None) -> str:
    """Render a compact [LISTENER CONTEXT] block from a ConversationStateV0Plus dict.

    `track_label(track_id) -> str` resolves accepted/rejected feedback tracks to a
    human-readable label (extracts the track_name from metadata)."""
    if not state:
        return "[LISTENER CONTEXT]\n(unavailable)"

    def label(tid: str) -> str:
        if track_label is None:
            return tid
        s = track_label(tid) or tid
        # Extract track_name from multi-line metadata format (field: value\n...)
        # or pipe-delimited format (field | field) for backwards compatibility.
        if "\n" in s:
            # Multi-line format: extract the line that starts with "track_name:"
            for line in s.split("\n"):
                if line.startswith("track_name:"):
                    return line.split(":", 1)[1].strip()
            # Fallback: use first non-empty line
            for line in s.split("\n"):
                stripped = line.strip()
                if stripped and not stripped.startswith("track_id:"):
                    return stripped.split(":", 1)[-1].strip()
            return tid
        # Pipe-delimited format: trim to avoid echoing metadata beyond the first field
        # Format: "field: value | field: value | ..." -> extract just "field: value"
        return s.split(" | ")[0]

    lines = ["[LISTENER CONTEXT]"]
    ti = state.get("turn_intent")
    if ti:
        lines.append(f"Current request: {ti}")

    ents = state.get("mentioned_entities") or []
    liked = [e["value"] for e in ents if (e.get("sentiment") or 0) > 0]
    disliked = [e["value"] for e in ents if (e.get("sentiment") or 0) < 0]

    fb = state.get("track_feedback") or []
    liked += [label(t["track_id"]) for t in fb if t.get("role") == "accepted"]
    disliked += [label(t["track_id"]) for t in fb if t.get("role") == "rejected"]

    if liked:
        lines.append("Liked / wants: " + ", ".join(dict.fromkeys(liked)))
    if disliked:
        lines.append("Disliked / avoid: " + ", ".join(dict.fromkeys(disliked)))

    er = state.get("explicit_rejections") or []
    if er:
        lines.append("Explicit rejections: " + ", ".join(f"{x.get('kind')}:{x.get('value')}" for x in er))

    yr = state.get("release_year_range")
    if yr and (yr.get("start") or yr.get("end")):
        lines.append(f"Release year range: {yr.get('start')}-{yr.get('end')}")

    lt = state.get("lyrical_theme")
    if lt:
        lines.append(f"Lyrical theme: {lt}")

    return "\n".join(lines)


def response_state_dict(state: Any) -> dict:
    """Serialize a ConversationStateV0Plus for the response path.

    pydantic's ``model_dump()`` only serializes declared fields, so derived
    ``@property`` fields are dropped. This augments the dump with fields the
    response prompt consumes (for example ``mentioned_entities``) plus compiler
    policy fields used by trace/compiled-state diagnostics and reranker
    feature extraction. Duck-typed (no schema import) so this module stays
    dependency-free.

    The result carries keys beyond the model's declared fields, so it is for the
    response / trace path only — do NOT round-trip it back through
    ``ConversationStateV0Plus.model_validate`` (``extra="forbid"`` would reject
    the augmented keys).
    """
    d = state.model_dump(mode="json")
    d["mentioned_entities"] = [m.model_dump(mode="json") for m in state.mentioned_entities]
    d["explicit_rejections"] = [r.model_dump(mode="json") for r in state.explicit_rejections]
    ryr = state.release_year_range
    d["release_year_range"] = ryr.model_dump(mode="json") if ryr is not None else None
    d["intent_mode"] = getattr(state.intent_mode, "value", str(state.intent_mode))
    d["process_constraints"] = state.process_constraints.model_dump(mode="json")
    d["routing_tags"] = state.routing_tags.model_dump(mode="json")
    d["hard_filters"] = [f.model_dump(mode="json") for f in state.hard_filters]
    return d


def is_metadata_echo(text: str) -> bool:
    """True when the model parroted the track metadata (or returned nothing) —
    used to trigger a regeneration."""
    t = (text or "").strip().lower()
    return (not t) or t.startswith("title:") or "<recommended_track" in t or " | tags:" in t[:160]
