"""Replay response generation across candidate models on a fixed slice.

Reads existing retrieval predictions (top-1 track per turn), reconstructs the
production prompt inputs, and generates a response per candidate model. Outputs
one JSON per model under exp/bakeoff/responses/.

Usage:
  python scripts/response_bakeoff.py \
    --predictions exp/inference/devset/v0plus_compiler_all_retrievers_devset.json \
    --slice exp/subsets/bakeoff_smoke_8.json \
    --models configs/bakeoff/models.yaml \
    --out_dir exp/bakeoff/responses
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def collect_turns(predictions: list[dict], session_ids: set[str]) -> list[dict]:
    turns = []
    for r in predictions:
        if r["session_id"] not in session_ids:
            continue
        ids = r.get("predicted_track_ids") or []
        if not ids:
            continue
        turns.append({
            "session_id": r["session_id"],
            "turn_number": r["turn_number"],
            "top_track_id": ids[0],
            "user_id": r.get("user_id"),
        })
    turns.sort(key=lambda t: (t["session_id"], t["turn_number"]))
    return turns


def main() -> None:
    import os
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set; required for OpenRouter model calls.")
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--slice", required=True)
    ap.add_argument("--models", default="configs/bakeoff/models.yaml")
    ap.add_argument("--prompts_dir", default="mcrs/system_prompts")
    ap.add_argument("--out_dir", default="exp/bakeoff/responses")
    ap.add_argument("--only", default=None, help="comma-separated tags to run")
    ap.add_argument("--response_prompt", default="configs/bakeoff/prompts/response_generation.txt")
    ap.add_argument("--mode", choices=["transcript", "state"], default="transcript")
    ap.add_argument("--trace", default=None,
                    help="trace jsonl with per-turn state (required for --mode state)")
    args = ap.parse_args()

    predictions = json.loads(Path(args.predictions).read_text())
    session_ids = set(json.loads(Path(args.slice).read_text())["session_ids"])
    cfg = yaml.safe_load(Path(args.models).read_text())
    defaults = cfg.get("defaults", {})
    turns = collect_turns(predictions, session_ids)
    print(f"slice sessions={len(session_ids)} turns={len(turns)}")

    from mcrs.bakeoff.track_lookup import TrackMetadataLookup
    from mcrs.bakeoff.replay import generate_for_model
    from mcrs.lm_modules.litellm_chat import LITELLM_LM
    from mcrs.db_user.user_profile import UserProfileDB

    convs_by_session = None
    states = None
    if args.mode == "state":
        if not args.trace:
            raise SystemExit("--trace is required for --mode state")
        from mcrs.bakeoff.state_context import load_states
        states = load_states(args.trace, session_ids)
        print(f"loaded states for {len(states)} (session,turn) keys")
    else:
        from datasets import load_dataset
        ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
        convs_by_session = {r["session_id"]: r["conversations"]
                            for r in ds if r["session_id"] in session_ids}
    lookup = TrackMetadataLookup.from_hf()
    user_db = UserProfileDB(
        dataset_name="talkpl-ai/TalkPlayData-Challenge-User-Metadata",
        split_types=["all_users"],
    )
    prompts_dir = Path(args.prompts_dir)
    roleplay = (prompts_dir / "roleplay.txt").read_text(encoding="utf-8")
    response = Path(args.response_prompt).read_text(encoding="utf-8")
    personalization = (prompts_dir / "personalization.txt").read_text(encoding="utf-8")

    def build_system_prompt(user_id):
        sp = roleplay + response
        if user_id:
            try:
                sp += personalization + "\n" + user_db.id_to_profile_str(user_id)
            except KeyError:
                pass  # unknown user_id -> no profile segment
        return sp

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None

    for g in cfg["generators"]:
        if only and g["tag"] not in only:
            continue
        print(f"== generating: {g['tag']} ({g['model_name']})")
        lm = LITELLM_LM(
            model_name=g["model_name"],
            temperature=defaults.get("temperature", 0.7),
            max_tokens=defaults.get("max_tokens", 2048),
            completion_kwargs=g.get("completion_kwargs") or {},
        )
        if args.mode == "state":
            from mcrs.bakeoff.replay import generate_for_model_state
            recs = generate_for_model_state(
                lm, turns, build_system_prompt, states, lookup,
                max_new_tokens=defaults.get("max_tokens", 2048),
            )
        else:
            recs = generate_for_model(
                lm, turns, build_system_prompt, lookup, convs_by_session,
                max_new_tokens=defaults.get("max_tokens", 2048),
            )
        (out_dir / f"{g['tag']}.json").write_text(json.dumps(recs, indent=2))
        print(f"   wrote {len(recs)} responses -> {out_dir / (g['tag'] + '.json')}")


if __name__ == "__main__":
    main()
