"""Build the labelable universe for the anchoring data-clean from the TalkPlayData train split.

A turn `tn` is labelable iff: a track was played at `tn` AND `assessment[tn+1]` is non-null
(off-by-one: assessment[tn+1] grades track[tn]; the last track per session is unlabeled). For each:
  reaction    = MOVES / DOES_NOT   (from assessment[tn+1])
  same_artist = deterministic catalog match (candidate artist == just-played artist)
  track_meta  = candidate doc text
  request     = FULL conversation up to the current ask (assistant-stripped, played-markers kept)

Writes a lightweight universe file (ids + flags) and a JUDGE-READY sheet (with request + track_meta)
for a stratified sample that oversamples same_artist=True (the anchoring-relevant cell).

  python scripts/rerank/anchor_labels/build_anchor_universe.py --sample-n 2000          # validation sheet
  python scripts/rerank/anchor_labels/build_anchor_universe.py --expand-all             # full judge-ready sheet
"""
from __future__ import annotations
import argparse, json, os, random, sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, REPO)
from scripts.rerank.anchor_labels.convo_context import (  # noqa: E402
    load_index, load_docmap, build_full_request, candidate_tid, same_artist)

# Artifacts dir: defaults to the local repo's exp/analysis/retrieval_exploration.
# Set ANCHOR_DATA_DIR to point elsewhere (e.g. a shared cache; see scripts/setup_worktree_cache.py).
DD = os.environ.get("ANCHOR_DATA_DIR", os.path.join(REPO, "exp/analysis/retrieval_exploration"))
MOVES = "MOVES_TOWARD_GOAL"


def labelable_turns(sid2row, doc):
    """Yield lightweight rows for every labelable (sid, tn)."""
    for sid, row in sid2row.items():
        gpa = {a["turn_number"]: a["goal_progress_assessment"] for a in row["goal_progress_assessments"]}
        music_turns = {t["turn_number"] for t in row["conversations"] if t["role"] == "music"}
        for tn in sorted(music_turns):
            nxt = gpa.get(tn + 1)
            if nxt is None:                      # last track / ungraded -> drop
                continue
            cand = candidate_tid(sid, tn, sid2row)
            if cand not in doc:                  # candidate not resolvable -> skip
                continue
            yield {"sid": sid, "tn": tn,
                   "gt_label": "MOVES" if nxt == MOVES else "DOES_NOT",
                   "same_artist": same_artist(sid, tn, sid2row, doc),
                   "cand_tid": cand}


def to_sheet_row(r, sid2row, doc, ctx_turns=3):
    """Expand a lightweight row into a judge-ready sheet row (last `ctx_turns` turns of context)."""
    return {"sid": r["sid"], "tn": r["tn"], "gt_label": r["gt_label"], "same_artist": r["same_artist"],
            "request": build_full_request(r["sid"], r["tn"], sid2row, doc, max_turns=ctx_turns),
            "track_meta": doc[r["cand_tid"]]["doc"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train")
    ap.add_argument("--doc", default=f"{DD}/doc_corpus.jsonl")
    ap.add_argument("--out-universe", default=f"{DD}/anchor_universe_train.jsonl")
    ap.add_argument("--out-sample", default=f"{DD}/judge_bakeoff/sheet_strat2k_train.jsonl")
    ap.add_argument("--sample-n", type=int, default=2000)
    ap.add_argument("--sa-frac", type=float, default=0.6, help="fraction of sample forced same_artist=True")
    ap.add_argument("--expand-all", action="store_true", help="write the FULL judge-ready sheet too")
    ap.add_argument("--out-full", default=f"{DD}/judge_bakeoff/sheet_full_train.jsonl")
    ap.add_argument("--ctx-turns", type=int, default=3, help="turns of conversation context per row")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    print(f"loading {a.split} index + doc_corpus ...", flush=True)
    sid2row = load_index(a.split)
    doc = load_docmap(a.doc)

    uni = list(labelable_turns(sid2row, doc))
    with open(a.out_universe, "w") as f:
        for r in uni:
            f.write(json.dumps(r) + "\n")

    n = len(uni)
    sa = [r for r in uni if r["same_artist"]]
    print(f"\n=== labelable universe ({a.split}) ===")
    print(f"  turns: {n}   sessions: {len({r['sid'] for r in uni})}")
    print(f"  reaction: {dict(Counter(r['gt_label'] for r in uni))}")
    print(f"  same_artist=True: {len(sa)} ({len(sa)/n:.1%})")
    print(f"  same_artist=True x reaction: {dict(Counter(r['gt_label'] for r in sa))}")
    print(f"  -> universe written: {a.out_universe}")

    # stratified sample: oversample same_artist=True to --sa-frac
    rng = random.Random(a.seed)
    sa_t = [r for r in uni if r["same_artist"]]
    sa_f = [r for r in uni if not r["same_artist"]]
    rng.shuffle(sa_t); rng.shuffle(sa_f)
    n_t = min(len(sa_t), int(a.sample_n * a.sa_frac))
    n_f = min(len(sa_f), a.sample_n - n_t)
    sample = sa_t[:n_t] + sa_f[:n_f]
    rng.shuffle(sample)
    os.makedirs(os.path.dirname(a.out_sample), exist_ok=True)
    with open(a.out_sample, "w") as f:
        for r in sample:
            f.write(json.dumps(to_sheet_row(r, sid2row, doc, a.ctx_turns)) + "\n")
    print(f"\n=== stratified sample (n={len(sample)}) ===")
    print(f"  same_artist: {dict(Counter(r['same_artist'] for r in sample))}")
    print(f"  cells (same_artist,reaction): {dict(Counter((r['same_artist'], r['gt_label']) for r in sample))}")
    print(f"  -> judge-ready sheet written: {a.out_sample}")

    if a.expand_all:
        with open(a.out_full, "w") as f:
            for r in uni:
                f.write(json.dumps(to_sheet_row(r, sid2row, doc, a.ctx_turns)) + "\n")
        print(f"\n  -> FULL judge-ready sheet written: {a.out_full} ({n} rows)")


if __name__ == "__main__":
    main()
