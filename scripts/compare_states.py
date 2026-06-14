#!/usr/bin/env python
"""Compare local Ollama state extractions against Modal trace reference states.

Usage:
  python scripts/compare_states.py \\
    --modal-traces exp/inference/devset/v0plus_compiler_all_retrievers_devset.run_20260603T233201Z-ae1aeb.shard_0_trace.jsonl \\
    --local exp/state_extraction/smoke_qwen27b.jsonl exp/state_extraction/smoke_gemma31b.jsonl exp/state_extraction/smoke_qwen35b.jsonl \\
    --sessions data/smoke_test_sessions.json \\
    --labels qwen27b gemma31b qwen35b
"""

import argparse
import glob
import json
from pathlib import Path


def load_sessions(path: str) -> set[str]:
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        data = data.get("session_ids", [])
    return set(str(s) for s in data)


def load_trace_states(patterns: list[str], session_ids: set[str]) -> dict[tuple, dict]:
    """Load states from Modal inference trace JONSLs — each row has trace.state."""
    states: dict[tuple, dict] = {}
    for pattern in patterns:
        for f in sorted(glob.glob(pattern)):
            for line in open(f):
                row = json.loads(line)
                sid = row.get("session_id", "")
                if sid not in session_ids:
                    continue
                turn = row.get("turn_number")
                key = (sid, turn)
                if key not in states:
                    trace_state = (row.get("trace") or {}).get("state")
                    states[key] = trace_state
    return states


def load_local_states(path: str, session_ids: set[str]) -> dict[tuple, dict]:
    """Load states from extract_state.py JSONL output."""
    states: dict[tuple, dict] = {}
    for line in open(path):
        row = json.loads(line)
        sid = row.get("session_id", "")
        if sid not in session_ids:
            continue
        turn = row.get("turn_number")
        key = (sid, turn)
        states[key] = row.get("state")
    return states


def _str_val(v) -> str:
    if v is None:
        return "∅"
    if isinstance(v, list):
        return str(len(v)) + " items"
    return str(v)[:60]


def _entities_summary(state: dict | None, key: str) -> str:
    """Summarize entity-like lists from either schema variant."""
    if state is None:
        return "∅"
    # New V0Plus schema: entities list
    entities = state.get("entities") or []
    if entities:
        return ", ".join(f"{e.get('type','?')}:{e.get('value','?')}" for e in entities[:3])
    # Old schema: mentioned_entities
    entities = state.get("mentioned_entities") or []
    if entities:
        return ", ".join(f"{e.get('type','?')}:{e.get('value','?')}" for e in entities[:3])
    return "∅"


def _intent_summary(state: dict | None) -> str:
    if state is None:
        return "∅"
    # retrieval_profile serializes as a plain string (the intent mode value)
    profile = state.get("retrieval_profile")
    if isinstance(profile, str):
        return profile
    if isinstance(profile, dict):
        return str(profile.get("intent_mode") or "?")
    # old schema stores intent_mode at top level
    return str(state.get("intent_mode") or "?")


def _turn_intent(state: dict | None) -> str:
    if state is None:
        return "∅"
    v = state.get("turn_intent") or state.get("current_request") or "?"
    return str(v)[:70]


def compare(
    modal_states: dict[tuple, dict],
    local_states_map: dict[str, dict[tuple, dict]],
    labels: list[str],
    session_ids: set[str],
) -> None:
    # Collect all (session, turn) pairs
    all_keys = sorted(
        {k for k in modal_states if k[0] in session_ids} |
        {k for states in local_states_map.values() for k in states if k[0] in session_ids}
    )

    # Error summary
    print("\n=== ERRORS ===")
    for label, local_states in local_states_map.items():
        errs = [(k, v) for k, v in local_states.items() if v is None and k[0] in session_ids]
        print(f"  {label}: {len(errs)} errors out of {len(local_states)} rows")

    # Per-turn comparison table
    print("\n=== INTENT MODE COMPARISON (per session+turn) ===")
    header = f"{'session':<12} {'turn':>4}  {'Modal':<18}" + "".join(f"  {l:<18}" for l in labels)
    print(header)
    print("-" * len(header))

    for (sid, turn) in all_keys[:40]:
        modal_s = modal_states.get((sid, turn))
        modal_intent = _intent_summary(modal_s)
        row = f"{sid[:8]:<12} {turn:>4}  {modal_intent:<18}"
        for label in labels:
            local_s = local_states_map[label].get((sid, turn))
            local_intent = _intent_summary(local_s)
            match = "✓" if local_intent == modal_intent else "✗"
            row += f"  {match}{local_intent:<17}"
        print(row)

    print("\n=== TURN INTENT SNIPPET (first turn of each session) ===")
    for sid in sorted(session_ids):
        key = (sid, 1)
        modal_s = modal_states.get(key)
        print(f"\n{sid[:8]}... turn=1")
        print(f"  Modal   : {_turn_intent(modal_s)}")
        for label in labels:
            local_s = local_states_map[label].get(key)
            print(f"  {label:<10}: {_turn_intent(local_s)}")

    # Agreement stats
    print("\n=== INTENT MODE AGREEMENT RATES ===")
    for label, local_states in local_states_map.items():
        agree = 0
        total = 0
        for key in all_keys:
            if key[0] not in session_ids:
                continue
            modal_s = modal_states.get(key)
            local_s = local_states.get(key)
            if modal_s is None or local_s is None:
                continue
            total += 1
            if _intent_summary(modal_s) == _intent_summary(local_s):
                agree += 1
        pct = 100 * agree / total if total else 0
        print(f"  {label:<12}: {agree}/{total} ({pct:.0f}%)")

    print("\n=== ENTITY EXTRACTION SAMPLES (turn=1 per session) ===")
    for sid in sorted(session_ids):
        key = (sid, 1)
        modal_s = modal_states.get(key)
        print(f"\n{sid[:8]}... turn=1")
        print(f"  Modal   : {_entities_summary(modal_s, 'entities')}")
        for label in labels:
            local_s = local_states_map[label].get(key)
            print(f"  {label:<10}: {_entities_summary(local_s, 'entities')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modal-traces", nargs="+", required=True,
                        help="Glob patterns for Modal trace JSONLs")
    parser.add_argument("--local", nargs="+", required=True,
                        help="Paths to local extraction JONSLs")
    parser.add_argument("--labels", nargs="+", required=True,
                        help="Labels for each local extraction file")
    parser.add_argument("--sessions", required=True,
                        help="Sessions JSON file")
    args = parser.parse_args()

    if len(args.local) != len(args.labels):
        parser.error("--local and --labels must have same count")

    session_ids = load_sessions(args.sessions)
    print(f"Sessions: {len(session_ids)}")

    modal_states = load_trace_states(args.modal_traces, session_ids)
    print(f"Modal reference rows: {len(modal_states)}")

    local_states_map = {}
    for path, label in zip(args.local, args.labels):
        p = Path(path)
        if not p.exists():
            print(f"WARNING: {path} not found — skipping {label}")
            continue
        local_states_map[label] = load_local_states(path, session_ids)
        print(f"Local rows [{label}]: {len(local_states_map[label])}")

    if not local_states_map:
        print("No local extraction files found. Run extract_state.py first.")
        return 1

    compare(modal_states, local_states_map, list(local_states_map.keys()), session_ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
