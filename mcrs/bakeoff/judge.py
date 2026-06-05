"""G-Eval-style proxy judge for the response bake-off.

The official server-side judge prompt is undisclosed; this is a reconstructed
proxy for RELATIVE ranking only. Two axes scored 1-5: personalization and
explanation quality. Normalized (s-1)/4.
"""
from __future__ import annotations

import json
import re
from statistics import mean

JUDGE_SYSTEM = (
    "You are a strict evaluator of a music chatbot's reply. Score the reply on "
    "two axes, each an integer 1-5:\n"
    "- personalization: is it tailored to the listener's stated taste/request/history, "
    "and is it in the listener's language?\n"
    "- explanation: is the 'why this track' clear, honest about any mismatch (not "
    "overselling), natural, and non-repetitive?\n"
    'Respond ONLY with JSON: {"personalization": <1-5>, "explanation": <1-5>}'
)


def build_judge_prompt(conversation: str, response: str, track: str, profile: str | None = None) -> str:
    profile_block = f"[LISTENER PROFILE]\n{profile}\n\n" if profile else ""
    return (
        f"{JUDGE_SYSTEM}\n\n"
        f"{profile_block}"
        f"[CONVERSATION SO FAR]\n{conversation}\n\n"
        f"[RECOMMENDED TRACK]\n{track}\n\n"
        f"[CHATBOT REPLY TO SCORE]\n{response}\n\n"
        "JSON:"
    )


def parse_judge_json(raw: str) -> dict:
    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object in judge output: {raw!r}")
    obj = json.loads(m.group(0))
    out = {}
    for axis in ("personalization", "explanation"):
        if axis not in obj:
            raise ValueError(f"missing axis {axis} in {obj!r}")
        out[axis] = max(1, min(5, int(round(float(obj[axis])))))
    return out


def normalize_score(s: float) -> float:
    return (float(s) - 1.0) / 4.0


def aggregate_model_report(tag: str, per_turn: list[dict], distinct2: float) -> dict:
    """per_turn: [{turn, judges: {judge_name: {personalization, explanation}}}]"""
    judge_names = sorted({j for t in per_turn for j in t["judges"]})
    by_judge = {axis: {} for axis in ("personalization", "explanation")}
    for axis in ("personalization", "explanation"):
        for jn in judge_names:
            vals = [normalize_score(t["judges"][jn][axis]) for t in per_turn if jn in t["judges"]]
            by_judge[axis][jn] = mean(vals) if vals else 0.0
    pers_panel = mean(by_judge["personalization"].values()) if judge_names else 0.0
    expl_panel = mean(by_judge["explanation"].values()) if judge_names else 0.0
    return {
        "tag": tag,
        "distinct2": distinct2,
        "personalization_by_judge": by_judge["personalization"],
        "explanation_by_judge": by_judge["explanation"],
        "personalization_panel": pers_panel,
        "explanation_panel": expl_panel,
        "combined": (pers_panel + expl_panel) / 2,
        "n_turns": len(per_turn),
    }
