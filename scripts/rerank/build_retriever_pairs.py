"""M0b — assemble variant-agnostic training pairs for the bi-encoder retriever.

Per TRAIN turn emit:
    {sid, tn, gpa, q, pos_id, negs_filt, negs_raw}
  - q       : raw query content "[goal] <goal> [msg] <last 1-2 user turns + current>"
              (the "Instruct: ...\\nQuery: " prefix is applied at encode time, not stored).
  - pos_id  : the played (ground-truth) track at this turn.
  - gpa     : goal_progress_assessment for this turn (e.g. MOVES_TOWARD_GOAL / DOES_NOT_*).
  - negs_raw  : mined hard-negative track ids (<=8).
  - negs_filt : negs_raw minus false-negatives (drop any neg sharing the GT's artist OR
                >=2 of the GT's top-5 cleaned tags) — the FN-filter; the trainer ablates filt vs raw.

The LABEL POLICY is applied by the trainer, not here, so this file feeds all 3 ablation
variants from one build:
    (a) all turns positive
    (b) only gpa==MOVES_TOWARD_GOAL positive (drop the rest)
    (c) (b) + each MOVES turn's negatives augmented with its session's DOES_NOT played tracks
        (soft, session-local negatives — the goal is constant within a session).

HARD pre-check: asserts no session_id is shared between the train split and the devset
(`exp/ground_truth/devset.json`) before writing — a leak guard.

Run from the main checkout. Example:
    python scripts/rerank/build_retriever_pairs.py --out exp/analysis/retrieval_exploration/retriever_pairs.jsonl
"""
from __future__ import annotations
import argparse, ast, json, os, sys
sys.path.insert(0, "scripts/rerank")
from datasets import load_dataset
from build_doc_corpus import load_catalog, select_tags  # reuse exact tag cleaning

TRAIN_NEG = "exp/analysis/rerank/train_negatives_full.jsonl"
DEVSET_GT = "exp/ground_truth/devset.json"
MOVES = "MOVES_TOWARD_GOAL"


def load_split(split):
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split=split)
    um, goal, gpa, played = {}, {}, {}, {}
    sids = set()
    for r in ds:
        conv = r.get("conversations")
        if isinstance(conv, str):
            conv = ast.literal_eval(conv)
        cg = r.get("conversation_goal")
        if isinstance(cg, str):
            cg = ast.literal_eval(cg)
        sid = str(r["session_id"]); sids.add(sid); u = {}; p = {}
        for m in conv:
            tn = int(m["turn_number"])
            if m["role"] == "user":
                u[tn] = str(m["content"])
            elif m["role"] == "music":
                p.setdefault(tn, []).append(str(m["content"]))
        um[sid] = u; played[sid] = p
        goal[sid] = (cg or {}).get("listener_goal", "")
        g = r.get("goal_progress_assessments")
        if isinstance(g, str):
            g = ast.literal_eval(g)
        for a in (g or []):
            gpa[(sid, int(a["turn_number"]))] = a.get("goal_progress_assessment")
    return um, goal, gpa, played, sids


def build_q(um, goal, tn, recent=""):
    """Query = [goal] (+ optional [recent] played-artist anaphora context) + last 1-2 user turns.
    `recent` must be derived from tracks played STRICTLY BEFORE tn (no forward leak)."""
    turns = [um[k] for k in (tn - 1, tn) if um.get(k)]
    g = (goal or "").strip()
    head = f"[goal] {g} " if g else ""
    rec = f"[recent] {recent} " if recent else ""
    return (head + rec + "[msg] " + " / ".join(turns)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="exp/analysis/retrieval_exploration/retriever_pairs.jsonl")
    ap.add_argument("--min-tag-freq", type=int, default=20)
    ap.add_argument("--cap-tags", type=int, default=5)
    ap.add_argument("--max-negs", type=int, default=8)
    ap.add_argument("--recent-context", type=int, default=0,
                    help="prepend last-N recently-played ARTISTS to the query (anaphora; leak-safe)")
    ap.add_argument("--same-artist-keep", type=int, default=0,
                    help="keep up to N same-artist hard negs (within-artist precision) instead of dropping all")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)

    # track meta (artist + top-5 cleaned tags) for the FN-filter; reuse doc-corpus cleaning
    info = load_catalog()
    select_tags(info, a.min_tag_freq, a.cap_tags)
    meta = {d["tid"]: {"ar": d["ar"].lower(), "tags": set(d["tags"])} for d in info}
    artist_disp = {d["tid"]: d["ar"] for d in info}  # proper-case for query text
    valid = set(meta)
    print(f"catalog meta: {len(meta)} tracks", flush=True)

    print("loading train split...", flush=True)
    um, goal, gpa, played, train_sids = load_split("train")
    print(f"train sessions: {len(train_sids)}", flush=True)

    # HARD pre-check: train vs devset session disjointness
    dev = json.load(open(DEVSET_GT))
    dev_sids = {str(r["session_id"]) for r in dev}
    overlap = train_sids & dev_sids
    assert not overlap, f"LEAK: {len(overlap)} session_ids shared between train and devset, e.g. {list(overlap)[:3]}"
    print(f"disjointness OK: train {len(train_sids)} ∩ devset {len(dev_sids)} = 0", flush=True)

    def fn_filter(gt, negs, sa_keep=0):
        gm = meta.get(gt)
        if not gm:
            return negs
        out = []; sa = 0
        for nid in negs:
            nm = meta.get(nid)
            if not nm:
                continue
            if nm["ar"] and nm["ar"] == gm["ar"]:
                if sa < sa_keep:        # keep a few same-artist hard negs for within-artist precision
                    out.append(nid); sa += 1
                continue                 # else drop (likely-valid same-artist alternative)
            if gm["tags"] and len(nm["tags"] & gm["tags"]) >= 2:
                continue  # >=2 shared top tags -> too close, likely valid
            out.append(nid)
        return out

    def recent_artists(sid, tn, n):
        if not n:
            return ""
        seen = []
        for k in range(1, tn):
            for x in played.get(sid, {}).get(k, []):
                ar = artist_disp.get(x, "")
                if ar and ar not in seen:
                    seen.append(ar)
        return "; ".join(seen[-n:])

    n = 0; n_moves = 0; n_filtered_negs = 0; n_raw_negs = 0; gpa_counts = {}
    with open(a.out, "w") as f:
        for line in open(TRAIN_NEG):
            d = json.loads(line)
            sid = d["session_id"]; tn = int(d["turn_number"]); gt = str(d["gt"])
            if gt not in valid or not um.get(sid):
                continue
            negs_raw = [h["id"] for h in d["hard_negatives"] if h["id"] in valid][: a.max_negs]
            negs_filt = fn_filter(gt, negs_raw, a.same_artist_keep)
            g = gpa.get((sid, tn))
            gpa_counts[g] = gpa_counts.get(g, 0) + 1
            if g == MOVES:
                n_moves += 1
            n_raw_negs += len(negs_raw); n_filtered_negs += len(negs_filt)
            f.write(json.dumps({
                "sid": sid, "tn": tn, "gpa": g,
                "q": build_q(um[sid], goal[sid], tn, recent_artists(sid, tn, a.recent_context)),
                "pos_id": gt, "negs_filt": negs_filt, "negs_raw": negs_raw,
            }) + "\n")
            n += 1
            if n % 20000 == 0:
                print(f"  {n}", flush=True)
    print(f"DONE wrote {n} turns -> {a.out}", flush=True)
    print(f"  MOVES turns: {n_moves} ({100*n_moves/max(1,n):.1f}%)", flush=True)
    print(f"  negs: raw avg {n_raw_negs/max(1,n):.1f}, FN-filtered avg {n_filtered_negs/max(1,n):.1f} "
          f"(dropped {100*(n_raw_negs-n_filtered_negs)/max(1,n_raw_negs):.1f}%)", flush=True)
    top = sorted(gpa_counts.items(), key=lambda kv: -kv[1])[:6]
    print(f"  gpa distribution: {top}", flush=True)


if __name__ == "__main__":
    main()
