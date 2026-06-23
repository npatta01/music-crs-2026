from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from mcrs.response_context import format_state_block, xml_track_item


@dataclass(frozen=True)
class SelectedTrack:
    track_id: str | None
    track_ids: list[str]
    changed: bool
    reason: str


def _first(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return str(value[0]).strip() if value else ""
    return str(value).strip() if value is not None else ""


def _norm(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"^[\"'“”‘’*\s]+|[\"'“”‘’*\s]+$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def load_predictions(path: str | Path) -> list[dict[str, Any]]:
    """Load CodaBench prediction rows from either a JSON file or a zip."""
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            if "prediction.json" not in zf.namelist():
                raise ValueError(f"{path} does not contain prediction.json")
            return json.loads(zf.read("prediction.json"))
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_traces(path: str | Path) -> dict[tuple[str, int], dict[str, Any]]:
    """Load a JSONL trace sidecar keyed by ``(session_id, turn_number)``."""
    path = Path(path)
    traces: dict[tuple[str, int], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            traces[(row["session_id"], int(row["turn_number"]))] = row
    return traces


def write_predictions(rows: Sequence[dict[str, Any]], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(list(rows), handle, ensure_ascii=False, indent=2)


def write_submission_zip(rows: Sequence[dict[str, Any]], zip_path: str | Path) -> None:
    """Write the single-file CodaBench zip format."""
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(list(rows), ensure_ascii=False, separators=(",", ":"))
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("prediction.json", payload)


def _tokens(text: str) -> list[str]:
    return str(text or "").lower().split()


def distinct_n(responses: Iterable[str], n: int = 2) -> float:
    """Evaluator-style Distinct-n over whitespace tokens."""
    total = 0
    unique: set[tuple[str, ...]] = set()
    for response in responses:
        toks = _tokens(response)
        if len(toks) < n:
            continue
        grams = [tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)]
        total += len(grams)
        unique.update(grams)
    return (len(unique) / total) if total else 0.0


_AVOID_PATTERNS = (
    re.compile(r"\bno more\s+(.+?)(?:\s+for now|\s+this time|[.!?,;]|$)", re.I),
    re.compile(r"\bmove beyond\s+(.+?)(?:[.!?,;]|$)", re.I),
    re.compile(r"\bbeyond\s+(.+?)(?:[.!?,;]|$)", re.I),
    re.compile(r"\bother than\s+(.+?)(?:[.!?,;]|$)", re.I),
    re.compile(r"\bavoid\s+(.+?)(?:[.!?,;]|$)", re.I),
    re.compile(r"\bnot\s+(.+?)(?:\s+this time|\s+again)", re.I),
)


def extract_avoid_hints(text: str) -> set[str]:
    """Extract simple surface hints for artists/entities the user wants to avoid."""
    hints: set[str] = set()
    for pattern in _AVOID_PATTERNS:
        for match in pattern.finditer(text or ""):
            for raw_part in re.split(r"/|\bor\b|\band\b", match.group(1), flags=re.I):
                value = _norm(raw_part)
                value = re.sub(r"\b(?:please|thanks|artist|artists|track|tracks|song|songs)\b", "", value)
                value = _norm(value)
                if value and len(value) > 1:
                    hints.add(value)
    return hints


def _artist_for(track_id: str, metadata_by_id: dict[str, dict[str, Any]]) -> str:
    return _first((metadata_by_id.get(track_id) or {}).get("artist_name"))


def _track_label(track_id: str, metadata_by_id: dict[str, dict[str, Any]]) -> str:
    meta = metadata_by_id.get(track_id) or {}
    title = _first(meta.get("track_name")) or track_id
    artist = _first(meta.get("artist_name"))
    return f"{title} — {artist}" if artist else title


def _artist_is_avoided(artist: str, avoid_hints: set[str]) -> bool:
    artist_norm = _norm(artist)
    if not artist_norm:
        return False
    return any(hint in artist_norm or artist_norm in hint for hint in avoid_hints)


def select_response_track(
    track_ids: Sequence[str],
    metadata_by_id: dict[str, dict[str, Any]],
    avoid_hints: set[str],
    *,
    promote: bool = False,
    search_topk: int = 20,
) -> SelectedTrack:
    """Pick the track the response should introduce.

    By default this does not reorder submitted IDs; set ``promote=True`` only for
    an explicit retrieval-affecting variant.
    """
    original = list(track_ids)
    if not original:
        return SelectedTrack(None, [], False, "empty_track_ids")
    selected = original[0]
    reason = "top1"
    if avoid_hints:
        for candidate in original[:search_topk]:
            artist = _artist_for(candidate, metadata_by_id)
            if not _artist_is_avoided(artist, avoid_hints):
                selected = candidate
                reason = "skipped_avoided_top_artist" if candidate != original[0] else "top1_safe"
                break
    changed = selected != original[0]
    out_ids = list(original)
    if promote and changed:
        out_ids = [selected] + [tid for tid in original if tid != selected]
    return SelectedTrack(selected, out_ids, changed, reason)


def _latest_user(conversations: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    for turn in reversed(conversations):
        if turn.get("role") == "user":
            return turn
    return None


def _previous_user(conversations: Sequence[dict[str, Any]], latest_turn_number: int | None) -> dict[str, Any] | None:
    candidates = [
        turn
        for turn in conversations
        if turn.get("role") == "user"
        and (latest_turn_number is None or turn.get("turn_number", -1) < latest_turn_number)
    ]
    return candidates[-1] if candidates else None


def render_context(
    dataset_row: dict[str, Any],
    variant_flags: dict[str, Any] | None = None,
    *,
    track_label: Callable[[str], str] | None = None,
) -> str:
    """Render response context available from the Blind-A row, without traces."""
    flags = variant_flags or {}
    conversations = list(dataset_row.get("conversations") or [])
    latest = _latest_user(conversations)
    latest_turn_number = latest.get("turn_number") if latest else None
    previous = _previous_user(conversations, latest_turn_number)
    lines = ["[LISTENER CONTEXT]"]

    if flags.get("listener_goal"):
        goal = (dataset_row.get("conversation_goal") or {}).get("listener_goal")
        if goal:
            lines.append(f"Listener goal: {goal}")
    if flags.get("preferred_language"):
        language = (dataset_row.get("user_profile") or {}).get("preferred_language")
        if language:
            lines.append(f"Preferred language: {language}")
    if flags.get("previous_user") and previous:
        lines.append(f"Previous user request: {previous.get('content', '')}")
    if flags.get("latest_user", True) and latest:
        lines.append(f"Latest user request: {latest.get('content', '')}")
    if flags.get("prior_music") and track_label:
        labels = [
            track_label(turn.get("content"))
            for turn in conversations
            if turn.get("role") == "music" and turn.get("content")
        ]
        labels = [label for label in labels if label]
        if labels:
            lines.append("Prior recommendations: " + "; ".join(labels[-4:]))
    return "\n".join(lines)


_CONSTRAINT_CONFESSION_RE = re.compile(
    r"(asked to avoid|specifically asked to avoid|looking to move beyond|by the artist you|sorry,\s*but that track|let me find something else)",
    re.I,
)
_OVERCONFIDENT_RE = re.compile(r"\b(perfect match|perfect fit|fits .* exactly|exactly|you'?re in luck|perfect)\b", re.I)
_GENERIC_WORD_RE = re.compile(r"\b(vibe|energy|mood|feel|perfect|classic|timeless|journey|standout)\b", re.I)
_QUEUE_RE = re.compile(r"\b(lined up|queue|playlist|first[, ]+try|first of|few options|some songs|several options)\b", re.I)
_GENERIC_FOLLOWUP_RE = re.compile(r"\?\s*$|\b(want more|want me|keep exploring|similar or|more tracks|next direction)\b", re.I)
_APOLOGY_CONFESSION_RE = re.compile(r"\b(sorry|bad recommendation|doesn'?t match|not the cleanest|not really|actually not)\b", re.I)


def _title_from_label(label: str) -> str:
    return _norm(str(label or "").split(" — ", 1)[0])


def _base_title(title: str) -> str:
    title = _norm(title)
    suffix = r"(?:original\s+mix|radio\s+edit|single\s+edit|album\s+version|remaster(?:ed)?(?:\s+\d{4})?|.*?remix|.*?mix|.*?version)"
    title = re.sub(rf"\s+[-–]\s+{suffix}$", "", title)
    title = re.sub(rf"\s+[\[(]{suffix}[\])]\s*$", "", title)
    return _norm(title)


def _quoted_titles(text: str) -> set[str]:
    titles: set[str] = set()
    for match in re.finditer(r"[\"“”']([^\"“”']{2,120})[\"“”']", text or ""):
        titles.add(_norm(match.group(1)))
    for match in re.finditer(r"\*([^*]{2,120})\*", text or ""):
        titles.add(_norm(match.group(1)))
    return {title for title in titles if title}


def response_risk_flags(row: dict[str, Any], top_track_label: str = "") -> dict[str, bool]:
    """Surface response risks for top-1 explanation work.

    These are diagnostics, not a hidden score. In particular, not asking a
    follow-up is intentionally not a risk.
    """
    response = row.get("predicted_response") or row.get("response") or ""
    top_title = _title_from_label(top_track_label)
    top_base_title = _base_title(top_title)
    quoted_titles = _quoted_titles(response)
    response_norm = _norm(response)
    names_a_track = bool(re.search(r"\b(try|recommend|playing|here'?s|start with|go with)\b", response, re.I))
    mentions_top = bool(
        top_title
        and (
            top_title in response_norm
            or (top_base_title and len(top_base_title) >= 4 and top_base_title in response_norm)
        )
    )
    quoted_top = bool(top_title and (top_title in quoted_titles or top_base_title in quoted_titles))
    possible_non_top = bool(
        top_title
        and not mentions_top
        and (
            (quoted_titles and not quoted_top)
            or names_a_track
        )
    )
    return {
        "playlist_or_queue_framing": bool(_QUEUE_RE.search(response)),
        "generic_followup_question": bool(_GENERIC_FOLLOWUP_RE.search(response)),
        "overclaiming": bool(_OVERCONFIDENT_RE.search(response)),
        "apology_or_confession": bool(_APOLOGY_CONFESSION_RE.search(response)),
        "constraint_confession": bool(_CONSTRAINT_CONFESSION_RE.search(response)),
        "possible_non_top_explanation": possible_non_top,
    }


def heuristic_audit_row(row: dict[str, Any]) -> dict[str, Any]:
    response = row.get("predicted_response") or row.get("response") or ""
    words = response.split()
    generic_count = len(_GENERIC_WORD_RE.findall(response))
    return {
        "constraint_confession": bool(_CONSTRAINT_CONFESSION_RE.search(response)),
        "overconfident": bool(_OVERCONFIDENT_RE.search(response)),
        "long_response": len(words) > 70,
        "generic_word_count": generic_count,
    }


def summarize_audits(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    audits = [heuristic_audit_row(row) for row in rows]
    keys = ["constraint_confession", "overconfident", "long_response"]
    return {
        "n": len(rows),
        **{key: sum(1 for audit in audits if audit[key]) for key in keys},
        "generic_word_count": sum(audit["generic_word_count"] for audit in audits),
    }


def label_for_track(track_id: str, metadata_by_id: dict[str, dict[str, Any]]) -> str:
    return _track_label(track_id, metadata_by_id)


def variant_flags_for_name(name: str) -> dict[str, Any]:
    """Named response variants for the frozen replay script."""
    aliases = {
        # Best observed frozen-retrieval template from the Blind-A response sweep.
        "phase2_best_qwen": "top1_constraint_latest_state_qwen",
    }
    name = aliases.get(name, name)
    variants: dict[str, dict[str, Any]] = {
        "baseline": {
            "latest_user": True,
            "item_format": "xml",
            "max_tags": 10,
        },
        "goal_turn": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "item_format": "xml",
            "max_tags": 10,
        },
        "safe_goal_turn": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "safe_candidate": True,
            "item_format": "xml",
            "max_tags": 10,
        },
        "anchor_replay": {
            "context_mode": "state_only",
            "trace_state": True,
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.7,
            "max_tokens": 2048,
            "echo_retries": 3,
        },
        "top1_concise_qwen": {
            "latest_user": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Name the track and artist, give one specific supported reason it fits, "
                "avoid 'perfect'/'exactly', and do not ask a generic follow-up question."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_context_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Use the listener context only when it directly supports the explanation. "
                "Avoid 'perfect'/'exactly' and do not ask a generic follow-up question."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_honest_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "If the track is reasonably aligned, explain the fit with one specific supported reason. "
                "If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it "
                "or blame the system; briefly frame the limitation and the closest supported reason."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_no_system_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Explain the fit with one specific supported reason. "
                "If the track conflicts with an explicit avoid/new-artist constraint, do not apologize, "
                "mention the system/model/retrieval, or say the recommendation is bad or wrong; "
                "instead frame it as a close fit for one available requested quality."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_no_system_no_overclaim_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Explain the fit with one specific supported reason. "
                "Never use 'perfect', 'exactly', 'signature', 'standout', or broad claims about popularity. "
                "If the track conflicts with an explicit avoid/new-artist constraint, do not apologize, "
                "mention the system/model/retrieval, or say the recommendation is bad or wrong; "
                "instead frame it as a close fit for one available requested quality."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_latest_state_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "latest_user": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Prioritize the latest user request and extracted state over older conversation history. "
                "If the track is reasonably aligned, explain the fit with one specific supported reason. "
                "If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it "
                "or blame the system; briefly frame the limitation and the closest supported reason."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_latest_state_no_goal_qwen": {
            "preferred_language": True,
            "latest_user": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Prioritize the latest user request and extracted state over older conversation history. "
                "If the track is reasonably aligned, explain the fit with one specific supported reason. "
                "If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it "
                "or blame the system; briefly frame the limitation and the closest supported reason."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_latest_state_soft_confident_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "latest_user": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Prioritize the latest user request and extracted state over older conversation history. "
                "Explain the fit with one specific supported reason from the selected track metadata or state. "
                "If there is a clear avoid/new-artist conflict, do not apologize, mention the system/model/retrieval, "
                "or call the recommendation bad; give the strongest supported fit in terms of mood, genre, language, era, or energy."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_latest_state_no_alt_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "latest_user": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Prioritize the latest user request and extracted state over older conversation history. "
                "If the track is reasonably aligned, explain the fit with one specific supported reason. "
                "If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it "
                "or blame the system; briefly frame the limitation and the closest supported reason. "
                "Do not offer to find, play, or recommend any other track, artist, queue, playlist, or next option."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_latest_state_no_alt_no_overclaim_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "latest_user": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Prioritize the latest user request and extracted state over older conversation history. "
                "Explain the fit with one specific supported reason from the selected track metadata or state. "
                "Avoid 'perfect', 'exactly', 'signature', 'standout', and broad unsupported popularity claims. "
                "If it clearly conflicts with an explicit avoid/new-artist constraint, acknowledge the mismatch briefly "
                "without apology or system blame, then give the closest supported reason. "
                "Do not offer to find, play, or recommend any other track, artist, queue, playlist, or next option."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_language_exact_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences in the same language as the user's latest request when it is clear. "
                "Name the selected track and artist from the XML item, and explain only that top track with one supported reason. "
                "If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it "
                "or blame the system; briefly frame the limitation and the closest supported reason."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_close_fit_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "trace_state": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "If the track is reasonably aligned, explain the fit with one specific supported reason. "
                "If it conflicts with an explicit avoid/new-artist constraint, do not apologize, confess, or blame the system; "
                "present it as the closest fit for one requested quality such as mood, genre, language, era, or energy."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_constraint_short_qwen": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "trace_state": True,
            "style": (
                "Write exactly one concise sentence about only the selected track, ideally under 35 words. "
                "Name the track and artist, then give one supported reason it fits. "
                "If it conflicts with an explicit constraint, avoid apology or system blame and state only the closest supported fit."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "top1_concise_alt_model": {
            "latest_user": True,
            "style": (
                "Write 1-2 concise sentences about only the selected track. "
                "Name the track and artist, give one specific supported reason it fits, "
                "avoid 'perfect'/'exactly', and do not ask a generic follow-up question."
            ),
            "item_format": "xml",
            "max_tags": 10,
            "temperature": 0.0,
            "max_tokens": 512,
        },
        "concise_goal_turn": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "style": (
                "Write 1-2 concise sentences. Avoid saying 'perfect' unless the match is literal. "
                "Name the track and artist, give one concrete reason, and invite the next direction."
            ),
            "item_format": "xml",
            "max_tags": 10,
        },
        "safe_concise_goal_turn": {
            "listener_goal": True,
            "preferred_language": True,
            "previous_user": True,
            "latest_user": True,
            "prior_music": True,
            "safe_candidate": True,
            "style": (
                "Write 1-2 concise sentences. Avoid saying 'perfect' unless the match is literal. "
                "Do not confess that the system chose a bad track; choose the safest provided track context, "
                "name the track and artist, give one concrete reason, and invite the next direction."
            ),
            "item_format": "xml",
            "max_tags": 10,
        },
    }
    if name not in variants:
        allowed = ", ".join(sorted(variants))
        raise ValueError(f"Unknown variant {name!r}. Allowed: {allowed}")
    return dict(variants[name])


def _recommend_item_for(
    track_id: str | None,
    metadata_by_id: dict[str, dict[str, Any]],
    flags: dict[str, Any],
) -> str:
    if not track_id:
        return "<recommended_track>\n</recommended_track>"
    if flags.get("item_format", "xml") == "xml":
        return xml_track_item(
            metadata_by_id.get(track_id),
            track_id=track_id,
            max_tags=int(flags.get("max_tags", 10)),
        )
    return _track_label(track_id, metadata_by_id)


def _avoid_hints_from_trace(trace: dict[str, Any] | None) -> set[str]:
    if not isinstance(trace, dict):
        return set()
    state = trace.get("state") or trace.get("extracted_state") or {}
    texts = [state.get("turn_intent") or ""]
    current_request = state.get("current_request")
    if isinstance(current_request, dict):
        texts.append(current_request.get("summary") or "")
    hints: set[str] = set()
    for text in texts:
        hints.update(extract_avoid_hints(text))
    for key in ("explicit_rejections", "rejections", "exclusions"):
        for item in state.get(key) or []:
            if isinstance(item, dict) and item.get("value"):
                hints.add(_norm(str(item["value"])))
    return hints


def build_variant_rows(
    base_rows: Sequence[dict[str, Any]],
    dataset_rows_by_session: dict[str, dict[str, Any]],
    metadata_by_id: dict[str, dict[str, Any]],
    variant_flags: dict[str, Any],
    generate_responses: Callable[[list[dict[str, Any]]], list[str]],
    *,
    promote_response_track: bool = False,
    trace_rows_by_key: dict[tuple[str, int], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build a response-only variant while keeping retrieval IDs frozen by default."""
    if variant_flags.get("safe_candidate") and not promote_response_track:
        raise ValueError("safe_candidate variants must use promote_response_track=True to avoid non-top explanations")
    requests: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []
    for row in base_rows:
        session_id = row["session_id"]
        dataset_row = dataset_rows_by_session.get(session_id)
        if dataset_row is None:
            raise KeyError(f"No dataset row for session_id={session_id}")
        latest = _latest_user(dataset_row.get("conversations") or {})
        latest_text = latest.get("content", "") if latest else ""
        trace_row = None
        trace = None
        if trace_rows_by_key:
            trace_row = trace_rows_by_key.get((session_id, int(row.get("turn_number", 0))))
            trace = (trace_row or {}).get("trace")
        avoid_hints = set()
        if variant_flags.get("safe_candidate"):
            avoid_hints.update(extract_avoid_hints(latest_text))
            avoid_hints.update(_avoid_hints_from_trace(trace))
        selected = select_response_track(
            row.get("predicted_track_ids") or [],
            metadata_by_id,
            avoid_hints,
            promote=promote_response_track,
        )
        label = _track_label(selected.track_id, metadata_by_id) if selected.track_id else ""
        state = None
        if isinstance(trace, dict):
            state = trace.get("state") or trace.get("extracted_state")
        if variant_flags.get("context_mode") == "state_only":
            context = format_state_block(state, lambda tid: _track_label(tid, metadata_by_id))
        else:
            context = render_context(
                dataset_row,
                variant_flags,
                track_label=lambda tid: _track_label(tid, metadata_by_id),
            )
            if variant_flags.get("trace_state") and state:
                state_block = format_state_block(state, lambda tid: _track_label(tid, metadata_by_id))
                context = f"{context}\n{state_block}"
        style = (variant_flags.get("style") or "").strip()
        if style:
            context = f"{context}\nResponse style: {style}"
        recommend_item = _recommend_item_for(selected.track_id, metadata_by_id, variant_flags)
        request = {
            "session_id": session_id,
            "turn_number": row.get("turn_number"),
            "context": context,
            "recommend_item": recommend_item,
            "selected_track_id": selected.track_id,
            "selected_track_label": label,
            "selection_changed": selected.changed,
            "selection_reason": selected.reason,
            "avoid_hints": sorted(avoid_hints),
            "base_row": row,
            "dataset_row": dataset_row,
            "trace_row": trace_row,
            "trace": trace,
            "latest_user": latest_text,
        }
        requests.append(request)
        out = dict(row)
        out["predicted_track_ids"] = selected.track_ids
        output_rows.append(out)

    responses = generate_responses(requests)
    if len(responses) != len(output_rows):
        raise ValueError(f"generator returned {len(responses)} responses for {len(output_rows)} rows")
    for out, response in zip(output_rows, responses):
        out["predicted_response"] = response or ""
    return output_rows


def load_dataset_rows_by_session(dataset_name: str, split: str = "test") -> dict[str, dict[str, Any]]:
    from datasets import load_dataset

    dataset = load_dataset(dataset_name, split=split)
    return {row["session_id"]: dict(row) for row in dataset}


def load_track_metadata(
    track_ids: Iterable[str],
    dataset_name: str = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata",
    split: str = "all_tracks",
) -> dict[str, dict[str, Any]]:
    from datasets import load_dataset

    needed = {track_id for track_id in track_ids if track_id}
    metadata: dict[str, dict[str, Any]] = {}
    if not needed:
        return metadata
    dataset = load_dataset(dataset_name, split=split)
    for row in dataset:
        track_id = row.get("track_id")
        if track_id in needed:
            metadata[track_id] = dict(row)
            if len(metadata) == len(needed):
                break
    return metadata
