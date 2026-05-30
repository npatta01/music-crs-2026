"""Fallback: run the cohort classification ON Modal (avoid the 1.24 GB
local download flake). Returns just the cohort jsonl (~1k rows = small).

Usage:
  modal run experiments/analysis/extractor_prompt_v2/scripts/classify_on_modal.py
"""

from __future__ import annotations

import json
import modal
import re
from pathlib import Path

# Use the same volume the inference writes to.
results_vol = modal.Volume.from_name("music-crs-results", create_if_missing=False)
hf_cache_vol = modal.Volume.from_name("music-crs-hf-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("ijson==3.5", "datasets>=2.18", "huggingface-hub>=0.22")
)

app = modal.App("extractor-prompt-v2-classify")

STOPWORDS = {
    "a","an","and","or","of","the","to","in","on","at","for","with","is","it",
    "by","as","be","that","this","i","you","me","my","your","we","us","like",
    "from","but","not","so","very","more","some","any","other","just",
    "music","song","songs","track","tracks","artist","band",
}

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")


def normalize(s: str) -> str:
    return s.strip().lower()


def tokenize_text(text: str) -> set[str]:
    return {WORD_RE.findall(text or "")[i].lower()
            for i in range(len(WORD_RE.findall(text or "")))}


def tag_to_tokens(tag: str) -> list[str]:
    raw = WORD_RE.findall(tag or "")
    return [t.lower() for t in raw
            if len(t) >= 3 and t.lower() not in STOPWORDS and not t.isdigit()]


def latest_user_text(conversation, turn_number):
    parts = []
    for t in conversation:
        if t.get("turn_number") == turn_number and t.get("role") == "user":
            parts.append(t.get("content", ""))
    return " ".join(parts)


@app.function(
    image=image,
    volumes={
        "/data/results": results_vol,
        "/data/hf-cache": hf_cache_vol,
    },
    timeout=3600,
    memory=8192,
)
def classify_remote() -> tuple[list[dict], dict]:
    import ijson
    import os
    from datasets import load_dataset

    os.environ.setdefault("HF_DATASETS_CACHE", "/data/hf-cache/datasets")
    os.environ.setdefault("HF_HOME", "/data/hf-cache")

    trace_path = Path("/data/results/inference/devset/v0plus_compiler_textside_v2_devset_trace.json")
    pred_path  = Path("/data/results/inference/devset/v0plus_compiler_textside_v2_devset.json")
    gt_path    = Path("/data/results/ground_truth/devset.json")

    print(f"trace size: {trace_path.stat().st_size:,}")

    print("loading predictions...")
    with pred_path.open() as fh:
        preds = {(r["session_id"], r["turn_number"]): r["predicted_track_ids"] for r in json.load(fh)}
    print(f"  {len(preds)} prediction rows")

    print("loading GT...")
    with gt_path.open() as fh:
        gt = {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"] for r in json.load(fh)}
    print(f"  {len(gt)} GT rows")

    print("loading track metadata...")
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks")
    tracks = {r["track_id"]: r for r in ds}
    print(f"  {len(tracks)} tracks")

    print("loading devset conversations...")
    cv = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    convos = {r["session_id"]: r["conversations"] for r in cv}
    print(f"  {len(convos)} sessions")

    print("streaming trace + classifying...")
    cohort = []
    n_total = n_failed = n_cohort = n_zero_pos = 0
    with trace_path.open("rb") as fh:
        for row in ijson.items(fh, "item"):
            n_total += 1
            sid, tn = row["session_id"], row["turn_number"]
            if (sid, tn) not in gt:
                continue
            gt_tid = gt[(sid, tn)]
            pred = preds.get((sid, tn), [])
            if gt_tid in pred[:20]:
                continue
            n_failed += 1

            state = row.get("trace", {}).get("state", {}) or {}
            resolver = row.get("trace", {}).get("resolver", {}) or {}
            positive_tags = {normalize(t) for t in (resolver.get("positive_tags") or [])}
            for me in state.get("mentioned_entities", []) or []:
                if me.get("type") == "tag" and me.get("sentiment", 0) > 0:
                    positive_tags.add(normalize(me.get("value", "")))
            if not positive_tags:
                n_zero_pos += 1

            gt_track = tracks.get(gt_tid)
            if not gt_track:
                continue
            gt_tags = gt_track.get("tag_list") or []
            gt_token_set = set()
            for t in gt_tags:
                for tok in tag_to_tokens(t):
                    gt_token_set.add(tok)
            if not gt_token_set:
                continue

            user_text = latest_user_text(convos.get(sid, []), tn)
            user_tokens = {WORD_RE.findall(user_text)[i].lower()
                           for i in range(len(WORD_RE.findall(user_text)))}
            missed = sorted(tok for tok in (gt_token_set & user_tokens)
                            if tok not in positive_tags
                            and not any(tok in pt for pt in positive_tags))
            if not missed:
                continue
            n_cohort += 1
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
                "missed_literal_tokens": missed,
                "in_top1000": gt_tid in pred[:1000],
            })

    summary = {
        "n_trace_rows": n_total,
        "n_failed_top20": n_failed,
        "n_zero_positive_tags": n_zero_pos,
        "n_cohort_missed_literal_tags": n_cohort,
        "share_of_failed": n_cohort / max(n_failed, 1),
    }
    print(json.dumps(summary, indent=2))
    return cohort, summary


@app.local_entrypoint()
def main():
    cohort, summary = classify_remote.remote()
    out_dir = Path("experiments/analysis/extractor_prompt_v2/artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "cohort_missed_literal_tags.jsonl").open("w") as fh:
        for r in cohort:
            fh.write(json.dumps(r) + "\n")
    (out_dir / "cohort_summary.json").write_text(json.dumps(summary, indent=2))
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
    print(f"Wrote {len(cohort)} cohort rows + summary + 20 examples")
