"""Reproduce the 'extractor missed a GT-tag word the user literally said'
classification from experiments/v0plus_textside_2026-05-28.md (reported 1432
turns = 46.2% of 3100 R2 full-devset failures).

Inputs:
- R2 trace                evaluator/exp/inference/devset/v0plus_compiler_textside_v2_devset_trace.json
- R2 predictions          evaluator/exp/inference/devset/v0plus_compiler_textside_v2_devset.json
- devset ground truth     evaluator/exp/ground_truth/devset.json
- track metadata          HF: talkpl-ai/TalkPlayData-Challenge-Track-Metadata
- devset conversations    HF: talkpl-ai/TalkPlayData-Challenge-Dataset (test split)

Definition (best-fit to writeup wording):
  A failed turn (GT not in top-20 predictions) is in the cohort if there is at
  least one TOKEN inside GT.tag_list that appears literally in the latest
  user-turn text AND is NOT already in state.positive_tags (both compared
  case-insensitively after light normalization).

  Multi-word tags are split into whitespace-tokens; each token is checked
  individually so "alternative rock" matches "alternative" appearing alone.
  Single-character / pure-digit / stopword tokens are excluded.

Outputs:
- artifacts/cohort_missed_literal_tags.jsonl  one row per cohort turn
- artifacts/cohort_summary.json                aggregate counts
- artifacts/cohort_examples.md                 20 illustrative examples
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import ijson  # streaming JSON parser for the 1.2 GB trace
from datasets import load_dataset

# Tokens never worth flagging — they trip false-positives.
STOPWORDS = {
    "a","an","and","or","of","the","to","in","on","at","for","with","is","it",
    "by","as","be","that","this","i","you","me","my","your","we","us","like",
    "from","but","not","so","very","more","some","any","other","just",
    "music","song","songs","track","tracks","artist","band",
}

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")


def normalize(token: str) -> str:
    return token.strip().lower()


def tokenize_text(text: str) -> set[str]:
    """All alphanumeric words in the text, lowercased."""
    return {normalize(m.group(0)) for m in WORD_RE.finditer(text or "")}


def tag_to_tokens(tag: str) -> list[str]:
    """Split a (possibly multi-word) tag into normalized tokens; filter junk."""
    raw = WORD_RE.findall(tag or "")
    return [
        t.lower()
        for t in raw
        if len(t) >= 3 and t.lower() not in STOPWORDS and not t.isdigit()
    ]


def latest_user_text(conversation: list[dict[str, Any]], turn_number: int) -> str:
    """All user utterances at turn_number, concatenated. (Usually there's just one.)"""
    parts = []
    for t in conversation:
        if t.get("turn_number") == turn_number and t.get("role") == "user":
            parts.append(t.get("content", ""))
    return " ".join(parts)


def cumulative_user_text(conversation: list[dict[str, Any]], turn_number: int) -> str:
    """All user utterances at turn_number AND prior turns."""
    parts = []
    for t in conversation:
        tn = t.get("turn_number", 0)
        if tn <= turn_number and t.get("role") == "user":
            parts.append(t.get("content", ""))
    return " ".join(parts)


def load_predictions(path: Path) -> dict[tuple[str, int], list[str]]:
    out: dict[tuple[str, int], list[str]] = {}
    with path.open() as fh:
        data = json.load(fh)
    for row in data:
        out[(row["session_id"], row["turn_number"])] = row["predicted_track_ids"]
    return out


def load_ground_truth(path: Path) -> dict[tuple[str, int], str]:
    with path.open() as fh:
        data = json.load(fh)
    return {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"] for r in data}


def load_track_metadata() -> dict[str, dict[str, Any]]:
    ds = load_dataset(
        "talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks"
    )
    return {r["track_id"]: r for r in ds}


def load_devset_conversations() -> dict[str, list[dict[str, Any]]]:
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    return {r["session_id"]: r["conversations"] for r in ds}


def iter_trace(path: Path):
    """Stream the trace file (it's 1.2 GB) yielding one row at a time."""
    with path.open("rb") as fh:
        for row in ijson.items(fh, "item"):
            yield row


def classify(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] Loading predictions...")
    preds = load_predictions(Path(args.predictions))
    print(f"      {len(preds)} prediction rows")

    print("[2/5] Loading ground truth...")
    gt = load_ground_truth(Path(args.ground_truth))
    print(f"      {len(gt)} GT rows")

    print("[3/5] Loading track metadata (HF)...")
    tracks = load_track_metadata()
    print(f"      {len(tracks)} tracks")

    print("[4/5] Loading devset conversations (HF)...")
    convos = load_devset_conversations()
    print(f"      {len(convos)} sessions")

    print("[5/5] Streaming trace + classifying...")
    cohort: list[dict[str, Any]] = []
    n_total = 0
    n_failed = 0
    n_zero_pos_tags = 0
    n_cohort = 0
    n_gt_no_tags = 0
    token_counter: Counter[str] = Counter()

    for row in iter_trace(Path(args.trace)):
        n_total += 1
        sid, tn = row["session_id"], row["turn_number"]
        if (sid, tn) not in gt:
            continue
        gt_tid = gt[(sid, tn)]

        # "Failed" = GT not in top-20 predictions (writeup denominator).
        pred = preds.get((sid, tn), [])
        in_top20 = gt_tid in pred[:20]
        if in_top20:
            continue
        n_failed += 1

        # Pull state from trace
        state = row.get("trace", {}).get("state", {}) or {}
        resolver = row.get("trace", {}).get("resolver", {}) or {}

        positive_tags = set(
            normalize(t) for t in (resolver.get("positive_tags") or [])
        )
        # Also fold mentioned_entities[type=tag, sentiment=1] in case resolver dedupes oddly
        for me in state.get("mentioned_entities", []) or []:
            if me.get("type") == "tag" and me.get("sentiment", 0) > 0:
                positive_tags.add(normalize(me.get("value", "")))

        if not positive_tags:
            n_zero_pos_tags += 1

        # GT tag tokens
        gt_track = tracks.get(gt_tid)
        if not gt_track:
            continue
        gt_tags = gt_track.get("tag_list") or []
        gt_token_set: set[str] = set()
        for t in gt_tags:
            for tok in tag_to_tokens(t):
                gt_token_set.add(tok)
        if not gt_token_set:
            n_gt_no_tags += 1
            continue

        # User text from latest turn
        conversation = convos.get(sid, [])
        user_text = latest_user_text(conversation, tn)
        user_tokens = tokenize_text(user_text)

        # Tokens that the user literally said AND match a GT-tag word AND are NOT in positive_tags
        missed_literals = sorted(
            tok for tok in (gt_token_set & user_tokens)
            if tok not in positive_tags and not any(tok in pt for pt in positive_tags)
        )
        if not missed_literals:
            continue
        n_cohort += 1
        for tok in missed_literals:
            token_counter[tok] += 1

        cohort.append({
            "session_id": sid,
            "turn_number": tn,
            "gt_track_id": gt_tid,
            "gt_track_name": (gt_track.get("track_name") or [""])[0],
            "gt_artist_name": (gt_track.get("artist_name") or [""])[0],
            "gt_tags": gt_tags,
            "state_positive_tags": sorted(positive_tags),
            "state_turn_intent": state.get("turn_intent", ""),
            "user_text_latest_turn": user_text,
            "missed_literal_tokens": missed_literals,
            "in_top1000": gt_tid in pred[:1000],
        })

    # --- Write artifacts -------------------------------------------------
    jsonl_path = out_dir / "cohort_missed_literal_tags.jsonl"
    with jsonl_path.open("w") as fh:
        for r in cohort:
            fh.write(json.dumps(r) + "\n")

    summary = {
        "n_trace_rows": n_total,
        "n_failed_top20": n_failed,
        "n_zero_positive_tags": n_zero_pos_tags,
        "n_cohort_missed_literal_tags": n_cohort,
        "share_of_failed": (n_cohort / n_failed) if n_failed else 0,
        "n_gt_with_no_tag_tokens": n_gt_no_tags,
        "top_30_missed_tokens": token_counter.most_common(30),
    }
    (out_dir / "cohort_summary.json").write_text(json.dumps(summary, indent=2))
    print()
    print(json.dumps(summary, indent=2))

    # --- Pretty examples -------------------------------------------------
    examples = cohort[:: max(1, len(cohort) // 20)][:20]
    lines = ["# Sample cohort turns (extractor missed a GT-tag word the user literally said)\n"]
    for i, r in enumerate(examples, 1):
        lines.append(f"## Example {i} — {r['gt_artist_name']} – {r['gt_track_name']} "
                     f"(session {r['session_id'][:8]}, turn {r['turn_number']})\n")
        lines.append(f"**User said (latest turn):** {r['user_text_latest_turn']}\n")
        lines.append(f"**Extractor positive_tags:** `{r['state_positive_tags']}`\n")
        lines.append(f"**Extractor turn_intent:** {r['state_turn_intent']}\n")
        lines.append(f"**GT tags:** `{r['gt_tags']}`\n")
        lines.append(f"**Missed literal tokens:** `{r['missed_literal_tokens']}`\n")
        lines.append(f"**GT made top-1000:** {r['in_top1000']}\n")
        lines.append("")
    (out_dir / "cohort_examples.md").write_text("\n".join(lines))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--trace", default="evaluator/exp/inference/devset/v0plus_compiler_textside_v2_devset_trace.json")
    p.add_argument("--predictions", default="evaluator/exp/inference/devset/v0plus_compiler_textside_v2_devset.json")
    p.add_argument("--ground-truth", default="evaluator/exp/ground_truth/devset.json")
    p.add_argument("--out-dir", default="experiments/analysis/extractor_prompt_v2/artifacts")
    classify(p.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
