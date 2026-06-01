"""Embedding bake-off: Qwen3-Embedding 0.6B vs 4B vs 8B on a SMALL catalog subset.

Goal
----
Settle empirically whether a *bigger* metadata encoder helps retrieval, while
tracking the metric that the original 0.6B-vs-8B comparison missed: deep
**recall** (Recall@100 / Recall@1000), not just NDCG@20.

Why a subset (and why that's valid)
-----------------------------------
We do NOT re-embed the full 47k catalog or build a new LanceDB collection.
Instead we build a small candidate pool = (all ground-truth tracks for the
sampled turns) + (random negatives), and have every encoder rank within the
*same* pool. Absolute recall numbers are inflated vs the full catalog, but the
*relative* ordering between encoders is a fair apples-to-apples comparison
because the pool, the document template, the query text, and the scoring are
identical across models.

What it does
------------
1. Loads track metadata + the devset from HF (no precomputed vectors used —
   we re-encode docs ourselves so all three models go through one code path).
2. Builds (query_text, gold_track_id) examples from devset turns.
3. Builds the candidate pool and renders each track via the canonical
   `talkplay_metadata_document_template`.
4. For each model, encodes docs once and queries in two modes:
     - "symmetric": no instruct prefix (matches how the talkpl-ai catalog was
       built and how the current pipeline queries it).
     - "instruct":  Qwen3 asymmetric instruct prefix on the query side (gives
       the Qwen3 models their "intended" retrieval setup).
5. Scores with the repo's own metrics and prints a side-by-side table.

Run
---
    # smoke (fast): a handful of sessions, small pool
    modal run modal/embedding_bakeoff.py --num-sessions 10 --pool-size 2000

    # fuller comparison
    modal run modal/embedding_bakeoff.py --num-sessions 150 --pool-size 8000

    # restrict models / query modes
    modal run modal/embedding_bakeoff.py --models 0.6B,8B --query-modes symmetric

Results are printed and also written to
`exp/analysis/embedding_bakeoff/<run>.json` locally by the entrypoint.

NOTE: this cannot run from the Claude-Code-on-the-web container (HF + model
downloads are blocked there). Run it from a machine with Modal configured and
HF access, exactly like the other `modal/` scripts.
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
# Pure helpers (data shaping) — importable/testable without a GPU
# ----------------------------------------------------------------------
def _build_query_text(conversations, target_turn: int, catalog) -> str:
    """Raw-conversation query: prior turns (track_ids rendered as labels) plus
    the current turn's user message, in chronological order.

    Mirrors `mcrs/inference_utils.chat_history_parser`: history is every turn
    with turn_number < target; music turns are converted to a metadata label;
    the current user message is appended last.
    """
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
    """-> list of dicts: {session_id, turn_number, query, gold}. Only turns whose
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


def _build_pool(examples, catalog, pool_size: int, seed: int):
    """Pool = all gold tracks + random negatives, deduped & shuffled.
    Returns (pool_ids, doc_texts) aligned by index."""
    import random
    from mcrs.embeddings.qwen3_embedding import talkplay_metadata_document_template

    rng = random.Random(seed + 1)
    gold_ids = {ex["gold"] for ex in examples}
    all_ids = catalog.all_track_ids()
    negatives_needed = max(0, pool_size - len(gold_ids))
    negative_candidates = [t for t in all_ids if t not in gold_ids]
    rng.shuffle(negative_candidates)
    pool = list(gold_ids) + negative_candidates[:negatives_needed]
    rng.shuffle(pool)

    doc_texts = [talkplay_metadata_document_template(catalog.metadata[tid]) for tid in pool]
    return pool, doc_texts


def _score(examples, pool_ids, query_vecs, doc_vecs):
    """Cosine (= dot, vecs are L2-normalized) → ranked preds → mean metrics.
    Returns (overall_means: dict, per_turn_ndcg20: dict)."""
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
    timeout=3600,
    cpu=4.0,
    memory=32768,
)
def run_bakeoff(
    models: list[str],
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

    pool_ids, doc_texts = _build_pool(examples, catalog, pool_size, seed)
    print(f"[bakeoff] candidate pool size: {len(pool_ids)} "
          f"(gold={len({e['gold'] for e in examples})})")

    query_texts = [ex["query"] for ex in examples]
    instruct_map = {
        "symmetric": "",
        "instruct": DEFAULT_QUERY_INSTRUCT_FOR_MUSIC_CRS,
    }

    results: dict = {
        "config": {
            "models": models,
            "query_modes": query_modes,
            "num_sessions": num_sessions,
            "num_examples": len(examples),
            "pool_size": len(pool_ids),
            "num_gold": len({e["gold"] for e in examples}),
            "max_turns": max_turns,
            "max_length": max_length,
            "seed": seed,
            "metadata_dataset": METADATA_DATASET,
            "devset": f"{DEVSET_DATASET}:{DEVSET_SPLIT}",
        },
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
        # Docs encoded once (symmetric, no instruct) — reused across query modes.
        doc_vecs = np.asarray(client.embed_batch(doc_texts), dtype=np.float32)
        print(f"[bakeoff]   docs encoded {doc_vecs.shape} in {time.time()-t0:.1f}s")

        for mode in query_modes:
            client.query_instruct = instruct_map[mode]
            qv = np.asarray(client.embed_batch(query_texts), dtype=np.float32)
            overall, per_turn = _score(examples, pool_ids, qv, doc_vecs)
            results["runs"][f"{alias}::{mode}"] = overall
            results["per_turn_ndcg20"][f"{alias}::{mode}"] = per_turn
            print(f"[bakeoff]   [{mode}] "
                  f"ndcg@20={overall.get('ndcg@20', 0):.4f} "
                  f"recall@100={overall.get('recall@100', 0):.4f} "
                  f"recall@1000={overall.get('recall@1000', 0):.4f} "
                  f"hit@20={overall.get('hit@20', 0):.4f}")

        # free GPU memory before the next (larger) model
        del client._model
        del client
        torch.cuda.empty_cache()

    return results


def _print_table(results: dict) -> None:
    cfg = results["config"]
    print("\n" + "=" * 84)
    print("EMBEDDING BAKE-OFF — metadata encoder comparison (subset)")
    print("=" * 84)
    print(f"examples(turns)={cfg['num_examples']}  pool={cfg['pool_size']}  "
          f"gold={cfg['num_gold']}  sessions={cfg['num_sessions']}  "
          f"max_len={cfg['max_length']}  seed={cfg['seed']}")
    print("(recall is over the subset pool — relative comparison only)\n")
    cols = ["ndcg@20", "recall@20", "recall@100", "recall@1000", "hit@20", "hit@100"]
    header = f"{'model::mode':<22}" + "".join(f"{c:>13}" for c in cols)
    print(header)
    print("-" * len(header))
    for name, m in results["runs"].items():
        row = f"{name:<22}" + "".join(f"{m.get(c, 0.0):>13.4f}" for c in cols)
        print(row)
    print("=" * 84)


@app.local_entrypoint()
def main(
    models: str = "0.6B,4B,8B",
    query_modes: str = "symmetric,instruct",
    num_sessions: int = 100,
    pool_size: int = 5000,
    max_turns: int = 8,
    batch_size: int = 32,
    max_length: int = 512,
    seed: int = 0,
):
    model_list = [m for m in models.split(",") if m.strip()]
    mode_list = [m.strip() for m in query_modes.split(",") if m.strip() in ("symmetric", "instruct")]
    if not mode_list:
        raise ValueError("query_modes must include 'symmetric' and/or 'instruct'")

    results = run_bakeoff.remote(
        models=model_list,
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
