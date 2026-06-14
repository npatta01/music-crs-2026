"""Generate a decision report for Music CRS devset recall gaps.

This report builds on the compact recall-gap JSON already produced from the
large trace and enriches sampled failures with the original TalkPlay
conversation text. It writes a static HTML report, companion Markdown, a full
analysis prompt, PNG charts, and compact JSON for later agents.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_ROOT = Path("/Users/npatta01/data/projects/music-conversational-music-recomender-2026")
DEFAULT_REPORT_ROOT = Path("experiments/analysis/devset_recall_gap_state_ranker_v10_2026_06_14")
DEFAULT_OUT_DIR = DEFAULT_REPORT_ROOT / "ranker_decision"
DEFAULT_TID = "state_ranker_v10_rrf_devset"
HF_CONVERSATION_DATASET = "talkpl-ai/TalkPlayData-Challenge-Dataset"
HF_USER_METADATA_DATASET = "talkpl-ai/TalkPlayData-Challenge-User-Metadata"

IMPORTANT_GROUPS = [
    "not_in_any_branch_top1000",
    "union20_fusion_loss",
    "union20_postfusion_or_final_loss",
    "union100_near_miss",
    "union200_deep_miss",
    "union1000_deep_miss",
]
SPECIFICITY_ORDER = {"LL": 0, "LH": 1, "HL": 2, "HH": 3}
SPECIFICITY_GLOSSARY = {
    "LL": {
        "label": "Low / low specificity",
        "meaning": "Observed goals are broad discovery or multi-item asks with weak exact-entity constraints.",
        "example": "discover multiple instrumental pieces from a broad era or explore ambient/downtempo music.",
        "why_it_matters": "This is the worst specificity slice: a ranker helps only after better candidates enter union@20/100.",
    },
    "LH": {
        "label": "Low / high specificity",
        "meaning": "Observed goals often name a hidden target type or specific memory, but the surface clue is vague.",
        "example": "find one album remembered by cover art, or identify a composer/song from vague soundtrack memory.",
        "why_it_matters": "Needs better goal-conditioned retrieval and structured metadata, not only exact text matching.",
    },
    "HL": {
        "label": "High / low specificity",
        "meaning": "Observed goals have concrete genres, artists, eras, or journey constraints, but still ask for multiple possible tracks.",
        "example": "find multiple punk/hardcore songs with era and lyrical-theme constraints.",
        "why_it_matters": "Candidate generation is decent, but final ranking/policy still loses many recoverable items.",
    },
    "HH": {
        "label": "High / high specificity",
        "meaning": "Observed goals often identify exact titles, artists, lyrics, albums, or strongly constrained targets.",
        "example": "play a specific globally popular song by exact title and artist.",
        "why_it_matters": "This is the easiest slice; it is the guardrail when adding broad-goal retrievers or metadata features.",
    },
}

CATEGORY_FOCUS_GLOSSARY = {
    "C": {
        "description": "Visual / cover-art remembered album targets.",
        "why_gap": "The user clue is often visual or remembered-art based, while current retrieval is mostly text/tags/embeddings from track metadata.",
        "work_on": "Add cover-art caption/visual retrieval and album-level matching, then rerank with visual-goal features.",
    },
    "K": {
        "description": "Broad instrumental, soundtrack, mood, era, or aesthetic discovery.",
        "why_gap": "The goal is latent and multi-answer; exact entity recall is weak and generic dense branches often bury the intended target.",
        "work_on": "Add instrumental/OST/mood/tag-popularity retrievers and use goal text plus state tags as candidate generators.",
    },
    "I": {
        "description": "Small mixed slice: exact global-hit requests plus nuanced modern genre/style asks.",
        "why_gap": "It combines exact popularity/canonicality with style-matching, so one generic routing strategy misses both ends.",
        "work_on": "Split routing between exact-popular probes and style/genre candidate generation; do not rely on equal current fusion weights.",
    },
    "J": {
        "description": "Popularity, canonicality, or widely-recognized song requests within an era/genre/community.",
        "why_gap": "The clue is often 'popular/recognized' rather than a track title, but popularity is not a calibrated final-ranker feature.",
        "work_on": "Add popularity/canonicality features and genre-community popularity lookups; train the ranker to trust them only when state asks for it.",
    },
}

STATE_FIELD_REFERENCE = [
    {
        "field": "turn_intent",
        "meaning": "Natural-language active ask for this turn.",
        "retrieval_use": "Main BM25 and dense-query text.",
        "example_use": "Shown as State turn_intent in each failed example.",
    },
    {
        "field": "intent_mode",
        "meaning": "open_explore, refinement, pivot, or playlist_build.",
        "retrieval_use": "Controls anchor mixing and whether prior accepted tracks should influence retrieval.",
        "example_use": "Shown in the rank/evidence strip and state audit.",
    },
    {
        "field": "track_feedback / anchors",
        "meaning": "Played tracks and whether the user accepted, rejected, seeded, or reacted neutrally.",
        "retrieval_use": "Accepted/seed tracks become centroid anchors; rejected tracks can demote artists/tracks.",
        "example_use": "The report shows n_anchor, n_played, and anchor_artist_ids when available.",
    },
    {
        "field": "mentioned_entities",
        "meaning": "Artists, albums, tracks, and tags named by the user with sentiment.",
        "retrieval_use": "Feeds BM25 clauses, resolver targets, discography lookup, tag boosts, and state QA.",
        "example_use": "Shown as mentioned and resolved entities in failed-example details.",
    },
    {
        "field": "positive / rejected tags",
        "meaning": "Tag-like constraints extracted from the user turn and history.",
        "retrieval_use": "Positive tags boost matching candidates; rejected tags can demote.",
        "example_use": "Shown as positive_tags, gt_tag_overlap, and rejected tags.",
    },
    {
        "field": "release_year_range / hard_filters",
        "meaning": "Soft era hints and hard catalog constraints.",
        "retrieval_use": "Era lookup, year boosts, and candidate masks. Era should be soft because many misses are release-date mismatches.",
        "example_use": "Shown as release bucket, release year, year_range, and hard_filters.",
    },
    {
        "field": "explicit_rejections",
        "meaning": "Artists, tracks, or tags the user explicitly wants excluded.",
        "retrieval_use": "Hard drops or post-fusion demotions.",
        "example_use": "Shown in state audit when present.",
    },
    {
        "field": "process_constraints.exploration_policy",
        "meaning": "Whether to exploit, diversify artists/albums, or stay balanced.",
        "retrieval_use": "Post-fusion same-artist/same-album demotion policy.",
        "example_use": "Shown as policy; many recoverable misses are under diversify_artists.",
    },
    {
        "field": "routing_tags",
        "meaning": "Flags such as exact_entity_probe, lyric_search, feature_articulation, image_or_visual_search, hidden_target_search.",
        "retrieval_use": "Should steer branch weighting/routing; current routing boost is limited.",
        "example_use": "Shown as routing in the example details.",
    },
    {
        "field": "lyrical_theme",
        "meaning": "Theme or subject requested for lyrics.",
        "retrieval_use": "Lyric dense branch query when lyric intent is detected.",
        "example_use": "Shown in state audit when available.",
    },
]


def pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def pct_from_count(count: int, denom: int, digits: int = 1) -> str:
    if not denom:
        return "n/a"
    return f"{count / denom * 100:.{digits}f}%"


def pp(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f} pp"


def clean_text(value: Any, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def first_list_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return first_list_value(value[0]) if value else ""
    if hasattr(value, "tolist"):
        return first_list_value(value.tolist())
    return str(value)


def plain_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return plain_list(value.tolist())
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def safe_json_script(data: Any) -> str:
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def gap_lookup(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["name"]: row for row in report.get("gap_buckets", [])}


def metric_lookup(report: dict[str, Any]) -> dict[str, Any]:
    return report.get("metrics", {})


def choose_examples(report: dict[str, Any], per_group: int = 4, total: int = 18) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    examples = report.get("examples", {})
    for group in IMPORTANT_GROUPS:
        for ex in examples.get(group, [])[: per_group * 2]:
            key = (str(ex["session_id"]), int(ex["turn"]))
            if key in seen:
                continue
            seen.add(key)
            item = dict(ex)
            item["case_bucket"] = group
            chosen.append(item)
            if len([x for x in chosen if x["case_bucket"] == group]) >= per_group:
                break
            if len(chosen) >= total:
                return chosen
    return chosen[:total]


def load_hf_conversations(session_ids: set[str]) -> tuple[dict[str, dict[str, Any]], str | None]:
    if not session_ids:
        return {}, None
    try:
        from datasets import load_dataset

        ds = load_dataset(HF_CONVERSATION_DATASET, split="test")
        rows = {row["session_id"]: row for row in ds if row["session_id"] in session_ids}
        return rows, None
    except Exception as exc:  # pragma: no cover - best-effort enrichment
        return {}, f"{type(exc).__name__}: {exc}"


def recent_conversation(row: dict[str, Any] | None, turn: int) -> dict[str, Any]:
    if not row:
        return {
            "current_user": "",
            "previous_user": "",
            "goal": {},
            "user_profile": {},
            "recent_messages": [],
            "music_ids": [],
        }
    conversations = row.get("conversations") or []
    current_user = ""
    previous_user = ""
    recent = []
    music_ids = []
    for msg in conversations:
        msg_turn = int(msg.get("turn_number") or 0)
        if msg_turn > turn:
            continue
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "user" and msg_turn == turn and not current_user:
            current_user = content
        if role == "user" and msg_turn < turn:
            previous_user = content
        if role == "music":
            music_ids.append(content)
        recent.append(
            {
                "turn": msg_turn,
                "role": role,
                "content": content,
            }
        )
    return {
        "current_user": clean_text(current_user, 700),
        "previous_user": clean_text(previous_user, 500),
        "goal": row.get("conversation_goal") or {},
        "user_profile": row.get("user_profile") or {},
        "recent_messages": recent[-7:],
        "music_ids": music_ids,
    }


def load_track_lookup(source_root: Path, track_ids: set[str]) -> tuple[dict[str, dict[str, Any]], str | None]:
    if not track_ids:
        return {}, None
    try:
        import lancedb

        db_path = source_root / "cache/lancedb"
        table = lancedb.connect(str(db_path)).open_table("music_track_catalog")
        ids = sorted(t for t in track_ids if re.fullmatch(r"[A-Za-z0-9_-]+", t or ""))
        lookup: dict[str, dict[str, Any]] = {}
        for start in range(0, len(ids), 200):
            chunk = ids[start : start + 200]
            quoted = ", ".join("'" + value.replace("'", "''") + "'" for value in chunk)
            df = (
                table.search()
                .where(f"track_id IN ({quoted})")
                .select(["track_id", "track_name", "artist_name", "release_date", "popularity", "tag_list"])
                .limit(len(chunk))
                .to_pandas()
            )
            for row in df.to_dict(orient="records"):
                track_id = str(row["track_id"])
                lookup[track_id] = {
                    "track": first_list_value(row.get("track_name")),
                    "artist": first_list_value(row.get("artist_name")),
                    "release_date": str(row.get("release_date") or ""),
                    "popularity": float(row.get("popularity") or 0.0),
                    "tags": [str(x) for x in plain_list(row.get("tag_list"))][:12],
                }
        return lookup, None
    except Exception as exc:  # pragma: no cover - best-effort enrichment
        return {}, f"{type(exc).__name__}: {exc}"


def render_message(msg: dict[str, Any], track_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    content = msg.get("content") or ""
    if msg.get("role") == "music":
        meta = track_lookup.get(content)
        if meta:
            content = f"{meta.get('track') or content} by {meta.get('artist') or '-'}"
        else:
            content = f"track_id {content}"
    return {
        "turn": msg.get("turn"),
        "role": msg.get("role"),
        "content": clean_text(content, 340),
    }


def load_jsonl_by_key(path: Path, keys: set[tuple[str, int]], sid_field: str, turn_field: str) -> dict[tuple[str, int], dict[str, Any]]:
    found: dict[tuple[str, int], dict[str, Any]] = {}
    if not path.exists() or not keys:
        return found
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (str(row.get(sid_field)), int(row.get(turn_field) or 0))
            if key in keys:
                found[key] = row
                if len(found) == len(keys):
                    break
    return found


def inspect_lancedb_schema(source_root: Path, config_path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "available": False,
        "path": str(source_root / "cache/lancedb"),
        "row_count": None,
        "text_fields": [],
        "vector_fields": [],
        "required_vector_fields": [],
        "missing_required_vector_fields": [],
        "error": None,
    }
    try:
        import lancedb

        db_path = source_root / "cache/lancedb"
        table = lancedb.connect(str(db_path)).open_table("music_track_catalog")
        fields = list(table.schema)
        summary["available"] = True
        summary["row_count"] = table.count_rows()
        vector_fields = []
        text_fields = []
        for field in fields:
            type_text = str(field.type)
            if "fixed_size_list" in type_text:
                match = re.search(r"\[(\d+)\]", type_text)
                vector_fields.append({"name": field.name, "dim": int(match.group(1)) if match else None})
            elif field.name.endswith("_text") or type_text == "string":
                text_fields.append(field.name)
        summary["text_fields"] = sorted(text_fields)
        summary["vector_fields"] = sorted(vector_fields, key=lambda row: row["name"])
    except Exception as exc:  # pragma: no cover - best-effort schema read
        summary["error"] = f"{type(exc).__name__}: {exc}"

    required = []
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        required.extend(re.findall(r'vector_field:\s*"([^"]+)"', text))
        required.extend(re.findall(r"vector_field:\s*'([^']+)'", text))
        required.extend(re.findall(r"vector_field:\s*([A-Za-z0-9_]+)", text))
    required = sorted(set(required))
    available = {row["name"] for row in summary.get("vector_fields", [])}
    summary["required_vector_fields"] = required
    summary["missing_required_vector_fields"] = [field for field in required if field not in available]
    return summary


def diagnose_state_gap(example: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    user_text = (ctx.get("current_user") or "").lower()
    state_intent = (example.get("intent") or "").lower()
    tags = {str(x).lower() for x in example.get("positive_tags") or []}
    if example.get("entity_bucket") == "no_gt_track_or_artist_in_state":
        flags.append("No exact gold track or gold artist is grounded in state.")
    if "popular" in tags or "widely recognized" in tags or "popular" in user_text:
        flags.append("The ask has a popularity/canonicality signal, but final ranking has no calibrated popularity feature.")
    if "90s" in tags and "90s" not in user_text and "1990" not in user_text:
        flags.append("Prior-era tag appears sticky relative to the current user turn.")
    if example.get("release_bucket") == "release_range_excludes_gt":
        flags.append("Extracted era/range excludes the catalog release year of the gold item.")
    if example.get("policy") == "diversify_artists" and example.get("fused_rank") and example.get("final_rank"):
        if int(example["fused_rank"]) <= 20 and int(example["final_rank"]) > 20:
            flags.append("Gold survives fusion top-20, then post-fusion/final policy removes it from top-20.")
    if example.get("case_bucket") == "union20_fusion_loss":
        flags.append("A branch found the gold in top-20, but the current fusion stack did not trust that branch enough.")
    if example.get("case_bucket") == "not_in_any_branch_top1000":
        flags.append("No retriever branch found the gold in top-1000, so a ranker cannot recover this case.")
    if user_text and state_intent and clean_text(user_text, 180).lower() not in state_intent:
        if len(user_text) > 80:
            flags.append("State is a compressed rewrite; audit for lost constraints against the raw user turn.")
    return flags[:5]


def classify_case(example: dict[str, Any]) -> str:
    bucket = example.get("case_bucket")
    if bucket == "not_in_any_branch_top1000":
        return "candidate-generation gap"
    if bucket in {"union1000_deep_miss", "union200_deep_miss", "union100_near_miss"}:
        return "retriever depth or state gap"
    if bucket == "union20_fusion_loss":
        return "current-fusion gap"
    if bucket == "union20_postfusion_or_final_loss":
        return "post-fusion or finalization gap"
    return "mixed"


def enrich_examples(
    examples: list[dict[str, Any]],
    source_root: Path,
    track_lookup: dict[str, dict[str, Any]],
    conversations: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    keys = {(str(ex["session_id"]), int(ex["turn"])) for ex in examples}
    state_audit = load_jsonl_by_key(
        source_root / "exp/inference/devset/_state_audit.jsonl",
        keys,
        "sid",
        "turn",
    )
    anatomy = load_jsonl_by_key(
        source_root / "exp/inference/devset/_per_turn_anatomy.jsonl",
        keys,
        "session_id",
        "turn_number",
    )
    enriched = []
    for ex in examples:
        key = (str(ex["session_id"]), int(ex["turn"]))
        ctx = recent_conversation(conversations.get(ex["session_id"]), int(ex["turn"]))
        recent = [render_message(msg, track_lookup) for msg in ctx.get("recent_messages", [])]
        row = dict(ex)
        row["case_type"] = classify_case(ex)
        row["raw_user_turn"] = ctx.get("current_user") or ""
        row["previous_user_turn"] = ctx.get("previous_user") or ""
        row["conversation_goal"] = ctx.get("goal") or {}
        profile = ctx.get("user_profile") or {}
        row["profile"] = {
            "age_group": profile.get("age_group"),
            "country_name": profile.get("country_name"),
            "preferred_musical_culture": profile.get("preferred_musical_culture"),
        }
        row["recent_conversation"] = recent
        row["state_audit"] = state_audit.get(key, {})
        row["anatomy"] = anatomy.get(key, {})
        row["diagnosis"] = diagnose_state_gap(row, ctx)
        row["smallest_next_test"] = next_test_for_case(row)
        enriched.append(row)
    return enriched


def next_test_for_case(row: dict[str, Any]) -> str:
    bucket = row.get("case_bucket")
    if bucket == "not_in_any_branch_top1000":
        return "Add a tag+popularity or goal-conditioned lookup retriever and check whether the gold enters union@100."
    if bucket == "union20_fusion_loss":
        return "Score union@200 with a lightweight ranker using branch rank and state features; compare final@20 against the current fusion baseline."
    if bucket == "union20_postfusion_or_final_loss":
        return "Run a post-fusion ablation with trusted survivor slots and weaker same-artist/album demotion."
    if bucket == "union100_near_miss":
        return "Evaluate union@100 ranker recovery and branch-specific calibration before adding a new retriever."
    if bucket in {"union200_deep_miss", "union1000_deep_miss"}:
        return "Improve candidate generation for this state slice, then rerank over the wider union pool."
    return "Inspect state, branch ranks, and final policy for this turn."


def build_decision_metrics(report: dict[str, Any]) -> dict[str, Any]:
    metrics = metric_lookup(report)
    n = int(metrics.get("n_turns") or 0)
    final20 = metrics.get("final_hit", {}).get("20")
    union20 = metrics.get("union_hit", {}).get("20")
    union100 = metrics.get("union_hit", {}).get("100")
    union1000 = metrics.get("union_hit", {}).get("1000")
    gaps = gap_lookup(report)
    no_branch = gaps.get("not_in_any_branch_top1000", {}).get("n", 0)
    union20_loss = (union20 or 0) - (final20 or 0)
    return {
        "n_turns": n,
        "final20": final20,
        "union20": union20,
        "union100": union100,
        "union1000": union1000,
        "union20_rank_policy_gap": max(0.0, union20_loss),
        "not_in_union20": max(0.0, 1 - (union20 or 0)),
        "not_in_union100": max(0.0, 1 - (union100 or 0)),
        "not_in_any_branch_top1000_n": no_branch,
        "not_in_any_branch_top1000_rate": no_branch / n if n else None,
        "fusion_efficiency20": metrics.get("fusion_efficiency", {}).get("20"),
        "fusion_efficiency100": metrics.get("fusion_efficiency", {}).get("100"),
    }


def find_named_row(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for row in rows:
        if row.get("name") == name:
            return row
    return {}


def state_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    n = int(report.get("metrics", {}).get("n_turns") or 0)
    entity = report.get("entity_buckets", [])
    no_gt = find_named_row(entity, "no_gt_track_or_artist_in_state")
    mentioned_unresolved = find_named_row(entity, "mentioned_gt_artist_name_unresolved")
    post = report.get("postfusion_summary", [])
    same_artist = find_named_row(post, "same_artist_as_played")
    diversify = find_named_row(post, "policy:diversify_artists")
    release_dims = report.get("dimensions", {}).get("release_bucket", [])
    release_excludes = find_named_row(release_dims, "release_range_excludes_gt")
    return [
        {
            "title": "State often lacks the target entity",
            "evidence": f"{no_gt.get('n', 0):,} turns ({pct_from_count(int(no_gt.get('n', 0)), n)}) have no gold track or artist grounded in state.",
            "implication": "This is a state/retriever coverage problem, not just a current-fusion problem. The next state should expose latent canonicality, goal, and continuation intent.",
        },
        {
            "title": "Post-fusion policy is suppressing recoverable items",
            "evidence": f"In fused-top20 demotions, same_artist_as_played appears in {same_artist.get('n', 0):,} cases and diversify_artists in {diversify.get('n', 0):,}.",
            "implication": "Keep diversity as a feature, but stop letting it erase high-confidence branch survivors without a calibrated ranker.",
        },
        {
            "title": "Era extraction can become a penalty",
            "evidence": f"{release_excludes.get('n', 0):,} turns are marked release_range_excludes_gt in the current slice table.",
            "implication": "Treat era as soft positive evidence or catalog-normalized original-era evidence, not a hard-ish demotion from release_date alone.",
        },
        {
            "title": "Unresolved mentions are small; latent asks are bigger",
            "evidence": f"Only {mentioned_unresolved.get('n', 0):,} turns mention the gold artist name unresolved, while no-target-in-state is much larger.",
            "implication": "The larger miss is not fuzzy matching names. It is representing broad requests like 'popular alternative rock' as candidate generators.",
        },
    ]


def recommended_experiments(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "priority": "P0",
            "name": "Trusted survivor and demotion ablation",
            "why": "Gold items already in fused top-20 or branch top-20 should not vanish before final top-20.",
            "how": "Reserve 3-5 slots for high-confidence exact/discography/BM25/dense winners, and sweep diversify_artists and release-range demotion strengths.",
            "success": "Raises final@20 without lowering union@20; inspect same-artist and release-excluded slices.",
        },
        {
            "priority": "P0",
            "name": "Train a first-stage ranker over union@200",
            "why": f"Union@20 exceeds final@20 by {pp(metrics.get('union20_rank_policy_gap'))}; union@100 gives a {pct(metrics.get('union100'))} ceiling.",
            "how": "Use LambdaMART or logistic pairwise scoring with branch ranks, branch counts, state features, tag/release/popularity features, and policy multipliers.",
            "success": "Improves final Hit@20/NDCG@20 and fusion_efficiency@20 on session-held-out dev evaluation.",
        },
        {
            "priority": "P1",
            "name": "Popularity-aware latent-target retrievers",
            "why": f"{pct(metrics.get('not_in_union20'))} of turns are not in union@20, and {pct(metrics.get('not_in_union100'))} are not in union@100.",
            "how": "Add tag+popularity, goal-conditioned, and similar-artist expansion retrievers keyed by raw user turn plus cleaned state tags.",
            "success": "Raises union@20/100 before any ranker changes, especially broad popular/canonical requests.",
        },
        {
            "priority": "P1",
            "name": "State audit with raw conversation alignment",
            "why": "Raw user turns expose sticky tags, lost constraints, and policy mistakes that compact state hides.",
            "how": "Add an audit that compares current user text, conversation_goal, prior accepted tracks, extracted state, and gold branch ranks.",
            "success": "Reduces no_gt_track_or_artist_in_state and release_range_excludes_gt miss rates in targeted slices.",
        },
    ]


def official_score_summary(source_root: Path, tid: str) -> dict[str, Any]:
    path = source_root / "exp/scores/devset" / f"{tid}.json"
    if not path.exists():
        return {"path": str(path), "available": False}
    scores = read_json(path)
    return {
        "path": str(path),
        "available": True,
        "ndcg@10": scores.get("ndcg@10"),
        "ndcg@20": scores.get("ndcg@20"),
        "hit@20": scores.get("hit@20"),
        "hit@100": scores.get("hit@100"),
        "hit@1000": scores.get("hit@1000"),
        "mrr": scores.get("mrr"),
        "per_turn": scores.get("per_turn", {}),
    }


def configured_lm_type(config_path: Path) -> str:
    if not config_path.exists():
        return "unknown"
    match = re.search(r'^\s*lm_type:\s*["\']?([^"\'\n#]+)', config_path.read_text(encoding="utf-8"), re.M)
    return match.group(1).strip() if match else "unknown"


def scoring_context(config_path: Path) -> dict[str, str]:
    lm_type = configured_lm_type(config_path)
    return {
        "public_dimensions": "nDCG@20, catalog diversity, Distinct-2 lexical diversity, and Gemini LLM-as-a-judge response quality.",
        "formula_note": (
            "Codabench publishes the composite formula: 0.50*nDCG@20 + 0.10*CatalogDiversity + "
            "0.10*LexicalDiversity + 0.30*LLM-Judge. The challenge website lists the same dimensions but says "
            "the exact formula is not published there, so use Codabench as the formula source."
        ),
        "current_response_gap": (
            f"This run is retrieval-only (`lm_type={lm_type}`), so generated responses are empty/unanalyzed. "
            "That leaves the 0.30 LLM-Judge and 0.10 LexicalDiversity lanes unoptimized, plus CatalogDiversity as a "
            "track-list diversity lane."
        ),
        "next_test": "Run a real response generator on dev predictions, then measure Distinct-2 and inspect Gemini-judge style/explanation quality before optimizing prose prompts.",
    }


def load_state_focus_evidence(report_root: Path) -> dict[str, Any]:
    path = report_root / "state_focus" / "state_report_data.json"
    if not path.exists():
        return {"available": False, "path": str(path)}
    data = read_json(path)
    levers: dict[str, dict[str, Any]] = {}
    for raw_row in data.get("measured_levers", []):
        row = dict(raw_row)
        if "RRF-fused" in str(row.get("lever") or ""):
            row["lever"] = str(row.get("lever")).replace("RRF-fused", "Baseline-fused")
        for field in ("result", "decision"):
            text = str(row.get(field) or "")
            text = text.replace("RRF/branch", "current-fusion/branch")
            text = text.replace("RRF-rank fusion", "rank fusion")
            text = text.replace("replace RRF", "replace current fusion")
            text = text.replace("raw RRF", "raw current-fusion")
            row[field] = text
        levers[row.get("lever")] = row
    reranker_bakeoff = dict(data.get("reranker_bakeoff", {}))
    if reranker_bakeoff:
        decision = str(reranker_bakeoff.get("decision") or "")
        decision = decision.replace("RRF-rank fusion", "rank fusion")
        decision = decision.replace("replace RRF", "replace current fusion")
        reranker_bakeoff["decision"] = decision
    return {
        "available": True,
        "path": str(path),
        "measured_levers": levers,
        "routing_counts": data.get("routing_counts", {}),
        "reranker_bakeoff": reranker_bakeoff,
    }


def organizer_dimension_rows(rows: list[dict[str, Any]], dim: str, min_n: int = 0) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get(dim) or "NONE"), []).append(row)
    out = []
    for label, vals in groups.items():
        n = len(vals)
        if n < min_n:
            continue
        final20 = sum(bool(v["final20"]) for v in vals) / n
        union20 = sum(bool(v["union20"]) for v in vals) / n
        union100 = sum(bool(v["union100"]) for v in vals) / n
        union1000 = sum(bool(v["union1000"]) for v in vals) / n
        top_branches = Counter(v["best_branch"] for v in vals if v["union100"]).most_common(4)
        out.append(
            {
                "name": label,
                "n": n,
                "final20_rate": round(final20, 4),
                "union20_rate": round(union20, 4),
                "union100_rate": round(union100, 4),
                "union1000_rate": round(union1000, 4),
                "rank_policy_gap_rate": round(max(0.0, union20 - final20), 4),
                "candidate_gap20_rate": round(max(0.0, 1.0 - union20), 4),
                "candidate_gap100_rate": round(max(0.0, 1.0 - union100), 4),
                "top_union100_branches": [
                    {"name": branch, "n": count} for branch, count in top_branches
                ],
            }
        )
    if dim == "turn":
        out.sort(key=lambda row: int(row["name"]))
    elif dim == "specificity":
        out.sort(key=lambda row: SPECIFICITY_ORDER.get(row["name"], 99))
    else:
        out.sort(key=lambda row: (row["final20_rate"], -row["n"], row["name"]))
    return out


def load_organizer_metadata_analysis(source_root: Path) -> dict[str, Any]:
    from datasets import load_dataset

    ds = load_dataset(HF_CONVERSATION_DATASET, split="test")
    sessions = {row["session_id"]: row for row in ds}
    inline_user_profile_fields = sorted(
        {
            key
            for row in ds
            for key in (row.get("user_profile") or {}).keys()
        }
    )
    standalone_user_metadata = {"checked": False, "fields": [], "num_rows": None, "error": None}
    try:
        user_ds = load_dataset(HF_USER_METADATA_DATASET, split="all_users")
        standalone_user_metadata = {
            "checked": True,
            "fields": sorted(user_ds.features.keys()),
            "num_rows": len(user_ds),
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - best-effort live HF check
        standalone_user_metadata = {
            "checked": True,
            "fields": [],
            "num_rows": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    assessments = {
        (row["session_id"], int(assessment["turn_number"])): (
            assessment.get("goal_progress_assessment") or "TURN1_OR_NONE"
        )
        for row in ds
        for assessment in (row.get("goal_progress_assessments") or [])
    }
    rows: list[dict[str, Any]] = []
    anatomy_path = source_root / "exp/inference/devset/_per_turn_anatomy.jsonl"
    with anatomy_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            anatomy = json.loads(line)
            session_id = anatomy["session_id"]
            turn = int(anatomy["turn_number"])
            session = sessions[session_id]
            goal = session.get("conversation_goal") or {}
            profile = session.get("user_profile") or {}
            branch_rank = anatomy.get("gt_best_branch_rank")
            final_rank = anatomy.get("gt_final_rank")
            rows.append(
                {
                    "session_id": session_id,
                    "turn": turn,
                    "category": goal.get("category") or "NONE",
                    "specificity": goal.get("specificity") or "NONE",
                    "assessment": assessments.get((session_id, turn), "TURN1_OR_NONE"),
                    "culture": profile.get("preferred_musical_culture") or "NONE",
                    "country": profile.get("country_name") or "NONE",
                    "age_group": profile.get("age_group") or "NONE",
                    "final20": final_rank is not None and final_rank <= 20,
                    "union20": branch_rank is not None and branch_rank <= 20,
                    "union100": branch_rank is not None and branch_rank <= 100,
                    "union1000": branch_rank is not None and branch_rank <= 1000,
                    "best_branch": anatomy.get("gt_best_branch") or "NONE",
                }
            )
    category_goal_examples: dict[str, list[str]] = {}
    for row in ds:
        goal = row.get("conversation_goal") or {}
        category = goal.get("category") or "NONE"
        examples = category_goal_examples.setdefault(category, [])
        if len(examples) < 3:
            examples.append(goal.get("listener_goal") or "")
    dims = {
        "category": organizer_dimension_rows(rows, "category"),
        "specificity": organizer_dimension_rows(rows, "specificity"),
        "assessment": organizer_dimension_rows(rows, "assessment"),
        "turn": organizer_dimension_rows(rows, "turn"),
        "culture": organizer_dimension_rows(rows, "culture", min_n=80),
        "country": organizer_dimension_rows(rows, "country", min_n=160),
        "age_group": organizer_dimension_rows(rows, "age_group", min_n=80),
    }
    blind_schema = {"checked": False, "same_metadata_available": None, "error": None}
    try:
        blind = load_dataset("talkpl-ai/TalkPlayData-Challenge-Blind-A", split="test")
        blind_schema = {
            "checked": True,
            "same_metadata_available": all(
                key in blind.features
                for key in ("conversation_goal", "user_profile", "goal_progress_assessments")
            ),
            "num_rows": len(blind),
            "features": sorted(blind.features.keys()),
        }
    except Exception as exc:  # pragma: no cover - best-effort live HF check
        blind_schema = {"checked": True, "same_metadata_available": None, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "n_turns": len(rows),
        "n_sessions": len(ds),
        "anatomy_path": str(anatomy_path),
        "dimensions": dims,
        "category_goal_examples": category_goal_examples,
        "inline_user_profile_fields": inline_user_profile_fields,
        "standalone_user_metadata": standalone_user_metadata,
        "blind_schema": blind_schema,
        "headline": organizer_headline(dims),
    }


def organizer_headline(dims: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    spec = {row["name"]: row for row in dims.get("specificity", [])}
    turns = {row["name"]: row for row in dims.get("turn", [])}
    assessment = {row["name"]: row for row in dims.get("assessment", [])}
    return {
        "ll_final20": spec.get("LL", {}).get("final20_rate"),
        "ll_union20": spec.get("LL", {}).get("union20_rate"),
        "hh_final20": spec.get("HH", {}).get("final20_rate"),
        "hh_union20": spec.get("HH", {}).get("union20_rate"),
        "turn8_final20": turns.get("8", {}).get("final20_rate"),
        "turn8_union20": turns.get("8", {}).get("union20_rate"),
        "does_not_move_final20": assessment.get("DOES_NOT_MOVE_TOWARD_GOAL", {}).get("final20_rate"),
        "does_not_move_union20": assessment.get("DOES_NOT_MOVE_TOWARD_GOAL", {}).get("union20_rate"),
    }


def priority_recommendations(organizer: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, str]]:
    headline = organizer.get("headline", {})
    return [
        {
            "priority": "P0",
            "title": "Train the ranker on true branch union@200, with candidate-varying state features",
            "why": (
                f"Union@20 is {pct(metrics.get('union20'))} while final@20 is {pct(metrics.get('final20'))}; "
                f"turn 8 has final@20 {pct(headline.get('turn8_final20'))} but union@20 {pct(headline.get('turn8_union20'))}."
            ),
            "do": "Build candidates from raw branch union@200, not branches.final. Add branch ranks, branch-count features, popularity, tag overlap, release distance, album/artist recency, candidate artist role, and candidate-varying goal/culture affinity. Keep raw category/specificity/demographics as slices or routing conditioners, not direct within-turn ranking features.",
            "proof": "Session-grouped CV must beat the current fusion baseline on NDCG@20/Hit@20 and on LL + turn 5-8 slices; also report whether raw session constants add any lift.",
        },
        {
            "priority": "P0",
            "title": "Pass organizer goal/profile metadata into routing and candidate features",
            "why": (
                f"LL goals have final@20 {pct(headline.get('ll_final20'))}; HH goals have {pct(headline.get('hh_final20'))}. "
                "The field is available in dev/test and Blind-A, but current inference only passes user_query, user_id, and session_memory."
            ),
            "do": "Extend the batch item and compiler input with conversation_goal.category/specificity/listener_goal plus preferred_musical_culture. Use listener_goal as retrieval/routing text and transform profile/category signals into candidate-varying affinity or popularity features.",
            "proof": "Metadata-aware routing/candidate features should improve LL/category C/K/J slices without regressing HH exact-title slices; raw constants alone are expected to be a no-lift baseline.",
        },
        {
            "priority": "P1",
            "title": "Build goal-family retrievers for the low-union slices",
            "why": "LL/category C/K/I/J have low union@20 or union@100, so a ranker cannot recover enough by itself.",
            "do": "For cover-art goals, add image/album-cover text routing; for broad instrumental/film-score goals, add mood+instrumental+OST tag-popularity retrieval; for popular/exact goals, add canonical popularity and exact-entity probes.",
            "proof": "Raise union@20/100 for LL and categories C/K/J before evaluating final ranking.",
        },
        {
            "priority": "P1",
            "title": "Fix late-turn state carryover and post-fusion suppression",
            "why": "Turns 5-8 keep decent union@20 but lose final@20, so final policy is over-demoting or over-trusting stale context.",
            "do": "Add trusted survivor slots and learn same-artist/album diversity instead of fixed demotions. Add state QA for stale tags and release-year carryover.",
            "proof": "Turn 5-8 final@20 and fusion_efficiency@20 should rise while turn 1-3 does not regress.",
        },
    ]


def field_opportunities(schema: dict[str, Any]) -> list[dict[str, str]]:
    missing_8b = ", ".join(schema.get("missing_required_vector_fields", [])) or "none"
    return [
        {
            "field": "conversation_goal.category/specificity/listener_goal",
            "current": "Available in dev/test and Blind-A HF rows; current inference batch does not pass it into retrieval/compiler state.",
            "use": "Use listener_goal as goal text for broad latent-target retrieval; use category/specificity mostly as routing conditioners, slices, or candidate-varying goal compatibility rather than raw within-turn ranker constants.",
        },
        {
            "field": "raw current user turn and recent user turns",
            "current": "Used to produce state, but not preserved in the compact recall-gap report until this join.",
            "use": "Use for state QA and as a second ranker text feature beside state.turn_intent.",
        },
        {
            "field": "user_profile preferred_musical_culture/country/age_group",
            "current": "UserProfileDB renders only user_id, age_group, gender, country_name; preferred_musical_culture is not used by retrieval/ranking.",
            "use": "Add cautious personalization features and slice checks, especially for culture-specific genres.",
        },
        {
            "field": "goal_progress_assessments",
            "current": "Available from organizer data in dev/test and Blind-A, but not passed into the compiler.",
            "use": "Use previous-turn progress labels as state/ranking features when available; use current-turn labels only for diagnostics/training labels.",
        },
        {
            "field": "track popularity",
            "current": "Used in lookup/backfill paths, not as a calibrated final ranker feature across all candidates.",
            "use": "Model popularity/canonicality explicitly for asks like 'highly popular' or 'widely recognized'.",
        },
        {
            "field": "track tag_list and tag overlap",
            "current": "Used by BM25 and post-fusion boosts; ranker does not learn tag precision by slice.",
            "use": "Use overlap count, exact tag matches, tag rarity, and missed-positive-tag features.",
        },
        {
            "field": "artist_id/album_id continuity",
            "current": "Used for demotion/discography; policy is mostly rule-based.",
            "use": "Learn when same-artist continuation is good, neutral, or bad instead of fixed demotion.",
        },
        {
            "field": "audio/image/CF/text embeddings",
            "current": "Used as branch retrievers; ranker mostly sees their current-fusion positions, not calibrated similarities.",
            "use": "Expose branch ranks, raw distances where safe, modality coverage flags, and cross-branch agreement.",
        },
        {
            "field": "Qwen 8B LanceDB fields",
            "current": f"Trace/config use 8B branches; local source cache is missing: {missing_8b}.",
            "use": "Use Modal LanceDB for reproducible schema/ranker feature extraction when training the ranker.",
        },
    ]


def user_metadata_field_map(organizer: dict[str, Any]) -> dict[str, Any]:
    inline_fields = organizer.get("inline_user_profile_fields") or [
        "age",
        "age_group",
        "country_code",
        "country_name",
        "gender",
        "preferred_language",
        "preferred_musical_culture",
    ]
    standalone = organizer.get("standalone_user_metadata") or {}
    standalone_fields = standalone.get("fields") or [
        "age",
        "age_group",
        "country_code",
        "country_name",
        "gender",
        "user_id",
    ]
    report_profile_fields = ["age_group", "country_name", "preferred_musical_culture"]
    field_info = {
        "user_id": {
            "source": "inline user_profile and standalone User Metadata",
            "meaning": "Stable user join key.",
            "current_use": "Passed into inference; UserProfileDB uses it to join the standalone profile.",
            "ranker_use": "Use only as a join key for profile/user-embedding features; avoid identity memorization in devset CV.",
        },
        "user_split": {
            "source": "inline user_profile in live HF rows",
            "meaning": "Organizer split marker such as test_warm.",
            "current_use": "Not used by retrieval/ranking; not present in the standalone user metadata table.",
            "ranker_use": "Diagnostic only; do not train deployable ranking behavior on split labels.",
        },
        "age": {
            "source": "inline user_profile and standalone User Metadata",
            "meaning": "Exact user age.",
            "current_use": "Available, but not rendered by the default UserProfileDB prompt string.",
            "ranker_use": "Low-priority weak feature or slice only; avoid hard personalization from demographics.",
        },
        "age_group": {
            "source": "inline user_profile, standalone User Metadata, and report examples",
            "meaning": "Decade bucket such as 20s or 30s.",
            "current_use": "Rendered into the response-generation profile string; carried in report examples and slices.",
            "ranker_use": "Use as a weak/calibrated feature and diagnostic slice, not as a filter.",
        },
        "country_code": {
            "source": "inline user_profile and standalone User Metadata",
            "meaning": "ISO country code.",
            "current_use": "Available, but not rendered by the default profile string.",
            "ranker_use": "Use for geography/culture diagnostics or cautious localization features.",
        },
        "country_name": {
            "source": "inline user_profile, standalone User Metadata, and report examples",
            "meaning": "Full country name.",
            "current_use": "Rendered into the response-generation profile string; report slices also track country.",
            "ranker_use": "Use cautiously for cultural priors or localized music requests; never override explicit user intent.",
        },
        "gender": {
            "source": "inline user_profile and standalone User Metadata",
            "meaning": "Organizer-provided gender label.",
            "current_use": "Rendered into the response-generation profile string; not used by retrieval/ranking.",
            "ranker_use": "Prefer diagnostics/guardrails only; avoid ranking decisions driven by gender.",
        },
        "preferred_language": {
            "source": "inline user_profile in conversation rows",
            "meaning": "Preferred language for the session/user.",
            "current_use": "Available in organizer rows but not passed into compiler retrieval/ranking.",
            "ranker_use": "Useful for response style and multilingual/local music cues; weak ranking feature if explicit request is ambiguous.",
        },
        "preferred_musical_culture": {
            "source": "inline user_profile and report examples",
            "meaning": "Organizer cultural/music-affinity label, such as Punk/Hardcore Subculture.",
            "current_use": "Used only for this report's examples/slices; not used by current retrieval/ranking.",
            "ranker_use": "Highest-value user metadata feature to test for ranker/router personalization, especially culture-specific genre asks.",
        },
    }
    rows = []
    for field in sorted(set(inline_fields) | set(standalone_fields) | set(report_profile_fields)):
        info = field_info.get(field, {})
        rows.append(
            {
                "field": field,
                "source": info.get("source", "Observed in metadata"),
                "meaning": info.get("meaning", ""),
                "current_use": info.get("current_use", "Available, but current use is not explicitly mapped."),
                "ranker_use": info.get("ranker_use", "Treat as a candidate feature only after leakage and fairness checks."),
                "in_inline_profile": field in inline_fields,
                "in_standalone_user_metadata": field in standalone_fields,
                "in_report_examples": field in report_profile_fields,
            }
        )
    return {
        "inline_user_profile_fields": inline_fields,
        "standalone_user_metadata": standalone,
        "report_example_profile_fields": report_profile_fields,
        "current_pipeline_summary": (
            "Current inference passes user_id and session_memory into the compiler. "
            "UserProfileDB renders only user_id, age_group, gender, and country_name for response generation; "
            "preferred_musical_culture and preferred_language are not used by retrieval/ranking."
        ),
        "ranker_summary": (
            "For the trained-ranker path, preferred_musical_culture is the most actionable user-profile field. "
            "country_name/country_code can be weak context; age, age_group, and gender should be diagnostics or guarded weak features."
        ),
        "fields": rows,
    }


def standalone_context(organizer: dict[str, Any]) -> dict[str, Any]:
    dims = organizer.get("dimensions", {})
    specificity_by_name = {row["name"]: row for row in dims.get("specificity", [])}
    category_by_name = {row["name"]: row for row in dims.get("category", [])}
    examples = organizer.get("category_goal_examples", {})

    specificity_rows = []
    for code in ("LL", "LH", "HL", "HH"):
        metric_row = specificity_by_name.get(code, {})
        info = SPECIFICITY_GLOSSARY[code]
        specificity_rows.append(
            {
                "code": code,
                **info,
                "n": metric_row.get("n"),
                "final20_rate": metric_row.get("final20_rate"),
                "union20_rate": metric_row.get("union20_rate"),
                "union100_rate": metric_row.get("union100_rate"),
                "candidate_gap20_rate": metric_row.get("candidate_gap20_rate"),
                "rank_policy_gap_rate": metric_row.get("rank_policy_gap_rate"),
            }
        )

    focus_categories = []
    for code in ("C", "K", "I", "J"):
        metric_row = category_by_name.get(code, {})
        info = CATEGORY_FOCUS_GLOSSARY[code]
        focus_categories.append(
            {
                "code": code,
                **info,
                "examples": examples.get(code, [])[:3],
                "n": metric_row.get("n"),
                "final20_rate": metric_row.get("final20_rate"),
                "union20_rate": metric_row.get("union20_rate"),
                "union100_rate": metric_row.get("union100_rate"),
                "candidate_gap20_rate": metric_row.get("candidate_gap20_rate"),
                "rank_policy_gap_rate": metric_row.get("rank_policy_gap_rate"),
            }
        )

    return {
        "label_caveat": (
            "The repo docs and HF schema expose conversation_goal.category, specificity, and listener_goal, "
            "but do not provide official human-readable names for category codes. The descriptions below are "
            "derived from the observed listener_goal examples in this devset."
        ),
        "why_ll_c_k_i_j": (
            "LL and categories C/K/I/J are called out because their union@20 or union@100 rates show a candidate-generation "
            "problem. A trained ranker can recover near misses, but it cannot recover turns where the gold track never enters "
            "the union pool."
        ),
        "specificity": specificity_rows,
        "focus_categories": focus_categories,
        "state_fields": STATE_FIELD_REFERENCE,
        "failed_example_inventory": [
            {
                "item": "Raw conversation",
                "what_we_have": "Current user turn, previous user turn, and recent conversation messages joined from the HF test split.",
                "why_it_matters": "Lets us see whether the extracted state dropped constraints or over-carried stale context.",
            },
            {
                "item": "Organizer metadata",
                "what_we_have": "conversation_goal.category, specificity, listener_goal, goal_progress_assessments, and compact user profile.",
                "why_it_matters": "Gives goal family and deployable metadata features for routing/ranking.",
            },
            {
                "item": "Ground truth and ranks",
                "what_we_have": "GT track/artist, final rank, fused rank, best branch, min branch rank, and per-branch ranks.",
                "why_it_matters": "Separates candidate-generation gaps from current-fusion/post-fusion/finalization losses.",
            },
            {
                "item": "Extracted/resolved state audit",
                "what_we_have": "intent mode, mentioned/resolved entities, positive/rejected tags, hard filters, year range, lyrical theme, anchors, played count, and anchor artists.",
                "why_it_matters": "Shows whether state is wrong, incomplete, stale, or simply not used strongly enough.",
            },
            {
                "item": "Action label",
                "what_we_have": "Case bucket, diagnosis, and smallest next test.",
                "why_it_matters": "Turns examples into work items: retriever/state gap, ranker gap, or policy/demotion gap.",
            },
        ],
    }


def load_task_mode_state_addendum(source_root: Path) -> dict[str, Any]:
    """Pull compact task-mode/state findings from the local recall anatomy artifact.

    The source artifact embeds a large JavaScript object; keep this addendum
    small so our report stays readable and agent-friendly.
    """
    source_path = source_root / "exp/inference/devset/recall_anatomy_report.html"
    addendum: dict[str, Any] = {
        "available": False,
        "error": None,
    }
    if not source_path.exists():
        addendum["error"] = "Task-mode/state anatomy artifact was not found."
        return addendum

    try:
        text = source_path.read_text(encoding="utf-8")
        start = text.index("const D = ") + len("const D = ")
        end = text.index("\nconst C=", start)
        payload = text[start:end].strip()
        if payload.endswith(";"):
            payload = payload[:-1]
        data = json.loads(payload)
    except Exception as exc:  # noqa: BLE001 - report parse failure, do not crash generation.
        addendum["error"] = f"Could not parse task-mode/state anatomy payload: {exc}"
        return addendum

    honest = data.get("honest", {})
    taskmix = data.get("taskmix", {})
    state = data.get("state", {})
    extract = data.get("extract", {})
    fixes = data.get("fixes", {})
    task_modes = [
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
        for row in taskmix.get("modes", [])
    ]
    scorecard = [
        {
            "item": row.get("item"),
            "verdict": row.get("verdict"),
            "stat": row.get("stat"),
            "detail": row.get("detail"),
        }
        for row in state.get("scorecard", [])
    ]
    taxonomy = [
        {
            "cue": row.get("cue"),
            "role": row.get("role"),
            "current": row.get("current"),
            "ideal": row.get("ideal"),
        }
        for row in extract.get("taxonomy", [])
    ]
    graded_bad = [
        {
            "id": row.get("id"),
            "intent": row.get("intent"),
            "ask": clean_text(row.get("ask"), 180),
            "anchored": clean_text(row.get("anchored"), 140),
            "reason": clean_text(row.get("reason"), 220),
            "ideal": clean_text(row.get("ideal"), 220),
        }
        for row in extract.get("graded", [])
        if row.get("verdict") == "bad"
    ][:5]
    for row in scorecard:
        if str(row.get("item") or "").strip().lower() == "hidden_target_search":
            row["verdict"] = "inert"
            row["stat"] = "391 fires; 0 weighted-routing consumption"
            row["detail"] = "The routing tag fires in the trace, but routing_boost is empty, so the bug is non-consumption rather than non-extraction."

    feature_catalog = dict(fixes.get("feature_catalog") or {})
    feature_catalog["build"] = [list(row) for row in feature_catalog.get("build", [])]
    for row in feature_catalog["build"]:
        if row and str(row[0]).strip().lower() == "album-affinity":
            row[1] = "measured about +6pp Hit@20 ceiling; prototype before commit"
    caveats = [list(row) for row in (data.get("caveats") or {}).get("items", [])]
    for row in caveats:
        if not row:
            continue
        title = str(row[0])
        if title.startswith("Response TEXT is unmeasured"):
            row[1] = (
                "lm_type=dummy; Codabench weights response quality and lexical diversity at 0.30 and 0.10 respectively, "
                "plus catalog diversity at 0.10. Run a real generator over dev predictions and measure response "
                "quality/diversity separately."
            )
        elif title.startswith("Album +8pp"):
            row[0] = "Album-affinity upside corrected to ~+6pp ceiling"
            row[1] = (
                "Measured counterfactual: 479 of 964 same-album misses are rescuable by a ranking boost "
                "(GT at fused rank 21-100). Still high-confidence, but prototype and measure before committing."
            )

    addendum.update(
        {
            "available": True,
            "n_turns": len(data.get("turns", [])),
            "n_branches": len(data.get("branches", [])),
            "honest_ceiling": {
                "curve": honest.get("curve", []),
                "ceiling_k": honest.get("ceiling_k"),
                "ceiling": honest.get("ceiling"),
                "gap": honest.get("gap"),
                "gap_n": honest.get("gap_n"),
                "deep_gap_n": honest.get("gap_deep"),
                "deep_gap_pct": honest.get("gap_deep_pct"),
                "absent_gap_n": honest.get("gap_absent"),
                "absent_gap_pct": honest.get("gap_absent_pct"),
                "fused20": honest.get("fused20"),
                "fused100": honest.get("fused100"),
            },
            "evaluation": {
                "accepted": [
                    "Use union@100 as the honest first-stage ranker ceiling while keeping union@20 as the primary gap boundary.",
                    "Split the work by turn-level mode: continuation is mostly ranking/within-artist selection; new-artist is the largest candidate-generation gap.",
                    "Add relation-typed state for named artists: seed, satisfied, contrast, history, rejected. Binary positive/negative anchoring is too blunt.",
                    "Treat category/specificity and raw demographics as session-level context, not as candidate-varying ranker features.",
                    "Promote album-affinity, artist-recency, is_new_artist, user-CF, and genre/popularity priors into the first ranker feature set.",
                ],
                "caveated": [
                    "Do not use union@1000 as the headline ranker target; it is an oracle over thousands of candidates.",
                    "The continuation/new-artist taxonomy is partly GT-defined, so validate it with current-turn intent labels before training against it.",
                    "New-artist popularity/CF fixes are plausible but not counterfactually verified yet.",
                    "Album-affinity has a measured rescue pool, but the report itself corrects the upside to a prototype-before-commit estimate.",
                    "Response text quality is a separate scored gap: Codabench weights LLM-Judge at 0.30 and LexicalDiversity at 0.10, while current lm_type=dummy produces empty responses.",
                ],
            },
            "task_modes": task_modes,
            "task_cat_note": taskmix.get("cat_note"),
            "intent_gap_note": (taskmix.get("intent_gap") or {}).get("note"),
            "state": {
                "novelty": state.get("novelty"),
                "recycle_overall": state.get("recycle_overall"),
                "gtnew_overall": state.get("gtnew_overall"),
                "entity_by_turn": state.get("entity_by_turn", []),
                "scorecard": scorecard,
                "year": state.get("year"),
                "rejection": state.get("rejection"),
            },
            "extraction": {
                "taxonomy": taxonomy,
                "grounding": extract.get("grounding"),
                "corrections": extract.get("corrections", []),
                "bad_examples": graded_bad,
            },
            "fixes": {
                "continuation": fixes.get("continuation"),
                "newartist": fixes.get("newartist"),
                "album": fixes.get("album"),
                "feature_catalog": feature_catalog,
                "ruled_out": fixes.get("ruledout", []),
                "demographics": fixes.get("demographics"),
                "category_routing": fixes.get("category_routing"),
            },
            "caveats": caveats,
        }
    )
    return addendum


def build_prompt() -> str:
    return """Build a decision-ready Music CRS devset recall-gap report for state_ranker_v10_rrf_devset.

Sources to inspect:
- exp/inference/devset/state_ranker_v10_rrf_devset_trace.jsonl
- exp/inference/devset/state_ranker_v10_rrf_devset.json
- evaluator/exp/ground_truth/devset.json
- experiments/analysis/devset_recall_gap_state_ranker_v10_2026_06_14/recall_gap_data.json
- experiments/analysis/devset_recall_gap_state_ranker_v10_2026_06_14/branch_diagnostics.json
- configs/state_ranker_v10_rrf_devset.yaml
- docs/data.md, docs/architectures/session_state.md, docs/architectures/v0plus_retrieval.md
- Hugging Face TalkPlayData-Challenge-Dataset test split for raw conversation turns
- Hugging Face organizer metadata: conversation_goal.category/specificity/listener_goal, goal_progress_assessments, user_profile.preferred_musical_culture
- Hugging Face Blind-A schema check to determine whether organizer metadata is usable at inference time
- Local or Modal LanceDB catalog when schema/ranker feature fields are needed

Central questions:
1. Treat union@20 as the first decision boundary. If gold is not in union@20, classify it as a candidate-generation/state/retriever gap. If gold is in union@20 but not final top-20, classify it as fusion, ranker, post-fusion, or finalization loss.
2. Also report union@100 and union@1000 so we can separate near misses from deep retriever misses.
3. Diagnose whether misses come from state being wrong or incomplete. Compare raw user turns and recent conversation against trace.state.turn_intent, mentioned_entities, release_year_range, routing_tags, resolver anchors, and exploration_policy.
4. Check whether fields in the data are not being used enough: conversation_goal, user_profile, profile culture, track popularity, tags, duration, artist/album IDs, track/user embeddings, and LanceDB vector fields.
5. Decide whether the next step should be better state, better use of state, better retrievers, post-fusion fixes, or replacing the current fusion stage with a trained ranker.
6. Include concrete examples of gaps or bugs. Each example should show session_id, turn_number, raw user turn, recent context, ground-truth track/artist, final/fused/branch ranks, state fields, branch ranks, post-fusion symptoms, classification, and the smallest fix or experiment.
7. Separate confirmed bugs/config gaps from plausible gaps. Do not call something a bug unless the code/config/artifact proves it.

Output:
- Primary: visually clear HTML report with charts and an example explorer.
- Companion: Markdown report for future agents.
- Include the full prompt and source/caveat notes.
"""


def svg_text(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def write_vertical_svg(path: Path, title: str, rows: list[tuple[str, float, str]], *, max_value: float = 100.0) -> str:
    width = 920
    height = 520
    left = 70
    right = 36
    top = 70
    bottom = 72
    plot_w = width - left - right
    plot_h = height - top - bottom
    gap = 26
    bar_w = (plot_w - gap * (len(rows) - 1)) / max(1, len(rows))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{svg_text(title)}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="{left}" y="34" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" fill="#172033">{svg_text(title)}</text>',
    ]
    for tick in range(0, 101, 20):
        y = top + plot_h - (tick / max_value) * plot_h
        parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" font-family="Inter, Arial, sans-serif" font-size="12" fill="#5b6575">{tick}%</text>')
    for idx, (label, value, color) in enumerate(rows):
        x = left + idx * (bar_w + gap)
        bar_h = max(0, min(value, max_value)) / max_value * plot_h
        y = top + plot_h - bar_h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="6" fill="{color}"/>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 10:.1f}" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="14" font-weight="700" fill="#172033">{value:.1f}%</text>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{height - 32}" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="13" fill="#172033">{svg_text(label)}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")
    return path.name


def write_horizontal_svg(path: Path, title: str, rows: list[tuple[str, float, str]], *, max_value: float | None = None) -> str:
    width = 1000
    row_h = 42
    top = 68
    bottom = 36
    left = 320
    right = 80
    height = top + bottom + row_h * len(rows)
    plot_w = width - left - right
    maxv = max_value if max_value is not None else max([value for _, value, _ in rows] + [1]) * 1.18
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{svg_text(title)}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="28" y="34" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" fill="#172033">{svg_text(title)}</text>',
    ]
    for idx, (label, value, color) in enumerate(rows):
        y = top + idx * row_h
        bar_w = max(0, value) / maxv * plot_w
        parts.append(f'<text x="{left - 14}" y="{y + 20}" text-anchor="end" font-family="Inter, Arial, sans-serif" font-size="13" fill="#172033">{svg_text(label)}</text>')
        parts.append(f'<rect x="{left}" y="{y + 4}" width="{plot_w}" height="22" rx="6" fill="#edf0f4"/>')
        parts.append(f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="22" rx="6" fill="{color}"/>')
        parts.append(f'<text x="{left + bar_w + 8:.1f}" y="{y + 20}" font-family="Inter, Arial, sans-serif" font-size="13" font-weight="700" fill="#172033">{value:.1f}%</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")
    return path.name


def write_grouped_horizontal_svg(
    path: Path,
    title: str,
    rows: list[tuple[str, float, float]],
    *,
    max_value: float = 100.0,
) -> str:
    width = 1020
    row_h = 58
    top = 82
    bottom = 40
    left = 350
    right = 90
    height = top + bottom + row_h * len(rows)
    plot_w = width - left - right
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{svg_text(title)}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="28" y="34" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" fill="#172033">{svg_text(title)}</text>',
        '<rect x="28" y="52" width="14" height="14" rx="3" fill="#0f766e"/><text x="50" y="64" font-family="Inter, Arial, sans-serif" font-size="13" fill="#5b6575">union@20</text>',
        '<rect x="128" y="52" width="14" height="14" rx="3" fill="#2563eb"/><text x="150" y="64" font-family="Inter, Arial, sans-serif" font-size="13" fill="#5b6575">final@20</text>',
    ]
    for idx, (label, union_value, final_value) in enumerate(rows):
        y = top + idx * row_h
        u_w = max(0, union_value) / max_value * plot_w
        f_w = max(0, final_value) / max_value * plot_w
        parts.append(f'<text x="{left - 14}" y="{y + 27}" text-anchor="end" font-family="Inter, Arial, sans-serif" font-size="13" fill="#172033">{svg_text(label)}</text>')
        parts.append(f'<rect x="{left}" y="{y + 4}" width="{plot_w}" height="18" rx="5" fill="#edf0f4"/>')
        parts.append(f'<rect x="{left}" y="{y + 4}" width="{u_w:.1f}" height="18" rx="5" fill="#0f766e"/>')
        parts.append(f'<text x="{left + u_w + 8:.1f}" y="{y + 18}" font-family="Inter, Arial, sans-serif" font-size="12" fill="#172033">{union_value:.1f}%</text>')
        parts.append(f'<rect x="{left}" y="{y + 28}" width="{plot_w}" height="18" rx="5" fill="#edf0f4"/>')
        parts.append(f'<rect x="{left}" y="{y + 28}" width="{f_w:.1f}" height="18" rx="5" fill="#2563eb"/>')
        parts.append(f'<text x="{left + f_w + 8:.1f}" y="{y + 42}" font-family="Inter, Arial, sans-serif" font-size="12" fill="#172033">{final_value:.1f}%</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")
    return path.name


def save_coverage_chart(report: dict[str, Any], out_dir: Path) -> str:
    metrics = metric_lookup(report)
    rows = [
        ("Final@20", metrics.get("final_hit", {}).get("20", 0) * 100, "#2563eb"),
        ("Union@20", metrics.get("union_hit", {}).get("20", 0) * 100, "#0f766e"),
        ("Union@100", metrics.get("union_hit", {}).get("100", 0) * 100, "#7c3aed"),
        ("Union@1000", metrics.get("union_hit", {}).get("1000", 0) * 100, "#c2410c"),
    ]
    return write_vertical_svg(out_dir / "coverage_ceiling.svg", "Candidate ceilings vs current final top-20", rows)


def save_gap_chart(report: dict[str, Any], out_dir: Path) -> str:
    rows = list(reversed(report.get("gap_buckets", [])[:7]))
    chart_rows = [
        (
            r["name"].replace("_", " "),
            float(r["pct"]),
            "#2563eb" if "final" in r["name"] else "#c2410c" if "not_in" in r["name"] else "#0f766e",
        )
        for r in rows
    ]
    return write_horizontal_svg(out_dir / "gap_buckets.svg", "Failure buckets by union/final boundary", chart_rows)


def save_branch_chart(report: dict[str, Any], out_dir: Path) -> str:
    rows = sorted(report.get("branches", []), key=lambda r: r.get("recall@20", 0), reverse=True)[:10]
    rows = list(reversed(rows))
    chart_rows = [(short_branch_name(r["name"]), r.get("recall@20", 0) * 100, "#2563eb") for r in rows]
    return write_horizontal_svg(out_dir / "branch_recall20.svg", "Top branch top-20 recall", chart_rows)


def save_state_chart(report: dict[str, Any], out_dir: Path) -> str:
    rows = report.get("dimensions", {}).get("entity_bucket", [])
    rows = sorted(rows, key=lambda r: r.get("n", 0), reverse=True)[:5]
    rows = list(reversed(rows))
    chart_rows = [
        (
            r["name"].replace("_", " "),
            r.get("union20_rate", 0) * 100,
            r.get("final_hit20_rate", 0) * 100,
        )
        for r in rows
    ]
    return write_grouped_horizontal_svg(
        out_dir / "state_entity_union20.svg",
        "Entity grounding changes the union@20 ceiling",
        chart_rows,
    )


def save_organizer_grouped_chart(
    organizer: dict[str, Any],
    out_dir: Path,
    dim: str,
    filename: str,
    title: str,
    *,
    limit: int | None = None,
) -> str:
    rows = organizer.get("dimensions", {}).get(dim, [])
    if limit is not None:
        rows = rows[:limit]
    chart_rows = [
        (
            row["name"],
            row.get("union20_rate", 0) * 100,
            row.get("final20_rate", 0) * 100,
        )
        for row in rows
    ]
    return write_grouped_horizontal_svg(out_dir / filename, title, chart_rows)


def short_branch_name(name: str) -> str:
    replacements = {
        "dense.qwen_8b.metadata.metadata_qwen3_embedding_8b": "qwen8 metadata",
        "dense.qwen_8b.attributes.attributes_qwen3_embedding_8b": "qwen8 attributes",
        "dense.qwen_0_6b.metadata.metadata_qwen3_embedding_0_6b": "qwen0.6 metadata",
        "dense.qwen_0_6b.attributes.attributes_qwen3_embedding_0_6b": "qwen0.6 attributes",
        "dense.qwen_0_6b.lyric.lyrics_qwen3_embedding_0_6b": "qwen0.6 lyric",
        "dense.clap_text.sonic.audio_laion_clap": "CLAP text sonic",
        "centroid.anchor_tracks.image_siglip2": "anchor image",
        "centroid.anchor_tracks.audio_laion_clap": "anchor audio",
        "centroid.anchor_tracks.cf_bpr": "anchor CF",
        "centroid.user.cf_bpr": "user CF",
        "lookup.resolved_artist_discography": "artist discography",
        "lookup.era_popularity": "era popularity",
    }
    return replacements.get(name, name.replace("_", " "))


def generate_charts(report: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "coverage": save_coverage_chart(report, out_dir),
        "gaps": save_gap_chart(report, out_dir),
        "branches": save_branch_chart(report, out_dir),
        "state": save_state_chart(report, out_dir),
    }


def generate_organizer_charts(organizer: dict[str, Any], out_dir: Path) -> dict[str, str]:
    return {
        "organizer_specificity": save_organizer_grouped_chart(
            organizer,
            out_dir,
            "specificity",
            "organizer_specificity.svg",
            "Specificity: low-specificity goals need better candidates",
        ),
        "organizer_turns": save_organizer_grouped_chart(
            organizer,
            out_dir,
            "turn",
            "organizer_turns.svg",
            "Turns: late conversation ranking degrades",
        ),
        "organizer_categories": save_organizer_grouped_chart(
            organizer,
            out_dir,
            "category",
            "organizer_categories.svg",
            "Goal categories: worst slices by final@20",
            limit=8,
        ),
        "organizer_assessment": save_organizer_grouped_chart(
            organizer,
            out_dir,
            "assessment",
            "organizer_assessment.svg",
            "Organizer progress labels expose the hard cases",
        ),
    }


def html_report(data: dict[str, Any]) -> str:
    payload = safe_json_script(data)
    organizer = data.get("organizer", {})
    org_headline = organizer.get("headline", {})
    category_examples = organizer.get("category_goal_examples", {})
    user_meta = data.get("user_metadata_fields", {})
    context = data.get("standalone_context", {})
    mode_state = data.get("task_mode_state_addendum", {})
    scoring = data.get("scoring_context", {})
    state_evidence = data.get("state_focus_evidence", {})
    new_artist_mode = next(
        (row for row in mode_state.get("task_modes", []) if str(row.get("mode") or "").upper() == "NEW-ARTIST"),
        {},
    )
    category_table_html = "".join(
        (
            "<tr>"
            f"<td>{html.escape(row['name'])}</td>"
            f"<td>{row['n']:,}</td>"
            f"<td>{html.escape(clean_text(' | '.join(category_examples.get(row['name'], [])[:2]), 220))}</td>"
            f"<td>{pct(row.get('final20_rate'))}</td>"
            f"<td>{pct(row.get('union20_rate'))}</td>"
            f"<td>{pct(row.get('union100_rate'))}</td>"
            f"<td>{pp(row.get('rank_policy_gap_rate'))}</td>"
            f"<td>{pct(row.get('candidate_gap20_rate'))}</td>"
            "</tr>"
        )
        for row in organizer.get("dimensions", {}).get("category", [])
    )
    specificity_table_html = "".join(
        (
            "<tr>"
            f"<td><span class=\"mono\">{html.escape(row['code'])}</span></td>"
            f"<td>{html.escape(row['label'])}</td>"
            f"<td>{html.escape(row['meaning'])}<br><span class=\"mono\">Example: {html.escape(row['example'])}</span></td>"
            f"<td>{row.get('n') or 0:,}</td>"
            f"<td>{pct(row.get('final20_rate'))}</td>"
            f"<td>{pct(row.get('union20_rate'))}</td>"
            f"<td>{pct(row.get('union100_rate'))}</td>"
            f"<td>{html.escape(row['why_it_matters'])}</td>"
            "</tr>"
        )
        for row in context.get("specificity", [])
    )
    focus_category_html = "".join(
        (
            '<div class="finding">'
            f"<strong>Category {html.escape(row['code'])}: {html.escape(row['description'])}</strong>"
            f"<p><span class=\"mono\">n={row.get('n') or 0:,}; Final@20 {pct(row.get('final20_rate'))}; Union@20 {pct(row.get('union20_rate'))}; Union@100 {pct(row.get('union100_rate'))}</span></p>"
            f"<p><strong>Why it gaps:</strong> {html.escape(row['why_gap'])}</p>"
            f"<p><strong>Work on:</strong> {html.escape(row['work_on'])}</p>"
            f"<p><strong>Observed goals:</strong> {html.escape(' | '.join(row.get('examples', [])))}</p>"
            "</div>"
        )
        for row in context.get("focus_categories", [])
    )
    state_fields_table_html = "".join(
        (
            "<tr>"
            f"<td><span class=\"mono\">{html.escape(row['field'])}</span></td>"
            f"<td>{html.escape(row['meaning'])}</td>"
            f"<td>{html.escape(row['retrieval_use'])}</td>"
            f"<td>{html.escape(row['example_use'])}</td>"
            "</tr>"
        )
        for row in context.get("state_fields", [])
    )
    failed_inventory_html = "".join(
        (
            "<tr>"
            f"<td>{html.escape(row['item'])}</td>"
            f"<td>{html.escape(row['what_we_have'])}</td>"
            f"<td>{html.escape(row['why_it_matters'])}</td>"
            "</tr>"
        )
        for row in context.get("failed_example_inventory", [])
    )
    user_meta_table_html = "".join(
        (
            "<tr>"
            f"<td><span class=\"mono\">{html.escape(row['field'])}</span></td>"
            f"<td>{html.escape(row['source'])}</td>"
            f"<td>{html.escape(row['meaning'])}</td>"
            f"<td>{html.escape(row['current_use'])}</td>"
            f"<td>{html.escape(row['ranker_use'])}</td>"
            "</tr>"
        )
        for row in user_meta.get("fields", [])
    )
    priority_html = "".join(
        (
            '<div class="finding">'
            f"<strong>{html.escape(row['priority'])}: {html.escape(row['title'])}</strong>"
            f"<p>{html.escape(row['why'])}</p>"
            f"<p><strong>Do:</strong> {html.escape(row['do'])}</p>"
            f"<p><strong>Proof:</strong> {html.escape(row['proof'])}</p>"
            "</div>"
        )
        for row in data.get("priority_recommendations", [])
    )
    mode_state_honest = mode_state.get("honest_ceiling") or {}
    mode_state_accepted_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in (mode_state.get("evaluation") or {}).get("accepted", [])
    )
    mode_state_caveated_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in (mode_state.get("evaluation") or {}).get("caveated", [])
    )
    mode_state_task_modes_html = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(row.get('mode') or ''))}</td>"
            f"<td>{html.escape(str(row.get('description') or ''))}</td>"
            f"<td>{int(row.get('n') or 0):,}</td>"
            f"<td>{pct(row.get('share'))}</td>"
            f"<td>{pct(row.get('hit20'))}</td>"
            f"<td>{pct(row.get('ndcg20'))}</td>"
            f"<td>{pct(row.get('gap50'))}</td>"
            f"<td>{pct(row.get('miss_share'))}</td>"
            f"<td>{html.escape(str(row.get('verdict') or ''))}</td>"
            "</tr>"
        )
        for row in mode_state.get("task_modes", [])
    )
    mode_state_taxonomy_html = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(row.get('cue') or ''))}</td>"
            f"<td><span class=\"mono\">{html.escape(str(row.get('role') or ''))}</span></td>"
            f"<td>{html.escape(str(row.get('current') or ''))}</td>"
            f"<td>{html.escape(str(row.get('ideal') or ''))}</td>"
            "</tr>"
        )
        for row in (mode_state.get("extraction") or {}).get("taxonomy", [])
    )
    mode_state_scorecard_html = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(row.get('item') or ''))}</td>"
            f"<td><span class=\"mono\">{html.escape(str(row.get('verdict') or ''))}</span></td>"
            f"<td>{html.escape(str(row.get('stat') or ''))}</td>"
            f"<td>{html.escape(str(row.get('detail') or ''))}</td>"
            "</tr>"
        )
        for row in (mode_state.get("state") or {}).get("scorecard", [])
    )
    mode_state_bad_examples_html = "".join(
        (
            '<div class="finding">'
            f"<strong>{html.escape(str(row.get('id') or ''))}: {html.escape(str(row.get('intent') or ''))}</strong>"
            f"<p><strong>Ask:</strong> {html.escape(str(row.get('ask') or ''))}</p>"
            f"<p><strong>Anchored:</strong> {html.escape(str(row.get('anchored') or ''))}</p>"
            f"<p><strong>Why bad:</strong> {html.escape(str(row.get('reason') or ''))}</p>"
            f"<p><strong>Ideal:</strong> {html.escape(str(row.get('ideal') or ''))}</p>"
            "</div>"
        )
        for row in (mode_state.get("extraction") or {}).get("bad_examples", [])
    )
    mode_state_feature_build_html = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str((row or [''])[0]))}</td>"
            f"<td>{html.escape(str((row or ['', ''])[1] if len(row or []) > 1 else ''))}</td>"
            f"<td>{html.escape(str((row or ['', '', ''])[2] if len(row or []) > 2 else ''))}</td>"
            "</tr>"
        )
        for row in ((mode_state.get("fixes") or {}).get("feature_catalog") or {}).get("build", [])
    )
    mode_state_do_not_html = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in ((mode_state.get("fixes") or {}).get("feature_catalog") or {}).get("dont", [])
    )
    mode_state_ruled_out_html = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str((row or [''])[0]))}</td>"
            f"<td>{html.escape(str((row or ['', ''])[1] if len(row or []) > 1 else ''))}</td>"
            "</tr>"
        )
        for row in (mode_state.get("fixes") or {}).get("ruled_out", [])
    )
    mode_state_open_caveats_html = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str((row or [''])[0]))}</td>"
            f"<td>{html.escape(str((row or ['', ''])[1] if len(row or []) > 1 else ''))}</td>"
            "</tr>"
        )
        for row in mode_state.get("caveats", [])
    )
    reranker_bakeoff = state_evidence.get("reranker_bakeoff") or {}
    reranker_evidence_html = ""
    if reranker_bakeoff.get("available"):
        reranker_evidence_html = (
            '<div class="callout">'
            "<strong>Measured ranker evidence:</strong> "
            f"adjacent-pool bakeoff NDCG@20 {float(reranker_bakeoff.get('base_ndcg20') or 0):.4f} → "
            f"{float(reranker_bakeoff.get('rerank_ndcg20') or 0):.4f} "
            f"({pct(reranker_bakeoff.get('relative_ndcg20'))} relative); Hit@20 "
            f"{float(reranker_bakeoff.get('base_hit20') or 0):.4f} → {float(reranker_bakeoff.get('rerank_hit20') or 0):.4f}. "
            "Revalidate on the all-retrievers union pool before shipping."
            "</div>"
        )
    styles = """
    :root {
      --ink: #172033;
      --muted: #5b6575;
      --line: #d8dde6;
      --paper: #f7f8fa;
      --panel: #ffffff;
      --blue: #2563eb;
      --teal: #0f766e;
      --orange: #c2410c;
      --violet: #7c3aed;
    }
    * { box-sizing: border-box; }
    html { overflow-x: hidden; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--paper);
      line-height: 1.5;
      overflow-x: hidden;
    }
    section, .wrap, .panel, .example-card, details { min-width: 0; }
    header {
      border-bottom: 1px solid var(--line);
      background: #fff;
    }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 28px 22px; }
    h1 { margin: 0; font-size: clamp(28px, 4vw, 46px); line-height: 1.05; letter-spacing: 0; }
    h2 { margin: 0 0 14px; font-size: 24px; letter-spacing: 0; }
    h3 { margin: 0 0 8px; font-size: 17px; letter-spacing: 0; }
    p { margin: 0 0 12px; overflow-wrap: anywhere; }
    .subtitle { color: var(--muted); max-width: 880px; margin-top: 12px; font-size: 16px; }
    nav {
      position: sticky;
      top: 0;
      z-index: 5;
      background: rgba(255,255,255,.96);
      border-bottom: 1px solid var(--line);
    }
    nav .wrap { max-width: 100%; padding-top: 10px; padding-bottom: 10px; display: flex; gap: 8px; overflow-x: auto; }
    nav a { color: var(--muted); text-decoration: none; border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px; white-space: nowrap; }
    nav a:hover { color: var(--ink); border-color: var(--ink); }
    nav a.report-link { color: var(--blue); border-color: var(--blue); background: #f4f8ff; }
    nav a.report-link:hover { background: #eaf2ff; }
    section { border-bottom: 1px solid var(--line); }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .metric, .panel, .example-card, .finding {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(16,24,40,.04);
    }
    .metric { padding: 16px; }
    .metric .label { color: var(--muted); font-size: 13px; }
    .metric .value { font-size: 30px; font-weight: 760; margin-top: 4px; }
    .metric .note { color: var(--muted); font-size: 12px; margin-top: 4px; }
    .grid-2 { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }
    .grid-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    .panel { padding: 18px; }
    .chart { width: 100%; max-width: 100%; height: auto; display: block; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
    .callout { border-left: 4px solid var(--teal); padding: 10px 14px; background: #eefaf8; border-radius: 0 8px 8px 0; margin: 12px 0; }
    .warn { border-left-color: var(--orange); background: #fff4ed; }
    .tag { display: inline-flex; align-items: center; max-width: 100%; border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; color: var(--muted); font-size: 12px; margin: 0 4px 5px 0; overflow-wrap: anywhere; }
    .finding { padding: 15px; }
    .finding strong { display: block; margin-bottom: 4px; }
    .split { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 16px; align-items: start; }
    .filters { position: sticky; top: 56px; display: grid; gap: 8px; }
    button.filter {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 8px;
      padding: 9px 10px;
      text-align: left;
      cursor: pointer;
      font: inherit;
      overflow-wrap: anywhere;
    }
    button.filter.active { border-color: var(--blue); box-shadow: inset 0 0 0 1px var(--blue); }
    .examples { display: grid; gap: 14px; }
    .example-card { padding: 16px; }
    .example-head { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; border-bottom: 1px solid var(--line); padding-bottom: 10px; margin-bottom: 12px; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; color: var(--muted); overflow-wrap: anywhere; }
    .rank-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 10px 0; }
    .mini { border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #fbfcfd; }
    .mini span { display: block; color: var(--muted); font-size: 12px; }
    .mini b { font-size: 18px; }
    .messages { display: grid; gap: 6px; margin-top: 8px; }
    .msg { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; background: #fbfcfd; }
    .msg-role { color: var(--muted); font-size: 12px; text-transform: uppercase; }
    .evidence-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; margin-top: 12px; }
    .evidence-block { border-top: 1px solid var(--line); padding-top: 10px; min-width: 0; }
    table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
    th, td { padding: 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; overflow-wrap: anywhere; }
    th { background: #f0f2f5; font-size: 13px; }
    tr:last-child td { border-bottom: 0; }
    details { border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 12px 14px; }
    details summary { cursor: pointer; font-weight: 700; }
    pre { overflow-x: auto; white-space: pre-wrap; background: #101828; color: #f2f4f7; border-radius: 8px; padding: 14px; }
    @media (max-width: 900px) {
      .summary, .grid-2, .grid-3, .split, .evidence-grid { grid-template-columns: 1fr; }
      .filters { position: static; }
      .rank-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .wrap { padding-left: 16px; padding-right: 16px; }
      table { display: block; overflow-x: auto; }
    }
    """
    script = """
    const DATA = JSON.parse(document.getElementById('report-data').textContent);

    function esc(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }
    function rank(value) { return value === null || value === undefined ? '-' : value; }
    function label(value) { return String(value || '').replaceAll('_', ' '); }

    function renderFilters() {
      const filters = document.getElementById('filters');
      const buckets = ['all', ...new Set(DATA.examples.map(ex => ex.case_bucket))];
      filters.innerHTML = buckets.map((bucket, idx) =>
        `<button class="filter ${idx === 0 ? 'active' : ''}" data-bucket="${esc(bucket)}">${esc(label(bucket))}</button>`
      ).join('');
      filters.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('click', () => {
          filters.querySelectorAll('button').forEach(x => x.classList.remove('active'));
          btn.classList.add('active');
          renderExamples(btn.dataset.bucket);
        });
      });
    }

    function renderMessages(messages) {
      return `<div class="messages">${(messages || []).map(msg => `
        <div class="msg">
          <div class="msg-role">T${esc(msg.turn)} ${esc(msg.role)}</div>
          <div>${esc(msg.content)}</div>
        </div>
      `).join('')}</div>`;
    }

    function tagList(values) {
      const rows = values || [];
      return rows.length ? rows.map(value => `<span class="tag">${esc(value)}</span>`).join('') : '<span class="mono">none</span>';
    }

    function tupleList(values) {
      const rows = values || [];
      return rows.length ? rows.map(value => `<span class="tag">${esc((value || []).join(': '))}</span>`).join('') : '<span class="mono">none</span>';
    }

    function objectText(value) {
      if (value === null || value === undefined) return 'none';
      if (typeof value === 'string') return value || 'none';
      if (Array.isArray(value)) return value.length ? value.map(x => typeof x === 'object' ? JSON.stringify(x) : String(x)).join(', ') : 'none';
      if (typeof value === 'object') {
        const entries = Object.entries(value).filter(([_, v]) => v !== null && v !== undefined && v !== '');
        return entries.length ? entries.map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join(', ') : 'none';
      }
      return String(value);
    }

    function branchRankRows(mapValue) {
      const entries = Object.entries(mapValue || {}).filter(([_, rankValue]) => rankValue !== null && rankValue !== undefined);
      if (!entries.length) return '<tr><td colspan="2">No branch rank evidence</td></tr>';
      return entries.sort((a, b) => Number(a[1]) - Number(b[1])).map(([branch, rankValue]) =>
        `<tr><td class="mono">${esc(branch)}</td><td>${esc(rankValue)}</td></tr>`
      ).join('');
    }

    function renderStateAudit(ex) {
      const s = ex.state_audit || {};
      const a = ex.anatomy || {};
      return `
        <div class="evidence-grid">
          <div class="evidence-block">
            <h3>Organizer and profile</h3>
            <p><strong>Goal:</strong> ${esc(ex.conversation_goal?.listener_goal || '')}</p>
            <p><strong>Category / specificity:</strong> <span class="mono">${esc(ex.conversation_goal?.category || '-')} / ${esc(ex.conversation_goal?.specificity || '-')}</span></p>
            <p><strong>Profile:</strong> age_group=${esc(ex.profile?.age_group || '-')}; country=${esc(ex.profile?.country_name || '-')}; culture=${esc(ex.profile?.preferred_musical_culture || '-')}</p>
          </div>
          <div class="evidence-block">
            <h3>Rank and branch evidence</h3>
            <p><strong>GT:</strong> ${esc(ex.gt_track)} by ${esc(ex.gt_artist)} <span class="mono">${esc(ex.gt_track_id)}</span></p>
            <p><strong>Release/popularity:</strong> year ${esc(ex.release_year || '-')}; popularity ${esc(ex.popularity ?? '-')}; bucket ${esc(ex.release_bucket || '-')}</p>
            <p><strong>Top branch ranks:</strong> ${(ex.top_branch_ranks || []).map(pair => `${esc(pair[0])}: ${esc(pair[1])}`).join(', ') || 'none'}</p>
          </div>
          <div class="evidence-block">
            <h3>Extracted state audit</h3>
            <p><strong>intent_mode:</strong> <span class="mono">${esc(s.intent || ex.intent_mode || '-')}</span></p>
            <p><strong>mentioned:</strong> ${tupleList(s.mentioned)}</p>
            <p><strong>resolved:</strong> ${tupleList(s.resolved)}</p>
            <p><strong>positive tags:</strong> ${tagList(s.pos_tags || ex.positive_tags)}</p>
            <p><strong>GT tag overlap:</strong> ${tagList(ex.gt_tag_overlap)}</p>
            <p><strong>rejections:</strong> tags=${esc(objectText(s.rej_tags))}; artists=${esc(objectText(s.rej_artist_ids))}; tracks=${esc(objectText(s.rej_track_ids))}</p>
            <p><strong>filters/year/lyrics:</strong> hard_filters=${esc(objectText(s.hard_filters))}; year_range=${esc(objectText(s.year_range))}; lyrical_theme=${esc(objectText(s.lyrical_theme))}</p>
            <p><strong>anchors:</strong> n_anchor=${esc(s.n_anchor ?? '-')}; n_played=${esc(s.n_played ?? '-')}; artists=${tagList(s.anchor_artist_ids)}</p>
            <p><strong>routing:</strong> ${tagList(ex.routing)}</p>
          </div>
          <div class="evidence-block">
            <h3>Per-branch ranks from anatomy</h3>
            <table><thead><tr><th>Branch</th><th>GT rank</th></tr></thead><tbody>${branchRankRows(a.per_branch_rank)}</tbody></table>
            <p class="mono">n_pools=${esc(a.n_pools ?? '-')}; n_anchor_tracks=${esc(a.n_anchor_tracks ?? '-')}; n_anchor_artists=${esc(a.n_anchor_artists ?? '-')}; n_resolved_targets=${esc(a.n_resolved_targets ?? '-')}; n_positive_tags=${esc(a.n_positive_tags ?? '-')}</p>
          </div>
        </div>
      `;
    }

    function renderExamples(bucket = 'all') {
      const host = document.getElementById('examples');
      const rows = DATA.examples.filter(ex => bucket === 'all' || ex.case_bucket === bucket);
      host.innerHTML = rows.map(ex => `
        <article class="example-card">
          <div class="example-head">
            <div>
              <h3>${esc(ex.gt_track)} by ${esc(ex.gt_artist)}</h3>
              <div class="mono">${esc(ex.session_id)} / turn ${esc(ex.turn)} / ${esc(label(ex.case_type))}</div>
            </div>
            <div><span class="tag">${esc(label(ex.case_bucket))}</span><span class="tag">${esc(ex.best_branch || 'NONE')}</span></div>
          </div>
          <p><strong>User turn:</strong> ${esc(ex.raw_user_turn || '(conversation text unavailable)')}</p>
          <p><strong>State turn_intent:</strong> ${esc(ex.intent)}</p>
          <div class="rank-row">
            <div class="mini"><span>Final rank</span><b>${rank(ex.final_rank)}</b></div>
            <div class="mini"><span>Fused rank</span><b>${rank(ex.fused_rank)}</b></div>
            <div class="mini"><span>Best branch rank</span><b>${rank(ex.min_branch_rank)}</b></div>
            <div class="mini"><span>Policy</span><b>${esc(ex.policy)}</b></div>
          </div>
          <p>${(ex.diagnosis || []).map(x => `<span class="tag">${esc(x)}</span>`).join('')}</p>
          <p><strong>Smallest next test:</strong> ${esc(ex.smallest_next_test)}</p>
          <details>
            <summary>Recent conversation and state details</summary>
            ${renderMessages(ex.recent_conversation)}
            ${renderStateAudit(ex)}
          </details>
        </article>
      `).join('');
    }

    function init() {
      renderFilters();
      renderExamples('all');
    }
    init();
    """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Music CRS Recall Gap Decision Report</title>
  <style>{styles}</style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>Music CRS Recall Gap Decision Report</h1>
      <p class="subtitle">Why gold tracks miss final top-20 in <span class="mono">{html.escape(data["tid"])}</span>, centered on union@20, state quality, retriever coverage, and whether the fusion stage should become a trained ranker.</p>
      <div class="summary">
        <div class="metric"><div class="label">Final Hit@20</div><div class="value">{pct(data["metrics"]["final20"])}</div><div class="note">Current submitted top-20 quality</div></div>
        <div class="metric"><div class="label">Union@20</div><div class="value">{pct(data["metrics"]["union20"])}</div><div class="note">Recoverable before fusion/ranking</div></div>
        <div class="metric"><div class="label">Not In Union@20</div><div class="value">{pct(data["metrics"]["not_in_union20"])}</div><div class="note">Retriever/state candidate gap</div></div>
        <div class="metric"><div class="label">Union@20 -> Final Gap</div><div class="value">{pp(data["metrics"]["union20_rank_policy_gap"])}</div><div class="note">Rank/fusion/post-fusion opportunity</div></div>
      </div>
      <div class="callout" style="margin-top:16px"><strong>Snapshot contract:</strong> This is a baseline decision report for <span class="mono">{html.escape(data["tid"])}</span> generated at <span class="mono">{html.escape(data["generated_at"])}</span>. Treat recommendations as A/B hypotheses for this exact compact report and trace family; after scorer, retriever, state, catalog, or split changes, regenerate and compare before treating old counts as current.</div>
    </div>
  </header>
  <nav><div class="wrap">
    <a class="report-link" href="../index.html">Recall Explorer</a>
    <a href="#summary">Summary</a>
    <a href="#task-mode-state">Task Modes</a>
    <a href="#gap-map">Gap Map</a>
    <a href="#organizer">Organizer</a>
    <a href="#standalone-context">Glossary</a>
    <a href="#user-metadata">User Metadata</a>
    <a href="#priority">Priority</a>
    <a href="#state">State</a>
    <a href="#ranker">Ranker</a>
    <a href="#examples-section">Examples</a>
    <a href="#fields">Fields</a>
    <a href="#prompt">Prompt</a>
  </div></nav>

  <section id="summary"><div class="wrap">
    <h2>The short answer</h2>
    <div class="grid-2">
      <div class="panel">
        <p><strong>This is not only a current-fusion problem.</strong> More than half of turns are not in union@20, and roughly one third are not in union@100. That is a real candidate-generation/state/retriever gap.</p>
        <p><strong>It is also not only a retriever problem.</strong> Union@20 is materially above final@20, and post-fusion demotions explain many recoverable losses. A trained ranker over union@100/200 is justified, but it should ship with state and post-fusion ablations.</p>
        <div class="callout"><strong>Recommended direction:</strong> keep broad retriever coverage, add a trained/calibrated ranker, weaken brittle post-fusion demotions, and improve state features for latent popular/canonical requests.</div>
        <div class="callout warn"><strong>Scoring context:</strong> {html.escape(scoring.get("public_dimensions", ""))} {html.escape(scoring.get("formula_note", ""))} {html.escape(scoring.get("current_response_gap", ""))}</div>
      </div>
      <div class="panel">
        <img class="chart" src="{html.escape(data["charts"]["coverage"])}" alt="Candidate ceilings vs current final top-20">
      </div>
    </div>
  </div></section>

  <section id="task-mode-state"><div class="wrap">
    <h2>Task-mode and state audit</h2>
    <div class="grid-3">
      <div class="metric"><div class="label">Honest Ranker Ceiling</div><div class="value">{pct(mode_state_honest.get("ceiling"))}</div><div class="note">Use union@100 as the practical first-stage ceiling</div></div>
      <div class="metric"><div class="label">Real Retrieval Gap@100</div><div class="value">{pct(mode_state_honest.get("gap"))}</div><div class="note">{int(mode_state_honest.get("gap_n") or 0):,} turns not in shallow branch pools</div></div>
      <div class="metric"><div class="label">New-Artist Hit@20</div><div class="value">{pct(new_artist_mode.get("hit20"))}</div><div class="note">Same source as the task-mode table below</div></div>
    </div>
    <div class="grid-2" style="margin-top:16px">
      <div class="panel">
        <h3>What this adds to the plan</h3>
        <ul>{mode_state_accepted_html}</ul>
      </div>
      <div class="panel">
        <h3>Caveats before acting</h3>
        <ul>{mode_state_caveated_html}</ul>
      </div>
    </div>
    <div class="callout warn">
      <strong>How this changes the recommendation:</strong> keep the union@20 boundary, but stop treating all misses as one retrieval bucket. The most actionable split is now continuation vs new-artist: continuation wants album/artist-recency ranking; new-artist wants turn-level novelty routing, popularity/user-CF priors, and better candidate generation.
    </div>
    <h3>Task-mode split</h3>
    <table>
      <thead><tr><th>Mode</th><th>Meaning</th><th>Turns</th><th>Share</th><th>Hit@20</th><th>NDCG@20</th><th>Gap@50</th><th>Miss share</th><th>Verdict</th></tr></thead>
      <tbody>{mode_state_task_modes_html}</tbody>
    </table>
    <div class="callout">{html.escape(str(mode_state.get("task_cat_note") or ""))}</div>
    <div class="grid-2" style="margin-top:16px">
      <div class="panel">
        <h3>Relation-aware state taxonomy to copy</h3>
        <table>
          <thead><tr><th>User cue</th><th>Role</th><th>Current state</th><th>Ideal state</th></tr></thead>
          <tbody>{mode_state_taxonomy_html}</tbody>
        </table>
      </div>
      <div class="panel">
        <h3>State bugs and checks worth adding</h3>
        <table>
          <thead><tr><th>Item</th><th>Verdict</th><th>Stat</th><th>Detail</th></tr></thead>
          <tbody>{mode_state_scorecard_html}</tbody>
        </table>
      </div>
    </div>
    <h3 style="margin-top:18px">Failed state examples worth preserving</h3>
    <div class="grid-2">{mode_state_bad_examples_html}</div>
    <div class="grid-2" style="margin-top:16px">
      <div class="panel">
        <h3>Ranker/retriever features to add</h3>
        <table>
          <thead><tr><th>Feature</th><th>Evidence</th><th>Target slice</th></tr></thead>
          <tbody>{mode_state_feature_build_html}</tbody>
        </table>
        <p class="mono">{html.escape(str((((mode_state.get("fixes") or {}).get("feature_catalog") or {}).get("meta") or "")))}</p>
      </div>
      <div class="panel">
        <h3>Do not over-invest here</h3>
        <ul>{mode_state_do_not_html}</ul>
        <h3>Ruled-out hypotheses</h3>
        <table>
          <thead><tr><th>Hypothesis</th><th>Why not</th></tr></thead>
          <tbody>{mode_state_ruled_out_html}</tbody>
        </table>
      </div>
    </div>
    <h3 style="margin-top:18px">Open caveats</h3>
    <table>
      <thead><tr><th>Caveat</th><th>Why it matters</th></tr></thead>
      <tbody>{mode_state_open_caveats_html}</tbody>
    </table>
  </div></section>

  <section id="gap-map"><div class="wrap">
    <h2>Union boundaries show two separate failures</h2>
    <div class="grid-2">
      <div class="panel"><img class="chart" src="{html.escape(data["charts"]["gaps"])}" alt="Failure buckets by union and final rank"></div>
      <div class="panel">
        <h3>Decision boundaries</h3>
        <p><strong>Not in union@20:</strong> fix candidate generation, state, routing, or retrievers.</p>
        <p><strong>In union@20 but not final top-20:</strong> fix fusion, final ranker, post-fusion policy, or backfill/finalization.</p>
        <p><strong>In union@100 but not union@20:</strong> ranker can help, but retriever calibration and branch query quality still matter.</p>
        <p><strong>Not in union@100:</strong> treat as a deeper state/retriever/data-field gap.</p>
      </div>
    </div>
  </div></section>

  <section id="organizer"><div class="wrap">
    <h2>Organizer metadata makes the problem clearer</h2>
    <div class="summary">
      <div class="metric"><div class="label">Official NDCG@10</div><div class="value">{pct(data.get("official_scores", {}).get("ndcg@10"))}</div><div class="note">Evaluator primary-style ranking metric</div></div>
      <div class="metric"><div class="label">LL Final@20</div><div class="value">{pct(org_headline.get("ll_final20"))}</div><div class="note">Low-specificity organizer goals</div></div>
      <div class="metric"><div class="label">HH Final@20</div><div class="value">{pct(org_headline.get("hh_final20"))}</div><div class="note">High-specificity organizer goals</div></div>
      <div class="metric"><div class="label">Turn 8 Final@20</div><div class="value">{pct(org_headline.get("turn8_final20"))}</div><div class="note">Late-history failure mode</div></div>
    </div>
    <div class="grid-2" style="margin-top:16px">
      <div class="panel"><img class="chart" src="{html.escape(data["charts"]["organizer_specificity"])}" alt="Final and union top-20 by organizer specificity"></div>
      <div class="panel"><img class="chart" src="{html.escape(data["charts"]["organizer_turns"])}" alt="Final and union top-20 by turn"></div>
      <div class="panel"><img class="chart" src="{html.escape(data["charts"]["organizer_categories"])}" alt="Worst goal categories by final top-20"></div>
      <div class="panel"><img class="chart" src="{html.escape(data["charts"]["organizer_assessment"])}" alt="Final and union top-20 by organizer goal progress assessment"></div>
    </div>
    <div class="callout"><strong>Blind relevance:</strong> Blind-A exposes <span class="mono">conversation_goal</span>, <span class="mono">user_profile</span>, and <span class="mono">goal_progress_assessments</span> too, so these fields are not merely offline diagnostics.</div>
    <div class="callout warn"><strong>Read this standalone:</strong> {html.escape(context.get("why_ll_c_k_i_j", ""))}</div>
    <table>
      <thead><tr><th>Category</th><th>Turns</th><th>Organizer goal examples</th><th>Final@20</th><th>Union@20</th><th>Union@100</th><th>Rank gap</th><th>Not union@20</th></tr></thead>
      <tbody>{category_table_html}</tbody>
    </table>
  </div></section>

  <section id="standalone-context"><div class="wrap">
    <h2>Glossary for the hard slices</h2>
    <div class="callout">{html.escape(context.get("label_caveat", ""))}</div>
    <h3>Specificity codes</h3>
    <table>
      <thead><tr><th>Code</th><th>Plain meaning</th><th>Observed goal shape</th><th>Turns</th><th>Final@20</th><th>Union@20</th><th>Union@100</th><th>Why it matters</th></tr></thead>
      <tbody>{specificity_table_html}</tbody>
    </table>
    <h3 style="margin-top:18px">Why categories C/K/I/J are called out</h3>
    <div class="grid-2">{focus_category_html}</div>
  </div></section>

  <section id="user-metadata"><div class="wrap">
    <h2>User metadata field map</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>What is in the organizer rows</h3>
        <p>The live conversation <span class="mono">user_profile</span> object exposes: {html.escape(", ".join(user_meta.get("inline_user_profile_fields", [])))}.</p>
        <p>The standalone user metadata table exposes: {html.escape(", ".join((user_meta.get("standalone_user_metadata") or {}).get("fields", [])))}.</p>
        <p>The compact examples in this report carry: {html.escape(", ".join(user_meta.get("report_example_profile_fields", [])))}.</p>
      </div>
      <div class="panel">
        <h3>How we should treat it</h3>
        <p>{html.escape(user_meta.get("current_pipeline_summary", ""))}</p>
        <div class="callout"><strong>Ranker take:</strong> {html.escape(user_meta.get("ranker_summary", ""))}</div>
      </div>
    </div>
    <table style="margin-top:16px">
      <thead><tr><th>Field</th><th>Where it appears</th><th>Meaning</th><th>Current use</th><th>Better use</th></tr></thead>
      <tbody>{user_meta_table_html}</tbody>
    </table>
  </div></section>

  <section id="priority"><div class="wrap">
    <h2>What I would work on first</h2>
    <div class="callout warn"><strong>My sharper recommendation:</strong> do not spend the next cycle adding another generic dense retriever or tuning equal-weight fusion. Build a union-pool ranker using candidate-varying state/behavioral features, and in parallel pass organizer goal/profile fields into retrieval routing and candidate affinity features for the low-specificity slices.</div>
    <div class="grid-2">{priority_html}</div>
    <div class="panel" style="margin-top:16px">
      <h3>Confirmed implementation gaps</h3>
      <p><strong>Metadata is available but not used by retrieval:</strong> dev/test/Blind-A include <span class="mono">conversation_goal</span>, <span class="mono">specificity</span>, <span class="mono">preferred_musical_culture</span>, and <span class="mono">goal_progress_assessments</span>; current devset batch input passes only <span class="mono">user_query</span>, <span class="mono">user_id</span>, and <span class="mono">session_memory</span>.</p>
      <p><strong>Existing rerank feature extraction is too narrow:</strong> the original-project helper uses organizer metadata, but its candidate window is <span class="mono">branches.final.track_ids[:100]</span>. That cannot recover items discarded before final ranking. The ranker must train over raw branch union@100/200.</p>
    </div>
  </div></section>

  <section id="state"><div class="wrap">
    <h2>State is incomplete in the highest-impact slices</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>What the state object looks like</h3>
        <p>The v0+ pipeline extracts a structured <span class="mono">ConversationStateV0Plus</span>, resolves names to catalog IDs, then the compiler turns that state into BM25, dense, lookup, centroid, masking, fusion, and post-fusion signals.</p>
        <p>In failed examples, we show the compact trace-derived audit: intent mode, mentioned/resolved entities, tags, filters, year range, anchors, policy, branch ranks, and diagnosis.</p>
      </div>
      <div class="panel">
        <h3>What failed examples contain</h3>
        <table>
          <thead><tr><th>Evidence</th><th>What we have</th><th>Why it matters</th></tr></thead>
          <tbody>{failed_inventory_html}</tbody>
        </table>
      </div>
    </div>
    <table style="margin-top:16px">
      <thead><tr><th>State field</th><th>Meaning</th><th>Retrieval/ranking use</th><th>Where to see it</th></tr></thead>
      <tbody>{state_fields_table_html}</tbody>
    </table>
    <div class="grid-2">
      <div class="panel"><img class="chart" src="{html.escape(data["charts"]["state"])}" alt="Entity grounding by final and union top-20 rates"></div>
      <div class="grid-2">
        {''.join(f'<div class="finding"><strong>{html.escape(x["title"])}</strong><p>{html.escape(x["evidence"])}</p><p>{html.escape(x["implication"])}</p></div>' for x in data["state_findings"])}
      </div>
    </div>
  </div></section>

  <section id="ranker"><div class="wrap">
    <h2>The fusion stage should become a trained scorer, but not alone</h2>
    <div class="grid-2">
      <div class="panel"><img class="chart" src="{html.escape(data["charts"]["branches"])}" alt="Top branch recall at 20"></div>
      <div class="panel">
        <h3>Ranker recipe</h3>
        <p>Train on union@200 candidates with session-grouped splits. Start simple: LightGBM/LambdaMART or logistic pairwise scoring, then compare to the current fusion baseline and post-fusion ablations.</p>
        <p><strong>Core features:</strong> min branch rank, reciprocal ranks by branch, branch-hit count, branch family flags, fused rank, post-fusion multipliers, intent mode, exploration policy, routing tags, turn number, anchors, tag overlap, release distance, popularity, same-artist/same-album flags, resolver confidence, candidate artist role, and candidate-varying goal/profile affinity where deployable.</p>
        <p><strong>Guardrail:</strong> never use current-turn gold music IDs, assistant thought, or future turns as features.</p>
        {reranker_evidence_html}
      </div>
    </div>
    <div class="grid-2" style="margin-top:16px">
      {''.join(f'<div class="finding"><strong>{html.escape(x["priority"])}: {html.escape(x["name"])}</strong><p>{html.escape(x["why"])}</p><p><strong>First test:</strong> {html.escape(x["how"])}</p><p><strong>Success:</strong> {html.escape(x["success"])}</p></div>' for x in data["experiments"])}
    </div>
  </div></section>

  <section id="examples-section"><div class="wrap">
    <h2>Concrete misses and near misses</h2>
    <div class="split">
      <aside class="filters" id="filters"></aside>
      <div class="examples" id="examples"></div>
    </div>
  </div></section>

  <section id="fields"><div class="wrap">
    <h2>Data fields to use better</h2>
    <table>
      <thead><tr><th>Field</th><th>Current use</th><th>Better use</th></tr></thead>
      <tbody>
        {''.join(f'<tr><td>{html.escape(row["field"])}</td><td>{html.escape(row["current"])}</td><td>{html.escape(row["use"])}</td></tr>' for row in data["field_opportunities"])}
      </tbody>
    </table>
    <div class="callout warn"><strong>Reproducibility gap:</strong> local LanceDB has {html.escape(str(data["schema"].get("row_count")))} catalog rows, but required vector fields missing locally are {html.escape(", ".join(data["schema"].get("missing_required_vector_fields", [])) or "none")}. Use the Modal LanceDB catalog before training features that depend on missing 8B columns.</div>
  </div></section>

  <section id="prompt"><div class="wrap">
    <h2>Full reusable prompt</h2>
    <details open>
      <summary>Prompt for future agents</summary>
      <pre>{html.escape(data["prompt"])}</pre>
    </details>
    <p class="subtitle">Generated {html.escape(data["generated_at"])}. Sources are preserved in <span class="mono">report_data.json</span> and <span class="mono">agent_report.md</span>.</p>
  </div></section>

  <script id="report-data" type="application/json">{payload}</script>
  <script>{script}</script>
</body>
</html>
"""


def markdown_report(data: dict[str, Any]) -> str:
    organizer = data.get("organizer", {})
    headline = organizer.get("headline", {})
    user_meta = data.get("user_metadata_fields", {})
    context = data.get("standalone_context", {})
    mode_state = data.get("task_mode_state_addendum", {})
    mode_state_honest = mode_state.get("honest_ceiling") or {}
    scoring = data.get("scoring_context", {})
    state_evidence = data.get("state_focus_evidence", {})
    reranker_bakeoff = state_evidence.get("reranker_bakeoff") or {}
    lines = [
        "# Music CRS Recall Gap Decision Report",
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
        f"- Official-score context: NDCG@10 is {pct(data.get('official_scores', {}).get('ndcg@10'))}; NDCG@20 is {pct(data.get('official_scores', {}).get('ndcg@20'))}.",
        f"- Final Hit@20 is {pct(data['metrics']['final20'])}; union@20 is {pct(data['metrics']['union20'])}.",
        f"- {pct(data['metrics']['not_in_union20'])} of turns are not in union@20, so candidate generation/state/retrieval is a real gap.",
        f"- The union@20 to final@20 opportunity is {pp(data['metrics']['union20_rank_policy_gap'])}, so current fusion/post-fusion/ranking is also a real gap.",
        f"- Union@100 is {pct(data['metrics']['union100'])}; a trained ranker over union@100/200 is justified, but cannot fix not-in-union cases.",
        f"- Organizer metadata sharpens the diagnosis: LL final@20 is {pct(headline.get('ll_final20'))} vs HH final@20 {pct(headline.get('hh_final20'))}; turn 8 final@20 is {pct(headline.get('turn8_final20'))} while union@20 is {pct(headline.get('turn8_union20'))}.",
        f"- Public challenge scoring dimensions include {scoring.get('public_dimensions', '')} {scoring.get('formula_note', '')}",
        f"- Response-generation gap: {scoring.get('current_response_gap', '')}",
        "",
        "## Response Generation And Scoring Context",
        "",
        f"- Public dimensions: {scoring.get('public_dimensions', '')}",
        f"- Formula caveat: {scoring.get('formula_note', '')}",
        f"- Current gap: {scoring.get('current_response_gap', '')}",
        f"- Next test: {scoring.get('next_test', '')}",
        "",
        "## Task-Mode And State Audit Addendum",
        "",
        f"- Honest first-stage ranker ceiling: union@{mode_state_honest.get('ceiling_k')} = {pct(mode_state_honest.get('ceiling'))}; gap@{mode_state_honest.get('ceiling_k')} = {pct(mode_state_honest.get('gap'))} ({int(mode_state_honest.get('gap_n') or 0):,} turns).",
        f"- This preserves the user's union@20 concern, but makes union@100 the practical shallow-pool ceiling for first-stage ranker design.",
        "",
        "### What This Adds To The Plan",
        "",
    ]
    for item in (mode_state.get("evaluation") or {}).get("accepted", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "### Caveats before acting",
        "",
    ])
    for item in (mode_state.get("evaluation") or {}).get("caveated", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "### Task Mode Split",
        "",
        "| Mode | Meaning | Turns | Share | Hit@20 | NDCG@20 | Gap@50 | Miss share | Verdict |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for row in mode_state.get("task_modes", []):
        lines.append(
            f"| {row.get('mode')} | {row.get('description')} | {int(row.get('n') or 0):,} | {pct(row.get('share'))} | {pct(row.get('hit20'))} | {pct(row.get('ndcg20'))} | {pct(row.get('gap50'))} | {pct(row.get('miss_share'))} | {row.get('verdict')} |"
        )
    lines.extend([
        "",
        f"Task-mode note: {mode_state.get('task_cat_note', '')}",
        "",
        "### Relation-Aware State Taxonomy",
        "",
        "| Cue | Role | Current state | Ideal state |",
        "| --- | --- | --- | --- |",
    ])
    for row in (mode_state.get("extraction") or {}).get("taxonomy", []):
        lines.append(
            f"| {row.get('cue')} | `{row.get('role')}` | {row.get('current')} | {row.get('ideal')} |"
        )
    lines.extend([
        "",
        "### State Bugs And Checks To Add",
        "",
        "| Item | Verdict | Stat | Detail |",
        "| --- | --- | --- | --- |",
    ])
    for row in (mode_state.get("state") or {}).get("scorecard", []):
        lines.append(
            f"| {row.get('item')} | `{row.get('verdict')}` | {row.get('stat')} | {row.get('detail')} |"
        )
    lines.extend([
        "",
        "### Feature Catalog From This Audit",
        "",
        "| Feature | Evidence | Target slice |",
        "| --- | --- | --- |",
    ])
    for row in ((mode_state.get("fixes") or {}).get("feature_catalog") or {}).get("build", []):
        feature = row[0] if len(row) > 0 else ""
        evidence = row[1] if len(row) > 1 else ""
        target = row[2] if len(row) > 2 else ""
        lines.append(f"| {feature} | {evidence} | {target} |")
    lines.extend([
        "",
        "Do not over-invest in:",
    ])
    for item in ((mode_state.get("fixes") or {}).get("feature_catalog") or {}).get("dont", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## What To Work On First",
        "",
    ])
    for row in data.get("priority_recommendations", []):
        lines.extend([
            f"### {row['priority']}: {row['title']}",
            "",
            f"Why: {row['why']}",
            "",
            f"Do: {row['do']}",
            "",
            f"Proof: {row['proof']}",
            "",
        ])
    lines.extend([
        "## Measured Ranker And Feature Evidence",
        "",
    ])
    if reranker_bakeoff.get("available"):
        lines.extend([
            (
                f"- Adjacent reranker bakeoff: NDCG@20 {float(reranker_bakeoff.get('base_ndcg20') or 0):.4f} -> "
                f"{float(reranker_bakeoff.get('rerank_ndcg20') or 0):.4f} "
                f"({pct(reranker_bakeoff.get('relative_ndcg20'))} relative); Hit@20 "
                f"{float(reranker_bakeoff.get('base_hit20') or 0):.4f} -> "
                f"{float(reranker_bakeoff.get('rerank_hit20') or 0):.4f}."
            ),
            f"- Scope caveat: {reranker_bakeoff.get('scope', '')}",
            f"- Decision: {reranker_bakeoff.get('decision', '')}",
            "",
        ])
    for row in state_evidence.get("measured_levers", {}).values():
        if row:
            lines.append(
                f"- {row.get('lever')}: {row.get('status')}; {row.get('result')} Decision: {row.get('decision')}"
            )
    lines.append("")
    lines.extend([
        "## Organizer Metadata Slices",
        "",
        "| Slice | n | Final@20 | Union@20 | Union@100 | Rank gap | Not union@20 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in organizer.get("dimensions", {}).get("specificity", []):
        lines.append(
            f"| specificity={row['name']} | {row['n']:,} | {pct(row.get('final20_rate'))} | {pct(row.get('union20_rate'))} | {pct(row.get('union100_rate'))} | {pp(row.get('rank_policy_gap_rate'))} | {pct(row.get('candidate_gap20_rate'))} |"
        )
    for row in organizer.get("dimensions", {}).get("assessment", []):
        lines.append(
            f"| assessment={row['name']} | {row['n']:,} | {pct(row.get('final20_rate'))} | {pct(row.get('union20_rate'))} | {pct(row.get('union100_rate'))} | {pp(row.get('rank_policy_gap_rate'))} | {pct(row.get('candidate_gap20_rate'))} |"
        )
    lines.extend([
        "",
        "### Goal Categories",
        "",
        "| Category | n | Example organizer goals | Final@20 | Union@20 | Union@100 |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ])
    examples = organizer.get("category_goal_examples", {})
    for row in organizer.get("dimensions", {}).get("category", []):
        goal_text = clean_text(" | ".join(examples.get(row["name"], [])[:2]), 220)
        lines.append(
            f"| {row['name']} | {row['n']:,} | {goal_text} | {pct(row.get('final20_rate'))} | {pct(row.get('union20_rate'))} | {pct(row.get('union100_rate'))} |"
        )
    lines.extend([
        "",
        "## Standalone Glossary For Hard Slices",
        "",
        context.get("label_caveat", ""),
        "",
        context.get("why_ll_c_k_i_j", ""),
        "",
        "### Specificity Codes",
        "",
        "| Code | Plain meaning | Observed goal shape | n | Final@20 | Union@20 | Union@100 | Why it matters |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ])
    for row in context.get("specificity", []):
        lines.append(
            f"| `{row['code']}` | {row['label']} | {row['meaning']} Example: {row['example']} | {row.get('n') or 0:,} | {pct(row.get('final20_rate'))} | {pct(row.get('union20_rate'))} | {pct(row.get('union100_rate'))} | {row['why_it_matters']} |"
        )
    lines.extend([
        "",
        "### Focus Categories C/K/I/J",
        "",
    ])
    for row in context.get("focus_categories", []):
        lines.extend([
            f"#### Category {row['code']}: {row['description']}",
            "",
            f"- Metrics: n={row.get('n') or 0:,}; Final@20={pct(row.get('final20_rate'))}; Union@20={pct(row.get('union20_rate'))}; Union@100={pct(row.get('union100_rate'))}.",
            f"- Why it gaps: {row['why_gap']}",
            f"- Work on: {row['work_on']}",
            f"- Observed goals: {' | '.join(row.get('examples', []))}",
            "",
        ])
    lines.extend([
        "",
        "## User Metadata Field Map",
        "",
        f"- Live inline `user_profile` fields: `{ '`, `'.join(user_meta.get('inline_user_profile_fields', [])) }`.",
        f"- Standalone user metadata fields: `{ '`, `'.join((user_meta.get('standalone_user_metadata') or {}).get('fields', [])) }`.",
        f"- Compact report example profile fields: `{ '`, `'.join(user_meta.get('report_example_profile_fields', [])) }`.",
        f"- Current pipeline summary: {user_meta.get('current_pipeline_summary', '')}",
        f"- Ranker summary: {user_meta.get('ranker_summary', '')}",
        "",
        "| Field | Where it appears | Meaning | Current use | Better use |",
        "| --- | --- | --- | --- | --- |",
    ])
    for row in user_meta.get("fields", []):
        lines.append(
            f"| `{row['field']}` | {row['source']} | {row['meaning']} | {row['current_use']} | {row['ranker_use']} |"
        )
    lines.extend([
        "",
        "## State And Retriever Findings",
        "",
        "### What The State Object Looks Like",
        "",
        "The v0+ pipeline extracts a structured `ConversationStateV0Plus`, resolves surface names to catalog IDs, then compiles that state into BM25, dense, lookup, centroid, masking, fusion, and post-fusion signals.",
        "",
        "| State field | Meaning | Retrieval/ranking use | Where to see it in examples |",
        "| --- | --- | --- | --- |",
    ])
    for row in context.get("state_fields", []):
        lines.append(
            f"| `{row['field']}` | {row['meaning']} | {row['retrieval_use']} | {row['example_use']} |"
        )
    lines.extend([
        "",
        "### What Failed Examples Contain",
        "",
        "| Evidence | What we have | Why it matters |",
        "| --- | --- | --- |",
    ])
    for row in context.get("failed_example_inventory", []):
        lines.append(
            f"| {row['item']} | {row['what_we_have']} | {row['why_it_matters']} |"
        )
    lines.append("")
    for finding in data["state_findings"]:
        lines.extend([
            f"### {finding['title']}",
            "",
            finding["evidence"],
            "",
            f"Implication: {finding['implication']}",
            "",
        ])
    lines.extend(["## Recommended Experiments", ""])
    for exp in data["experiments"]:
        lines.extend([
            f"### {exp['priority']}: {exp['name']}",
            "",
            f"Why: {exp['why']}",
            "",
            f"How: {exp['how']}",
            "",
            f"Success: {exp['success']}",
            "",
        ])
    lines.extend(["## Example Gaps", ""])
    for ex in data["examples"]:
        state = ex.get("state_audit") or {}
        anatomy = ex.get("anatomy") or {}
        lines.extend([
            f"### {ex['case_bucket']} - {ex['gt_track']} by {ex['gt_artist']}",
            "",
            f"- Session/turn: `{ex['session_id']}` / `{ex['turn']}`",
            f"- User turn: {ex.get('raw_user_turn') or '(unavailable)'}",
            f"- Organizer goal: category `{(ex.get('conversation_goal') or {}).get('category')}`, specificity `{(ex.get('conversation_goal') or {}).get('specificity')}`, listener_goal: {(ex.get('conversation_goal') or {}).get('listener_goal')}",
            f"- Profile: `{ex.get('profile')}`",
            f"- State intent: {ex.get('intent') or ''}",
            f"- State audit: intent_mode `{state.get('intent')}`, mentioned `{state.get('mentioned')}`, resolved `{state.get('resolved')}`, pos_tags `{state.get('pos_tags')}`, rejected tags `{state.get('rej_tags')}`, year_range `{state.get('year_range')}`, anchors `{state.get('anchor_artist_ids')}`.",
            f"- Ranks: final `{ex.get('final_rank')}`, fused `{ex.get('fused_rank')}`, best branch `{ex.get('min_branch_rank')}` via `{ex.get('best_branch')}`",
            f"- Anatomy: n_pools `{anatomy.get('n_pools')}`, n_anchor_tracks `{anatomy.get('n_anchor_tracks')}`, n_resolved_targets `{anatomy.get('n_resolved_targets')}`, per_branch_rank `{anatomy.get('per_branch_rank')}`.",
            f"- Classification: {ex.get('case_type')}",
            f"- Diagnosis: {'; '.join(ex.get('diagnosis') or [])}",
            f"- Smallest next test: {ex.get('smallest_next_test')}",
            "",
        ])
    lines.extend(["## Data Fields To Use Better", ""])
    for row in data["field_opportunities"]:
        lines.extend([
            f"- `{row['field']}`: {row['current']} Better use: {row['use']}",
        ])
    lines.extend([
        "",
        "## Reusable Prompt",
        "",
        "```text",
        data["prompt"].rstrip(),
        "```",
        "",
    ])
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    report_root = Path(args.report_root)
    source_root = Path(args.source_root)
    out_dir = Path(args.out_dir)
    report = read_json(report_root / "recall_gap_data.json")
    branch_diag = read_json(report_root / "branch_diagnostics.json")
    selected_examples = choose_examples(report)
    session_ids = {str(ex["session_id"]) for ex in selected_examples}
    conversations, hf_error = load_hf_conversations(session_ids)

    raw_contexts = {sid: recent_conversation(conversations.get(sid), 8) for sid in session_ids}
    track_ids = {str(ex.get("gt_track_id")) for ex in selected_examples if ex.get("gt_track_id")}
    for sid in session_ids:
        track_ids.update(raw_contexts.get(sid, {}).get("music_ids", []))
    track_lookup, lancedb_track_error = load_track_lookup(source_root, track_ids)
    examples = enrich_examples(selected_examples, source_root, track_lookup, conversations)

    config_path = source_root / "configs" / f"{args.tid}.yaml"
    schema = inspect_lancedb_schema(source_root, config_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    organizer = load_organizer_metadata_analysis(source_root)
    user_metadata_fields = user_metadata_field_map(organizer)
    context = standalone_context(organizer)
    task_mode_state_addendum = load_task_mode_state_addendum(source_root)
    charts = generate_charts(report, out_dir)
    charts.update(generate_organizer_charts(organizer, out_dir))
    metrics = build_decision_metrics(report)
    official_scores = official_score_summary(source_root, args.tid)
    score_context = scoring_context(config_path)
    state_focus_evidence = load_state_focus_evidence(report_root)
    prompt = build_prompt()
    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "tid": args.tid,
        "snapshot_contract": {
            "status": "Baseline ranker/retriever decision snapshot, not a permanent ranking policy.",
            "applies_to": f"{args.tid} compact recall data, branch diagnostics, state-focus data, config, and sampled conversations at generation time.",
            "valid_until": (
                "Rerun after changing candidate generation, retriever routing, fusion/finalization, ranker features, "
                "state extraction, catalog/index contents, or evaluation split."
            ),
            "how_to_use": (
                "Use recommendations as A/B experiment hypotheses. After implementing a scorer or retriever change, "
                "regenerate and compare union@20/100, final@20, nDCG, guardrail slices, and case-study examples."
            ),
        },
        "metrics": metrics,
        "official_scores": official_scores,
        "scoring_context": score_context,
        "state_focus_evidence": state_focus_evidence,
        "gap_buckets": report.get("gap_buckets", []),
        "branch_diagnostics": branch_diag,
        "organizer": organizer,
        "state_findings": state_findings(report),
        "experiments": recommended_experiments(metrics),
        "priority_recommendations": priority_recommendations(organizer, metrics),
        "standalone_context": context,
        "user_metadata_fields": user_metadata_fields,
        "task_mode_state_addendum": task_mode_state_addendum,
        "field_opportunities": field_opportunities(schema),
        "schema": schema,
        "examples": examples,
        "charts": charts,
        "prompt": prompt,
        "sources": {
            "report_json": str(report_root / "recall_gap_data.json"),
            "branch_diagnostics": str(report_root / "branch_diagnostics.json"),
            "source_trace": str(source_root / "exp/inference/devset" / f"{args.tid}_trace.jsonl"),
            "predictions": str(source_root / "exp/inference/devset" / f"{args.tid}.json"),
            "ground_truth": str(source_root / "evaluator/exp/ground_truth/devset.json"),
            "hf_conversation_dataset": HF_CONVERSATION_DATASET,
            "config": str(config_path),
            "lancedb": str(source_root / "cache/lancedb"),
        },
        "source_errors": {
            "hf_conversations": hf_error,
            "lancedb_track_lookup": lancedb_track_error,
            "lancedb_schema": schema.get("error"),
        },
        "caveats": [
            "The report uses the existing compact trace-derived recall_gap_data.json rather than rescanning the 5.1 GB trace.",
            "Raw conversation text is joined from the HF test split for sampled examples.",
            "Current-turn music targets and assistant thought are labels/evaluation evidence, not deployable ranker features.",
            "Local LanceDB lacks some config-required 8B vector fields; Modal LanceDB should be used for schema-sensitive ranker training.",
        ],
    }
    (out_dir / "report_data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "index.html").write_text(html_report(data), encoding="utf-8")
    (out_dir / "agent_report.md").write_text(markdown_report(data), encoding="utf-8")
    (out_dir / "full_prompt.md").write_text(data["prompt"], encoding="utf-8")
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default=str(DEFAULT_SOURCE_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--tid", default=DEFAULT_TID)
    return parser.parse_args()


def main() -> None:
    data = build_report(parse_args())
    print(json.dumps({
        "html": str(Path(DEFAULT_OUT_DIR) / "index.html"),
        "markdown": str(Path(DEFAULT_OUT_DIR) / "agent_report.md"),
        "prompt": str(Path(DEFAULT_OUT_DIR) / "full_prompt.md"),
        "examples": len(data["examples"]),
    }, indent=2))


if __name__ == "__main__":
    main()
