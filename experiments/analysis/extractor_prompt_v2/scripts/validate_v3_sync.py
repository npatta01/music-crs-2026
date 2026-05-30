"""Synchronous v3 validation — avoids the flaky async batch path.

Runs the v3 extractor SEQUENTIALLY (extract(), not aextract()) on a sample of
cohort turns and reports the same retrieval-predictive metrics as the smoke
test, plus release_year_range coverage. Sync = robust against the async
half-closed-connection hangs we hit.
"""
from __future__ import annotations
import json, re, sys, time, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from datasets import load_dataset
from mcrs.qu_modules.compiler_v0plus_qu import LiteLLMExtractor
from experiments.analysis.extractor_prompt_v2.scripts.smoketest_extractor_v2 import (
    session_memory_from_devset, session_memory_to_conv_with_labels, build_label_lookup,
    state_positive_tags, state_named_entities, overlap_tokens,
)

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--model", default="openrouter/google/gemma-4-26b-a4b-it")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="experiments/analysis/extractor_prompt_v2/artifacts/v3_final/sync_validation.json")
    a = ap.parse_args()

    import random
    cohort = [json.loads(l) for l in open(
        "experiments/analysis/extractor_prompt_v2/artifacts/cohort_missed_literal_tags.jsonl")]
    random.Random(a.seed).shuffle(cohort)
    cohort = cohort[:a.n]

    print(f"[load] devset + labels ...", flush=True)
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    sess = {r["session_id"]: r["conversations"] for r in ds}
    labels = build_label_lookup()

    ext = LiteLLMExtractor(model_name=a.model, prompt_version="v3", max_tokens=4000, timeout_s=90)

    rows = []
    n_none = 0
    n_era_present = 0
    for i, r in enumerate(cohort, 1):
        sid, tn = r["session_id"], r["turn_number"]
        sm = session_memory_from_devset(sess.get(sid, []), tn)
        conv, played = session_memory_to_conv_with_labels(sm, labels)
        t0 = time.time()
        st = ext.extract(conv, played)
        dt = time.time() - t0
        if st is None:
            n_none += 1
            print(f"  {i}/{a.n} {sid[:8]} t{tn} None ({dt:.1f}s)", flush=True)
            continue
        tags = state_positive_tags(st)
        gt = overlap_tokens(r.get("gt_tags", []))
        emit = overlap_tokens(tags)
        user = overlap_tokens([" ".join(t.get("text", "") for t in conv).lower()])
        hits = emit & gt
        ryr = st.release_year_range.model_dump() if st.release_year_range else None
        if ryr:
            n_era_present += 1
        rows.append({
            "session_id": sid, "turn_number": tn,
            "n_tags": len(tags), "catalog_recall": len(hits) / max(len(gt), 1),
            "n_catalog_hits": len(hits),
            "n_pure_noise": len(emit - user - gt), "n_emit": len(emit),
            "release_year_range": ryr, "latency_s": dt,
        })
        print(f"  {i}/{a.n} {sid[:8]} t{tn} tags={len(tags)} cat_hits={len(hits)} ryr={ryr} ({dt:.1f}s)", flush=True)

    ok = rows
    summ = {
        "model": a.model, "prompt_version": "v3", "n": a.n, "n_none": n_none,
        "mean_catalog_recall": sum(x["catalog_recall"] for x in ok) / max(len(ok), 1),
        "share_with_catalog_hit": sum(1 for x in ok if x["n_catalog_hits"] > 0) / max(len(ok), 1),
        "total_pure_noise": sum(x["n_pure_noise"] for x in ok),
        "total_emit": sum(x["n_emit"] for x in ok),
        "pure_noise_rate": sum(x["n_pure_noise"] for x in ok) / max(sum(x["n_emit"] for x in ok), 1),
        "release_year_range_coverage": n_era_present / max(len(ok), 1),
        "n_with_release_year_range": n_era_present,
        "latency_p50_s": sorted(x["latency_s"] for x in ok)[len(ok)//2] if ok else 0,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"summary": summ, "rows": rows}, indent=2))
    print("\n" + json.dumps(summ, indent=2))


if __name__ == "__main__":
    main()
