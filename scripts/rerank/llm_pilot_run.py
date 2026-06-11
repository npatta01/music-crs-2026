"""LLM listwise-reranker pilot — LLM stage.

For each selected turn: prompt an OpenRouter model (via litellm, temperature 0)
with (a) last user message + previous 2 turns, (b) listener_goal + played-so-far
names, (c) the GBDT top-25 as numbered 'Artist - Track (Year) | top-5 tags'
lines. Ask for the 10 best 'next play' candidates as comma-separated numbers.

Scoring: reranked ordering = LLM's 10 picks first (LLM order), then the rest of
the pool in GBDT order. Paired NDCG@20 / hit@1 / hit@5 vs the GBDT's own order.

Usage:
  python scripts/rerank/llm_pilot_run.py --model openrouter/deepseek/deepseek-v4-flash --n 120
  python scripts/rerank/llm_pilot_run.py --model openrouter/qwen/qwen3-30b-a3b-instruct-2507 --n 60
"""
from __future__ import annotations

import argparse
import json
import math
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

ROOT = Path("/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.claude/worktrees/busy-ishizaka-f3d4a7")
DB_URI = "/Users/npatta01/data/projects/music-conversational-music-recomender-2026/cache/lancedb"
TURNS = ROOT / "exp/analysis/rerank/llm_rerank/pilot_turns.json"
OUT_DIR = ROOT / "exp/analysis/rerank/llm_rerank"

# live OpenRouter pricing (USD per token), fetched 2026-06-11
PRICING = {
    "openrouter/deepseek/deepseek-v4-flash": (0.0983e-6, 0.1966e-6),
    "openrouter/qwen/qwen3-30b-a3b-instruct-2507": (0.04815e-6, 0.19305e-6),
}


def load_track_meta() -> dict[str, dict]:
    import lancedb
    db = lancedb.connect(DB_URI)
    ds = db.open_table("music_track_catalog").to_lance()
    cols = ["track_id", "track_name", "artist_name", "release_date", "tag_list"]
    tbl = ds.to_table(columns=cols).to_pydict()
    meta = {}
    for i in range(len(tbl["track_id"])):
        name = tbl["track_name"][i]
        if isinstance(name, (list, tuple)):
            name = " ".join(str(x) for x in name)
        artists = tbl["artist_name"][i]
        if not isinstance(artists, (list, tuple)):
            artists = [artists]
        rd = tbl["release_date"][i]
        year = None
        try:
            year = (rd if isinstance(rd, date) else date.fromisoformat(str(rd)[:10])).year
        except Exception:
            pass
        tags = [str(t) for t in (tbl["tag_list"][i] or [])][:5]
        meta[str(tbl["track_id"][i])] = {
            "name": str(name or "?"),
            "artist": ", ".join(str(a) for a in artists if a) or "?",
            "year": year, "tags": tags,
        }
    return meta


def load_sessions() -> dict[str, dict]:
    from collections import defaultdict

    from datasets import load_dataset
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    out = {}
    for row in ds:
        sid = str(row["session_id"])
        played, user_text = defaultdict(list), {}
        for msg in row["conversations"]:
            if msg["role"] == "music":
                played[int(msg["turn_number"])].append(str(msg["content"]))
            elif msg["role"] == "user":
                user_text[int(msg["turn_number"])] = str(msg["content"])
        g = row.get("conversation_goal") or {}
        out[sid] = {"played_by_turn": dict(played), "user_text_by_turn": user_text,
                    "listener_goal": str(g.get("listener_goal") or "")}
    return out


def fmt_track(m: dict | None) -> str:
    if m is None:
        return "(unknown track)"
    y = f" ({m['year']})" if m["year"] else ""
    tags = f" | {', '.join(m['tags'])}" if m["tags"] else ""
    return f"{m['artist']} - {m['name']}{y}{tags}"


def build_prompt(turn: dict, sess: dict, meta: dict, no_state: bool = False) -> str:
    tn = turn["turn_number"]
    ut = sess.get("user_text_by_turn", {})
    pbt = sess.get("played_by_turn", {})
    lines = ["You are reranking music recommendations for what a listener should hear NEXT in an ongoing session."]
    if no_state:
        lines += ["", f"User request: {ut.get(tn, '')}"]
    else:
        lg = sess.get("listener_goal", "")
        if lg:
            lines += ["", f"Listener goal: {lg}"]
        played = [t for k in sorted(pbt) if k < tn for t in pbt[k]]
        if played:
            shown = played[-20:]
            lines += ["", f"Played so far ({len(played)} tracks"
                      + (f", last {len(shown)} shown" if len(played) > len(shown) else "") + "):"]
            lines += [f"- {meta[t]['artist']} - {meta[t]['name']}" for t in shown if t in meta]
        lines += ["", "Conversation:"]
        for k in (tn - 2, tn - 1):
            if k in ut:
                lines.append(f"[turn {k}] User: {ut[k]}")
                pl = [t for t in pbt.get(k, []) if t in meta]
                if pl:
                    lines.append(f"[turn {k}] System played: "
                                 + "; ".join(f"{meta[t]['artist']} - {meta[t]['name']}" for t in pl))
        lines.append(f"[turn {tn}] User (CURRENT): {ut.get(tn, '')}")
    lines += ["", "Candidates:"]
    for i, c in enumerate(turn["top25"], 1):
        lines.append(f"{i}. {fmt_track(meta.get(c['track_id']))}")
    lines += ["", "Rank the 10 best candidates for what this user should hear NEXT, "
              "as a comma-separated list of numbers, best first. Output only the numbers."]
    return "\n".join(lines)


NUM_RE = re.compile(r"\b([1-9]|1[0-9]|2[0-5])\b")


def parse_picks(text: str) -> list[int]:
    # prefer the last line containing >=5 valid numbers (skips any preamble)
    best: list[int] = []
    for line in text.strip().splitlines():
        nums, seen = [], set()
        for m in NUM_RE.finditer(line):
            v = int(m.group(1))
            if v not in seen:
                seen.add(v)
                nums.append(v)
        if len(nums) >= 5:
            best = nums
    if not best:  # fall back: all numbers anywhere
        seen = set()
        for m in NUM_RE.finditer(text):
            v = int(m.group(1))
            if v not in seen:
                seen.add(v)
                best.append(v)
    return best[:10]


def reranked_gt_rank(turn: dict, picks: list[int]) -> int:
    """GT rank under: LLM picks first (their order), rest in GBDT order."""
    gt_rank = turn["gt_rank_gbdt"]
    pick_ranks = picks  # candidate number i == GBDT rank i (top25 is in GBDT order)
    if gt_rank in pick_ranks:
        return pick_ranks.index(gt_rank) + 1
    n_above = sum(1 for r in pick_ranks if r < gt_rank)
    return len(pick_ranks) + (gt_rank - n_above)


def ndcg20(r: int) -> float:
    return 1.0 / math.log2(r + 1) if r <= 20 else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-state", action="store_true",
                    help="Ablation: only the current user message + candidates "
                         "(no listener_goal, no played-so-far, no prior turns).")
    ap.add_argument("--allow-reasoning", action="store_true",
                    help="Do not send OpenRouter reasoning:{enabled:false} "
                         "(hybrid models like deepseek-v4-flash otherwise burn "
                         "the token cap on reasoning and return empty content).")
    args = ap.parse_args()

    import litellm
    litellm.suppress_debug_info = True

    data = json.loads(TURNS.read_text())
    turns = data["turns"][: args.n]
    print(f"{len(turns)} turns, model={args.model}", flush=True)
    meta = load_track_meta()
    print(f"catalog meta: {len(meta)} tracks", flush=True)
    sessions = load_sessions()
    print(f"sessions: {len(sessions)}", flush=True)

    lock = threading.Lock()
    usage = {"prompt": 0, "completion": 0, "fail": 0}

    def call(turn):
        prompt = build_prompt(turn, sessions.get(turn["session_id"], {}), meta,
                              no_state=args.no_state)
        last_err = None
        for attempt in range(3):
            try:
                kw = {}
                if not args.allow_reasoning:
                    kw["extra_body"] = {"reasoning": {"enabled": False}}
                resp = litellm.completion(
                    model=args.model, temperature=0, max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=120, **kw)
                msg = resp.choices[0].message
                text = msg.content or getattr(msg, "reasoning_content", None) or ""
                with lock:
                    usage["prompt"] += resp.usage.prompt_tokens
                    usage["completion"] += resp.usage.completion_tokens
                picks = parse_picks(text)
                return {"session_id": turn["session_id"], "turn_number": turn["turn_number"],
                        "gt_rank_gbdt": turn["gt_rank_gbdt"], "picks": picks,
                        "llm_rank": reranked_gt_rank(turn, picks) if picks else turn["gt_rank_gbdt"],
                        "parse_ok": bool(picks), "raw": text, "prompt": prompt}
            except Exception as e:  # noqa: BLE001
                last_err = e
                import time
                time.sleep(2 * (attempt + 1))
        with lock:
            usage["fail"] += 1
        return {"session_id": turn["session_id"], "turn_number": turn["turn_number"],
                "gt_rank_gbdt": turn["gt_rank_gbdt"], "picks": [],
                "llm_rank": turn["gt_rank_gbdt"], "parse_ok": False,
                "raw": f"ERROR: {last_err}", "prompt": prompt}

    results = []
    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(call, t) for t in turns]
        for i, f in enumerate(as_completed(futs), 1):
            results.append(f.result())
            if i % 20 == 0:
                print(f"  {i}/{len(turns)}", flush=True)

    # deterministic order for the artifact
    key = {(t["session_id"], t["turn_number"]): i for i, t in enumerate(turns)}
    results.sort(key=lambda r: key[(r["session_id"], r["turn_number"])])

    # paired metrics
    import numpy as np
    g = np.array([r["gt_rank_gbdt"] for r in results], dtype=float)
    l = np.array([r["llm_rank"] for r in results], dtype=float)
    nd_g = np.array([ndcg20(int(r)) for r in g])
    nd_l = np.array([ndcg20(int(r)) for r in l])
    d = nd_l - nd_g
    t_stat = float(d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))) if d.std(ddof=1) > 0 else 0.0

    def block(mask, name):
        if mask.sum() == 0:
            return {}
        dm = d[mask]
        return {"name": name, "n": int(mask.sum()),
                "gbdt": {"ndcg20": float(nd_g[mask].mean()),
                         "hit1": float((g[mask] <= 1).mean()), "hit5": float((g[mask] <= 5).mean())},
                "llm": {"ndcg20": float(nd_l[mask].mean()),
                        "hit1": float((l[mask] <= 1).mean()), "hit5": float((l[mask] <= 5).mean())},
                "delta_ndcg20": float(dm.mean()),
                "t": float(dm.mean() / (dm.std(ddof=1) / math.sqrt(len(dm)))) if len(dm) > 1 and dm.std(ddof=1) > 0 else 0.0,
                "wins": int((dm > 0).sum()), "losses": int((dm < 0).sum()), "ties": int((dm == 0).sum())}

    all_mask = np.ones(len(d), dtype=bool)
    in25 = g <= 25
    pin, pout = PRICING.get(args.model, (0.0, 0.0))
    cost = usage["prompt"] * pin + usage["completion"] * pout
    report = {
        "model": args.model, "no_state": args.no_state, "n_turns": len(results),
        "parse_ok": int(sum(r["parse_ok"] for r in results)),
        "call_failures": usage["fail"],
        "overall": block(all_mask, "all"),
        "gt_in_top25": block(in25, "gt_in_top25"),
        "gt_in_26_50": block(~in25, "gt_26_50"),
        "tokens": {"prompt": usage["prompt"], "completion": usage["completion"]},
        "cost_usd": round(cost, 4),
    }
    tag = args.model.split("/")[-1] + ("_nostate" if args.no_state else "")
    (OUT_DIR / f"results_{tag}.json").write_text(json.dumps(
        {"report": report, "results": [{k: v for k, v in r.items() if k != "prompt"}
                                       for r in results]}, indent=1))
    # keep two full prompts for the record
    (OUT_DIR / f"sample_prompts_{tag}.txt").write_text(
        "\n\n========\n\n".join(r["prompt"] + "\n\n--- RAW ---\n" + r["raw"] for r in results[:2]))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
