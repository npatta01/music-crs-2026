"""Backfill `predicted_response` into a blindset submission.

Holds retrieval fixed (keeps the submission's `predicted_track_ids` untouched) and
generates only the natural-language reply for each row, using the bake-off winner
setup: role+goal "track explainer" prompt + user profile, transcript-conditioned,
via a chosen model. Only `predicted_response` is modified.

Usage:
  python scripts/backfill_blindset_responses.py \
    --submission /path/prediction.json --out /path/prediction.json \
    --model openrouter/qwen/qwen3-30b-a3b-instruct-2507
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
    ap.add_argument("--model", default="openrouter/qwen/qwen3-30b-a3b-instruct-2507")
    ap.add_argument("--response_prompt", default="configs/bakeoff/prompts/response_generation.txt")
    ap.add_argument("--prompts_dir", default="mcrs/system_prompts")
    ap.add_argument("--max_tokens", type=int, default=2048)
    ap.add_argument("--temperature", type=float, default=0.7)
    args = ap.parse_args()

    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set; required for OpenRouter model calls.")

    rows = json.loads(Path(args.submission).read_text())

    from datasets import load_dataset
    from mcrs.bakeoff.track_lookup import TrackMetadataLookup, _first
    from mcrs.bakeoff.replay import build_turn_inputs
    from mcrs.lm_modules.litellm_chat import LITELLM_LM
    from mcrs.db_user.user_profile import UserProfileDB

    ds = load_dataset(args.blind_dataset, split=args.blind_split)
    conv_by_session = {r["session_id"]: r["conversations"] for r in ds}
    lookup = TrackMetadataLookup.from_hf()
    by_id = lookup._by_id
    user_db = UserProfileDB(
        dataset_name="talkpl-ai/TalkPlayData-Challenge-User-Metadata",
        split_types=["all_users"],
    )
    response_prompt = Path(args.response_prompt).read_text(encoding="utf-8")
    personalization = (Path(args.prompts_dir) / "personalization.txt").read_text(encoding="utf-8")
    # The track is presented as a labeled XML block with capped tags. Both the XML
    # delimiting and the explicit instruction stop the model from echoing the raw
    # metadata blob verbatim (observed failure mode with the pipe-delimited string).
    no_verbatim = (
        "\n- The track is provided as structured <recommended_track> data. NEVER output that "
        "data, the tag list, or any XML verbatim — write a natural conversational sentence."
    )

    def build_system_prompt(user_id):
        sp = response_prompt + no_verbatim
        if user_id:
            try:
                sp += personalization + "\n" + user_db.id_to_profile_str(user_id)
            except KeyError:
                pass
        return sp

    def _esc(x):
        return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def xml_item(track_id, max_tags=10):
        m = by_id.get(track_id) or {}
        tags = [str(t) for t in (m.get("tag_list") or []) if t][:max_tags]
        return (
            "<recommended_track>\n"
            f"  <title>{_esc(_first(m.get('track_name')))}</title>\n"
            f"  <artist>{_esc(_first(m.get('artist_name')))}</artist>\n"
            f"  <album>{_esc(_first(m.get('album_name')))}</album>\n"
            f"  <tags>{_esc(', '.join(tags))}</tags>\n"
            "</recommended_track>"
        )

    def _is_echo(t):
        t = (t or "").strip().lower()
        return (not t) or t.startswith("title:") or "<recommended_track" in t or " | tags:" in t[:160]

    lm = LITELLM_LM(model_name=args.model, temperature=args.temperature, max_tokens=args.max_tokens)

    filled = skipped = retried = 0
    for r in rows:
        ids = r.get("predicted_track_ids") or []
        convs = conv_by_session.get(r["session_id"])
        if not ids or convs is None:
            skipped += 1
            continue
        sys_p, history, _ = build_turn_inputs(
            convs, r["turn_number"], ids[0], lookup, build_system_prompt(r.get("user_id"))
        )
        item = xml_item(ids[0])  # XML + capped tags instead of the raw pipe blob
        resp = ""
        for attempt in range(4):  # safety net; should rarely fire now
            resp = lm.response_generation(sys_p, history, item, max_new_tokens=args.max_tokens)
            if not _is_echo(resp):
                break
            retried += 1
        r["predicted_response"] = resp.strip()
        filled += 1
        print(f"  [{filled}] {r['session_id'][:8]} t{r['turn_number']} -> {r['predicted_response'][:70]!r}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rows, indent=2))
    empty = sum(1 for r in rows if not (r.get("predicted_response") or "").strip())
    echoes = sum(1 for r in rows if _is_echo(r.get("predicted_response")))
    print(f"filled={filled} skipped={skipped} retried={retried} still_empty={empty} echoes={echoes} -> {args.out}")


if __name__ == "__main__":
    main()
