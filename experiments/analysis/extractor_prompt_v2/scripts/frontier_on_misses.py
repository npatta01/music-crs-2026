"""Run claude-opus-4.7 (frontier) on the v2+gemma-4 miss turns and compare.

Question: does a frontier model recover the literal tokens that gemma-4
dropped? Particularly the 6 artist-name misses (megadeth, ennio morricone,
cannibal corpse, kreator, eminem, destiny's child) and 2 "classic" descriptor
misses.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from datasets import load_dataset
from mcrs.qu_modules.compiler_v0plus_qu import LiteLLMExtractor
from experiments.analysis.extractor_prompt_v2.prompts_v2 import (
    build_messages as build_messages_v2,
    json_schema_for_response_format as schema_v2,
)
from experiments.analysis.extractor_prompt_v2.scripts.smoketest_extractor_v2 import (
    state_positive_tags,
    session_memory_from_devset,
    session_memory_to_conv_with_labels,
    build_label_lookup,
    run_one,
)

# 8 representative miss turns from the v2b smoke (gemma-4-26b)
TARGETS = [
    # 6 artist-name misses
    ("a3a9d0e4", 2, "megadeth"),
    ("c73e7980", 7, "ennio morricone"),
    ("6e00389a", 8, "cannibal corpse"),
    ("d5a58190", 7, "kreator"),
    ("f21ccd75", 3, "eminem"),
    ("9580e0ed", 7, "destiny's child"),
    # 2 "classic" descriptor misses
    ("f51831e3", 3, "classic"),
    ("80984510", 2, "classic"),
]


async def main():
    print("loading devset...")
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    sess_map = {r["session_id"][:8]: (r["session_id"], r["conversations"]) for r in ds}

    print("loading labels...")
    labels = build_label_lookup()

    print("calling frontier model...")
    extractor = LiteLLMExtractor(
        model_name="openrouter/anthropic/claude-opus-4.7",
        temperature=0.0,
        max_tokens=2000,
        timeout_s=120,
    )

    results = []
    for sid_short, tn, what in TARGETS:
        if sid_short not in sess_map:
            print(f"!! missing session {sid_short}")
            continue
        sid, convs = sess_map[sid_short]
        sm = session_memory_from_devset(convs, tn)
        conv, played = session_memory_to_conv_with_labels(sm, labels)
        user_text = next((t.get("text", "") for t in conv if t["role"] == "user" and t["turn"] == tn), "")

        state, dt = await run_one(extractor, conv, played, build_messages_v2, schema_v2)
        if state is None:
            print(f"  {sid_short} t{tn} ({what}): EXTRACT FAILED")
            continue
        new_pos_tags = state_positive_tags(state)
        # Also pull all mentioned_entities to see if it captured the artist
        all_me = []
        for me in state.mentioned_entities or []:
            mtype = me.type.value if hasattr(me.type, "value") else me.type
            all_me.append({"type": mtype, "value": me.value, "sentiment": me.sentiment})

        # Check substring of `what` against any tag value OR any mentioned_entity value
        what_lc = what.lower()
        recovered_as_tag = any(what_lc in t.lower() for t in new_pos_tags)
        recovered_as_entity = any(what_lc in e["value"].lower() for e in all_me)

        print(f"\n=== session {sid_short} turn {tn} — target: '{what}' ===")
        print(f"  USER: {user_text[:200]}")
        print(f"  CLAUDE tags ({len(new_pos_tags)}): {new_pos_tags}")
        print(f"  CLAUDE all mentioned_entities ({len(all_me)}):")
        for e in all_me:
            print(f"    - {e['type']:6} {e['value']!r:40} sent={e['sentiment']}")
        print(f"  recovered as tag:    {recovered_as_tag}")
        print(f"  recovered as entity: {recovered_as_entity}")
        print(f"  latency: {dt:.1f}s")

        results.append({
            "session_id": sid,
            "turn_number": tn,
            "target_token": what,
            "user_text": user_text,
            "claude_tags": new_pos_tags,
            "claude_mentioned_entities": all_me,
            "recovered_as_tag": recovered_as_tag,
            "recovered_as_entity": recovered_as_entity,
            "latency_s": dt,
        })

    out = Path("experiments/analysis/extractor_prompt_v2/artifacts/frontier_misses.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        json.dump(results, fh, indent=2)

    n_recovered = sum(1 for r in results if r["recovered_as_tag"] or r["recovered_as_entity"])
    print(f"\n{n_recovered}/{len(results)} recovered by claude (tag or mentioned_entity)")


if __name__ == "__main__":
    asyncio.run(main())
