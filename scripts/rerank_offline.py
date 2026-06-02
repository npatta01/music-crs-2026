"""Offline reranker replay.

Replays a cross-encoder rerank step on top of an existing retrieval run, with
no re-inference required. The rerank is a pure transformation over:
  - saved top-N predictions per turn
  - saved per-turn state (`state.turn_intent`) from the trace file
  - a catalog text representation of each candidate track

This lets us test multiple rerankers cheaply against the SAME retrieval pool —
the only thing that varies between bake-off runs is the model.

Usage:
    python scripts/rerank_offline.py \
        --base-tid v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset \
        --model cross-encoder/ms-marco-MiniLM-L-12-v2 \
        --rerank-top-k 200

Output:
    {exp_dir}/inference/devset/{base_tid}.rerank_{slug}.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.qu_modules.cross_encoder_reranker import CrossEncoderReranker  # noqa: E402

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    """File-system-friendly slug for a model name."""
    s = name.replace("/", "_").replace(":", "_")
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", s)


def load_predictions(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def load_traces(path: Path) -> tuple[dict[tuple[str, int], dict], dict[tuple[str, int], list[str]]]:
    """Return ({(session_id, turn_number): state}, {(session_id, turn_number): played_track_ids}).

    Two parallel dicts:
    - states: the LLM-extracted ConversationState (turn_intent, mentions,
      rejections, process_constraints, etc.)
    - played_by_turn: the played-track history at this turn, sourced from
      `trace.resolver.played_track_ids` (the canonical place; `state.played_track_ids`
      doesn't exist in saved traces).
    """
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    states: dict[tuple[str, int], dict] = {}
    played: dict[tuple[str, int], list[str]] = {}
    for r in rows:
        sid = r.get("session_id")
        tn = r.get("turn_number")
        tr = (r.get("trace") or {})
        state = (tr.get("state") or {})
        resolver = (tr.get("resolver") or {})
        if sid is not None and tn is not None:
            key = (sid, int(tn))
            states[key] = state
            played[key] = [str(p) for p in (resolver.get("played_track_ids") or [])]
    return states, played


def build_history_metadata_dict(max_tags: int = 3) -> dict[str, str]:
    """Compact per-track metadata for the "Just heard" / "Recent" lines in
    a structured query. Returns: track_id -> '"Artist - Track" (year, tag1, tag2, tag3)'.

    Smaller than the doc-side track_text dict (only year + 3 tags vs full
    metadata) because history annotations should be terse — the reranker
    cares about "what vibe was the user in," not full track details.
    """
    from datasets import load_dataset

    logger.info("loading metadata dataset for history-metadata dict...")
    ds = load_dataset(
        "talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks"
    )

    def _first(v):
        if isinstance(v, list):
            return v[0] if v else ""
        return v or ""

    out: dict[str, str] = {}
    for row in ds:
        tid = str(row["track_id"])
        artist = str(_first(row.get("artist_name"))).strip()
        track = str(_first(row.get("track_name"))).strip()
        rd = row.get("release_date")
        year = str(rd)[:4] if rd and str(rd)[:4].isdigit() else ""
        tags = row.get("tag_list") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        tags = [str(x).strip() for x in tags if x][:max_tags]
        if not (artist or track):
            out[tid] = ""
            continue
        meta_str = f'"{artist} - {track}"' if (artist and track) else f'"{track or artist}"'
        bits = []
        if year:
            bits.append(year)
        if tags:
            bits.extend(tags)
        if bits:
            meta_str += f" ({', '.join(bits)})"
        out[tid] = meta_str
    return out


def build_query_structured(
    state: dict,
    history_with_metadata: list[str],
) -> str:
    """Labeled-fields query: turn_intent + JUST HEARD (with year/tags) + RECENT + likes + policy.

    Mirrors `modal/rerank.py:build_query_structured` so DeepInfra runs use
    the SAME prompt content as the (deferred) Modal runs. Newline-separated
    labeled fields — terse, deterministic, easy for the cross-encoder to
    attend to.

    `history_with_metadata` is the list of annotated prior tracks
    (output of `build_history_metadata_dict()` indexed by played_track_ids).
    Empty list = no history (turn 1).
    """
    parts: list[str] = []
    intent = (state.get("turn_intent") or "").strip()
    if intent:
        parts.append(f"Request: {intent}")

    if history_with_metadata:
        parts.append(f"Just heard: {history_with_metadata[-1]}")
        recent = history_with_metadata[-3:]
        if len(recent) > 1:
            parts.append(f'Recent: {"; ".join(recent)}')

    me = state.get("mentioned_entities") or []
    likes = [m.get("value") for m in me if (m.get("sentiment") or 0) > 0 and m.get("value")]
    likes = list(dict.fromkeys(likes))[:6]
    if likes:
        parts.append(f"User likes: {', '.join(likes)}")

    pc = state.get("process_constraints") or {}
    policy = pc.get("exploration_policy") or "balanced"
    if policy == "diversify_artists":
        parts.append("Policy: prefer a different artist from the ones already played.")
    elif policy == "exploit":
        parts.append("Policy: prefer more from the same artist as the recent plays.")
    elif policy == "diversify_albums":
        parts.append("Policy: prefer a different album from the ones already played.")
    return "\n".join(parts)


def build_enriched_query(state: dict) -> str:
    """Legacy free-form enriched query (kept for backwards compatibility).
    See `build_query_structured` for the labeled-field version that mirrors
    the Modal-side prompt.
    """
    parts: list[str] = []
    ti = (state.get("turn_intent") or "").strip()
    if ti:
        parts.append(ti)

    me = state.get("mentioned_entities") or []
    pos = [m.get("value") for m in me if (m.get("sentiment") or 0) > 0 and m.get("value")]
    neg = [m.get("value") for m in me if (m.get("sentiment") or 0) < 0 and m.get("value")]
    rejections = [r.get("value") for r in (state.get("explicit_rejections") or []) if r.get("value")]

    pos = list(dict.fromkeys(pos))[:6]
    avoid = list(dict.fromkeys(neg + rejections))[:6]

    if pos:
        parts.append(f"The user likes {', '.join(pos)}.")
    if avoid:
        parts.append(f"The user does not want {', '.join(avoid)}.")

    pc = state.get("process_constraints") or {}
    policy = pc.get("exploration_policy") or "balanced"
    if policy == "diversify_artists":
        parts.append("The user wants the same style but a different artist.")
    elif policy == "diversify_albums":
        parts.append("The user wants the same artist but a different album.")
    elif policy == "exploit":
        parts.append("The user wants more from the same source.")

    return " ".join(parts)


def build_track_text_dict(max_tags: int = 10) -> dict[str, str]:
    """Build {track_id: text} from the HF metadata dataset.

    Format: `"{artist} - {track} | {album} ({year}) | tag1, tag2, ..."`.
    Year and extra tags give the cross-encoder more signal than just
    artist/track. Local LanceDB isn't required.
    """
    from datasets import load_dataset

    logger.info("loading metadata dataset for track_text dict...")
    ds = load_dataset(
        "talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks"
    )

    def _first(v):
        if isinstance(v, list):
            return v[0] if v else ""
        return v or ""

    def _year_of(release_date):
        if not release_date:
            return ""
        s = str(release_date)
        return s[:4] if len(s) >= 4 and s[:4].isdigit() else ""

    out: dict[str, str] = {}
    for row in ds:
        tid = str(row["track_id"])
        artist = str(_first(row.get("artist_name"))).strip()
        track = str(_first(row.get("track_name"))).strip()
        album = str(_first(row.get("album_name"))).strip()
        year = _year_of(row.get("release_date"))
        tags = row.get("tag_list") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        tags = [str(t).strip() for t in tags if t][:max_tags]

        parts: list[str] = []
        if artist and track:
            parts.append(f"{artist} - {track}")
        elif track:
            parts.append(track)
        elif artist:
            parts.append(artist)
        else:
            out[tid] = ""
            continue
        # Add album + year, prefer "Album (Year)" form if both present
        album_part = ""
        if album and album not in parts[0]:
            album_part = album
        if year:
            album_part = f"{album_part} ({year})" if album_part else year
        if album_part:
            parts.append(album_part)
        if tags:
            parts.append(", ".join(tags))
        out[tid] = " | ".join(parts)
    logger.info("track_text dict built: %d tracks", len(out))
    return out


class DictCatalog:
    """Thin wrapper around a {track_id: text} dict implementing the
    `CatalogTextProtocol`. Used by the offline reranker."""

    def __init__(self, texts: dict[str, str]):
        self._texts = texts

    def track_text(self, track_id: str) -> str:
        return self._texts.get(track_id, "")


class _State:
    """Tiny stand-in for ResolvedConversationState's turn_intent attribute."""

    def __init__(self, turn_intent: str):
        self.turn_intent = turn_intent


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Replay a cross-encoder rerank on saved retrieval predictions.")
    p.add_argument("--base-tid", required=True, help="Existing tid whose predictions/trace to rerank.")
    p.add_argument("--model", required=True, help="Reranker model name (HF id).")
    p.add_argument("--rerank-top-k", type=int, default=200, help="How many head candidates to rerank.")
    p.add_argument("--batch-size", type=int, default=32, help="Reranker batch size.")
    p.add_argument("--device", default=None, help="cpu / cuda / mps (auto-detect if omitted).")
    p.add_argument("--backend", default=None, help="Force backend: st / flag / qwen3 (default: auto from model name).")
    p.add_argument("--exp-dir", default="evaluator/exp", help="Root containing inference/devset/...")
    p.add_argument("--num-sessions", type=int, default=0, help="Smoke-test cap; 0 = full run.")
    p.add_argument("--out-tid", default=None, help="Override output tid. Default: {base_tid}.rerank_{slug}.")
    p.add_argument(
        "--no-enrich",
        action="store_true",
        help="DEPRECATED: alias for --query-template basic. Use only turn_intent as query.",
    )
    p.add_argument(
        "--query-template",
        choices=["basic", "enriched", "structured"],
        default="structured",
        help=(
            "Query format. "
            "'basic': just turn_intent. "
            "'enriched': legacy free-form (turn_intent + 'The user likes ...' sentences). "
            "'structured': labeled fields with annotated 'Just heard'/'Recent' history + likes + policy "
            "(mirrors modal/rerank.py). Default: structured."
        ),
    )
    p.add_argument(
        "--fusion",
        choices=["replace", "rrf"],
        default="replace",
        help="How to combine reranker score with RRF rank. 'replace' = xenc score wins, 'rrf' = RRF rank fusion of RRF + xenc ranks.",
    )
    p.add_argument("--fusion-xenc-weight", type=float, default=1.0, help="Weight on xenc-rank term in fusion=rrf.")
    p.add_argument("--fusion-rrf-weight", type=float, default=1.0, help="Weight on RRF-rank term in fusion=rrf.")
    p.add_argument("--fusion-k", type=int, default=60, help="RRF dampening constant in fusion=rrf.")
    p.add_argument("--max-in-flight", type=int, default=1, help="Concurrent HTTP requests WITHIN a single turn (per-batch, HTTP backends only). Default 1.")
    p.add_argument("--turn-workers", type=int, default=8, help="Concurrent TURNS being reranked (thread pool). Only honored for HTTP-thread-safe backends (DeepInfra). Default 8.")
    args = p.parse_args()

    exp_dir = Path(args.exp_dir)
    base_pred_path = exp_dir / "inference" / "devset" / f"{args.base_tid}.json"
    base_trace_path = exp_dir / "inference" / "devset" / f"{args.base_tid}_trace.jsonl"
    if not base_pred_path.exists():
        raise SystemExit(f"predictions not found: {base_pred_path}")
    if not base_trace_path.exists():
        raise SystemExit(f"trace not found: {base_trace_path}")

    # `--no-enrich` is the deprecated alias — preserve its behavior.
    template = "basic" if args.no_enrich else args.query_template
    weight_suffix = ""
    if args.fusion == "rrf" and (args.fusion_xenc_weight != 1.0 or args.fusion_rrf_weight != 1.0):
        weight_suffix = f"_w{args.fusion_xenc_weight}-{args.fusion_rrf_weight}"
    out_tid = args.out_tid or f"{args.base_tid}.rerank_{slugify(args.model)}_{template}_{args.fusion}{weight_suffix}"
    out_path = exp_dir / "inference" / "devset" / f"{out_tid}.json"

    logger.info("loading predictions from %s", base_pred_path)
    preds = load_predictions(base_pred_path)
    logger.info("loaded %d turn predictions", len(preds))

    logger.info("loading traces from %s", base_trace_path)
    states, played_by_turn = load_traces(base_trace_path)
    logger.info("loaded %d turn states", len(states))

    text_dict = build_track_text_dict()
    catalog = DictCatalog(text_dict)

    # Only build history-metadata when needed (structured template).
    history_meta: dict[str, str] = {}
    if template == "structured":
        history_meta = build_history_metadata_dict()
        logger.info("history-metadata dict built: %d tracks", len(history_meta))

    reranker = CrossEncoderReranker(
        model_name=args.model,
        rerank_top_k=args.rerank_top_k,
        batch_size=args.batch_size,
        device=args.device,
        backend_name=args.backend,
        fusion=args.fusion,
        fusion_xenc_weight=args.fusion_xenc_weight,
        fusion_rrf_weight=args.fusion_rrf_weight,
        fusion_k=args.fusion_k,
        max_in_flight=args.max_in_flight,
    )

    rows_to_rerank = preds[: args.num_sessions * 8] if args.num_sessions > 0 else preds
    logger.info(
        "reranking %d turns with %s (rerank_top_k=%d, batch_size=%d)",
        len(rows_to_rerank), args.model, args.rerank_top_k, args.batch_size,
    )

    n_no_intent = 0
    n_empty_pool = 0
    t0 = time.time()

    # Build per-turn work units first (cheap, no I/O), then process in parallel.
    work: list[tuple[int, dict, str, list[str]]] = []  # (idx, row, query, pred_ids)
    for i, row in enumerate(rows_to_rerank):
        sid = row.get("session_id")
        tn = row.get("turn_number")
        pred_ids = row.get("predicted_track_ids") or []
        st = states.get((sid, int(tn))) if tn is not None else {}
        if not st:
            st = {}
        if template == "basic":
            query = (st.get("turn_intent") or "").strip()
        elif template == "enriched":
            query = build_enriched_query(st).strip()
        else:  # structured
            played = played_by_turn.get((sid, int(tn)), []) if tn is not None else []
            history_with_meta = [history_meta.get(p, p) for p in played]
            query = build_query_structured(st, history_with_meta).strip()
        if not query:
            n_no_intent += 1
        if not pred_ids:
            n_empty_pool += 1
        work.append((i, row, query, pred_ids))

    # Log a sample query for sanity
    for _, _, q, _ in work:
        if q:
            logger.info("sample query: %r", q[:280])
            break

    # Turn-level parallelism: each thread processes one turn via
    # reranker.rerank() which itself can fan out HTTP calls per-batch
    # (max_in_flight). The reranker instance is THREAD-SAFE for the
    # DeepInfra backend (each .rerank() call only reads instance state).
    # For other backends (sentence-transformers HF) this would NOT be safe
    # because the underlying model isn't reentrant; we gate accordingly.
    is_http_backend = (args.backend == "deepinfra") or (
        args.backend is None and "Reranker" in args.model and "Qwen" in args.model
    )
    turn_workers = args.turn_workers if is_http_backend else 1
    if turn_workers > 1:
        logger.info("turn-level parallelism: %d concurrent turns", turn_workers)
    else:
        logger.info("turn-level parallelism disabled (backend=%s is not HTTP / not thread-safe)", args.backend)

    def process_turn(item):
        idx, row, query, pred_ids = item
        if not query or not pred_ids:
            return idx, {**row}  # passthrough — no rerank possible
        fused = [(tid, 1.0 / (r + 1)) for r, tid in enumerate(pred_ids)]
        state = _State(turn_intent=query)
        try:
            reranked = reranker.rerank(fused, state, catalog)
        except Exception as e:
            logger.warning("turn %d (sid=%s, tn=%s) failed: %s", idx, row.get("session_id"), row.get("turn_number"), e)
            return idx, {**row}  # passthrough on error
        new_pred_ids = [tid for tid, _ in reranked]
        return idx, {**row, "predicted_track_ids": new_pred_ids}

    out_by_idx: dict[int, dict] = {}
    if turn_workers > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=turn_workers) as pool:
            futures = {pool.submit(process_turn, item): item[0] for item in work}
            for n_done, f in enumerate(as_completed(futures), start=1):
                idx, new_row = f.result()
                out_by_idx[idx] = new_row
                if n_done % 50 == 0 or n_done == len(work):
                    elapsed = time.time() - t0
                    rate = n_done / elapsed if elapsed > 0 else 0
                    logger.info("  %d/%d turns reranked (%.1f turns/sec)", n_done, len(work), rate)
    else:
        for item in work:
            idx, new_row = process_turn(item)
            out_by_idx[idx] = new_row
            if (idx + 1) % 50 == 0:
                elapsed = time.time() - t0
                rate = (idx + 1) / elapsed if elapsed > 0 else 0
                logger.info("  %d/%d turns reranked (%.1f turns/sec)", idx + 1, len(work), rate)

    # Reassemble in original order
    out_rows: list[dict] = [out_by_idx[i] for i in range(len(work))]

    elapsed = time.time() - t0
    logger.info(
        "done: %d turns reranked in %.1fs (%.2f turns/sec). no_intent=%d, empty_pool=%d",
        len(out_rows), elapsed, len(out_rows) / max(elapsed, 1e-9), n_no_intent, n_empty_pool,
    )

    # Carry forward any rows that weren't reranked (when --num-sessions caps)
    if args.num_sessions > 0 and len(rows_to_rerank) < len(preds):
        out_rows.extend(preds[len(rows_to_rerank):])
        logger.info("appended %d non-reranked rows for full-output preservation", len(preds) - len(rows_to_rerank))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_rows))
    logger.info("wrote %s (%d rows)", out_path, len(out_rows))


if __name__ == "__main__":
    main()
