"""Replay a LightGBM reranker over saved retrieval traces.

This is the staged counterpart to the online LGBM reranker. It consumes a
retrieval trace JSONL, computes the same candidate features with
``compute_turn_features(..., gt=None)``, scores candidates with a model bundle,
and writes normal inference JSON + trace sidecar files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RERANK_DIR = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, RERANK_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mcrs.qu_modules.compiled_state import final_recommendation, ranking_stage  # noqa: E402
from mcrs.qu_modules.lgbm_reranker import CATEGORICALS  # noqa: E402


def model_bundle_paths(model_ref: str | Path) -> dict[str, Path]:
    base = Path(model_ref)
    if base.is_dir():
        return {
            "model": base / "model.txt",
            "meta": base / "meta.json",
            "cat_maps": base / "cat_maps.json",
            "branch_names": base / "branch_names.json",
        }
    raise ValueError(f"model_ref must be a model bundle directory, got {model_ref!r}")


def _candidate_stage(trace: dict[str, Any]) -> dict[str, Any] | None:
    ranking = trace.get("ranking") or {}
    stages = ranking.get("stages") or []
    for stage in stages:
        if isinstance(stage, dict) and stage.get("name") == "candidate_fusion":
            return stage
    return stages[0] if stages and isinstance(stages[0], dict) else None


def fallback_track_ids(trace: dict[str, Any]) -> list[str]:
    final = trace.get("final_recommendation")
    if isinstance(final, dict) and final.get("track_ids"):
        return [str(track_id) for track_id in final["track_ids"]]

    stage = _candidate_stage(trace)
    if isinstance(stage, dict) and stage.get("track_ids"):
        return [str(track_id) for track_id in stage["track_ids"]]

    branches = trace.get("branches") or {}
    fused = branches.get("fused") or []
    return [str(track_id) for track_id, _score in fused]


def hard_drop_ids(trace: dict[str, Any]) -> set[str]:
    resolver = trace.get("resolver") or {}
    return {str(track_id) for track_id in resolver.get("rejected_track_ids") or []}


def add_constraint_features(rows: list[dict[str, Any]], trace: dict[str, Any]) -> None:
    resolver = trace.get("resolver") or {}
    played = {str(track_id) for track_id in resolver.get("played_track_ids") or []}
    rejected_tracks = {str(track_id) for track_id in resolver.get("rejected_track_ids") or []}
    rejected_artists = {str(artist_id) for artist_id in resolver.get("rejected_artist_ids") or []}

    for row in rows:
        track_id = str(row["track_id"])
        artists = row.get("_artists") or ()
        row["is_played_track"] = float(track_id in played)
        row["rejected_track_exact"] = float(track_id in rejected_tracks)
        row["rejected_artist_exact"] = float(
            bool(rejected_artists) and any(str(artist) in rejected_artists for artist in artists)
        )
        mode = str(row.get("target_artist_mode") or "")
        row["violates_new_artist"] = float(
            ("new" in mode or "different" in mode)
            and float(row.get("same_artist_session") or 0.0) > 0
        )


def assemble_matrix(rows: list[dict[str, Any]], cols: list[str], cat_maps: dict[str, dict]) -> np.ndarray:
    x = np.empty((len(rows), len(cols)), dtype=np.float32)
    for j, col in enumerate(cols):
        if col in CATEGORICALS:
            mapping = cat_maps[col]
            x[:, j] = [float(mapping.get(str(row.get(col, "")), -1)) for row in rows]
        else:
            values = []
            for row in rows:
                value = row.get(col)
                if value is None or value != value:
                    values.append(np.nan)
                else:
                    values.append(float(value))
            x[:, j] = values
    return x


def update_trace_for_rerank(
    trace: dict[str, Any],
    ranked_track_ids: list[str],
    *,
    model_version: str,
) -> dict[str, Any]:
    trace = dict(trace)
    ranking = dict(trace.get("ranking") or {})
    stages = list(ranking.get("stages") or [])
    stages = [
        stage for stage in stages
        if not (isinstance(stage, dict) and stage.get("name") == model_version)
    ]
    stages.append(
        ranking_stage(model_version, ranked_track_ids, method="lightgbm_lambdamart")
    )
    ranking["stages"] = stages
    ranking["final_stage"] = model_version
    trace["ranking"] = ranking
    trace["final_recommendation"] = final_recommendation(
        ranked_track_ids,
        source_stage=model_version,
        ranking_mode="lgbm",
    )
    return trace


def run(args: argparse.Namespace) -> None:
    import lightgbm as lgb

    from build_features import (  # noqa: WPS433
        Catalog,
        EmbedMemo,
        NpzEmbedStore,
        load_sessions,
        load_user_cf,
    )
    from features_v9 import TurnContext, compute_turn_features  # noqa: WPS433
    from mcrs.qu_modules.tag_resolver import TagEmbeddingIndex, TieredTagResolver  # noqa: WPS433

    paths = model_bundle_paths(args.model_ref)
    booster = lgb.Booster(model_file=str(paths["model"]))
    meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
    cols = list(meta["cols"])
    cat_maps = json.loads(paths["cat_maps"].read_text(encoding="utf-8"))
    branch_names = json.loads(paths["branch_names"].read_text(encoding="utf-8"))
    if booster.num_feature() != len(cols):
        raise ValueError(
            f"model expects {booster.num_feature()} features, meta has {len(cols)}"
        )

    print("loading replay context ...", flush=True)
    catalog = Catalog(args.db_uri, args.table_name)
    sessions = load_sessions(dataset_name=args.dataset_name, split=args.dataset_split)
    user_cf = load_user_cf()
    tag_index = TagEmbeddingIndex.load(args.tag_index)
    tag_vec = {tag: tag_index.matrix[i] for i, tag in enumerate(tag_index.tags)}
    vocab = frozenset(tag_index.tags)
    resolver = TieredTagResolver(catalog_tag_keys=vocab, substring_vocab=vocab)
    memo = EmbedMemo(Path(args.embed_memo))
    msg_store = NpzEmbedStore(args.msg_store)
    ctx = TurnContext(
        catalog,
        sessions,
        user_cf,
        resolver,
        tag_vec,
        memo,
        msg_store,
        branch_names=branch_names,
        pool_k=args.pool_k,
        offline=args.offline,
    )

    out_dir = Path(args.out_exp_dir) / "inference" / args.split
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / f"{args.out_tid}.json"
    trace_path = out_dir / f"{args.out_tid}_trace.jsonl"

    predictions: list[dict[str, Any]] = []
    n_rows = 0
    n_fallback = 0
    with open(args.trace, encoding="utf-8") as source, trace_path.open("w", encoding="utf-8") as sink:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            trace = row.get("trace") or {}
            fallback = fallback_track_ids(trace)
            rows, _playable = compute_turn_features(row, ctx, gt=None)
            for feature_row in rows:
                track_meta = ctx.cat.meta.get(str(feature_row["track_id"]), {})
                feature_row["_artists"] = track_meta.get("artists", ())
            add_constraint_features(rows, trace)
            if rows:
                x = assemble_matrix(rows, cols, cat_maps)
                scores = booster.predict(x)
                order = np.argsort(-scores)
                dropped = hard_drop_ids(trace)
                ranked = [
                    str(rows[i]["track_id"])
                    for i in order
                    if str(rows[i]["track_id"]) not in dropped
                ]
                seen = set(ranked)
                for track_id in fallback:
                    if track_id not in seen and track_id not in dropped:
                        ranked.append(track_id)
                        seen.add(track_id)
                ranked = ranked[: args.top_k_out]
            else:
                ranked = fallback[: args.top_k_out]
                n_fallback += 1

            updated_trace = update_trace_for_rerank(
                trace,
                ranked,
                model_version=args.model_version,
            )
            predictions.append(
                {
                    "session_id": row["session_id"],
                    "user_id": row.get("user_id"),
                    "turn_number": row["turn_number"],
                    "predicted_track_ids": ranked[: args.output_topk],
                    "predicted_response": "",
                }
            )
            sink.write(
                json.dumps(
                    {
                        "session_id": row["session_id"],
                        "user_id": row.get("user_id"),
                        "turn_number": row["turn_number"],
                        "trace": updated_trace,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            n_rows += 1
            if n_rows % 250 == 0:
                print(f"  reranked {n_rows} turns", flush=True)

    pred_path.write_text(json.dumps(predictions, ensure_ascii=False), encoding="utf-8")
    print(
        f"wrote {pred_path} and {trace_path} ({n_rows} turns, fallback={n_fallback})",
        flush=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--out-exp-dir", required=True)
    parser.add_argument("--out-tid", required=True)
    parser.add_argument("--split", default="devset")
    parser.add_argument("--model-ref", required=True)
    parser.add_argument("--model-version", default="lgbm_v10")
    parser.add_argument("--db-uri", default="cache/lancedb")
    parser.add_argument("--table-name", default="music_track_catalog")
    parser.add_argument("--tag-index", default="cache/tag_embedding_index/qwen_0_6b.npz")
    parser.add_argument("--embed-memo", default="exp/analysis/rerank/q06_memo.json")
    parser.add_argument("--msg-store", default="exp/analysis/rerank/raw_msg_store")
    parser.add_argument("--dataset-name", default="talkpl-ai/TalkPlayData-Challenge-Dataset")
    parser.add_argument("--dataset-split", default="test")
    parser.add_argument("--pool-k", type=int, default=500)
    parser.add_argument("--top-k-out", type=int, default=1000)
    parser.add_argument("--output-topk", type=int, default=20)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not fill missing embedding memo entries during replay.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
