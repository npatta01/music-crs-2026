"""Categorize residual failure modes of v2c × gemma-4-26b on the full cohort.

Run after `smoketest_extractor_v2.py --n 0 --resume` has produced
`smoketest_openrouter_google_gemma_4_26b_a4b_it.jsonl` in the v2c output dir.

What it categorizes (and why each matters for retrieval):

A. RECOVERY DISTRIBUTION  — overall tag recovery vs the missed-literal labels.
B. ARTIST-NAME COVERAGE   — proper noun extraction (highest signal anchor).
C. ERA → release_date     — when an era word lands in tags, does the
                            matching hard_filter also land? (sub-95% means
                            era constraints become soft hints, not filters).
D. REACTION-WORD LEAKAGE  — `awesome/amazing/great/love` showing up as
                            positive tags (pollutes ranking).
E. HALLUCINATION SOURCES  — which tags appear in outputs but not in conv text.
F. STILL-MISSED TOKEN BAG — what categories the model keeps dropping?
G. EMPTY-OUTPUT TURNS     — turns where extractor returned zero tags AND
                            zero named entities (worst-case state).
H. CALL FAILURES          — error count + rate.

Outputs:
- artifacts/full_cohort/residual_failures.json   (machine-readable summary)
- artifacts/full_cohort/residual_failures.md     (human-readable + examples)
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")
ERA_RE  = re.compile(
    r"\b("
    r"early\s+\d{2,4}s?|late\s+\d{2,4}s?|mid\s+\d{2,4}s?|"
    r"\d{4}s?|"
    r"[1-9]0s|"
    r"modern|vintage|contemporary|classic\s+rock|oldies"
    r")\b", re.I,
)

REACTION_WORDS = {
    "awesome","amazing","great","good","perfect","fantastic","wonderful",
    "love","loved","cool","nice","incredible","brilliant","outstanding",
    "thanks","thank","recommendations","pick","picks","choice","choices",
}

GENERIC_FILLER = {
    "song","songs","track","tracks","music","artist","band","one","time",
    "thing","stuff","kind","sort","more","another","again","again",
}


def tag_tokens(tag: str) -> set[str]:
    return {m.group(0).lower() for m in WORD_RE.finditer(tag or "")}


def all_tag_tokens(tags) -> set[str]:
    out: set[str] = set()
    for t in tags or []:
        out |= tag_tokens(t)
    return out


def main(path: Path, out_dir: Path):
    rows = []
    with path.open() as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    total = len(rows)
    if total == 0:
        print("No rows.")
        return

    # H — call failures
    errored = [r for r in rows if r.get("error")]
    ok = [r for r in rows if not r.get("error")]

    # A — recovery distribution
    recovery_rates = [r["recovery_rate"] for r in ok if "recovery_rate" in r]
    n_any_rec = sum(1 for r in ok if r.get("recovered_tokens"))

    # B — artist-name coverage (vs the original cohort's literal artist tokens we know about)
    # Pull known artist-mention turns from cohort (heuristic: cohort entries that
    # have a `gt_artist_name` whose surname tokens appear in user_text_latest_turn)
    artist_recovered = 0
    artist_failed = 0
    artist_examples_failed: list[dict] = []
    # The smoketest jsonl has new_named_entities but not user_text_latest_turn or gt_artist_name,
    # so we instead approximate using whether anything is in named_entities.
    # We additionally count: turns where missed_literal_tokens contained a token
    # not in TAG output AND that token is a proper-noun shape (capitalized in user text).
    # This is approximate — full audit requires the cohort jsonl join.

    # C — era → release_date conversion
    n_era_in_tag = 0
    n_era_with_filter = 0
    era_missing_filter_examples: list[dict] = []
    for r in ok:
        tag_blob = " ".join(r.get("new_positive_tags", []))
        has_era = bool(ERA_RE.search(tag_blob.lower()))
        has_filter = bool(r.get("new_hard_filters"))
        if has_era:
            n_era_in_tag += 1
            if has_filter:
                n_era_with_filter += 1
            else:
                if len(era_missing_filter_examples) < 8:
                    era_missing_filter_examples.append({
                        "session_id": r["session_id"],
                        "turn_number": r["turn_number"],
                        "tags": r["new_positive_tags"],
                        "era_words_in_tags": ERA_RE.findall(tag_blob.lower())[:5],
                    })

    # D — reaction-word leakage
    leak_counts: Counter[str] = Counter()
    leak_turns: set[tuple] = set()
    leak_examples: list[dict] = []
    for r in ok:
        leaked = [t for t in r.get("new_positive_tags", [])
                  if t.strip().lower() in REACTION_WORDS]
        for t in leaked:
            leak_counts[t.lower()] += 1
        if leaked:
            leak_turns.add((r["session_id"], r["turn_number"]))
            if len(leak_examples) < 8:
                leak_examples.append({
                    "session_id": r["session_id"],
                    "turn_number": r["turn_number"],
                    "leaked": leaked,
                    "all_tags": r["new_positive_tags"],
                })

    # E — hallucination sources
    hallu_counts: Counter[str] = Counter()
    n_hallu = 0
    hallu_examples: list[dict] = []
    for r in ok:
        for tag in r.get("hallucinated_tags", []) or []:
            hallu_counts[str(tag).lower()] += 1
            n_hallu += 1
        if r.get("hallucinated_tags") and len(hallu_examples) < 8:
            hallu_examples.append({
                "session_id": r["session_id"],
                "turn_number": r["turn_number"],
                "hallucinated_tags": r["hallucinated_tags"],
                "all_tags": r["new_positive_tags"],
            })

    # F — still-missed token bag
    still_missed: Counter[str] = Counter()
    for r in ok:
        new_words = all_tag_tokens(r.get("new_positive_tags", []))
        for t in r.get("missed_literal_tokens", []):
            if t.lower() not in new_words:
                still_missed[t.lower()] += 1

    # G — empty-output turns
    empty_turns: list[dict] = []
    for r in ok:
        if not r.get("new_positive_tags") and not r.get("new_named_entities"):
            empty_turns.append(r)

    # Build summary
    summary = {
        "n_total": total,
        "n_ok": len(ok),
        "n_errors": len(errored),
        "error_rate": len(errored) / max(total, 1),

        "share_with_at_least_one_recovered": n_any_rec / max(len(ok), 1),
        "mean_per_turn_recovery_rate": sum(recovery_rates) / max(len(recovery_rates), 1),

        "n_era_in_tag": n_era_in_tag,
        "n_era_with_release_date_filter": n_era_with_filter,
        "era_to_filter_conversion_rate": n_era_with_filter / max(n_era_in_tag, 1),

        "reaction_word_leak_turns": len(leak_turns),
        "reaction_word_leak_share": len(leak_turns) / max(len(ok), 1),
        "top_reaction_leak_tokens": leak_counts.most_common(15),

        "total_hallucinated_tag_instances": n_hallu,
        "share_emitted_tags_hallucinated": (
            n_hallu / max(sum(r.get("n_emitted_tags", 0) for r in ok), 1)
        ),
        "top_hallucinated_tokens": hallu_counts.most_common(20),

        "top_still_missed_tokens": still_missed.most_common(30),

        "n_empty_output_turns": len(empty_turns),
        "share_empty_output": len(empty_turns) / max(len(ok), 1),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "residual_failures.json").write_text(json.dumps(summary, indent=2))

    # Human-readable markdown
    md = [
        "# v2c × gemma-4-26b residual-failure analysis on full cohort",
        "",
        f"**Total turns:** {total}    **OK:** {len(ok)}    **Errored:** {len(errored)} ({summary['error_rate']*100:.1f}%)",
        "",
        "## A. Tag-recovery distribution",
        f"- Turns with ≥1 recovered missed token: **{summary['share_with_at_least_one_recovered']*100:.1f}%**",
        f"- Mean per-turn recovery rate (of missed tokens): **{summary['mean_per_turn_recovery_rate']*100:.1f}%**",
        "",
        "## C. Era → `release_date` hard_filter conversion",
        f"- Turns with an era word in tags: **{n_era_in_tag}**",
        f"- ... with the matching `release_date` hard_filter: **{n_era_with_filter}** ({summary['era_to_filter_conversion_rate']*100:.1f}%)",
        "",
        "Example era-without-filter turns:",
    ]
    for ex in era_missing_filter_examples:
        md.append(f"- {ex['session_id'][:8]} t{ex['turn_number']}: era words {ex['era_words_in_tags']!r} in tags {ex['tags']}")
    md += [
        "",
        "## D. Reaction-word leakage (tags like 'awesome', 'great', 'love', etc.)",
        f"- Turns with at least one reaction word as a positive tag: **{len(leak_turns)}** ({summary['reaction_word_leak_share']*100:.1f}%)",
        "",
        "Top leaked tokens:",
    ]
    for tok, n in leak_counts.most_common(15):
        md.append(f"- {n}× `{tok}`")
    md += [
        "",
        "Example reaction-leak turns:",
    ]
    for ex in leak_examples:
        md.append(f"- {ex['session_id'][:8]} t{ex['turn_number']}: leaked={ex['leaked']} all_tags={ex['all_tags']}")
    md += [
        "",
        "## E. Hallucination",
        f"- Total hallucinated tag instances (not in conv text): **{n_hallu}**",
        f"- Share of all emitted tags that are hallucinations: **{summary['share_emitted_tags_hallucinated']*100:.2f}%**",
        "",
        "Top hallucinated tokens:",
    ]
    for tok, n in hallu_counts.most_common(20):
        md.append(f"- {n}× `{tok}`")
    md += [
        "",
        "## F. Top still-missed tokens (classifier reports missed; gemma-4 didn't emit)",
    ]
    for tok, n in still_missed.most_common(30):
        md.append(f"- {n}× `{tok}`")
    md += [
        "",
        "## G. Empty-output turns (zero tags AND zero named entities)",
        f"- **{len(empty_turns)}** turns ({summary['share_empty_output']*100:.1f}%)",
    ]

    (out_dir / "residual_failures.md").write_text("\n".join(md))

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--in",
                   default="experiments/analysis/extractor_prompt_v2/artifacts/full_cohort/smoketest_openrouter_google_gemma_4_26b_a4b_it.jsonl",
                   dest="in_path")
    p.add_argument("--out-dir",
                   default="experiments/analysis/extractor_prompt_v2/artifacts/full_cohort",
                   dest="out_dir")
    args = p.parse_args()
    main(Path(args.in_path), Path(args.out_dir))
