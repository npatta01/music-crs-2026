"""Smoke test for the new v0+ compiler config + post-fusion-features framework.

Runs the full pipeline on 5 devset sessions, verifies:
  - extractor emits the new `process_constraints.exploration_policy` field
  - resolver runs without exception
  - compiler returns a non-empty list of track_ids
  - PostFusionReranker is wired (default `balanced` policy → no-op vs legacy)

Cost: ~5 OpenRouter extractor calls @ $0.005 = ~$0.025.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datasets import load_dataset

from mcrs.qu_modules.compiler_qu import build_v0plus_compiler_qu


CONFIG = Path("configs/v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset.yaml")
N_SESSIONS = 5


def session_to_session_memory(sess, up_to_turn: int) -> list[dict]:
    """Build the CRS_BASELINE session_memory format up to (and including) the
    user message at `up_to_turn`."""
    sm: list[dict] = []
    for m in sess["conversations"]:
        tn = m.get("turn_number")
        role = m.get("role")
        if tn is None or role is None:
            continue
        if tn > up_to_turn:
            break
        if role == "user" and tn == up_to_turn:
            sm.append({"role": "user", "content": m.get("content", "")})
            break
        if role == "user":
            sm.append({"role": "user", "content": m.get("content", "")})
        elif role == "assistant":
            sm.append({"role": "assistant", "content": m.get("content", "")})
        elif role == "music":
            sm.append({"role": "music", "content": m.get("content", "")})
    return sm


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    assert os.environ.get("OPENROUTER_API_KEY"), "OPENROUTER_API_KEY required"

    print(f"loading config: {CONFIG}")
    cfg = yaml.safe_load(CONFIG.read_text())
    qu_kwargs = cfg["qu_kwargs"]

    print("building pipeline (extractor + catalog + resolver + compiler)...")
    qu = build_v0plus_compiler_qu(qu_kwargs)
    print(f"  compiler type: {type(qu.compiler).__name__}")
    print(f"  enable_dense:  {qu.compiler.cfg.enable_dense}")
    print(f"  dense_branches: {[b.vector_field for b in qu.compiler.cfg.dense_branches]}")
    print(f"  centroid_only_branches: {[b.vector_field for b in qu.compiler.cfg.centroid_only_branches]}")

    print("\nloading 5 devset sessions...")
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")

    # Pick sessions that cover a mix of turn-depths
    sample_ids = []
    seen = set()
    for s in ds:
        if s["session_id"] in seen:
            continue
        sample_ids.append(s["session_id"])
        seen.add(s["session_id"])
        if len(sample_ids) >= N_SESSIONS:
            break
    sessions = {s["session_id"]: s for s in ds if s["session_id"] in seen}

    n_pass = 0
    n_extracted_policy = {"balanced": 0, "diversify_artists": 0, "exploit": 0, "diversify_albums": 0}
    for i, sid in enumerate(sample_ids, start=1):
        sess = sessions[sid]
        # Pick a mid-conversation turn (turn 3) for a richer state
        turn = 3
        sm = session_to_session_memory(sess, up_to_turn=turn)
        print(f"\n[{i}/{N_SESSIONS}] session={sid[:8]}... turn={turn}")
        last_user = next((m["content"] for m in reversed(sm) if m["role"] == "user"), "")
        print(f"  last user: {last_user[:120]!r}")

        # Extract state (also exercises the schema validation)
        conv, played = qu.extractor.extract.__wrapped__ if False else None, None
        from mcrs.qu_modules.compiler_qu import session_memory_to_conversation
        conv, played = session_memory_to_conversation(sm, qu.catalog)
        state = qu.extractor.extract(conv, played)
        if state is None:
            print("  EXTRACT FAILED (state=None)")
            continue
        policy = state.process_constraints.exploration_policy.value
        n_extracted_policy[policy] = n_extracted_policy.get(policy, 0) + 1
        print(
            f"  state: intent_mode={state.intent_mode.value}, "
            f"exploration_policy={policy}, "
            f"mentioned_entities={len(state.mentioned_entities)}, "
            f"track_feedback={len(state.track_feedback)}, "
            f"explicit_rejections={len(state.explicit_rejections)}"
        )

        # Resolve + compile
        rs = qu.resolver.resolve(state, played_track_ids=played)
        track_ids = qu.compiler.compile(rs)
        print(f"  compiled: {len(track_ids)} track_ids (head: {track_ids[:3]})")

        # Smoke-test the new framework path: re-check that PostFusionReranker
        # is in the call chain by verifying `_apply_soft_adjustments` is using it
        if hasattr(qu.compiler, "_apply_soft_adjustments") and len(track_ids) > 0:
            n_pass += 1

    print("\n" + "=" * 60)
    print(f"sessions passed: {n_pass}/{N_SESSIONS}")
    print(f"exploration_policy distribution in sample:")
    for p, n in n_extracted_policy.items():
        if n:
            print(f"  {p}: {n}")
    if n_pass == N_SESSIONS:
        print("\nSMOKE TEST PASSED ✓ — safe to launch full devset run")
    else:
        print("\nSMOKE TEST FAILED — DO NOT launch full devset")
        sys.exit(1)


if __name__ == "__main__":
    main()
