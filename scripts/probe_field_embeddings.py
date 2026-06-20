"""Cheap offline probe: which embedding field (or fusion) ranks the ground-truth
track best — WITHOUT re-embedding the 47k catalog.

Motivation
----------
We want to know whether the per-field dense embeddings (metadata / attributes /
lyrics) are individually useful, and whether collapsing them into "one field"
(here approximated by mean-pooling the precomputed per-field vectors) would beat
keeping them separate and fusing with RRF.

Doing that properly over the full catalog would mean re-embedding 47k tracks.
This probe avoids that entirely. For a handful of conversations it only:

  1. embeds the *request* text once per turn (a few short strings), and
  2. reuses the *precomputed* per-field track vectors already in LanceDB for a
     small candidate pool = {ground-truth track} ∪ {a few negatives}.

It then ranks the pool under several strategies and reports how high the
ground-truth lands (MRR / hit@k). This is a *relative* comparison of fields on
a small sample — not a full retrieval benchmark — but it answers the "is one
field better?" question for a few dollars of compute.

What it does NOT do
-------------------
- It does not reproduce the production per-field query strings (the v0+ compiler
  builds a different query per branch). For a controlled field comparison we use
  one request text per turn against every field. That is the fair A/B.
- The "mean_vector" strategy mean-pools the three precomputed vectors. That is a
  cheap *surrogate* for a true single combined-document embedding; mean-pooling
  heterogeneous subspaces is not identical to encoding one combined document.
  Use --rebuild-combined to additionally embed a real combined document for the
  pool only (metadata + tags; lyrics/tempo/key/chord raw text are NOT stored
  locally, so that variant is metadata+tags only).

Usage
-----
    python scripts/probe_field_embeddings.py \
        --db-uri cache/lancedb --table music_track_catalog \
        --dataset talkpl-ai/TalkPlayData-Challenge-Dataset --split test \
        --num-sessions 50 --pool-size 50 --seed 0 --device cpu

Requires the shared local cache (cache/lancedb) and HF access for the dataset.
See CLAUDE.md "Shared local caches".
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict

import numpy as np


# Precomputed per-field track vector columns in the LanceDB catalog.
FIELD_COLUMNS = {
    "metadata": "metadata_qwen3_embedding_0_6b",
    "attributes": "attributes_qwen3_embedding_0_6b",
    "lyrics": "lyrics_qwen3_embedding_0_6b",
}

RRF_K0 = 60


# ----------------------------------------------------------------------
# Conversation parsing
# ----------------------------------------------------------------------
def gt_track_for_turn(conversations, turn_number):
    """Ground-truth track_id recommended at `turn_number`, or None.

    Mirrors evaluator/make_ground_truth.py::parsing_groundtruth: within a turn
    the rows are [user, music, assistant]; the music row's content is the
    recommended track_id.
    """
    rows = [c for c in conversations if c.get("turn_number") == turn_number]
    if len(rows) < 2:
        return None
    music = rows[1].get("content")
    return music or None


def request_text_for_turn(conversations, turn_number):
    """The conversational request leading up to (and including) the user message
    of `turn_number`, excluding music rows (those are track ids, not text)."""
    parts = []
    for c in conversations:
        tn = c.get("turn_number")
        role = c.get("role")
        if role == "music":
            continue
        if tn is None:
            continue
        # All earlier turns, plus the user message of the target turn.
        if tn < turn_number or (tn == turn_number and role == "user"):
            content = (c.get("content") or "").strip()
            if content:
                parts.append(content)
    return "\n".join(parts)


# ----------------------------------------------------------------------
# Scoring helpers
# ----------------------------------------------------------------------
def cosine(query_vec, doc_vec):
    if doc_vec is None:
        return None
    a = np.asarray(query_vec, dtype=np.float32)
    b = np.asarray(doc_vec, dtype=np.float32)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return None
    return float(np.dot(a, b) / (na * nb))


def rank_of(target_id, scored):
    """1-based rank of target_id in a list of (id, score) sorted desc, or None.

    `scored` entries with score None are dropped (field missing for that track).
    """
    ranked = sorted(
        (s for s in scored if s[1] is not None),
        key=lambda x: x[1],
        reverse=True,
    )
    for i, (cid, _) in enumerate(ranked, start=1):
        if cid == target_id:
            return i
    return None


def rrf_rank_of(target_id, per_field_scored):
    """1-based RRF-fused rank of target_id across multiple per-field score lists."""
    rrf = defaultdict(float)
    seen = set()
    for scored in per_field_scored:
        ranked = sorted(
            (s for s in scored if s[1] is not None),
            key=lambda x: x[1],
            reverse=True,
        )
        for rank, (cid, _) in enumerate(ranked, start=1):
            rrf[cid] += 1.0 / (RRF_K0 + rank)
            seen.add(cid)
    if target_id not in seen:
        return None
    fused = sorted(rrf.items(), key=lambda x: x[1], reverse=True)
    for i, (cid, _) in enumerate(fused, start=1):
        if cid == target_id:
            return i
    return None


# ----------------------------------------------------------------------
# Candidate pool
# ----------------------------------------------------------------------
def build_pool(gt_id, all_ids, popular_ids, pool_size, rng):
    """Pool = GT + (pool_size-1) negatives: half popular distractors, half random."""
    negatives = []
    used = {gt_id}
    n_neg = max(pool_size - 1, 0)
    n_popular = n_neg // 2

    for cid in popular_ids:
        if len(negatives) >= n_popular:
            break
        if cid not in used:
            negatives.append(cid)
            used.add(cid)

    pool_random = [c for c in all_ids if c not in used]
    rng.shuffle(pool_random)
    for cid in pool_random:
        if len(negatives) >= n_neg:
            break
        negatives.append(cid)
        used.add(cid)

    pool = [gt_id] + negatives
    rng.shuffle(pool)
    return pool


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db-uri", default="cache/lancedb")
    ap.add_argument("--table", default="music_track_catalog")
    ap.add_argument("--dataset", default="talkpl-ai/TalkPlayData-Challenge-Dataset")
    ap.add_argument("--split", default="test")
    ap.add_argument("--num-sessions", type=int, default=50, help="sessions to sample")
    ap.add_argument("--max-queries", type=int, default=400, help="cap on total (session, turn) queries")
    ap.add_argument("--pool-size", type=int, default=50, help="candidates per query (incl. ground truth)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument(
        "--rebuild-combined",
        action="store_true",
        help="also embed a real combined document (metadata+tags only) for the pool",
    )
    args = ap.parse_args()

    rng = random.Random(args.seed)

    from datasets import load_dataset
    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog
    from mcrs.embeddings.qwen3_embedding import (
        Qwen3EmbeddingClient,
        talkplay_metadata_document_template,
        talkplay_attributes_document_template,
    )

    print(f"Loading catalog {args.db_uri}::{args.table} (eager-loading field vectors)...")
    catalog = LanceDbCatalog(
        db_uri=args.db_uri,
        table_name=args.table,
        eager_vector_fields=tuple(FIELD_COLUMNS.values()),
    )
    rows = catalog.feature_rows()
    all_ids = list(rows.keys())
    popular_ids = sorted(
        all_ids,
        key=lambda t: -float(rows[t].get("popularity") or 0.0),
    )
    print(f"  catalog tracks: {len(all_ids)}")

    encoder = Qwen3EmbeddingClient(device=args.device)

    print(f"Loading dataset {args.dataset}::{args.split}...")
    ds = load_dataset(args.dataset, split=args.split)

    # rank stats per strategy: list of (rank or None)
    strategies = list(FIELD_COLUMNS) + ["rrf_fusion", "mean_vector"]
    if args.rebuild_combined:
        strategies.append("combined_reembed")
    ranks = {s: [] for s in strategies}
    n_queries = 0
    n_skipped_gt = 0

    for item in ds:
        if n_queries >= args.max_queries:
            break
        # bound sessions consumed
        if item is None:
            continue
        conversations = item.get("conversations") or []
        for turn in range(1, 9):
            if n_queries >= args.max_queries:
                break
            gt_id = gt_track_for_turn(conversations, turn)
            if not gt_id or gt_id not in rows:
                continue
            # require GT to have at least the metadata vector
            if catalog.vector(gt_id, FIELD_COLUMNS["metadata"]) is None:
                n_skipped_gt += 1
                continue
            req = request_text_for_turn(conversations, turn)
            if not req.strip():
                continue

            q_vec = encoder.embed_one(req)
            pool = build_pool(gt_id, all_ids, popular_ids, args.pool_size, rng)

            # per-field similarity scoring against precomputed vectors
            per_field_scored = {}
            for fname, col in FIELD_COLUMNS.items():
                scored = [(cid, cosine(q_vec, catalog.vector(cid, col))) for cid in pool]
                per_field_scored[fname] = scored
                ranks[fname].append(rank_of(gt_id, scored))

            ranks["rrf_fusion"].append(
                rrf_rank_of(gt_id, list(per_field_scored.values()))
            )

            # mean-vector surrogate for "one field": L2-normalize each present
            # field vector, average, cosine vs query.
            mean_scored = []
            for cid in pool:
                vecs = []
                for col in FIELD_COLUMNS.values():
                    v = catalog.vector(cid, col)
                    if v is not None:
                        v = np.asarray(v, dtype=np.float32)
                        n = np.linalg.norm(v)
                        if n > 0:
                            vecs.append(v / n)
                if not vecs:
                    mean_scored.append((cid, None))
                else:
                    mean_scored.append((cid, cosine(q_vec, np.mean(vecs, axis=0))))
            ranks["mean_vector"].append(rank_of(gt_id, mean_scored))

            if args.rebuild_combined:
                docs = []
                for cid in pool:
                    row = rows[cid]
                    meta_doc = talkplay_metadata_document_template(row)
                    attr_doc = talkplay_attributes_document_template(
                        {"tags": row.get("tag_list")}
                    )
                    docs.append(" ".join(d for d in (meta_doc, attr_doc) if d))
                doc_vecs = encoder.embed_batch(docs)
                comb_scored = [
                    (cid, cosine(q_vec, dv)) for cid, dv in zip(pool, doc_vecs)
                ]
                ranks["combined_reembed"].append(rank_of(gt_id, comb_scored))

            n_queries += 1
            if n_queries % 25 == 0:
                print(f"  ...{n_queries} queries")

    print(f"\nQueries evaluated: {n_queries}  (GT missing vector skips: {n_skipped_gt})")
    print(f"Pool size: {args.pool_size}\n")
    report(ranks, n_queries)


def report(ranks, n_queries):
    def metrics(rlist):
        found = [r for r in rlist if r is not None]
        n = len(rlist)
        if n == 0:
            return None
        mrr = sum(1.0 / r for r in found) / n
        hit1 = sum(1 for r in found if r <= 1) / n
        hit5 = sum(1 for r in found if r <= 5) / n
        hit10 = sum(1 for r in found if r <= 10) / n
        med = float(np.median(found)) if found else float("nan")
        return mrr, hit1, hit5, hit10, med

    header = f"{'strategy':<18}{'MRR':>8}{'hit@1':>8}{'hit@5':>8}{'hit@10':>8}{'medRank':>9}"
    print(header)
    print("-" * len(header))
    for name, rlist in ranks.items():
        m = metrics(rlist)
        if m is None:
            continue
        mrr, hit1, hit5, hit10, med = m
        print(f"{name:<18}{mrr:>8.3f}{hit1:>8.3f}{hit5:>8.3f}{hit10:>8.3f}{med:>9.1f}")


if __name__ == "__main__":
    main()
