"""Bucket ALL R2 failures (GT not in top-20) by the dataset's own goal category
(A-K) + specificity (HH/HL/LH/LL), and split each bucket into:
  - extractor-addressable: GT-tag word literally in user text but not extracted
  - needs-other-branch: audio/lyric/visual/geography categories
  - low-ceiling: low target specificity (LH/LL — vague target)

This tells us where the ceiling actually is, using the GENERATION PROCESS's own
labels rather than reverse-engineering from text.

The TalkPlayData-2 goal taxonomy (from the paper / HF card):
  A Audio-Based Discovery       → needs CLAP audio branch
  B Lyrical Discovery           → needs lyric text (we lack raw lyrics)
  C Visual-Musical Connections  → needs SigLIP image branch
  D Contextual & Situational    → mood/activity tags (extractor-addressable)
  E Interactive Refinement      → multi-genre refinement (anchors + tags)
  F Metadata-Rich Exploration   → album/collection (entity anchor)
  G Mood & Emotion-Based        → mood tags (extractor-addressable)
  H Artist & Discography        → artist anchor (extractor-addressable)
  I Cultural & Geographic       → artist geography (we likely lack the field)
  J Social & Popularity         → popularity prior
  K Temporal & Era Discovery    → release_date hard_filter (extractor-addressable)

Run: modal run .../failures_by_goal_category_on_modal.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import modal

results_vol = modal.Volume.from_name("music-crs-results", create_if_missing=False)
hf_cache_vol = modal.Volume.from_name("music-crs-hf-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("ijson==3.5", "datasets>=2.18", "huggingface-hub>=0.22")
)
app = modal.App("failures-by-goal-category")

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")
STOP = {"a","an","and","or","of","the","to","in","on","at","for","with","is","it",
        "by","as","be","that","this","i","you","me","my","like","from","but","not",
        "music","song","songs","track","tracks","artist","band","good","love","great"}

# Categories whose primary signal the v0+ extractor + current branches CAN attack.
EXTRACTOR_ADDRESSABLE = {"D", "G", "K", "H", "F", "E"}
# Categories that fundamentally need a branch we don't fully have.
NEEDS_OTHER_BRANCH = {"A", "B", "C", "I", "J"}


def tag_tokens(tags):
    out = set()
    for t in tags or []:
        for m in WORD_RE.finditer(t or ""):
            w = m.group(0).lower()
            if len(w) >= 3 and w not in STOP and not w.isdigit():
                out.add(w)
    return out


def user_tokens_for_turn(conv, tn):
    parts = [t.get("content", "") for t in conv
             if t.get("turn_number") == tn and t.get("role") == "user"]
    text = " ".join(parts)
    return {WORD_RE.findall(text)[i].lower() for i in range(len(WORD_RE.findall(text)))}


@app.function(image=image,
              volumes={"/data/results": results_vol, "/data/hf-cache": hf_cache_vol},
              timeout=3600, memory=8192)
def run():
    import os, ijson
    from collections import defaultdict
    from datasets import load_dataset
    os.environ.setdefault("HF_DATASETS_CACHE", "/data/hf-cache/datasets")
    os.environ.setdefault("HF_HOME", "/data/hf-cache")

    base = Path("/data/results/inference/devset")
    trace = base / "v0plus_compiler_textside_v2_devset_trace.json"
    preds = base / "v0plus_compiler_textside_v2_devset.json"
    gt_path = Path("/data/results/ground_truth/devset.json")

    with preds.open() as fh:
        pred = {(r["session_id"], r["turn_number"]): r["predicted_track_ids"] for r in json.load(fh)}
    with gt_path.open() as fh:
        gt = {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"] for r in json.load(fh)}

    tracks = {r["track_id"]: r for r in load_dataset(
        "talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks")}

    dev = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    goal_by_sid = {r["session_id"]: r["conversation_goal"] for r in dev}
    conv_by_sid = {r["session_id"]: r["conversations"] for r in dev}

    # category -> counters
    cat_total = defaultdict(int)        # all turns of that category that we evaluated
    cat_fail = defaultdict(int)         # failed turns (GT not top20)
    cat_fail_addressable = defaultdict(int)  # failed AND a GT-tag word literally said
    spec_fail = defaultdict(int)
    spec_total = defaultdict(int)
    # cross: category x extractor-addressable
    fail_by_cat_spec = defaultdict(int)

    n = 0
    with trace.open("rb") as fh:
        for row in ijson.items(fh, "item"):
            n += 1
            sid, tn = row["session_id"], row["turn_number"]
            key = (sid, tn)
            if key not in gt:
                continue
            goal = goal_by_sid.get(sid) or {}
            cat = goal.get("category", "?")
            spec = goal.get("specificity", "?")
            cat_total[cat] += 1
            spec_total[spec] += 1

            gt_tid = gt[key]
            if gt_tid in pred.get(key, [])[:20]:
                continue  # success
            cat_fail[cat] += 1
            spec_fail[spec] += 1
            fail_by_cat_spec[(cat, spec)] += 1

            # extractor-addressable test: GT-tag word literally said by user, but
            # extractor positive_tags didn't capture it.
            gt_track = tracks.get(gt_tid) or {}
            gt_toks = tag_tokens(gt_track.get("tag_list") or [])
            if not gt_toks:
                continue
            utoks = user_tokens_for_turn(conv_by_sid.get(sid, []), tn)
            resolver = row.get("trace", {}).get("resolver", {}) or {}
            pos = {p.lower() for p in (resolver.get("positive_tags") or [])}
            missed = [t for t in (gt_toks & utoks)
                      if t not in pos and not any(t in p for p in pos)]
            if missed:
                cat_fail_addressable[cat] += 1

    return {
        "n_trace_rows": n,
        "cat_total": dict(cat_total),
        "cat_fail": dict(cat_fail),
        "cat_fail_addressable": dict(cat_fail_addressable),
        "spec_total": dict(spec_total),
        "spec_fail": dict(spec_fail),
        "fail_by_cat_spec": {f"{c}/{s}": v for (c, s), v in fail_by_cat_spec.items()},
    }


@app.local_entrypoint()
def main():
    out = run.remote()
    p = Path("experiments/analysis/extractor_prompt_v2/artifacts/failures_by_goal_category.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))

    CAT_NAMES = {
        "A": "Audio-Based Discovery", "B": "Lyrical Discovery",
        "C": "Visual-Musical", "D": "Contextual/Situational",
        "E": "Interactive Refinement", "F": "Metadata-Rich",
        "G": "Mood & Emotion", "H": "Artist & Discography",
        "I": "Cultural & Geographic", "J": "Social & Popularity",
        "K": "Temporal & Era",
    }
    ADDRESSABLE = {"D","G","K","H","F","E"}
    cf = out["cat_fail"]; ct = out["cat_total"]; ca = out["cat_fail_addressable"]
    total_fail = sum(cf.values())
    print(f"\n{'cat':<4}{'name':<24}{'fails':>7}{'fail%':>7}{'failrate':>9}{'lit-addr':>9}  branch")
    print("-" * 78)
    for cat in sorted(cf, key=lambda c: -cf.get(c, 0)):
        name = CAT_NAMES.get(cat, "?")
        fails = cf[cat]
        share = fails / max(total_fail, 1)
        failrate = fails / max(ct.get(cat, 1), 1)
        addr = ca.get(cat, 0)
        tag = "EXTRACTOR" if cat in ADDRESSABLE else "needs-branch"
        print(f"{cat:<4}{name:<24}{fails:>7}{share*100:>6.1f}%{failrate*100:>8.1f}%{addr:>9}  {tag}")
    print(f"\nTotal failures: {total_fail}")
    print(f"In extractor-addressable categories: {sum(cf.get(c,0) for c in ADDRESSABLE)} "
          f"({sum(cf.get(c,0) for c in ADDRESSABLE)/max(total_fail,1)*100:.1f}%)")
    print(f"In needs-other-branch categories:    {sum(cf.get(c,0) for c in cf if c not in ADDRESSABLE)} "
          f"({sum(cf.get(c,0) for c in cf if c not in ADDRESSABLE)/max(total_fail,1)*100:.1f}%)")
    print("\nBy specificity (fail / total):")
    for s in ("HH","HL","LH","LL","?"):
        if s in out["spec_fail"]:
            print(f"  {s}: {out['spec_fail'][s]} / {out['spec_total'].get(s,0)} "
                  f"({out['spec_fail'][s]/max(out['spec_total'].get(s,1),1)*100:.1f}% fail)")
    print(f"\nWrote {p}")
