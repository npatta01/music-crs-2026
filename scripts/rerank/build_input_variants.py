"""Build input-variant data for the bi-encoder INPUT-lever experiment (Step 1).

Reuses retriever_pairs.jsonl (labels + mined negatives UNCHANGED) and rebuilds ONLY the query text
per variant — so each variant is an apples-to-apples test of the INPUT against the e1/b1 baseline
(same positives, same negatives, same model recipe). Doc side stays the plain doc_corpus.

Variants (query format):
  baseline    : [goal] <goal> [msg] <prev> / <now>                       (== b1/e1, for reference)
  v_user      : [goal] <goal> [user] <profile> [msg] <prev> / <now>      (+ user info, plain markers)
  v_tok       : <|goal|> <goal> <|prev|> <prev> <|now|> <now> <|prev_track|> <pt>   (special tokens + structure)
  v_tok_user  : v_tok + <|user|> <profile>                               (both)

Outputs per variant to exp/analysis/retrieval_exploration/input_variants/:
  pairs_<v>.jsonl : {sid, tn, gpa, q, pos_id, negs_filt, negs_raw}   (TRAIN; for the Modal trainer)
  eval_<v>.jsonl  : {sid, tn, q, gt}                                  (devset MOVES turns; for retrieval eval)

    python scripts/rerank/build_input_variants.py
"""
from __future__ import annotations
import ast, json, os, sys
sys.path.insert(0, "scripts/rerank")
from datasets import load_dataset

PAIRS = "exp/analysis/retrieval_exploration/retriever_pairs.jsonl"
DOCS = "exp/analysis/retrieval_exploration/doc_corpus.jsonl"
OUT = "exp/analysis/retrieval_exploration/input_variants"
MOVES = "MOVES_TOWARD_GOAL"
# disentangled grid (advisor): isolate structure / prev_track / special-tokens / user independently.
SPECIAL_TOKENS = ["<|goal|>", "<|prev|>", "<|now|>"]   # v_tok matches v_struct structure (no prev_track) to isolate the TOKEN effect
# v_user_lean: only the MUSIC-relevant profile fields (culture+language), dropping noisy demographics
VARIANTS = ["baseline", "v_struct", "v_struct_pt", "v_tok", "v_user", "v_struct_user", "v_user_lean", "v_fullconv"]


def load_split(split):
    """-> per sid: um{tn:text}, goal, gpa{(sid,tn)}, played{tn:[tids]}, profile{dict}."""
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split=split)
    um, goal, gpa, played, profile = {}, {}, {}, {}, {}
    for r in ds:
        conv = r.get("conversations")
        if isinstance(conv, str): conv = ast.literal_eval(conv)
        cg = r.get("conversation_goal")
        if isinstance(cg, str): cg = ast.literal_eval(cg)
        up = r.get("user_profile")
        if isinstance(up, str): up = ast.literal_eval(up)
        sid = str(r["session_id"]); u, p = {}, {}
        for m in conv:
            tn = int(m["turn_number"])
            if m["role"] == "user": u[tn] = str(m["content"])
            elif m["role"] == "music": p.setdefault(tn, []).append(str(m["content"]))
        um[sid] = u; played[sid] = p; profile[sid] = up or {}
        goal[sid] = (cg or {}).get("listener_goal", "")
        g = r.get("goal_progress_assessments")
        if isinstance(g, str): g = ast.literal_eval(g)
        for a in (g or []):
            gpa[(sid, int(a["turn_number"]))] = a.get("goal_progress_assessment")
    return um, goal, gpa, played, profile


def fmt_user(p):
    parts = [p.get("age_group"), p.get("country_name"), p.get("gender"),
             p.get("preferred_language"), p.get("preferred_musical_culture")]
    return ", ".join(str(x) for x in parts if x)


def fmt_user_lean(p):  # music-relevant fields only (drop age/gender/country noise)
    parts = [p.get("preferred_musical_culture"), p.get("preferred_language")]
    return ", ".join(str(x) for x in parts if x)


def short_track(doc):  # "artist — title" from "Music track: artist — title (year) | ..."
    return doc.split(" (")[0].replace("Music track: ", "").strip() if doc else ""


def prev_track_str(played_sid, tn, doc_by_tid):
    for k in range(tn - 1, 0, -1):
        if played_sid.get(k):
            return short_track(doc_by_tid.get(played_sid[k][-1], ""))
    return ""


def build_q(variant, goal, prev, now, pt, user, user_lean="", allturns=""):
    """Disentangled grid — each variant flips ONE dimension vs its control:
      baseline      [goal] g [msg] p / n                          (== b1 anchor)
      v_struct      [goal] g [prev] p [now] n                     (structure: split prev/now, plain markers)
      v_struct_pt   v_struct + [prev_track] pt                    (prev_track field; isolates vs v_struct)
      v_tok         <|goal|> g <|prev|> p <|now|> n               (special tokens; isolates token-vs-marker vs v_struct)
      v_user        [goal] g [user] u [msg] p / n                 (user info; isolates vs baseline)
      v_struct_user [goal] g [user] u [prev] p [now] n            (user x structure)
    """
    g = (goal or "").strip()
    turns = " / ".join(t for t in (prev, now) if t)
    if variant == "baseline":
        return ((f"[goal] {g} " if g else "") + "[msg] " + turns).strip()
    if variant == "v_user":
        return ((f"[goal] {g} " if g else "") + (f"[user] {user} " if user else "") + "[msg] " + turns).strip()
    if variant == "v_user_lean":
        return ((f"[goal] {g} " if g else "") + (f"[user] {user_lean} " if user_lean else "") + "[msg] " + turns).strip()
    if variant == "v_fullconv":  # goal + ALL user turns up to now (vs last-2) — does more history help?
        return ((f"[goal] {g} " if g else "") + "[msg] " + (allturns or turns)).strip()
    if variant in ("v_struct", "v_struct_pt", "v_struct_user"):
        s = (f"[goal] {g}" if g else "").strip()
        if variant == "v_struct_user" and user: s += f" [user] {user}"
        if prev: s += f" [prev] {prev}"
        if now: s += f" [now] {now}"
        if variant == "v_struct_pt" and pt: s += f" [prev_track] {pt}"
        return s.strip()
    if variant == "v_tok":  # special-token version of v_struct (tokens instead of [markers]); no prev_track
        s = (f"<|goal|> {g}" if g else "").strip()
        if prev: s += f" <|prev|> {prev}"
        if now: s += f" <|now|> {now}"
        return s.strip()
    raise ValueError(f"unknown variant {variant!r}")


def main():
    os.makedirs(OUT, exist_ok=True)
    doc_by_tid = {}
    for line in open(DOCS):
        d = json.loads(line); doc_by_tid[d["track_id"]] = d["doc"]

    print("loading train split...", flush=True)
    um, goal, gpa, played, profile = load_split("train")
    pairs = [json.loads(l) for l in open(PAIRS)]
    print(f"{len(pairs)} train pairs", flush=True)

    print("loading test/devset split...", flush=True)
    t_um, t_goal, t_gpa, t_played, t_profile = load_split("test")

    writers = {v: (open(f"{OUT}/pairs_{v}.jsonl", "w"), open(f"{OUT}/eval_{v}.jsonl", "w")) for v in VARIANTS}
    samples = {}

    # TRAIN pairs (rebuild q only; keep pos_id/negs/gpa)
    miss = 0
    for r in pairs:
        sid, tn = r["sid"], int(r["tn"])
        if sid not in um: miss += 1; continue
        prev, now = um[sid].get(tn - 1, ""), um[sid].get(tn, "")
        pt = prev_track_str(played.get(sid, {}), tn, doc_by_tid)
        user = fmt_user(profile.get(sid, {})); user_lean = fmt_user_lean(profile.get(sid, {}))
        allturns = " / ".join(um[sid][k] for k in sorted(um.get(sid, {})) if k <= tn and um[sid].get(k))
        for v in VARIANTS:
            q = build_q(v, goal.get(sid, ""), prev, now, pt, user, user_lean, allturns)
            writers[v][0].write(json.dumps({"sid": sid, "tn": tn, "gpa": r["gpa"], "q": q,
                                            "pos_id": r["pos_id"], "negs_filt": r["negs_filt"],
                                            "negs_raw": r["negs_raw"]}) + "\n")
            samples.setdefault(v, q)

    # DEVSET eval (test MOVES turns: q + GT played track)
    n_eval = 0
    for sid in t_um:
        for tn in sorted(t_um[sid]):
            if t_gpa.get((sid, tn)) != MOVES: continue
            gt_list = t_played.get(sid, {}).get(tn, [])
            if not gt_list: continue
            prev, now = t_um[sid].get(tn - 1, ""), t_um[sid].get(tn, "")
            pt = prev_track_str(t_played.get(sid, {}), tn, doc_by_tid)
            user = fmt_user(t_profile.get(sid, {})); user_lean = fmt_user_lean(t_profile.get(sid, {}))
            allturns = " / ".join(t_um[sid][k] for k in sorted(t_um.get(sid, {})) if k <= tn and t_um[sid].get(k))
            for v in VARIANTS:
                q = build_q(v, t_goal.get(sid, ""), prev, now, pt, user, user_lean, allturns)
                writers[v][1].write(json.dumps({"sid": sid, "tn": tn, "q": q, "gt": gt_list[0]}) + "\n")
            n_eval += 1

    for v in VARIANTS:
        writers[v][0].close(); writers[v][1].close()
    print(f"DONE train pairs (skipped {miss}); devset eval turns {n_eval} -> {OUT}/", flush=True)
    print(f"special tokens for the trainer: {SPECIAL_TOKENS}", flush=True)
    for v in VARIANTS:
        print(f"\n[{v}] sample query:\n  {samples.get(v, '')[:300]}", flush=True)


if __name__ == "__main__":
    main()
