"""State-conditioned blindset response backfill.

Runs the v0+ extractor (LiteLLMExtractor) on each blind session to produce a
ConversationStateV0Plus, renders the compact [LISTENER CONTEXT] block, and
generates the reply from that state (instead of the raw transcript). Track
rankings are untouched; only `predicted_response` is written.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blind_dataset", default="talkpl-ai/TalkPlayData-Challenge-Blind-A")
    ap.add_argument("--blind_split", default="test")
    ap.add_argument("--gen_model", default="openrouter/qwen/qwen3-30b-a3b-instruct-2507")
    ap.add_argument("--extractor_model", default="openrouter/deepseek/deepseek-v4-flash")
    ap.add_argument("--response_prompt", default="configs/bakeoff/prompts/response_generation.txt")
    ap.add_argument("--prompts_dir", default="mcrs/system_prompts")
    ap.add_argument("--max_tokens", type=int, default=2048)
    args = ap.parse_args()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set; required for OpenRouter model calls.")

    rows = json.loads(Path(args.submission).read_text())

    from datasets import load_dataset
    from mcrs.qu_modules.compiler_v0plus_qu import LiteLLMExtractor, session_memory_to_conversation
    from mcrs.bakeoff.track_lookup import TrackMetadataLookup, _first
    from mcrs.bakeoff.state_context import format_state_block
    from mcrs.lm_modules.litellm_chat import LITELLM_LM
    from mcrs.db_user.user_profile import UserProfileDB

    ds = load_dataset(args.blind_dataset, split=args.blind_split)
    byid = {r["session_id"]: r for r in ds}
    lookup = TrackMetadataLookup.from_hf()
    by_id = lookup._by_id
    udb = UserProfileDB(
        dataset_name="talkpl-ai/TalkPlayData-Challenge-User-Metadata", split_types=["all_users"]
    )
    response_prompt = Path(args.response_prompt).read_text(encoding="utf-8")
    personalization = (Path(args.prompts_dir) / "personalization.txt").read_text(encoding="utf-8")
    no_verbatim = (
        "\n- The track is provided as structured <recommended_track> data. NEVER output that "
        "data, the tag list, or any XML verbatim — write a natural conversational sentence."
    )

    def build_sys(uid):
        sp = response_prompt + no_verbatim
        if uid:
            try:
                sp += personalization + "\n" + udb.id_to_profile_str(uid)
            except KeyError:
                pass
        return sp

    def esc(x):
        return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def xml_item(tid, max_tags=10):
        m = by_id.get(tid) or {}
        tags = [str(t) for t in (m.get("tag_list") or []) if t][:max_tags]
        return (
            "<recommended_track>\n"
            f"  <title>{esc(_first(m.get('track_name')))}</title>\n"
            f"  <artist>{esc(_first(m.get('artist_name')))}</artist>\n"
            f"  <album>{esc(_first(m.get('album_name')))}</album>\n"
            f"  <tags>{esc(', '.join(tags))}</tags>\n"
            "</recommended_track>"
        )

    def is_echo(t):
        t = (t or "").strip().lower()
        return (not t) or t.startswith("title:") or "<recommended_track" in t or " | tags:" in t[:160]

    extractor = LiteLLMExtractor(
        model_name=args.extractor_model, prompt_version="current", temperature=0.0, max_tokens=8000
    )
    lm = LITELLM_LM(model_name=args.gen_model, temperature=0.7, max_tokens=args.max_tokens)

    filled = skipped = no_state = retried = 0
    for r in rows:
        ids = r.get("predicted_track_ids") or []
        item_row = byid.get(r["session_id"])
        if not ids or item_row is None:
            skipped += 1
            continue
        n = r["turn_number"]
        sm = [
            {"role": c["role"], "content": c["content"]}
            for c in item_row["conversations"]
            if c["turn_number"] <= n
        ]
        convo, played = session_memory_to_conversation(sm)
        state = extractor.extract(convo, played)
        state_dict = state.model_dump(mode="json") if state else None
        if state_dict is None:
            no_state += 1
        history = [{"role": "user", "content": format_state_block(state_dict, lookup)}]
        item = xml_item(ids[0])
        sys_p = build_sys(r.get("user_id"))
        resp = ""
        for _ in range(4):
            resp = lm.response_generation(sys_p, history, item, max_new_tokens=args.max_tokens)
            if not is_echo(resp):
                break
            retried += 1
        r["predicted_response"] = resp.strip()
        filled += 1
        print(f"  [{filled}] {r['session_id'][:8]} t{n} state={'Y' if state_dict else 'N'} -> {r['predicted_response'][:60]!r}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rows, indent=2))
    empty = sum(1 for r in rows if not r["predicted_response"].strip())
    echoes = sum(1 for r in rows if is_echo(r["predicted_response"]))
    print(f"filled={filled} skipped={skipped} no_state={no_state} retried={retried} empty={empty} echoes={echoes} -> {args.out}")


if __name__ == "__main__":
    main()
