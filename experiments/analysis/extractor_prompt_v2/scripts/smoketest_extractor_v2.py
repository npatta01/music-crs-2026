"""Cheap extractor-only A/B smoke test for the v2 prompt.

For each turn in the cohort (or a sample of it), call the LLM extractor with
the v2 prompt and compare against the original extractor output that is
already saved in the R2 trace. NO retrieval, NO compiler — only the extractor
LLM call. ~$0.003-0.01 per turn at openrouter/gemma-3-12b.

Inputs:
- cohort jsonl:  experiments/analysis/extractor_prompt_v2/artifacts/cohort_missed_literal_tags.jsonl
- devset:        HF talkpl-ai/TalkPlayData-Challenge-Dataset (test split)
- catalog:       HF talkpl-ai/TalkPlayData-Challenge-Track-Metadata (for music-turn labels)

Outputs:
- artifacts/smoketest_<model_slug>.jsonl  one row per turn: old vs new tags +
                                          which missed literals were recovered
- artifacts/smoketest_<model_slug>_summary.json  recovery-rate headline

Usage:
  # Default: 100 cohort turns through gemma-3-12b-it
  python experiments/analysis/extractor_prompt_v2/scripts/smoketest_extractor_v2.py

  # Try a beefier model
  python ... --model "openrouter/google/gemma-4-26b-a4b-it" --n 100
  python ... --model "openrouter/qwen/qwen3.6-35b-a3b" --n 100

The model_slug in output filenames sanitizes the model name.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Project root on path so we can import the v0+ extractor + the v2 prompt.
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from datasets import load_dataset

from mcrs.qu_modules.compiler_v0plus_qu import LiteLLMExtractor, session_memory_to_conversation
from experiments.analysis.conversation_state_extraction_bakeoff.schema import ConversationStateV0Plus


def load_prompt_module(version: str):
    """Select the prompt version's build_messages / schema functions."""
    if version in ("v2", "v2c"):
        from experiments.analysis.extractor_prompt_v2 import prompts_v2 as m
    elif version == "v3":
        from experiments.analysis.extractor_prompt_v2 import prompts_v3 as m
    else:
        raise ValueError(f"unknown prompt version: {version}")
    return m.build_messages, m.json_schema_for_response_format


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")
# Generic tokens that pollute the catalog-overlap signal (true of any track).
_OVERLAP_STOP = {
    "the","a","an","and","or","of","to","in","on","for","with","is","it","by",
    "song","songs","track","tracks","music","like","good","love","via","feat",
}


def overlap_tokens(tags) -> set[str]:
    out: set[str] = set()
    for t in tags or []:
        for m in WORD_RE.finditer(t or ""):
            w = m.group(0).lower()
            if len(w) >= 3 and w not in _OVERLAP_STOP:
                out.add(w)
    return out


def slugify_model(model_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", model_name).strip("_").lower()


def normalize(s: str) -> str:
    return s.strip().lower()


def tag_words(tags: list[str]) -> set[str]:
    out: set[str] = set()
    for t in tags or []:
        for m in WORD_RE.finditer(t):
            out.add(m.group(0).lower())
    return out


def state_positive_tags(state: ConversationStateV0Plus) -> list[str]:
    """Return the tags the *retriever* will see (mentioned_entities[type=tag, sentiment=1])."""
    out: list[str] = []
    for me in state.mentioned_entities or []:
        me_type = me.type.value if hasattr(me.type, "value") else me.type
        if me_type == "tag" and me.sentiment == 1:
            out.append(me.value)
    return out


def state_named_entities(state: ConversationStateV0Plus) -> list[dict]:
    """All non-tag mentioned_entities (artist/track/album) with sentiment."""
    out = []
    for me in state.mentioned_entities or []:
        me_type = me.type.value if hasattr(me.type, "value") else me.type
        if me_type != "tag":
            out.append({"type": me_type, "value": me.value, "sentiment": me.sentiment})
    return out


def session_memory_from_devset(conversations: list[dict[str, Any]],
                               turn_number: int) -> list[dict[str, Any]]:
    """Build a CRS_BASELINE-style session_memory through turn_number — i.e. up
    to and including the latest user message of `turn_number`. Drops the
    assistant + music entries for the current turn (they're what we want the
    extractor to predict context for)."""
    out: list[dict[str, Any]] = []
    for t in conversations:
        tn = t.get("turn_number", 0)
        role = t.get("role")
        content = t.get("content", "")
        if tn < turn_number:
            if role == "user":
                out.append({"role": "user", "content": content})
            elif role == "assistant":
                # Assistant message + the music it recommended come in two
                # entries in the devset; both are needed for the played list.
                out.append({"role": "assistant", "content": content})
            elif role == "music":
                out.append({"role": "music", "content": content})
        elif tn == turn_number and role == "user":
            out.append({"role": "user", "content": content})
    return out


def build_label_lookup() -> dict[str, str]:
    """artist - track labels keyed by track_id, for music-turn rendering."""
    ds = load_dataset(
        "talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks"
    )
    out: dict[str, str] = {}
    for r in ds:
        artist = (r["artist_name"] or [""])[0]
        track = (r["track_name"] or [""])[0]
        out[r["track_id"]] = f"{artist} - {track}".strip(" -")
    return out


def session_memory_to_conv_with_labels(session_memory, labels):
    """Local adapter that mirrors session_memory_to_conversation but doesn't
    need a CompilerCatalog instance (we don't want to spin up LanceDB just to
    look up labels for ~100 turns)."""
    conv: list[dict[str, Any]] = []
    played: list[str] = []
    turn = 0
    for item in session_memory:
        role = item.get("role")
        content = item.get("content", "") or ""
        if role == "user":
            turn += 1
            conv.append({"turn": turn, "role": "user", "text": str(content)})
        elif role == "assistant":
            conv.append({"turn": turn or 1, "role": "assistant", "text": str(content)})
        elif role == "music":
            tid = str(content).strip()
            played.append(tid)
            label = labels.get(tid, f"track={tid[:8]}")
            conv.append({"turn": turn or 1, "role": "music", "track_id": tid, "label": label})
    return conv, played


async def run_one(extractor: LiteLLMExtractor, conv, played, build_messages_fn, schema_fn) -> tuple[ConversationStateV0Plus | None, float]:
    """Patch the global build_messages in the extractor by temporarily
    monkey-patching the symbol on the module the extractor imports from."""
    # We monkey-patch the v1 symbols the extractor module imported at module
    # load time. Cheap, contained, deterministic.
    import mcrs.qu_modules.compiler_v0plus_qu as ext_mod
    old_build = ext_mod.build_messages
    old_schema = ext_mod.json_schema_for_response_format
    ext_mod.build_messages = build_messages_fn
    ext_mod.json_schema_for_response_format = schema_fn
    try:
        t0 = time.perf_counter()
        state = await extractor.aextract(conv, played)
        dt = time.perf_counter() - t0
        return state, dt
    finally:
        ext_mod.build_messages = old_build
        ext_mod.json_schema_for_response_format = old_schema


async def amain(args):
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Loading cohort from {args.cohort}")
    cohort: list[dict[str, Any]] = []
    with open(args.cohort) as fh:
        for line in fh:
            cohort.append(json.loads(line))
    print(f"      {len(cohort)} cohort turns")

    if args.n and len(cohort) > args.n:
        random.seed(args.seed)
        cohort = random.sample(cohort, args.n)
        print(f"      sampled {len(cohort)} for smoke test")

    # Resume support: skip turns already in the output file
    slug = f"{args.prompt_version}_{slugify_model(args.model)}"
    out_jsonl = Path(args.out_dir) / f"smoketest_{slug}.jsonl"
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    done_keys: set[tuple[str, int]] = set()
    if args.resume and out_jsonl.exists():
        with out_jsonl.open() as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    done_keys.add((r["session_id"], r["turn_number"]))
                except Exception:
                    continue
        if done_keys:
            print(f"      resume: {len(done_keys)} turns already done; skipping")
        cohort = [r for r in cohort if (r["session_id"], r["turn_number"]) not in done_keys]

    print(f"[2/4] Loading devset conversations (HF)")
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    sess_map = {r["session_id"]: r["conversations"] for r in ds}

    print(f"[3/4] Building track-label lookup")
    labels = build_label_lookup()

    print(f"[4/4] Calling extractor (model={args.model}, prompt={args.prompt_version}, in_flight={args.in_flight})")
    build_messages_fn, schema_fn = load_prompt_module(args.prompt_version)
    extractor = LiteLLMExtractor(
        model_name=args.model,
        temperature=0.0,
        max_tokens=1500,
        timeout_s=120,
    )

    results: list[dict[str, Any]] = []
    if args.resume and out_jsonl.exists():
        # Pre-load already-completed rows so summary reflects all of them
        with out_jsonl.open() as fh:
            for line in fh:
                try:
                    results.append(json.loads(line))
                except Exception:
                    continue
    sem = asyncio.Semaphore(args.in_flight)
    # Append mode for resumability
    out_fh = out_jsonl.open("a")

    async def process(row):
        async with sem:
            sid, tn = row["session_id"], row["turn_number"]
            convs = sess_map.get(sid, [])
            sm = session_memory_from_devset(convs, tn)
            conv, played = session_memory_to_conv_with_labels(sm, labels)
            state, dt = await run_one(extractor, conv, played, build_messages_fn, schema_fn)
            if state is None:
                return {"session_id": sid, "turn_number": tn, "error": "extract failed", "latency_s": dt}

            new_pos_tags = state_positive_tags(state)
            new_tag_words = tag_words(new_pos_tags)
            missed = set(row["missed_literal_tokens"])
            recovered = sorted(missed & new_tag_words)

            conv_text = " ".join(t.get("text", "") for t in conv).lower()
            named = state_named_entities(state)

            # --- Non-verbatim accounting (split into bridged vs pure-noise) ---
            # v3 deliberately emits non-verbatim catalog-canonical tags, so a flat
            # "hallucination" count is misleading. We instead measure each emitted
            # tag token against (a) the conversation text and (b) the GT track's
            # actual catalog tag_list.
            user_tokens = overlap_tokens([conv_text])
            gt_tag_tokens = overlap_tokens(row.get("gt_tags", []))
            emitted_tag_tokens = overlap_tokens(new_pos_tags)

            # Catalog overlap = the retrieval-predictive signal. How many of the
            # GT track's catalog tags did we surface?
            catalog_hits = sorted(emitted_tag_tokens & gt_tag_tokens)
            # Bridged = catalog tags we surfaced that the user did NOT literally
            # say (the vocabulary-bridging win v3 is designed to produce).
            bridged = sorted((emitted_tag_tokens & gt_tag_tokens) - user_tokens)
            # Pure noise = emitted tokens in NEITHER the conversation NOR the GT
            # tag list. Under boosting these are the only genuinely harmful ones.
            pure_noise = sorted(emitted_tag_tokens - user_tokens - gt_tag_tokens)

            # Legacy verbatim-hallucination count (kept for continuity with v2c runs)
            hallucinated = [tag for tag in new_pos_tags if tag.strip().lower() and tag.strip().lower() not in conv_text]
            for e in named:
                v = e["value"].strip().lower()
                if v and v not in conv_text:
                    hallucinated.append(f"[{e['type']}] {e['value']}")

            return {
                "session_id": sid, "turn_number": tn,
                "missed_literal_tokens": sorted(missed),
                "old_positive_tags": row["state_positive_tags"],
                "new_positive_tags": new_pos_tags,
                "new_named_entities": named,
                "new_hard_filters": [hf.model_dump(mode="json") for hf in (state.hard_filters or [])],
                "release_year_range": (state.release_year_range.model_dump() if getattr(state, "release_year_range", None) else None),
                "gt_tag_token_count": len(gt_tag_tokens),
                "recovered_tokens": recovered,
                "recovery_rate": len(recovered) / max(len(missed), 1),
                # Catalog-overlap metrics (retrieval-predictive)
                "catalog_hits": catalog_hits,
                "n_catalog_hits": len(catalog_hits),
                "catalog_recall": len(catalog_hits) / max(len(gt_tag_tokens), 1),
                "bridged_tokens": bridged,
                "n_bridged": len(bridged),
                "pure_noise_tokens": pure_noise,
                "n_pure_noise": len(pure_noise),
                "n_emitted_tag_tokens": len(emitted_tag_tokens),
                "pure_noise_rate": len(pure_noise) / max(len(emitted_tag_tokens), 1),
                # Legacy verbatim hallucination
                "hallucinated_tags": hallucinated,
                "n_hallucinated_tags": len(hallucinated),
                "n_emitted_tags": len(new_pos_tags),
                "n_emitted_named_entities": len(named),
                "hallucination_rate": len(hallucinated) / max(len(new_pos_tags) + len(named), 1),
                "latency_s": dt,
            }

    tasks = [process(r) for r in cohort]
    done = 0
    for fut in asyncio.as_completed(tasks):
        res = await fut
        results.append(res)
        # Stream to disk so we can resume on crash
        out_fh.write(json.dumps(res) + "\n")
        out_fh.flush()
        done += 1
        if done % 25 == 0:
            recs = sum(1 for r in results if r.get("recovered_tokens"))
            print(f"  {done}/{len(cohort)} done — turns with ≥1 recovered token so far: {recs}")
    out_fh.close()

    # Summary
    n = len(results)
    n_err = sum(1 for r in results if r.get("error"))
    n_ok = n - n_err
    n_recovered_any = sum(1 for r in results if r.get("recovered_tokens"))
    recovery_rates = [r["recovery_rate"] for r in results if "recovery_rate" in r]
    hallu_totals = [r.get("n_hallucinated_tags", 0) for r in results if "n_hallucinated_tags" in r]
    emit_totals = [r.get("n_emitted_tags", 0) for r in results if "n_emitted_tags" in r]
    hallu_rates = [r["hallucination_rate"] for r in results if "hallucination_rate" in r]
    n_zero_hallucination = sum(1 for r in results if r.get("n_hallucinated_tags") == 0)
    ok_rows = [r for r in results if not r.get("error")]
    # Catalog-overlap aggregates (retrieval-predictive)
    catalog_recalls = [r["catalog_recall"] for r in ok_rows if "catalog_recall" in r]
    n_with_catalog_hit = sum(1 for r in ok_rows if r.get("n_catalog_hits", 0) > 0)
    total_catalog_hits = sum(r.get("n_catalog_hits", 0) for r in ok_rows)
    total_bridged = sum(r.get("n_bridged", 0) for r in ok_rows)
    total_pure_noise = sum(r.get("n_pure_noise", 0) for r in ok_rows)
    total_emitted_tokens = sum(r.get("n_emitted_tag_tokens", 0) for r in ok_rows)
    summary = {
        "model": args.model,
        "prompt_version": args.prompt_version,
        "n_turns": n,
        "n_errors": n_err,
        # Literal recovery (legacy)
        "n_with_at_least_one_recovered_token": n_recovered_any,
        "share_with_at_least_one_recovered": n_recovered_any / max(n_ok, 1),
        "mean_per_turn_recovery_rate": sum(recovery_rates) / max(len(recovery_rates), 1),
        # Catalog overlap (the retrieval-predictive metrics)
        "mean_catalog_recall": sum(catalog_recalls) / max(len(catalog_recalls), 1),
        "share_turns_with_any_catalog_hit": n_with_catalog_hit / max(n_ok, 1),
        "total_catalog_hits": total_catalog_hits,
        "total_bridged_tokens": total_bridged,
        "total_pure_noise_tokens": total_pure_noise,
        "total_emitted_tag_tokens": total_emitted_tokens,
        "share_emitted_tokens_pure_noise": total_pure_noise / max(total_emitted_tokens, 1),
        # Legacy verbatim hallucination (note: under v3 bridged tags count here too)
        "total_emitted_tags": sum(emit_totals),
        "total_hallucinated_tags": sum(hallu_totals),
        "share_emitted_tags_hallucinated": sum(hallu_totals) / max(sum(emit_totals), 1),
        "n_turns_with_zero_hallucination": n_zero_hallucination,
        "latency_p50_s": sorted([r.get("latency_s", 0) for r in results])[n // 2],
    }
    (out_dir / f"smoketest_{slug}_summary.json").write_text(json.dumps(summary, indent=2))
    print()
    print(json.dumps(summary, indent=2))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cohort", default="experiments/analysis/extractor_prompt_v2/artifacts/cohort_missed_literal_tags.jsonl")
    p.add_argument("--out-dir", default="experiments/analysis/extractor_prompt_v2/artifacts")
    p.add_argument("--model", default="openrouter/google/gemma-3-12b-it")
    p.add_argument("--n", type=int, default=100, help="random sample size (0 = all)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--in-flight", type=int, default=8)
    p.add_argument("--prompt-version", default="v2c", choices=["v2", "v2c", "v3"],
                   help="Which prompt module to use (v2/v2c → prompts_v2, v3 → prompts_v3).")
    p.add_argument("--resume", action="store_true",
                   help="Skip turns already present in the output JSONL (resumable across crashes/runs).")
    args = p.parse_args()
    asyncio.run(amain(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
