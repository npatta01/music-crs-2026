"""Judge bake-off responses with a Gemini+neutral panel + Distinct-2.

Usage:
  python scripts/judge_responses.py \
    --responses_dir exp/bakeoff/responses \
    --models configs/bakeoff/models.yaml \
    --out_dir exp/bakeoff
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from evaluator.metrics.metrics_diversity import compute_lexical_diversity
from mcrs.bakeoff.judge import (
    aggregate_model_report,
    build_judge_prompt,
    parse_judge_json,
)


def _conversation_text(convs: list[dict], turn_number: int) -> str:
    lines = [
        f"{c['role']}: {c['content']}"
        for c in convs
        if c["turn_number"] < turn_number and c["role"] in ("user", "assistant")
    ]
    # include the current turn's user ask — the request the reply must address
    lines += [
        f"user: {c['content']}"
        for c in convs
        if c["turn_number"] == turn_number and c["role"] == "user"
    ]
    return "\n".join(lines)


def render_markdown(reports: list[dict]) -> str:
    rows = sorted(reports, key=lambda r: r["combined"], reverse=True)
    out = ["# Response bake-off report", "",
           "| Model | Distinct-2 | Personalization (panel) | Explanation (panel) | Combined | turns |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(
            f"| {r['tag']} | {r['distinct2']:.3f} | {r['personalization_panel']:.3f} "
            f"| {r['explanation_panel']:.3f} | {r['combined']:.3f} | {r['n_turns']} |"
        )
    out += ["", "## Per-judge (personalization / explanation)", ""]
    for r in rows:
        out.append(
            f"- **{r['tag']}**: "
            + ", ".join(
                f"{jn}={r['personalization_by_judge'][jn]:.2f}/{r['explanation_by_judge'][jn]:.2f}"
                for jn in sorted(r["personalization_by_judge"])
            )
        )
    out += ["", "## Judge parse failures", ""]
    for r in rows:
        out.append(f"- **{r['tag']}**: {r.get('parse_failures', 0)}")
    out += ["", "_Proxy judge — relative ranking only; official Gemini prompt is undisclosed._"]
    return "\n".join(out)


def main() -> None:
    import os
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set; required for OpenRouter model calls.")
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses_dir", default="exp/bakeoff/responses")
    ap.add_argument("--models", default="configs/bakeoff/models.yaml")
    ap.add_argument("--out_dir", default="exp/bakeoff")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.models).read_text())
    judges = cfg["judges"]

    from mcrs.db_user.user_profile import UserProfileDB
    user_db = UserProfileDB(
        dataset_name="talkpl-ai/TalkPlayData-Challenge-User-Metadata",
        split_types=["all_users"],
    )

    def _profile(user_id):
        if not user_id:
            return None
        try:
            return user_db.id_to_profile_str(user_id)
        except KeyError:
            return None

    from datasets import load_dataset
    from mcrs.lm_modules.litellm_client import LiteLLMChatClient
    from mcrs.bakeoff.track_lookup import TrackMetadataLookup

    lookup = TrackMetadataLookup.from_hf()
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    convs_by_session = {r["session_id"]: r["conversations"] for r in ds}

    judge_clients = {
        # 512 (not 32): reasoning judges (e.g. gpt-5-mini) spend the token budget
        # on hidden reasoning and return empty content at small caps. Overridable
        # per judge via `max_tokens` in models.yaml.
        name: LiteLLMChatClient(
            model_name=spec["model_name"], temperature=0.0,
            max_tokens=spec.get("max_tokens", 512),
        )
        for name, spec in judges.items()
    }

    reports = []
    audit_dir = Path(args.out_dir) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    for resp_file in sorted(Path(args.responses_dir).glob("*.json")):
        tag = resp_file.stem
        recs = json.loads(resp_file.read_text())
        per_turn = []
        audit = []
        parse_failures = 0
        for rec in recs:
            convs = convs_by_session.get(rec["session_id"], [])
            conv_text = _conversation_text(convs, rec["turn_number"])
            track = lookup.id_to_metadata(rec["top_track_id"])
            profile = _profile(rec.get("user_id"))
            prompt = build_judge_prompt(conv_text, rec["response"], track, profile)
            judges_scores = {}
            raw_by_judge = {}
            for jn, client in judge_clients.items():
                raw = client.chat(messages=[{"role": "user", "content": prompt}])
                raw_by_judge[jn] = raw
                try:
                    judges_scores[jn] = parse_judge_json(raw)
                except ValueError:
                    parse_failures += 1
                    # Do NOT score a parse failure as 1/1 — that corrupts the mean.
                    # Exclude this (turn, judge) from aggregation instead (aggregate_model_report
                    # already skips judges absent from a turn).
            per_turn.append({"turn": rec["turn_number"], "judges": judges_scores})
            audit.append({
                "session_id": rec["session_id"],
                "turn": rec["turn_number"],
                "response": rec["response"],
                "scores": judges_scores,
                "raw": raw_by_judge,
            })
        distinct2 = compute_lexical_diversity([r["response"] for r in recs])
        report = aggregate_model_report(tag, per_turn, distinct2)
        report["parse_failures"] = parse_failures
        reports.append(report)
        (audit_dir / f"{tag}.json").write_text(json.dumps(audit, indent=2))
        print(f"judged {tag}: combined={report['combined']:.3f} parse_failures={parse_failures}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(reports, indent=2))
    (out_dir / "report.md").write_text(render_markdown(reports))
    print(f"wrote {out_dir/'report.md'}")


if __name__ == "__main__":
    main()
