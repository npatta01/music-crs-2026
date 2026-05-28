"""One-off: intent_mode vs novel-artist cohort audit on v0plus_compiler_image_devset traces."""
import json
import glob
from collections import Counter, defaultdict
from datasets import load_dataset

TRACE_GLOB = "evaluator/exp/inference/devset/v0plus_compiler_image_devset.shard_*_trace.json"
GT_PATH = "evaluator/exp/ground_truth/devset.json"


def load_traces():
    rows = []
    for path in sorted(glob.glob(TRACE_GLOB)):
        with open(path) as f:
            rows.extend(json.load(f))
    return rows


def load_gt():
    with open(GT_PATH) as f:
        gt = json.load(f)
    return {(r["session_id"], r["turn_number"]): r["ground_truth_track_id"] for r in gt}


def _norm_artist(a):
    if isinstance(a, list):
        return tuple(sorted(a))
    return a


def load_track_to_artist():
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks")
    return {r["track_id"]: _norm_artist(r["artist_name"]) for r in ds}


def load_conversations():
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    out = {}
    for sess in ds:
        out[sess["session_id"]] = sess
    return out


def main():
    traces = load_traces()
    gt = load_gt()
    t2a = load_track_to_artist()
    convos = load_conversations()
    print(f"traces: {len(traces)}, gt: {len(gt)}, tracks: {len(t2a)}, sessions: {len(convos)}")

    # build per-session ordered turn list to compute "prior accepted artists"
    by_session = defaultdict(list)
    for tr in traces:
        by_session[tr["session_id"]].append(tr)
    for sid in by_session:
        by_session[sid].sort(key=lambda r: r["turn_number"])

    rows = []
    for sid, turns in by_session.items():
        sess = convos.get(sid)
        if sess is None:
            continue
        # build prior-accepted-artists set incrementally from the conversation's prior music turns
        # use the GT-style "accepted" via the session's actual played tracks list ordered by turn
        # the dataset format: each session has a `conversation` list with turns containing track_ids
        prior_artists = set()
        for tr in turns:
            tn = tr["turn_number"]
            gt_tid = gt.get((sid, tn))
            gt_artist = t2a.get(gt_tid) if gt_tid else None
            trace = tr.get("trace") or {}
            state = trace.get("state") or {}
            intent = trace.get("intent_mode") or state.get("intent_mode") or "NONE"
            novel = (gt_artist is not None and gt_artist not in prior_artists)
            # user utterance: try to pull from session conversation
            user_text = None
            try:
                conv = sess.get("conversations") or []
                # find the user message with turn_number == tn
                for m in conv:
                    if m.get("role") == "user" and m.get("turn_number") == tn:
                        user_text = m.get("content")
                        break
            except Exception:
                pass

            rows.append({
                "session_id": sid,
                "turn": tn,
                "intent_mode": intent,
                "gt_artist": gt_artist,
                "novel": novel,
                "n_prior_artists": len(prior_artists),
                "user_text": (user_text or "")[:200],
            })
            if gt_artist:
                prior_artists.add(gt_artist)

    # Cross-tab 1: intent_mode distribution overall
    intent_counts = Counter(r["intent_mode"] for r in rows)
    print("\n=== overall intent_mode distribution ===")
    total = sum(intent_counts.values())
    for k, v in intent_counts.most_common():
        print(f"  {k!s:>18}  {v:>6}  ({v/total:.1%})")

    # Cross-tab 2: novel-artist by intent_mode
    print("\n=== novel-artist rate by intent_mode ===")
    by_intent = defaultdict(lambda: [0, 0])
    for r in rows:
        by_intent[r["intent_mode"]][0] += int(r["novel"])
        by_intent[r["intent_mode"]][1] += 1
    for k, (nov, n) in sorted(by_intent.items(), key=lambda x: -x[1][1]):
        print(f"  {k!s:>18}  novel={nov:>5}/{n:<5} ({nov/n:.1%})")

    # Cross-tab 3: novel-artist turns broken down by cold-start vs has-prior
    print("\n=== novel-artist sub-cohorts ===")
    cold_start = sum(1 for r in rows if r["novel"] and r["n_prior_artists"] == 0)
    has_prior = sum(1 for r in rows if r["novel"] and r["n_prior_artists"] > 0)
    novel_total = sum(1 for r in rows if r["novel"])
    print(f"  cold-start (no prior artists)        : {cold_start:>5}  ({cold_start/novel_total:.1%} of novel)")
    print(f"  has-prior (genuinely novel mid-conv) : {has_prior:>5}  ({has_prior/novel_total:.1%} of novel)")
    print(f"  total novel                          : {novel_total}  ({novel_total/len(rows):.1%} of all turns)")

    # Cross-tab 4: intent_mode for novel mid-conversation (the cohort we'd hope is pivot/explore)
    print("\n=== intent_mode for novel-artist turns WITH prior plays (i.e., genuinely novel mid-conv) ===")
    novel_mid = [r for r in rows if r["novel"] and r["n_prior_artists"] > 0]
    c = Counter(r["intent_mode"] for r in novel_mid)
    for k, v in c.most_common():
        print(f"  {k!s:>18}  {v:>5}  ({v/len(novel_mid):.1%})")

    # sample novel mid-conv turns with their user text (for qualitative inspection)
    print("\n=== 15 sample novel-artist mid-conv turns (text snippets) ===")
    samp = [r for r in novel_mid if r["user_text"]][:15]
    for r in samp:
        print(f"  [intent={r['intent_mode']!s:>12} t{r['turn']}] {r['user_text'][:140]}")


if __name__ == "__main__":
    main()
