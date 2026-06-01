"""Embedding bake-off: Qwen3-Embedding 0.6B vs 4B vs 8B on a SMALL catalog subset.

Two questions in one harness:

A. **Encoder size** — does a bigger metadata encoder (4B / 8B) retrieve better
   than the 0.6B the catalog was built with? We track deep **recall**
   (Recall@100 / Recall@1000), the signal the original 0.6B-vs-8B comparison
   (NDCG@20-only) couldn't see.

B. **Tags representation** — for the attributes/tags branch (which *hurt* in the
   v0+ ablation), does rewriting the catalog document from the raw tag-dump
   template into **natural language** help? The clean comparison is
   `attributes_raw` vs `attributes_nl` (same tag info, different formatting).

Design: subset pool, no new collection
--------------------------------------
We do NOT re-embed the full 47k catalog or build a new LanceDB collection.
We build one candidate pool = (all ground-truth tracks for the sampled turns) +
(random negatives), and every (model × document-variant) ranks within the *same*
pool against the *same* raw-conversation queries. Absolute recall is inflated vs
the full catalog, but the **relative** ordering across models / variants / query
modes is a fair apples-to-apples comparison.

Document variants (how each catalog track is rendered before encoding)
----------------------------------------------------------------------
- `metadata`        : canonical title/artist/album template (reference branch).
- `attributes_raw`  : existing `talkplay_attributes_document_template` tag-dump,
                      e.g. "music attributes, tags :rock,melancholic,90s".
- `attributes_nl`   : natural-language rewrite of the same tags,
                      e.g. "This is a rock, melancholic and 90s track."

Query modes
-----------
- `symmetric` : no instruct prefix (matches how the catalog was built / queried).
- `instruct`  : Qwen3 asymmetric instruct prefix on the query side.

Run
---
    # smoke (fast)
    modal run modal/embedding_bakeoff.py --num-sessions 10 --pool-size 2000

    # fuller
    modal run modal/embedding_bakeoff.py --num-sessions 150 --pool-size 8000

    # focus the tags question only
    modal run modal/embedding_bakeoff.py --doc-variants attributes_raw,attributes_nl --models 0.6B,8B

Results are printed and written to `exp/analysis/embedding_bakeoff/<run>.json`.

NOTE: cannot run from the Claude-Code-on-the-web container (Modal/HF egress
blocked, no GPU). Run from a machine with Modal configured + HF access, exactly
like the other `modal/` scripts. See modal/EMBEDDING_BAKEOFF_HANDOFF.md.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import modal
from omegaconf import OmegaConf


# ----------------------------------------------------------------------
# Modal app / image / volumes — mirrors modal/app.py conventions
# ----------------------------------------------------------------------
def _config_path() -> Path:
    candidates = [
        Path(__file__).parent / "config.yaml",
        Path.cwd() / "modal" / "config.yaml",
        Path("/app/modal/config.yaml"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Could not find modal/config.yaml")


_cfg = OmegaConf.load(_config_path())
APP_NAME = f"{_cfg.app_name}-embedding-bakeoff"
HF_CACHE_VOLUME = _cfg.volumes.hf_cache
HF_CACHE_DIR = _cfg.container.hf_cache_dir

# 8B in bf16 (~16GB weights) needs a roomy GPU; fall back through a few.
BAKEOFF_GPU = ["H100", "A100-80GB", "A100-40GB", "L40S"]

ENV_SECRET = modal.Secret.from_dotenv(__file__)
hf_cache_vol = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_sync(".")
    .add_local_dir(
        ".",
        "/app",
        copy=True,
        ignore=[".*", "__pycache__", "*.pyc", ".venv", "exp", "cache", "submission*"],
    )
    .env({"PYTHONPATH": "/app"})
)

app = modal.App(APP_NAME)

# Friendly aliases → full HF model ids.
MODEL_ALIASES = {
    "0.6B": "Qwen/Qwen3-Embedding-0.6B",
    "4B": "Qwen/Qwen3-Embedding-4B",
    "8B": "Qwen/Qwen3-Embedding-8B",
}

METADATA_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
DEVSET_DATASET = "talkpl-ai/TalkPlayData-Challenge-Dataset"
DEVSET_SPLIT = "test"

K_VALUES = [1, 5, 10, 20, 50, 100, 200, 500, 1000]

# Max tags to include when rendering attribute documents (avoid runaway length).
MAX_TAGS = 12


def _resolve_model(name: str) -> str:
    return MODEL_ALIASES.get(name.strip(), name.strip())


def _batch_size_for(model_id: str, base_bs: int) -> int:
    """Bigger models get smaller batches so they fit comfortably."""
    if "8B" in model_id:
        return max(2, base_bs // 8)
    if "4B" in model_id:
        return max(4, base_bs // 4)
    return base_bs


# ----------------------------------------------------------------------
# Document-variant renderers: metadata dict -> text (or "" to skip)
# ----------------------------------------------------------------------
def _tags_of(meta: dict) -> list[str]:
    tags = meta.get("tag_list") or []
    if not isinstance(tags, list):
        tags = [tags]
    return [str(t) for t in tags if t][:MAX_TAGS]


def _render_metadata(meta: dict) -> str:
    from mcrs.embeddings.qwen3_embedding import talkplay_metadata_document_template

    return talkplay_metadata_document_template(meta)


def _render_attributes_raw(meta: dict) -> str:
    """Existing tag-dump template, fed from tag_list (tempo/key/chord aren't in
    the published metadata, so this is the tags-only form of the upstream doc)."""
    from mcrs.embeddings.qwen3_embedding import talkplay_attributes_document_template

    return talkplay_attributes_document_template({"tags": _tags_of(meta)})


def _render_attributes_nl(meta: dict) -> str:
    """Natural-language rewrite of the same tags — the hypothesis is that this
    lands closer to conversational queries than the raw tag-dump."""
    tags = _tags_of(meta)
    if not tags:
        return ""
    if len(tags) == 1:
        return f"This is a {tags[0]} track."
    return f"This is a {', '.join(tags[:-1])} and {tags[-1]} track."


DOC_VARIANTS = {
    "metadata": _render_metadata,
    "attributes_raw": _render_attributes_raw,
    "attributes_nl": _render_attributes_nl,
}


# ----------------------------------------------------------------------
# Pure helpers (data shaping) — importable/testable without a GPU
# ----------------------------------------------------------------------
def _build_query_text(conversations, target_turn: int, catalog) -> str:
    """Raw-conversation query: prior turns (track_ids rendered as labels) plus
    the current turn's user message, in chronological order. Mirrors
    `mcrs/inference_utils.chat_history_parser`. The gold track never appears."""
    lines: list[str] = []
    for turn in conversations:
        if turn.get("turn_number", 0) >= target_turn:
            continue
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role == "music":
            content = catalog.track_label(str(content)) or str(content)
        if content:
            lines.append(f"{role}: {content}")
    for turn in conversations:
        if turn.get("turn_number") == target_turn and turn.get("role") == "user":
            lines.append(f"user: {turn.get('content', '')}")
            break
    return "\n".join(lines)


def _extract_examples(devset, catalog, num_sessions: int, max_turns: int, seed: int):
    """-> list of {session_id, turn_number, query, gold}. Only turns whose
    ground-truth track exists in the catalog are kept."""
    import random

    rng = random.Random(seed)
    indices = list(range(len(devset)))
    rng.shuffle(indices)
    indices = indices[:num_sessions]

    examples = []
    for idx in indices:
        item = devset[idx]
        convs = item["conversations"]
        for target_turn in range(1, max_turns + 1):
            gold = None
            for turn in convs:
                if turn.get("turn_number") == target_turn and turn.get("role") == "music":
                    gold = str(turn.get("content") or "")
                    break
            if not gold or gold not in catalog.metadata:
                continue
            query = _build_query_text(convs, target_turn, catalog)
            if not query.strip():
                continue
            examples.append(
                {
                    "session_id": item.get("session_id"),
                    "turn_number": target_turn,
                    "query": query,
                    "gold": gold,
                }
            )
    return examples


def _build_pool(examples, catalog, pool_size: int, seed: int) -> list[str]:
    """Pool = all gold tracks + random negatives, deduped & shuffled."""
    import random

    rng = random.Random(seed + 1)
    gold_ids = {ex["gold"] for ex in examples}
    all_ids = catalog.all_track_ids()
    negatives_needed = max(0, pool_size - len(gold_ids))
    negative_candidates = [t for t in all_ids if t not in gold_ids]
    rng.shuffle(negative_candidates)
    pool = list(gold_ids) + negative_candidates[:negatives_needed]
    rng.shuffle(pool)
    return pool


def _render_pool(pool_ids, catalog, variant: str):
    """Render every pool track with the given document variant.
    Returns (doc_texts, coverage_fraction)."""
    render = DOC_VARIANTS[variant]
    docs = [render(catalog.metadata[tid]) for tid in pool_ids]
    nonempty = sum(1 for d in docs if d)
    coverage = nonempty / len(docs) if docs else 0.0
    return docs, coverage


def _score(examples, pool_ids, query_vecs, doc_vecs):
    """Cosine (= dot, vecs are L2-normalized) → ranked preds → mean metrics.
    Returns (overall_means, per_turn_ndcg20)."""
    import numpy as np
    from collections import defaultdict
    from evaluator.metrics.metrics_recsys import compute_metrics

    max_k = min(max(K_VALUES), len(pool_ids))
    k_values = [k for k in K_VALUES if k <= len(pool_ids)]

    sums: dict[str, float] = defaultdict(float)
    per_turn_n: dict[int, list] = defaultdict(list)
    n = len(examples)

    sims = query_vecs @ doc_vecs.T  # (N, P)
    for i, ex in enumerate(examples):
        order = np.argpartition(-sims[i], max_k - 1)[:max_k]
        order = order[np.argsort(-sims[i][order])]
        preds = [pool_ids[j] for j in order]
        m = compute_metrics(preds, [ex["gold"]], k_values, metrics=["recall", "ndcg", "hit"])
        for key, val in m.items():
            sums[key] += val
        per_turn_n[ex["turn_number"]].append(m.get("ndcg@20", 0.0))

    overall = {key: (sums[key] / n if n else 0.0) for key in sums}
    per_turn = {t: (sum(v) / len(v) if v else 0.0) for t, v in sorted(per_turn_n.items())}
    return overall, per_turn


# ----------------------------------------------------------------------
# GPU entrypoint
# ----------------------------------------------------------------------
@app.function(
    image=image,
    gpu=BAKEOFF_GPU,
    volumes={HF_CACHE_DIR: hf_cache_vol},
    secrets=[ENV_SECRET],
    timeout=5400,
    cpu=4.0,
    memory=32768,
)
def run_bakeoff(
    models: list[str],
    doc_variants: list[str],
    query_modes: list[str],
    num_sessions: int,
    pool_size: int,
    max_turns: int,
    base_batch_size: int,
    max_length: int,
    seed: int,
) -> dict:
    import os

    os.environ.setdefault("HF_HOME", HF_CACHE_DIR)

    import numpy as np
    import torch
    from datasets import load_dataset

    from mcrs.embeddings.qwen3_embedding import (
        Qwen3EmbeddingClient,
        DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS,
    )
    from mcrs.qu_modules.v0plus_catalog_hf import HFTalkPlayCatalog

    print(f"[bakeoff] loading metadata catalog from {METADATA_DATASET} ...")
    meta_ds = load_dataset(METADATA_DATASET, split="all_tracks")
    catalog = HFTalkPlayCatalog.from_rows(meta_ds)  # metadata only; we encode ourselves
    print(f"[bakeoff] catalog tracks: {len(catalog.metadata)}")

    print(f"[bakeoff] loading devset {DEVSET_DATASET}:{DEVSET_SPLIT} ...")
    devset = load_dataset(DEVSET_DATASET, split=DEVSET_SPLIT)

    examples = _extract_examples(devset, catalog, num_sessions, max_turns, seed)
    print(f"[bakeoff] scoring examples (turns): {len(examples)}")
    if not examples:
        raise RuntimeError("No scorable examples — check sampling parameters.")

    pool_ids = _build_pool(examples, catalog, pool_size, seed)
    num_gold = len({e["gold"] for e in examples})
    print(f"[bakeoff] candidate pool size: {len(pool_ids)} (gold={num_gold})")

    # Pre-render each document variant once (cheap, CPU-only).
    docs_by_variant: dict[str, list[str]] = {}
    coverage: dict[str, float] = {}
    for variant in doc_variants:
        docs, cov = _render_pool(pool_ids, catalog, variant)
        docs_by_variant[variant] = docs
        coverage[variant] = cov
        print(f"[bakeoff] variant '{variant}' doc coverage: {cov:.1%} non-empty")

    query_texts = [ex["query"] for ex in examples]
    instruct_map = {"symmetric": "", "instruct": DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS}

    results: dict = {
        "config": {
            "models": models,
            "doc_variants": doc_variants,
            "query_modes": query_modes,
            "num_sessions": num_sessions,
            "num_examples": len(examples),
            "pool_size": len(pool_ids),
            "num_gold": num_gold,
            "max_turns": max_turns,
            "max_length": max_length,
            "seed": seed,
            "metadata_dataset": METADATA_DATASET,
            "devset": f"{DEVSET_DATASET}:{DEVSET_SPLIT}",
        },
        "coverage": coverage,
        "runs": {},
        "per_turn_ndcg20": {},
    }

    for alias in models:
        model_id = _resolve_model(alias)
        bs = _batch_size_for(model_id, base_batch_size)
        print(f"\n[bakeoff] ===== {alias} ({model_id}) | batch_size={bs} =====")
        t0 = time.time()
        client = Qwen3EmbeddingClient(
            model_name=model_id,
            device="cuda",
            torch_dtype_name="bfloat16",
            max_length=max_length,
            batch_size=bs,
            query_instruct="",
        )

        # Encode queries once per mode (shared across all document variants).
        q_by_mode = {}
        for mode in query_modes:
            client.query_instruct = instruct_map[mode]
            q_by_mode[mode] = np.asarray(client.embed_batch(query_texts), dtype=np.float32)
        client.query_instruct = ""  # docs are always encoded without instruct
        print(f"[bakeoff]   queries encoded ({len(query_texts)}) in {time.time()-t0:.1f}s")

        for variant in doc_variants:
            doc_vecs = np.asarray(
                client.embed_batch(docs_by_variant[variant]), dtype=np.float32
            )
            for mode in query_modes:
                overall, per_turn = _score(examples, pool_ids, q_by_mode[mode], doc_vecs)
                key = f"{alias}::{variant}::{mode}"
                results["runs"][key] = overall
                results["per_turn_ndcg20"][key] = per_turn
                print(f"[bakeoff]   [{variant} | {mode}] "
                      f"ndcg@20={overall.get('ndcg@20', 0):.4f} "
                      f"recall@100={overall.get('recall@100', 0):.4f} "
                      f"recall@1000={overall.get('recall@1000', 0):.4f} "
                      f"hit@20={overall.get('hit@20', 0):.4f}")
            del doc_vecs

        del client._model
        del client
        torch.cuda.empty_cache()

    return results


def _print_table(results: dict) -> None:
    cfg = results["config"]
    print("\n" + "=" * 96)
    print("EMBEDDING BAKE-OFF — encoder size  ×  document variant  ×  query mode (subset)")
    print("=" * 96)
    print(f"examples(turns)={cfg['num_examples']}  pool={cfg['pool_size']}  "
          f"gold={cfg['num_gold']}  sessions={cfg['num_sessions']}  "
          f"max_len={cfg['max_length']}  seed={cfg['seed']}")
    cov = results.get("coverage", {})
    if cov:
        print("doc coverage: " + "  ".join(f"{v}={cov[v]:.0%}" for v in cov))
    print("(recall is over the subset pool — relative comparison only)\n")
    cols = ["ndcg@20", "recall@20", "recall@100", "recall@1000", "hit@20", "hit@100"]
    header = f"{'model::variant::mode':<34}" + "".join(f"{c:>13}" for c in cols)
    print(header)
    print("-" * len(header))
    for name, m in results["runs"].items():
        row = f"{name:<34}" + "".join(f"{m.get(c, 0.0):>13.4f}" for c in cols)
        print(row)
    print("=" * 96)


@app.local_entrypoint()
def main(
    models: str = "0.6B,4B,8B",
    doc_variants: str = "metadata,attributes_raw,attributes_nl",
    query_modes: str = "symmetric,instruct",
    num_sessions: int = 100,
    pool_size: int = 5000,
    max_turns: int = 8,
    batch_size: int = 32,
    max_length: int = 512,
    seed: int = 0,
):
    model_list = [m for m in models.split(",") if m.strip()]
    variant_list = [v.strip() for v in doc_variants.split(",") if v.strip() in DOC_VARIANTS]
    if not variant_list:
        raise ValueError(f"doc_variants must be a subset of {sorted(DOC_VARIANTS)}")
    mode_list = [m.strip() for m in query_modes.split(",") if m.strip() in ("symmetric", "instruct")]
    if not mode_list:
        raise ValueError("query_modes must include 'symmetric' and/or 'instruct'")

    results = run_bakeoff.remote(
        models=model_list,
        doc_variants=variant_list,
        query_modes=mode_list,
        num_sessions=num_sessions,
        pool_size=pool_size,
        max_turns=max_turns,
        base_batch_size=batch_size,
        max_length=max_length,
        seed=seed,
    )

    _print_table(results)

    out_dir = Path("exp/analysis/embedding_bakeoff")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"bakeoff_{stamp}.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote results to {out_path}")
