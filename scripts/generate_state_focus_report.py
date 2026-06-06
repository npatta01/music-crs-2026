"""Generate a state-focused Music CRS recall-gap work report.

The report answers a narrower question than the broad recall explorer:
which state failures or state-use gaps should be worked on first, and what
data validates each recommendation?
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


DEFAULT_SOURCE_ROOT = Path("/Users/npatta01/data/projects/music-conversational-music-recomender-2026")
DEFAULT_REPORT_ROOT = Path("experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06")
DEFAULT_OUT_DIR = DEFAULT_REPORT_ROOT / "state_focus"
DEFAULT_TID = "v0plus_compiler_all_retrievers_devset"

HF_TRACK_METADATA_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
HF_CONVERSATION_DATASET = "talkpl-ai/TalkPlayData-Challenge-Dataset"
HF_BLIND_A_DATASET = "talkpl-ai/TalkPlayData-Challenge-Blind-A"

NOVELTY_RE = re.compile(
    r"\b(other|another|else|different|new artist|new band|new artists|new bands|"
    r"more artists|more bands|different artist|different band|entirely|besides|"
    r"instead|away from|not like|completely different)\b",
    re.I,
)
CONTRAST_RE = re.compile(r"\b(different from|not like|besides|instead of|away from|completely different)\b", re.I)
POPULARITY_RE = re.compile(
    r"\b(popular|hit|classic|iconic|well[- ]known|famous|mainstream|chart|"
    r"recognized|recognisable|recognizable|canonical|staple)\b",
    re.I,
)
QUOTE_CHARS = "\"'"


@dataclass
class TrackMeta:
    track_id: str
    track_name: str
    artist_names: list[str]
    artist_ids: list[str]
    album_names: list[str]
    album_ids: list[str]
    tags: set[str]
    popularity: float | None
    release_year: int | None

    @property
    def artist_display(self) -> str:
        return ", ".join(self.artist_names[:3]) or "Unknown artist"

    @property
    def album_display(self) -> str:
        return ", ".join(self.album_names[:2]) or "Unknown album"


def first_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "tolist"):
        return first_text(value.tolist())
    if isinstance(value, (list, tuple)):
        return first_text(value[0]) if value else ""
    return str(value)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return as_list(value.tolist())
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def flat_list(value: Any) -> list[Any]:
    out: list[Any] = []
    for item in as_list(value):
        if item is None:
            continue
        if hasattr(item, "tolist"):
            out.extend(flat_list(item.tolist()))
        elif isinstance(item, (list, tuple, set)):
            out.extend(flat_list(item))
        else:
            out.append(item)
    return out


def norm_text(value: Any) -> str:
    text = first_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_phrase(haystack: str, needle: Any) -> bool:
    n = norm_text(needle)
    if len(n) < 3:
        return False
    h = f" {norm_text(haystack)} "
    return f" {n} " in h


def contains_track_title(haystack: str, title: Any) -> bool:
    """Return true when the current text plausibly names a track title.

    Short titles like "Hip Hop" or "Home" are too ambiguous in music-dialogue
    text unless quoted. Longer titles can use normal phrase matching.
    """
    raw_title = first_text(title).strip()
    norm_title = norm_text(raw_title)
    if not norm_title or len(norm_title) < 4:
        return False
    quoted_patterns = [
        f"'{raw_title}'",
        f'"{raw_title}"',
        f"`{raw_title}`",
    ]
    if any(pattern.lower() in haystack.lower() for pattern in quoted_patterns):
        return True
    if len(norm_title) < 12:
        return False
    return contains_phrase(haystack, raw_title)


def parse_year(value: Any) -> int | None:
    text = first_text(value)
    match = re.search(r"\b(18|19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def pct(value: float | None, digits: int = 1) -> str:
    if value is None or math.isnan(value):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def pct_count(count: int, denom: int, digits: int = 1) -> str:
    return pct(count / denom if denom else None, digits)


def rank_band(rank: int | None) -> str:
    if rank is None:
        return "absent"
    if rank <= 20:
        return "1-20"
    if rank <= 100:
        return "21-100"
    if rank <= 200:
        return "101-200"
    if rank <= 1000:
        return "201-1000"
    return ">1000"


def rank_value(rank: int | None) -> str:
    return "-" if rank is None else str(rank)


def load_ground_truth(path: Path) -> dict[tuple[str, int], str]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {(row["session_id"], int(row["turn_number"])): row["ground_truth_track_id"] for row in rows}


def load_prediction_ranks(path: Path, gt: dict[tuple[str, int], str]) -> dict[tuple[str, int], dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        key = (row["session_id"], int(row["turn_number"]))
        gt_id = gt.get(key)
        preds = row.get("predicted_track_ids") or []
        final_rank = None
        if gt_id:
            for idx, tid in enumerate(preds):
                if tid == gt_id:
                    final_rank = idx + 1
                    break
        out[key] = {"final_rank": final_rank, "top20": preds[:20]}
    return out


def top_track_summaries(
    track_ids: list[str],
    catalog: dict[str, TrackMeta],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, tid in enumerate(track_ids[:limit], start=1):
        meta = catalog.get(tid)
        rows.append(
            {
                "rank": idx,
                "track_id": tid,
                "track": meta.track_name if meta else tid,
                "artist": meta.artist_display if meta else "Unknown artist",
            }
        )
    return rows


def load_track_metadata() -> dict[str, TrackMeta]:
    from datasets import load_dataset

    ds = load_dataset(HF_TRACK_METADATA_DATASET, split="all_tracks")
    out: dict[str, TrackMeta] = {}
    for row in ds:
        tid = row["track_id"]
        tags = {norm_text(tag) for tag in flat_list(row.get("tag_list")) if norm_text(tag)}
        out[tid] = TrackMeta(
            track_id=tid,
            track_name=first_text(row.get("track_name")),
            artist_names=[str(x) for x in flat_list(row.get("artist_name")) if str(x)],
            artist_ids=[str(x) for x in flat_list(row.get("artist_id")) if str(x)],
            album_names=[str(x) for x in flat_list(row.get("album_name")) if str(x)],
            album_ids=[str(x) for x in flat_list(row.get("album_id")) if str(x)],
            tags=tags,
            popularity=float(row["popularity"]) if row.get("popularity") is not None else None,
            release_year=parse_year(row.get("release_date")),
        )
    return out


def load_conversations() -> dict[str, dict[str, Any]]:
    from datasets import load_dataset

    ds = load_dataset(HF_CONVERSATION_DATASET, split="test")
    out: dict[str, dict[str, Any]] = {}
    for row in ds:
        by_turn: dict[int, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
        for msg in row.get("conversations") or []:
            turn = int(msg.get("turn_number") or 0)
            role = str(msg.get("role") or "")
            by_turn[turn][role].append(
                {
                    "role": role,
                    "content": str(msg.get("content") or ""),
                    "thought": str(msg.get("thought") or ""),
                }
            )
        assessments = {
            int(item.get("turn_number") or 0): str(item.get("goal_progress_assessment") or "")
            for item in row.get("goal_progress_assessments") or []
        }
        out[row["session_id"]] = {
            "goal": row.get("conversation_goal") or {},
            "profile": row.get("user_profile") or {},
            "turns": by_turn,
            "assessments": assessments,
        }
    return out


def probe_blindset_metadata_availability() -> dict[str, Any]:
    from datasets import load_dataset

    try:
        ds = load_dataset(HF_BLIND_A_DATASET, split="test")
    except Exception as exc:  # pragma: no cover - report should still render offline.
        return {
            "available": False,
            "dataset": HF_BLIND_A_DATASET,
            "split": "test",
            "error": str(exc),
            "summary": "Blind-A metadata availability could not be verified during report generation.",
            "rows": [
                {
                    "item": "Blind-A schema probe",
                    "blind_a_status": "probe failed",
                    "evidence": str(exc),
                    "report_decision": "Do not assume organizer metadata availability until the HF probe succeeds.",
                }
            ],
        }

    required = ["conversation_goal", "user_profile", "goal_progress_assessments"]
    missing_counts = {key: 0 for key in required}
    empty_counts = {key: 0 for key in required}
    conversation_goal_keys: set[str] = set()
    user_profile_keys: set[str] = set()
    assessment_keys: set[str] = set()
    assessment_values: list[Any] = []
    last_assessment_values: list[Any] = []
    conversation_lengths: Counter[int] = Counter()
    assessment_lengths: Counter[int] = Counter()

    for row in ds:
        for key in required:
            if key not in row:
                missing_counts[key] += 1
            if not row.get(key):
                empty_counts[key] += 1
        conversation_goal_keys.update((row.get("conversation_goal") or {}).keys())
        user_profile_keys.update((row.get("user_profile") or {}).keys())
        assessments = row.get("goal_progress_assessments") or []
        conversations = row.get("conversations") or []
        conversation_lengths[len(conversations)] += 1
        assessment_lengths[len(assessments)] += 1
        if assessments:
            last = assessments[-1]
            if isinstance(last, dict):
                last_assessment_values.append(last.get("goal_progress_assessment"))
        for item in assessments:
            if not isinstance(item, dict):
                continue
            assessment_keys.update(item.keys())
            assessment_values.append(item.get("goal_progress_assessment"))

    n_rows = len(ds)
    non_null_assessments = sum(value is not None for value in assessment_values)
    last_non_null = sum(value is not None for value in last_assessment_values)
    goal_keys = ", ".join(sorted(conversation_goal_keys)) or "-"
    profile_keys = ", ".join(sorted(user_profile_keys)) or "-"
    assessment_key_text = ", ".join(sorted(assessment_keys)) or "-"
    rows = [
        {
            "item": "Blind-A raw HF rows",
            "blind_a_status": "available",
            "evidence": (
                f"{n_rows:,} rows in {HF_BLIND_A_DATASET} test; columns include "
                f"{', '.join(ds.column_names)}."
            ),
            "report_decision": "Organizer metadata is available in Blind-A raw rows; do not pay extractor calls to emulate it first.",
        },
        {
            "item": "conversation_goal",
            "blind_a_status": "available",
            "evidence": (
                f"missing={missing_counts['conversation_goal']:,}, empty={empty_counts['conversation_goal']:,}; "
                f"keys={goal_keys}."
            ),
            "report_decision": "Thread category, specificity, and listener_goal into retrieval/ranker context when testing metadata features.",
        },
        {
            "item": "user_profile",
            "blind_a_status": "available",
            "evidence": (
                f"missing={missing_counts['user_profile']:,}, empty={empty_counts['user_profile']:,}; "
                f"keys={profile_keys}."
            ),
            "report_decision": "Use preferred_musical_culture/profile as context or candidate-varying affinity; do not infer demographics from text.",
        },
        {
            "item": "goal_progress_assessments",
            "blind_a_status": "partially labeled",
            "evidence": (
                f"missing={missing_counts['goal_progress_assessments']:,}, empty={empty_counts['goal_progress_assessments']:,}; "
                f"keys={assessment_key_text}; non-null assessments={non_null_assessments:,}/{len(assessment_values):,}; "
                f"last-row assessment non-null={last_non_null:,}/{len(last_assessment_values):,}."
            ),
            "report_decision": "Use with leakage review. Visible progress can be useful, but do not treat it as a hidden GT label.",
        },
        {
            "item": "current blindset inference path",
            "blind_a_status": "metadata dropped before retrieval",
            "evidence": "run_inference_blindset.py builds batch_data with user_query, user_id, and session_memory only; output metadata keeps session_id, user_id, turn_number.",
            "report_decision": "The next implementation step is plumbing available metadata into the compiler/ranker input, not emulating Blind-A metadata.",
        },
    ]
    return {
        "available": True,
        "dataset": HF_BLIND_A_DATASET,
        "split": "test",
        "n_rows": n_rows,
        "columns": list(ds.column_names),
        "missing_counts": missing_counts,
        "empty_counts": empty_counts,
        "conversation_goal_keys": sorted(conversation_goal_keys),
        "user_profile_keys": sorted(user_profile_keys),
        "assessment_keys": sorted(assessment_keys),
        "assessment_value_counts": dict(Counter(str(value) for value in assessment_values)),
        "last_assessment_value_counts": dict(Counter(str(value) for value in last_assessment_values)),
        "conversation_lengths": dict(conversation_lengths),
        "assessment_lengths": dict(assessment_lengths),
        "summary": (
            f"Verified Blind-A raw rows include conversation_goal, user_profile, and goal_progress_assessments "
            f"on {n_rows:,}/{n_rows:,} rows. Current blindset inference does not pass those objects into retrieval/compiler state."
        ),
        "rows": rows,
    }


def build_prior_maps(
    gt: dict[tuple[str, int], str], catalog: dict[str, TrackMeta]
) -> tuple[dict[tuple[str, int], set[str]], dict[tuple[str, int], set[str]], dict[tuple[str, int], list[str]]]:
    by_session: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for (sid, turn), tid in gt.items():
        by_session[sid].append((turn, tid))
    prior_artists: dict[tuple[str, int], set[str]] = {}
    prior_albums: dict[tuple[str, int], set[str]] = {}
    prior_tracks: dict[tuple[str, int], list[str]] = {}
    for sid, rows in by_session.items():
        artist_ids: set[str] = set()
        album_ids: set[str] = set()
        track_ids: list[str] = []
        for turn, tid in sorted(rows):
            key = (sid, turn)
            prior_artists[key] = set(artist_ids)
            prior_albums[key] = set(album_ids)
            prior_tracks[key] = list(track_ids)
            meta = catalog.get(tid)
            if meta:
                artist_ids.update(meta.artist_ids)
                album_ids.update(meta.album_ids)
            track_ids.append(tid)
    return prior_artists, prior_albums, prior_tracks


def rank_in_hits(hits: list[Any], gt_id: str) -> int | None:
    for idx, item in enumerate(hits):
        tid = None
        if isinstance(item, dict):
            tid = item.get("track_id") or item.get("id")
        elif isinstance(item, (list, tuple)) and item:
            tid = item[0]
        elif isinstance(item, str):
            tid = item
        if tid == gt_id:
            return idx + 1
    return None


def ids_from_ranked_list(items: Any) -> list[str]:
    out: list[str] = []
    if isinstance(items, dict):
        maybe = items.get("track_ids") or items.get("ids") or items.get("items")
        return ids_from_ranked_list(maybe)
    for item in items or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            tid = item.get("track_id") or item.get("id")
            if tid:
                out.append(str(tid))
        elif isinstance(item, (list, tuple)) and item:
            out.append(str(item[0]))
    return out


def rank_in_ids(ids: list[str], gt_id: str) -> int | None:
    for idx, tid in enumerate(ids):
        if tid == gt_id:
            return idx + 1
    return None


def active_routing_tags(trace: dict[str, Any], state: dict[str, Any]) -> list[str]:
    tags = trace.get("routing_tags") or state.get("routing_tags") or {}
    if isinstance(tags, dict):
        return sorted([name for name, active in tags.items() if bool(active)])
    return []


def state_entity_values(state: dict[str, Any], kinds: set[str] | None = None, positive_only: bool = False) -> list[str]:
    out: list[str] = []
    for ent in state.get("mentioned_entities") or []:
        if not isinstance(ent, dict):
            continue
        kind = str(ent.get("type") or "")
        if kinds and kind not in kinds:
            continue
        if positive_only and float(ent.get("sentiment") or 0) <= 0:
            continue
        value = str(ent.get("value") or "")
        if value:
            out.append(value)
    return out


def year_range(state: dict[str, Any]) -> tuple[int | None, int | None] | None:
    ryr = state.get("release_year_range") or {}
    if not isinstance(ryr, dict):
        return None
    start = ryr.get("start")
    end = ryr.get("end")
    if start is None and end is None:
        return None
    try:
        start_i = int(start) if start is not None else None
        end_i = int(end) if end is not None else None
    except (TypeError, ValueError):
        return None
    return start_i, end_i


def in_year_range(year: int | None, bounds: tuple[int | None, int | None] | None) -> bool | None:
    if year is None or bounds is None:
        return None
    start, end = bounds
    if start is not None and year < start:
        return False
    if end is not None and year > end:
        return False
    return True


def text_for_turn(convo: dict[str, Any] | None, turn: int, role: str) -> str:
    if not convo:
        return ""
    msgs = (convo.get("turns") or {}).get(turn, {}).get(role, [])
    return " ".join(str(msg.get("content") or "") for msg in msgs).strip()


def recent_messages(convo: dict[str, Any] | None, turn: int) -> list[dict[str, Any]]:
    if not convo:
        return []
    out: list[dict[str, Any]] = []
    turns = convo.get("turns") or {}
    for t in range(max(1, turn - 2), turn + 1):
        for role in ("user", "music", "assistant"):
            for msg in turns.get(t, {}).get(role, []):
                content = str(msg.get("content") or "")
                if len(content) > 260:
                    content = content[:257].rstrip() + "..."
                out.append({"turn": t, "role": role, "content": content})
    return out


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {
            "n": 0,
            "share": 0.0,
            "final20": None,
            "union20": None,
            "union100": None,
            "union200": None,
            "union1000": None,
            "rank_loss20": 0,
            "candidate_gap20": 0,
        }
    return {
        "n": n,
        "share": None,
        "final20": sum(r["final20"] for r in rows) / n,
        "union20": sum(r["union20"] for r in rows) / n,
        "union100": sum(r["union100"] for r in rows) / n,
        "union200": sum(r["union200"] for r in rows) / n,
        "union1000": sum(r["union1000"] for r in rows) / n,
        "rank_loss20": sum(r["union20"] and not r["final20"] for r in rows),
        "candidate_gap20": sum(not r["union20"] for r in rows),
        "miss20": sum(not r["final20"] for r in rows),
    }


def add_share(metrics: list[dict[str, Any]], total: int) -> list[dict[str, Any]]:
    for row in metrics:
        row["share"] = row["n"] / total if total else 0.0
    return metrics


def clean_text(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) > limit:
        return text[: max(0, limit - 3)].rstrip() + "..."
    return text


def load_supplemental_audit(source_root: Path) -> dict[str, Any]:
    """Parse compact hypotheses from the local supplemental audit HTML.

    The state-focus report remains trace-derived. This supplemental input is
    used as a hypothesis and example source, then rendered as normal report
    evidence with caveats and current-run validation.
    """
    source_path = source_root / "exp/inference/devset/recall_anatomy_report.html"
    addendum: dict[str, Any] = {"available": False, "error": None}
    if not source_path.exists():
        addendum["error"] = "Supplemental audit HTML was not found."
        return addendum

    try:
        text = source_path.read_text(encoding="utf-8")
        start = text.index("const D = ") + len("const D = ")
        end = text.index("\nconst C=", start)
        payload = text[start:end].strip()
        if payload.endswith(";"):
            payload = payload[:-1]
        data = json.loads(payload)
    except Exception as exc:  # noqa: BLE001 - report generation should not fail on optional audit input.
        addendum["error"] = f"Could not parse supplemental audit payload: {exc}"
        return addendum

    taskmix = data.get("taskmix") or {}
    state = data.get("state") or {}
    extract = data.get("extract") or {}
    fixes = data.get("fixes") or {}
    honest = data.get("honest") or {}
    feature_catalog = fixes.get("feature_catalog") or {}

    addendum.update(
        {
            "available": True,
            "honest_ceiling": {
                "curve": honest.get("curve") or [],
                "ceiling_k": honest.get("ceiling_k"),
                "ceiling": honest.get("ceiling"),
                "gap": honest.get("gap"),
                "gap_n": honest.get("gap_n"),
                "deep_gap_n": honest.get("gap_deep"),
                "absent_gap_n": honest.get("gap_absent"),
                "fused20": honest.get("fused20"),
                "fused100": honest.get("fused100"),
            },
            "task_modes": [
                {
                    "mode": row.get("mode"),
                    "description": row.get("desc"),
                    "n": row.get("n"),
                    "share": row.get("share"),
                    "hit20": row.get("hit20"),
                    "ndcg20": row.get("ndcg"),
                    "gap50": row.get("gap50"),
                    "miss_share": row.get("missshare"),
                    "verdict": row.get("verdict"),
                }
                for row in taskmix.get("modes") or []
            ],
            "task_cat_note": taskmix.get("cat_note"),
            "intent_gap_note": (taskmix.get("intent_gap") or {}).get("note"),
            "state": {
                "scorecard": [
                    {
                        "item": row.get("item"),
                        "verdict": row.get("verdict"),
                        "stat": row.get("stat"),
                        "detail": row.get("detail"),
                    }
                    for row in state.get("scorecard") or []
                ],
                "year": state.get("year"),
                "rejection": state.get("rejection"),
                "entity_by_turn": state.get("entity_by_turn") or [],
                "recycle_overall": state.get("recycle_overall"),
                "gtnew_overall": state.get("gtnew_overall"),
            },
            "extraction": {
                "taxonomy": [
                    {
                        "cue": row.get("cue"),
                        "role": row.get("role"),
                        "current": row.get("current"),
                        "ideal": row.get("ideal"),
                    }
                    for row in extract.get("taxonomy") or []
                ],
                "grounding": extract.get("grounding"),
                "corrections": extract.get("corrections") or [],
                "bad_examples": [
                    {
                        "id": row.get("id"),
                        "intent": row.get("intent"),
                        "ask": clean_text(row.get("ask"), 180),
                        "anchored": clean_text(row.get("anchored"), 140),
                        "reason": clean_text(row.get("reason"), 220),
                        "ideal": clean_text(row.get("ideal"), 220),
                    }
                    for row in extract.get("graded") or []
                    if row.get("verdict") == "bad"
                ][:6],
            },
            "fixes": {
                "continuation": fixes.get("continuation"),
                "newartist": fixes.get("newartist"),
                "album": fixes.get("album"),
                "demographics": fixes.get("demographics"),
                "category_routing": fixes.get("category_routing"),
                "feature_catalog": {
                    "build": feature_catalog.get("build") or [],
                    "dont": feature_catalog.get("dont") or [],
                    "upstream": feature_catalog.get("upstream"),
                    "meta": feature_catalog.get("meta"),
                },
                "ruled_out": fixes.get("ruledout") or [],
            },
            "caveats": (data.get("caveats") or {}).get("items") or [],
            "crosscheck": data.get("codex_xref") or {},
        }
    )
    return addendum


def load_reranker_bakeoff(source_root: Path) -> dict[str, Any]:
    """Load an adjacent reranker bakeoff if the historical artifact is present."""
    candidates = [
        source_root
        / ".claude/worktrees/interesting-bose-a608d3/experiments/cross_encoder_rerank_bakeoff.md",
        source_root
        / ".claude/worktrees/beautiful-snyder-426460/experiments/cross_encoder_rerank_bakeoff.md",
        source_root / "experiments/cross_encoder_rerank_bakeoff.md",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return {"available": False, "error": "No reranker bakeoff markdown found."}

    text = path.read_text(encoding="utf-8")
    base_match = re.search(
        r"\| base \(no rerank\) \|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|",
        text,
    )
    rerank_match = re.search(
        r"\| \*\*0\.6B-structured rerank.*?\*\* \|\s*\*\*([0-9.]+)\*\*\s*\|\s*\*\*([0-9.]+)\*\*\s*\|\s*\*\*([0-9.]+)\*\*\s*\|\s*\*\*([0-9.]+)\*\*\s*\|\s*\*?\*?([0-9.]+)\*?\*?\s*\|",
        text,
    )
    if not base_match or not rerank_match:
        return {"available": False, "error": f"Could not parse reranker metrics from {path}"}

    base = [float(x) for x in base_match.groups()]
    rerank = [float(x) for x in rerank_match.groups()]
    rel_ndcg = (rerank[0] - base[0]) / base[0] if base[0] else None
    return {
        "available": True,
        "path": str(path),
        "scope": "Adjacent full-devset reranker bakeoff on v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset, not the all-retrievers trace in this report.",
        "base_ndcg20": base[0],
        "rerank_ndcg20": rerank[0],
        "relative_ndcg20": rel_ndcg,
        "base_hit20": base[1],
        "rerank_hit20": rerank[1],
        "decision": "RRF-rank fusion helps; pure score replacement was reported as structurally harmful. Revalidate on this report's all-retrievers union pool before shipping.",
    }


def infer_category_pattern(category: str) -> str:
    patterns = {
        "A": "sonic/audio characteristics, instrumentation, tempo, or production feel",
        "B": "lyrics, lyrical phrase, theme, story, or named lyrical content",
        "C": "album art / cover-art visual memory or visual-mood matching",
        "D": "situational use case, soundtrack memory, activity, or scene mood",
        "E": "guided progression through a musical journey or preference refinement",
        "F": "specific era, artist, subgenre, or catalog constraint discovery",
        "G": "emotional outcome: uplifting, comfort, grief, hope, or mood regulation",
        "H": "specific artist/song/composer or subgenre identity from vague clues",
        "I": "globally popular or internationally recognizable exact/near-exact targets",
        "J": "popularity within genre/era, classics, hits, or culturally defining songs",
        "K": "broad discovery by era/style/aesthetic with looser starting constraints",
    }
    return patterns.get(category, "observed listener-goal pattern not summarized")


def explain_failure(row: dict[str, Any]) -> dict[str, str]:
    final_rank = rank_value(row.get("final_rank"))
    branch_rank = rank_value(row.get("best_branch_rank"))
    branch = row.get("best_branch") or "no branch"
    gt = f"{row['gt_track']} by {row['gt_artist']}"

    if row.get("exact_track_named_miss"):
        return {
            "why_wrong": (
                f"The current user appears to name the target track, but {gt} is still absent from final top-20 "
                f"(final {final_rank}; best branch {branch_rank} in {branch}). Exact-title turns should be the least ambiguous slice."
            ),
            "what_should_change": (
                "Exact-track lookup should create a protected candidate with a high exactness feature, and finalization should "
                "preserve at least one exact named-track candidate unless a hard rejection conflicts."
            ),
            "regression_test": (
                "Replay this turn and assert the named target track is present in the candidate pool and cannot be dropped by "
                "RRF, diversity, or soft post-fusion adjustments."
            ),
        }

    strict_leak = row.get("rejection_leak_strict_top20")
    broad_leak = row.get("rejection_leak_top20")
    if strict_leak or broad_leak:
        leaked = ", ".join((row.get("rejected_slots") or [])[:2]) or "a rejected slot"
        leak_kind = "strict rejected ID" if strict_leak else "rejected name"
        return {
            "why_wrong": (
                f"The state contains an explicit rejection, but final top-20 still includes {leaked}. "
                f"That is a {leak_kind} leak, independent of whether the ground-truth target was retrieved."
            ),
            "what_should_change": (
                "Add a deterministic post-final rejection filter/assertion over rejected track IDs, artist IDs, and normalized "
                "multi-artist names. Treat broad name matches as an audit sample, but make strict ID leakage impossible."
            ),
            "regression_test": (
                "For this turn, replay finalization and assert no final slot intersects explicit_rejections by track_id, "
                "artist_id, or verified rejected artist name."
            ),
        }

    if row.get("release_range_excludes_gt"):
        bounds = row.get("year_range")
        year = row.get("release_year")
        return {
            "why_wrong": (
                f"The extracted release range {bounds} excludes the target release year {year}. "
                f"If this range is treated as a hard constraint or strong demotion, the correct item is pushed away before ranking."
            ),
            "what_should_change": (
                "Split hard date constraints from stylistic era cues. Era-like wording should become a soft compatibility feature; "
                "only explicit date-bound language should hard-filter or heavily penalize candidates."
            ),
            "regression_test": (
                "Run a no-year and soft-year replay for this turn; the target should remain eligible, and exact/HH turns should "
                "not regress when explicit date constraints are present."
            ),
        }

    if row.get("novelty_prior_anchor_conflict"):
        anchors = ", ".join((row.get("prior_anchor_values") or row.get("anchor_artist_values") or [])[:3]) or "prior artists"
        return {
            "why_wrong": (
                f"The user asks for novelty or a different direction, but the state still keeps {anchors} as positive anchors. "
                f"That sends retrievers toward already-satisfied artists instead of the new target space."
            ),
            "what_should_change": (
                "Add entity roles such as seed, satisfied, contrast, history, and rejected. For novelty/diversify turns, demote "
                "satisfied/history anchors as retrieval seeds and upweight tag, metadata, popularity, and CF profiles."
            ),
            "regression_test": (
                "Replay this turn and assert prior anchors are marked satisfied/history, not current seed; measure union@20/100 "
                "for novelty + new-artist turns before checking final ranking."
            ),
        }

    if row.get("stale_artist_or_track_state"):
        stale = ", ".join((row.get("stale_pos_entities") or [])[:3]) or "prior positive entities"
        return {
            "why_wrong": (
                f"The state still treats {stale} as positive artist/track evidence even though it is not present in the current user turn. "
                f"This can over-anchor retrieval on conversation history rather than the current ask."
            ),
            "what_should_change": (
                "Keep prior entities as history/context, but decay or remove them from current anchors unless the user re-mentions "
                "them. The resolver should expose current-vs-history roles to retrievers and the ranker."
            ),
            "regression_test": (
                "Replay state extraction for this turn and assert stale entities are not emitted as current positive anchors; "
                "then compare branch union for current-turn target candidates."
            ),
        }

    if row.get("gt_artist_named") and not row.get("final20"):
        return {
            "why_wrong": (
                f"The current user names the target artist, but {gt} misses final top-20 "
                f"(final {final_rank}; best branch {branch_rank} in {branch}). The entity is understood, but track selection or final ranking fails."
            ),
            "what_should_change": (
                "Protect named-artist candidate generation, then rank tracks with artist_recency, album affinity, exactness, branch-rank, "
                "and popularity features instead of relying on equal-weight RRF alone."
            ),
            "regression_test": (
                "Replay the named-artist slice and require the target artist's plausible tracks in union@20/100, with final@20/NDCG@20 "
                "tracked separately from broad new-artist cases."
            ),
        }

    if row.get("union20") and not row.get("final20"):
        return {
            "why_wrong": (
                f"The target is already reachable in a branch top-20, but final ranking drops it "
                f"(best branch {branch_rank} in {branch}; final {final_rank}). This is a fusion/ranker decision error."
            ),
            "what_should_change": (
                "Replace or calibrate RRF with a state-aware scorer that sees branch ranks plus candidate state features such as "
                "role, same-album, new-artist, rejection, year distance, and tag overlap."
            ),
            "regression_test": (
                "Train or replay a scorer over union@20/100 and assert this turn's target moves into final top-20 without "
                "violating rejection/year/exact guardrails."
            ),
        }

    if row.get("union100") and not row.get("union20"):
        return {
            "why_wrong": (
                f"The target is a near miss: it appears by union@100 but not union@20 "
                f"(best branch {branch_rank} in {branch}). Candidate generation is possible, but branch weighting/routing is too weak."
            ),
            "what_should_change": (
                "Use state routing to change branch weights and retrieval profiles by turn type, then use a trained/rule ranker "
                "over union@100 or union@200 to pull reachable targets upward."
            ),
            "regression_test": (
                "Replay with routing_boost populated and compare union@20/100 for this cohort before evaluating final@20."
            ),
        }

    return {
        "why_wrong": (
            f"The target is not in a strong candidate pool (best branch {branch_rank} in {branch}; final {final_rank}). "
            "This is mostly a retriever/state-to-retriever coverage gap, not just a final-ranker miss."
        ),
        "what_should_change": (
            "Improve turn-type routing and candidate generation: use listener_goal/current state, role-aware entities, tags, popularity, "
            "culture/CF affinity, and novelty profiles before spending effort only on final reranking."
        ),
        "regression_test": (
            "Track union@20 and union@100 for this example after each retriever/routing change; a ranker cannot fix it until "
            "the target enters the practical union pool."
        ),
    }


def ideal_state_for_row(row: dict[str, Any]) -> dict[str, Any]:
    gt_entity = {
        "track": row.get("gt_track"),
        "artist": row.get("gt_artist"),
        "track_id": row.get("gt_track_id"),
    }
    base = {
        "target": gt_entity,
        "target_artist_mode": "same_artist" if row.get("continuation_same_artist") else "new_artist",
        "retrieval_profile": "continuation" if row.get("continuation_same_artist") else "novelty",
    }

    if row.get("exact_track_named_miss"):
        return {
            **base,
            "current_target_entities": [
                {
                    "type": "track",
                    "value": row.get("gt_track"),
                    "id": row.get("gt_track_id"),
                    "role": "current_target",
                    "source": "current_user_turn",
                    "use_as_retrieval_seed": True,
                }
            ],
            "exact_reference_guard": {
                "protect_candidate": True,
                "reason": "user appears to name the target track in the current turn",
            },
        }

    if row.get("rejection_leak_top20"):
        return {
            **base,
            "normalized_rejections": {
                "track_ids": "from resolver.rejected_track_ids",
                "artist_ids": "from resolver.rejected_artist_ids",
                "names": "verified aliases only",
            },
            "finalization_assertion": "no final top-20 slot may intersect strict rejected IDs",
            "uncertain_name_matches": "hand-label before widening beyond strict IDs",
        }

    if row.get("release_range_excludes_gt"):
        return {
            **base,
            "temporal_constraint": {
                "kind": "style_era",
                "range": row.get("year_range"),
                "strength": "soft",
                "apply_as_filter": False,
                "reason": "the wording is compatible with an era/style cue, but the GT year sits outside the literal range",
            },
        }

    if row.get("novelty_prior_anchor_conflict"):
        return {
            **base,
            "target_artist_mode": "new_artist",
            "prior_entities": [
                {
                    "value": value,
                    "role": "satisfied_or_history",
                    "use_as_retrieval_seed": False,
                }
                for value in (row.get("prior_anchor_values") or row.get("anchor_artist_values") or [])[:5]
            ],
            "retrieval_profile": "novelty",
            "branch_hints": ["tag", "metadata", "popularity", "user_cf"],
        }

    if row.get("stale_artist_or_track_state"):
        return {
            **base,
            "entities": [
                {
                    "value": value,
                    "role": "history",
                    "mentioned_current_turn": False,
                    "use_as_retrieval_seed": False,
                }
                for value in (row.get("stale_pos_entities") or [])[:5]
            ],
            "current_turn_entities": "only entities re-mentioned in the current user turn should become current targets/seeds",
        }

    if row.get("gt_artist_named") and not row.get("final20"):
        return {
            **base,
            "current_target_entities": [
                {
                    "type": "artist",
                    "value": row.get("gt_artist"),
                    "role": "current_target",
                    "source": "current_user_turn",
                    "use_as_retrieval_seed": True,
                }
            ],
            "ranker_features": ["exact_artist_match", "branch_rank_bundle", "artist_recency", "album_affinity", "popularity"],
        }

    if row.get("union20") and not row.get("final20"):
        return {
            **base,
            "candidate_scoring": {
                "candidate_is_retrieved": True,
                "workbench": "union@20/100",
                "features": ["branch_rank_bundle", "entity_role", "same_album_recent", "tag_overlap", "year_distance"],
            },
            "finalization_policy": "do not blanket-demote trusted same-artist or exact-entity candidates",
        }

    if row.get("union100") and not row.get("union20"):
        return {
            **base,
            "retrieval_profile": "route_by_turn_mode",
            "branch_weights": {
                "exact_or_artist_lookup": "upweight when current target exists",
                "tag_metadata_popularity_cf": "upweight for novelty/new-artist asks",
                "old_anchor_centroids": "decay when user asks for different/new",
            },
        }

    return {
        **base,
        "retrieval_gap": "GT is not in a practical candidate pool yet",
        "state_to_retriever_contract": "derive a focused retrieval profile from current target, entity roles, tags, goal/profile context, and constraints",
    }


def display_row(row: dict[str, Any]) -> dict[str, Any]:
    explanation = explain_failure(row)
    return {
        "session_id": row["session_id"],
        "turn": row["turn"],
        "gt_track": row["gt_track"],
        "gt_artist": row["gt_artist"],
        "current_user": row["current_user"],
        "previous_user": row["previous_user"],
        "final_rank": row["final_rank"],
        "best_branch_rank": row["best_branch_rank"],
        "best_branch": row["best_branch"],
        "rank_band": row["rank_band"],
        "cohort_labels": row["cohort_labels"],
        "diagnostics": row["diagnostics"],
        "why_wrong": explanation["why_wrong"],
        "what_should_change": explanation["what_should_change"],
        "regression_test": explanation["regression_test"],
        "state": row["state_summary"],
        "ideal_state": ideal_state_for_row(row),
        "final_top_results": row.get("final_top_results") or [],
        "recent_messages": row["recent_messages"],
    }


def experiment_sample_row(
    row: dict[str, Any],
    *,
    pack: str,
    class_type: str,
    reason_to_test: str,
    expected_change: str,
    success_metric: str,
) -> dict[str, Any]:
    explanation = explain_failure(row)
    return {
        "sample_id": f"{row['session_id']}::t{row['turn']}",
        "pack": pack,
        "class_type": class_type,
        "session_id": row["session_id"],
        "turn": row["turn"],
        "gt_track_id": row["gt_track_id"],
        "gt_track": row["gt_track"],
        "gt_artist": row["gt_artist"],
        "current_user": clean_text(row.get("current_user"), 260),
        "baseline": {
            "final_rank": row.get("final_rank"),
            "fused_rank": row.get("fused_rank"),
            "best_branch_rank": row.get("best_branch_rank"),
            "best_branch": row.get("best_branch"),
            "union20": row.get("union20"),
            "union100": row.get("union100"),
            "union200": row.get("union200"),
        },
        "cohort_labels": row.get("cohort_labels") or [],
        "diagnostics": row.get("diagnostics") or [],
        "state_snapshot": row.get("state_summary") or {},
        "ideal_state": ideal_state_for_row(row),
        "recent_messages": row.get("recent_messages") or [],
        "final_top_results": row.get("final_top_results") or [],
        "reason_to_test": reason_to_test,
        "expected_change": expected_change,
        "success_metric": success_metric,
        "why_wrong": explanation["why_wrong"],
        "what_should_change": explanation["what_should_change"],
        "regression_test": explanation["regression_test"],
    }


def choose_examples(rows: list[dict[str, Any]], flag: str, limit: int = 5) -> list[dict[str, Any]]:
    candidates = [r for r in rows if r.get(flag) and not r["final20"]]
    candidates.sort(key=lambda r: (r["union20"], r["union100"], -(r["popularity"] or 0), r["turn"]))
    return [display_row(r) for r in candidates[:limit]]


def analyze(source_root: Path, tid: str) -> dict[str, Any]:
    trace_path = source_root / "exp/inference/devset" / f"{tid}_trace.jsonl"
    pred_path = source_root / "exp/inference/devset" / f"{tid}.json"
    gt_path = source_root / "evaluator/exp/ground_truth/devset.json"
    config_path = source_root / "configs" / f"{tid}.yaml"

    ground_truth = load_ground_truth(gt_path)
    predictions = load_prediction_ranks(pred_path, ground_truth)
    catalog = load_track_metadata()
    conversations = load_conversations()
    blindset_metadata_availability = probe_blindset_metadata_availability()
    prior_artists, prior_albums, prior_tracks = build_prior_maps(ground_truth, catalog)

    rows: list[dict[str, Any]] = []
    routing_counts = Counter()

    with trace_path.open(encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            row = json.loads(raw)
            key = (row["session_id"], int(row["turn_number"]))
            gt_id = ground_truth.get(key)
            if not gt_id:
                continue

            meta = catalog.get(gt_id)
            if not meta:
                continue

            trace = row.get("trace") or {}
            state = trace.get("state") or {}
            resolver = trace.get("resolver") or {}
            branches = trace.get("branches") or {}
            pools = branches.get("pools") or []
            branch_ranks: dict[str, int] = {}
            for pool in pools:
                name = str(pool.get("name") or "UNKNOWN")
                rank = rank_in_hits(pool.get("hits") or [], gt_id)
                if rank is not None:
                    branch_ranks[name] = rank
            best_branch = min(branch_ranks, key=branch_ranks.get) if branch_ranks else "NONE"
            best_branch_rank = branch_ranks.get(best_branch)

            fused_rank = rank_in_ids(ids_from_ranked_list(branches.get("fused") or []), gt_id)
            pred = predictions.get(key, {})
            final_rank = pred.get("final_rank")
            top20 = pred.get("top20") or []
            final_top_results = top_track_summaries(top20, catalog, limit=5)

            convo = conversations.get(key[0])
            current_user = text_for_turn(convo, key[1], "user")
            previous_user = text_for_turn(convo, key[1] - 1, "user")
            profile = (convo or {}).get("profile") or {}
            goal = (convo or {}).get("goal") or {}
            assessment = ((convo or {}).get("assessments") or {}).get(key[1], "")

            prior_artist_ids = prior_artists.get(key, set())
            prior_album_ids = prior_albums.get(key, set())
            prior_track_ids = prior_tracks.get(key, [])
            prior_primary_album_ids = {
                prior_meta.album_ids[0]
                for tid in prior_track_ids
                if (prior_meta := catalog.get(tid)) and prior_meta.album_ids
            }
            gt_artist_ids = set(meta.artist_ids)
            gt_album_ids = set(meta.album_ids)
            continuation = bool(gt_artist_ids & prior_artist_ids)
            same_album = bool(gt_album_ids & prior_album_ids)
            same_primary_album = bool(meta.album_ids and meta.album_ids[0] in prior_primary_album_ids)
            cold_open = key[1] == 1
            midconv_new_artist = key[1] > 1 and not continuation

            gt_track_named = contains_track_title(current_user, meta.track_name)
            gt_artist_named = any(contains_phrase(current_user, name) for name in meta.artist_names)
            novelty_cue = bool(NOVELTY_RE.search(current_user or ""))
            contrast_cue = bool(CONTRAST_RE.search(current_user or ""))
            popularity_cue = bool(POPULARITY_RE.search(current_user or ""))

            turn_intent_text = str(state.get("turn_intent") or "")
            mentioned_entities = [ent for ent in state.get("mentioned_entities") or [] if isinstance(ent, dict)]
            track_feedback = [item for item in state.get("track_feedback") or [] if isinstance(item, dict)]
            track_feedback_roles = Counter(
                str(item.get("role") or item.get("sentiment") or "unknown").lower() for item in track_feedback
            )
            referenced_track_ids = [str(x) for x in flat_list(state.get("referenced_track_ids")) if str(x)]
            hard_filters = [item for item in state.get("hard_filters") or [] if isinstance(item, dict)]
            hard_filter_types = sorted(
                {
                    str(item.get("field") or item.get("type") or item.get("kind") or "unknown")
                    for item in hard_filters
                }
            )
            process_constraints = state.get("process_constraints") or {}
            lyrical_theme = clean_text(state.get("lyrical_theme"), 160)

            pos_entities = state_entity_values(state, {"artist", "track"}, positive_only=True)
            pos_artist_values = state_entity_values(state, {"artist"}, positive_only=True)
            pos_track_values = state_entity_values(state, {"track"}, positive_only=True)
            state_intent_gt_artist = any(contains_phrase(turn_intent_text, name) for name in meta.artist_names)
            state_intent_gt_track = contains_track_title(turn_intent_text, meta.track_name)
            state_gt_artist_in_positive_entities = any(
                any(contains_phrase(value, name) or contains_phrase(name, value) for name in meta.artist_names)
                for value in pos_artist_values
            )
            state_gt_track_in_positive_entities = any(
                contains_track_title(value, meta.track_name) or contains_phrase(meta.track_name, value)
                for value in pos_track_values
            )
            positive_tag_values = [str(x) for x in as_list(resolver.get("positive_tags")) if str(x)]
            positive_tag_norms = {norm_text(tag) for tag in positive_tag_values if norm_text(tag)}
            positive_tag_overlap_gt = bool(positive_tag_norms & meta.tags)
            stale_pos_entities = [value for value in pos_entities if not contains_phrase(current_user, value)]
            stale_artist_or_track_state = bool(stale_pos_entities and key[1] > 1)

            anchor_artist_values = [str(x) for x in as_list(resolver.get("anchor_artist_ids")) if str(x)]
            anchor_track_ids = {str(x) for x in as_list(resolver.get("anchor_track_ids")) if str(x)}
            prior_artist_names = {
                name
                for tid in prior_track_ids
                for name in (catalog.get(tid).artist_names if catalog.get(tid) else [])
            }
            prior_anchor_values = [
                value
                for value in sorted(set(anchor_artist_values + pos_artist_values))
                if any(norm_text(value) == norm_text(name) for name in prior_artist_names)
                or any(contains_phrase(value, name) or contains_phrase(name, value) for name in prior_artist_names)
            ]
            novelty_prior_anchor_conflict = bool(novelty_cue and prior_anchor_values and key[1] > 1)

            bounds = year_range(state)
            gt_year_in_range = in_year_range(meta.release_year, bounds)
            release_range_set = bounds is not None
            release_range_excludes_gt = gt_year_in_range is False

            reject_track_ids = {str(x) for x in as_list(resolver.get("rejected_track_ids")) if str(x)}
            reject_artist_values = {str(x) for x in as_list(resolver.get("rejected_artist_ids")) if str(x)}
            explicit_rejections = state.get("explicit_rejections") or []
            rejected_values = {str(item.get("value") or "") for item in explicit_rejections if isinstance(item, dict)}
            rejection_state_present = bool(reject_track_ids or reject_artist_values or rejected_values)
            rejected_slots: list[str] = []
            strict_rejected_slots: list[str] = []
            broad_name_only_rejected_slots: list[str] = []
            for cand_tid in top20:
                cand = catalog.get(cand_tid)
                if not cand:
                    continue
                strict_track_rejected = cand_tid in reject_track_ids
                strict_artist_rejected = bool(set(cand.artist_ids) & reject_artist_values)
                strict_rejected = strict_track_rejected or strict_artist_rejected
                track_name_rejected = any(
                    contains_phrase(cand.track_name, value) or contains_phrase(value, cand.track_name)
                    for value in rejected_values
                )
                artist_name_rejected = any(
                    any(contains_phrase(name, value) or contains_phrase(value, name) for name in cand.artist_names)
                    for value in rejected_values
                )
                broad_name_rejected = track_name_rejected or artist_name_rejected
                if strict_rejected or broad_name_rejected:
                    rejected_slots.append(f"{cand.track_name} by {cand.artist_display}")
                if strict_rejected:
                    strict_rejected_slots.append(f"{cand.track_name} by {cand.artist_display}")
                elif broad_name_rejected:
                    broad_name_only_rejected_slots.append(f"{cand.track_name} by {cand.artist_display}")
            rejection_leak_top20 = bool(rejected_slots)
            rejection_leak_strict_top20 = bool(strict_rejected_slots)
            rejection_leak_name_only_top20 = bool(broad_name_only_rejected_slots)
            rejection_leak_name_only_without_strict_top20 = bool(
                broad_name_only_rejected_slots and not strict_rejected_slots
            )

            routing = active_routing_tags(trace, state)
            routing_counts.update(routing)

            final20 = final_rank is not None and final_rank <= 20
            union20 = best_branch_rank is not None and best_branch_rank <= 20
            union100 = best_branch_rank is not None and best_branch_rank <= 100
            union200 = best_branch_rank is not None and best_branch_rank <= 200
            union1000 = best_branch_rank is not None and best_branch_rank <= 1000

            diagnostics: list[str] = []
            if stale_artist_or_track_state:
                diagnostics.append(f"stale positive artist/track mentions: {', '.join(stale_pos_entities[:4])}")
            if novelty_prior_anchor_conflict:
                diagnostics.append(f"novelty cue but prior artist remains anchored: {', '.join(prior_anchor_values[:4])}")
            if release_range_excludes_gt:
                diagnostics.append(f"release range {bounds} excludes GT year {meta.release_year}")
            if rejection_leak_strict_top20:
                diagnostics.append(f"top-20 contains strict rejected ID slot(s): {', '.join(strict_rejected_slots[:2])}")
            elif rejection_leak_name_only_top20:
                diagnostics.append(f"top-20 contains rejected slot(s): {', '.join(rejected_slots[:2])}")
            if gt_track_named and not final20:
                diagnostics.append("user named the GT track but it did not land in final top-20")
            if gt_artist_named and not final20:
                diagnostics.append("user named the GT artist but it did not land in final top-20")
            if not diagnostics and not final20:
                diagnostics.append("no confirmed state defect from current heuristics; inspect retriever/ranker")

            cohort_labels: list[str] = []
            if cold_open:
                cohort_labels.append("cold_open")
            if gt_track_named:
                cohort_labels.append("exact_track_named")
            if gt_artist_named:
                cohort_labels.append("gt_artist_named_current")
            if continuation:
                cohort_labels.append("continuation_same_artist")
            if same_album:
                cohort_labels.append("same_album_continuation")
            if same_primary_album:
                cohort_labels.append("same_primary_album_continuation")
            if midconv_new_artist:
                cohort_labels.append("midconv_new_artist")
            if novelty_cue:
                cohort_labels.append("novelty_cue")
            if popularity_cue:
                cohort_labels.append("popularity_cue")
            if release_range_set:
                cohort_labels.append("release_range_set")

            rows.append(
                {
                    "session_id": key[0],
                    "turn": key[1],
                    "user_id": row.get("user_id"),
                    "gt_track_id": gt_id,
                    "gt_track": meta.track_name,
                    "gt_artist": meta.artist_display,
                    "gt_album": meta.album_display,
                    "release_year": meta.release_year,
                    "popularity": meta.popularity,
                    "final_rank": final_rank,
                    "fused_rank": fused_rank,
                    "best_branch": best_branch,
                    "best_branch_rank": best_branch_rank,
                    "rank_band": rank_band(best_branch_rank),
                    "final20": final20,
                    "union20": union20,
                    "union100": union100,
                    "union200": union200,
                    "union1000": union1000,
                    "current_user": current_user,
                    "previous_user": previous_user,
                    "recent_messages": recent_messages(convo, key[1]),
                    "final_top_results": final_top_results,
                    "goal": goal,
                    "profile": profile,
                    "assessment": assessment,
                    "intent_mode": trace.get("intent_mode") or state.get("intent_mode"),
                    "policy": (state.get("process_constraints") or {}).get("exploration_policy") or "balanced",
                    "routing": routing,
                    "state_turn_intent_present": bool(turn_intent_text.strip()),
                    "state_intent_gt_artist": state_intent_gt_artist,
                    "state_intent_gt_track": state_intent_gt_track,
                    "state_mentioned_entity_count": len(mentioned_entities),
                    "state_positive_entity_count": len(pos_entities),
                    "state_positive_tag_count": len(positive_tag_values),
                    "state_track_feedback_count": len(track_feedback),
                    "state_track_feedback_roles": dict(track_feedback_roles),
                    "state_referenced_track_ids_count": len(referenced_track_ids),
                    "state_hard_filters_count": len(hard_filters),
                    "state_hard_filter_types": hard_filter_types,
                    "state_explicit_rejection_count": len(explicit_rejections),
                    "state_routing_count": len(routing),
                    "state_lyrical_theme_present": bool(lyrical_theme),
                    "state_process_constraints_present": bool(process_constraints),
                    "state_gt_artist_in_positive_entities": state_gt_artist_in_positive_entities,
                    "state_gt_track_in_positive_entities": state_gt_track_in_positive_entities,
                    "state_has_entities_or_tags": bool(pos_entities or positive_tag_values),
                    "positive_tags": positive_tag_values,
                    "positive_tag_overlap_gt": positive_tag_overlap_gt,
                    "positive_entities": pos_entities,
                    "stale_pos_entities": stale_pos_entities,
                    "anchor_artist_values": anchor_artist_values,
                    "anchor_track_ids": sorted(anchor_track_ids),
                    "prior_anchor_values": prior_anchor_values,
                    "year_range": bounds,
                    "rejected_slots": rejected_slots,
                    "gt_track_named": gt_track_named,
                    "gt_artist_named": gt_artist_named,
                    "continuation_same_artist": continuation,
                    "same_album_continuation": same_album,
                    "same_primary_album_continuation": same_primary_album,
                    "midconv_new_artist": midconv_new_artist,
                    "cold_open": cold_open,
                    "novelty_cue": novelty_cue,
                    "contrast_cue": contrast_cue,
                    "popularity_cue": popularity_cue,
                    "stale_artist_or_track_state": stale_artist_or_track_state,
                    "novelty_prior_anchor_conflict": novelty_prior_anchor_conflict,
                    "release_range_set": release_range_set,
                    "release_range_excludes_gt": release_range_excludes_gt,
                    "rejection_state_present": rejection_state_present,
                    "rejection_leak_top20": rejection_leak_top20,
                    "rejection_leak_strict_top20": rejection_leak_strict_top20,
                    "rejection_leak_name_only_top20": rejection_leak_name_only_top20,
                    "rejection_leak_name_only_without_strict_top20": rejection_leak_name_only_without_strict_top20,
                    "cohort_labels": cohort_labels,
                    "diagnostics": diagnostics,
                    "state_summary": {
                        "turn_intent": state.get("turn_intent"),
                        "intent_mode": trace.get("intent_mode") or state.get("intent_mode"),
                        "policy": (state.get("process_constraints") or {}).get("exploration_policy") or "balanced",
                        "routing": routing,
                        "positive_entities": pos_entities[:12],
                        "stale_entities": stale_pos_entities[:8],
                        "anchors": anchor_artist_values[:8],
                        "positive_tags": (resolver.get("positive_tags") or [])[:12],
                        "field_counts": {
                            "mentioned_entities": len(mentioned_entities),
                            "track_feedback": len(track_feedback),
                            "referenced_track_ids": len(referenced_track_ids),
                            "hard_filters": len(hard_filters),
                            "explicit_rejections": len(explicit_rejections),
                        },
                        "year_range": bounds,
                        "explicit_rejections": explicit_rejections[:5],
                    },
                }
            )

    total = len(rows)
    headline = summarize(rows)
    headline["share"] = 1.0

    cohort_defs = [
        ("cold_open", "Turn 1 cold open", lambda r: r["cold_open"]),
        ("exact_track_named", "Current user names GT track", lambda r: r["gt_track_named"]),
        ("gt_artist_named_current", "Current user names GT artist", lambda r: r["gt_artist_named"]),
        ("continuation_same_artist", "GT artist already heard", lambda r: r["continuation_same_artist"]),
        ("same_album_continuation", "GT album already heard", lambda r: r["same_album_continuation"]),
        ("same_primary_album_continuation", "GT primary album already heard", lambda r: r["same_primary_album_continuation"]),
        ("midconv_new_artist", "Mid-conversation new artist", lambda r: r["midconv_new_artist"]),
        ("novelty_cue_new_artist", "Novelty cue + new artist", lambda r: r["novelty_cue"] and r["midconv_new_artist"]),
        ("contrast_cue", "Contrast cue in current turn", lambda r: r["contrast_cue"]),
        ("popularity_cue_new_artist", "Popularity cue + new artist", lambda r: r["popularity_cue"] and r["midconv_new_artist"]),
        ("release_range_set", "Release range present", lambda r: r["release_range_set"]),
        ("release_range_excludes_gt", "Release range excludes GT", lambda r: r["release_range_excludes_gt"]),
        ("stale_artist_or_track_state", "Stale positive artist/track state", lambda r: r["stale_artist_or_track_state"]),
        ("novelty_prior_anchor_conflict", "Novelty cue but prior anchor retained", lambda r: r["novelty_prior_anchor_conflict"]),
        ("rejection_state_present", "Explicit rejection state present", lambda r: r["rejection_state_present"]),
        ("rejection_leak_top20", "Rejected artist/track leaks into top-20", lambda r: r["rejection_leak_top20"]),
        ("rejection_leak_strict_top20", "Rejected ID leaks into top-20", lambda r: r["rejection_leak_strict_top20"]),
        ("rejection_leak_name_only_top20", "Name-only rejection leak audit", lambda r: r["rejection_leak_name_only_top20"]),
        (
            "rejection_leak_name_only_without_strict_top20",
            "Additional name-only rejection flags",
            lambda r: r["rejection_leak_name_only_without_strict_top20"],
        ),
    ]
    cohorts = add_share(
        [
            {"key": key, "label": label, **summarize([r for r in rows if pred(r)])}
            for key, label, pred in cohort_defs
        ],
        total,
    )

    defect_defs = [
        (
            "stale_artist_or_track_state",
            "Roleless or stale state entities",
            "Positive artist/track entities appear in state but not in the current user turn.",
            "Add entity role and decay: seed, satisfied, contrast, history, rejected. Drop history from current anchors.",
        ),
        (
            "novelty_prior_anchor_conflict",
            "Novelty asks keep old anchors",
            "The user asks for other/new/different music, but prior artists stay positive anchors.",
            "Make novelty/diversify state lower prior-artist centroid and discography influence unless the user asks for same artist.",
        ),
        (
            "release_range_excludes_gt",
            "Era state contradicts GT release year",
            "The extracted release range excludes the catalog release year of the judged target.",
            "Distinguish hard release constraints from stylistic-era cues; use softer penalties and audit 80s/90s style wording.",
        ),
        (
            "rejection_leak_top20",
            "Rejected entities leak into top-20",
            "A rejected track or artist appears in the final top-20 recommendation list.",
            "Add a deterministic post-final assertion and fix multi-artist/name/id rejection matching.",
        ),
        (
            "exact_track_named_miss",
            "Exact named-track misses",
            "The current user names the GT track, but final top-20 misses it.",
            "Treat exact named tracks as a protected retrieval and finalization path.",
        ),
    ]
    for row in rows:
        row["exact_track_named_miss"] = row["gt_track_named"] and not row["final20"]

    defects = []
    for key, label, definition, work in defect_defs:
        flagged = [r for r in rows if r.get(key)]
        summary = summarize(flagged)
        summary["share"] = len(flagged) / total if total else 0.0
        summary.update(
            {
                "key": key,
                "label": label,
                "definition": definition,
                "work": work,
                "examples": choose_examples(rows, key, limit=4),
            }
        )
        defects.append(summary)

    task_modes = [
        {
            "key": "exact_track_named",
            "label": "Exact named track",
            "interpretation": "This should be nearly solved; misses here are precision/state-routing bugs.",
            **summarize([r for r in rows if r["gt_track_named"]]),
        },
        {
            "key": "continuation_same_artist",
            "label": "Continuation: same artist",
            "interpretation": "Mostly a state-use/ranking problem: the relevant artist is known, but the right track is not chosen.",
            **summarize([r for r in rows if r["continuation_same_artist"] and not r["cold_open"]]),
        },
        {
            "key": "midconv_new_artist",
            "label": "New artist mid-conversation",
            "interpretation": "The main state/retriever problem: the system must convert state constraints into new-artist candidates.",
            **summarize([r for r in rows if r["midconv_new_artist"]]),
        },
        {
            "key": "cold_open",
            "label": "Cold open",
            "interpretation": "No session state exists yet, so popularity/canonicality and profile priors matter more than state repair.",
            **summarize([r for r in rows if r["cold_open"]]),
        },
    ]
    add_share(task_modes, total)

    supplemental = load_supplemental_audit(source_root)
    reranker_bakeoff = load_reranker_bakeoff(source_root)
    cohort_lookup = {row["key"]: row for row in cohorts}
    defect_lookup = {row["key"]: row for row in defects}
    task_lookup = {row["key"]: row for row in task_modes}

    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    routing_boost_empty = bool(re.search(r"(?m)^\s*routing_boost:\s*\{\}\s*$", config_text))
    tagged_rows = [r for r in rows if r.get("positive_tags")]
    positive_tag_overlap_rate = (
        sum(bool(r.get("positive_tag_overlap_gt")) for r in tagged_rows) / len(tagged_rows)
        if tagged_rows
        else None
    )
    routing_total = sum(routing_counts.values())

    category_counts: Counter[str] = Counter()
    specificity_counts: Counter[str] = Counter()
    category_examples: dict[str, list[str]] = defaultdict(list)
    specificity_examples: dict[str, list[str]] = defaultdict(list)
    inline_profile_fields: set[str] = set()
    for convo in conversations.values():
        goal = convo.get("goal") or {}
        profile = convo.get("profile") or {}
        inline_profile_fields.update(profile.keys())
        category = str(goal.get("category") or "NONE")
        specificity = str(goal.get("specificity") or "NONE")
        listener_goal = clean_text(goal.get("listener_goal"), 180)
        category_counts[category] += 1
        specificity_counts[specificity] += 1
        if listener_goal and len(category_examples[category]) < 3:
            category_examples[category].append(listener_goal)
        if listener_goal and len(specificity_examples[specificity]) < 2:
            specificity_examples[specificity].append(listener_goal)

    session_total = max(1, len(conversations))
    specificity_glossary = {
        "LL": "Low / low specificity: observed goals are broad discovery or multi-item asks with weak exact-entity constraints.",
        "LH": "Low / high specificity: observed goals often name a target type or memory, but the surface clue is vague.",
        "HL": "High / low specificity: observed goals have concrete genres, artists, eras, or journey constraints but multiple acceptable tracks.",
        "HH": "High / high specificity: observed goals often identify exact titles, artists, lyrics, albums, or tightly constrained targets.",
    }
    category_summary = [
        {
            "category": category,
            "sessions": count,
            "share": count / session_total,
            "observed_pattern": infer_category_pattern(category),
            "example_goal": category_examples.get(category, [""])[0],
        }
        for category, count in sorted(category_counts.items())
        if category != "NONE"
    ]
    specificity_summary = [
        {
            "specificity": spec,
            "sessions": count,
            "share": count / session_total,
            "meaning": specificity_glossary.get(
                spec,
                "Organizer specificity code present in the dataset; local docs do not decode this value.",
            ),
            "example_goal": specificity_examples.get(spec, [""])[0],
        }
        for spec, count in sorted(specificity_counts.items(), key=lambda item: {"LL": 0, "LH": 1, "HL": 2, "HH": 3}.get(item[0], 99))
        if spec != "NONE"
    ]
    user_profile_fields = []
    profile_use = {
        "user_id": "join key; passed through inference, not a semantic ranker feature",
        "user_split": "organizer split marker; diagnostic only",
        "age": "available inline; not rendered by UserProfileDB default profile string",
        "age_group": "rendered in response-generation profile string; weak diagnostic/personalization feature",
        "country_code": "available inline; not rendered by default profile string",
        "country_name": "rendered in response-generation profile string; weak cultural/localization feature",
        "gender": "rendered in response-generation profile string; diagnostics/guardrails only",
        "preferred_language": "available inline; useful for response style and weak language/culture cues",
        "preferred_musical_culture": "available inline; highest-value user metadata feature to test for router/ranker personalization",
    }
    rendered_profile_fields = {"user_id", "age_group", "gender", "country_name"}
    for field in sorted(inline_profile_fields):
        user_profile_fields.append(
            {
                "field": field,
                "current_use": "rendered in UserProfileDB profile string"
                if field in rendered_profile_fields
                else "available in organizer metadata; not used by current retrieval/ranking",
                "recommended_use": profile_use.get(field, "candidate-varying feature only after leakage checks"),
            }
        )

    organizer_metadata = {
        "fields": [
            {
                "field": "conversation_goal.category",
                "description": "Organizer session-level code A-K. The local docs expose the code plus listener_goal text, but not an official codebook.",
                "recommendation": "Use for slicing and goal-family routing experiments; do not use as the only per-turn router.",
            },
            {
                "field": "conversation_goal.specificity",
                "description": "Organizer two-letter H/L specificity code. Local docs expose LL/LH/HL/HH but do not define the two axes.",
                "recommendation": "Use LL/HH as guardrail slices. LL needs better candidate generation; HH should not regress.",
            },
            {
                "field": "conversation_goal.listener_goal",
                "description": "Natural-language session goal from organizers.",
                "recommendation": "Better than raw category for retrieval routing; can feed a goal-conditioned query or ranker text feature.",
            },
            {
                "field": "goal_progress_assessments",
                "description": "Organizer turn-level assessment labels in the dataset.",
                "recommendation": "Use previous-turn labels for analysis/training if available; avoid using current-turn labels as live inference signals unless confirmed available at inference time.",
            },
            {
                "field": "user_profile",
                "description": "Inline profile with age, age_group, country, gender, preferred_language, preferred_musical_culture, user_split.",
                "recommendation": "Convert to candidate-varying affinity features such as demographic/culture-conditioned popularity or user-CF, not raw constants.",
            },
        ],
        "category_summary": category_summary,
        "specificity_summary": specificity_summary,
        "user_profile_fields": user_profile_fields,
        "blindset_availability": blindset_metadata_availability,
        "current_pipeline_summary": (
            "Current retrieval state is extracted from session_memory. UserProfileDB renders only user_id, age_group, "
            "gender, and country_name for response generation; conversation_goal and preferred_musical_culture are not "
            "consumed by current retrieval/ranking. Blind-A raw rows were probed separately: "
            f"{blindset_metadata_availability.get('summary')}"
        ),
        "category_caveat": (
            "Category descriptions are derived from observed listener_goal examples in this devset because the local docs "
            "do not provide official labels for A-K."
        ),
    }
    metadata_decision_plan = [
        {
            "source": "conversation_goal.listener_goal",
            "available_as": "Organizer session-level natural-language goal; verified present in Blind-A raw rows.",
            "use_directly": "Yes. Feed as immutable session context for routing/query text and as a goal-text compatibility feature.",
            "emulate_or_extract": "Do not emulate for Blind-A: it is available. Only extract a replacement for a future split that lacks listener_goal.",
            "ranking_shape": "Candidate-varying goal_text_match, goal-conditioned popularity, or retrieval profile; not a raw constant score.",
            "first_test": "First plumb listener_goal through run_inference_blindset/devset batch inputs; then compare novelty/broad-goal packs with and without it.",
        },
        {
            "source": "conversation_goal.category A-K",
            "available_as": "Organizer session-level code with no official local codebook; verified present in Blind-A raw rows.",
            "use_directly": "Use for slicing, guardrails, and coarse route priors when available.",
            "emulate_or_extract": "Do not spend extractor calls predicting A-K for Blind-A. If useful, derive operational route labels from listener_goal/state instead of matching organizer codes.",
            "ranking_shape": "Category-conditioned retriever profile or evaluation slice; raw category is candidate-constant within a turn.",
            "first_test": "Measure union@20/final@20 by A-K and only promote categories that map to different successful retriever profiles.",
        },
        {
            "source": "conversation_goal.specificity LL/LH/HL/HH",
            "available_as": "Organizer session-level specificity code; verified present in Blind-A raw rows, but official axis definitions are not in local docs.",
            "use_directly": "Use as guardrail slices: HH exactness should not regress; LL broad discovery needs better candidate generation.",
            "emulate_or_extract": "Do not emulate the code itself for Blind-A. If needed, extract simpler operational fields: exactness_required, broad_discovery, constraint_strength.",
            "ranking_shape": "Route exact/high-specificity turns toward entity protection; route low-specificity turns toward popularity/CF/tag exploration.",
            "first_test": "Run exact-reference controls by HH-like turns and novelty-popularity packs by LL-like turns.",
        },
        {
            "source": "user_profile.preferred_musical_culture",
            "available_as": "Organizer user-profile field; verified present in Blind-A raw rows and standalone user metadata.",
            "use_directly": "Use as context for culture-conditioned popularity, CF priors, and response style.",
            "emulate_or_extract": "Do not infer culture from conversation when profile is present; that is noisy and can create bias/leakage.",
            "ranking_shape": "Candidate-varying culture/user affinity, not a constant feature attached to every candidate.",
            "first_test": "Test culture-conditioned popularity or user-CF affinity on new-artist and popularity-cue packs.",
        },
        {
            "source": "age_group, gender, country, preferred_language",
            "available_as": "Organizer user-profile demographics and language metadata; verified present in Blind-A raw rows.",
            "use_directly": "Use mainly for response style, analysis slices, leakage/fairness checks, and maybe language/local catalog priors.",
            "emulate_or_extract": "Do not extract or infer these from conversation text.",
            "ranking_shape": "Only candidate-varying features after validation; raw demographics showed no within-turn ranking lift as constants.",
            "first_test": "Keep as guardrail slices while testing stronger behavioral features first.",
        },
        {
            "source": "goal_progress_assessments",
            "available_as": "Organizer turn-level assessment labels; structurally present in Blind-A raw rows and partially populated.",
            "use_directly": "Use only after leakage review. Prior visible progress may help; the current row's assessment should be treated carefully.",
            "emulate_or_extract": "Do not emulate first. If used, prefer visible previous-turn labels and audit current-turn labels for leakage.",
            "ranking_shape": "Satisfaction/move-on signal, not a hidden GT label.",
            "first_test": "Ablate previous-turn assessment features separately from conversation text/state features and inspect exact-target cases.",
        },
    ]

    source_scorecard = {
        str(row.get("item") or "").lower(): row for row in (supplemental.get("state") or {}).get("scorecard", [])
    }
    cont = task_lookup["continuation_same_artist"]
    same_album = cohort_lookup["same_album_continuation"]
    same_primary_album = cohort_lookup["same_primary_album_continuation"]
    new_artist = task_lookup["midconv_new_artist"]
    continuation_fix = (supplemental.get("fixes") or {}).get("continuation") or {}
    album_fix = (supplemental.get("fixes") or {}).get("album") or {}
    same_album_misses = [r for r in rows if r["same_album_continuation"] and not r["final20"]]
    same_primary_album_misses = [r for r in rows if r["same_primary_album_continuation"] and not r["final20"]]
    album_fused_top20_demoted = sum(
        (r["fused_rank"] is not None and 1 <= r["fused_rank"] <= 20) for r in same_album_misses
    )
    album_fused_21_100 = sum((r["fused_rank"] is not None and 21 <= r["fused_rank"] <= 100) for r in same_album_misses)
    album_fused_101_1000 = sum((r["fused_rank"] is not None and 101 <= r["fused_rank"] <= 1000) for r in same_album_misses)
    album_fused_absent = sum(r["fused_rank"] is None for r in same_album_misses)
    primary_album_fused_top20_demoted = sum(
        (r["fused_rank"] is not None and 1 <= r["fused_rank"] <= 20) for r in same_primary_album_misses
    )
    primary_album_fused_21_100 = sum(
        (r["fused_rank"] is not None and 21 <= r["fused_rank"] <= 100) for r in same_primary_album_misses
    )
    primary_album_fused_101_1000 = sum(
        (r["fused_rank"] is not None and 101 <= r["fused_rank"] <= 1000) for r in same_primary_album_misses
    )
    primary_album_fused_absent = sum(r["fused_rank"] is None for r in same_primary_album_misses)
    state_scorecard = [
        {
            "area": "Positive tag extraction",
            "current_evidence": (
                f"{len(tagged_rows):,} turns have positive_tags; {pct(positive_tag_overlap_rate)} overlap at least one GT catalog tag."
            ),
            "audit_signal": clean_text((source_scorecard.get("genre/mood tags") or {}).get("detail"), 180),
            "decision": "Do not make tag extraction the first major state rewrite. Use tags better in ranker/router features.",
        },
        {
            "area": "Entity role and recency",
            "current_evidence": (
                f"{defect_lookup['stale_artist_or_track_state']['n']:,} turns have positive artist/track state not present in the current user turn; "
                f"{defect_lookup['novelty_prior_anchor_conflict']['n']:,} novelty turns keep prior anchors."
            ),
            "audit_signal": clean_text((source_scorecard.get("entity over-extraction") or {}).get("detail"), 200),
            "decision": "P0. Add seed/satisfied/contrast/history/rejected roles and decay history before anchors/discography.",
        },
        {
            "area": "Release-year state",
            "current_evidence": (
                f"{cohort_lookup['release_range_set']['n']:,} turns set a release range; "
                f"{defect_lookup['release_range_excludes_gt']['n']:,} exclude the GT release year."
            ),
            "audit_signal": clean_text((source_scorecard.get("year filter over-fires") or {}).get("detail"), 180),
            "decision": "P1. Split stylistic era from hard release-date bounds; run no-year and soft-year ablations.",
        },
        {
            "area": "P0 routing config gap",
            "current_evidence": (
                f"Trace routing tags fire {routing_total:,} times "
                f"(feature_articulation={routing_counts.get('feature_articulation', 0):,}, "
                f"exact_entity_probe={routing_counts.get('exact_entity_probe', 0):,}, "
                f"hidden_target_search={routing_counts.get('hidden_target_search', 0):,}), "
                f"but config routing_boost is {'empty' if routing_boost_empty else 'non-empty'}."
            ),
            "audit_signal": "Routing tags are extracted, but routing is ineffective when the boost map is empty.",
            "decision": "P0. Treat this as a config/consumption bug: wire tags into retriever profile weights before adding new retrievers.",
        },
        {
            "area": "Rejection enforcement",
            "current_evidence": (
                f"{cohort_lookup['rejection_state_present']['n']:,} turns have rejection state; "
                f"{cohort_lookup['rejection_leak_strict_top20']['n']:,} strict-ID leak turns plus "
                f"{cohort_lookup['rejection_leak_name_only_without_strict_top20']['n']:,} additional name-only audit turns produce "
                f"{defect_lookup['rejection_leak_top20']['n']:,} broad final top-20 leak flags."
            ),
            "audit_signal": clean_text((source_scorecard.get("rejection enforcement") or {}).get("detail"), 180),
            "decision": "P1. Add deterministic post-final assertions and multi-artist rejection tests.",
        },
    ]

    def summarize_slice(pred: Any) -> dict[str, Any]:
        subset = [r for r in rows if pred(r)]
        summary = summarize(subset)
        summary["share"] = len(subset) / total if total else 0.0
        return summary

    def metric_line(summary: dict[str, Any]) -> str:
        return (
            f"n={int(summary.get('n') or 0):,} ({pct(summary.get('share'))}); "
            f"final@20={pct(summary.get('final20'))}; union@20={pct(summary.get('union20'))}; "
            f"union@100={pct(summary.get('union100'))}"
        )

    feedback_role_counts: Counter[str] = Counter()
    for r in rows:
        feedback_role_counts.update(r.get("state_track_feedback_roles") or {})
    feedback_roles_text = ", ".join(f"{role}:{count:,}" for role, count in feedback_role_counts.most_common(4))
    policy_counts = Counter(str(r.get("policy") or "unknown") for r in rows)
    policy_counts_text = ", ".join(f"{policy}:{count:,}" for policy, count in policy_counts.most_common(4))
    hard_filter_type_counts: Counter[str] = Counter()
    for r in rows:
        hard_filter_type_counts.update(r.get("state_hard_filter_types") or [])
    hard_filter_types_text = ", ".join(f"{name}:{count:,}" for name, count in hard_filter_type_counts.most_common(4))

    intent_present = summarize_slice(lambda r: r["state_turn_intent_present"])
    intent_gt_artist = summarize_slice(lambda r: r["state_intent_gt_artist"])
    positive_entities_present = summarize_slice(lambda r: r["state_positive_entity_count"] > 0)
    positive_tags_present = summarize_slice(lambda r: r["state_positive_tag_count"] > 0)
    positive_tag_overlap = summarize_slice(lambda r: r["positive_tag_overlap_gt"])
    track_feedback_present = summarize_slice(lambda r: r["state_track_feedback_count"] > 0)
    referenced_tracks_present = summarize_slice(lambda r: r["state_referenced_track_ids_count"] > 0)
    hard_filters_present = summarize_slice(lambda r: r["state_hard_filters_count"] > 0)
    process_constraints_present = summarize_slice(lambda r: r["state_process_constraints_present"])
    routing_present = summarize_slice(lambda r: r["state_routing_count"] > 0)
    lyrical_theme_present = summarize_slice(lambda r: r["state_lyrical_theme_present"])
    goal_profile_present = summarize_slice(lambda r: bool(r.get("goal") or r.get("profile")))
    temporal_ok = summarize_slice(lambda r: r["release_range_set"] and not r["release_range_excludes_gt"])

    state_field_audit = [
        {
            "field": "turn_intent",
            "evidence": (
                f"{metric_line(intent_present)}. The normalized intent text names the GT artist on "
                f"{intent_gt_artist['n']:,} turns."
            ),
            "failure_read": "Keep, but do not rely on free text alone. It does not encode whether an entity is the current target, already satisfied, contrast, or old history.",
            "schema_decision": "Keep as extractor QA/debug text; derive structured target mode and entity roles from it.",
            "validation": "After rerun, compare intent text to role labels on sampled novelty, continuation, and exact-entity turns.",
        },
        {
            "field": "mentioned_entities",
            "evidence": (
                f"{metric_line(positive_entities_present)}. Stale positive artist/track evidence appears on "
                f"{defect_lookup['stale_artist_or_track_state']['n']:,} turns; novelty+prior-anchor conflicts appear on "
                f"{defect_lookup['novelty_prior_anchor_conflict']['n']:,} turns."
            ),
            "failure_read": "This is the main confusing field: positive sentiment is carrying too much meaning and downstream code treats old positives like current anchors.",
            "schema_decision": "Split into role-typed entities: seed/current_target, satisfied, contrast, history/context, rejected, with source_turn and recency.",
            "validation": "Primary state QA metric: stale positive artist/track rate and novelty-prior-anchor conflict count should fall without hurting named-artist union@20.",
        },
        {
            "field": "track_feedback",
            "evidence": (
                f"{metric_line(track_feedback_present)}. Observed feedback roles: {feedback_roles_text or 'none'}."
            ),
            "failure_read": "Useful but underspecified: feedback can mean keep exploring around this track, move on after a satisfied track, or avoid a disliked track.",
            "schema_decision": "Keep, but align feedback roles with entity roles and expose a candidate-level recency/album/artist feature.",
            "validation": "Sample feedback turns and assert accepted/satisfied tracks do not automatically become current retrieval seeds on novelty turns.",
        },
        {
            "field": "referenced_track_ids",
            "evidence": metric_line(referenced_tracks_present),
            "failure_read": "Low-coverage but precise. It is not the broad recall gap, but it should be exact when present.",
            "schema_decision": "Keep as a surgical exact-reference field; do not make it a P0 schema rewrite.",
            "validation": "For turns with referenced IDs, assert exact-reference candidates are protected before RRF/finalization.",
        },
        {
            "field": "positive_tags",
            "evidence": (
                f"{metric_line(positive_tags_present)}. When tags are present, {pct(positive_tag_overlap_rate)} overlap at least one GT catalog tag; "
                f"the overlap slice itself is {metric_line(positive_tag_overlap)}."
            ),
            "failure_read": "Tag extraction is not the clearest extractor bug. The larger issue is that tags do not overcome stale anchors or weak novelty routing.",
            "schema_decision": "Keep tags; canonicalize/map them and use candidate-level overlap/compatibility features instead of adding more raw tag fields.",
            "validation": "Measure positive-tag-overlap turns by union@20 and final@20 after routing/ranker changes, not just extractor precision.",
        },
        {
            "field": "release_year_range + hard_filters",
            "evidence": (
                f"Release range present: {metric_line(cohort_lookup['release_range_set'])}; range excludes GT on "
                f"{defect_lookup['release_range_excludes_gt']['n']:,} turns. Hard filters present: {metric_line(hard_filters_present)}; "
                f"types: {hard_filter_types_text or 'none'}."
            ),
            "failure_read": "The state confuses stylistic era with literal release-date constraints. This can suppress correct targets even when the user meant an aesthetic.",
            "schema_decision": "Collapse into one temporal_constraint object with kind=release_date/style_era/reference_era and strength=hard/soft.",
            "validation": "Run no-year and soft-year ablations; exact/HH turns are guardrails, release-range-excludes-GT should shrink.",
        },
        {
            "field": "explicit_rejections",
            "evidence": (
                f"{metric_line(cohort_lookup['rejection_state_present'])}. Strict-ID leak lower bound: "
                f"{cohort_lookup['rejection_leak_strict_top20']['n']:,}; broad name audit: {defect_lookup['rejection_leak_top20']['n']:,}."
            ),
            "failure_read": "Extraction is probably good enough to detect many rejections; the bigger bug is enforcement and ID/name normalization.",
            "schema_decision": "Keep, but normalize to rejected_track_ids, rejected_artist_ids, and verified name aliases before finalization.",
            "validation": "Post-final replay should produce zero strict rejection leaks; hand-label name-only flags before treating them as defects.",
        },
        {
            "field": "routing_tags + intent_mode + process_constraints",
            "evidence": (
                f"Routing tags present: {metric_line(routing_present)}; total active tags={routing_total:,}; "
                f"routing_boost is {'empty' if routing_boost_empty else 'configured'}. Process constraints: "
                f"{metric_line(process_constraints_present)}; policies: {policy_counts_text or 'none'}."
            ),
            "failure_read": "The extractor creates useful mode hints, but they are fragmented and not consumed by weighted retrieval.",
            "schema_decision": "Collapse downstream into a derived retrieval_profile: continuation, novelty, exact_probe, feature_search, hidden_target_search.",
            "validation": "Populate routing_boost/profiles and report union@20/100 by routing tag and by continuation vs new-artist mode.",
        },
        {
            "field": "lyrical_theme",
            "evidence": metric_line(lyrical_theme_present),
            "failure_read": "Can matter for lyrics/theme tasks, but it is not the broad state failure in the current trace.",
            "schema_decision": "Keep as a specialized field; route only to lyric/theme retrieval or a candidate text feature.",
            "validation": "Evaluate B/category lyric/theme slices separately so this field is not overfit into general retrieval.",
        },
        {
            "field": "conversation_goal + user_profile",
            "evidence": (
                f"{metric_line(goal_profile_present)}. Metadata is session-level and currently not consumed by retrieval/ranking; "
                "preferred_musical_culture and listener_goal are the most plausible additions. Blind-A raw rows expose these fields, but the current blindset batch input drops them before retrieval."
            ),
            "failure_read": "Missing pipeline context, not a state extraction bug. Raw constants do not rank candidates within a turn unless converted to candidate-varying affinity.",
            "schema_decision": "Add to the state/ranker input as context, but derive candidate-level features: culture-conditioned popularity, goal-text compatibility, user-CF affinity.",
            "validation": "Session-grouped CV. Raw demographic/session features are a guardrail baseline; candidate-varying affinity must beat it.",
        },
    ]

    schema_change_plan = [
        {
            "priority": "P0",
            "failure_class": "Roleless entity carryover",
            "schema_move": "Split",
            "change": "Replace a single positive entity interpretation with role, source_turn, recency, and anchor_strength.",
            "why_it_makes_sense": (
                f"{defect_lookup['stale_artist_or_track_state']['n']:,} stale positive-entity turns and "
                f"{defect_lookup['novelty_prior_anchor_conflict']['n']:,} novelty-anchor conflicts are direct state-shape failures."
            ),
            "validation": "Extractor rerun should reduce stale-current positives; retrieval should improve new-artist union@20/100 without named-artist regression.",
        },
        {
            "priority": "P0",
            "failure_class": "Same-artist vs new-artist mode ambiguity",
            "schema_move": "Add derived field",
            "change": "Add target_artist_mode: same_artist, new_artist, any_artist, or unknown, derived from cues plus history.",
            "why_it_makes_sense": (
                f"Continuation and mid-conversation new-artist turns have different hit profiles; new-artist union@20 is "
                f"{pct(new_artist['union20'])}, so mode should change retriever profile before ranking."
            ),
            "validation": "Track target_artist_mode confusion matrix against GT artist history; route-specific union@20/100 must move.",
        },
        {
            "priority": "P0",
            "failure_class": "Extracted routing is not consumed",
            "schema_move": "Collapse downstream view",
            "change": "Collapse routing_tags, intent_mode, and process policy into a retrieval_profile consumed by branch weights.",
            "why_it_makes_sense": (
                f"Routing tags fire {routing_total:,} times while routing_boost is {'empty' if routing_boost_empty else 'configured'}."
            ),
            "validation": "Run routing profile A/B and report exact_probe, hidden_target_search, feature_articulation, continuation, and novelty slices.",
        },
        {
            "priority": "P1",
            "failure_class": "Era vs hard-date confusion",
            "schema_move": "Collapse and type",
            "change": "Unify release_year_range and date hard_filters into temporal_constraint(kind, range, strength, evidence_text).",
            "why_it_makes_sense": f"{defect_lookup['release_range_excludes_gt']['n']:,} turns have release-year state excluding the GT year.",
            "validation": "No-year/soft-year ablation should recover excluded-GT turns without hurting explicit date-bound asks.",
        },
        {
            "priority": "P1",
            "failure_class": "Known rejection not enforced",
            "schema_move": "Keep plus normalize",
            "change": "Keep explicit_rejections but normalize to strict IDs and alias-verified names before final filtering.",
            "why_it_makes_sense": (
                f"Strict leak lower bound={cohort_lookup['rejection_leak_strict_top20']['n']:,}; "
                f"name-only audit adds {cohort_lookup['rejection_leak_name_only_without_strict_top20']['n']:,} uncertain cases."
            ),
            "validation": "Zero strict leaks; human-check name-only sample before widening the assertion.",
        },
        {
            "priority": "P2",
            "failure_class": "Metadata context absent from state/ranker",
            "schema_move": "Add context, not raw ranker constants",
            "change": "Thread available conversation_goal and user_profile fields through devset/blindset batch inputs; derive goal/culture affinity per candidate.",
            "why_it_makes_sense": "Organizer metadata is available in Blind-A raw rows and semantically useful, but raw session constants previously showed no within-turn lift and current inference drops them.",
            "validation": "Candidate-varying affinity must beat raw session/category/demographic features in session-grouped CV and remain usable in Blind-A inference.",
        },
        {
            "priority": "Do not start here",
            "failure_class": "More raw tags / raw demographics",
            "schema_move": "Do not add",
            "change": "Avoid adding extra raw tag buckets or feeding raw demographics/category as direct candidate features.",
            "why_it_makes_sense": "Tags already overlap GT often enough to be useful; raw demographics/category are candidate-constant unless transformed.",
            "validation": "Only revisit if candidate-varying tag or affinity features beat the simpler role/routing/ranker changes.",
        },
    ]

    def compact_state_json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))

    ideal_state_targets = [
        {
            "target_id": "role_typed_entities",
            "priority": "P0",
            "failure_classes": "Roleless entity carryover; Novelty prior-anchor failure",
            "sample_packs": "P0_roleless_stale_entity_failure; P0_novelty_prior_anchor_failure",
            "ideal_state_shape": compact_state_json(
                {
                    "entities": [
                        {
                            "type": "artist|track|album|tag",
                            "value": "Lana Del Rey",
                            "id": "optional_catalog_id",
                            "role": "current_target|seed|satisfied|history|contrast|rejected",
                            "source_turn": 4,
                            "mentioned_current_turn": True,
                            "anchor_strength": "0.0-1.0",
                            "use_as_retrieval_seed": True,
                            "evidence_text": "more like Lana but not the same artist",
                        }
                    ],
                    "current_target_entities": ["entity_id_or_value"],
                    "history_context_entities": ["entity_id_or_value"],
                }
            ),
            "minimum_viable_state": "For each entity: type, value/id, role, source_turn, use_as_retrieval_seed.",
            "extraction_probe": "On each 10-turn pack, ask whether every prior positive artist/track is current_target, seed, satisfied, history, contrast, or rejected.",
            "if_too_hard": "Keep mentioned_entities, but derive current_turn_entity and seed_allowed booleans from current utterance plus source_turn recency.",
            "downstream_use": "Only current_target/seed entities should fan out discography and exact-entity branches; satisfied/history entities become context or recency features.",
        },
        {
            "target_id": "target_artist_mode",
            "priority": "P0",
            "failure_classes": "Same-artist vs new-artist ambiguity; New-artist union@20 gap",
            "sample_packs": "P0_novelty_prior_anchor_failure; P0_new_artist_union20_gap_failure",
            "ideal_state_shape": compact_state_json(
                {
                    "target_artist_mode": "same_artist|new_artist|any_artist|unknown",
                    "confidence": "0.0-1.0",
                    "evidence_text": "different artist, same vibe",
                    "anchor_policy": "keep_recent|decay_prior|suppress_prior|suppress_rejected",
                }
            ),
            "minimum_viable_state": "target_artist_mode enum plus evidence_text and confidence.",
            "extraction_probe": "Check whether novelty and diversify asks reliably become new_artist or any_artist instead of continuation.",
            "if_too_hard": "Derive with rules: explicit 'more by X' => same_artist; 'different/new/other artists' => new_artist; otherwise unknown.",
            "downstream_use": "Switch retriever profile before fusion: continuation keeps album/artist branches; novelty boosts tag, CF, popularity, and similar-artist branches.",
        },
        {
            "target_id": "retrieval_profile",
            "priority": "P0",
            "failure_classes": "Extracted routing is not consumed; Good tag state but union@20 gap",
            "sample_packs": "P0_new_artist_union20_gap_failure; P1_positive_tag_retrieval_gap_failure",
            "ideal_state_shape": compact_state_json(
                {
                    "retrieval_profile": "continuation|novelty|exact_probe|feature_search|hidden_target_search",
                    "branch_weights": {
                        "artist_discography": 0.2,
                        "tag_metadata": 1.4,
                        "cf": 1.2,
                    },
                    "suppressions": ["prior_artist_discography"],
                    "fanout_topk": 100,
                }
            ),
            "minimum_viable_state": "retrieval_profile enum plus positive branch hints and suppressions.",
            "extraction_probe": "For each sampled turn, label which retriever branches should get more fanout and which old anchors should be suppressed.",
            "if_too_hard": "Do not spend LLM calls first; map existing routing_tags into routing_boost/profile configs and replay.",
            "downstream_use": "Consumes state before candidate generation, so union@20 can move instead of only final ranking.",
        },
        {
            "target_id": "temporal_constraint",
            "priority": "P1",
            "failure_classes": "Era vs hard-date confusion",
            "sample_packs": "P1_temporal_constraint_failure",
            "ideal_state_shape": compact_state_json(
                {
                    "temporal_constraint": {
                        "kind": "release_date|style_era|reference_era",
                        "range": [1995, 2004],
                        "strength": "hard|soft",
                        "apply_as_filter": False,
                        "evidence_text": "late 90s sound",
                    }
                }
            ),
            "minimum_viable_state": "kind, range, strength, and apply_as_filter.",
            "extraction_probe": "Ask whether the user meant literal release years or an aesthetic era; hard should be rare and explicit.",
            "if_too_hard": "Treat all inferred era ranges as soft boosts unless the user explicitly asks for a year/decade/date constraint.",
            "downstream_use": "Hard filters only for literal constraints; style/reference eras become compatibility features.",
        },
        {
            "target_id": "normalized_rejections",
            "priority": "P1",
            "failure_classes": "Known rejection not enforced",
            "sample_packs": "P1_rejection_guardrail_failure",
            "ideal_state_shape": compact_state_json(
                {
                    "rejections": [
                        {
                            "kind": "track|artist|album|tag|style",
                            "value": "metal",
                            "ids": ["optional_catalog_or_alias_id"],
                            "scope": "hard|soft",
                            "source_turn": 8,
                            "evidence_text": "not metal",
                        }
                    ]
                }
            ),
            "minimum_viable_state": "kind, value, scope, source_turn, plus strict IDs when resolver can provide them.",
            "extraction_probe": "Check whether each negative phrase is a hard rejection, a soft preference, or a contrast-only cue.",
            "if_too_hard": "Keep strict ID rejection as the canonical assertion; route name-only and style-only flags into manual/audit buckets.",
            "downstream_use": "Finalization guardrail: strict rejected IDs must be filtered after ranking; soft rejections become negative features.",
        },
        {
            "target_id": "feedback_carry_forward",
            "priority": "P0",
            "failure_classes": "Track feedback underused; Same-album ranker failure",
            "sample_packs": "P0_same_album_ranker_failure; P0_good_state_ranker_near_miss_failure",
            "ideal_state_shape": compact_state_json(
                {
                    "track_feedback": [
                        {
                            "track_id": "catalog_track_id",
                            "role": "accepted|satisfied|seed|rejected|contrast",
                            "source_turn": 3,
                            "carry_forward": "seed|context|avoid|none",
                            "artist_keep_strength": "0.0-1.0",
                            "album_keep_strength": "0.0-1.0",
                        }
                    ]
                }
            ),
            "minimum_viable_state": "track_id, role, source_turn, carry_forward.",
            "extraction_probe": "Separate 'I liked this, keep going' from 'that satisfied the ask, now move on'.",
            "if_too_hard": "Do not rerun extraction; derive same_album_recent, same_artist_recent, and rejected_track flags from play history and existing feedback.",
            "downstream_use": "Ranker features for same_album_recent, artist_recency, accepted-track proximity, and avoid flags.",
        },
        {
            "target_id": "album_artist_recency_features",
            "priority": "P0",
            "failure_classes": "Same-album continuation rank loss; Good state low recall",
            "sample_packs": "P0_same_album_ranker_failure; POS_clean_final_hit_control",
            "ideal_state_shape": compact_state_json(
                {
                    "candidate_features": {
                        "same_album_recent": True,
                        "same_artist_recent": True,
                        "artist_last_seen_turn_delta": 2,
                        "album_last_seen_turn_delta": 1,
                        "accepted_anchor_similarity": "0.0-1.0",
                    }
                }
            ),
            "minimum_viable_state": "No new extractor field required; compute same_album_recent, same_artist_recent, and recency deltas from history.",
            "extraction_probe": "No LLM probe. Verify feature computation on same-album and clean-hit packs.",
            "if_too_hard": "Use binary same_album_recent and same_artist_recent only.",
            "downstream_use": "Trained ranker/reranker feature; should improve final@20 without changing union@20.",
        },
        {
            "target_id": "positive_tag_compatibility",
            "priority": "P1",
            "failure_classes": "Positive tag retrieval gap",
            "sample_packs": "P1_positive_tag_retrieval_gap_failure",
            "ideal_state_shape": compact_state_json(
                {
                    "positive_tags": [
                        {
                            "raw": "late-night",
                            "canonical": "late night",
                            "role": "target_feature|context|contrast",
                            "confidence": "0.0-1.0",
                            "source_turn": 2,
                        }
                    ],
                    "negative_tags": [
                        {
                            "raw": "too heavy",
                            "canonical": "heavy metal",
                            "scope": "soft",
                        }
                    ],
                }
            ),
            "minimum_viable_state": "canonical tag, role, confidence, source_turn.",
            "extraction_probe": "Check whether tags are current target features or merely old context; normalize synonyms without adding many new fields.",
            "if_too_hard": "Keep raw positive_tags; add candidate tag-overlap and tag-compatibility features from catalog metadata.",
            "downstream_use": "Candidate generation/ranker compatibility feature; not a standalone reason to rerun the whole extractor.",
        },
        {
            "target_id": "exact_reference_guard",
            "priority": "P1",
            "failure_classes": "Exact entity success control; Named artist ranker failure",
            "sample_packs": "P0_named_artist_ranker_failure; POS_exact_entity_success_control",
            "ideal_state_shape": compact_state_json(
                {
                    "exact_references": [
                        {
                            "kind": "track|artist|album",
                            "value": "Dreams",
                            "ids": ["catalog_id"],
                            "confidence": "0.0-1.0",
                            "protect_topk": 20,
                            "evidence_text": "play Dreams",
                        }
                    ]
                }
            ),
            "minimum_viable_state": "kind, value/id, confidence, protect_topk.",
            "extraction_probe": "Verify explicit named-track controls stay exact and named-artist cases protect artist candidates without overfitting common words.",
            "if_too_hard": "Use strict title/artist lexical resolver and branch protection; avoid broad fuzzy matching for short/common titles.",
            "downstream_use": "Candidate protection and ranker exactness feature; also regression guardrail for any state rewrite.",
        },
        {
            "target_id": "goal_profile_context",
            "priority": "P2",
            "failure_classes": "Metadata context absent from state/ranker",
            "sample_packs": "P0_new_artist_union20_gap_failure; POS_clean_final_hit_control",
            "ideal_state_shape": compact_state_json(
                {
                    "goal_context": {
                        "listener_goal": "discover energetic songs for workouts",
                        "category": "J",
                        "specificity": "LH",
                        "preferred_musical_culture": "US mainstream",
                        "use_for": "routing|candidate_affinity|analysis_only",
                        "candidate_varying_features": [
                            "culture_conditioned_popularity",
                            "goal_text_match",
                            "user_cf_affinity",
                        ],
                    }
                }
            ),
            "minimum_viable_state": "Thread existing listener_goal, category, specificity, and preferred_musical_culture from raw rows into the state/ranker pack.",
            "extraction_probe": "No expensive per-turn extraction first; Blind-A raw rows already have these fields. Test whether metadata improves candidate-varying affinity features in CV.",
            "if_too_hard": "Use metadata only for slicing and diagnostics until candidate-varying features show lift; do not emulate fields that Blind-A already provides.",
            "downstream_use": "Novelty and popularity retrieval/ranker features; raw session constants are not enough.",
        },
    ]
    state_confusion_plan = [
        {
            "confusing_surface": "mentioned_entities treated as positive anchors",
            "risk": "The extractor stores prior liked/satisfied/history mentions in a field that downstream retrieval reads as current intent.",
            "decision": "Split roles instead of adding more positive-entity fields.",
            "field_economy_move": "Replace positive/current ambiguity with role_typed_entities and seed_allowed/use_as_retrieval_seed.",
            "small_test": "On stale and novelty packs, every old artist/track should be satisfied, history, contrast, or rejected unless the current user explicitly reuses it.",
        },
        {
            "confusing_surface": "turn_intent, intent_mode, routing_tags, and process_constraints all describe mode",
            "risk": "Multiple mode fields can disagree, and the current config does not consume routing_boost anyway.",
            "decision": "Collapse downstream to one retrieval_profile plus target_artist_mode.",
            "field_economy_move": "Keep raw fields for QA/debug; expose only retrieval_profile to candidate generation.",
            "small_test": "For novelty packs, retrieval_profile should suppress old-artist fanout and boost tag/CF/popularity branches.",
        },
        {
            "confusing_surface": "release_year_range plus date hard_filters",
            "risk": "The system can misread a style-era cue as a literal release-date filter.",
            "decision": "Collapse to temporal_constraint(kind, range, strength, apply_as_filter).",
            "field_economy_move": "One temporal object beats separate range/filter fields.",
            "small_test": "In year-excludes-GT samples, style_era/reference_era should be soft and apply_as_filter=false unless the user asks for literal years.",
        },
        {
            "confusing_surface": "positive_tags, lyrical_theme, attributes, and genre descriptors",
            "risk": "More tag-like fields can fragment the same signal and dilute retrieval/ranker features.",
            "decision": "Keep specialized fields, but canonicalize and assign roles instead of adding more raw buckets.",
            "field_economy_move": "Use positive_tag_compatibility with raw/canonical/role/source_turn; keep lyrical_theme for lyric/theme routing.",
            "small_test": "Positive-tag gap samples should preserve current target tags and avoid promoting old context tags.",
        },
        {
            "confusing_surface": "explicit_rejections mixed with soft dislikes or contrast cues",
            "risk": "A contrast cue can become an over-hard filter, while true rejected IDs can still leak without normalization.",
            "decision": "Keep rejections separate from contrast; normalize strict IDs and aliases.",
            "field_economy_move": "Use normalized_rejections with hard/soft scope and keep contrast as an entity role.",
            "small_test": "Rejected-ID samples should have zero strict leaks; name/style-only samples stay audit-only until hand-labeled.",
        },
        {
            "confusing_surface": "track_feedback, referenced_track_ids, and exact references",
            "risk": "A referenced track can mean exact target, satisfied prior item, seed, contrast, or rejection.",
            "decision": "Keep exact_reference_guard separate from feedback_carry_forward.",
            "field_economy_move": "Exact references protect candidates; feedback roles decide seed/context/avoid/none.",
            "small_test": "Exact controls stay final@20; same-album samples compute recency features without making every played track a seed.",
        },
        {
            "confusing_surface": "candidate features requested from the extractor",
            "risk": "Asking the LLM for derived ranker features increases cost and inconsistency.",
            "decision": "Do not extract deterministic features.",
            "field_economy_move": "Compute same_album_recent, same_artist_recent, artist_recency, album_recency, branch ranks, and exactness outside the LLM.",
            "small_test": "Same-album/ranker packs should test feature computation and trained scoring, not state reruns.",
        },
        {
            "confusing_surface": "organizer session metadata blended into turn state",
            "risk": "Session constants can look important but cannot rank candidates within a turn unless transformed.",
            "decision": "Keep organizer metadata in a separate goal_context namespace.",
            "field_economy_move": "Use listener_goal/category/specificity/profile as context, slices, or candidate-varying affinity; do not ask the extractor to recreate them.",
            "small_test": "Goal/profile experiments must beat raw-constant baselines in session-grouped CV.",
        },
    ]

    def low_recall_slice(slice_name: str, pred: Any, read: str, work: str) -> dict[str, Any]:
        summary = summarize_slice(pred)
        return {
            "slice": slice_name,
            "n": summary["n"],
            "final20": summary["final20"],
            "union20": summary["union20"],
            "union100": summary["union100"],
            "not_union20": summary["candidate_gap20"],
            "rank_loss20": summary["rank_loss20"],
            "read": read,
            "work": work,
        }

    good_state_low_recall = [
        low_recall_slice(
            "Positive tags overlap GT",
            lambda r: r["positive_tag_overlap_gt"],
            "The tag state often contains a semantically relevant signal, but that does not guarantee the GT reaches union@20.",
            "Do not rewrite tags first; route/tag-rank candidates better and add tag-overlap features to the trained scorer.",
        ),
        low_recall_slice(
            "Current user names GT artist",
            lambda r: r["gt_artist_named"],
            "The user gave an explicit artist signal, so misses here are usually track selection, final ranking, or exact-artist candidate protection.",
            "Protect named-artist candidates, then train ranker features for branch rank, artist recency, album affinity, exactness, and popularity.",
        ),
        low_recall_slice(
            "GT primary album already heard",
            lambda r: r["same_primary_album_continuation"],
            "History is informative and the candidate is often nearby, but final ranking still underuses album/artist recency.",
            "Add same_album_recent and artist_recency features; measure continuation NDCG@20 and new-artist guardrails.",
        ),
        low_recall_slice(
            "Routing tag active",
            lambda r: r["state_routing_count"] > 0,
            "The state detects a route signal, but the config does not translate it into branch weights.",
            "Wire retrieval_profile/routing_boost before adding new retrievers; measure union@20/100 per tag.",
        ),
        low_recall_slice(
            "Popularity cue + new artist",
            lambda r: r["popularity_cue"] and r["midconv_new_artist"],
            "The user cue is clear, but novelty plus popularity needs canonical candidates outside old anchors.",
            "Add target_artist_mode and genre/era-conditioned popularity or CF retrieval for novelty profiles.",
        ),
        low_recall_slice(
            "Release range present and GT in range",
            lambda r: r["release_range_set"] and not r["release_range_excludes_gt"],
            "Temporal state can be correct and still not retrieve the target; this is not just a year-extraction bug.",
            "Use temporal compatibility as a soft feature and focus hard-filter work on the exclude-GT failures.",
        ),
        low_recall_slice(
            "Track feedback present",
            lambda r: r["state_track_feedback_count"] > 0,
            "The state has behavioral feedback, but it needs a downstream role: keep-near, move-on, avoid, or satisfied.",
            "Map feedback to entity roles plus artist/album recency features; sample accepted vs novelty turns.",
        ),
    ]

    def sample_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            bool(row.get("final20")),
            bool(row.get("union20")),
            bool(row.get("union100")),
            row.get("best_branch_rank") if row.get("best_branch_rank") is not None else 999_999,
            -(row.get("popularity") or 0),
            row["session_id"],
            row["turn"],
        )

    def near_miss_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            not bool(row.get("union20")),
            bool(row.get("final20")),
            row.get("best_branch_rank") if row.get("best_branch_rank") is not None else 999_999,
            -(row.get("popularity") or 0),
            row["session_id"],
            row["turn"],
        )

    used_sample_keys: set[tuple[str, int]] = set()

    def pick_sample_rows(
        predicate: Any,
        *,
        limit: int,
        sort_key: Any = sample_sort_key,
        exclude_used: bool = True,
    ) -> list[dict[str, Any]]:
        candidates = [
            r
            for r in rows
            if predicate(r) and (not exclude_used or (r["session_id"], r["turn"]) not in used_sample_keys)
        ]
        candidates.sort(key=sort_key)
        selected = candidates[:limit]
        if exclude_used:
            used_sample_keys.update((r["session_id"], r["turn"]) for r in selected)
        return selected

    def build_experiment_pack(
        name: str,
        hypothesis: str,
        rows_for_pack: list[dict[str, Any]],
        *,
        class_type: str,
        reason_to_test: str,
        expected_change: str,
        success_metric: str,
    ) -> dict[str, Any]:
        sample_turns = [
            experiment_sample_row(
                row,
                pack=name,
                class_type=class_type,
                reason_to_test=reason_to_test,
                expected_change=expected_change,
                success_metric=success_metric,
            )
            for row in rows_for_pack
        ]
        return {
            "pack": name,
            "class_type": class_type,
            "hypothesis": hypothesis,
            "n": len(sample_turns),
            "target_n": STATE_TEST_TURNS_PER_CLASS,
            "reason_to_test": reason_to_test,
            "expected_change": expected_change,
            "success_metric": success_metric,
            "sample_turns": sample_turns,
        }

    STATE_TEST_TURNS_PER_CLASS = 10
    state_experiment_packs = [
        build_experiment_pack(
            "P0_roleless_stale_entity_failure",
            "A role-typed state rerun should stop stale/satisfied entities from acting like current anchors.",
            pick_sample_rows(
                lambda r: r["stale_artist_or_track_state"] and not r["final20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
            ),
            class_type="failure",
            reason_to_test="These turns show stale positive artist/track state and are good smoke tests for source_turn, recency, and seed/satisfied/history roles.",
            expected_change="After extraction rerun, stale prior entities should move out of current positive anchors or get lower anchor_strength.",
            success_metric="State QA first: stale-current-positive count drops on all sampled turns. Retrieval QA second: union@20/100 should not get worse, and target branch rank should improve on at least some samples.",
        ),
        build_experiment_pack(
            "P0_novelty_prior_anchor_failure",
            "Novelty/diversify turns should not keep old artists as active positive anchors.",
            pick_sample_rows(
                lambda r: r["novelty_prior_anchor_conflict"] and not r["final20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
            ),
            class_type="failure",
            reason_to_test="These turns explicitly ask for novelty or a different direction while prior artists remain anchored.",
            expected_change="Prior artists should be labeled satisfied/history/contrast rather than current seed; retrieval_profile should reduce old-artist discography and centroid pressure.",
            success_metric="State QA: prior anchors are not current positive seeds. Recall QA: best_branch_rank or union@20 improves for novelty/new-artist targets.",
        ),
        build_experiment_pack(
            "P0_new_artist_union20_gap_failure",
            "Novelty/new-artist turns need a different retrieval profile, not just better final ranking.",
            pick_sample_rows(
                lambda r: r["midconv_new_artist"]
                and (r["novelty_prior_anchor_conflict"] or r["popularity_cue"])
                and not r["union20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
            ),
            class_type="failure",
            reason_to_test="These turns are not in union@20, so a ranker alone cannot fix them. They test target_artist_mode plus retrieval_profile routing.",
            expected_change="target_artist_mode should become new_artist/any_artist, prior artists should be satisfied/history, and routing should upweight tag/metadata/popularity/CF branches.",
            success_metric="Primary: GT enters union@20 or improves best_branch_rank. Secondary: final@20 after a stable ranker should improve without continuation regression.",
        ),
        build_experiment_pack(
            "P1_temporal_constraint_failure",
            "Temporal state should distinguish style-era cues from hard release-date filters.",
            pick_sample_rows(
                lambda r: r["release_range_excludes_gt"] and not r["final20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
            ),
            class_type="failure",
            reason_to_test="These turns have release-year state that excludes the GT catalog year.",
            expected_change="Temporal constraints should separate style-era from hard release-date bounds, with soft compatibility used for aesthetic eras.",
            success_metric="Target remains eligible and best_branch_rank improves under soft/no-year ablation; explicit date-bound turns stay clean.",
        ),
        build_experiment_pack(
            "P1_rejection_guardrail_failure",
            "Rejected entities should never leak into final top-20.",
            pick_sample_rows(
                lambda r: r["rejection_leak_top20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
                sort_key=near_miss_sort_key,
            ),
            class_type="failure",
            reason_to_test="These turns have explicit rejection state but still show rejected ID/name leakage in final top-20.",
            expected_change="Rejected IDs and verified aliases should be normalized and filtered after finalization.",
            success_metric="Zero strict rejected ID leakage; name-only flags are hand-labeled before widening assertions.",
        ),
        build_experiment_pack(
            "P0_named_artist_ranker_failure",
            "Named-artist turns usually have the right entity but still lose the right track in ranking/finalization.",
            pick_sample_rows(
                lambda r: r["gt_artist_named"] and r["union20"] and not r["final20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
                sort_key=near_miss_sort_key,
            ),
            class_type="failure",
            reason_to_test="The current user names the GT artist and the GT is reachable in union@20, so extraction is often adequate and ranker/finalization is the failure.",
            expected_change="A state-aware scorer should protect named-artist candidates and use branch rank, exactness, album/artist recency, and popularity features.",
            success_metric="GT moves into final top-20 without hurting exact-track or rejection guardrails.",
        ),
        build_experiment_pack(
            "P0_same_album_ranker_failure",
            "Album-continuation turns need album/artist recency features, not another state extraction pass.",
            pick_sample_rows(
                lambda r: r["same_primary_album_continuation"] and r["union20"] and not r["final20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
                sort_key=near_miss_sort_key,
            ),
            class_type="failure",
            reason_to_test="The GT primary album has already been heard and the candidate is in union@20, but final ranking misses it.",
            expected_change="Ranker should consume same_album_recent, artist_recency, track_feedback role, and branch-rank features.",
            success_metric="Same-album continuation final@20/NDCG@20 improves while new-artist slices do not regress.",
        ),
        build_experiment_pack(
            "P1_positive_tag_retrieval_gap_failure",
            "Good tag state can still fail candidate generation when stale anchors or weak routing dominate.",
            pick_sample_rows(
                lambda r: r["positive_tag_overlap_gt"] and not r["union20"] and not r["final20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
            ),
            class_type="failure",
            reason_to_test="These turns have at least one positive tag overlapping GT catalog tags, yet the GT is outside union@20.",
            expected_change="Use tag compatibility in retrieval_profile/ranker features and reduce stale-anchor pressure before rewriting tag extraction.",
            success_metric="GT enters union@20 or best_branch_rank improves; tag-overlap final@20 does not regress.",
        ),
        build_experiment_pack(
            "P0_good_state_ranker_near_miss_failure",
            "Some extraction is already good enough; these turns should test state-aware ranking rather than an extractor rerun.",
            pick_sample_rows(
                lambda r: (
                    r["gt_artist_named"]
                    or r["same_primary_album_continuation"]
                    or r["positive_tag_overlap_gt"]
                    or r["state_track_feedback_count"] > 0
                )
                and r["union20"]
                and not r["final20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
                sort_key=near_miss_sort_key,
            ),
            class_type="failure",
            reason_to_test="These turns already have useful state or a union@20 candidate, so the failure is ranking/finalization, not missing extraction.",
            expected_change="A trained scorer should consume branch ranks, role labels, same_album_recent, artist_recency, tag overlap, exactness, popularity, and guardrail flags.",
            success_metric="GT moves into final top-20 while rejection/year/exact guardrails stay clean.",
        ),
        build_experiment_pack(
            "POS_exact_entity_success_control",
            "Exact or very explicit entity cases should remain solved after any state/ranker change.",
            pick_sample_rows(
                lambda r: r["gt_track_named"] and r["final20"],
                limit=STATE_TEST_TURNS_PER_CLASS,
                sort_key=near_miss_sort_key,
            ),
            class_type="positive_control",
            reason_to_test="These are high-confidence positive controls: exact named-track turns currently succeed.",
            expected_change="No change should demote exact named-track candidates or break entity lookup.",
            success_metric="All sampled exact-entity controls remain final@20 after state/routing/ranker changes.",
        ),
        build_experiment_pack(
            "POS_clean_final_hit_control",
            "Clean final hits should stay stable while failure classes improve.",
            pick_sample_rows(
                lambda r: r["final20"]
                and not r["stale_artist_or_track_state"]
                and not r["novelty_prior_anchor_conflict"]
                and not r["release_range_excludes_gt"]
                and not r["rejection_leak_top20"]
                and bool(r["state_has_entities_or_tags"]),
                limit=STATE_TEST_TURNS_PER_CLASS,
                sort_key=near_miss_sort_key,
            ),
            class_type="positive_control",
            reason_to_test="These turns have useful state and already succeed, so they are regression controls for broad pipeline changes.",
            expected_change="State/routing/ranker changes should preserve final@20 and avoid introducing rejection/year/exact regressions.",
            success_metric="All sampled clean-hit controls remain final@20; ranks should not degrade materially.",
        ),
    ]
    ideal_target_lookup = {row["target_id"]: row for row in ideal_state_targets}
    pack_to_ideal_targets = {
        "P0_roleless_stale_entity_failure": ["role_typed_entities", "feedback_carry_forward"],
        "P0_novelty_prior_anchor_failure": ["role_typed_entities", "target_artist_mode", "retrieval_profile"],
        "P0_new_artist_union20_gap_failure": ["target_artist_mode", "retrieval_profile", "goal_profile_context"],
        "P1_temporal_constraint_failure": ["temporal_constraint"],
        "P1_rejection_guardrail_failure": ["normalized_rejections"],
        "P0_named_artist_ranker_failure": ["exact_reference_guard", "role_typed_entities"],
        "P0_same_album_ranker_failure": ["feedback_carry_forward", "album_artist_recency_features"],
        "P1_positive_tag_retrieval_gap_failure": ["positive_tag_compatibility", "retrieval_profile"],
        "P0_good_state_ranker_near_miss_failure": [
            "feedback_carry_forward",
            "album_artist_recency_features",
            "exact_reference_guard",
        ],
        "POS_exact_entity_success_control": ["exact_reference_guard"],
        "POS_clean_final_hit_control": [
            "role_typed_entities",
            "album_artist_recency_features",
            "positive_tag_compatibility",
        ],
    }
    for pack in state_experiment_packs:
        target_ids = pack_to_ideal_targets.get(pack["pack"], [])
        targets = [ideal_target_lookup[target_id] for target_id in target_ids if target_id in ideal_target_lookup]
        pack["ideal_state_target_ids"] = target_ids
        pack["ideal_state_targets"] = "; ".join(target_ids)
        pack["state_terms_to_check"] = " | ".join(row["minimum_viable_state"] for row in targets)
        pack["extractor_probe"] = " | ".join(row["extraction_probe"] for row in targets)
    state_experiment_turns = [
        sample
        for pack in state_experiment_packs
        for sample in pack["sample_turns"]
    ]

    counting_reconciliation = [
        {
            "claim": "GT primary album already heard",
            "report_value": f"{cohort_lookup['same_primary_album_continuation']['n']:,}",
            "alternate_value": f"{cohort_lookup['same_album_continuation']['n']:,} any-album",
            "basis": "Primary/first album_id is the conservative continuation count; any album_id overlap includes multi-album catalog metadata.",
            "decision": "Use primary-album as the canonical strict album-continuation count; keep any-album as broader sensitivity.",
        },
        {
            "claim": "Album miss fused-rank buckets",
            "report_value": (
                f"primary misses={len(same_primary_album_misses):,}; buckets sum="
                f"{primary_album_fused_top20_demoted + primary_album_fused_21_100 + primary_album_fused_101_1000 + primary_album_fused_absent:,}"
            ),
            "alternate_value": (
                f"album counterfactual miss_total={int((album_fix.get('counterfactual') or {}).get('miss_total') or 0):,}; "
                f"21-100={int((album_fix.get('counterfactual') or {}).get('resc_21_100') or 0):,}; "
                f"101-1000={int((album_fix.get('counterfactual') or {}).get('deep_101_1000') or 0):,}; "
                f"absent={int((album_fix.get('counterfactual') or {}).get('absent') or 0):,}"
            ),
            "basis": "The current report's trace proxy buckets by fused_rank and now includes fused<=20/final-missed rows; the album-completion counterfactual uses a separate replay denominator.",
            "decision": "Use the trace proxy for failure anatomy and the counterfactual for measured upside. Do not compare raw bucket values without the denominator.",
        },
        {
            "claim": "Rejection leak turns",
            "report_value": f"{defect_lookup['rejection_leak_top20']['n']:,}",
            "alternate_value": (
                f"{cohort_lookup['rejection_leak_strict_top20']['n']:,} strict ID; "
                f"{cohort_lookup['rejection_leak_name_only_without_strict_top20']['n']:,} additional name-only"
            ),
            "basis": "Broad audit catches rejected track/artist IDs plus explicit rejection names; strict audit only counts resolver IDs.",
            "decision": "Treat broad count as an upper audit bound and strict count as the verified lower bound until a hand sample labels name-only cases.",
        },
        {
            "claim": "Routing tag counts",
            "report_value": (
                f"exact_entity_probe={routing_counts.get('exact_entity_probe', 0):,}; "
                f"hidden_target_search={routing_counts.get('hidden_target_search', 0):,}"
            ),
            "alternate_value": "Sample extrapolations can differ.",
            "basis": "Full trace pass counts active boolean routing tags on all 8,000 rows.",
            "decision": "Keep the full-trace counts. The important bug is not extraction frequency; routing_boost is empty, so tags are not consumed by weighted routing.",
        },
        {
            "claim": "Current user names GT artist",
            "report_value": f"{cohort_lookup['gt_artist_named_current']['n']:,}",
            "alternate_value": "Alias/partial-name methods can move the count by roughly tens of turns.",
            "basis": "Lexical phrase match against catalog artist_name values in the current user turn.",
            "decision": "Rates are the stable takeaway: named-artist turns have very high union@20 but lower final@20, so they are a track-selection/ranking slice.",
        },
        {
            "claim": "Stale positive entity turns",
            "report_value": f"{defect_lookup['stale_artist_or_track_state']['n']:,}",
            "alternate_value": "More inclusive substring heuristics count slightly more.",
            "basis": "Positive artist/track state value not lexically present in the current user turn.",
            "decision": "Use as a directional state QA metric, not a perfect semantic label.",
        },
        {
            "claim": "Exact named-track turns",
            "report_value": f"{task_lookup['exact_track_named']['n']:,}",
            "alternate_value": "Looser title-substring methods count more.",
            "basis": "Strict current-turn track-title match with safeguards for short/common titles.",
            "decision": "Keep the stricter count to avoid false positives from common words.",
        },
    ]

    routing_reconciliation = [
        {
            "tag": tag,
            "active_turns": count,
            "basis": "full-trace active boolean count",
            "consumed": "no weighted routing effect because config routing_boost is empty" if routing_boost_empty else "routing_boost is configured",
        }
        for tag, count in routing_counts.most_common()
    ]

    role_evidence = {
        "SEED": (
            f"Current-user GT artist named: n={cohort_lookup['gt_artist_named_current']['n']:,}, "
            f"union@20={pct(cohort_lookup['gt_artist_named_current']['union20'])}; exact named-track slice has n={task_lookup['exact_track_named']['n']:,}."
        ),
        "SATISFIED": (
            f"Stale positive artist/track state appears in {defect_lookup['stale_artist_or_track_state']['n']:,} turns; "
            "many are prior played artists that should be context, not fresh anchors."
        ),
        "CONTRAST": (
            f"Contrast-cue turns: n={cohort_lookup['contrast_cue']['n']:,}; "
            f"novelty + prior-anchor conflicts: n={defect_lookup['novelty_prior_anchor_conflict']['n']:,}."
        ),
        "HISTORY": (
            f"Roleless history is the broadest defect: n={defect_lookup['stale_artist_or_track_state']['n']:,}, "
            "detected when positive entities are absent from the current user turn."
        ),
        "REJECTED": (
            f"Explicit rejection state exists in {cohort_lookup['rejection_state_present']['n']:,} turns; "
            f"leak audit flags {defect_lookup['rejection_leak_top20']['n']:,} turns."
        ),
    }
    taxonomy_source = (supplemental.get("extraction") or {}).get("taxonomy") or [
        {
            "cue": "similar to / like / in the vein of X",
            "role": "SEED",
            "current": "often positive anchor",
            "ideal": "anchor on",
        },
        {
            "cue": "X was great, now more / other / else",
            "role": "SATISFIED",
            "current": "often still a positive anchor",
            "ideal": "keep as context, do not anchor as current target",
        },
        {
            "cue": "different from / not like / instead of X",
            "role": "CONTRAST",
            "current": "can become a positive anchor",
            "ideal": "anchor off; optionally repel",
        },
        {
            "cue": "X named earlier, not this turn",
            "role": "HISTORY",
            "current": "can remain positive",
            "ideal": "drop from current targets unless re-mentioned",
        },
        {
            "cue": "not X / no more X / stop X",
            "role": "REJECTED",
            "current": "hard-drop path exists",
            "ideal": "hard drop and assert no leakage",
        },
    ]
    role_taxonomy = [
        {
            "cue": clean_text(row.get("cue"), 150),
            "role": row.get("role"),
            "current_behavior": clean_text(row.get("current"), 120),
            "desired_behavior": clean_text(row.get("ideal"), 160),
            "current_evidence": role_evidence.get(str(row.get("role") or ""), ""),
        }
        for row in taxonomy_source
    ]

    continuation_deep_dive = {
        "summary": (
            f"Continuation turns are {cont['n']:,} turns with final@20 {pct(cont['final20'])}, "
            f"union@20 {pct(cont['union20'])}, and union@100 {pct(cont['union100'])}. "
            f"Primary-album continuations are {same_primary_album['n']:,} turns with final@20 {pct(same_primary_album['final20'])} "
            f"and union@20 {pct(same_primary_album['union20'])}. The broader any-album sensitivity is {same_album['n']:,} turns."
        ),
        "work": "This is the cleanest ranker/state-use lane: preserve most-recent artist/album evidence, but learn which track to choose instead of blindly demoting same-artist candidates.",
        "buckets": [
            {
                "label": row.get("label"),
                "n": row.get("n"),
                "share": row.get("pct"),
                "cause": clean_text(row.get("cause"), 180),
                "fix": clean_text(row.get("fix"), 180),
            }
            for row in continuation_fix.get("buckets") or []
        ],
        "album_signal": {
            "current_same_album_n": same_album["n"],
            "current_same_album_final20": same_album["final20"],
            "current_same_album_union20": same_album["union20"],
            "current_same_album_union100": same_album["union100"],
            "current_primary_album_n": same_primary_album["n"],
            "current_primary_album_final20": same_primary_album["final20"],
            "current_primary_album_union20": same_primary_album["union20"],
            "current_primary_album_union100": same_primary_album["union100"],
            "primary_album_miss_total": len(same_primary_album_misses),
            "primary_album_fused_top20_demoted": primary_album_fused_top20_demoted,
            "primary_album_fused_21_100": primary_album_fused_21_100,
            "primary_album_fused_101_1000": primary_album_fused_101_1000,
            "primary_album_fused_absent": primary_album_fused_absent,
            "primary_album_fused_bucket_sum": (
                primary_album_fused_top20_demoted
                + primary_album_fused_21_100
                + primary_album_fused_101_1000
                + primary_album_fused_absent
            ),
            "same_album_miss_total": len(same_album_misses),
            "same_album_fused_top20_demoted": album_fused_top20_demoted,
            "same_album_fused_21_100": album_fused_21_100,
            "same_album_fused_101_1000": album_fused_101_1000,
            "same_album_fused_absent": album_fused_absent,
            "same_album_fused_bucket_sum": (
                album_fused_top20_demoted + album_fused_21_100 + album_fused_101_1000 + album_fused_absent
            ),
            "audit_counterfactual": album_fix.get("counterfactual") or {},
            "audit_same_album_pct": album_fix.get("same_album_pct"),
            "audit_upside": clean_text(album_fix.get("upside"), 260),
            "action": "Prototype album-affinity and recent-artist features inside a ranker over union@100/200; track continuation NDCG@20 separately.",
        },
    }

    new_artist = task_lookup["midconv_new_artist"]
    novelty_new = cohort_lookup["novelty_cue_new_artist"]
    popularity_new = cohort_lookup["popularity_cue_new_artist"]
    newartist_fix = (supplemental.get("fixes") or {}).get("newartist") or {}
    newartist_deep_dive = {
        "summary": (
            f"Mid-conversation new-artist turns are {new_artist['n']:,} turns with final@20 {pct(new_artist['final20'])}, "
            f"union@20 {pct(new_artist['union20'])}, and union@100 {pct(new_artist['union100'])}. "
            f"Even explicit novelty-cue + new-artist turns are weak: n={novelty_new['n']:,}, final@20 {pct(novelty_new['final20'])}, "
            f"union@20 {pct(novelty_new['union20'])}."
        ),
        "work": "This is the candidate-generation lane. A trained ranker helps only when the candidate is already in union@100/200; novelty state must also change which retrievers fire and which priors dominate.",
        "buckets": [
            {
                "label": row.get("label"),
                "n": row.get("n"),
                "share": row.get("pct"),
                "cause": clean_text(row.get("cause"), 180),
                "fix": clean_text(row.get("fix"), 180),
            }
            for row in newartist_fix.get("buckets") or []
        ],
        "current_slices": [
            {
                "slice": "All mid-conversation new artist",
                "n": new_artist["n"],
                "final20": new_artist["final20"],
                "union20": new_artist["union20"],
                "union100": new_artist["union100"],
            },
            {
                "slice": "Novelty cue + new artist",
                "n": novelty_new["n"],
                "final20": novelty_new["final20"],
                "union20": novelty_new["union20"],
                "union100": novelty_new["union100"],
            },
            {
                "slice": "Popularity cue + new artist",
                "n": popularity_new["n"],
                "final20": popularity_new["final20"],
                "union20": popularity_new["union20"],
                "union100": popularity_new["union100"],
            },
        ],
    }

    feature_catalog = [
        {
            "feature": "candidate_artist_role",
            "grain": "turn x candidate",
            "why": "Separates seed, satisfied, contrast, history, and rejected entities instead of treating all positive mentions as anchors.",
            "source": "state role taxonomy + stale-state audit",
            "validation": "Lower stale positive state rate; improve new-artist union@20 without exact/continuation regression.",
        },
        {
            "feature": "artist_recency / keep_strength",
            "grain": "turn x candidate artist",
            "why": "Continuation needs the most recent relevant artist, while novelty needs older anchors decayed.",
            "source": "continuation bucket and stale-anchor examples",
            "validation": "Continuation NDCG@20 up; new-artist candidate gap not worse.",
        },
        {
            "feature": "same_album_recent",
            "grain": "turn x candidate album",
            "why": "Album-mates are highly retrievable and often rank just outside top-20.",
            "source": "current same-album cohort + album counterfactual audit",
            "validation": "Same-album continuation final@20/NDCG@20; inspect same-artist diversity side effects.",
        },
        {
            "feature": "is_new_artist_for_session",
            "grain": "turn x candidate artist",
            "why": "Novelty asks should favor unseen artists; continuation asks should not.",
            "source": "new-artist mode split",
            "validation": "New-artist union/final@20 by novelty-cue slice; continuation guardrail.",
        },
        {
            "feature": "genre_or_era_conditioned_popularity",
            "grain": "turn x candidate",
            "why": "Broad novelty asks often need a canonical/popular candidate within requested tags or era.",
            "source": "new-artist genre-fit/popular hypothesis + popularity-cue slice",
            "validation": "Lift on popularity-cue and LL/J/K slices without generic popularity takeover.",
        },
        {
            "feature": "user_cf_or_culture_affinity",
            "grain": "turn x candidate",
            "why": "Raw demographics are candidate-constant, but user/culture affinity varies by track.",
            "source": "user_profile metadata + CF branch availability",
            "validation": "Session-grouped CV; preferred_musical_culture slices; no user-id leakage.",
        },
        {
            "feature": "constraint_satisfaction",
            "grain": "turn x candidate",
            "why": "Year and rejection state should be modeled/guarded, not allowed to silently suppress valid targets or leak invalid ones.",
            "source": "release-year and rejection audits",
            "validation": "Zero rejection leaks; lower year-excludes-GT miss rate; no exact-turn regression.",
        },
        {
            "feature": "branch_rank_bundle",
            "grain": "turn x candidate",
            "why": "Replacing RRF needs the ranker to see which branch found the candidate and at what rank.",
            "source": "union@20 vs final@20 gap",
            "validation": "Session-grouped CV over union@100/200 beats RRF on NDCG@20.",
        },
    ]

    album_counterfactual = album_fix.get("counterfactual") or {}
    supp_feature_catalog = ((supplemental.get("fixes") or {}).get("feature_catalog") or {})
    ruled_out_lookup = {
        str(item[0]).lower(): str(item[1])
        for item in ((supplemental.get("fixes") or {}).get("ruled_out") or [])
        if isinstance(item, list) and len(item) >= 2
    }
    measured_levers = [
        {
            "lever": "Album-affinity / album completion",
            "status": "measured counterfactual",
            "result": (
                f"{int(album_counterfactual.get('resc_21_100') or 0):,} of "
                f"{int(album_counterfactual.get('miss_total') or 0):,} same-album misses are rescuable from fused rank 21-100; "
                f"{int(album_counterfactual.get('deep_101_1000') or 0):,} sit at 101-1000 and "
                f"{int(album_counterfactual.get('absent') or 0):,} are absent. Reported ceiling: about +6pp Hit@20."
                if album_counterfactual
                else "No measured album counterfactual found; use the current trace fused-rank proxy below."
            ),
            "decision": "Keep as a P0 ranker feature: same_album_recent plus artist_recency, with continuation and new-artist guardrails.",
            "source": "album counterfactual audit",
        },
        {
            "lever": "Current trace album fused-rank anatomy",
            "status": "trace recount",
            "result": (
                f"Primary-album misses={len(same_primary_album_misses):,}; fused<=20/final-missed="
                f"{primary_album_fused_top20_demoted:,}, fused 21-100={primary_album_fused_21_100:,}, "
                f"fused 101-1000={primary_album_fused_101_1000:,}, absent={primary_album_fused_absent:,}; "
                f"bucket sum={primary_album_fused_top20_demoted + primary_album_fused_21_100 + primary_album_fused_101_1000 + primary_album_fused_absent:,}."
            ),
            "decision": "Read fused<=20 as post-fusion/finalization loss, not album-retrieval absence.",
            "source": "current trace rows",
        },
        {
            "lever": "RRF-fused cross-encoder reranker",
            "status": "measured adjacent-pool bakeoff" if reranker_bakeoff.get("available") else "source not found",
            "result": (
                f"NDCG@20 {reranker_bakeoff.get('base_ndcg20'):.4f} -> {reranker_bakeoff.get('rerank_ndcg20'):.4f} "
                f"({pct(reranker_bakeoff.get('relative_ndcg20'))} relative); Hit@20 "
                f"{reranker_bakeoff.get('base_hit20'):.4f} -> {reranker_bakeoff.get('rerank_hit20'):.4f}. "
                f"Scope: {reranker_bakeoff.get('scope')}"
                if reranker_bakeoff.get("available")
                else "No local reranker bakeoff artifact was found."
            ),
            "decision": "Use rank fusion or a trained scorer over RRF/branch features; do not replace RRF with raw cross-encoder score.",
            "source": "cross_encoder_rerank_bakeoff.md",
        },
        {
            "lever": "Candidate-level is_new_artist feature",
            "status": "measured small positive",
            "result": next(
                (
                    f"{item[1]} on {item[2]}"
                    for item in supp_feature_catalog.get("build") or []
                    if isinstance(item, list) and item and str(item[0]) == "is_new_artist"
                ),
                "Not found in supplemental feature catalog.",
            ),
            "decision": "Use as a ranker feature, but still fix candidate generation because new-artist GTs are often outside union@20.",
            "source": "feature experiment audit",
        },
        {
            "lever": "Raw session/category/demographic features in a within-turn ranker",
            "status": "measured no lift",
            "result": ruled_out_lookup.get(
                "session features / demographics as ranker inputs",
                "0 lift signal not found; still candidate-constant within a turn by construction.",
            ),
            "decision": "Do not feed raw constants directly; derive candidate-varying culture/user-CF/popularity affinity or use them for routing/slicing.",
            "source": "feature-ablation audit",
        },
        {
            "lever": "Rarity-weighted / IDF tags",
            "status": "measured negative",
            "result": ruled_out_lookup.get("rarity-weighted (idf) tags", "Negative result not found in supplemental audit."),
            "decision": "Do not prioritize IDF-tag weighting; tags are useful, but role/routing and candidate-varying behavioral features are stronger.",
            "source": "feature-ablation audit",
        },
    ]

    not_first = [
        {
            "idea": "Use union@1000 as the ranker target",
            "decision": "Do not headline it.",
            "evidence": f"Union@1000 is {pct(headline['union1000'])}, but it is an oracle over very large branch pools. Use union@20 as the gap line and union@100/200 as ranker workbench.",
        },
        {
            "idea": "Feed raw category/specificity/demographics directly into a within-turn ranker",
            "decision": "Use them as slices or derive candidate-varying features.",
            "evidence": "Category, specificity, and demographics are session constants within a candidate list. They can condition retrieval/ranker behavior but cannot distinguish candidate A vs B unless transformed.",
        },
        {
            "idea": "Overhaul tag extraction first",
            "decision": "Not first.",
            "evidence": f"Positive tags overlap a GT tag on {pct(positive_tag_overlap_rate)} of tagged turns; entity role/recency has a broader and clearer failure signature.",
        },
        {
            "idea": "Tune RRF alone",
            "decision": "Insufficient.",
            "evidence": f"New-artist union@20 is only {pct(new_artist['union20'])}. RRF replacement helps near misses, not absent candidates.",
        },
        {
            "idea": "Replace RRF with raw cross-encoder score",
            "decision": "Do not use replace mode.",
            "evidence": "The adjacent reranker bakeoff found replace-mode reranking structurally harmful; rank-fuse RRF and reranker scores or train a scorer over branch/state features.",
        },
        {
            "idea": "IDF-weight positive tags",
            "decision": "Not first.",
            "evidence": ruled_out_lookup.get("rarity-weighted (idf) tags", "The supplemental audit marks this as lower priority than state roles/routing."),
        },
    ]

    experiment_backlog = [
        {
            "experiment": "Role-typed entity-state extractor QA",
            "status": "not run in this report",
            "why": "Diagnostics show stale/roleless entity state, but the extractor/schema change needs a before/after run.",
            "measurement": "stale positive entity rate, novelty-prior-anchor conflict count, final/union@20 by new-artist and continuation.",
        },
        {
            "experiment": "Album-affinity / artist-recency ranker A/B",
            "status": "measured counterfactual exists; implementation A/B still needed",
            "why": (
                f"Primary-album misses={len(same_primary_album_misses):,}; fused<=20/final-missed={primary_album_fused_top20_demoted:,}; "
                f"fused 21-100={primary_album_fused_21_100:,}; fused 101-1000={primary_album_fused_101_1000:,}; "
                f"fused absent={primary_album_fused_absent:,}. "
                f"Any-album sensitivity misses={len(same_album_misses):,}."
            ),
            "measurement": "session-grouped CV or replayed scorer over union@100/200; continuation NDCG@20, same-album final@20, new-artist guardrail.",
        },
        {
            "experiment": "Routing-boost configuration A/B",
            "status": "not run in this report",
            "why": (
                f"Routing tags fire {routing_total:,} times, but routing_boost is "
                f"{'empty' if routing_boost_empty else 'configured'}; this means turn-type signals are not changing branch weights."
            ),
            "measurement": "Run explicit routing profiles by tag; report union@20/100 by exact_entity_probe, hidden_target_search, feature_articulation, novelty, and continuation slices.",
        },
        {
            "experiment": "Novelty retriever profile A/B",
            "status": "not run in this report",
            "why": f"New-artist union@20 is {pct(new_artist['union20'])}; ranker changes cannot rescue absent candidates.",
            "measurement": "new-artist and novelty-cue union@20/100 first, then final@20/NDCG@20.",
        },
        {
            "experiment": "No-year / soft-year penalty ablation",
            "status": "not run in this report",
            "why": f"{defect_lookup['release_range_excludes_gt']['n']:,} turns have a release range that excludes the GT year.",
            "measurement": "release-range slice final@20/NDCG@20 and exact/HH guardrails.",
        },
        {
            "experiment": "Strict rejection assertion replay",
            "status": "not run in this report",
            "why": (
                f"Strict ID leak lower bound is {cohort_lookup['rejection_leak_strict_top20']['n']:,}; "
                f"broad name audit adds {cohort_lookup['rejection_leak_name_only_without_strict_top20']['n']:,} cases."
            ),
            "measurement": "zero strict leaks after finalization; hand-label name-only sample for false positives.",
        },
        {
            "experiment": "IDF-tag / session-feature tests",
            "status": "already de-prioritized by feature-ablation measurements",
            "why": f"Positive tag overlap is {pct(positive_tag_overlap_rate)}, while entity role/recency has a larger confirmed failure surface.",
            "measurement": "Session/demographic raw features show 0 lift as candidate constants; IDF tags were worse than raw. Revisit only as candidate-varying affinity/tag-precision features.",
        },
    ]

    experiments = [
        {
            "priority": "P0",
            "title": "Add role-typed current-turn entity state",
            "why": (
                f"{next(d for d in defects if d['key']=='stale_artist_or_track_state')['n']} turns have stale positive artist/track state; "
                f"{next(d for d in defects if d['key']=='novelty_prior_anchor_conflict')['n']} have a novelty cue while prior artists remain anchored."
            ),
            "change": "Change extractor output or resolver annotation so named entities are seed, satisfied, contrast, history, or rejected. Feed only seed/current-positive entities into anchors and discography.",
            "validation": "State QA: stale positive artist/track rate should drop. Eval: improve new-artist mid-conversation union@20/100 without hurting exact named-track turns.",
        },
        {
            "priority": "P0",
            "title": "Fix inert routing: configure routing_boost and retrieval profiles",
            "why": (
                f"Mid-conversation new-artist turns are {pct(next(t for t in task_modes if t['key']=='midconv_new_artist')['share'])} of turns "
                f"with final@20 {pct(next(t for t in task_modes if t['key']=='midconv_new_artist')['final20'])}; routing tags fire {routing_total:,} times but config routing_boost is empty."
            ),
            "change": "For novelty/diversify turns, downweight prior-artist centroid/discography and upweight tag/metadata/popularity/CF candidate generation. For continuation turns, do the opposite.",
            "validation": "Track union@20 and union@100 by new-artist vs continuation. Success means candidate generation rises for new-artist turns before final ranker tuning.",
        },
        {
            "priority": "P0",
            "title": "Prototype album-affinity and artist-recency features",
            "why": (
                f"Primary-album continuation is {same_primary_album['n']:,} turns with union@20 {pct(same_primary_album['union20'])} "
                f"but final@20 {pct(same_primary_album['final20'])}; the candidate is often nearby but ranked wrong."
            ),
            "change": "Add same_album_recent, artist_recency, and candidate_artist_role features to a lightweight scorer over union@100/200.",
            "validation": "Continuation NDCG@20 and same-album final@20 improve; new-artist and exact named-track slices are guardrails.",
        },
        {
            "priority": "P0",
            "title": "Build novelty candidate-generation profiles",
            "why": (
                f"Mid-conversation new-artist union@20 is {pct(new_artist['union20'])}; "
                f"novelty-cue + new-artist union@20 is {pct(novelty_new['union20'])}."
            ),
            "change": "For novelty/diversify turns, add genre/era-conditioned popularity, user-CF/culture affinity, and tag-first dense/metadata retrieval while suppressing stale prior-artist pools.",
            "validation": "Raise union@20 and union@100 for mid-conversation new-artist and novelty-cue slices before evaluating final ranker lift.",
        },
        {
            "priority": "P1",
            "title": "Add a release-year guardrail",
            "why": (
                f"{next(d for d in defects if d['key']=='release_range_excludes_gt')['n']} turns have release-year state that excludes the GT catalog year."
            ),
            "change": "Represent era as stylistic cue vs release-date constraint; keep release-year evidence soft unless the user explicitly asks for a date bound.",
            "validation": "Audit all release-range-excludes-GT turns and run no-year-penalty / soft-year-penalty ablations on final@20 and union@20.",
        },
        {
            "priority": "P1",
            "title": "Make rejections impossible to leak",
            "why": (
                f"{next(d for d in defects if d['key']=='rejection_leak_top20')['n']} turns show final top-20 leakage under this name/id heuristic."
            ),
            "change": "Add post-final assertions for rejected tracks/artists and test multi-artist track handling.",
            "validation": "Leak count should be zero on devset trace replays; then verify hit@20 does not regress materially.",
        },
        {
            "priority": "P1",
            "title": "Train or calibrate ranker features that consume state",
            "why": f"Overall union@20 is {pct(headline['union20'])} but final@20 is {pct(headline['final20'])}; state can tell the ranker when diversity, album affinity, popularity, or exactness should matter.",
            "change": "Candidate features: branch ranks, candidate_artist_role, is_new_artist, same_album_recent, release_distance, positive_tag_overlap, rejected_flag, popularity, and routing tags.",
            "validation": "Session-grouped CV over union@100/200 should improve NDCG@20/Hit@20 and report separate new-artist, continuation, LL, and late-turn slices.",
        },
    ]

    hypotheses = [
        {
            "hypothesis": "State is worth focusing on before adding more blind retrievers.",
            "verdict": "validated",
            "evidence": f"Mid-conversation new-artist final@20 is {pct(next(t for t in task_modes if t['key']=='midconv_new_artist')['final20'])}; stale/roleless state defects appear in {pct(next(d for d in defects if d['key']=='stale_artist_or_track_state')['share'])} of turns.",
            "implication": "Fix state roles and state-to-retriever routing first; measure union@20/100 by cohort.",
        },
        {
            "hypothesis": "Continuation and new-artist turns need different state use.",
            "verdict": "validated",
            "evidence": f"Continuation final@20 is {pct(next(t for t in task_modes if t['key']=='continuation_same_artist')['final20'])}; new-artist final@20 is {pct(next(t for t in task_modes if t['key']=='midconv_new_artist')['final20'])}.",
            "implication": "One RRF recipe is too blunt; state should select retrieval profile and ranker features.",
        },
        {
            "hypothesis": "Year state can be harmful.",
            "verdict": "validated with caveat",
            "evidence": f"{next(d for d in defects if d['key']=='release_range_excludes_gt')['n']} turns have a range that excludes GT. Some are benchmark/organizer ambiguity, not necessarily extractor errors.",
            "implication": "Build guardrails and ablations; do not simply delete era extraction.",
        },
        {
            "hypothesis": "Union@1000 should be the ranker target.",
            "verdict": "not accepted",
            "evidence": f"Union@1000 is {pct(headline['union1000'])}, but it is thousands of candidates per turn. Union@20 and union@100 are better work boundaries.",
            "implication": "Use union@20 as the state/retriever gap line and union@100 as the practical near-miss line.",
        },
    ]

    examples = {
        "stale_artist_or_track_state": choose_examples(rows, "stale_artist_or_track_state"),
        "novelty_prior_anchor_conflict": choose_examples(rows, "novelty_prior_anchor_conflict"),
        "release_range_excludes_gt": choose_examples(rows, "release_range_excludes_gt"),
        "rejection_leak_top20": choose_examples(rows, "rejection_leak_top20"),
        "exact_track_named_miss": choose_examples(rows, "exact_track_named_miss"),
    }

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "tid": tid,
        "snapshot_contract": {
            "status": "Baseline state-audit snapshot, not a permanent schema spec.",
            "applies_to": f"{tid} devset trace, predictions, organizer metadata, and Hugging Face conversation rows at generation time.",
            "valid_until": (
                "Rerun after changing the extractor prompt/schema, resolver, routing profile, ranker features, "
                "finalization rules, catalog/index, or evaluation split."
            ),
            "how_to_use": (
                "Use ideal states and replay packs as small-batch experiments. Once a fix lands, regenerate this "
                "report and compare stale-state, novelty-anchor, temporal, rejection, union@20, and final@20 slices."
            ),
        },
        "headline": headline,
        "task_modes": task_modes,
        "cohorts": cohorts,
        "defects": defects,
        "experiments": experiments,
        "hypotheses": hypotheses,
        "examples": examples,
        "supplemental_audit": supplemental,
        "organizer_metadata": organizer_metadata,
        "blindset_metadata_availability": blindset_metadata_availability,
        "metadata_decision_plan": metadata_decision_plan,
        "state_scorecard": state_scorecard,
        "state_field_audit": state_field_audit,
        "schema_change_plan": schema_change_plan,
        "ideal_state_targets": ideal_state_targets,
        "state_confusion_plan": state_confusion_plan,
        "good_state_low_recall": good_state_low_recall,
        "state_experiment_packs": state_experiment_packs,
        "state_experiment_turns": state_experiment_turns,
        "role_taxonomy": role_taxonomy,
        "role_bug_examples": (supplemental.get("extraction") or {}).get("bad_examples", []),
        "continuation_deep_dive": continuation_deep_dive,
        "newartist_deep_dive": newartist_deep_dive,
        "feature_catalog": feature_catalog,
        "measured_levers": measured_levers,
        "not_first": not_first,
        "counting_reconciliation": counting_reconciliation,
        "routing_reconciliation": routing_reconciliation,
        "experiment_backlog": experiment_backlog,
        "routing_counts": dict(routing_counts.most_common()),
        "reranker_bakeoff": reranker_bakeoff,
        "sources": {
            "trace": str(trace_path),
            "predictions": str(pred_path),
            "ground_truth": str(gt_path),
            "config": str(config_path),
            "track_metadata": HF_TRACK_METADATA_DATASET,
            "conversation_dataset": HF_CONVERSATION_DATASET,
            "docs_data": "docs/data.md",
            "session_state_docs": "docs/architectures/session_state.md",
            "user_profile_code": "mcrs/db_user/user_profile.py",
            "reranker_bakeoff": reranker_bakeoff.get("path") if reranker_bakeoff.get("available") else None,
        },
        "method": {
            "denominator": f"{total} evaluated devset turns",
            "union20": "GT appears in any retriever branch top-20 in the trace.",
            "union100": "GT appears in any retriever branch top-100 in the trace.",
            "final20": "GT appears in the generated final top-20 prediction list.",
            "stale_state_heuristic": "Positive artist/track state value is not lexically present in the current user turn. This is strong evidence for over-carry on named entities, but not a complete semantic proof.",
            "rejection_leak_heuristic": "Final top-20 candidate matches rejected track/artist IDs or names from resolver/state.",
        },
    }


def draw_bar_chart(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    title: str,
    label_key: str,
    value_keys: list[tuple[str, str, tuple[int, int, int]]],
    width: int = 1180,
    row_height: int = 44,
) -> None:
    height = max(260, 92 + len(rows) * row_height + 40)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("Arial.ttf", 17)
        small = ImageFont.truetype("Arial.ttf", 13)
        title_font = ImageFont.truetype("Arial Bold.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
        title_font = ImageFont.load_default()
    draw.text((28, 22), title, fill=(23, 32, 51), font=title_font)
    x0, x1 = 330, width - 180
    y = 82
    for row in rows:
        label = str(row[label_key])[:38]
        draw.text((28, y + 8), label, fill=(23, 32, 51), font=font)
        for idx, (key, short, color) in enumerate(value_keys):
            value = row.get(key)
            if value is None:
                continue
            yy = y + idx * 12
            bar_w = int((x1 - x0) * max(0.0, min(1.0, float(value))))
            draw.rectangle((x0, yy + 8, x1, yy + 17), fill=(236, 240, 246))
            draw.rectangle((x0, yy + 8, x0 + bar_w, yy + 17), fill=color)
            draw.text((x1 + 12, yy + 2), f"{short} {pct(float(value), 1)}", fill=color, font=small)
        y += row_height
    image.save(path)


def html_escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def render_metric_card(label: str, value: str, detail: str) -> str:
    return f"""
      <div class="metric-card">
        <span>{html_escape(label)}</span>
        <strong>{html_escape(value)}</strong>
        <small>{html_escape(detail)}</small>
      </div>
    """


def render_table(rows: list[dict[str, Any]], columns: list[tuple[str, str, str]]) -> str:
    head = "".join(f"<th>{html_escape(label)}</th>" for _, label, _ in columns)
    body = []
    for row in rows:
        cells = []
        for key, _, kind in columns:
            value = row.get(key)
            if kind == "pct":
                text = pct(value)
            elif kind == "share":
                text = pct(value)
            elif kind == "int":
                text = f"{int(value):,}" if value is not None else "-"
            else:
                text = str(value if value is not None else "-")
            cells.append(f"<td>{html_escape(text)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def render_examples(examples: dict[str, list[dict[str, Any]]]) -> str:
    cards: list[str] = []
    for group, rows in examples.items():
        if not rows:
            continue
        cards.append(f"<h3>{html_escape(group.replace('_', ' ').title())}</h3>")
        for ex in rows:
            messages = "".join(
                f"<p><b>t{msg['turn']} {html_escape(msg['role'])}:</b> {html_escape(msg['content'])}</p>"
                for msg in ex.get("recent_messages", [])
            )
            got_rows = "".join(
                f"<li><span>#{html_escape(item.get('rank'))}</span> "
                f"{html_escape(item.get('track'))} by {html_escape(item.get('artist'))}</li>"
                for item in ex.get("final_top_results", [])
            )
            got_html = f"<ol class=\"result-list\">{got_rows}</ol>" if got_rows else "<p class=\"note\">No final top results available in the captured predictions.</p>"
            diagnostics = "".join(f"<span class=\"tag\">{html_escape(x)}</span>" for x in ex.get("diagnostics", []))
            explanation_html = f"""
                    <div class="example-explain">
                      <div><span>Why wrong</span><p>{html_escape(ex.get('why_wrong') or '')}</p></div>
                      <div><span>What should change</span><p>{html_escape(ex.get('what_should_change') or '')}</p></div>
                      <div><span>Regression test</span><p>{html_escape(ex.get('regression_test') or '')}</p></div>
                    </div>
            """
            state = ex.get("state") or {}
            state_bits = [
                ("intent", state.get("turn_intent")),
                ("mode", state.get("intent_mode")),
                ("policy", state.get("policy")),
                ("routing", ", ".join(state.get("routing") or [])),
                ("stale", ", ".join(state.get("stale_entities") or [])),
                ("anchors", ", ".join(state.get("anchors") or [])),
                ("year", state.get("year_range")),
            ]
            state_html = "".join(
                f"<div><span>{html_escape(k)}</span><strong>{html_escape(v or '-')}</strong></div>" for k, v in state_bits
            )
            extracted_json = json.dumps(ex.get("state") or {}, indent=2, ensure_ascii=False)
            ideal_json = json.dumps(ex.get("ideal_state") or {}, indent=2, ensure_ascii=False)
            cards.append(
                f"""
                <article class="example-card">
                  <div class="example-head">
                    <div>
                      <h4>{html_escape(ex['gt_track'])} by {html_escape(ex['gt_artist'])}</h4>
                      <p class="mono">{html_escape(ex['session_id'])} / turn {html_escape(ex['turn'])}</p>
                    </div>
                    <div class="rank-strip">
                      <span>final {html_escape(rank_value(ex.get('final_rank')))}</span>
                      <span>branch {html_escape(rank_value(ex.get('best_branch_rank')))}</span>
                      <span>{html_escape(ex.get('best_branch') or 'NONE')}</span>
                    </div>
                  </div>
                  <p><b>User turn:</b> {html_escape(ex.get('current_user') or '')}</p>
                  <p>{diagnostics}</p>
                  {explanation_html}
                  <details open>
                    <summary>Case study: truncated conversation, returned tracks, extracted state, and ideal state</summary>
                    <div class="case-grid">
                      <div>
                        <h5>Truncated conversation window</h5>
                        <div class="messages">{messages}</div>
                      </div>
                      <div>
                        <h5>What we got: final top-5</h5>
                        {got_html}
                      </div>
                    </div>
                    <h5>What we extracted</h5>
                    <div class="state-grid">{state_html}</div>
                    <pre class="json-box">{html_escape(extracted_json)}</pre>
                    <h5>Ideal state for this failure</h5>
                    <pre class="json-box ideal">{html_escape(ideal_json)}</pre>
                  </details>
                </article>
                """
            )
    return "\n".join(cards)


def render_html(data: dict[str, Any], out_dir: Path) -> str:
    h = data["headline"]
    stale = next(d for d in data["defects"] if d["key"] == "stale_artist_or_track_state")
    novelty = next(d for d in data["defects"] if d["key"] == "novelty_prior_anchor_conflict")
    year = next(d for d in data["defects"] if d["key"] == "release_range_excludes_gt")
    leak = next(d for d in data["defects"] if d["key"] == "rejection_leak_top20")
    cont_detail = data["continuation_deep_dive"]
    new_detail = data["newartist_deep_dive"]
    album_signal = cont_detail.get("album_signal") or {}
    org = data["organizer_metadata"]
    routing_counts = data.get("routing_counts") or {}
    routing_total = sum(int(v or 0) for v in routing_counts.values())
    experiment_pack_rows = [
        {
            "pack": pack.get("pack"),
            "class_type": pack.get("class_type"),
            "n": pack.get("n"),
            "target_n": pack.get("target_n"),
            "hypothesis": pack.get("hypothesis"),
            "ideal_state_targets": pack.get("ideal_state_targets"),
            "state_terms_to_check": pack.get("state_terms_to_check"),
            "success_metric": pack.get("success_metric"),
        }
        for pack in data.get("state_experiment_packs", [])
    ]
    experiment_turn_rows = [
        {
            "sample_id": sample.get("sample_id"),
            "pack": sample.get("pack"),
            "class_type": sample.get("class_type"),
            "gt": f"{sample.get('gt_track')} by {sample.get('gt_artist')}",
            "baseline": (
                f"final={rank_value((sample.get('baseline') or {}).get('final_rank'))}; "
                f"fused={rank_value((sample.get('baseline') or {}).get('fused_rank'))}; "
                f"branch={rank_value((sample.get('baseline') or {}).get('best_branch_rank'))} "
                f"{(sample.get('baseline') or {}).get('best_branch') or ''}"
            ),
            "diagnosis": "; ".join(sample.get("diagnostics") or []) or sample.get("reason_to_test"),
            "expected_change": sample.get("expected_change"),
        }
        for sample in data.get("state_experiment_turns", [])
    ]
    replay_case_groups: dict[str, list[dict[str, Any]]] = {}
    seen_case_packs: set[str] = set()
    for sample in data.get("state_experiment_turns", []):
        pack = str(sample.get("pack") or "")
        if sample.get("class_type") != "failure" or pack in seen_case_packs:
            continue
        seen_case_packs.add(pack)
        baseline = sample.get("baseline") or {}
        replay_case_groups[pack] = [
            {
                "session_id": sample.get("session_id"),
                "turn": sample.get("turn"),
                "gt_track": sample.get("gt_track"),
                "gt_artist": sample.get("gt_artist"),
                "current_user": sample.get("current_user"),
                "final_rank": baseline.get("final_rank"),
                "best_branch_rank": baseline.get("best_branch_rank"),
                "best_branch": baseline.get("best_branch"),
                "diagnostics": sample.get("diagnostics") or [],
                "why_wrong": sample.get("why_wrong"),
                "what_should_change": sample.get("what_should_change"),
                "regression_test": sample.get("regression_test"),
                "state": sample.get("state_snapshot") or {},
                "ideal_state": sample.get("ideal_state") or {},
                "final_top_results": sample.get("final_top_results") or [],
                "recent_messages": sample.get("recent_messages") or [],
            }
        ]
    mode_chart = "state_task_modes.png"
    defect_chart = "state_defects.png"
    cohort_chart = "state_cohorts.png"
    state_payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Music CRS State Focus Report</title>
<style>
:root {{
  --ink:#172033; --muted:#5d6878; --line:#d9dee7; --panel:#fff; --bg:#f7f8fb;
  --blue:#2563eb; --teal:#0f766e; --orange:#c2410c; --rose:#be3455; --green:#2f7d32;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:var(--bg); line-height:1.55; }}
header {{ background:#fff; border-bottom:1px solid var(--line); }}
.wrap {{ max-width:1180px; margin:0 auto; padding:28px 22px; }}
h1 {{ margin:0; font-size:clamp(30px,4vw,46px); line-height:1.08; letter-spacing:0; }}
h2 {{ margin:0 0 12px; font-size:24px; letter-spacing:0; }}
h3 {{ margin:0 0 10px; font-size:18px; letter-spacing:0; }}
h4 {{ margin:0 0 4px; font-size:16px; }}
p {{ margin:0 0 12px; }}
a {{ color:var(--blue); }}
nav {{ position:sticky; top:0; z-index:5; background:rgba(255,255,255,.96); border-bottom:1px solid var(--line); }}
nav .wrap {{ max-width:100%; padding-top:10px; padding-bottom:10px; display:flex; gap:8px; overflow-x:auto; }}
nav a {{ color:var(--muted); text-decoration:none; border:1px solid var(--line); border-radius:8px; padding:7px 10px; white-space:nowrap; }}
section {{ border-bottom:1px solid var(--line); scroll-margin-top:64px; }}
.subtitle {{ color:var(--muted); max-width:900px; margin-top:12px; }}
.meta {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }}
.pill,.tag {{ display:inline-flex; align-items:center; min-height:26px; padding:4px 8px; border:1px solid var(--line); border-radius:7px; background:#fff; color:var(--muted); font-size:12px; margin:0 5px 5px 0; }}
.metric-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }}
.metric-card,.panel,.example-card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; min-width:0; }}
.metric-card span {{ display:block; color:var(--muted); font-size:12px; }}
.metric-card strong {{ display:block; font-size:28px; margin:3px 0; }}
.metric-card small {{ color:var(--muted); }}
.summary-grid {{ display:grid; grid-template-columns:1.1fr .9fr; gap:16px; align-items:start; }}
.work-list {{ display:grid; gap:10px; }}
.work-item {{ border-left:4px solid var(--blue); padding:10px 12px; background:#fff; border-radius:0 8px 8px 0; border-top:1px solid var(--line); border-right:1px solid var(--line); border-bottom:1px solid var(--line); }}
.work-item[data-priority="P1"] {{ border-left-color:var(--teal); }}
.work-item b {{ color:var(--blue); }}
table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
th,td {{ padding:9px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; font-size:13px; }}
th {{ background:#eef2f7; color:#303849; }}
tr:last-child td {{ border-bottom:0; }}
.table-scroll {{ display:block; width:100%; max-width:100%; overflow-x:auto; border-radius:8px; }}
.table-scroll table {{ min-width:760px; }}
.table-scroll th,.table-scroll td {{ overflow-wrap:anywhere; }}
.chart {{ width:100%; border:1px solid var(--line); border-radius:8px; background:#fff; padding:8px; }}
.chart img {{ display:block; width:100%; height:auto; }}
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start; }}
.two-col > *,.summary-grid > *,.metric-grid > * {{ min-width:0; }}
.example-card {{ margin:12px 0; }}
.example-head {{ display:flex; justify-content:space-between; gap:12px; align-items:start; }}
.rank-strip {{ display:flex; flex-wrap:wrap; gap:6px; justify-content:flex-end; }}
.rank-strip span {{ border:1px solid var(--line); border-radius:6px; padding:4px 7px; font-size:12px; color:var(--muted); }}
.mono {{ font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:12px; color:var(--muted); }}
.example-explain {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:10px 0; }}
.example-explain div {{ border:1px solid var(--line); border-radius:7px; padding:9px; background:#f8fafc; min-width:0; }}
.example-explain span {{ display:block; color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; }}
.example-explain p {{ margin:4px 0 0; font-size:13px; overflow-wrap:anywhere; }}
details {{ margin-top:8px; }}
summary {{ cursor:pointer; color:var(--blue); }}
h5 {{ margin:12px 0 6px; font-size:13px; color:#303849; text-transform:uppercase; letter-spacing:0; }}
.case-grid {{ display:grid; grid-template-columns:1.2fr .8fr; gap:12px; align-items:start; }}
.messages {{ background:#f8fafc; border:1px solid var(--line); border-radius:8px; padding:10px; margin:10px 0; }}
.messages p {{ margin-bottom:6px; }}
.result-list {{ margin:10px 0 0; padding-left:0; list-style:none; display:grid; gap:7px; }}
.result-list li {{ border:1px solid var(--line); border-radius:7px; padding:8px; background:#fff; font-size:13px; }}
.result-list span {{ display:inline-flex; min-width:32px; color:var(--muted); font-weight:700; }}
.state-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }}
.state-grid div {{ border:1px solid var(--line); border-radius:7px; padding:8px; min-width:0; }}
.state-grid span {{ display:block; color:var(--muted); font-size:12px; }}
.state-grid strong {{ overflow-wrap:anywhere; font-size:13px; }}
.json-box {{ white-space:pre-wrap; overflow-wrap:anywhere; border:1px solid var(--line); border-radius:8px; background:#101827; color:#e5edf8; padding:12px; font-size:12px; line-height:1.45; max-height:360px; overflow:auto; }}
.json-box.ideal {{ background:#0f2f2b; color:#ecfdf5; }}
.note {{ color:var(--muted); }}
.callout {{ background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; padding:12px; }}
@media (max-width: 820px) {{
  .metric-grid,.summary-grid,.two-col,.state-grid,.example-explain,.case-grid {{ grid-template-columns:1fr; }}
  .example-head {{ display:block; }}
  .rank-strip {{ justify-content:flex-start; margin-top:8px; }}
}}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>State Focus Report</h1>
    <p class="subtitle">A validated work queue for <code>{html_escape(data['tid'])}</code>. This report keeps union@20 as the first gap boundary and uses union@100 as the practical near-miss lens. It asks what to fix in conversation state and state use before chasing a bigger candidate pool.</p>
    <div class="meta">
      <span class="pill">Generated {html_escape(data['generated_at'])}</span>
      <span class="pill">{int(h['n']):,} devset turns</span>
      <span class="pill">Final@20 {pct(h['final20'])}</span>
      <span class="pill">Union@20 {pct(h['union20'])}</span>
      <span class="pill">Union@100 {pct(h['union100'])}</span>
    </div>
    <div class="callout" style="margin-top:16px"><strong>Snapshot contract:</strong> This is a baseline state audit for <code>{html_escape(data['tid'])}</code> generated at <code>{html_escape(data['generated_at'])}</code>. The ideal states and decisions are experiment targets for this exact trace/config; after implementing extractor, routing, ranker, catalog, or split changes, regenerate this report and compare before treating old counts as current.</div>
  </div>
</header>
<nav><div class="wrap">
  <a href="../index.html">Recall Explorer</a>
  <a href="#summary">Summary</a>
  <a href="#schema-audit">Schema Audit</a>
  <a href="#roles">Role Taxonomy</a>
  <a href="#metadata">Metadata</a>
  <a href="#ranker">Ranker Features</a>
  <a href="#experiments">Experiments</a>
  <a href="#examples">Examples</a>
  <a href="#methods">Methods</a>
</div></nav>

<section id="summary"><div class="wrap">
  <h2>Technical Summary</h2>
  <div class="summary-grid">
    <div class="panel">
      <p><strong>The state work to prioritize is role and recency, not just more fields.</strong> {stale['n']:,} turns have positive artist/track entities that are not in the current user turn, and {novelty['n']:,} turns combine a novelty cue with prior artists still anchored. That points to stale carryover and missing entity roles: seed vs satisfied vs contrast vs history.</p>
      <p><strong>Routing is currently inert.</strong> Routing tags fire {routing_total:,} times, including exact_entity_probe {routing_counts.get('exact_entity_probe', 0):,} times and hidden_target_search {routing_counts.get('hidden_target_search', 0):,} times, but <code>routing_boost</code> is empty in the config. This is a P0 configuration gap because the system distinguishes turn types and then does not spend those distinctions on retriever weights.</p>
      <p><strong>New-artist turns are the sharpest state/retrieval gap.</strong> The report recomputes task-mode cohorts from GT artist history. Mid-conversation new-artist turns have much lower final@20 than continuation turns, so the state needs to route novelty/diversify turns toward tag/metadata/popularity/CF candidate generation and away from old-artist anchors.</p>
      <p><strong>Some state bugs are bounded and directly testable.</strong> {year['n']:,} turns have release-year state that excludes the judged target year, and {leak['n']:,} turns show rejected entities leaking into top-20 under this audit heuristic. These should become small guardrail tests.</p>
      <div class="callout"><strong>Decision:</strong> Work on state roles, state-to-retriever routing, and state guardrails first. A trained ranker is still useful, but it should consume better state features rather than hide state errors.</div>
    </div>
    <div class="metric-grid">
      {render_metric_card('Final@20', pct(h['final20']), 'Submitted top-20 hit rate')}
      {render_metric_card('Union@20', pct(h['union20']), 'First candidate/state gap boundary')}
      {render_metric_card('Union@100', pct(h['union100']), 'Practical near-miss ceiling')}
      {render_metric_card('Not in union@20', pct(1 - h['union20']), 'State/retriever gap')}
    </div>
  </div>
</div></section>

<section id="scorecard"><div class="wrap">
  <h2>State Scorecard: What Is Broken vs Usable</h2>
  <p class="note">The point is to avoid an everything-is-bad diagnosis. Tags are usable; entity role/recency and state consumption are the highest-value gaps; year/rejection are bounded guardrails.</p>
  {render_table(data['state_scorecard'], [
      ('area','Area','text'), ('current_evidence','Current trace evidence','text'),
      ('audit_signal','Additional audit signal','text'), ('decision','Decision','text')
  ])}
</div></section>

<section id="schema-audit"><div class="wrap">
  <h2>State Schema Audit: Keep, Split, Collapse, Add</h2>
  <p class="note">This section is aimed at the next extraction rerun. It separates true extractor/schema problems from downstream consumption problems, so a rerun has a concrete QA contract.</p>
  <div class="callout"><strong>Looking for concrete cases?</strong> Jump to <a href="#examples">Failure Examples</a> for cards with truncated conversation, final returned tracks, extracted state, why it is wrong, and an ideal state target.</div>
  <h3>Field-By-Field Diagnosis</h3>
  {render_table(data['state_field_audit'], [
      ('field','State field','text'), ('evidence','Current evidence','text'), ('failure_read','Failure read','text'),
      ('schema_decision','Decision','text'), ('validation','Rerun validation','text')
  ])}
  <h3>Schema Change Queue</h3>
  {render_table(data['schema_change_plan'], [
      ('priority','Priority','text'), ('failure_class','Failure class','text'), ('schema_move','Move','text'),
      ('change','Change','text'), ('why_it_makes_sense','Why it makes sense','text'), ('validation','Validation','text')
  ])}
  <h3>Ideal State Targets To Try Extracting</h3>
  <p class="note">Use this as the small-batch extractor contract. The ideal shape is intentionally richer than the minimum viable state, so cheap experiments can reveal which fields are extractable and which should become deterministic derived features instead.</p>
  {render_table(data['ideal_state_targets'], [
      ('target_id','State target','text'), ('priority','Priority','text'), ('failure_classes','Failure classes','text'),
      ('ideal_state_shape','Ideal state shape','text'), ('minimum_viable_state','Minimum viable state','text'),
      ('extraction_probe','Small-batch extraction probe','text'), ('if_too_hard','If extraction is too hard','text'),
      ('downstream_use','Downstream use','text'), ('sample_packs','Replay packs','text')
  ])}
  <h3>State Confusion / Field Economy Plan</h3>
  <p class="note">More state is not always better. This table marks fields that can confuse the extractor or downstream retrieval if they overlap, and gives the simplification rule to test before adding new schema surface.</p>
  {render_table(data['state_confusion_plan'], [
      ('confusing_surface','Confusing surface','text'), ('risk','Risk','text'), ('decision','Decision','text'),
      ('field_economy_move','Field-economy move','text'), ('small_test','Small test','text')
  ])}
  <h3>Good State, Low Recall Slices</h3>
  <p class="note">These slices are important because they show where extraction may be adequate but retrieval/ranking still fails. They should not all trigger extractor rewrites.</p>
  {render_table(data['good_state_low_recall'], [
      ('slice','Slice','text'), ('n','Turns','int'), ('final20','Final@20','pct'),
      ('union20','Union@20','pct'), ('union100','Union@100','pct'), ('not_union20','Not union@20','int'),
      ('rank_loss20','Union@20 not final','int'), ('read','Read','text'), ('work','What to work on','text')
  ])}
  <h3>Small Subset Experiment Packs</h3>
  <p class="note">State extraction is expensive, so these are deliberately small smoke packs for before/after recall tests. The full per-turn payload is also embedded in <code>state_report_data.json</code> under <code>state_experiment_turns</code>.</p>
  {render_table(experiment_pack_rows, [
      ('pack','Pack','text'), ('class_type','Class type','text'), ('n','Sample turns','int'), ('target_n','Target','int'),
      ('hypothesis','Hypothesis','text'), ('ideal_state_targets','State targets','text'),
      ('state_terms_to_check','State terms to check','text'), ('success_metric','Success metric','text')
  ])}
  <h3>Sample Turns For Future Replays</h3>
  {render_table(experiment_turn_rows, [
      ('sample_id','Sample id','text'), ('pack','Pack','text'), ('class_type','Class type','text'), ('gt','GT','text'), ('baseline','Baseline ranks','text'),
      ('diagnosis','Diagnosis','text'), ('expected_change','Expected change','text')
  ])}
</div></section>

<section id="roles"><div class="wrap">
  <h2>Entity Roles The State Needs</h2>
  <p class="note">Binary positive/negative entity state is too blunt for music conversations. The same artist mention can mean seed, satisfied item, contrast, old history, or hard rejection.</p>
  {render_table(data['role_taxonomy'], [
      ('role','Role','text'), ('cue','User cue','text'), ('current_behavior','Current behavior','text'),
      ('desired_behavior','Desired behavior','text'), ('current_evidence','Current evidence','text')
  ])}
  <h3>Role Bug Examples To Turn Into Tests</h3>
  <p class="note">These examples are compact utterance-level cases for extractor prompt/schema QA. They should become regression tests once the role taxonomy is implemented.</p>
  {render_table(data['role_bug_examples'], [
      ('id','Case','text'), ('intent','Intent','text'), ('ask','User ask','text'), ('anchored','Anchored today','text'),
      ('reason','Why wrong','text'), ('ideal','Ideal state','text')
  ]) if data['role_bug_examples'] else '<p class="note">No role examples were available in the generated audit inputs.</p>'}
</div></section>

<section id="continuation"><div class="wrap">
  <h2>Continuation Is Mostly A Track-Selection Problem</h2>
  <p>{html_escape(cont_detail['summary'])}</p>
  <div class="callout"><strong>Implication:</strong> {html_escape(cont_detail['work'])}</div>
  <div class="two-col" style="margin-top:14px">
    <div class="panel">
      <h3>Continuation Miss Buckets</h3>
      {render_table(cont_detail['buckets'], [
          ('label','Bucket','text'), ('n','Misses','int'), ('share','Share','pct'),
          ('cause','Cause','text'), ('fix','Fix','text')
      ]) if cont_detail['buckets'] else '<p class="note">Bucket detail unavailable; use current continuation metrics above.</p>'}
    </div>
    <div class="panel">
      <h3>Album-Affinity Signal</h3>
      <p><strong>Canonical primary-album cohort:</strong> n={int(album_signal.get('current_primary_album_n') or 0):,}, final@20 {pct(album_signal.get('current_primary_album_final20'))}, union@20 {pct(album_signal.get('current_primary_album_union20'))}, union@100 {pct(album_signal.get('current_primary_album_union100'))}.</p>
      <p><strong>Any-album sensitivity:</strong> n={int(album_signal.get('current_same_album_n') or 0):,}, final@20 {pct(album_signal.get('current_same_album_final20'))}, union@20 {pct(album_signal.get('current_same_album_union20'))}. This broader count includes tracks with multiple catalog album IDs.</p>
      <p><strong>Primary-album fused-rank proxy:</strong> among {int(album_signal.get('primary_album_miss_total') or 0):,} primary-album final misses, {int(album_signal.get('primary_album_fused_top20_demoted') or 0):,} were already fused top-20 but missed final top-20, {int(album_signal.get('primary_album_fused_21_100') or 0):,} sit at fused rank 21-100, {int(album_signal.get('primary_album_fused_101_1000') or 0):,} at 101-1000, and {int(album_signal.get('primary_album_fused_absent') or 0):,} are absent from fused output. Bucket sum: {int(album_signal.get('primary_album_fused_bucket_sum') or 0):,}.</p>
      <p><strong>Any-album fused-rank sensitivity:</strong> misses={int(album_signal.get('same_album_miss_total') or 0):,}, fused<=20/final-missed={int(album_signal.get('same_album_fused_top20_demoted') or 0):,}, fused 21-100={int(album_signal.get('same_album_fused_21_100') or 0):,}, fused 101-1000={int(album_signal.get('same_album_fused_101_1000') or 0):,}, absent={int(album_signal.get('same_album_fused_absent') or 0):,}, bucket sum={int(album_signal.get('same_album_fused_bucket_sum') or 0):,}.</p>
      <p><strong>Additional audit signal:</strong> {html_escape(album_signal.get('audit_upside') or 'No album counterfactual available.')}</p>
      <p><strong>Action:</strong> {html_escape(album_signal.get('action') or '')}</p>
    </div>
  </div>
</div></section>

<section id="newartist"><div class="wrap">
  <h2>New-Artist Turns Are The Main Candidate Gap</h2>
  <p>{html_escape(new_detail['summary'])}</p>
  <div class="callout"><strong>Implication:</strong> {html_escape(new_detail['work'])}</div>
  <div class="two-col" style="margin-top:14px">
    <div class="panel">
      <h3>Current New-Artist Slices</h3>
      {render_table(new_detail['current_slices'], [
          ('slice','Slice','text'), ('n','Turns','int'), ('final20','Final@20','pct'),
          ('union20','Union@20','pct'), ('union100','Union@100','pct')
      ])}
    </div>
    <div class="panel">
      <h3>Candidate-Generation Buckets</h3>
      {render_table(new_detail['buckets'], [
          ('label','Bucket','text'), ('n','Misses','int'), ('share','Share','pct'),
          ('cause','Cause','text'), ('fix','Fix','text')
      ]) if new_detail['buckets'] else '<p class="note">Bucket detail unavailable; use current new-artist metrics above.</p>'}
    </div>
  </div>
</div></section>

<section id="metadata"><div class="wrap">
  <h2>Organizer Metadata: Useful, But Mostly As Routing Context</h2>
  <p class="note">{html_escape(org['current_pipeline_summary'])}</p>
  <p class="note">{html_escape(org['category_caveat'])}</p>
  {render_table(org['fields'], [
      ('field','Field','text'), ('description','What it is','text'), ('recommendation','How to use it','text')
  ])}
  <h3>Blind-A Availability Check</h3>
  <p class="note">{html_escape((org.get('blindset_availability') or {}).get('summary') or 'Blind-A availability was not checked.')}</p>
  {render_table((org.get('blindset_availability') or {}).get('rows') or [], [
      ('item','Item','text'), ('blind_a_status','Blind-A status','text'), ('evidence','Evidence','text'),
      ('report_decision','Report decision','text')
  ])}
  <h3>Use vs Emulate / Extract Decision</h3>
  <p class="note">Because these are organizer-provided session fields, the default is to use them directly when available and avoid paying extractor calls to recreate them. Emulation only makes sense if the target inference split lacks the field and the feature has already shown lift.</p>
  {render_table(data['metadata_decision_plan'], [
      ('source','Metadata source','text'), ('available_as','Available as','text'), ('use_directly','Use directly?','text'),
      ('emulate_or_extract','Emulate / extract?','text'), ('ranking_shape','Ranking shape','text'), ('first_test','First test','text')
  ])}
  <h3>Specificity Codes</h3>
  {render_table(org['specificity_summary'], [
      ('specificity','Code','text'), ('sessions','Sessions','int'), ('share','Share','share'),
      ('meaning','Meaning','text'), ('example_goal','Example listener_goal','text')
  ])}
  <h3>Category Codes From Observed Listener Goals</h3>
  {render_table(org['category_summary'], [
      ('category','Category','text'), ('sessions','Sessions','int'), ('share','Share','share'),
      ('observed_pattern','Observed pattern','text'), ('example_goal','Example listener_goal','text')
  ])}
  <h3>User Profile Fields</h3>
  {render_table(org['user_profile_fields'], [
      ('field','Field','text'), ('current_use','Current use','text'), ('recommended_use','Recommended use','text')
  ])}
</div></section>

<section id="ranker"><div class="wrap">
  <h2>Ranker Feature Catalog</h2>
  <p class="note">Replacing RRF makes sense if the ranker sees candidate-varying state features. Raw category, specificity, and demographics are useful only after they become router decisions, slices, or candidate-level affinity features.</p>
  <h3>Measured Lever Evidence</h3>
  {render_table(data['measured_levers'], [
      ('lever','Lever','text'), ('status','Status','text'), ('result','Measured result','text'),
      ('decision','Decision','text'), ('source','Source','text')
  ])}
  <h3>Candidate Features To Build</h3>
  {render_table(data['feature_catalog'], [
      ('feature','Feature','text'), ('grain','Grain','text'), ('why','Why it matters','text'),
      ('source','Evidence source','text'), ('validation','Validation','text')
  ])}
  <h3>What Not To Work On First</h3>
  {render_table(data['not_first'], [
      ('idea','Idea','text'), ('decision','Decision','text'), ('evidence','Evidence','text')
  ])}
</div></section>

<section id="reconciliation"><div class="wrap">
  <h2>Counting Caveats And Reconciliation</h2>
  <p class="note">The headline metrics and mode counts are exact. Some diagnostic cohorts are definition-sensitive because artist/album metadata has multiple IDs and rejection matching can be strict ID-only or broader name-based auditing.</p>
  {render_table(data['counting_reconciliation'], [
      ('claim','Claim','text'), ('report_value','Report value','text'), ('alternate_value','Sensitivity / alternate','text'),
      ('basis','Basis','text'), ('decision','How to read it','text')
  ])}
  <h3>Full Trace Routing Counts</h3>
  {render_table(data['routing_reconciliation'], [
      ('tag','Routing tag','text'), ('active_turns','Active turns','int'), ('basis','Basis','text'), ('consumed','Consumption note','text')
  ])}
</div></section>

<section id="experiments"><div class="wrap">
  <h2>Experiment Backlog And Measurement Contract</h2>
  <p class="note">This report is a trace-derived diagnostic report, not a completed ablation suite. Treat the work queue as prioritized hypotheses until these experiments run.</p>
  {render_table(data['experiment_backlog'], [
      ('experiment','Experiment','text'), ('status','Status','text'), ('why','Why this test','text'), ('measurement','Success metric / guardrail','text')
  ])}
</div></section>

<section id="work"><div class="wrap">
  <h2>What To Work On First</h2>
  <div class="work-list">
    {''.join(f'''
    <div class="work-item" data-priority="{html_escape(item['priority'])}">
      <h3><b>{html_escape(item['priority'])}</b> {html_escape(item['title'])}</h3>
      <p><strong>Why:</strong> {html_escape(item['why'])}</p>
      <p><strong>Change:</strong> {html_escape(item['change'])}</p>
      <p><strong>Validation:</strong> {html_escape(item['validation'])}</p>
    </div>''' for item in data['experiments'])}
  </div>
</div></section>

<section id="evidence"><div class="wrap">
  <h2>Task Mode Evidence</h2>
  <p class="note">Mode is recomputed from ground-truth artist history and current user text, not copied from a prior report. Union@20 is the first state/retriever boundary; final@20 shows what survives ranking and finalization.</p>
  <div class="chart"><img src="{mode_chart}" alt="Task mode hit and union rates"></div>
  {render_table(data['task_modes'], [
      ('label','Cohort','text'), ('n','Turns','int'), ('share','Share','share'),
      ('final20','Final@20','pct'), ('union20','Union@20','pct'), ('union100','Union@100','pct'),
      ('candidate_gap20','Not union@20','int'), ('rank_loss20','Union@20 not final','int'),
      ('interpretation','Interpretation','text')
  ])}
</div></section>

<section id="defects"><div class="wrap">
  <h2>Validated State Defects</h2>
  <p class="note">These are not all equal. Stale/roleless entities are a broad state-design issue. Release-year and rejection leakage are smaller guardrail issues. Exact named-track misses are tiny but high severity.</p>
  <div class="chart"><img src="{defect_chart}" alt="State defect counts and final miss rates"></div>
  {render_table(data['defects'], [
      ('label','Defect','text'), ('n','Turns','int'), ('share','Share','share'),
      ('final20','Final@20','pct'), ('union20','Union@20','pct'), ('union100','Union@100','pct'),
      ('definition','Definition','text'), ('work','Work item','text')
  ])}
</div></section>

<section id="hypotheses"><div class="wrap">
  <h2>Hypotheses Tested</h2>
  {render_table(data['hypotheses'], [
      ('hypothesis','Hypothesis','text'), ('verdict','Verdict','text'), ('evidence','Evidence','text'), ('implication','Implication','text')
  ])}
</div></section>

<section id="cohorts"><div class="wrap">
  <h2>State Cohort Detail</h2>
  <p class="note">Use this table to choose slices for ablations. If a fix claims to repair state, it should move a specific row here, not only the aggregate metric.</p>
  <div class="chart"><img src="{cohort_chart}" alt="State cohort final and union rates"></div>
  {render_table(data['cohorts'], [
      ('label','Cohort','text'), ('n','Turns','int'), ('share','Share','share'),
      ('final20','Final@20','pct'), ('union20','Union@20','pct'), ('union100','Union@100','pct'),
      ('miss20','Final misses','int'), ('candidate_gap20','Not union@20','int'), ('rank_loss20','Union@20 not final','int')
  ])}
</div></section>

<section id="examples"><div class="wrap">
  <h2>Failure Examples</h2>
  <p class="note">Each card shows the truncated conversation window, what the system returned, the extracted state, why that is wrong, and the ideal state target. These are intended as implementation test cases, not just illustrative anecdotes.</p>
  <h3>Replay Pack Case Studies: One Per Failure Class</h3>
  <p class="note">Use this first when planning small API-call extractor experiments. The full pack still has 10 turns per class in <code>state_report_data.json</code> and <code>../state_experiment_pack.json</code>.</p>
  {render_examples(replay_case_groups)}
  <h3>Trace-Diagnosis Case Studies</h3>
  <p class="note">These are additional examples selected from the major trace-derived defect cohorts.</p>
  {render_examples(data['examples'])}
</div></section>

<section id="methods"><div class="wrap">
  <h2>Scope And Method</h2>
  <div class="two-col">
    <div class="panel">
      <h3>Definitions</h3>
      <p><strong>Snapshot contract:</strong> {html_escape(data['snapshot_contract']['status'])} {html_escape(data['snapshot_contract']['valid_until'])} {html_escape(data['snapshot_contract']['how_to_use'])}</p>
      <p><strong>Final@20:</strong> {html_escape(data['method']['final20'])}</p>
      <p><strong>Union@20:</strong> {html_escape(data['method']['union20'])}</p>
      <p><strong>Union@100:</strong> {html_escape(data['method']['union100'])}</p>
      <p><strong>State-staleness heuristic:</strong> {html_escape(data['method']['stale_state_heuristic'])}</p>
      <p><strong>Rejection-leak heuristic:</strong> {html_escape(data['method']['rejection_leak_heuristic'])}</p>
    </div>
    <div class="panel">
      <h3>Sources</h3>
      {''.join(f'<p><strong>{html_escape(k)}:</strong> <span class="mono">{html_escape(v)}</span></p>' for k, v in data['sources'].items())}
    </div>
  </div>
</div></section>

<script id="state-report-data" type="application/json">{state_payload}</script>
</body>
</html>
"""


def render_markdown(data: dict[str, Any]) -> str:
    def json_code_block(value: Any) -> list[str]:
        if value in (None, ""):
            return ["```json", "{}", "```"]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return ["```text", value, "```"]
        else:
            parsed = value
        return ["```json", json.dumps(parsed, indent=2, ensure_ascii=False), "```"]

    def add_record(title: Any, fields: list[tuple[str, Any]], *, level: int = 3) -> None:
        lines.extend([f"{'#' * level} {title}", ""])
        for label, value in fields:
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            chunks = split_readable_chunks(text)
            lines.append(f"- {label}: {chunks[0]}")
            for chunk in chunks[1:]:
                lines.append(f"- {label} detail: {chunk}")
        lines.append("")

    def split_readable_chunks(text: str, max_len: int = 230) -> list[str]:
        if len(text) <= max_len:
            return [text]
        if " | " in text:
            parts = [part.strip() for part in text.split(" | ") if part.strip()]
        else:
            parts = [part.strip() for part in re.split(r"(?<=\.)\s+", text) if part.strip()]
        if len(parts) == 1 and "; " in text:
            parts = [part.strip() for part in text.split("; ") if part.strip()]

        chunks: list[str] = []
        for part in parts:
            if len(part) <= max_len:
                chunks.append(part)
                continue
            words = part.split()
            current: list[str] = []
            for word in words:
                candidate = " ".join([*current, word])
                if current and len(candidate) > max_len:
                    chunks.append(" ".join(current))
                    current = [word]
                else:
                    current.append(word)
            if current:
                chunks.append(" ".join(current))
        return chunks or [text]

    def count_text(value: Any) -> str:
        if value is None or value == "":
            return "n/a"
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return str(value)

    h = data["headline"]
    routing_counts = data.get("routing_counts") or {}
    routing_total = sum(int(v or 0) for v in routing_counts.values())
    lines = [
        "# Music CRS State Focus Report",
        "",
        f"Generated: {data['generated_at']}",
        f"TID: `{data['tid']}`",
        "",
        "## Snapshot Contract",
        "",
        f"- Status: {data['snapshot_contract']['status']}",
        f"- Applies to: {data['snapshot_contract']['applies_to']}",
        f"- Valid until: {data['snapshot_contract']['valid_until']}",
        f"- How to use: {data['snapshot_contract']['how_to_use']}",
        "",
        "## Technical Summary",
        "",
        f"- Final@20 is {pct(h['final20'])}; union@20 is {pct(h['union20'])}; union@100 is {pct(h['union100'])}.",
        "- The highest-value state work is role-typed, current-turn entity state and state-to-retriever routing.",
        f"- Routing tags fire {routing_total:,} times, but `routing_boost` is empty, so routing is currently a P0 config/consumption gap.",
        "- Treat union@20 as the state/retriever gap boundary; use union@100 as the near-miss/ranker workbench.",
        "",
        "## Work Queue",
        "",
    ]
    for item in data["experiments"]:
        lines.extend(
            [
                f"### {item['priority']} {item['title']}",
                "",
                f"- Why: {item['why']}",
                f"- Change: {item['change']}",
                f"- Validation: {item['validation']}",
                "",
            ]
        )
    lines.extend(["## Task Modes", ""])
    for row in data["task_modes"]:
        add_record(
            row["label"],
            [
                ("Turns", count_text(row["n"])),
                ("Final@20", pct(row["final20"])),
                ("Union@20", pct(row["union20"])),
                ("Union@100", pct(row["union100"])),
                ("Read", row["interpretation"]),
            ],
        )
    lines.extend(["", "## State Scorecard", ""])
    for row in data["state_scorecard"]:
        add_record(
            row["area"],
            [
                ("Current evidence", row["current_evidence"]),
                ("Decision", row["decision"]),
            ],
        )
    lines.extend(["", "## State Schema Audit", ""])
    for row in data["state_field_audit"]:
        add_record(
            row["field"],
            [
                ("Evidence", row["evidence"]),
                ("Failure read", row["failure_read"]),
                ("Decision", row["schema_decision"]),
                ("Validation", row["validation"]),
            ],
        )
    lines.extend(["", "## Schema Change Queue", ""])
    for row in data["schema_change_plan"]:
        add_record(
            f"{row['priority']} / {row['failure_class']} / {row['schema_move']}",
            [
                ("Change", row["change"]),
                ("Why it makes sense", row["why_it_makes_sense"]),
                ("Validation", row["validation"]),
            ],
        )
    lines.extend(["", "## Ideal State Targets To Try Extracting", ""])
    lines.append(
        "Use this as the small-batch extractor contract: test the ideal shape, keep the minimum viable state if the full shape is unreliable, and fall back to deterministic derived features when extraction is too expensive or noisy."
    )
    lines.append("")
    for row in data.get("ideal_state_targets", []):
        lines.extend(
            [
                f"### {row['priority']} / {row['target_id']}",
                "",
                f"- Failure classes: {row['failure_classes']}",
                f"- Minimum viable state: {row['minimum_viable_state']}",
                f"- Extraction probe: {row['extraction_probe']}",
                f"- Fallback if too hard: {row['if_too_hard']}",
                f"- Downstream use: {row['downstream_use']}",
                f"- Replay packs: {row['sample_packs']}",
                "",
                "Ideal state shape:",
                "",
            ]
        )
        lines.extend(json_code_block(row.get("ideal_state_shape")))
        lines.append("")
    lines.extend(["", "## State Confusion / Field Economy Plan", ""])
    lines.append(
        "More state is not automatically better. These are the fields that can confuse the extractor or downstream code if they overlap, plus the simplification rule to test first."
    )
    lines.append("")
    for row in data.get("state_confusion_plan", []):
        lines.extend(
            [
                f"### {row['confusing_surface']}",
                "",
                f"- Risk: {row['risk']}",
                f"- Decision: {row['decision']}",
                f"- Field-economy move: {row['field_economy_move']}",
                f"- Small test: {row['small_test']}",
                "",
            ]
        )
    lines.extend(["", "## Good State, Low Recall Slices", ""])
    for row in data["good_state_low_recall"]:
        add_record(
            row["slice"],
            [
                ("Turns", count_text(row["n"])),
                ("Final@20", pct(row["final20"])),
                ("Union@20", pct(row["union20"])),
                ("Union@100", pct(row["union100"])),
                ("Not union@20", count_text(row["not_union20"])),
                ("Union@20 not final", count_text(row["rank_loss20"])),
                ("Read", row["read"]),
                ("Work", row["work"]),
            ],
        )
    lines.extend(["", "## Small Subset Experiment Packs", ""])
    lines.append(
        "Use these deterministic sample turns for future before/after recall tests when state extraction reruns are expensive."
    )
    lines.append("")
    for pack in data.get("state_experiment_packs", []):
        add_record(
            pack["pack"],
            [
                ("Class type", pack.get("class_type")),
                ("Turns", f"{pack['n']} sampled; target={pack.get('target_n')}"),
                ("Hypothesis", pack["hypothesis"]),
                ("State targets", pack.get("ideal_state_targets")),
                ("State terms to check", pack.get("state_terms_to_check")),
                ("Success metric", pack["success_metric"]),
            ],
        )
        for sample in pack.get("sample_turns", []):
            baseline = sample.get("baseline") or {}
            best_branch = baseline.get("best_branch") or "NONE"
            add_record(
                sample["sample_id"],
                [
                    ("Class type", sample.get("class_type")),
                    ("GT", f"{sample['gt_track']} by {sample['gt_artist']}"),
                    (
                        "Ranks",
                        f"final={rank_value(baseline.get('final_rank'))}; "
                        f"fused={rank_value(baseline.get('fused_rank'))}; "
                        f"best_branch={rank_value(baseline.get('best_branch_rank'))} ({best_branch})",
                    ),
                    ("Expected change", sample["expected_change"]),
                ],
                level=4,
            )
    lines.extend(["", "## Entity Role Taxonomy", ""])
    for row in data["role_taxonomy"]:
        add_record(
            row["role"],
            [
                ("Cue", row["cue"]),
                ("Desired behavior", row["desired_behavior"]),
                ("Evidence", row["current_evidence"]),
            ],
        )
    if data["role_bug_examples"]:
        lines.extend(["", "### Role Bug Examples", ""])
        for row in data["role_bug_examples"]:
            add_record(
                row.get("id"),
                [
                    ("Ask", row.get("ask")),
                    ("Anchored", row.get("anchored")),
                    ("Ideal", row.get("ideal")),
                ],
                level=4,
            )
    cont = data["continuation_deep_dive"]
    lines.extend(["", "## Continuation Deep Dive", "", cont["summary"], ""])
    for row in cont.get("buckets") or []:
        add_record(
            row["label"],
            [
                ("Turns", count_text(row.get("n"))),
                ("Share", pct(row.get("share"))),
                ("Cause", row.get("cause")),
                ("Fix", row.get("fix")),
            ],
        )
    album = cont.get("album_signal") or {}
    add_record(
        "Album-affinity current cohort",
        [
            ("Turns", count_text(album.get("current_same_album_n"))),
            ("Final@20", pct(album.get("current_same_album_final20"))),
            ("Union@20", pct(album.get("current_same_album_union20"))),
            (
                "Primary miss fused buckets",
                "fused<=20/final-missed="
                f"{count_text(album.get('primary_album_fused_top20_demoted'))}; "
                f"21-100={count_text(album.get('primary_album_fused_21_100'))}; "
                f"101-1000={count_text(album.get('primary_album_fused_101_1000'))}; "
                f"absent={count_text(album.get('primary_album_fused_absent'))}; "
                f"sum={count_text(album.get('primary_album_fused_bucket_sum'))}",
            ),
            ("Action", album.get("action")),
        ],
    )
    new = data["newartist_deep_dive"]
    lines.extend(["", "## New-Artist Deep Dive", "", new["summary"], ""])
    for row in new.get("buckets") or []:
        add_record(
            row["label"],
            [
                ("Turns", count_text(row.get("n"))),
                ("Share", pct(row.get("share"))),
                ("Cause", row.get("cause")),
                ("Fix", row.get("fix")),
            ],
        )
    lines.extend(["", "## Organizer Metadata", ""])
    org = data["organizer_metadata"]
    lines.append(org["current_pipeline_summary"])
    lines.append(org["category_caveat"])
    blind = org.get("blindset_availability") or data.get("blindset_metadata_availability") or {}
    lines.extend(["", "### Blind-A Availability Check", ""])
    lines.append(blind.get("summary") or "Blind-A availability was not checked.")
    for row in blind.get("rows") or []:
        add_record(
            row["item"],
            [
                ("Blind-A status", row["blind_a_status"]),
                ("Evidence", row["evidence"]),
                ("Report decision", row["report_decision"]),
            ],
        )
    lines.extend(["", "### Use vs Emulate / Extract Decision", ""])
    for row in data.get("metadata_decision_plan", []):
        lines.extend(
            [
                f"### {row['source']}",
                "",
                f"- Available as: {row['available_as']}",
                f"- Use directly: {row['use_directly']}",
                f"- Emulate or extract: {row['emulate_or_extract']}",
                f"- Ranking shape: {row['ranking_shape']}",
                f"- First test: {row['first_test']}",
                "",
            ]
        )
    lines.extend(["", "### Specificity Codes", ""])
    for row in org["specificity_summary"]:
        add_record(
            row["specificity"],
            [
                ("Sessions", count_text(row["sessions"])),
                ("Share", pct(row["share"])),
                ("Meaning", row["meaning"]),
                ("Example goal", row["example_goal"]),
            ],
        )
    lines.extend(["", "### Category Codes", ""])
    for row in org["category_summary"]:
        add_record(
            f"Category {row['category']}",
            [
                ("Sessions", count_text(row["sessions"])),
                ("Share", pct(row["share"])),
                ("Observed pattern", row["observed_pattern"]),
                ("Example goal", row["example_goal"]),
            ],
        )
    lines.extend(["", "### User Profile Fields", ""])
    for row in org["user_profile_fields"]:
        add_record(
            row["field"],
            [
                ("Current use", row["current_use"]),
                ("Recommended use", row["recommended_use"]),
            ],
        )
    lines.extend(["", "## Measured Lever Evidence", ""])
    for row in data["measured_levers"]:
        add_record(
            row["lever"],
            [
                ("Status", row["status"]),
                ("Result", row["result"]),
                ("Decision", row["decision"]),
                ("Source", row["source"]),
            ],
        )
    lines.extend(["", "## Ranker Feature Catalog", ""])
    for row in data["feature_catalog"]:
        add_record(
            row["feature"],
            [
                ("Grain", row["grain"]),
                ("Why", row["why"]),
                ("Validation", row["validation"]),
            ],
        )
    lines.extend(["", "## What Not To Work On First", ""])
    for row in data["not_first"]:
        add_record(
            row["idea"],
            [
                ("Decision", row["decision"]),
                ("Evidence", row["evidence"]),
            ],
        )
    lines.extend(["", "## Counting Caveats And Reconciliation", ""])
    for row in data["counting_reconciliation"]:
        add_record(
            row["claim"],
            [
                ("Report value", row["report_value"]),
                ("Alternate value", row["alternate_value"]),
                ("Basis", row["basis"]),
                ("Decision", row["decision"]),
            ],
        )
    lines.extend(["", "### Full Trace Routing Counts", ""])
    for row in data["routing_reconciliation"]:
        add_record(
            row["tag"],
            [
                ("Active turns", count_text(row["active_turns"])),
                ("Consumed", row["consumed"]),
            ],
        )
    lines.extend(["", "## Experiment Backlog And Measurement Contract", ""])
    for row in data["experiment_backlog"]:
        add_record(
            row["experiment"],
            [
                ("Status", row["status"]),
                ("Why", row["why"]),
                ("Measurement", row["measurement"]),
            ],
        )
    lines.extend(["", "## Validated State Defects", ""])
    for row in data["defects"]:
        add_record(
            row["label"],
            [
                ("Turns", count_text(row["n"])),
                ("Share", pct(row["share"])),
                ("Final@20", pct(row["final20"])),
                ("Union@20", pct(row["union20"])),
                ("Work", row["work"]),
            ],
        )
    lines.extend(["", "## Failure Example Explanations", ""])
    for group, rows in data["examples"].items():
        if not rows:
            continue
        lines.extend(["", f"### {group.replace('_', ' ').title()}", ""])
        for ex in rows:
            add_record(
                f"{ex['session_id']} turn {ex['turn']}",
                [
                    ("GT", f"{ex['gt_track']} by {ex['gt_artist']}"),
                    (
                        "Ranks",
                        f"final={rank_value(ex.get('final_rank'))}; "
                        f"branch={rank_value(ex.get('best_branch_rank'))} ({ex.get('best_branch') or 'NONE'})",
                    ),
                    ("Why wrong", ex.get("why_wrong")),
                    ("What should change", ex.get("what_should_change")),
                    ("Regression test", ex.get("regression_test")),
                ],
                level=4,
            )
    lines.extend(["", "## Hypotheses Tested", ""])
    for row in data["hypotheses"]:
        add_record(
            row["hypothesis"],
            [
                ("Verdict", row["verdict"]),
                ("Evidence", row["evidence"]),
                ("Implication", row["implication"]),
            ],
        )
    lines.extend(["", "## Sources", ""])
    for key, value in data["sources"].items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def write_outputs(data: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = out_dir
    draw_bar_chart(
        charts_dir / "state_task_modes.png",
        data["task_modes"],
        title="Task mode performance: final@20 vs union@20/100",
        label_key="label",
        value_keys=[
            ("final20", "F20", (37, 99, 235)),
            ("union20", "U20", (15, 118, 110)),
            ("union100", "U100", (194, 65, 12)),
        ],
        row_height=52,
    )
    draw_bar_chart(
        charts_dir / "state_defects.png",
        data["defects"],
        title="State defect slices: how much still reaches candidate pools?",
        label_key="label",
        value_keys=[
            ("share", "share", (91, 101, 117)),
            ("union20", "U20", (15, 118, 110)),
            ("final20", "F20", (37, 99, 235)),
        ],
        row_height=52,
    )
    focus_cohorts = [row for row in data["cohorts"] if row["n"] >= 50]
    draw_bar_chart(
        charts_dir / "state_cohorts.png",
        focus_cohorts,
        title="State cohorts with at least 50 turns",
        label_key="label",
        value_keys=[
            ("final20", "F20", (37, 99, 235)),
            ("union20", "U20", (15, 118, 110)),
            ("union100", "U100", (194, 65, 12)),
        ],
        row_height=48,
    )
    html_text = render_html(data, out_dir)
    md_text = render_markdown(data)
    (out_dir / "index.html").write_text(html_text, encoding="utf-8")
    (out_dir / "agent_report.md").write_text(md_text, encoding="utf-8")
    (out_dir / "state_report_data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "html": str(out_dir / "index.html"),
        "markdown": str(out_dir / "agent_report.md"),
        "json": str(out_dir / "state_report_data.json"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--tid", default=DEFAULT_TID)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = analyze(args.source_root, args.tid)
    outputs = write_outputs(data, args.out_dir)
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
