"""Smoke-test the extractor on hand-picked cases for process_constraints quality.

Picks ~12 turns covering each exploration_policy value.
Cases are a mix of:
 - synthetic clean-signal turns (to test whether the LLM reads the prompt correctly)
 - real devset turns sampled from the trace audit (to test generalization)

Run: OPENROUTER_API_KEY=... uv run python scripts/test_process_constraints_extraction.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.conversation_state.prompts.current import build_messages, json_schema_for_response_format  # noqa: E402
from mcrs.conversation_state.schema import ConversationStateV0Plus  # noqa: E402


MODEL = "openrouter/google/gemma-3-12b-it"


# Each case: a self-contained mini conversation + expected process_constraints values
# (expected is a judgment call from the prompt's rules — we'll review whether the model agrees)
CASES = [
    # --- exploit ---
    {
        "id": "exploit_explicit_more_by_them",
        "expected": {"exploration_policy": "exploit"},
        "played": ["t1"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Play some Tame Impala."},
            {"turn": 1, "role": "assistant", "text": "Here's 'The Less I Know The Better'."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Tame Impala - The Less I Know The Better"},
            {"turn": 2, "role": "user", "text": "Nice — got another Tame Impala track?"},
        ],
    },
    {
        "id": "exploit_more_from_album",
        "expected": {"exploration_policy": "exploit"},
        "played": ["t1"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Play something from Kid A."},
            {"turn": 1, "role": "assistant", "text": "Here is 'Idioteque'."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Radiohead - Idioteque"},
            {"turn": 2, "role": "user", "text": "Loved it. Got more from this album?"},
        ],
    },
    # --- diversify_artists ---
    {
        "id": "diversify_more_bands_like_this",
        "expected": {"exploration_policy": "diversify_artists"},
        "played": ["t1"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Some Cro-Mags please — 80s hardcore."},
            {"turn": 1, "role": "assistant", "text": "Here's 'We Gotta Know'."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Cro-Mags - We Gotta Know"},
            {"turn": 2, "role": "user", "text": "Great pick. Now can you recommend a few more bands with that same kind of aggressive 80s hardcore sound?"},
        ],
    },
    {
        "id": "diversify_another_genre_track",
        "expected": {"exploration_policy": "diversify_artists"},
        "played": ["t1"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Got any popular alternative rock?"},
            {"turn": 1, "role": "assistant", "text": "Try this Arctic Monkeys track."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Arctic Monkeys - Do I Wanna Know"},
            {"turn": 2, "role": "user", "text": "Nice. Can you recommend another popular alternative rock track?"},
        ],
    },
    {
        "id": "diversify_more_artists_from_era",
        "expected": {"exploration_policy": "diversify_artists"},
        "played": ["t1"],
        "conv": [
            {"turn": 1, "role": "user", "text": "90s grunge — Nirvana style."},
            {"turn": 1, "role": "assistant", "text": "Here's Heart-Shaped Box."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Nirvana - Heart-Shaped Box"},
            {"turn": 2, "role": "user", "text": "Solid. What about other artists from that scene?"},
        ],
    },
    # --- balanced ---
    {
        "id": "balanced_more_like_this",
        "expected": {"exploration_policy": "balanced"},
        "played": ["t1"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Something chill for a rainy afternoon."},
            {"turn": 1, "role": "assistant", "text": "Try this Bon Iver track."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Bon Iver - Holocene"},
            {"turn": 2, "role": "user", "text": "Lovely. More like this please."},
        ],
    },
    {
        "id": "balanced_turn1_open",
        "expected": {"exploration_policy": "balanced"},
        "played": [],
        "conv": [
            {"turn": 1, "role": "user", "text": "What's something good and energetic?"},
        ],
    },
    # --- hard novelty / pivot ---
    {
        "id": "hard_anything_different",
        "expected": {"exploration_policy": "balanced"},
        "played": ["t1", "t2", "t3"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Some smooth jazz."},
            {"turn": 1, "role": "assistant", "text": "Here's a Miles Davis."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Miles Davis - So What"},
            {"turn": 2, "role": "user", "text": "Nice."},
            {"turn": 2, "role": "music", "track_id": "t2", "label": "John Coltrane - Naima"},
            {"turn": 3, "role": "user", "text": "Got another?"},
            {"turn": 3, "role": "music", "track_id": "t3", "label": "Chet Baker - My Funny Valentine"},
            {"turn": 4, "role": "user", "text": "Actually I'm bored of this — give me anything completely different."},
        ],
    },
    # --- diversify_albums (rare) ---
    {
        "id": "diversify_albums_earlier_career",
        "expected": {"exploration_policy": "diversify_albums"},
        "played": ["t1"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Play me some Radiohead from In Rainbows."},
            {"turn": 1, "role": "assistant", "text": "Here's '15 Step'."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Radiohead - 15 Step"},
            {"turn": 2, "role": "user", "text": "Nice. Got more Radiohead, but from an earlier album?"},
        ],
    },
    # --- pivot with novelty hard ---
    {
        "id": "pivot_dont_replay",
        "expected": {"exploration_policy": "diversify_artists"},
        "played": ["t1", "t2"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Some Morphine please."},
            {"turn": 1, "role": "assistant", "text": "Here's 'Cure for Pain'."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Morphine - Cure for Pain"},
            {"turn": 2, "role": "user", "text": "Another?"},
            {"turn": 2, "role": "music", "track_id": "t2", "label": "Morphine - Buena"},
            {"turn": 3, "role": "user", "text": "Stop Morphine — anything else in the smoky late-night bar vein?"},
        ],
    },
    # --- ambiguous: "another song" (no scope) ---
    {
        "id": "ambiguous_another_song",
        "expected": {"exploration_policy": "balanced"},
        "played": ["t1"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Play me something for studying."},
            {"turn": 1, "role": "assistant", "text": "Here's a Tycho track."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "Tycho - A Walk"},
            {"turn": 2, "role": "user", "text": "Cool. Another song please."},
        ],
    },
    # --- multi-turn, refinement of genre across artists ---
    {
        "id": "multi_turn_diversify_chain",
        "expected": {"exploration_policy": "diversify_artists"},
        "played": ["t1", "t2"],
        "conv": [
            {"turn": 1, "role": "user", "text": "Some shoegaze please."},
            {"turn": 1, "role": "assistant", "text": "Here's My Bloody Valentine."},
            {"turn": 1, "role": "music", "track_id": "t1", "label": "My Bloody Valentine - Only Shallow"},
            {"turn": 2, "role": "user", "text": "Spot on. Another?"},
            {"turn": 2, "role": "music", "track_id": "t2", "label": "Slowdive - Alison"},
            {"turn": 3, "role": "user", "text": "Yes! Got any more shoegaze artists I should try?"},
        ],
    },
]


def run_one(case: dict) -> dict:
    import litellm

    messages = build_messages(case["conv"], case["played"])
    response = litellm.completion(
        model=MODEL,
        messages=messages,
        temperature=0.0,
        max_tokens=1500,
        timeout=90,
        response_format=json_schema_for_response_format(),
        extra_body={"reasoning": {"enabled": False}},
    )
    raw = response.choices[0].message.content or ""
    parsed = json.loads(raw)
    state = ConversationStateV0Plus.model_validate(parsed)
    return {
        "intent_mode": state.intent_mode.value,
        "exploration_policy": state.process_constraints.exploration_policy.value,
        "turn_intent": state.turn_intent,
    }


def main():
    # Load .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    assert os.environ.get("OPENROUTER_API_KEY"), "OPENROUTER_API_KEY must be set"

    results = []
    n_match_policy = 0
    for case in CASES:
        last_user = next(t["text"] for t in reversed(case["conv"]) if t["role"] == "user")
        try:
            got = run_one(case)
        except Exception as e:
            print(f"\n[{case['id']}] EXTRACT FAILED: {type(e).__name__}: {e}")
            continue

        exp_policy = case["expected"]["exploration_policy"]
        got_policy = got["exploration_policy"]
        policy_ok = got_policy == exp_policy
        n_match_policy += int(policy_ok)

        mark_p = "OK" if policy_ok else "MISS"
        print(f"\n[{case['id']}]")
        print(f"  user: {last_user!r}")
        print(f"  expected: policy={exp_policy}")
        print(f"  got:      policy={got_policy} ({mark_p})")
        print(f"  intent_mode={got['intent_mode']}, turn_intent={got['turn_intent']!r}")
        results.append({
            "id": case["id"],
            "expected": case["expected"],
            "got": got,
            "policy_ok": policy_ok,
        })

    n = len(results)
    print("\n" + "=" * 60)
    print(f"Cases: {n}")
    print(f"exploration_policy match: {n_match_policy}/{n} ({n_match_policy/n:.0%})" if n else "no cases")

    # Dump full results so we can review
    out = Path("scripts/process_constraints_extraction_results.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"\nFull results: {out}")


if __name__ == "__main__":
    main()
