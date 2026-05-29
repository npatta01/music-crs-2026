"""Sample ~250 mid-conversation turns from devset, run the NEW extractor with
process_constraints, and cross-tab exploration_policy vs novel-artist-GT.

Tells us, empirically:
  - In the `diversify_artists` cohort, what % of GTs are continuation
    (i.e., would be lost by a hard filter on played artists)?
  - In the `exploit` cohort, what % of GTs are novel-artist
    (i.e., where exploit might be wrong)?

Cost: ~250 × $0.005 = ~$1.25 in OpenRouter calls.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datasets import load_dataset

from experiments.analysis.conversation_state_extraction_bakeoff.prompts import (  # noqa: E402
    build_messages,
    json_schema_for_response_format,
)
from experiments.analysis.conversation_state_extraction_bakeoff.schema import (  # noqa: E402
    ConversationStateV0Plus,
)

MODEL = "openrouter/google/gemma-3-12b-it"
SAMPLE_SIZE = 250
SEED = 42


def _norm_artist(a):
    if isinstance(a, list):
        return tuple(sorted(a))
    return a


def load_track_to_artist():
    ds = load_dataset(
        "talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks"
    )
    return {r["track_id"]: _norm_artist(r["artist_name"]) for r in ds}


def load_track_to_label(t2a):
    ds = load_dataset(
        "talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks"
    )
    out = {}
    for r in ds:
        a = _norm_artist(r["artist_name"])
        artist_str = " / ".join(a) if isinstance(a, tuple) else (a or "?")
        out[r["track_id"]] = f"{artist_str} - {r['track_name']}"
    return out


def load_gt():
    with open("evaluator/exp/ground_truth/devset.json") as f:
        gt = json.load(f)
    return {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"] for r in gt}


def build_extractor_conv(sess_conv, t2label, up_to_turn: int):
    """Convert dataset 'conversations' list into extractor format up to (and including
    music turns from) `up_to_turn-1`. The user's turn `up_to_turn` is the latest input.
    Returns (conv, played_track_ids).
    """
    conv = []
    played = []
    for m in sess_conv:
        tn = m.get("turn_number")
        role = m.get("role")
        if tn is None or role is None:
            continue
        if tn > up_to_turn:
            break
        if role == "user" and tn == up_to_turn:
            conv.append({"turn": tn, "role": "user", "text": m.get("content", "")})
            break
        if role == "user":
            conv.append({"turn": tn, "role": "user", "text": m.get("content", "")})
        elif role == "assistant":
            conv.append({"turn": tn, "role": "assistant", "text": m.get("content", "")})
        elif role == "music":
            tid = m.get("content")
            if tid:
                played.append(tid)
                conv.append({"turn": tn, "role": "music", "track_id": tid, "label": t2label.get(tid, tid)})
    return conv, played


async def extract_one(case):
    import litellm

    try:
        messages = build_messages(case["conv"], case["played"])
        resp = await litellm.acompletion(
            model=MODEL,
            messages=messages,
            temperature=0.0,
            max_tokens=1500,
            timeout=90,
            response_format=json_schema_for_response_format(),
            extra_body={"reasoning": {"enabled": False}},
        )
        raw = resp.choices[0].message.content or ""
        parsed = json.loads(raw)
        state = ConversationStateV0Plus.model_validate(parsed)
        return {
            "session_id": case["session_id"],
            "turn": case["turn"],
            "intent_mode": state.intent_mode.value,
            "exploration_policy": state.process_constraints.exploration_policy.value,
            "novel": case["novel"],
            "n_prior_artists": case["n_prior_artists"],
            "user_text": case["user_text"][:200],
        }
    except Exception as e:
        return {"session_id": case["session_id"], "turn": case["turn"], "error": f"{type(e).__name__}: {e}"}


async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    assert os.environ.get("OPENROUTER_API_KEY"), "OPENROUTER_API_KEY required"

    print("loading metadata + gt + conversations...")
    t2a = load_track_to_artist()
    t2label = load_track_to_label(t2a)
    gt = load_gt()
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    sessions = {s["session_id"]: s for s in ds}
    print(f"  sessions: {len(sessions)}, tracks: {len(t2a)}")

    # Build candidate cases: mid-conversation turns (turn >= 2) only, with prior artists.
    candidates = []
    for sid, sess in sessions.items():
        prior_artists = set()
        for m in sess["conversations"]:
            tn = m.get("turn_number")
            role = m.get("role")
            if role != "user" or tn is None or tn < 2:
                # only build a "case" for user turns at tn >= 2
                if role == "music":
                    tid = m.get("content")
                    if tid and t2a.get(tid):
                        prior_artists.add(t2a[tid])
                continue
            # current state: build candidate for THIS user turn
            if not prior_artists:
                continue
            gt_tid = gt.get((sid, tn))
            if not gt_tid:
                continue
            gt_artist = t2a.get(gt_tid)
            if gt_artist is None:
                continue
            novel = gt_artist not in prior_artists
            conv, played = build_extractor_conv(sess["conversations"], t2label, tn)
            candidates.append({
                "session_id": sid,
                "turn": tn,
                "novel": novel,
                "n_prior_artists": len(prior_artists),
                "user_text": m.get("content", ""),
                "conv": conv,
                "played": played,
            })

    random.seed(SEED)
    random.shuffle(candidates)
    sample = candidates[:SAMPLE_SIZE]
    print(f"  sampled {len(sample)} mid-conv turns (out of {len(candidates)} eligible)")
    novel_in_sample = sum(1 for c in sample if c["novel"])
    print(f"  novel-artist rate in sample: {novel_in_sample}/{len(sample)} ({novel_in_sample/len(sample):.1%})")

    # Run extractor in parallel (batched)
    print("running extractor...")
    BATCH = 8
    results = []
    for i in range(0, len(sample), BATCH):
        chunk = sample[i : i + BATCH]
        out = await asyncio.gather(*(extract_one(c) for c in chunk))
        results.extend(out)
        print(f"  {i + len(chunk)}/{len(sample)}", end="\r", flush=True)
    print()

    ok = [r for r in results if "error" not in r]
    fail = [r for r in results if "error" in r]
    print(f"  extracted ok: {len(ok)}, failed: {len(fail)}")

    # Cross-tab: exploration_policy × novel-artist
    print("\n=== exploration_policy × novel-artist (continuation) ===")
    by_policy = defaultdict(lambda: {"novel": 0, "cont": 0})
    for r in ok:
        b = by_policy[r["exploration_policy"]]
        b["novel" if r["novel"] else "cont"] += 1
    print(f"  {'policy':<20} {'novel':>7} {'cont':>7} {'total':>7} {'novel%':>8} {'cont%':>8}")
    for p, b in sorted(by_policy.items(), key=lambda kv: -(kv[1]["novel"] + kv[1]["cont"])):
        n = b["novel"] + b["cont"]
        print(f"  {p:<20} {b['novel']:>7} {b['cont']:>7} {n:>7} {b['novel']/n:>7.0%}  {b['cont']/n:>7.0%}")

    print("\n=== intent_mode × novel-artist (for comparison) ===")
    by_intent = defaultdict(lambda: {"novel": 0, "cont": 0})
    for r in ok:
        b = by_intent[r["intent_mode"]]
        b["novel" if r["novel"] else "cont"] += 1
    print(f"  {'intent':<20} {'novel':>7} {'cont':>7} {'total':>7} {'novel%':>8} {'cont%':>8}")
    for p, b in sorted(by_intent.items(), key=lambda kv: -(kv[1]["novel"] + kv[1]["cont"])):
        n = b["novel"] + b["cont"]
        print(f"  {p:<20} {b['novel']:>7} {b['cont']:>7} {n:>7} {b['novel']/n:>7.0%}  {b['cont']/n:>7.0%}")

    # Hard-filter cost simulation:
    # If hard filter on played-artist when exploration_policy ∈ {diversify_artists, diversify_albums},
    # the GT on continuation turns within that cohort is lost (Hit@20 → 0 for those).
    print("\n=== hard-filter cost on continuation GT within each policy cohort ===")
    print("  (these are GTs you would PERMANENTLY exclude if you hard-filter on played artists)")
    for p, b in by_policy.items():
        n = b["novel"] + b["cont"]
        if n == 0:
            continue
        print(f"  policy={p:<20}  cohort={n:>4}  continuation-GT={b['cont']:>3} ({b['cont']/n:.0%}) ← these would be ZEROED")

    # Save full per-row results
    out = Path("scripts/exploration_policy_sample_audit_results.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"\nfull results: {out}")


if __name__ == "__main__":
    asyncio.run(main())
