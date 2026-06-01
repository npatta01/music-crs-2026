"""Head-to-head: v2c vs v3 on the full cohort.

Both smoketest jsonl files store `new_positive_tags` per turn. We join each with
the cohort's `gt_tags` (the GT track's catalog tag_list) to compute the
retrieval-predictive catalog-overlap metrics offline — so the v2c run (done
before those metrics existed) is comparable to v3 without a re-run.

Metrics per prompt:
- literal recovery: share of turns recovering ≥1 missed literal token
- catalog recall:   mean fraction of GT catalog tag tokens surfaced
- catalog hit rate:  share of turns surfacing ≥1 GT catalog tag
- bridged tokens:    catalog tags surfaced that the user did NOT literally say
- pure noise:        emitted tokens in NEITHER conv text NOR GT tags
- era-filter rate:   share of era-mentioning turns that emit a release_date filter
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")
ERA_RE = re.compile(
    r"\b(early\s+\d{2,4}s?|late\s+\d{2,4}s?|mid\s+\d{2,4}s?|\d{4}s?|[1-9]0s|"
    r"modern|vintage|contemporary|oldies)\b", re.I,
)
_STOP = {
    "the","a","an","and","or","of","to","in","on","for","with","is","it","by",
    "song","songs","track","tracks","music","like","good","love","via","feat",
}


def toks(items):
    out = set()
    for t in items or []:
        for m in WORD_RE.finditer(t or ""):
            w = m.group(0).lower()
            if len(w) >= 3 and w not in _STOP:
                out.add(w)
    return out


def load_jsonl(p: Path):
    rows = []
    with p.open() as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def load_cohort(p: Path):
    by_key = {}
    with p.open() as fh:
        for line in fh:
            r = json.loads(line)
            by_key[(r["session_id"], r["turn_number"])] = r
    return by_key


def analyze(rows, cohort, user_text_by_key):
    n = len(rows)
    ok = [r for r in rows if not r.get("error")]
    n_err = n - len(ok)

    lit_recovered = 0
    catalog_recalls = []
    n_catalog_hit = 0
    total_bridged = total_noise = total_emitted = 0
    era_turns = era_with_filter = 0

    for r in ok:
        key = (r["session_id"], r["turn_number"])
        c = cohort.get(key, {})
        gt = toks(c.get("gt_tags", []))
        emitted = toks(r.get("new_positive_tags", []))
        # user text tokens: prefer cohort's stored user text; fall back to none
        utext = user_text_by_key.get(key, c.get("user_text_latest_turn", ""))
        user = toks([utext])

        if r.get("recovered_tokens"):
            lit_recovered += 1

        hits = emitted & gt
        catalog_recalls.append(len(hits) / max(len(gt), 1))
        if hits:
            n_catalog_hit += 1
        total_bridged += len(hits - user)
        total_noise += len(emitted - user - gt)
        total_emitted += len(emitted)

        # era→filter
        tag_blob = " ".join(r.get("new_positive_tags", [])).lower()
        if ERA_RE.search(tag_blob):
            era_turns += 1
            if r.get("new_hard_filters"):
                era_with_filter += 1

    lat = sorted(r.get("latency_s", 0) for r in rows)
    return {
        "n": n, "n_errors": n_err,
        "literal_recovery_share": lit_recovered / max(len(ok), 1),
        "mean_catalog_recall": sum(catalog_recalls) / max(len(catalog_recalls), 1),
        "catalog_hit_share": n_catalog_hit / max(len(ok), 1),
        "total_bridged": total_bridged,
        "total_pure_noise": total_noise,
        "total_emitted_tokens": total_emitted,
        "pure_noise_rate": total_noise / max(total_emitted, 1),
        "era_turns": era_turns,
        "era_filter_rate": era_with_filter / max(era_turns, 1),
        "latency_p50": lat[len(lat) // 2] if lat else 0,
    }


def main():
    base = Path("experiments/analysis/extractor_prompt_v2/artifacts")
    cohort = load_cohort(base / "cohort_missed_literal_tags.jsonl")

    # User text per key (from cohort jsonl)
    user_text_by_key = {
        (r["session_id"], r["turn_number"]): r.get("user_text_latest_turn", "")
        for r in cohort.values()
    }

    runs = {
        "v2c": base / "full_cohort/smoketest_openrouter_google_gemma_4_26b_a4b_it.jsonl",
        "v3":  base / "full_cohort/smoketest_v3_openrouter_google_gemma_4_26b_a4b_it.jsonl",
    }
    results = {}
    for name, p in runs.items():
        if not p.exists():
            print(f"!! missing {name}: {p}")
            continue
        results[name] = analyze(load_jsonl(p), cohort, user_text_by_key)

    # Print comparison table
    keys = [
        ("literal_recovery_share", "literal recovery (≥1)", "{:.1%}"),
        ("mean_catalog_recall", "mean catalog recall", "{:.1%}"),
        ("catalog_hit_share", "turns w/ ≥1 catalog hit", "{:.1%}"),
        ("total_bridged", "bridged tokens (total)", "{:,}"),
        ("total_pure_noise", "pure-noise tokens (total)", "{:,}"),
        ("pure_noise_rate", "pure-noise rate", "{:.1%}"),
        ("era_filter_rate", "era→release_date rate", "{:.1%}"),
        ("total_emitted_tokens", "emitted tag tokens (total)", "{:,}"),
        ("n_errors", "call errors", "{}"),
        ("latency_p50", "p50 latency (s)", "{:.1f}"),
    ]
    names = [n for n in ("v2c", "v3") if n in results]
    print(f"\n{'metric':<30} " + "  ".join(f"{n:>12}" for n in names))
    print("-" * (30 + 14 * len(names)))
    for k, label, fmt in keys:
        row = f"{label:<30} "
        for n in names:
            row += f"  {fmt.format(results[n][k]):>12}"
        print(row)

    (base / "full_cohort/compare_v2c_v3.json").write_text(json.dumps(results, indent=2))
    print(f"\nWrote {base/'full_cohort/compare_v2c_v3.json'}")


if __name__ == "__main__":
    main()
