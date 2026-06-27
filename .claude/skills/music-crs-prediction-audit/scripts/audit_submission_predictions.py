#!/usr/bin/env python3
"""Build an interactive Music CRS prediction audit.

The report is useful before and after submission:
- with ground truth, it adds label-aware nDCG/hit/MRR diagnostics
- without ground truth, it audits conversation/state validity and candidate gaps
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


DEFAULT_DATASETS = {
    "devset": "talkpl-ai/TalkPlayData-Challenge-Dataset",
    "blindset_A": "talkpl-ai/TalkPlayData-Challenge-Blind-A",
    "blindset_B": "talkpl-ai/TalkPlayData-Challenge-Blind-B",
}
DEFAULT_CATALOG_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
DEFAULT_CATALOG_SPLIT = "all_tracks"

DEFAULT_JUDGE_MODEL = "openrouter/deepseek/deepseek-v4-flash"
JUDGE_PROMPT_VERSION = "v3_conversation_only"
EXPLANATION_JUDGE_PROMPT_VERSION = "v3_recsys_justification_profile"
STATE_JUDGE_PROMPT_VERSION = "v1_state_accuracy"
JUDGE_VERDICTS = {"good", "acceptable", "weak", "bad"}
STATE_JUDGE_VERDICTS = {"good", "partial", "bad"}
VERDICT_LABELS = {
    "recommendation": {
        "good": "strong fit",
        "acceptable": "plausible",
        "weak": "weak fit",
        "bad": "bad fit",
        "error": "error",
    },
    "explanation": {
        "good": "clear",
        "acceptable": "acceptable",
        "weak": "thin",
        "bad": "misleading",
        "error": "error",
    },
    "state": {
        "good": "accurate",
        "partial": "partial",
        "bad": "inaccurate",
        "error": "error",
    },
}

CATALOG_COLUMNS = [
    "track_id",
    "track_name",
    "artist_name",
    "album_name",
    "artist_id",
    "album_id",
    "popularity",
    "tag_list",
    "release_date",
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "give",
    "have",
    "i",
    "in",
    "into",
    "is",
    "it",
    "like",
    "maybe",
    "me",
    "more",
    "music",
    "of",
    "or",
    "please",
    "song",
    "songs",
    "that",
    "the",
    "them",
    "this",
    "time",
    "to",
    "track",
    "tracks",
    "with",
    "you",
}


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def verdict_label(kind: str, verdict: Any) -> str:
    value = str(verdict or "").strip().lower()
    return VERDICT_LABELS.get(kind, {}).get(value, value or "not available")


def verdict_counts_text(kind: str, counts: dict[str, Any]) -> str:
    return ", ".join(
        f"{verdict_label(kind, key)}={value}"
        for key, value in counts.items()
    )


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def first_text(value: Any) -> str:
    values = as_list(value)
    return "" if not values else str(values[0])


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_json_or_zip(path: Path) -> Any:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "prediction.json" in names:
                prediction_name = "prediction.json"
            else:
                json_names = [
                    name
                    for name in names
                    if name.lower().endswith(".json") and not name.endswith("/")
                ]
                if len(json_names) != 1:
                    raise ValueError(
                        f"{path} must contain prediction.json or exactly one JSON file."
                    )
                prediction_name = json_names[0]
            return json.loads(zf.read(prediction_name).decode("utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def maybe_load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except Exception:
        text = path.read_text(encoding="utf-8")
        out: dict[str, Any] = {}
        for line in text.splitlines():
            if ":" in line and not line.startswith((" ", "#")):
                key, value = line.split(":", 1)
                out[key.strip()] = value.strip()
        return out
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def infer_split(tid: str | None, config: dict[str, Any], explicit: str | None) -> str:
    if explicit:
        return explicit
    dataset = str(config.get("test_dataset_name", ""))
    if "Blind-A" in dataset or (tid and "blindset_A" in tid):
        return "blindset_A"
    if "Blind-B" in dataset or (tid and "blindset_B" in tid):
        return "blindset_B"
    dataset_match = re.search(r"Blind-([A-Za-z0-9]+)", dataset)
    if dataset_match:
        return f"blindset_{dataset_match.group(1)}"
    if tid and "blind" in tid:
        match = re.search(r"(blindset_[A-Za-z0-9]+)", tid)
        if match:
            return match.group(1)
    return "devset"


def resolve_inputs(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    tid = args.tid
    config_path = Path(args.config).resolve() if args.config else None
    config: dict[str, Any] = {}

    if tid and not config_path:
        candidate = repo_root / "configs" / f"{tid}.yaml"
        if candidate.exists():
            config_path = candidate
    if config_path and config_path.exists():
        config = maybe_load_yaml(config_path)
        tid = tid or config_path.stem

    split = infer_split(tid, config, args.split)
    prediction_path = Path(args.prediction).resolve() if args.prediction else None
    if not prediction_path and tid:
        candidate = repo_root / "exp" / "inference" / split / f"{tid}.json"
        if candidate.exists():
            prediction_path = candidate
    if not prediction_path:
        raise SystemExit("Provide --prediction or a --tid with an existing exp/inference file.")
    if not prediction_path.exists():
        raise SystemExit(f"Prediction file not found: {prediction_path}")

    trace_path = Path(args.trace).resolve() if args.trace else None
    if not trace_path and tid:
        candidate = repo_root / "exp" / "inference" / split / f"{tid}_trace.jsonl"
        if candidate.exists():
            trace_path = candidate
    if trace_path and not trace_path.exists():
        raise SystemExit(f"Trace file not found: {trace_path}")

    gt_path = Path(args.ground_truth).resolve() if args.ground_truth else None
    if gt_path and not gt_path.exists():
        raise SystemExit(f"Ground-truth file not found: {gt_path}")

    dataset_name = args.dataset or config.get("test_dataset_name") or DEFAULT_DATASETS.get(split)
    out_dir = Path(args.out).resolve() if args.out else (
        repo_root
        / "exp"
        / "analysis"
        / "prediction_audit"
        / (tid or prediction_path.stem)
    )
    catalog_lancedb = Path(args.catalog_lancedb).resolve() if args.catalog_lancedb else (
        repo_root / "cache" / "lancedb"
    )

    return {
        "repo_root": repo_root,
        "tid": tid or prediction_path.stem,
        "config_path": config_path,
        "config": config,
        "split": split,
        "dataset_name": dataset_name,
        "prediction_path": prediction_path,
        "trace_path": trace_path,
        "ground_truth_path": gt_path,
        "leaderboard_metadata_path": Path(args.leaderboard_metadata).resolve()
        if args.leaderboard_metadata
        else None,
        "catalog_lancedb": catalog_lancedb,
        "out_dir": out_dir,
    }


def load_predictions(path: Path) -> list[dict[str, Any]]:
    data = load_json_or_zip(path)
    if not isinstance(data, list):
        raise SystemExit("Prediction file must contain a list of rows.")
    for row in data:
        if "predicted_track_ids" not in row and "track_ids" in row:
            row["predicted_track_ids"] = row["track_ids"]
    return data


def load_traces(path: Path | None) -> dict[tuple[str, int], dict[str, Any]]:
    if not path:
        return {}
    traces: dict[tuple[str, int], dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            outer = json.loads(line)
            key = (outer["session_id"], int(outer["turn_number"]))
            traces[key] = outer.get("trace", outer)
    return traces


def load_ground_truth(path: Path | None) -> dict[tuple[str, int], str]:
    if not path:
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for row in rows:
        out[(row["session_id"], int(row["turn_number"]))] = row["ground_truth_track_id"]
    return out


def load_conversations(dataset_name: str | None) -> tuple[dict[str, dict[str, Any]], str | None]:
    if not dataset_name:
        return {}, "No dataset name was provided."
    try:
        from datasets import load_dataset
    except Exception as exc:
        return {}, f"Could not import datasets: {exc}"
    try:
        ds = load_dataset(dataset_name, split="test")
    except Exception as exc:
        return {}, f"Could not load dataset {dataset_name}: {exc}"
    rows = {row["session_id"]: dict(row) for row in ds}
    return rows, None


@dataclass
class Catalog:
    meta: dict[str, dict[str, Any]]
    warning: str | None = None
    source: str | None = None

    def get(self, track_id: str) -> dict[str, Any]:
        return self.meta.get(
            track_id,
            {
                "track_id": track_id,
                "track_name": track_id,
                "artist_name": "",
                "album_name": "",
                "artist_id": "",
                "album_id": "",
                "popularity": 0.0,
                "tag_list": [],
                "release_date": "",
            },
        )


def load_catalog_lancedb(path: Path) -> Catalog:
    try:
        import lancedb
    except Exception as exc:
        return Catalog({}, f"Could not import lancedb: {exc}", source="lancedb")
    try:
        db = lancedb.connect(str(path))
        table = db.open_table("music_track_catalog")
        existing = {field.name for field in table.schema}
        available = [c for c in CATALOG_COLUMNS if c in existing]
        if not available:
            return Catalog({}, f"LanceDB catalog at {path} has no metadata columns.", source="lancedb")
        rows = table.search().select(available).limit(0).to_list()
        meta = {}
        for row in rows:
            track_id = row.get("track_id")
            if not track_id:
                continue
            row = {c: row.get(c) for c in available}
            meta[str(track_id)] = row
        return Catalog(meta, source="lancedb")
    except Exception as exc:
        return Catalog({}, f"Could not load LanceDB catalog at {path}: {exc}", source="lancedb")


def load_catalog_hf(
    dataset_name: str = DEFAULT_CATALOG_DATASET,
    split: str = DEFAULT_CATALOG_SPLIT,
    loader: Any | None = None,
) -> Catalog:
    try:
        if loader is None:
            from datasets import load_dataset as loader
    except Exception as exc:
        return Catalog({}, f"Could not import datasets: {exc}", source="hf")
    try:
        ds = loader(dataset_name, split=split)
        meta = {}
        for row in ds:
            track_id = row.get("track_id") if isinstance(row, dict) else None
            if not track_id:
                continue
            meta[str(track_id)] = {c: row.get(c) for c in CATALOG_COLUMNS if c in row}
        return Catalog(meta, source="hf")
    except Exception as exc:
        return Catalog(
            {},
            f"Could not load HF catalog {dataset_name} split {split}: {exc}",
            source="hf",
        )


def load_catalog(
    path: Path,
    *,
    source: str = "auto",
    hf_dataset: str = DEFAULT_CATALOG_DATASET,
    hf_split: str = DEFAULT_CATALOG_SPLIT,
) -> Catalog:
    source = (source or "auto").lower()
    if source == "hf":
        return load_catalog_hf(hf_dataset, hf_split)
    lancedb_catalog = load_catalog_lancedb(path)
    if source == "lancedb" or lancedb_catalog.meta:
        return lancedb_catalog
    hf_catalog = load_catalog_hf(hf_dataset, hf_split)
    if hf_catalog.meta:
        warning = lancedb_catalog.warning
        if warning:
            hf_catalog.warning = f"{warning}; fell back to HF catalog."
        return hf_catalog
    if lancedb_catalog.warning and hf_catalog.warning:
        return Catalog(
            {},
            f"{lancedb_catalog.warning}; {hf_catalog.warning}",
            source="auto",
        )
    return hf_catalog


def track_label(catalog: Catalog, track_id: str) -> str:
    m = catalog.get(track_id)
    artist = first_text(m.get("artist_name"))
    title = first_text(m.get("track_name"))
    return f"{title} -- {artist}" if artist else title


def metadata_text(catalog: Catalog, track_id: str) -> str:
    m = catalog.get(track_id)
    tags = " ".join(str(x) for x in as_list(m.get("tag_list")))
    return " ".join(
        [
            first_text(m.get("track_name")),
            first_text(m.get("artist_name")),
            first_text(m.get("album_name")),
            tags,
        ]
    )


def compact_meta(catalog: Catalog, track_id: str) -> dict[str, Any]:
    m = catalog.get(track_id)
    return {
        "track_id": track_id,
        "track_name": first_text(m.get("track_name")),
        "artist_name": first_text(m.get("artist_name")),
        "album_name": first_text(m.get("album_name")),
        "artist_id": first_text(m.get("artist_id")),
        "album_id": first_text(m.get("album_id")),
        "popularity": safe_float(first_text(m.get("popularity"))),
        "release_date": first_text(m.get("release_date")),
        "tags": [str(x) for x in as_list(m.get("tag_list"))[:12]],
    }


def compact_meta_text(meta: dict[str, Any]) -> str:
    return " ".join(
        [
            meta.get("track_name", ""),
            meta.get("artist_name", ""),
            meta.get("album_name", ""),
            " ".join(meta.get("tags") or []),
        ]
    )


def latest_user_text(conversation: dict[str, Any] | None, turn_number: int) -> str:
    if not conversation:
        return ""
    user_turns = [
        t.get("content", "")
        for t in conversation.get("conversations", [])
        if t.get("role") == "user" and int(t.get("turn_number", -1)) == int(turn_number)
    ]
    return str(user_turns[-1]) if user_turns else ""


def prior_music_track_ids(conversation: dict[str, Any] | None, turn_number: int) -> list[str]:
    if not conversation:
        return []
    ids = []
    for t in conversation.get("conversations", []):
        if t.get("role") == "music" and int(t.get("turn_number", 0)) < int(turn_number):
            ids.append(str(t.get("content", "")))
    return [x for x in ids if x]


def state_values(trace: dict[str, Any], keys: list[str]) -> list[Any]:
    values = []
    extracted = trace.get("extracted_state") or {}
    compiled = trace.get("compiled_state") or {}
    for container in (extracted, compiled):
        for key in keys:
            values.extend(as_list(container.get(key)))
    return values


def extract_fact_values(facts: list[Any], mode: str) -> list[str]:
    out = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        role = str(fact.get("role", ""))
        relation = str(fact.get("relation", ""))
        reuse = str(fact.get("reuse", ""))
        anchor = str(fact.get("anchor_use", ""))
        if mode == "hard" and not {
            role,
            relation,
            reuse,
            anchor,
        }.intersection({"rejected", "exclude", "must_exclude"}):
            continue
        if mode == "soft" and not {
            role,
            relation,
            reuse,
            anchor,
        }.intersection({"satisfied_prior", "avoid_exact", "do_not_use"}):
            continue
        value = str(fact.get("value", "")).strip()
        if value:
            out.append(value)
    return out


def extract_named_values(items: list[Any]) -> list[str]:
    out = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("value") or item.get("name") or item.get("text")
            if value:
                out.append(str(value))
        elif item:
            out.append(str(item))
    return out


def significant_terms(text: str) -> list[str]:
    raw = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]{2,}", text.lower())]
    terms = []
    for w in raw:
        n = norm(w)
        if n and n not in STOPWORDS and len(n) >= 3:
            terms.append(n)
    return list(dict.fromkeys(terms))


def derive_audit_terms(
    row: dict[str, Any],
    trace: dict[str, Any],
    conversation: dict[str, Any] | None,
    catalog: Catalog,
) -> dict[str, Any]:
    turn_number = int(row["turn_number"])
    extracted = trace.get("extracted_state") or {}
    resolver = trace.get("resolver") or {}
    latest = latest_user_text(conversation, turn_number)
    facts = as_list(extracted.get("facts"))

    rejected_names = []
    avoid_names = []
    rejected_names += extract_named_values(state_values(trace, ["exclusions", "rejections", "explicit_rejections"]))
    rejected_names += extract_fact_values(facts, "hard")
    avoid_names += extract_fact_values(facts, "soft")

    latest_norm = norm(latest)
    switch_requested = any(
        phrase in latest_norm
        for phrase in [
            "new artist",
            "new artists",
            "other artist",
            "other artists",
            "different artist",
            "different artists",
            "completely different artist",
            "another artist",
            "branch out",
            "diversify",
            "something different",
            "add some variety",
            "variety",
            "no more",
        ]
    )
    different_album_requested = any(
        phrase in latest_norm
        for phrase in [
            "another game soundtrack",
            "different game soundtrack",
            "other game soundtrack",
            "different soundtrack",
            "another soundtrack",
            "no more dmc",
            "no more album",
        ]
    )

    prior_ids = prior_music_track_ids(conversation, turn_number)
    prior_artists = []
    prior_albums = []
    for tid in prior_ids:
        m = compact_meta(catalog, tid)
        if m["artist_name"]:
            prior_artists.append(m["artist_name"])
        if m["album_name"]:
            prior_albums.append(m["album_name"])
    prior_artist_counts = Counter(prior_artists)
    prior_album_counts = Counter(prior_albums)
    if switch_requested:
        avoid_names += [name for name, count in prior_artist_counts.items() if count >= 1]
    if different_album_requested:
        avoid_names += [name for name, count in prior_album_counts.items() if count >= 1]

    current_request = extracted.get("current_request") or {}
    request_summary = ""
    if isinstance(current_request, dict):
        request_summary = str(current_request.get("summary") or "")
    else:
        request_summary = str(current_request)
    positive_text = " ".join(
        [
            latest,
            request_summary,
            " ".join(
                str(f.get("value", ""))
                for f in facts
                if isinstance(f, dict)
                and str(f.get("role", "")) in {"current_target", "positive", "query_facet"}
            ),
        ]
    )

    rejected_names = [
        x.strip()
        for x in dict.fromkeys(rejected_names)
        if len(norm(x)) >= 3 and norm(x) not in {"unknown", "none", "other artists"}
    ]
    avoid_names = [
        x.strip()
        for x in dict.fromkeys(avoid_names)
        if len(norm(x)) >= 3 and norm(x) not in {"unknown", "none", "other artists"}
    ]

    return {
        "latest_user_text": latest,
        "prior_track_ids": prior_ids,
        "prior_artists": dict(prior_artist_counts),
        "prior_albums": dict(prior_album_counts),
        "switch_requested": switch_requested,
        "different_album_requested": different_album_requested,
        "rejected_names": rejected_names,
        "avoid_names": avoid_names,
        "rejected_artist_ids": [str(x) for x in as_list(resolver.get("rejected_artist_ids"))],
        "rejected_track_ids": [str(x) for x in as_list(resolver.get("rejected_track_ids"))],
        "positive_terms": significant_terms(positive_text)[:40],
        "current_request_summary": request_summary,
    }


def violation_flags(
    track_id: str,
    catalog: Catalog,
    terms: dict[str, Any],
    meta: dict[str, Any] | None = None,
    text_norm: str | None = None,
) -> list[str]:
    m = meta or compact_meta(catalog, track_id)
    flags = []
    if track_id in set(terms["rejected_track_ids"]):
        flags.append("rejected_track_id")
    if m["artist_id"] and m["artist_id"] in set(terms["rejected_artist_ids"]):
        flags.append("rejected_artist_id")
    text_norm = text_norm or norm(compact_meta_text(m))
    for name in terms["rejected_names"]:
        name_norm = norm(name)
        if name_norm and name_norm in text_norm:
            flags.append(f"rejected_name:{name}")
    for name in terms.get("avoid_names", []):
        name_norm = norm(name)
        if name_norm and name_norm in text_norm:
            flags.append(f"avoid_name:{name}")
    if terms["switch_requested"] and m["artist_name"] in terms["prior_artists"]:
        flags.append(f"prior_artist_after_switch:{m['artist_name']}")
    if terms["different_album_requested"] and m["album_name"] in terms["prior_albums"]:
        flags.append(f"prior_album_after_switch:{m['album_name']}")
    return list(dict.fromkeys(flags))


def candidate_fit_score(
    track_id: str,
    catalog: Catalog,
    terms: dict[str, Any],
    meta: dict[str, Any] | None = None,
    text_norm: str | None = None,
) -> float:
    m = meta or compact_meta(catalog, track_id)
    text = text_norm or norm(metadata_text(catalog, track_id))
    score = 0.0
    for term in terms["positive_terms"]:
        if term and term in text:
            score += 1.0
    score += min(m["popularity"], 100.0) / 200.0
    return round(score, 4)


def find_better_candidate(
    track_ids: list[str],
    catalog: Catalog,
    terms: dict[str, Any],
    cf_rank: dict[str, int] | None = None,
    exclude_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    exclude_ids = exclude_ids or set()
    best = None
    for rank, tid in enumerate(track_ids, start=1):
        if tid in exclude_ids:
            continue
        meta = compact_meta(catalog, tid)
        text_norm = norm(compact_meta_text(meta))
        flags = violation_flags(tid, catalog, terms, meta=meta, text_norm=text_norm)
        if flags:
            continue
        score = candidate_fit_score(tid, catalog, terms, meta=meta, text_norm=text_norm)
        cf = cf_rank.get(tid) if cf_rank else None
        candidate = {
            "rank": rank,
            "candidate_fusion_rank": cf,
            "fit_score": score,
            "track": meta,
        }
        key = (score, -(cf or rank), -rank, safe_float(candidate["track"]["popularity"]))
        if best is None or key > best[0]:
            best = (key, candidate)
    return best[1] if best else None


def get_candidate_fusion(trace: dict[str, Any]) -> list[str]:
    stages = (trace.get("ranking") or {}).get("stages") or []
    for stage in stages:
        if isinstance(stage, dict) and stage.get("name") == "candidate_fusion":
            return [str(x) for x in stage.get("track_ids", [])]
    return []


def branch_names(trace: dict[str, Any]) -> list[str]:
    branches = (trace.get("retrieval") or {}).get("branches") or []
    out = []
    for branch in branches:
        if isinstance(branch, dict):
            out.append(str(branch.get("name", "")))
    return [x for x in out if x]


def conversation_for_judge(row: dict[str, Any], catalog: Catalog, max_turns: int = 12) -> str:
    turns = row.get("conversation") or []
    if not turns:
        latest = row.get("latest_user_text") or ""
        return f"user {row.get('turn_number')}: {latest}" if latest else "Conversation text unavailable."

    rendered = []
    for turn in turns[-max_turns:]:
        role = str(turn.get("role", ""))
        content = str(turn.get("content", ""))
        if role == "music":
            content = track_label(catalog, content)
        rendered.append(f"{role} {turn.get('turn_number', '')}: {content}")
    return "\n".join(rendered)


def profile_for_judge(row: dict[str, Any], max_chars: int = 1200) -> str:
    profile = row.get("user_profile")
    if profile in (None, "", [], {}):
        return "not provided"
    try:
        text = json.dumps(profile, ensure_ascii=False, sort_keys=True)
    except TypeError:
        text = str(profile)
    return text if len(text) <= max_chars else text[: max_chars - 3] + "..."


def state_under_review(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent_mode": row.get("intent_mode"),
        "request_type": row.get("request_type"),
        "retrieval_profile": row.get("retrieval_profile"),
        "routing_tags": row.get("routing_tags"),
        "state_excerpt": row.get("state_excerpt"),
    }


def state_for_judge(row: dict[str, Any], max_chars: int = 5000) -> str:
    text = json.dumps(state_under_review(row), ensure_ascii=False, sort_keys=True, indent=2)
    return text if len(text) <= max_chars else text[: max_chars - 3] + "..."


def item_for_judge(item: dict[str, Any], include_state: bool = False) -> str:
    track = item["track"]
    tags = ", ".join(track.get("tags", [])[:8]) or "no tags"
    text = (
        f"{item['rank']}. {track['track_name']} by {track['artist_name']} | "
        f"album: {track['album_name']} | popularity: {track.get('popularity', 0):.0f} | "
        f"tags: {tags}"
    )
    if include_state:
        flags = ", ".join(item.get("flags") or []) or "none"
        fusion = item.get("candidate_fusion_rank")
        fusion_text = f"fusion rank {fusion}" if fusion else "not present in fusion trace"
        text += (
            f" | diagnostic {fusion_text} | diagnostic heuristic fit: {item.get('fit_score', 0):.2f} | "
            f"diagnostic audit flags: {flags}"
        )
    return text


def build_judge_prompt(
    row: dict[str, Any],
    catalog: Catalog,
    top_k: int,
    include_state: bool = False,
) -> str:
    candidates = "\n".join(
        item_for_judge(item, include_state=include_state) for item in row.get("items", [])[:top_k]
    )
    state_section = ""
    if include_state:
        hard_rejections = ", ".join(row.get("rejected_names") or []) or "none found"
        soft_avoid = ", ".join(row.get("avoid_names") or []) or "none found"
        positive_terms = ", ".join(row.get("positive_terms") or []) or "none found"
        state_section = f"""
Diagnostic structured state summary:
- Treat this section as model/pipeline diagnostics, not ground truth.
- Current request: {row.get("current_request_summary") or "not captured"}
- Hard rejected names: {hard_rejections}
- Soft avoid / move-away names: {soft_avoid}
- Positive audit terms: {positive_terms}
"""
    return f"""You are judging a conversational music recommendation for a label-free/blind audit.

Important rules:
- Use the visible conversation and candidate metadata as the source of truth.
- Infer user constraints directly from the conversation; do not assume pipeline state is correct.
- Do not assume the hidden leaderboard answer.
- Judge whether the current top recommendation is a good response to the user's latest request.
- If another candidate in the shown list is clearly better, identify its rank.
- If the latest user request is informational, asks for an album/artist fact, asks for an explanation, or otherwise should not be answered by recommending a track, mark the top recommendation bad and set best_rank to null unless one shown track directly answers the request.
- If none of the shown candidates is a valid response, set best_rank to null and explain that no submitted track should be recommended for this turn.
- Prefer respecting explicit rejections, requested changes, genre/mood/artist constraints, and conversation continuity.

Conversation goal:
{row.get("conversation_goal") or "not provided"}

Recent conversation:
{conversation_for_judge(row, catalog)}

Latest user request:
{row.get("latest_user_text") or ""}
{state_section}

Candidate recommendations:
{candidates}

Return ONLY a JSON object with this shape:
{{
  "verdict": "good" | "acceptable" | "weak" | "bad",
  "top_rank_valid": true | false,
  "best_rank": integer rank from the shown candidates | null,
  "none_is_valid": true | false,
  "constraint_violation": true | false,
  "reason": "plain English, one or two sentences for a non-music expert"
}}
"""


def top_item_for_explanation(row: dict[str, Any]) -> str:
    items = row.get("items") or []
    if not items:
        return "No submitted recommendation metadata available."
    return item_for_judge(items[0], include_state=False)


def build_explanation_judge_prompt(row: dict[str, Any], catalog: Catalog) -> str:
    response = str(row.get("prediction_response") or "").strip()
    return f"""You are judging the natural-language response that accompanies a conversational music recommender's submitted top recommendation for a label-free/blind audit.

Organizer-facing task framing:
- The response should accompany the recommendations, justify the picks from the user's profile or previous turns, and maintain coherent conversational flow.
- Blind-set response quality is judged as text quality, especially personalization and explanation quality, independently from whether the retrieved track is the hidden ground-truth item.

Important rules:
- Use only the visible conversation and candidate metadata as evidence.
- Do not assume the hidden leaderboard answer.
- Do not use compiled/extracted pipeline state; it may be buggy.
- Judge the generated response text as an explanation of the submitted top recommendation, not as a replacement recommender.
- A good response should clearly ground itself in the submitted top recommendation, personalize or justify why that recommendation fits the visible conversation, stay coherent with the latest user turn, and use language a non-music expert can understand.
- Penalize generic prose that could fit any song, responses that explain a different song/artist, contradictions of visible constraints, unsupported album/artist/genre/mood claims, or recommending something while saying it should be avoided.
- If the submitted top recommendation itself appears weak from the visible conversation, do not score the response badly for retrieval accuracy alone; instead judge whether the prose remains honest, relevant, and not misleading.

Conversation goal:
{row.get("conversation_goal") or "not provided"}

User profile:
{profile_for_judge(row)}

Recent conversation:
{conversation_for_judge(row, catalog)}

Latest user request:
{row.get("latest_user_text") or ""}

Top submitted recommendation:
{top_item_for_explanation(row)}

Generated response to judge:
{response or "[empty response]"}

Return ONLY a JSON object with this shape:
{{
  "verdict": "good" | "acceptable" | "weak" | "bad",
  "grounds_top_recommendation": true | false,
  "justifies_fit": true | false,
  "conversation_relevant": true | false,
  "metadata_hallucination": true | false,
  "constraint_violation": true | false,
  "reason": "plain English, one or two sentences for a non-music expert"
}}
"""


def build_state_judge_prompt(row: dict[str, Any], catalog: Catalog) -> str:
    return f"""You are judging whether a Music CRS pipeline's extracted/compiled state is accurate for one conversation turn.

Important rules:
- This is a diagnostic state/compiler audit, not a recommendation-quality judge.
- Use the raw conversation as the source of truth. Conversation goal and user profile are auxiliary context only; if missing, ignore them.
- Evaluate whether the extracted/compiled state captures the current user turn and relevant prior context: requested artists/tracks/albums, genre/mood/era/style constraints, explicit rejections/exclusions, branch-out/switch requests, continuation intent, and resolver outputs.
- Penalize missing constraints, stale carried-over entities, contradictory state, or compiled routing/profile fields that would likely send retrieval in the wrong direction.
- Do not judge whether the final recommendation is correct.

Conversation goal:
{row.get("conversation_goal") or "not provided"}

User profile:
{profile_for_judge(row)}

Recent conversation:
{conversation_for_judge(row, catalog)}

Latest user request:
{row.get("latest_user_text") or ""}

Extracted/compiled state to judge:
{state_for_judge(row)}

Return ONLY a JSON object with this shape:
{{
  "verdict": "good" | "partial" | "bad",
  "state_accurate": true | false,
  "missing_constraints": ["short plain-English item", "..."],
  "extra_or_stale_state": ["short plain-English item", "..."],
  "compiled_state_risk": true | false,
  "reason": "plain English, one or two sentences for a non-music expert"
}}
"""


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass
    salvaged: dict[str, Any] = {}
    verdict = re.search(r'"verdict"\s*:\s*"([^"]+)"', text)
    if verdict:
        salvaged["verdict"] = verdict.group(1)
    top_rank_valid = re.search(r'"top_rank_valid"\s*:\s*(true|false)', text, flags=re.I)
    if top_rank_valid:
        salvaged["top_rank_valid"] = top_rank_valid.group(1).lower() == "true"
    best_rank = re.search(r'"best_rank"\s*:\s*([0-9]+)', text)
    if best_rank:
        salvaged["best_rank"] = int(best_rank.group(1))
    violation = re.search(r'"constraint_violation"\s*:\s*(true|false)', text, flags=re.I)
    if violation:
        salvaged["constraint_violation"] = violation.group(1).lower() == "true"
    none_valid = re.search(r'"none_is_valid"\s*:\s*(true|false)', text, flags=re.I)
    if none_valid:
        salvaged["none_is_valid"] = none_valid.group(1).lower() == "true"
    reason = re.search(r'"reason"\s*:\s*"([^"]*)', text, flags=re.S)
    if reason:
        salvaged["reason"] = reason.group(1)
    return salvaged


def judge_cache_key(
    row: dict[str, Any],
    catalog: Catalog,
    model: str,
    top_k: int,
    include_state: bool,
) -> str:
    candidate_prompt_items = [
        item_for_judge(item, include_state=include_state) for item in row.get("items", [])[:top_k]
    ]
    payload = {
        "prompt_version": JUDGE_PROMPT_VERSION,
        "model": model,
        "top_k": top_k,
        "include_state": include_state,
        "session_id": row.get("session_id"),
        "turn_number": row.get("turn_number"),
        "latest_user_text": row.get("latest_user_text"),
        "conversation_goal": row.get("conversation_goal"),
        "conversation": row.get("conversation"),
        "conversation_prompt": conversation_for_judge(row, catalog),
        "candidate_prompt_items": candidate_prompt_items,
    }
    if include_state:
        payload.update(
            {
                "current_request_summary": row.get("current_request_summary"),
                "rejected_names": row.get("rejected_names"),
                "avoid_names": row.get("avoid_names"),
                "positive_terms": row.get("positive_terms"),
            }
        )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def explanation_judge_cache_key(row: dict[str, Any], catalog: Catalog, model: str) -> str:
    top_track = ((row.get("items") or [{}])[0].get("track") or {}) if row.get("items") else {}
    payload = {
        "prompt_version": EXPLANATION_JUDGE_PROMPT_VERSION,
        "model": model,
        "session_id": row.get("session_id"),
        "turn_number": row.get("turn_number"),
        "latest_user_text": row.get("latest_user_text"),
        "conversation_goal": row.get("conversation_goal"),
        "user_profile": row.get("user_profile"),
        "conversation": row.get("conversation"),
        "conversation_prompt": conversation_for_judge(row, catalog),
        "user_profile_prompt": profile_for_judge(row),
        "top_item_prompt": top_item_for_explanation(row),
        "top_track": {
            "track_id": top_track.get("track_id"),
            "track_name": top_track.get("track_name"),
            "artist_name": top_track.get("artist_name"),
            "album_name": top_track.get("album_name"),
            "tags": top_track.get("tags"),
            "popularity": top_track.get("popularity"),
        },
        "prediction_response": row.get("prediction_response"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def state_judge_cache_key(row: dict[str, Any], catalog: Catalog, model: str) -> str:
    payload = {
        "prompt_version": STATE_JUDGE_PROMPT_VERSION,
        "model": model,
        "session_id": row.get("session_id"),
        "turn_number": row.get("turn_number"),
        "latest_user_text": row.get("latest_user_text"),
        "conversation_goal": row.get("conversation_goal"),
        "user_profile": row.get("user_profile"),
        "conversation": row.get("conversation"),
        "conversation_prompt": conversation_for_judge(row, catalog),
        "user_profile_prompt": profile_for_judge(row),
        "state_prompt": state_for_judge(row),
        "state_under_review": state_under_review(row),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_judge_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = row.get("cache_key")
            if key:
                out[str(key)] = row
    return out


def append_judge_cache(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_dotenv_for_judge(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value


def normalize_judgment(
    raw: dict[str, Any],
    *,
    model: str,
    top_k: int,
    cache_key: str,
    cached: bool,
) -> dict[str, Any]:
    verdict = str(raw.get("verdict") or "").strip().lower()
    if verdict not in JUDGE_VERDICTS:
        verdict = "weak"
    best_rank = raw.get("best_rank")
    try:
        best_rank = int(best_rank)
    except (TypeError, ValueError):
        best_rank = None
    if best_rank is not None and not (1 <= best_rank <= top_k):
        best_rank = None
    top_rank_valid = bool(raw.get("top_rank_valid", verdict in {"good", "acceptable"}))
    if top_rank_valid is False and verdict in {"good", "acceptable"}:
        verdict = "weak"
    elif best_rank and best_rank != 1 and verdict == "good":
        verdict = "acceptable"
    elif best_rank is None and verdict in {"good", "acceptable"}:
        verdict = "weak"
    return {
        "model": model,
        "top_k": top_k,
        "prompt_version": JUDGE_PROMPT_VERSION,
        "verdict": verdict,
        "top_rank_valid": top_rank_valid,
        "best_rank": best_rank,
        "none_is_valid": bool(raw.get("none_is_valid", best_rank is None and not top_rank_valid)),
        "constraint_violation": bool(raw.get("constraint_violation", verdict == "bad")),
        "reason": str(raw.get("reason") or "").strip()[:900],
        "cache_key": cache_key,
        "cached": cached,
    }


def normalize_explanation_judgment(
    raw: dict[str, Any],
    *,
    model: str,
    cache_key: str,
    cached: bool,
) -> dict[str, Any]:
    verdict = str(raw.get("verdict") or "").strip().lower()
    if verdict not in JUDGE_VERDICTS:
        verdict = "weak"
    grounds_top_recommendation = bool(
        raw.get(
            "grounds_top_recommendation",
            raw.get("faithful_to_recommendation", verdict in {"good", "acceptable"}),
        )
    )
    justifies_fit = bool(
        raw.get(
            "justifies_fit",
            raw.get("answers_latest_request", verdict in {"good", "acceptable"}),
        )
    )
    conversation_relevant = bool(
        raw.get(
            "conversation_relevant",
            raw.get("answers_latest_request", verdict in {"good", "acceptable"}),
        )
    )
    metadata_hallucination = bool(raw.get("metadata_hallucination", False))
    constraint_violation = bool(raw.get("constraint_violation", verdict == "bad"))
    if verdict in {"good", "acceptable"} and (
        not grounds_top_recommendation
        or not justifies_fit
        or not conversation_relevant
        or metadata_hallucination
        or constraint_violation
    ):
        verdict = "weak"
    return {
        "model": model,
        "prompt_version": EXPLANATION_JUDGE_PROMPT_VERSION,
        "verdict": verdict,
        "grounds_top_recommendation": grounds_top_recommendation,
        "justifies_fit": justifies_fit,
        "conversation_relevant": conversation_relevant,
        "answers_latest_request": conversation_relevant,
        "faithful_to_recommendation": grounds_top_recommendation,
        "metadata_hallucination": metadata_hallucination,
        "constraint_violation": constraint_violation,
        "reason": str(raw.get("reason") or "").strip()[:900],
        "cache_key": cache_key,
        "cached": cached,
    }


def short_string_list(value: Any, limit: int = 8) -> list[str]:
    out = []
    for item in as_list(value):
        text = str(item or "").strip()
        if text:
            out.append(text[:240])
    return out[:limit]


def normalize_state_judgment(
    raw: dict[str, Any],
    *,
    model: str,
    cache_key: str,
    cached: bool,
) -> dict[str, Any]:
    verdict = str(raw.get("verdict") or "").strip().lower()
    if verdict not in STATE_JUDGE_VERDICTS:
        verdict = "partial"
    missing = short_string_list(raw.get("missing_constraints"))
    stale = short_string_list(raw.get("extra_or_stale_state"))
    state_accurate = bool(raw.get("state_accurate", verdict == "good"))
    compiled_state_risk = bool(raw.get("compiled_state_risk", verdict == "bad"))
    if verdict == "good" and (not state_accurate or missing or stale or compiled_state_risk):
        verdict = "partial"
    if verdict == "partial" and compiled_state_risk and (missing or stale):
        verdict = "bad"
    return {
        "model": model,
        "prompt_version": STATE_JUDGE_PROMPT_VERSION,
        "verdict": verdict,
        "state_accurate": state_accurate,
        "missing_constraints": missing,
        "extra_or_stale_state": stale,
        "compiled_state_risk": compiled_state_risk,
        "reason": str(raw.get("reason") or "").strip()[:900],
        "cache_key": cache_key,
        "cached": cached,
    }


def configure_litellm_completion_cache(
    litellm_module: Any,
    mode: str,
    cache_dir: Path | None,
) -> dict[str, Any]:
    mode = (mode or "disk").strip().lower()
    if mode == "off":
        disable_cache = getattr(litellm_module, "disable_cache", None)
        if callable(disable_cache):
            disable_cache()
        else:
            litellm_module.cache = None
        return {"enabled": False, "mode": "off"}

    try:
        from litellm.caching.caching import Cache
    except Exception as exc:
        return {
            "enabled": False,
            "mode": mode,
            "warning": f"Could not import LiteLLM Cache: {exc}",
        }

    try:
        if mode == "disk":
            if cache_dir is None:
                raise ValueError("disk cache requires a cache directory")
            cache_dir.mkdir(parents=True, exist_ok=True)
            litellm_module.cache = Cache(
                type="disk",
                disk_cache_dir=str(cache_dir),
                supported_call_types=["completion"],
            )
            return {"enabled": True, "mode": "disk", "path": str(cache_dir)}
        if mode == "local":
            litellm_module.cache = Cache(type="local", supported_call_types=["completion"])
            return {"enabled": True, "mode": "local"}
    except Exception as exc:
        return {
            "enabled": False,
            "mode": mode,
            "warning": f"Could not initialize LiteLLM {mode} cache: {exc}",
        }

    return {
        "enabled": False,
        "mode": mode,
        "warning": f"Unsupported LiteLLM cache mode: {mode}",
    }


def requested_litellm_cache_metadata(mode: str, cache_dir: Path | None) -> dict[str, Any]:
    mode = (mode or "disk").strip().lower()
    return {
        "enabled": mode != "off",
        "mode": mode,
        "path": str(cache_dir) if mode == "disk" and cache_dir else None,
    }


def run_llm_json_judge(
    rows: list[dict[str, Any]],
    *,
    out_dir: Path,
    model: str,
    limit: int,
    workers: int,
    max_tokens: int,
    cache_path: Path | None,
    litellm_cache_mode: str,
    litellm_cache_dir: Path | None,
    cache_filename: str,
    judgment_key: str,
    log_label: str,
    warning_label: str,
    system_prompt: str,
    non_json_label: str,
    cache_key_fn: Any,
    prompt_fn: Any,
    normalize_fn: Any,
    metadata_extra: dict[str, Any] | None = None,
    label_free_only: bool = True,
) -> dict[str, Any]:
    load_dotenv_for_judge()
    metadata_extra = metadata_extra or {}

    def base_metadata() -> dict[str, Any]:
        return {
            "enabled": True,
            "model": model,
            "label_free_only": label_free_only,
            **metadata_extra,
        }

    if model.startswith("openrouter/") and not os.environ.get("OPENROUTER_API_KEY"):
        return {
            **base_metadata(),
            "ran": False,
            "warning": f"OPENROUTER_API_KEY is not set, so no {warning_label} calls were made.",
            "litellm_cache": requested_litellm_cache_metadata(
                litellm_cache_mode,
                litellm_cache_dir,
            ),
        }

    try:
        import litellm
    except Exception as exc:
        return {
            **base_metadata(),
            "ran": False,
            "warning": f"Could not import litellm: {exc}",
            "litellm_cache": requested_litellm_cache_metadata(
                litellm_cache_mode,
                litellm_cache_dir,
            ),
        }

    litellm.suppress_debug_info = True
    litellm_cache = configure_litellm_completion_cache(
        litellm,
        litellm_cache_mode,
        litellm_cache_dir,
    )
    cache_file = cache_path or (out_dir / cache_filename)
    cache = load_judge_cache(cache_file)
    max_rows = len(rows) if limit <= 0 else min(limit, len(rows))
    judged = 0
    errors = 0
    pending: list[tuple[dict[str, Any], str]] = []

    for row in rows[:max_rows]:
        key = cache_key_fn(row)
        cached_record = cache.get(key)
        if cached_record and isinstance(cached_record.get("judgment"), dict):
            row[judgment_key] = normalize_fn(cached_record["judgment"], key, True)
            judged += 1
            continue
        pending.append((row, key))

    if judged:
        print(f"{log_label}: {judged}/{max_rows} cached", flush=True)

    def call_one(row: dict[str, Any], key: str) -> dict[str, Any]:
        prompt = prompt_fn(row)
        call_kwargs = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "timeout": 90,
            "extra_body": {"reasoning": {"enabled": False}},
        }
        if model.startswith("openrouter/"):
            call_kwargs["response_format"] = {"type": "json_object"}
        try:
            response = litellm.completion(**call_kwargs)
        except Exception as exc:
            if "response_format" not in call_kwargs:
                raise
            call_kwargs.pop("response_format", None)
            try:
                response = litellm.completion(**call_kwargs)
            except Exception:
                raise exc
        content = response.choices[0].message.content or ""
        parsed = extract_json_object(content)
        if not parsed:
            raise ValueError(f"{non_json_label} returned non-JSON content: {content[:160]}")
        return normalize_fn(parsed, key, False)

    if pending:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {executor.submit(call_one, row, key): (row, key) for row, key in pending}
            for future in as_completed(futures):
                row, key = futures[future]
                try:
                    judgment = future.result()
                    row[judgment_key] = judgment
                    append_judge_cache(
                        cache_file,
                        {
                            "cache_key": key,
                            "session_id": row.get("session_id"),
                            "turn_number": row.get("turn_number"),
                            "model": model,
                            "judgment": judgment,
                        },
                    )
                    judged += 1
                    if judged % 10 == 0 or judged == max_rows:
                        print(f"{log_label}: {judged}/{max_rows}", flush=True)
                except Exception as exc:
                    errors += 1
                    error_record = {
                        "model": model,
                        "verdict": "error",
                        "reason": f"{type(exc).__name__}: {str(exc)[:220]}",
                        "cache_key": key,
                        "cached": False,
                    }
                    if "prompt_version" in metadata_extra:
                        error_record["prompt_version"] = metadata_extra["prompt_version"]
                    row[judgment_key] = error_record

    return {
        **base_metadata(),
        "ran": judged > 0,
        "limit": limit,
        "workers": max(1, workers),
        "max_tokens": max_tokens,
        "judged_rows": judged,
        "error_rows": errors,
        "cache_path": str(cache_file),
        "litellm_cache": litellm_cache,
    }


def run_llm_judge(
    rows: list[dict[str, Any]],
    catalog: Catalog,
    *,
    out_dir: Path,
    model: str,
    top_k: int,
    limit: int,
    workers: int,
    max_tokens: int,
    cache_path: Path | None,
    include_state: bool,
    litellm_cache_mode: str,
    litellm_cache_dir: Path | None,
) -> dict[str, Any]:
    return run_llm_json_judge(
        rows,
        out_dir=out_dir,
        model=model,
        limit=limit,
        workers=workers,
        max_tokens=max_tokens,
        cache_path=cache_path,
        litellm_cache_mode=litellm_cache_mode,
        litellm_cache_dir=litellm_cache_dir,
        cache_filename="llm_judgments.jsonl",
        judgment_key="llm_judgment",
        log_label="LLM judge",
        warning_label="LLM judge",
        system_prompt="You are a strict but fair music recommendation judge. Return valid JSON only.",
        non_json_label="judge",
        cache_key_fn=lambda row: judge_cache_key(row, catalog, model, top_k, include_state),
        prompt_fn=lambda row: build_judge_prompt(
            row,
            catalog,
            top_k,
            include_state=include_state,
        ),
        normalize_fn=lambda raw, key, cached: normalize_judgment(
            raw,
            model=model,
            top_k=top_k,
            cache_key=key,
            cached=cached,
        ),
        metadata_extra={
            "top_k": top_k,
            "include_state": include_state,
        },
    )


def run_llm_explanation_judge(
    rows: list[dict[str, Any]],
    catalog: Catalog,
    *,
    out_dir: Path,
    model: str,
    limit: int,
    workers: int,
    max_tokens: int,
    cache_path: Path | None,
    litellm_cache_mode: str,
    litellm_cache_dir: Path | None,
) -> dict[str, Any]:
    return run_llm_json_judge(
        rows,
        out_dir=out_dir,
        model=model,
        limit=limit,
        workers=workers,
        max_tokens=max_tokens,
        cache_path=cache_path,
        litellm_cache_mode=litellm_cache_mode,
        litellm_cache_dir=litellm_cache_dir,
        cache_filename="llm_explanation_judgments.jsonl",
        judgment_key="llm_explanation_judgment",
        log_label="LLM explanation judge",
        warning_label="LLM explanation judge",
        system_prompt="You are a strict but fair music response-quality judge. Return valid JSON only.",
        non_json_label="explanation judge",
        cache_key_fn=lambda row: explanation_judge_cache_key(row, catalog, model),
        prompt_fn=lambda row: build_explanation_judge_prompt(row, catalog),
        normalize_fn=lambda raw, key, cached: normalize_explanation_judgment(
            raw,
            model=model,
            cache_key=key,
            cached=cached,
        ),
        metadata_extra={
            "prompt_version": EXPLANATION_JUDGE_PROMPT_VERSION,
        },
    )


def run_llm_state_judge(
    rows: list[dict[str, Any]],
    catalog: Catalog,
    *,
    out_dir: Path,
    model: str,
    limit: int,
    workers: int,
    max_tokens: int,
    cache_path: Path | None,
    litellm_cache_mode: str,
    litellm_cache_dir: Path | None,
) -> dict[str, Any]:
    state_rows = [row for row in rows if row.get("trace_available")]
    if not state_rows:
        return {
            "enabled": True,
            "ran": False,
            "model": model,
            "warning": "No trace rows were available, so no LLM state judge calls were made.",
            "label_free_only": False,
            "diagnostic_only": True,
            "prompt_version": STATE_JUDGE_PROMPT_VERSION,
            "litellm_cache": requested_litellm_cache_metadata(
                litellm_cache_mode,
                litellm_cache_dir,
            ),
        }
    return run_llm_json_judge(
        state_rows,
        out_dir=out_dir,
        model=model,
        limit=limit,
        workers=workers,
        max_tokens=max_tokens,
        cache_path=cache_path,
        litellm_cache_mode=litellm_cache_mode,
        litellm_cache_dir=litellm_cache_dir,
        cache_filename="llm_state_judgments.jsonl",
        judgment_key="llm_state_judgment",
        log_label="LLM state judge",
        warning_label="LLM state judge",
        system_prompt="You are a strict but fair music conversation state-auditor. Return valid JSON only.",
        non_json_label="state judge",
        cache_key_fn=lambda row: state_judge_cache_key(row, catalog, model),
        prompt_fn=lambda row: build_state_judge_prompt(row, catalog),
        normalize_fn=lambda raw, key, cached: normalize_state_judgment(
            raw,
            model=model,
            cache_key=key,
            cached=cached,
        ),
        metadata_extra={
            "prompt_version": STATE_JUDGE_PROMPT_VERSION,
            "diagnostic_only": True,
        },
        label_free_only=False,
    )


def get_rank(gold: str, preds: list[str]) -> int | None:
    try:
        return preds.index(gold) + 1
    except ValueError:
        return None


def ndcg_at(rank: int | None, k: int) -> float:
    if rank is None or rank > k:
        return 0.0
    return 1.0 / math.log2(rank + 1)


def metrics_for_row(gold: str | None, preds: list[str]) -> dict[str, Any]:
    if not gold:
        return {}
    rank = get_rank(gold, preds)
    return {
        "ground_truth_track_id": gold,
        "ground_truth_rank": rank,
        "hit@20": 1.0 if rank is not None and rank <= 20 else 0.0,
        "hit@100": 1.0 if rank is not None and rank <= 100 else 0.0,
        "ndcg@20": ndcg_at(rank, 20),
        "mrr": 0.0 if rank is None else 1.0 / rank,
    }


def classify_gaps(
    trace: dict[str, Any],
    terms: dict[str, Any],
    top_flags: list[str],
    any_flags: list[str],
    better_submitted: dict[str, Any] | None,
    better_pool: dict[str, Any] | None,
    row_metrics: dict[str, Any],
) -> list[str]:
    gaps = []
    extracted = trace.get("extracted_state") or {}
    has_structured_rejection = any(
        as_list(extracted.get(k)) for k in ["exclusions", "rejections", "explicit_rejections"]
    )
    if (terms["switch_requested"] or terms["different_album_requested"] or "no more" in norm(terms["latest_user_text"])) and not has_structured_rejection:
        gaps.append("state_gap")
    if top_flags or any_flags:
        if terms["rejected_artist_ids"] or terms["rejected_track_ids"]:
            gaps.append("compiler_filter_gap")
        if has_structured_rejection and any("rejected_name:" in f for f in any_flags) and not (
            terms["rejected_artist_ids"] or terms["rejected_track_ids"]
        ):
            gaps.append("resolver_gap")
        if better_submitted or better_pool:
            gaps.append("ranking_gap")
    if not better_submitted and not better_pool and (top_flags or any_flags):
        gaps.append("retrieval_gap")
    if row_metrics and row_metrics.get("hit@20") == 0.0:
        gaps.append("label_miss")
    if not gaps and (top_flags or any_flags):
        gaps.append("validity_gap")
    return list(dict.fromkeys(gaps))


def response_self_flags(response: str) -> bool:
    text = norm(response)
    return any(
        phrase in text
        for phrase in [
            "asked to avoid",
            "specifically wanted to avoid",
            "artist you ve specifically asked to avoid",
            "which you specifically asked to avoid",
            "i ll skip this one",
            "let me find something else",
        ]
    )


def audit_rows(
    predictions: list[dict[str, Any]],
    traces: dict[tuple[str, int], dict[str, Any]],
    ground_truth: dict[tuple[str, int], str],
    conversations: dict[str, dict[str, Any]],
    catalog: Catalog,
    max_candidate_pool: int,
    limit: int | None,
) -> list[dict[str, Any]]:
    audited = []
    for idx, row in enumerate(predictions):
        if limit is not None and idx >= limit:
            break
        sid = row["session_id"]
        turn = int(row["turn_number"])
        key = (sid, turn)
        preds = [str(x) for x in row.get("predicted_track_ids", [])]
        trace = traces.get(key, {})
        conversation = conversations.get(sid)
        terms = derive_audit_terms(row, trace, conversation, catalog)
        cf = get_candidate_fusion(trace)
        cf_rank = {tid: i + 1 for i, tid in enumerate(cf)}

        item_rows = []
        any_flags = []
        for rank, tid in enumerate(preds[:20], start=1):
            flags = violation_flags(tid, catalog, terms)
            any_flags.extend(flags)
            item_rows.append(
                {
                    "rank": rank,
                    "track": compact_meta(catalog, tid),
                    "candidate_fusion_rank": cf_rank.get(tid),
                    "fit_score": candidate_fit_score(tid, catalog, terms),
                    "flags": flags,
                    "status": "bad" if flags else "ok",
                }
            )

        row_metrics = metrics_for_row(ground_truth.get(key), preds)
        top_flags = item_rows[0]["flags"] if item_rows else []
        needs_alternative = bool(top_flags) or bool(any_flags) or (
            bool(row_metrics) and row_metrics.get("hit@20") == 0.0
        )
        better_submitted = (
            find_better_candidate(preds[:20], catalog, terms, cf_rank)
            if needs_alternative
            else None
        )
        pool_ids = cf[:max_candidate_pool]
        better_pool = (
            find_better_candidate(
                pool_ids,
                catalog,
                terms,
                cf_rank,
                exclude_ids=set(preds[:20]),
            )
            if needs_alternative and pool_ids
            else None
        )
        gaps = classify_gaps(
            trace,
            terms,
            top_flags,
            any_flags,
            better_submitted,
            better_pool,
            row_metrics,
        )
        if response_self_flags(str(row.get("predicted_response", ""))):
            gaps.append("response_self_flag")

        audited.append(
            {
                "index": idx,
                "session_id": sid,
                "user_id": row.get("user_id"),
                "user_profile": (conversation or {}).get("user_profile"),
                "turn_number": turn,
                "latest_user_text": terms["latest_user_text"],
                "conversation_goal": (conversation or {}).get("conversation_goal"),
                "conversation": (conversation or {}).get("conversations", []),
                "prediction_response": row.get("predicted_response", ""),
                "current_request_summary": terms["current_request_summary"],
                "intent_mode": trace.get("intent_mode"),
                "request_type": ((trace.get("extracted_state") or {}).get("current_request") or {}).get("request_type")
                if isinstance((trace.get("extracted_state") or {}).get("current_request"), dict)
                else None,
                "retrieval_profile": (trace.get("extracted_state") or {}).get("retrieval_profile"),
                "routing_tags": (trace.get("compiled_state") or {}).get("routing_tags"),
                "state_excerpt": {
                    "exclusions": (trace.get("extracted_state") or {}).get("exclusions"),
                    "rejections": (trace.get("extracted_state") or {}).get("rejections"),
                    "explicit_rejections": (trace.get("extracted_state") or {}).get("explicit_rejections"),
                    "facts": (trace.get("extracted_state") or {}).get("facts"),
                    "resolver": trace.get("resolver"),
                },
                "rejected_names": terms["rejected_names"],
                "avoid_names": terms["avoid_names"],
                "prior_artists": terms["prior_artists"],
                "positive_terms": terms["positive_terms"],
                "branch_names": branch_names(trace),
                "top1_flags": top_flags,
                "top20_flag_count": len(any_flags),
                "gaps": list(dict.fromkeys(gaps)),
                "items": item_rows,
                "better_submitted": better_submitted,
                "better_pool": better_pool,
                "metrics": row_metrics,
                "trace_available": bool(trace),
            }
        )
    return audited


def aggregate(audited: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    n = len(audited)
    gap_counter = Counter(g for row in audited for g in row["gaps"])
    branch_counter = Counter(b for row in audited for b in row.get("branch_names", []))
    req_counter = Counter(row.get("request_type") or "unknown" for row in audited)
    top1_flagged = sum(1 for row in audited if row["top1_flags"])
    top20_flagged = sum(1 for row in audited if row["top20_flag_count"] > 0)
    hard_top1_invalid = sum(
        1
        for row in audited
        if any(str(flag).startswith(("rejected_", "rejected_name:")) for flag in row["top1_flags"])
    )
    hard_top20_invalid = sum(
        1
        for row in audited
        if any(
            str(flag).startswith(("rejected_", "rejected_name:"))
            for item in row["items"]
            for flag in item["flags"]
        )
    )
    with_better_submitted = sum(1 for row in audited if row["better_submitted"])
    with_better_pool = sum(1 for row in audited if row["better_pool"])
    with_trace = sum(1 for row in audited if row["trace_available"])
    judge_counter = Counter(
        str(row.get("llm_judgment", {}).get("verdict"))
        for row in audited
        if row.get("llm_judgment") and row.get("llm_judgment", {}).get("verdict") != "error"
    )
    judge_errors = sum(
        1 for row in audited if row.get("llm_judgment", {}).get("verdict") == "error"
    )
    explanation_judge_counter = Counter(
        str(row.get("llm_explanation_judgment", {}).get("verdict"))
        for row in audited
        if row.get("llm_explanation_judgment")
        and row.get("llm_explanation_judgment", {}).get("verdict") != "error"
    )
    explanation_judge_errors = sum(
        1
        for row in audited
        if row.get("llm_explanation_judgment", {}).get("verdict") == "error"
    )
    state_judge_counter = Counter(
        str(row.get("llm_state_judgment", {}).get("verdict"))
        for row in audited
        if row.get("llm_state_judgment")
        and row.get("llm_state_judgment", {}).get("verdict") != "error"
    )
    state_judge_errors = sum(
        1 for row in audited if row.get("llm_state_judgment", {}).get("verdict") == "error"
    )

    label_rows = [row for row in audited if row["metrics"]]
    label_metrics = None
    if label_rows:
        label_metrics = {
            "n_labeled": len(label_rows),
            "ndcg@20": sum(row["metrics"]["ndcg@20"] for row in label_rows) / len(label_rows),
            "hit@20": sum(row["metrics"]["hit@20"] for row in label_rows) / len(label_rows),
            "hit@100": sum(row["metrics"]["hit@100"] for row in label_rows) / len(label_rows),
            "mrr": sum(row["metrics"]["mrr"] for row in label_rows) / len(label_rows),
            "miss_top20": sum(1 for row in label_rows if row["metrics"]["hit@20"] == 0.0),
        }

    return {
        "n_rows": n,
        "n_with_trace": with_trace,
        "top1_flagged": top1_flagged,
        "top20_flagged_rows": top20_flagged,
        "hard_top1_invalid": hard_top1_invalid,
        "hard_top20_invalid_rows": hard_top20_invalid,
        # Backward-compatible aliases for early smoke outputs.
        "top1_invalid": top1_flagged,
        "top20_invalid_rows": top20_flagged,
        "with_better_submitted": with_better_submitted,
        "with_better_pool": with_better_pool,
        "gap_counts": dict(gap_counter.most_common()),
        "request_type_counts": dict(req_counter.most_common()),
        "branch_counts": dict(branch_counter.most_common()),
        "label_metrics": label_metrics,
        "llm_judge_metrics": {
            "n_judged": sum(judge_counter.values()),
            "verdict_counts": dict(judge_counter.most_common()),
            "weak_or_bad": judge_counter.get("weak", 0) + judge_counter.get("bad", 0),
            "error_rows": judge_errors,
        },
        "llm_explanation_judge_metrics": {
            "n_judged": sum(explanation_judge_counter.values()),
            "verdict_counts": dict(explanation_judge_counter.most_common()),
            "weak_or_bad": explanation_judge_counter.get("weak", 0)
            + explanation_judge_counter.get("bad", 0),
            "error_rows": explanation_judge_errors,
        },
        "llm_state_judge_metrics": {
            "n_judged": sum(state_judge_counter.values()),
            "verdict_counts": dict(state_judge_counter.most_common()),
            "partial_or_bad": state_judge_counter.get("partial", 0)
            + state_judge_counter.get("bad", 0),
            "error_rows": state_judge_errors,
        },
        "metadata": metadata,
    }


def human_flag(flag: str) -> str:
    if flag == "rejected_track_id":
        return "the track was explicitly rejected"
    if flag == "rejected_artist_id":
        return "the artist was explicitly rejected"
    if flag.startswith("rejected_name:"):
        return f"it matches the hard rejected name '{flag.split(':', 1)[1]}'"
    if flag.startswith("avoid_name:"):
        return f"it repeats something the user was trying to move away from: '{flag.split(':', 1)[1]}'"
    if flag.startswith("prior_artist_after_switch:"):
        return f"the user asked to branch out, but it repeats prior artist '{flag.split(':', 1)[1]}'"
    if flag.startswith("prior_album_after_switch:"):
        return f"the user asked for a different source/album, but it repeats '{flag.split(':', 1)[1]}'"
    return flag.replace("_", " ")


def gap_plain_text(gap: str) -> str:
    mapping = {
        "state_gap": "State gap: the conversation implies a constraint, but structured state did not capture it strongly enough.",
        "resolver_gap": "Resolver gap: state had a constraint, but artist/album identity matching was incomplete.",
        "compiler_filter_gap": "Compiler/filter gap: the rejected item was known but still survived into the final list.",
        "ranking_gap": "Ranking gap: a cleaner alternative existed, but final ordering chose a weaker or invalid item.",
        "retrieval_gap": "Retrieval gap: the inspected list/pool did not contain a clean enough alternative.",
        "label_miss": "Label miss: on devset, the ground-truth track was not in the submitted top 20.",
        "response_self_flag": "Response self-flag: the generated text itself says the chosen track should be avoided.",
        "validity_gap": "Validity gap: the row has a rule/intent flag that needs review.",
    }
    return mapping.get(gap, gap.replace("_", " "))


def candidate_reason(candidate: dict[str, Any] | None, row: dict[str, Any]) -> str:
    if not candidate:
        return ""
    track = candidate["track"]
    bits = []
    flags = row.get("top1_flags") or []
    if flags:
        bits.append("it avoids the top pick's rule violation")
    elif row.get("metrics", {}).get("hit@20") == 0.0:
        bits.append("it is the cleanest available fallback found by the heuristic")
    if candidate.get("candidate_fusion_rank"):
        bits.append(f"fusion stage already ranked it #{candidate['candidate_fusion_rank']}")
    if track.get("popularity", 0) > 0:
        bits.append(f"catalog popularity is {track['popularity']:.0f}")
    positive_terms = row.get("positive_terms") or []
    text = norm(" ".join([track.get("track_name", ""), track.get("artist_name", ""), track.get("album_name", ""), " ".join(track.get("tags", []))]))
    matches = [term for term in positive_terms if term in text][:5]
    if matches:
        bits.append("metadata/tags match: " + ", ".join(matches))
    return "; ".join(bits) + "."


def row_explanation(row: dict[str, Any]) -> dict[str, str]:
    first = row["items"][0]["track"] if row.get("items") else {}
    top_name = first.get("track_name") or "the top recommendation"
    artist = first.get("artist_name")
    top_label = f"{top_name} by {artist}" if artist else top_name
    metrics = row.get("metrics") or {}
    flags = row.get("top1_flags") or []
    gaps = row.get("gaps") or []
    judgment = row.get("llm_judgment") or {}
    judge_verdict = str(judgment.get("verdict") or "")

    if flags:
        verdict = "Likely wrong"
        reason = f"The top recommendation is {top_label}, but " + "; ".join(human_flag(f) for f in flags[:3]) + "."
    elif metrics:
        rank = metrics.get("ground_truth_rank")
        if rank and rank <= 20:
            verdict = "Looks right by devset label"
            reason = f"The provided label track is in the submitted top 20 at rank {rank}, so this row receives nDCG credit."
        else:
            verdict = "Wrong by provided label"
            reason = "The provided label track is not in the submitted top 20, so this row is a label miss."
    elif judge_verdict in {"weak", "bad"}:
        verdict = f"Recommendation fit: {verdict_label('recommendation', judge_verdict)}"
        reason = judgment.get("reason") or "The label-free judge thought the top recommendation was weak."
    elif judge_verdict in {"good", "acceptable"}:
        verdict = f"Recommendation fit: {verdict_label('recommendation', judge_verdict)}"
        reason = judgment.get("reason") or "The label-free judge did not find an obvious problem."
    elif gaps:
        verdict = "Needs review"
        reason = "No hidden label is available, but the audit found a conversation/state risk: " + gap_plain_text(gaps[0])
    else:
        verdict = "No obvious issue"
        reason = "No hard rejection leak, branch-out violation, or label miss was detected by the audit heuristics."

    if row.get("better_submitted"):
        better = row["better_submitted"]["track"]
        better_text = f"From the submitted list, {better['track_name']} by {better['artist_name']} looks better because {candidate_reason(row['better_submitted'], row)}"
    elif row.get("better_pool"):
        better = row["better_pool"]["track"]
        better_text = f"From the candidate pool, {better['track_name']} by {better['artist_name']} looks better because {candidate_reason(row['better_pool'], row)}"
    elif not row.get("trace_available"):
        better_text = "No candidate-pool comparison is possible because this report was generated without a trace."
    elif not gaps and metrics.get("hit@20") == 1.0:
        better_text = "No alternative is needed for this row."
    else:
        better_text = "The audit did not find a clearly better clean alternative in the inspected list/pool."

    root = "Likely cause: "
    if "state_gap" in gaps:
        root += "state extraction/structuring missed the user constraint."
    elif "compiler_filter_gap" in gaps:
        root += "compiler/final filtering let a known rejection through."
    elif "resolver_gap" in gaps:
        root += "resolver identity matching missed an artist/album variant."
    elif "ranking_gap" in gaps:
        root += "final ordering placed a weaker/invalid item over clean candidates."
    elif "retrieval_gap" in gaps:
        root += "retrieval did not surface a clean enough alternative."
    elif "label_miss" in gaps:
        root += "the submitted ranking missed the known devset target."
    else:
        root += "no specific pipeline gap was identified."

    judge = ""
    if judgment:
        best_rank = judgment.get("best_rank")
        top_valid = bool(judgment.get("top_rank_valid"))
        if not best_rank:
            best_text = " No valid submitted track was identified."
        elif not top_valid and int(best_rank) == 1:
            best_text = " Submitted rank 1 was judged invalid; no better valid submitted rank was identified."
        else:
            best_text = f" Best shown candidate: rank {best_rank}."
        if judge_verdict == "error":
            judge = f"Recommendation fit judge failed: {judgment.get('reason', '')}"
        else:
            judge = (
                f"Recommendation fit ({judgment.get('model', 'model unknown')}): "
                f"{verdict_label('recommendation', judge_verdict)}."
                f"{best_text} {judgment.get('reason', '')}"
            ).strip()

    return {"verdict": verdict, "reason": reason, "better": better_text, "root": root, "judge": judge}


def render_summary(agg: dict[str, Any]) -> str:
    n = agg["n_rows"] or 1
    label = agg.get("label_metrics")
    bullets = []
    if label:
        bullets.append(
            f"This is a label-aware audit because a label file was supplied: {label['n_labeled']} rows have labels, Hit@20 is {label['hit@20']:.3f}, and nDCG@20 is {label['ndcg@20']:.3f}."
        )
        bullets.append(
            f"{label['miss_top20']} labeled rows miss the ground-truth track in the submitted top 20."
        )
    else:
        bullets.append(
            "This is a label-free audit: it cannot know hidden leaderboard credit, so it focuses on conversation validity and pipeline gap signals."
        )
    judge_meta = (agg.get("metadata") or {}).get("llm_judge") or {}
    judge_metrics = agg.get("llm_judge_metrics") or {}
    explanation_judge_meta = (agg.get("metadata") or {}).get("llm_explanation_judge") or {}
    explanation_judge_metrics = agg.get("llm_explanation_judge_metrics") or {}
    state_judge_meta = (agg.get("metadata") or {}).get("llm_state_judge") or {}
    state_judge_metrics = agg.get("llm_state_judge_metrics") or {}
    if judge_meta.get("skipped_reason"):
        bullets.append(f"Recommendation fit judge was skipped: {judge_meta['skipped_reason']}")
    elif judge_meta.get("warning"):
        bullets.append(f"Recommendation fit judge warning: {judge_meta['warning']}")
    elif judge_metrics.get("n_judged"):
        counts = judge_metrics.get("verdict_counts") or {}
        counts_text = verdict_counts_text("recommendation", counts)
        bullets.append(
            f"Recommendation fit reviewed {judge_metrics['n_judged']} label-free rows; weak/bad-fit rows={judge_metrics['weak_or_bad']} ({counts_text})."
        )
    if explanation_judge_meta.get("skipped_reason"):
        bullets.append(f"Response quality judge was skipped: {explanation_judge_meta['skipped_reason']}")
    elif explanation_judge_meta.get("warning"):
        bullets.append(f"Response quality judge warning: {explanation_judge_meta['warning']}")
    elif explanation_judge_metrics.get("n_judged"):
        counts = explanation_judge_metrics.get("verdict_counts") or {}
        counts_text = verdict_counts_text("explanation", counts)
        bullets.append(
            f"Response quality reviewed {explanation_judge_metrics['n_judged']} label-free rows; thin/misleading responses={explanation_judge_metrics['weak_or_bad']} ({counts_text})."
        )
    if state_judge_meta.get("warning"):
        bullets.append(f"State accuracy judge warning: {state_judge_meta['warning']}")
    elif state_judge_metrics.get("n_judged"):
        counts = state_judge_metrics.get("verdict_counts") or {}
        counts_text = verdict_counts_text("state", counts)
        bullets.append(
            f"State accuracy reviewed {state_judge_metrics['n_judged']} trace-backed rows; partial/inaccurate state rows={state_judge_metrics['partial_or_bad']} ({counts_text})."
        )
    bullets.append(
        f"{agg['hard_top1_invalid']} rows ({agg['hard_top1_invalid'] / n:.1%}) have a hard top-1 rejection leak; these are the strongest proven-bad cases."
    )
    bullets.append(
        f"{agg['top1_flagged']} rows ({agg['top1_flagged'] / n:.1%}) have a top-1 risk flag, including softer branch-out/repetition issues."
    )
    if agg["n_with_trace"] < agg["n_rows"]:
        bullets.append(
            f"Only {agg['n_with_trace']} of {agg['n_rows']} rows include trace data, so candidate-pool and state/compiler diagnosis is unavailable for the rest."
        )
    if agg["gap_counts"]:
        top_gaps = ", ".join(f"{k}={v}" for k, v in list(agg["gap_counts"].items())[:4])
        bullets.append(f"Most common gap labels: {top_gaps}.")
    bullets.append(
        "Read each row as: latest user request -> top recommendation -> why flagged or credited -> better candidate if one can be inferred."
    )
    return "\n".join(f"<li>{escape(b)}</li>" for b in bullets)


def esc_json(value: Any) -> str:
    return escape(json.dumps(value, ensure_ascii=False, indent=2))


def render_item_table(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        track = item["track"]
        flags = item["flags"]
        cls = "bad" if flags else "ok"
        flags_text = ", ".join(flags) if flags else ""
        tags = ", ".join(track.get("tags", [])[:6])
        rows.append(
            f"""
            <tr class="{cls}">
              <td>{item['rank']}</td>
              <td><strong>{escape(track['track_name'])}</strong><br><span>{escape(track['artist_name'])}</span></td>
              <td>{escape(track['album_name'])}</td>
              <td>{track.get('popularity', 0):.0f}</td>
              <td>{escape(str(item.get('candidate_fusion_rank') or ''))}</td>
              <td>{item.get('fit_score', 0):.2f}</td>
              <td>{escape(flags_text)}<br><small>{escape(tags)}</small></td>
            </tr>
            """
        )
    return "\n".join(rows)


def render_empty_candidate(message: str) -> str:
    return f'<div class="empty">{escape(message)}</div>'


def render_candidate(candidate: dict[str, Any] | None, empty_message: str) -> str:
    if not candidate:
        return render_empty_candidate(empty_message)
    track = candidate["track"]
    tags = ", ".join(track.get("tags", [])[:8])
    cf = candidate.get("candidate_fusion_rank")
    cf_text = f"fusion rank {cf}" if cf else "not in fusion trace"
    return f"""
    <div class="candidate">
      <strong>{escape(track['track_name'])}</strong>
      <span>{escape(track['artist_name'])}</span>
      <small>{escape(track['album_name'])} · submitted/pool rank {candidate.get('rank')} · {escape(cf_text)} · fit {candidate.get('fit_score', 0):.2f}</small>
      <em>{escape(tags)}</em>
    </div>
    """


def render_llm_choice(row: dict[str, Any]) -> str:
    judgment = row.get("llm_judgment") or {}
    verdict = str(judgment.get("verdict") or "")
    if not judgment or verdict == "error":
        return ""
    best_rank = judgment.get("best_rank")
    try:
        best_rank = int(best_rank) if best_rank is not None else None
    except (TypeError, ValueError):
        best_rank = None
    items = row.get("items") or []
    if best_rank is not None and (best_rank < 1 or best_rank > len(items)):
        best_rank = None

    top_valid = bool(judgment.get("top_rank_valid"))
    if best_rank is None:
        track = {"track_name": "No valid submitted track", "artist_name": "", "album_name": ""}
        tags = ""
        action = "no valid submitted recommendation"
        rank_text = "none"
    else:
        item = items[best_rank - 1]
        track = item["track"]
        tags = ", ".join(track.get("tags", [])[:8])
        rank_text = f"#{best_rank}"
        if top_valid and best_rank == 1 and verdict in {"good", "acceptable"}:
            action = "accepted submitted rank #1"
        elif not top_valid and best_rank == 1:
            action = "top recommendation judged invalid; no better submitted rank chosen"
        elif not top_valid:
            action = f"top recommendation judged invalid; preferred submitted rank #{best_rank}"
        else:
            action = f"preferred submitted rank #{best_rank}"
    model = judgment.get("model") or "external judge"
    top_k = (row.get("llm_judgment") or {}).get("top_k") or ""
    top_k_text = f" · judged top {top_k}" if top_k else ""
    reason = judgment.get("reason") or ""
    return f"""
    <div class="llm-choice {escape(verdict)}">
      <div>
        <h3>Recommendation Fit</h3>
        <p><b>{escape(action)}:</b> {escape(track['track_name'])}{' by ' + escape(track['artist_name']) if track.get('artist_name') else ''}</p>
        <p>{escape(reason)}</p>
        <small>{escape(str(model))}{escape(top_k_text)} · {escape(verdict_label('recommendation', verdict))}</small>
      </div>
      <div class="choice-meta">
        <strong>{escape(rank_text)}</strong>
        <span>{escape(track['album_name'])}</span>
        <em>{escape(tags)}</em>
      </div>
    </div>
    """


def render_llm_explanation_judge(row: dict[str, Any]) -> str:
    judgment = row.get("llm_explanation_judgment") or {}
    verdict = str(judgment.get("verdict") or "")
    if not judgment or verdict == "error":
        return ""
    checks = [
        ("grounds top rec", judgment.get("grounds_top_recommendation", judgment.get("faithful_to_recommendation"))),
        ("justifies fit", judgment.get("justifies_fit")),
        ("conversation relevant", judgment.get("conversation_relevant", judgment.get("answers_latest_request"))),
        ("metadata hallucination", judgment.get("metadata_hallucination")),
        ("constraint violation", judgment.get("constraint_violation")),
    ]
    check_text = " · ".join(
        f"{name}: {'yes' if bool(value) else 'no'}" for name, value in checks
    )
    reason = judgment.get("reason") or ""
    model = judgment.get("model") or "external judge"
    return f"""
    <div class="llm-choice {escape(verdict)}">
      <div>
        <h3>Response Quality</h3>
        <p><b>response quality:</b> {escape(verdict_label('explanation', verdict))}</p>
        <p>{escape(reason)}</p>
        <small>{escape(str(model))} · prompt {escape(str(judgment.get('prompt_version') or ''))}</small>
      </div>
      <div class="choice-meta">
        <strong>{escape(verdict_label('explanation', verdict))}</strong>
        <span>{escape(check_text)}</span>
      </div>
    </div>
    """


def render_llm_state_judge(row: dict[str, Any]) -> str:
    judgment = row.get("llm_state_judgment") or {}
    verdict = str(judgment.get("verdict") or "")
    if not judgment or verdict == "error":
        return ""
    missing = judgment.get("missing_constraints") or []
    stale = judgment.get("extra_or_stale_state") or []
    checks = [
        ("state accurate", judgment.get("state_accurate")),
        ("compiled risk", judgment.get("compiled_state_risk")),
    ]
    check_text = " · ".join(
        f"{name}: {'yes' if bool(value) else 'no'}" for name, value in checks
    )
    missing_text = "; ".join(str(x) for x in missing) or "none called out"
    stale_text = "; ".join(str(x) for x in stale) or "none called out"
    reason = judgment.get("reason") or ""
    model = judgment.get("model") or "external judge"
    return f"""
    <div class="llm-choice {escape(verdict)}">
      <div>
        <h3>State Accuracy</h3>
        <p><b>state accuracy:</b> {escape(verdict_label('state', verdict))}</p>
        <p>{escape(reason)}</p>
        <p><b>missing:</b> {escape(missing_text)}</p>
        <p><b>extra/stale:</b> {escape(stale_text)}</p>
        <small>{escape(str(model))} · prompt {escape(str(judgment.get('prompt_version') or ''))}</small>
      </div>
      <div class="choice-meta">
        <strong>{escape(verdict_label('state', verdict))}</strong>
        <span>{escape(check_text)}</span>
      </div>
    </div>
    """


def row_search_text(row: dict[str, Any]) -> str:
    parts: list[str] = [
        row.get("session_id", ""),
        row.get("user_id", ""),
        row.get("latest_user_text", ""),
        row.get("conversation_goal", ""),
        row.get("prediction_response", ""),
        row.get("current_request_summary", ""),
        row.get("intent_mode", ""),
        row.get("request_type", ""),
        " ".join(row.get("gaps") or []),
        " ".join(row.get("branch_names") or []),
    ]
    for name in ["rejected_names", "avoid_names", "positive_terms"]:
        parts.append(" ".join(str(x) for x in row.get(name) or []))
    for item in row.get("items") or []:
        track = item.get("track") or {}
        parts.extend(
            [
                track.get("track_id", ""),
                track.get("track_name", ""),
                track.get("artist_name", ""),
                track.get("album_name", ""),
                " ".join(track.get("tags") or []),
                " ".join(item.get("flags") or []),
            ]
        )
    for key in ["better_submitted", "better_pool"]:
        candidate = row.get(key) or {}
        track = candidate.get("track") or {}
        parts.extend(
            [
                track.get("track_name", ""),
                track.get("artist_name", ""),
                track.get("album_name", ""),
            ]
        )
    return norm(" ".join(str(part or "") for part in parts))


def render_conversation(conversation: list[dict[str, Any]], catalog: Catalog) -> str:
    if not conversation:
        return '<div class="empty">Conversation text unavailable.</div>'
    chunks = []
    for turn in conversation:
        role = str(turn.get("role", ""))
        content = str(turn.get("content", ""))
        if role == "music":
            content = track_label(catalog, content)
        chunks.append(
            f"""
            <div class="turn {escape(role)}">
              <b>{escape(role)} {escape(str(turn.get('turn_number', '')))}</b>
              <p>{escape(content)}</p>
            </div>
            """
        )
    return "\n".join(chunks)


def submitted_empty_message(row: dict[str, Any]) -> str:
    if not row.get("gaps"):
        return "No alternative needed for this row."
    if row.get("metrics", {}).get("hit@20") == 0.0:
        return "No clean submitted-list alternative found for this label miss."
    return "No clean submitted-list alternative found."


def pool_empty_message(row: dict[str, Any]) -> str:
    if not row.get("trace_available"):
        return "Candidate pool unavailable because no trace was supplied."
    if not row.get("gaps"):
        return "No alternative needed for this row."
    return "No clean candidate-pool alternative found in the inspected pool."


def render_html(audit: dict[str, Any], catalog: Catalog) -> str:
    agg = audit["aggregate"]
    rows = audit["rows"]
    label = agg.get("label_metrics")
    run_cards = [
        ("Rows", agg["n_rows"]),
        ("Trace Rows", agg["n_with_trace"]),
    ]
    gap_cards = [
        ("Flagged Top1", agg["top1_flagged"]),
        ("Flagged Top20 Rows", agg["top20_flagged_rows"]),
        ("Hard Top1 Leaks", agg["hard_top1_invalid"]),
        ("Hard Top20 Leaks", agg["hard_top20_invalid_rows"]),
        ("Better In List", agg["with_better_submitted"]),
        ("Better In Pool", agg["with_better_pool"]),
    ]
    judge_cards = []
    if label:
        run_cards += [
            ("nDCG@20", f"{label['ndcg@20']:.4f}"),
            ("Hit@20", f"{label['hit@20']:.4f}"),
            ("MRR", f"{label['mrr']:.4f}"),
        ]
    else:
        run_cards.append(("Labels", "not available"))
    judge_metrics = agg.get("llm_judge_metrics") or {}
    judge_meta = agg["metadata"].get("llm_judge") or {}
    explanation_judge_metrics = agg.get("llm_explanation_judge_metrics") or {}
    explanation_judge_meta = agg["metadata"].get("llm_explanation_judge") or {}
    state_judge_metrics = agg.get("llm_state_judge_metrics") or {}
    state_judge_meta = agg["metadata"].get("llm_state_judge") or {}
    coverage_lines = []
    issue_lines = []
    issue_values = []
    if judge_metrics.get("n_judged"):
        coverage_lines.append(f"Fit {judge_metrics['n_judged']}/{agg['n_rows']}")
        issue_lines.append(f"Weak/bad fits {judge_metrics['weak_or_bad']}")
        issue_values.append(str(judge_metrics["weak_or_bad"]))
    elif judge_meta.get("enabled"):
        coverage_lines.append("Fit skipped")
    if explanation_judge_metrics.get("n_judged"):
        coverage_lines.append(f"Response {explanation_judge_metrics['n_judged']}/{agg['n_rows']}")
        issue_lines.append(f"Thin/misleading {explanation_judge_metrics['weak_or_bad']}")
        issue_values.append(str(explanation_judge_metrics["weak_or_bad"]))
    elif explanation_judge_meta.get("enabled"):
        coverage_lines.append("Response skipped")
    if state_judge_metrics.get("n_judged"):
        coverage_lines.append(f"State {state_judge_metrics['n_judged']}/{agg['n_rows']}")
        issue_lines.append(f"Partial/inaccurate state {state_judge_metrics['partial_or_bad']}")
        issue_values.append(str(state_judge_metrics["partial_or_bad"]))
    elif state_judge_meta.get("enabled"):
        coverage_lines.append("State skipped")
    if coverage_lines:
        judged_counts = [
            safe_float(metrics.get("n_judged"), 0)
            for metrics in [
                judge_metrics,
                explanation_judge_metrics,
                state_judge_metrics,
            ]
            if metrics.get("n_judged")
        ]
        coverage_value = (
            f"{int(min(judged_counts))}/{agg['n_rows']}"
            if judged_counts and len(set(judged_counts)) == 1
            else "mixed"
        )
        judge_cards.append(("Judge Coverage", coverage_value, " · ".join(coverage_lines)))
    if issue_lines:
        judge_cards.append(("Judge Issues", " / ".join(issue_values), " · ".join(issue_lines)))
    leaderboard = agg["metadata"].get("leaderboard_metadata")
    if leaderboard:
        for k, v in leaderboard.items():
            run_cards.append((str(k), v))

    def card_tone(card_label: str) -> str:
        lower = card_label.lower()
        if (
            "hard" in lower
            or "weak/bad" in lower
            or "partial/bad" in lower
            or "thin/misleading" in lower
            or "inaccurate" in lower
            or "issues" in lower
        ):
            return "danger"
        if "flagged" in lower or "better" in lower:
            return "warn"
        if lower in {
            "ndcg@20",
            "hit@20",
            "mrr",
            "fit judged",
            "responses judged",
            "state judged",
            "judge coverage",
            "rows",
            "trace rows",
        }:
            return "good"
        return "neutral"

    def render_card_grid(cards: list[tuple[Any, ...]]) -> str:
        return "\n".join(
            (
                f'<div class="card {card_tone(str(card[0]))}">'
                f'<span>{escape(str(card[0]))}</span>'
                f'<strong>{escape(str(card[1]))}</strong>'
                f"{f'<small>{escape(str(card[2]))}</small>' if len(card) > 2 and card[2] else ''}"
                "</div>"
            )
            for card in cards
        )

    metric_groups = [
        ("Run Coverage", run_cards, "Rows, trace availability, labels, and leaderboard metadata."),
        ("Validity And Gaps", gap_cards, "Hard leaks, broader risk flags, and heuristic alternatives."),
    ]
    if judge_cards:
        metric_groups.append(
            ("Judge Evaluations", judge_cards, "Recommendation fit, response quality, and state accuracy.")
        )
    metric_group_html = "\n".join(
        f"""
        <details class="metric-group" open>
          <summary><span>{escape(title)}</span><small>{escape(description)}</small></summary>
          <div class="cards">{render_card_grid(cards)}</div>
        </details>
        """
        for title, cards, description in metric_groups
    )
    gap_pills = "\n".join(
        f'<button class="pill" data-gap="{escape(k)}">{escape(k)} <b>{v}</b></button>'
        for k, v in agg["gap_counts"].items()
    )
    if not gap_pills:
        gap_pills = '<span class="muted">No gap flags.</span>'
    llm_counts = judge_metrics.get("verdict_counts") or {}
    llm_order = ["bad", "weak", "acceptable", "good"]
    if llm_counts:
        llm_filter_html = """
	    <select id="llmFilter" aria-label="LLM label filter">
	      <option value="">all recommendation-fit labels</option>
	      {options}
	    </select>
        """.format(
            options="\n".join(
                f'<option value="{escape(label)}">{escape(verdict_label("recommendation", label))} ({llm_counts[label]})</option>'
                for label in llm_order
                if llm_counts.get(label)
            )
        )
        llm_pills = """
        <section class="controls label-controls">
          <span class="control-label">Recommendation fit</span>
          {pills}
        </section>
        """.format(
            pills="\n".join(
                f'<button class="pill llm-pill {escape(label)}" data-llm="{escape(label)}">{escape(verdict_label("recommendation", label))} <b>{llm_counts[label]}</b></button>'
                for label in llm_order
                if llm_counts.get(label)
            )
        )
    else:
        llm_filter_html = '<select id="llmFilter" aria-label="Recommendation fit filter" disabled><option value="">Recommendation fit not run</option></select>'
        llm_pills = ""
    explanation_counts = explanation_judge_metrics.get("verdict_counts") or {}
    if explanation_counts:
        explanation_filter_html = """
	    <select id="explanationFilter" aria-label="Explanation label filter">
	      <option value="">all response-quality labels</option>
	      {options}
	    </select>
        """.format(
            options="\n".join(
                f'<option value="{escape(label)}">{escape(verdict_label("explanation", label))} ({explanation_counts[label]})</option>'
                for label in llm_order
                if explanation_counts.get(label)
            )
        )
        explanation_pills = """
        <section class="controls label-controls">
          <span class="control-label">Response quality</span>
          {pills}
        </section>
        """.format(
            pills="\n".join(
                f'<button class="pill explanation-pill {escape(label)}" data-explanation="{escape(label)}">{escape(verdict_label("explanation", label))} <b>{explanation_counts[label]}</b></button>'
                for label in llm_order
                if explanation_counts.get(label)
            )
        )
    else:
        explanation_filter_html = '<select id="explanationFilter" aria-label="Response quality filter" disabled><option value="">Response quality not run</option></select>'
        explanation_pills = ""
    state_counts = state_judge_metrics.get("verdict_counts") or {}
    state_order = ["bad", "partial", "good"]
    if state_counts:
        state_filter_html = """
	    <select id="stateFilter" aria-label="State label filter">
	      <option value="">all state-accuracy labels</option>
	      {options}
	    </select>
        """.format(
            options="\n".join(
                f'<option value="{escape(label)}">{escape(verdict_label("state", label))} ({state_counts[label]})</option>'
                for label in state_order
                if state_counts.get(label)
            )
        )
        state_pills = """
        <section class="controls label-controls">
          <span class="control-label">State accuracy</span>
          {pills}
        </section>
        """.format(
            pills="\n".join(
                f'<button class="pill state-pill {escape(label)}" data-state="{escape(label)}">{escape(verdict_label("state", label))} <b>{state_counts[label]}</b></button>'
                for label in state_order
                if state_counts.get(label)
            )
        )
    else:
        state_filter_html = '<select id="stateFilter" aria-label="State accuracy filter" disabled><option value="">State accuracy not run</option></select>'
        state_pills = ""

    row_cards = []
    for row in rows:
        first = row["items"][0]["track"] if row["items"] else {"track_name": "", "artist_name": ""}
        judge_verdict = str(row.get("llm_judgment", {}).get("verdict") or "")
        explanation_verdict = str(row.get("llm_explanation_judgment", {}).get("verdict") or "")
        state_verdict = str(row.get("llm_state_judgment", {}).get("verdict") or "")
        status = "bad" if row["top1_flags"] else (
            "warn"
            if row["gaps"]
            or judge_verdict in {"weak", "bad"}
            or explanation_verdict in {"weak", "bad"}
            or state_verdict in {"partial", "bad"}
            else "ok"
        )
        gap_attr = " ".join(row["gaps"])
        expl = row_explanation(row)
        metric_text = ""
        if row["metrics"]:
            rank = row["metrics"].get("ground_truth_rank")
            metric_text = f"GT rank: {rank if rank else 'miss'} · nDCG@20 {row['metrics']['ndcg@20']:.3f}"
        else:
            metric_text = "label-free"
        if judge_verdict and judge_verdict != "error":
            metric_text += f" · fit {verdict_label('recommendation', judge_verdict)}"
        if explanation_verdict and explanation_verdict != "error":
            metric_text += f" · response {verdict_label('explanation', explanation_verdict)}"
        if state_verdict and state_verdict != "error":
            metric_text += f" · state {verdict_label('state', state_verdict)}"
        status_label = "hard flag" if row["top1_flags"] else (
            "review"
            if row["gaps"]
            or judge_verdict in {"weak", "bad"}
            or explanation_verdict in {"weak", "bad"}
            or state_verdict in {"partial", "bad"}
            else "clear"
        )
        judge_badge = (
            f'<span class="badge judge {escape(judge_verdict)}">FIT {escape(verdict_label("recommendation", judge_verdict))}</span>'
            if judge_verdict and judge_verdict != "error"
            else ""
        )
        explanation_badge = (
            f'<span class="badge judge {escape(explanation_verdict)}">RESPONSE {escape(verdict_label("explanation", explanation_verdict))}</span>'
            if explanation_verdict and explanation_verdict != "error"
            else ""
        )
        state_badge = (
            f'<span class="badge judge {escape(state_verdict)}">STATE {escape(verdict_label("state", state_verdict))}</span>'
            if state_verdict and state_verdict != "error"
            else ""
        )
        row_cards.append(
            f"""
            <section class="row-card {status}" data-gaps="{escape(gap_attr)}" data-llm="{escape(judge_verdict)}" data-explanation="{escape(explanation_verdict)}" data-state="{escape(state_verdict)}" data-search="{escape(row_search_text(row))}">
              <header>
                <div>
                  <div class="row-kicker">
                    <span class="badge {status}">{escape(status_label)}</span>
                    {judge_badge}
                    {explanation_badge}
                    {state_badge}
                    <span>#{row['index']} · turn {row['turn_number']} · {escape(row['session_id'][:8])}</span>
                  </div>
                  <p>{escape(row['latest_user_text'][:260])}</p>
                </div>
                <div class="status">
                  <strong>{escape(first.get('track_name', ''))}</strong>
                  <span>{escape(first.get('artist_name', ''))}</span>
                  <small>{escape(metric_text)}</small>
                </div>
              </header>
              <div class="chips">
                {''.join(f'<span>{escape(g)}</span>' for g in row['gaps']) or '<span>no gap flag</span>'}
              </div>
              <details>
                <summary>Open row audit</summary>
                <div class="explain">
                  <h3>{escape(expl['verdict'])}</h3>
	                  <p>{escape(expl['reason'])}</p>
	                  <p>{escape(expl['better'])}</p>
	                  <p>{escape(expl['root'])}</p>
	                  {f"<p>{escape(expl['judge'])}</p>" if expl.get('judge') else ""}
	                </div>
                {render_llm_choice(row)}
                {render_llm_explanation_judge(row)}
                {render_llm_state_judge(row)}
                <div class="grid">
                  <div>
                    <h3>Conversation</h3>
                    {render_conversation(row['conversation'], catalog)}
                  </div>
                  <div>
                    <h3>State</h3>
                    <p><b>Current request:</b> {escape(str(row.get('current_request_summary') or ''))}</p>
                    <p><b>Hard rejected names:</b> {escape(', '.join(row.get('rejected_names') or []))}</p>
                    <p><b>Soft avoid names:</b> {escape(', '.join(row.get('avoid_names') or []))}</p>
                    <p><b>Positive terms:</b> {escape(', '.join(row.get('positive_terms') or []))}</p>
                    <pre>{esc_json(row['state_excerpt'])}</pre>
                  </div>
                </div>
                <div class="candidates">
                  <div><h3>Heuristic Better From Submitted Top20</h3>{render_candidate(row['better_submitted'], submitted_empty_message(row))}</div>
                  <div><h3>Heuristic Better From Candidate Pool</h3>{render_candidate(row['better_pool'], pool_empty_message(row))}</div>
                </div>
                <h3>Predicted Top20</h3>
                <div class="table-wrap">
                <table>
		                  <thead><tr><th>#</th><th>Track</th><th>Album</th><th>Popularity</th><th>Fusion Rank</th><th>Audit Fit</th><th>Flags / Tags</th></tr></thead>
                  <tbody>{render_item_table(row['items'])}</tbody>
                </table>
                </div>
                <h3>Predicted Response</h3>
                <blockquote>{escape(str(row.get('prediction_response') or ''))}</blockquote>
              </details>
            </section>
            """
        )

    source_bits = agg["metadata"]
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Music CRS Prediction Audit · {escape(source_bits.get('tid', 'run'))}</title>
<style>
:root {{
  --bg: #f4f6f8;
  --panel: #ffffff;
  --panel-soft: #fbfcfe;
  --ink: #111827;
  --muted: #5c6675;
  --quiet: #7a8492;
  --line: #d8dee7;
  --line-strong: #c6ceda;
  --bad: #b42318;
  --bad-bg: #fff3f0;
  --warn: #9a6700;
  --warn-bg: #fff7d6;
  --ok: #087443;
  --ok-bg: #ecfdf3;
  --blue: #1d4ed8;
  --blue-bg: #eef4ff;
  --violet: #6d28d9;
  --shadow: 0 1px 2px rgba(15, 23, 42, .05), 0 12px 32px rgba(15, 23, 42, .06);
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font: 14px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); font-feature-settings: "tnum"; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px clamp(16px, 2.3vw, 34px) 40px; }}
h1 {{ font-size: 30px; line-height: 1.1; margin: 0 0 6px; letter-spacing: 0; }}
h2 {{ font-size: 16px; line-height: 1.25; margin: 0 0 8px; letter-spacing: 0; }}
h3 {{ font-size: 13px; line-height: 1.25; margin: 20px 0 9px; letter-spacing: 0; text-transform: uppercase; color: #344054; }}
p {{ margin: 0 0 8px; }}
.hero {{ display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 18px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }}
.meta {{ color: var(--muted); max-width: 620px; }}
.metric-groups {{ display: grid; gap: 12px; margin: 18px 0; }}
.metric-group {{ background: rgba(255, 255, 255, .72); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 1px 0 rgba(15, 23, 42, .03); overflow: hidden; }}
.metric-group > summary {{ display: flex; justify-content: space-between; gap: 14px; align-items: baseline; margin: 0; padding: 12px 14px; color: var(--ink); border-bottom: 1px solid var(--line); list-style-position: inside; }}
.metric-group > summary span {{ font-weight: 850; }}
.metric-group > summary small {{ color: var(--muted); font-weight: 650; text-align: right; }}
.metric-group:not([open]) > summary {{ border-bottom: 0; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(154px, 1fr)); gap: 12px; margin: 0; padding: 12px; }}
.card {{ --accent: var(--line-strong); background: var(--panel); border: 1px solid var(--line); border-top: 3px solid var(--accent); border-radius: 8px; padding: 13px 14px 12px; box-shadow: 0 1px 0 rgba(15, 23, 42, .03); min-height: 86px; }}
.card.danger {{ --accent: var(--bad); background: linear-gradient(#fff, #fff), var(--bad-bg); }}
.card.warn {{ --accent: var(--warn); }}
.card.good {{ --accent: var(--ok); }}
.card span {{ display: block; color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0; }}
.card strong {{ display: block; font-size: 24px; line-height: 1.1; margin-top: 8px; }}
.card small {{ display: block; color: var(--muted); font-size: 12px; font-weight: 650; line-height: 1.35; margin-top: 8px; }}
.summary {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px 18px; margin: 16px 0; box-shadow: var(--shadow); }}
.summary ul {{ margin: 8px 0 0; padding-left: 20px; }}
.summary li {{ margin: 7px 0; color: #26313d; }}
.summary dl {{ display: grid; grid-template-columns: 180px 1fr; gap: 9px 14px; margin: 14px 0 0; }}
.summary dt {{ font-weight: 800; }}
.summary dd {{ margin: 0; color: var(--muted); }}
.controls {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin: 16px 0; padding: 10px; background: rgba(244, 246, 248, .92); border: 1px solid var(--line); border-radius: 8px; position: sticky; top: 0; z-index: 4; backdrop-filter: blur(10px); }}
.controls + .controls {{ position: static; background: transparent; border: 0; padding: 0; margin-top: -4px; }}
.label-controls {{ margin-top: -8px; }}
.control-label {{ color: var(--muted); font-size: 12px; font-weight: 800; text-transform: uppercase; }}
input, select, button {{ font: inherit; border: 1px solid var(--line-strong); border-radius: 7px; background: #fff; color: var(--ink); padding: 9px 11px; }}
input:focus, select:focus, button:focus-visible {{ outline: 2px solid rgba(29, 78, 216, .22); border-color: var(--blue); }}
select:disabled {{ color: var(--quiet); background: #f8fafc; }}
input {{ min-width: 300px; flex: 1; }}
button {{ cursor: pointer; }}
.pill {{ background: #fff; color: #374151; }}
.pill:hover {{ border-color: var(--blue); color: var(--blue); }}
.pill.active {{ border-color: var(--blue); color: var(--blue); background: var(--blue-bg); }}
.llm-pill.bad.active {{ color: var(--bad); border-color: #f3b8b0; background: var(--bad-bg); }}
.llm-pill.weak.active {{ color: var(--warn); border-color: #ecd48a; background: var(--warn-bg); }}
.llm-pill.acceptable.active {{ color: var(--blue); border-color: #b8cdfd; background: var(--blue-bg); }}
.llm-pill.good.active {{ color: var(--ok); border-color: #a9dfc1; background: var(--ok-bg); }}
.row-card {{ background: var(--panel); border: 1px solid var(--line); border-left: 5px solid var(--line-strong); border-radius: 8px; margin: 14px 0; padding: 16px; box-shadow: 0 1px 0 rgba(15, 23, 42, .03); }}
.row-card.bad {{ border-left-color: var(--bad); }}
.row-card.warn {{ border-left-color: var(--warn); }}
.row-card.ok {{ border-left-color: var(--ok); }}
.row-card header {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 390px); gap: 22px; align-items: start; }}
.row-card header p {{ color: #3d4754; font-size: 15px; line-height: 1.5; margin-top: 8px; }}
.row-kicker {{ display: flex; flex-wrap: wrap; align-items: center; gap: 7px; color: var(--quiet); font-size: 12px; font-weight: 700; text-transform: uppercase; }}
.badge {{ display: inline-flex; align-items: center; min-height: 22px; border-radius: 999px; padding: 2px 8px; border: 1px solid var(--line); background: #fff; color: #4b5563; font-size: 11px; font-weight: 800; text-transform: uppercase; white-space: nowrap; }}
.badge.bad, .badge.judge.bad {{ color: var(--bad); border-color: #f3b8b0; background: var(--bad-bg); }}
.badge.warn, .badge.judge.weak, .badge.judge.partial {{ color: var(--warn); border-color: #ecd48a; background: var(--warn-bg); }}
.badge.ok, .badge.judge.good {{ color: var(--ok); border-color: #a9dfc1; background: var(--ok-bg); }}
.badge.judge.acceptable {{ color: var(--blue); border-color: #b8cdfd; background: var(--blue-bg); }}
.status {{ text-align: right; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-soft); }}
.status strong {{ display: block; font-size: 15px; line-height: 1.25; }}
.status span, .status small {{ display: block; color: var(--muted); }}
.status small {{ margin-top: 4px; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }}
.chips span {{ border: 1px solid var(--line); background: #f8fafc; border-radius: 999px; padding: 3px 8px; font-size: 12px; color: #44505f; }}
summary {{ cursor: pointer; color: var(--blue); margin-top: 10px; font-weight: 750; }}
.explain {{ border: 1px solid #bdd0ff; border-left: 5px solid var(--blue); background: var(--blue-bg); border-radius: 8px; padding: 13px 15px; margin: 14px 0; }}
.explain h3 {{ margin-top: 0; color: #174ea6; }}
.explain p {{ margin: 7px 0; }}
.llm-choice {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(210px, 300px); gap: 16px; align-items: start; border: 1px solid var(--line); border-left: 5px solid var(--line-strong); border-radius: 8px; background: #fff; padding: 13px 15px; margin: 14px 0; }}
.llm-choice.bad {{ border-left-color: var(--bad); background: var(--bad-bg); }}
.llm-choice.weak, .llm-choice.partial {{ border-left-color: var(--warn); background: var(--warn-bg); }}
.llm-choice.acceptable {{ border-left-color: var(--blue); background: var(--blue-bg); }}
.llm-choice.good {{ border-left-color: var(--ok); background: var(--ok-bg); }}
.llm-choice h3 {{ margin-top: 0; }}
.llm-choice p {{ margin: 6px 0; }}
.llm-choice small, .llm-choice span, .llm-choice em {{ display: block; color: var(--muted); }}
.llm-choice em {{ font-style: normal; margin-top: 5px; }}
.choice-meta {{ padding: 10px 12px; border: 1px solid rgba(15, 23, 42, .12); border-radius: 8px; background: rgba(255, 255, 255, .72); }}
.choice-meta strong {{ display: block; font-size: 24px; line-height: 1; margin-bottom: 6px; }}
.grid {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(360px, 0.92fr); gap: 20px; align-items: start; }}
.grid > div, .candidates > div {{ min-width: 0; }}
.candidates {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
.candidate, .empty {{ border: 1px solid var(--line); border-radius: 8px; padding: 11px; background: var(--panel-soft); }}
.candidate strong {{ display: block; line-height: 1.25; }}
.candidate span, .candidate small, .candidate em {{ display: block; color: var(--muted); }}
.candidate em {{ margin-top: 5px; font-style: normal; }}
.turn {{ border-left: 3px solid var(--line); padding: 8px 11px; margin: 7px 0; background: var(--panel-soft); border-radius: 0 7px 7px 0; }}
.turn.user {{ border-left-color: var(--blue); }}
.turn.music {{ border-left-color: var(--violet); }}
.turn.assistant {{ border-left-color: #0891b2; }}
pre {{ white-space: pre-wrap; overflow: auto; max-height: 360px; background: #111827; color: #e6edf3; border-radius: 8px; padding: 12px; font-size: 12px; line-height: 1.5; }}
.table-wrap {{ overflow: auto; border: 1px solid var(--line); border-radius: 8px; background: #fff; }}
table {{ width: 100%; border-collapse: collapse; min-width: 880px; }}
th, td {{ text-align: left; border-bottom: 1px solid var(--line); padding: 9px 10px; vertical-align: top; }}
th {{ font-size: 11px; color: var(--muted); background: #f8fafc; text-transform: uppercase; letter-spacing: 0; position: sticky; top: 0; z-index: 1; }}
tbody tr:last-child td {{ border-bottom: 0; }}
tr.bad td {{ background: var(--bad-bg); }}
tr.ok td {{ background: var(--ok-bg); }}
td span, small {{ color: var(--muted); }}
blockquote {{ margin: 0; padding: 11px 13px; background: var(--panel-soft); border-left: 3px solid var(--line-strong); border-radius: 0 7px 7px 0; color: #374151; }}
.hidden {{ display: none; }}
.method {{ margin-top: 24px; color: var(--muted); font-size: 13px; }}
@media (max-width: 850px) {{
  main {{ padding: 16px; }}
  .hero, .row-card header, .grid, .candidates, .llm-choice {{ display: block; }}
  .controls {{ position: static; }}
  .summary dl {{ display: block; }}
  .summary dd {{ margin-bottom: 8px; }}
  .status {{ text-align: left; margin-top: 8px; }}
  input {{ min-width: 100%; }}
}}
</style>
</head>
<body>
<main>
  <section class="hero">
    <div>
      <h1>Music CRS Prediction Audit</h1>
      <p class="meta">{escape(source_bits.get('tid', 'run'))} · {escape(source_bits.get('split', ''))} · generated {escape(source_bits.get('generated_at', ''))}</p>
    </div>
    <div class="meta">Leaderboard metadata is optional. Hidden-label splits show validity, gap metrics, and optional judge evaluations.</div>
  </section>
  <section class="metric-groups">{metric_group_html}</section>
  <section class="summary">
    <h2>Top-Level Read</h2>
    <ul>{render_summary(agg)}</ul>
    <details>
      <summary>What the gap labels mean</summary>
      <dl>
        <dt>Hard leak</dt><dd>A recommendation violates an explicit rejected track, artist, album, or name. This is the strongest “bad recommendation” signal.</dd>
        <dt>Flagged row</dt><dd>A broader warning that can include hard leaks, repeated prior artists after a branch-out request, response self-contradictions, or label misses.</dd>
        <dt>State gap</dt><dd>The conversation says something important, but the structured state did not capture it as a usable constraint.</dd>
        <dt>Compiler/filter gap</dt><dd>The system knew a rejection but still allowed the item into the final list.</dd>
        <dt>Ranking gap</dt><dd>Cleaner candidates existed, but the final ordering placed a worse item above them.</dd>
        <dt>Fusion Rank</dt><dd>Where the item appeared in the candidate-fusion trace before final ordering. Lower usually means retrieval already liked it.</dd>
        <dt>Audit Fit</dt><dd>A simple metadata/tag/rejection heuristic used for inspection. It is not a leaderboard score.</dd>
        <dt>Recommendation Fit</dt><dd>Only available for label-free runs. It reads the conversation and visible candidates, then rates whether the submitted recommendation fits.</dd>
        <dt>Response Quality</dt><dd>Only available for label-free runs. It reads the conversation, top recommendation metadata, and generated response, then judges whether the prose grounds and justifies the top recommendation without unsupported claims.</dd>
        <dt>State Accuracy</dt><dd>Available for trace-backed runs. It compares raw conversation context against extracted/compiled state to find missing constraints or stale state.</dd>
        <dt>Label miss</dt><dd>Only for devset/ground-truth runs: the submitted top 20 did not contain the target track.</dd>
      </dl>
    </details>
  </section>
	  <section class="controls">
	    <input id="search" placeholder="Search sessions, user text, artists, tracks, gap names">
	    <select id="statusFilter">
	      <option value="">all rows</option>
	      <option value="bad">flagged top1</option>
	      <option value="warn">gap flagged</option>
	      <option value="ok">no gap flag</option>
	    </select>
	    {llm_filter_html}
	    {explanation_filter_html}
	    {state_filter_html}
	    <button id="clear">Clear filters</button>
	  </section>
	  <section class="controls">{gap_pills}</section>
	  {llm_pills}
	  {explanation_pills}
	  {state_pills}
  <section id="rows">{''.join(row_cards)}</section>
  <section class="method">
    <h3>Sources And Caveats</h3>
    <p>Prediction: {escape(str(source_bits.get('prediction_path')))}</p>
    <p>Trace: {escape(str(source_bits.get('trace_path') or 'not supplied'))}</p>
    <p>Ground truth: {escape(str(source_bits.get('ground_truth_path') or 'not supplied'))}</p>
    <p>Dataset: {escape(str(source_bits.get('dataset_name') or 'not supplied'))}</p>
    <p>Recommendation fit judge: {escape(json.dumps(source_bits.get('llm_judge') or {'enabled': False}, ensure_ascii=False))}</p>
    <p>Response quality judge: {escape(json.dumps(source_bits.get('llm_explanation_judge') or {'enabled': False}, ensure_ascii=False))}</p>
    <p>State accuracy judge: {escape(json.dumps(source_bits.get('llm_state_judge') or {'enabled': False}, ensure_ascii=False))}</p>
    <p>Catalog warning: {escape(str(source_bits.get('catalog_warning') or 'none'))}</p>
  </section>
</main>
<script>
const search = document.getElementById('search');
const statusFilter = document.getElementById('statusFilter');
const llmFilter = document.getElementById('llmFilter');
const explanationFilter = document.getElementById('explanationFilter');
const stateFilter = document.getElementById('stateFilter');
const clear = document.getElementById('clear');
const gapPills = Array.from(document.querySelectorAll('[data-gap]'));
const llmPills = Array.from(document.querySelectorAll('.llm-pill[data-llm]'));
const explanationPills = Array.from(document.querySelectorAll('.explanation-pill[data-explanation]'));
const statePills = Array.from(document.querySelectorAll('.state-pill[data-state]'));
const cards = Array.from(document.querySelectorAll('.row-card'));
let activeGap = '';
function normalizeSearch(value) {{
  return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}}
function syncLlmPills() {{
  const llm = llmFilter ? llmFilter.value : '';
  llmPills.forEach(p => p.classList.toggle('active', p.dataset.llm === llm));
}}
function syncExplanationPills() {{
  const explanation = explanationFilter ? explanationFilter.value : '';
  explanationPills.forEach(p => p.classList.toggle('active', p.dataset.explanation === explanation));
}}
function syncStatePills() {{
  const state = stateFilter ? stateFilter.value : '';
  statePills.forEach(p => p.classList.toggle('active', p.dataset.state === state));
}}
function applyFilters() {{
  const q = normalizeSearch(search.value);
  const status = statusFilter.value;
  const llm = llmFilter ? llmFilter.value : '';
  const explanation = explanationFilter ? explanationFilter.value : '';
  const state = stateFilter ? stateFilter.value : '';
  cards.forEach(card => {{
    const matchesSearch = !q || card.dataset.search.includes(q);
    const matchesStatus = !status || card.classList.contains(status);
    const matchesGap = !activeGap || card.dataset.gaps.split(' ').includes(activeGap);
    const matchesLlm = !llm || card.dataset.llm === llm;
    const matchesExplanation = !explanation || card.dataset.explanation === explanation;
    const matchesState = !state || card.dataset.state === state;
    card.classList.toggle('hidden', !(matchesSearch && matchesStatus && matchesGap && matchesLlm && matchesExplanation && matchesState));
  }});
  syncLlmPills();
  syncExplanationPills();
  syncStatePills();
}}
search.addEventListener('input', applyFilters);
statusFilter.addEventListener('change', applyFilters);
if (llmFilter) llmFilter.addEventListener('change', applyFilters);
if (explanationFilter) explanationFilter.addEventListener('change', applyFilters);
if (stateFilter) stateFilter.addEventListener('change', applyFilters);
clear.addEventListener('click', () => {{
  search.value = '';
  statusFilter.value = '';
  if (llmFilter) llmFilter.value = '';
  if (explanationFilter) explanationFilter.value = '';
  if (stateFilter) stateFilter.value = '';
  activeGap = '';
  gapPills.forEach(p => p.classList.remove('active'));
  llmPills.forEach(p => p.classList.remove('active'));
  explanationPills.forEach(p => p.classList.remove('active'));
  statePills.forEach(p => p.classList.remove('active'));
  applyFilters();
}});
gapPills.forEach(p => p.addEventListener('click', () => {{
  activeGap = activeGap === p.dataset.gap ? '' : p.dataset.gap;
  gapPills.forEach(x => x.classList.toggle('active', x.dataset.gap === activeGap));
  applyFilters();
}}));
llmPills.forEach(p => p.addEventListener('click', () => {{
  if (!llmFilter) return;
  llmFilter.value = llmFilter.value === p.dataset.llm ? '' : p.dataset.llm;
  applyFilters();
}}));
explanationPills.forEach(p => p.addEventListener('click', () => {{
  if (!explanationFilter) return;
  explanationFilter.value = explanationFilter.value === p.dataset.explanation ? '' : p.dataset.explanation;
  applyFilters();
}}));
statePills.forEach(p => p.addEventListener('click', () => {{
  if (!stateFilter) return;
  stateFilter.value = stateFilter.value === p.dataset.state ? '' : p.dataset.state;
  applyFilters();
}}));
</script>
</body>
</html>
"""
    return html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Music CRS repo root")
    parser.add_argument("--tid", help="Experiment/task id")
    parser.add_argument("--config", help="Config YAML path")
    parser.add_argument("--prediction", help="Prediction JSON or submission ZIP")
    parser.add_argument("--trace", help="Trace JSONL path")
    parser.add_argument("--ground-truth", help="Ground-truth JSON path")
    parser.add_argument("--leaderboard-metadata", help="Optional JSON with external leaderboard scores")
    parser.add_argument("--dataset", help="HF conversation dataset name")
    parser.add_argument("--split", help="Split name, e.g. devset, blindset_A, or blindset_B")
    parser.add_argument("--catalog-lancedb", help="LanceDB directory, default cache/lancedb")
    parser.add_argument(
        "--catalog-source",
        choices=["auto", "lancedb", "hf"],
        default="auto",
        help="Catalog metadata source. Default auto tries LanceDB, then HF track metadata.",
    )
    parser.add_argument(
        "--catalog-hf-dataset",
        default=DEFAULT_CATALOG_DATASET,
        help=f"HF catalog dataset for --catalog-source hf/auto fallback. Default {DEFAULT_CATALOG_DATASET}.",
    )
    parser.add_argument(
        "--catalog-hf-split",
        default=DEFAULT_CATALOG_SPLIT,
        help=f"HF catalog split. Default {DEFAULT_CATALOG_SPLIT}.",
    )
    parser.add_argument("--out", help="Output directory")
    parser.add_argument("--max-candidate-pool", type=int, default=200)
    parser.add_argument("--limit", type=int, help="Audit only the first N prediction rows")
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Run an optional LLM judge. Skipped automatically when ground truth labels are supplied.",
    )
    parser.add_argument(
        "--llm-explanation-judge",
        action="store_true",
        help=(
            "Run an optional LLM judge for the generated response/explanation text. "
            "Skipped automatically when ground truth labels are supplied."
        ),
    )
    parser.add_argument(
        "--llm-state-judge",
        action="store_true",
        help=(
            "Run an optional diagnostic LLM judge for extracted/compiled state accuracy. "
            "Requires trace rows and is separate from recommendation/explanation judging."
        ),
    )
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("MCRS_AUDIT_JUDGE_MODEL", DEFAULT_JUDGE_MODEL),
        help=f"LiteLLM model for label-free judging, default {DEFAULT_JUDGE_MODEL}",
    )
    parser.add_argument(
        "--judge-limit",
        type=int,
        default=80,
        help="Maximum rows to judge when --llm-judge is used; 0 means all audited rows.",
    )
    parser.add_argument(
        "--judge-top-k",
        type=int,
        default=20,
        help="How many submitted top recommendations to show the LLM judge.",
    )
    parser.add_argument(
        "--judge-workers",
        type=int,
        default=4,
        help="Concurrent LLM judge calls for uncached rows.",
    )
    parser.add_argument(
        "--judge-max-tokens",
        type=int,
        default=900,
        help="Maximum response tokens for each LLM judge call.",
    )
    parser.add_argument(
        "--judge-cache",
        help="Optional JSONL cache for LLM judgments; defaults to <out>/llm_judgments.jsonl.",
    )
    parser.add_argument(
        "--explanation-judge-cache",
        help=(
            "Optional JSONL cache for LLM response/explanation judgments; "
            "defaults to <out>/llm_explanation_judgments.jsonl."
        ),
    )
    parser.add_argument(
        "--state-judge-cache",
        help="Optional JSONL cache for LLM state judgments; defaults to <out>/llm_state_judgments.jsonl.",
    )
    parser.add_argument(
        "--judge-litellm-cache",
        choices=["disk", "local", "off"],
        default=os.environ.get("MCRS_AUDIT_LITELLM_CACHE", "disk"),
        help="LiteLLM completion cache for uncached judge calls. Default: disk.",
    )
    parser.add_argument(
        "--judge-litellm-cache-dir",
        help="Directory for LiteLLM disk cache. Defaults to <out parent>/.litellm_cache.",
    )
    parser.add_argument(
        "--judge-include-state",
        action="store_true",
        help=(
            "Include diagnostic compiled/extracted state and audit flags in the LLM judge prompt. "
            "Default is conversation/candidate metadata only."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolved = resolve_inputs(args)
    predictions = load_predictions(resolved["prediction_path"])
    traces = load_traces(resolved["trace_path"])
    ground_truth = load_ground_truth(resolved["ground_truth_path"])
    conversations, conv_warning = load_conversations(resolved["dataset_name"])
    catalog = load_catalog(
        resolved["catalog_lancedb"],
        source=args.catalog_source,
        hf_dataset=args.catalog_hf_dataset,
        hf_split=args.catalog_hf_split,
    )
    leaderboard = None
    lb_path = resolved["leaderboard_metadata_path"]
    if lb_path:
        leaderboard = json.loads(lb_path.read_text(encoding="utf-8"))
    out_dir = resolved["out_dir"]

    metadata = {
        "tid": resolved["tid"],
        "split": resolved["split"],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prediction_path": str(resolved["prediction_path"]),
        "trace_path": str(resolved["trace_path"]) if resolved["trace_path"] else None,
        "ground_truth_path": str(resolved["ground_truth_path"]) if resolved["ground_truth_path"] else None,
        "config_path": str(resolved["config_path"]) if resolved["config_path"] else None,
        "dataset_name": resolved["dataset_name"],
        "conversation_warning": conv_warning,
        "catalog_lancedb": str(resolved["catalog_lancedb"]),
        "catalog_source": catalog.source,
        "catalog_hf_dataset": args.catalog_hf_dataset,
        "catalog_hf_split": args.catalog_hf_split,
        "catalog_warning": catalog.warning,
        "leaderboard_metadata": leaderboard,
        "llm_judge": {"enabled": False},
        "llm_explanation_judge": {"enabled": False},
        "llm_state_judge": {"enabled": False},
    }
    rows = audit_rows(
        predictions,
        traces,
        ground_truth,
        conversations,
        catalog,
        args.max_candidate_pool,
        args.limit,
    )
    if args.llm_judge:
        litellm_cache_dir = (
            Path(args.judge_litellm_cache_dir).resolve()
            if args.judge_litellm_cache_dir
            else out_dir.parent / ".litellm_cache"
        )
        if ground_truth:
            metadata["llm_judge"] = {
                "enabled": True,
                "ran": False,
                "model": args.judge_model,
                "skipped_reason": "ground-truth labels were supplied; LLM judge is only for label-free/blind audits.",
                "label_free_only": True,
                "include_state": bool(args.judge_include_state),
                "litellm_cache": requested_litellm_cache_metadata(
                    args.judge_litellm_cache,
                    litellm_cache_dir,
                ),
            }
        else:
            metadata["llm_judge"] = run_llm_judge(
                rows,
                catalog,
                out_dir=out_dir,
                model=args.judge_model,
                top_k=max(1, args.judge_top_k),
                limit=args.judge_limit,
                workers=max(1, args.judge_workers),
                max_tokens=max(128, args.judge_max_tokens),
                cache_path=Path(args.judge_cache).resolve() if args.judge_cache else None,
                include_state=bool(args.judge_include_state),
                litellm_cache_mode=args.judge_litellm_cache,
                litellm_cache_dir=litellm_cache_dir,
            )
    if args.llm_explanation_judge:
        litellm_cache_dir = (
            Path(args.judge_litellm_cache_dir).resolve()
            if args.judge_litellm_cache_dir
            else out_dir.parent / ".litellm_cache"
        )
        if ground_truth:
            metadata["llm_explanation_judge"] = {
                "enabled": True,
                "ran": False,
                "model": args.judge_model,
                "skipped_reason": "ground-truth labels were supplied; LLM explanation judge is only for label-free/blind audits.",
                "label_free_only": True,
                "prompt_version": EXPLANATION_JUDGE_PROMPT_VERSION,
                "litellm_cache": requested_litellm_cache_metadata(
                    args.judge_litellm_cache,
                    litellm_cache_dir,
                ),
            }
        else:
            metadata["llm_explanation_judge"] = run_llm_explanation_judge(
                rows,
                catalog,
                out_dir=out_dir,
                model=args.judge_model,
                limit=args.judge_limit,
                workers=max(1, args.judge_workers),
                max_tokens=max(128, args.judge_max_tokens),
                cache_path=Path(args.explanation_judge_cache).resolve()
                if args.explanation_judge_cache
                else None,
                litellm_cache_mode=args.judge_litellm_cache,
                litellm_cache_dir=litellm_cache_dir,
            )
    if args.llm_state_judge:
        litellm_cache_dir = (
            Path(args.judge_litellm_cache_dir).resolve()
            if args.judge_litellm_cache_dir
            else out_dir.parent / ".litellm_cache"
        )
        metadata["llm_state_judge"] = run_llm_state_judge(
            rows,
            catalog,
            out_dir=out_dir,
            model=args.judge_model,
            limit=args.judge_limit,
            workers=max(1, args.judge_workers),
            max_tokens=max(128, args.judge_max_tokens),
            cache_path=Path(args.state_judge_cache).resolve()
            if args.state_judge_cache
            else None,
            litellm_cache_mode=args.judge_litellm_cache,
            litellm_cache_dir=litellm_cache_dir,
        )
    audit = {
        "aggregate": aggregate(rows, metadata),
        "rows": rows,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "index.html").write_text(render_html(audit, catalog), encoding="utf-8")
    print(f"Wrote {out_dir / 'index.html'}")
    print(f"Wrote {out_dir / 'audit.json'}")
    agg = audit["aggregate"]
    print(
        "Rows={n_rows} trace={n_with_trace} flagged_top1={top1_flagged} "
        "flagged_top20_rows={top20_flagged_rows} hard_top1_leaks={hard_top1_invalid}".format(**agg)
    )
    if agg.get("label_metrics"):
        lm = agg["label_metrics"]
        print(f"nDCG@20={lm['ndcg@20']:.4f} Hit@20={lm['hit@20']:.4f} MRR={lm['mrr']:.4f}")
    judge = metadata.get("llm_judge") or {}
    if judge.get("enabled"):
        if judge.get("ran"):
            print(
                "LLM judge={model} judged_rows={judged_rows} errors={error_rows}".format(**judge)
            )
        else:
            print(f"LLM judge skipped: {judge.get('skipped_reason') or judge.get('warning')}")
    explanation_judge = metadata.get("llm_explanation_judge") or {}
    if explanation_judge.get("enabled"):
        if explanation_judge.get("ran"):
            print(
                "LLM explanation judge={model} judged_rows={judged_rows} errors={error_rows}".format(
                    **explanation_judge
                )
            )
        else:
            print(
                "LLM explanation judge skipped: "
                f"{explanation_judge.get('skipped_reason') or explanation_judge.get('warning')}"
            )
    state_judge = metadata.get("llm_state_judge") or {}
    if state_judge.get("enabled"):
        if state_judge.get("ran"):
            print(
                "LLM state judge={model} judged_rows={judged_rows} errors={error_rows}".format(
                    **state_judge
                )
            )
        else:
            print(f"LLM state judge skipped: {state_judge.get('warning')}")
    sys.stdout.flush()
    # Some LanceDB/PyArrow builds abort during interpreter teardown in local
    # plugin sessions. Files and stdout are already flushed; exit directly.
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
