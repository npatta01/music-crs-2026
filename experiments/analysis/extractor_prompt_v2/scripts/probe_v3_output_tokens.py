"""Measure actual v3 extraction OUTPUT token counts on worst-case turns, to set
max_tokens with confidence (cheap: ~12 LLM calls).

Worst case for output length = latest turns (most played_track_ids → most
track_feedback entries, each echoing a 36-char UUID that tokenizes densely) +
the v3 prompt's extra tags/entities. We pick the highest-turn_number cohort
rows and report litellm's reported completion_tokens.
"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from datasets import load_dataset
from experiments.analysis.extractor_prompt_v2.prompts_v3 import (
    build_messages, json_schema_for_response_format,
)
from experiments.analysis.extractor_prompt_v2.scripts.smoketest_extractor_v2 import (
    session_memory_from_devset, session_memory_to_conv_with_labels, build_label_lookup,
)

MODEL = "openrouter/google/gemma-4-26b-a4b-it"
N = 12


async def main():
    cohort = [json.loads(l) for l in open(
        "experiments/analysis/extractor_prompt_v2/artifacts/cohort_missed_literal_tags.jsonl")]
    # worst case = highest turn_number (most played tracks → longest output)
    cohort.sort(key=lambda r: r["turn_number"], reverse=True)
    picks = cohort[:N]
    print(f"probing {N} highest-turn cohort rows (turns {picks[-1]['turn_number']}..{picks[0]['turn_number']})")

    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    sess = {r["session_id"]: r["conversations"] for r in ds}
    labels = build_label_lookup()

    import litellm
    litellm.suppress_debug_info = True

    comp_tokens = []
    for r in picks:
        sid, tn = r["session_id"], r["turn_number"]
        sm = session_memory_from_devset(sess.get(sid, []), tn)
        conv, played = session_memory_to_conv_with_labels(sm, labels)
        msgs = build_messages(conv, played)
        kw = dict(model=MODEL, messages=msgs, temperature=0.0, max_tokens=4000,
                  timeout=120, response_format=json_schema_for_response_format())
        if MODEL.startswith("openrouter/") and not MODEL.startswith("openrouter/openai/"):
            kw["extra_body"] = {"reasoning": {"enabled": False}}
        try:
            resp = litellm.completion(**kw)
            ct = resp.usage.completion_tokens
            finish = resp.choices[0].message.content
            ok = False
            try:
                json.loads(finish); ok = True
            except Exception:
                ok = False
            comp_tokens.append(ct)
            print(f"  sid={sid[:8]} turn={tn:2d} n_played={len(played):2d} "
                  f"completion_tokens={ct:4d} valid_json={ok}")
        except Exception as e:
            print(f"  sid={sid[:8]} turn={tn:2d} ERROR {type(e).__name__}: {str(e)[:80]}")

    if comp_tokens:
        comp_tokens.sort()
        print(f"\ncompletion_tokens: min={comp_tokens[0]} median={comp_tokens[len(comp_tokens)//2]} "
              f"max={comp_tokens[-1]}")
        print(f"max_tokens=4000 headroom over observed max: {4000 - comp_tokens[-1]} tokens "
              f"({4000/max(comp_tokens[-1],1):.1f}x)")


if __name__ == "__main__":
    asyncio.run(main())
