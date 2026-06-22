"""Independent LLM judge for the cross-encoder's soft-positive / false-negative candidates.

NON-CIRCULAR check (advisor requirement): the cross-encoder (Qwen3-Reranker) flagged certain
mined "negatives" as ranking >= the GT (see probe_xenc_mining.py -> xenc_softpos_candidates.jsonl).
Here a DIFFERENT model (default DeepSeek via OpenRouter — the gpa-labeler family, independent of
Qwen) judges whether each flagged track is actually a reasonable recommendation for the request.

Reports:
  - soft-positive PRECISION = fraction of flagged candidates judged VALID (the key number),
  - positive control: GT judged VALID rate (judge sanity — should be high),
  - negative control: random track judged VALID rate (should be low),
  - artist/popularity note left to the results file.

The judge never sees the cross-encoder score (avoids anchoring).

Run from the MAIN checkout (needs OPENROUTER_API_KEY; .env is auto-loaded):
    .venv/bin/python scripts/rerank/judge_softpos.py --limit 120
"""
from __future__ import annotations
import argparse, json, os, random, sys, time
from collections import Counter

sys.path.insert(0, "scripts/rerank")

CAND = "exp/analysis/retrieval_exploration/xenc_softpos_candidates.jsonl"
OUT = "exp/analysis/retrieval_exploration/xenc_softpos_judged.json"
SYS = ("You are a STRICT music recommendation judge. Given a user's request from a "
       "conversation and ONE candidate track, rate how SPECIFICALLY the track matches what "
       "the user actually asked for (genre / mood / era / artist intent). Be discriminating: "
       "a track that is merely generically listenable but does not match the specific request "
       "is NOT a good match. Answer with exactly one word:\n"
       "GOOD  = clearly matches the specific request\n"
       "WEAK  = only loosely related / generic, not really what was asked\n"
       "BAD   = does not match the request")


def load_env():
    """Minimal .env loader (KEY=VALUE lines) so litellm sees OPENROUTER_API_KEY."""
    p = ".env"
    if not os.path.exists(p):
        return
    for line in open(p):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def judge_one(client, cache, q, track_text):
    msg = [{"role": "system", "content": SYS},
           {"role": "user", "content": f"User request:\n{q}\n\nCandidate track: {track_text}\n\n"
                                        f"How specifically does this track match the request? "
                                        f"Answer GOOD, WEAK, or BAD."}]
    try:
        out = client.chat(msg, cache=cache).strip().upper()
    except Exception as e:
        return "ERROR", str(e)[:120]
    for lab in ("GOOD", "WEAK", "BAD"):
        if lab in out:
            return lab, out[:40]
    return "WEAK", out[:40]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=CAND)
    ap.add_argument("--model", default="openrouter/deepseek/deepseek-chat")
    ap.add_argument("--limit", type=int, default=120, help="turns (candidate rows) to judge")
    ap.add_argument("--max-per-turn", type=int, default=3, help="flagged candidates judged per turn")
    ap.add_argument("--controls", action="store_true", default=True,
                    help="also judge the GT (+ a random track) per turn as sanity controls")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    load_env()
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not found (.env not loaded?)"); sys.exit(1)
    from mcrs.lm_modules.litellm_client import LiteLLMChatClient
    from probe_xenc_mining import load_pairs  # for catalog text of GT/random controls
    from probe_xenc_zeroshot import load_catalog

    client = LiteLLMChatClient(model_name=a.model, temperature=0.0, max_tokens=8)
    cache = {"no-cache": False}
    rows = [json.loads(l) for l in open(a.inp)]
    random.seed(0); random.shuffle(rows); rows = rows[: a.limit]
    meta = load_catalog() if a.controls else {}
    all_tids = list(meta) if meta else []
    print(f"judging {len(rows)} turns with {a.model}", flush=True)

    flagged_labels = Counter(); gt_labels = Counter(); rand_labels = Counter()
    judged = []
    t0 = time.time()
    for i, r in enumerate(rows):
        q = r["q"]; rec = {"sid": r["sid"], "tn": r["tn"], "flagged": []}
        for c in r["flagged"][: a.max_per_turn]:
            lab, raw = judge_one(client, cache, q, c["text"])
            flagged_labels[lab] += 1
            rec["flagged"].append({"tid": c["tid"], "artist": c.get("artist"),
                                   "ce_score": c.get("score"), "judge": lab})
        if a.controls and meta:
            gt_t = meta.get(r["gt"], {}).get("text")
            if gt_t:
                lab, _ = judge_one(client, cache, q, gt_t); gt_labels[lab] += 1; rec["gt_judge"] = lab
            rt = random.choice(all_tids)
            lab, _ = judge_one(client, cache, q, meta[rt]["text"]); rand_labels[lab] += 1
            rec["rand_judge"] = lab
        judged.append(rec)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(rows)} ({(i+1)/max(1e-9,time.time()-t0):.1f} turns/s)", flush=True)

    def rate(c, lab="GOOD"):
        n = sum(c.values()); return (100 * c[lab] / n) if n else float("nan"), n

    fv, fn = rate(flagged_labels); gv, gn = rate(gt_labels); rv, rn = rate(rand_labels)
    print("\n================= INDEPENDENT JUDGE (%s) =================" % a.model)
    print(f"flagged soft-pos/FN candidates: GOOD={fv:.1f}%  (n={fn})  dist={dict(flagged_labels)}")
    if gn: print(f"  [pos control] GT judged GOOD  = {gv:.1f}% (n={gn})  dist={dict(gt_labels)}")
    if rn: print(f"  [neg control] random GOOD     = {rv:.1f}% (n={rn})  dist={dict(rand_labels)}")
    print("\nVALIDITY GATE: the judge is only usable if GT-GOOD%% >> random-GOOD%% (it can "
          "discriminate). Then: high flagged-GOOD%% => CE flags ARE real soft positives "
          "(mineable); low flagged-GOOD%% => CE over-flags; trust it for NEGATIVE cleaning only.")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump({"config": vars(a),
               "flagged_valid_pct": fv, "flagged_dist": dict(flagged_labels),
               "gt_valid_pct": gv, "gt_dist": dict(gt_labels),
               "random_valid_pct": rv, "random_dist": dict(rand_labels),
               "judged": judged}, open(a.out, "w"), indent=1, default=str)
    print(f"\nsaved -> {a.out}")


if __name__ == "__main__":
    main()
