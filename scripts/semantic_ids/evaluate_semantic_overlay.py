from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class OverlayConfig:
    base: str
    level: int
    seed_topn: int
    seed_weight: float
    anchor_turns: int
    anchor_weight: float


def _split_name(session_id: str) -> str:
    digest = hashlib.sha1(session_id.encode("utf-8")).digest()
    return "tune" if digest[0] < 128 else "test"


def _load_lgbm_oof_scores(train_dir: Path, n_rows: int) -> np.ndarray:
    sid_codes = np.load(train_dir / "sid_codes.npy")
    sid_fold = np.load(train_dir / "sid_fold.npy")
    scores = np.full(n_rows, np.nan, dtype=np.float32)
    lock_scores = np.zeros(n_rows, dtype=np.float64)
    n_folds = 5
    for fold in range(n_folds):
        idx = np.load(train_dir / f"idx_test_fold{fold}.npy")
        scores[idx] = np.load(train_dir / f"scores_test_fold{fold}.npy")
        lock_idx = np.load(train_dir / f"idx_lockbox_fold{fold}.npy")
        lock_scores[lock_idx] += np.load(train_dir / f"scores_lockbox_fold{fold}.npy")
    lock_rows = np.flatnonzero(sid_fold[sid_codes] == -1)
    scores[lock_rows] = (lock_scores[lock_rows] / n_folds).astype(np.float32)
    if np.isnan(scores).any():
        raise ValueError("OOF score reconstruction left NaN rows")
    return scores


def _semantic_arrays(semantic_path: Path, trk_uniq: list[str]) -> dict[int, np.ndarray]:
    semantic = pd.read_parquet(semantic_path)
    by_track = semantic.set_index("track_id")
    levels = sorted(
        int(col.removeprefix("sid_l"))
        for col in semantic.columns
        if col.startswith("sid_l") and not col.endswith("_size")
    )
    arrays: dict[int, np.ndarray] = {}
    parent = np.zeros(len(trk_uniq), dtype=np.int64)
    for level in levels:
        values = by_track.reindex(trk_uniq)[f"sid_l{level}"].fillna(-1).to_numpy(dtype=np.int64)
        max_value = int(values.max()) if len(values) else 0
        if level == 1:
            parent = values.copy()
            arrays[level] = parent.copy()
        else:
            parent = parent * (max_value + 1) + values
            arrays[level] = parent.copy()
    return arrays


def _ground_truth_history(gt_path: Path, sid_uniq: list[str], semantic_by_track: dict[str, tuple[int, int]]) -> dict[tuple[int, int], dict[int, list[int]]]:
    rows = json.loads(gt_path.read_text())
    sid_to_code = {sid: idx for idx, sid in enumerate(sid_uniq)}
    by_session: dict[str, list[dict]] = {}
    for row in rows:
        by_session.setdefault(str(row["session_id"]), []).append(row)

    out: dict[tuple[int, int], dict[int, list[int]]] = {}
    for sid, session_rows in by_session.items():
        if sid not in sid_to_code:
            continue
        prior: list[tuple[int, int]] = []
        for row in sorted(session_rows, key=lambda r: int(r["turn_number"])):
            key = (sid_to_code[sid], int(row["turn_number"]))
            by_level: dict[int, list[int]] = {1: [], 2: []}
            for l1, l2 in reversed(prior):
                by_level[1].append(l1)
                by_level[2].append(l2)
            out[key] = by_level
            code = semantic_by_track.get(str(row["ground_truth_track_id"]))
            if code is not None:
                prior.append(code)
    return out


def _metrics_from_ranks(ranks: list[int], denom: int) -> dict[str, float | int]:
    arr = np.asarray(ranks, dtype=np.int32)
    metrics: dict[str, float | int] = {}
    for k in (1, 5, 10, 20):
        metrics[f"hit@{k}"] = float((arr <= k).sum() / denom) if denom else 0.0
    metrics["ndcg@20"] = float(sum(1.0 / math.log2(int(r) + 1) for r in arr if r <= 20) / denom) if denom else 0.0
    metrics["n_playable"] = int(len(ranks))
    metrics["denom"] = int(denom)
    return metrics


def _branch_rank_array(
    base_ranks: np.ndarray,
    clusters: np.ndarray,
    *,
    seed_topn: int,
    anchor_clusters: list[int],
) -> np.ndarray:
    n = len(base_ranks)
    branch_rank = np.zeros(n, dtype=np.int32)
    best: dict[int, int] = {}
    if seed_topn > 0:
        seed_idx = np.flatnonzero(base_ranks <= seed_topn)
        for idx in seed_idx:
            cluster = int(clusters[idx])
            if cluster < 0:
                continue
            rank = int(base_ranks[idx])
            best[cluster] = min(best.get(cluster, rank), rank)
    for offset, cluster in enumerate(anchor_clusters, start=1):
        if cluster < 0:
            continue
        best[int(cluster)] = min(best.get(int(cluster), 10_000 + offset), 10_000 + offset)
    if not best:
        return branch_rank

    selected = np.isin(clusters, np.fromiter(best.keys(), dtype=np.int64))
    if not selected.any():
        return branch_rank
    selected_idx = np.flatnonzero(selected)
    cluster_priority = np.asarray([best[int(clusters[idx])] for idx in selected_idx], dtype=np.int32)
    order = np.lexsort((base_ranks[selected_idx], cluster_priority))
    branch_rank[selected_idx[order]] = np.arange(1, len(selected_idx) + 1, dtype=np.int32)
    return branch_rank


def _rank_gt(
    *,
    base_ranks: np.ndarray,
    branch_ranks: np.ndarray,
    gt_local_idx: int,
    seed_weight: float,
    anchor_weight: float,
    branch_has_anchor: np.ndarray,
    rrf_k: int,
) -> int:
    base_score = 1.0 / (rrf_k + base_ranks.astype(np.float32))
    branch_score = np.zeros(len(base_ranks), dtype=np.float32)
    has_branch = branch_ranks > 0
    branch_score[has_branch] = 1.0 / (rrf_k + branch_ranks[has_branch].astype(np.float32))
    combined = base_score + float(seed_weight) * branch_score
    if anchor_weight:
        anchor_score = np.zeros(len(base_ranks), dtype=np.float32)
        anchor_score[branch_has_anchor] = 1.0 / (rrf_k + base_ranks[branch_has_anchor].astype(np.float32))
        combined += float(anchor_weight) * anchor_score
    gt_score = float(combined[gt_local_idx])
    return int((combined > gt_score).sum()) + 1


def _evaluate_config(
    cfg: OverlayConfig,
    *,
    groups: list[dict],
    split: str,
    rrf_k: int,
) -> dict[str, float | int]:
    ranks = []
    denom = 0
    for group in groups:
        if split != "all" and group["split"] != split:
            continue
        denom += 1
        gt_local_idx = group["gt_local_idx"]
        if gt_local_idx is None:
            continue
        base_ranks = group[f"{cfg.base}_ranks"]
        clusters = group[f"clusters_l{cfg.level}"]
        anchors = group[f"anchor_l{cfg.level}"][: cfg.anchor_turns]
        branch_ranks = _branch_rank_array(
            base_ranks,
            clusters,
            seed_topn=cfg.seed_topn,
            anchor_clusters=[] if cfg.anchor_weight == 0 else anchors,
        )
        branch_has_anchor = (
            np.isin(clusters, np.asarray(anchors, dtype=np.int64))
            if anchors
            else np.zeros(len(clusters), dtype=bool)
        )
        ranks.append(
            _rank_gt(
                base_ranks=base_ranks,
                branch_ranks=branch_ranks,
                gt_local_idx=gt_local_idx,
                seed_weight=cfg.seed_weight,
                anchor_weight=cfg.anchor_weight,
                branch_has_anchor=branch_has_anchor,
                rrf_k=rrf_k,
            )
        )
    return _metrics_from_ranks(ranks, denom)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate semantic-ID overlay reranking on v10 OOF artifacts.")
    parser.add_argument("--train-dir", default="exp/analysis/rerank/v10/train_local")
    parser.add_argument("--semantic-ids", required=True)
    parser.add_argument("--gt", default="exp/ground_truth/devset.json")
    parser.add_argument("--out", default="exp/analysis/semantic_ids/overlay_eval.json")
    parser.add_argument("--rrf-k", type=int, default=60)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    train_dir = Path(args.train_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sid_codes = np.load(train_dir / "sid_codes.npy")
    turn_arr = np.load(train_dir / "turn_arr.npy")
    trk_codes = np.load(train_dir / "trk_codes.npy")
    y = np.load(train_dir / "y.npy")
    rrf_rank = np.load(train_dir / "rrf_rank.npy")
    sid_uniq = json.loads((train_dir / "sid_uniq.json").read_text())
    trk_uniq = json.loads((train_dir / "trk_uniq.json").read_text())
    lgbm_scores = _load_lgbm_oof_scores(train_dir, len(y))
    semantic_by_level = _semantic_arrays(Path(args.semantic_ids), trk_uniq)
    semantic_df = pd.read_parquet(args.semantic_ids)
    sid_l2_multiplier = int(semantic_df["sid_l2"].max()) + 1 if "sid_l2" in semantic_df else 1
    semantic_lookup = {
        str(row.track_id): (
            int(row.sid_l1),
            int(row.sid_l1) * sid_l2_multiplier + int(row.sid_l2),
        )
        for row in semantic_df.itertuples()
        if hasattr(row, "sid_l2")
    }
    history = _ground_truth_history(Path(args.gt), sid_uniq, semantic_lookup)

    order = np.lexsort((turn_arr, sid_codes))
    keys = sid_codes[order].astype(np.int64) * 10 + turn_arr[order].astype(np.int64)
    _, starts = np.unique(keys, return_index=True)
    stops = np.append(starts[1:], len(order))

    groups: list[dict] = []
    for start, stop in zip(starts, stops):
        idx = order[start:stop]
        sid_code = int(sid_codes[idx[0]])
        turn_number = int(turn_arr[idx[0]])
        label_positions = np.flatnonzero(y[idx] == 1)
        gt_local_idx = int(label_positions[0]) if len(label_positions) else None

        lgbm_order = np.argsort(-lgbm_scores[idx], kind="mergesort")
        lgbm_ranks = np.empty(len(idx), dtype=np.int32)
        lgbm_ranks[lgbm_order] = np.arange(1, len(idx) + 1, dtype=np.int32)

        rrf_values = np.nan_to_num(rrf_rank[idx], nan=1e9, posinf=1e9)
        rrf_order = np.argsort(rrf_values, kind="mergesort")
        rrf_ranks = np.empty(len(idx), dtype=np.int32)
        rrf_ranks[rrf_order] = np.arange(1, len(idx) + 1, dtype=np.int32)

        group = {
            "split": _split_name(str(sid_uniq[sid_code])),
            "gt_local_idx": gt_local_idx,
            "lgbm_oof_ranks": lgbm_ranks,
            "rrf_ranks": rrf_ranks,
        }
        for level, semantic_codes in semantic_by_level.items():
            group[f"clusters_l{level}"] = semantic_codes[trk_codes[idx]]
            group[f"anchor_l{level}"] = history.get((sid_code, turn_number), {}).get(level, [])
        groups.append(group)

    base_configs = [
        OverlayConfig(base="lgbm_oof", level=1, seed_topn=0, seed_weight=0.0, anchor_turns=0, anchor_weight=0.0),
        OverlayConfig(base="rrf", level=1, seed_topn=0, seed_weight=0.0, anchor_turns=0, anchor_weight=0.0),
    ]
    grid: list[OverlayConfig] = []
    for base in ("lgbm_oof", "rrf"):
        for level in (1, 2):
            for seed_topn in (5, 20, 50):
                for seed_weight in (0.10, 0.25, 0.50, 1.0, 2.0):
                    grid.append(OverlayConfig(base, level, seed_topn, seed_weight, 0, 0.0))
            for anchor_turns in (1, 3, 7):
                for anchor_weight in (0.10, 0.25, 0.50, 1.0, 2.0):
                    grid.append(OverlayConfig(base, level, 0, 0.0, anchor_turns, anchor_weight))

    baseline = {
        cfg.base: {
            split: _evaluate_config(cfg, groups=groups, split=split, rrf_k=args.rrf_k)
            for split in ("all", "tune", "test")
        }
        for cfg in base_configs
    }
    scored = []
    for idx, cfg in enumerate(grid, start=1):
        if idx == 1 or idx % 20 == 0 or idx == len(grid):
            print(f"evaluating overlay config {idx}/{len(grid)}", file=sys.stderr, flush=True)
        tune = _evaluate_config(cfg, groups=groups, split="tune", rrf_k=args.rrf_k)
        test = _evaluate_config(cfg, groups=groups, split="test", rrf_k=args.rrf_k)
        scored.append({
            "config": asdict(cfg),
            "tune": tune,
            "test": test,
            "objective": float(tune["ndcg@20"]),
        })
    scored.sort(key=lambda row: (row["objective"], row["tune"]["hit@20"]), reverse=True)
    best_by_base = {}
    for base in ("lgbm_oof", "rrf"):
        best = next(row for row in scored if row["config"]["base"] == base)
        cfg = OverlayConfig(**best["config"])
        best_by_base[base] = {
            **best,
            "all": _evaluate_config(cfg, groups=groups, split="all", rrf_k=args.rrf_k),
        }

    result = {
        "semantic_ids": str(args.semantic_ids),
        "train_dir": str(train_dir),
        "n_turn_groups": len(groups),
        "evaluation_note": "Metrics are conditional on playable turns in the v10 feature matrix; non-playable turns are skipped by build_features.py.",
        "baseline": baseline,
        "best_by_base": best_by_base,
        "top_10": scored[:10],
    }
    out_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
