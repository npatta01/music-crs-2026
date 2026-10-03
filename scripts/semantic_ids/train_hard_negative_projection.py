from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import lancedb
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcrs.analysis.semantic_hard_negatives import build_turn_example, session_split
from mcrs.analysis.semantic_ids import build_hierarchical_semantic_ids


DEFAULT_FIELDS = ("cf_bpr:1.0",)


@dataclass(frozen=True)
class EvalGroup:
    session_id: str
    turn_number: int
    split: str
    track_codes: np.ndarray
    gt_local_idx: int
    base_ranks: np.ndarray
    query_vector: np.ndarray


def _parse_weighted_fields(values: list[str]) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for value in values:
        if ":" in value:
            field, raw_weight = value.rsplit(":", 1)
            out.append((field, float(raw_weight)))
        else:
            out.append((value, 1.0))
    return out


def _normalise_rows(values: np.ndarray) -> np.ndarray:
    values = np.nan_to_num(np.asarray(values, dtype=np.float32), copy=False)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    np.divide(values, norms, out=values, where=norms > 0)
    return values


def _load_catalog_vectors(
    *,
    db_uri: str,
    table_name: str,
    track_ids: list[str],
    weighted_fields: list[tuple[str, float]],
    input_dim: int,
    seed: int,
) -> tuple[np.ndarray, list[dict]]:
    db = lancedb.connect(db_uri)
    table = db.open_table(table_name)
    schema_names = {field.name for field in table.schema}
    select_cols = ["track_id"]
    for field, _ in weighted_fields:
        if field not in schema_names:
            raise ValueError(f"LanceDB table does not contain vector field {field!r}")
        select_cols.append(field)
        has_col = f"has_{field}"
        if has_col in schema_names:
            select_cols.append(has_col)

    df = table.search().select(select_cols).limit(0).to_pandas()
    df["track_id"] = df["track_id"].astype(str)
    by_track = df.set_index("track_id", drop=False)
    rng = np.random.default_rng(seed)
    combined = np.zeros((len(track_ids), input_dim), dtype=np.float32)
    meta: list[dict] = []

    for field, weight in weighted_fields:
        has_col = f"has_{field}"
        present = (
            by_track[has_col].astype(bool)
            if has_col in by_track.columns
            else pd.Series(True, index=by_track.index)
        )

        first = None
        for track_id in track_ids:
            if track_id not in by_track.index or not bool(present.loc[track_id]):
                continue
            raw = by_track.at[track_id, field]
            if raw is not None and len(raw):
                first = np.asarray(raw, dtype=np.float32)
                break
        if first is None:
            raise ValueError(f"field {field!r} has no non-empty vectors")

        source = np.zeros((len(track_ids), len(first)), dtype=np.float32)
        filled = 0
        for row_idx, track_id in enumerate(track_ids):
            if track_id not in by_track.index or not bool(present.loc[track_id]):
                continue
            raw = by_track.at[track_id, field]
            if raw is None or not len(raw):
                continue
            vec = np.asarray(raw, dtype=np.float32)
            if len(vec) != source.shape[1]:
                raise ValueError(f"field {field!r} has inconsistent vector length for {track_id}")
            source[row_idx] = vec
            filled += 1
        _normalise_rows(source)

        if source.shape[1] == input_dim:
            projected = source
            projection = "identity"
        else:
            rand = rng.normal(
                loc=0.0,
                scale=1.0 / math.sqrt(float(input_dim)),
                size=(source.shape[1], input_dim),
            ).astype(np.float32)
            projected = source @ rand
            projection = "gaussian"
        combined += projected.astype(np.float32, copy=False) * float(weight)
        meta.append({
            "field": field,
            "weight": float(weight),
            "source_dim": int(source.shape[1]),
            "projection": projection,
            "non_empty_rows": int(filled),
        })

    return _normalise_rows(combined), meta


def _load_lgbm_oof_scores(train_dir: Path, n_rows: int) -> np.ndarray:
    sid_codes = np.load(train_dir / "sid_codes.npy")
    sid_fold = np.load(train_dir / "sid_fold.npy")
    scores = np.full(n_rows, np.nan, dtype=np.float32)
    lock_scores = np.zeros(n_rows, dtype=np.float64)
    for fold in range(5):
        idx = np.load(train_dir / f"idx_test_fold{fold}.npy")
        scores[idx] = np.load(train_dir / f"scores_test_fold{fold}.npy")
        lock_idx = np.load(train_dir / f"idx_lockbox_fold{fold}.npy")
        lock_scores[lock_idx] += np.load(train_dir / f"scores_lockbox_fold{fold}.npy")
    lock_rows = np.flatnonzero(sid_fold[sid_codes] == -1)
    scores[lock_rows] = (lock_scores[lock_rows] / 5).astype(np.float32)
    if np.isnan(scores).any():
        raise ValueError("OOF score reconstruction left NaN rows")
    return scores


def _ranks_from_scores(scores: np.ndarray) -> np.ndarray:
    order = np.argsort(-scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.int32)
    ranks[order] = np.arange(1, len(scores) + 1, dtype=np.int32)
    return ranks


def _ranks_from_rrf(rrf_rank: np.ndarray) -> np.ndarray:
    values = np.nan_to_num(rrf_rank, nan=1e9, posinf=1e9, neginf=1e9)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.int32)
    ranks[order] = np.arange(1, len(values) + 1, dtype=np.int32)
    return ranks


def _build_groups(
    *,
    train_dir: Path,
    item_vectors: np.ndarray,
    base: str,
    context_topn: int,
    max_negatives: int,
) -> tuple[list[EvalGroup], list[tuple[np.ndarray, int, np.ndarray]]]:
    sid_codes = np.load(train_dir / "sid_codes.npy")
    turn_arr = np.load(train_dir / "turn_arr.npy")
    trk_codes = np.load(train_dir / "trk_codes.npy")
    labels = np.load(train_dir / "y.npy")
    sid_uniq = json.loads((train_dir / "sid_uniq.json").read_text())
    rrf_rank = np.load(train_dir / "rrf_rank.npy") if base == "rrf" else None
    lgbm_scores = _load_lgbm_oof_scores(train_dir, len(labels)) if base == "lgbm_oof" else None

    order = np.lexsort((turn_arr, sid_codes))
    keys = sid_codes[order].astype(np.int64) * 10 + turn_arr[order].astype(np.int64)
    _, starts = np.unique(keys, return_index=True)
    stops = np.append(starts[1:], len(order))

    groups: list[EvalGroup] = []
    examples: list[tuple[np.ndarray, int, np.ndarray]] = []
    for start, stop in zip(starts, stops):
        idx = order[start:stop]
        label_positions = np.flatnonzero(labels[idx] == 1)
        if len(label_positions) == 0:
            continue
        if lgbm_scores is not None:
            base_ranks = _ranks_from_scores(lgbm_scores[idx])
        else:
            assert rrf_rank is not None
            base_ranks = _ranks_from_rrf(rrf_rank[idx])

        example = build_turn_example(
            item_vectors=item_vectors,
            labels=labels[idx],
            track_codes=trk_codes[idx],
            base_ranks=base_ranks,
            context_topn=context_topn,
            max_negatives=max_negatives,
        )
        if example is None or len(example.negative_codes) < max_negatives:
            continue

        sid_code = int(sid_codes[idx[0]])
        session_id = str(sid_uniq[sid_code])
        groups.append(EvalGroup(
            session_id=session_id,
            turn_number=int(turn_arr[idx[0]]),
            split=session_split(session_id),
            track_codes=trk_codes[idx].astype(np.int32, copy=True),
            gt_local_idx=int(label_positions[0]),
            base_ranks=base_ranks.astype(np.int32, copy=False),
            query_vector=example.query_vector,
        ))
        examples.append((example.query_vector, example.positive_code, example.negative_codes))
    return groups, examples


class ProjectionModel(torch.nn.Module):
    def __init__(self, input_dim: int, output_dim: int):
        super().__init__()
        self.query = torch.nn.Linear(input_dim, output_dim, bias=False)
        self.item = torch.nn.Linear(input_dim, output_dim, bias=False)

    def forward(self, query_vectors: torch.Tensor, item_vectors: torch.Tensor) -> torch.Tensor:
        q = torch.nn.functional.normalize(self.query(query_vectors), dim=-1)
        items = torch.nn.functional.normalize(self.item(item_vectors), dim=-1)
        return torch.einsum("bd,bnd->bn", q, items)

    @torch.no_grad()
    def project_items(self, item_vectors: np.ndarray, device: torch.device, batch_size: int = 4096) -> np.ndarray:
        out = []
        self.eval()
        for start in range(0, len(item_vectors), batch_size):
            batch = torch.from_numpy(item_vectors[start:start + batch_size]).to(device)
            out.append(torch.nn.functional.normalize(self.item(batch), dim=-1).cpu().numpy())
        return np.vstack(out).astype(np.float32)

    @torch.no_grad()
    def project_queries(self, query_vectors: np.ndarray, device: torch.device, batch_size: int = 4096) -> np.ndarray:
        out = []
        self.eval()
        for start in range(0, len(query_vectors), batch_size):
            batch = torch.from_numpy(query_vectors[start:start + batch_size]).to(device)
            out.append(torch.nn.functional.normalize(self.query(batch), dim=-1).cpu().numpy())
        return np.vstack(out).astype(np.float32)


def _train_model(
    *,
    item_vectors: np.ndarray,
    examples: list[tuple[np.ndarray, int, np.ndarray]],
    output_dim: int,
    epochs: int,
    batch_size: int,
    lr: float,
    temperature: float,
    seed: int,
    device: torch.device,
) -> tuple[ProjectionModel, list[dict]]:
    torch.manual_seed(seed)
    model = ProjectionModel(item_vectors.shape[1], output_dim).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    rng = np.random.default_rng(seed)

    q = np.vstack([ex[0] for ex in examples]).astype(np.float32)
    codes = np.vstack([
        np.concatenate([[ex[1]], ex[2]]).astype(np.int32)
        for ex in examples
    ])
    labels = torch.zeros(batch_size, dtype=torch.long, device=device)
    history: list[dict] = []

    for epoch in range(1, epochs + 1):
        perm = rng.permutation(len(examples))
        total_loss = 0.0
        total_rows = 0
        correct = 0
        model.train()
        for start in range(0, len(perm), batch_size):
            batch_idx = perm[start:start + batch_size]
            q_batch = torch.from_numpy(q[batch_idx]).to(device)
            item_batch = torch.from_numpy(item_vectors[codes[batch_idx]]).to(device)
            target = labels[: len(batch_idx)]
            logits = model(q_batch, item_batch) / float(temperature)
            loss = torch.nn.functional.cross_entropy(logits, target)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()

            rows = len(batch_idx)
            total_loss += float(loss.detach().cpu()) * rows
            total_rows += rows
            correct += int((logits.argmax(dim=1) == 0).sum().detach().cpu())
        history.append({
            "epoch": epoch,
            "loss": total_loss / max(total_rows, 1),
            "train_top1": correct / max(total_rows, 1),
        })
    return model, history


def _metrics_from_ranks(ranks: list[int], denom: int) -> dict[str, float | int]:
    arr = np.asarray(ranks, dtype=np.int32)
    out: dict[str, float | int] = {}
    for k in (1, 5, 10, 20):
        out[f"hit@{k}"] = float((arr <= k).sum() / denom) if denom else 0.0
    out["ndcg@20"] = float(sum(1.0 / math.log2(int(r) + 1) for r in arr if r <= 20) / denom) if denom else 0.0
    out["n_playable"] = int(len(ranks))
    out["denom"] = int(denom)
    return out


def _rank_gt_from_scores(scores: np.ndarray, gt_local_idx: int) -> int:
    gt_score = float(scores[gt_local_idx])
    return int((scores > gt_score).sum()) + 1


def _evaluate(
    groups: list[EvalGroup],
    *,
    item_proj: np.ndarray,
    query_proj_by_group: np.ndarray,
    split: str,
    semantic_weight: float,
    rrf_k: int,
) -> dict[str, dict[str, float | int]]:
    base_ranks: list[int] = []
    semantic_ranks: list[int] = []
    combined_ranks: list[int] = []
    denom = 0

    for group_idx, group in enumerate(groups):
        if split != "all" and group.split != split:
            continue
        denom += 1
        codes = group.track_codes
        sem_scores = item_proj[codes] @ query_proj_by_group[group_idx]
        semantic_rank = _rank_gt_from_scores(sem_scores, group.gt_local_idx)
        semantic_ranks.append(semantic_rank)
        base_ranks.append(int(group.base_ranks[group.gt_local_idx]))

        sem_order = np.argsort(-sem_scores, kind="mergesort")
        sem_rank_arr = np.empty(len(sem_scores), dtype=np.int32)
        sem_rank_arr[sem_order] = np.arange(1, len(sem_scores) + 1, dtype=np.int32)
        combined = (
            1.0 / (rrf_k + group.base_ranks.astype(np.float32))
            + float(semantic_weight) / (rrf_k + sem_rank_arr.astype(np.float32))
        )
        combined_ranks.append(_rank_gt_from_scores(combined, group.gt_local_idx))

    return {
        "base": _metrics_from_ranks(base_ranks, denom),
        "semantic": _metrics_from_ranks(semantic_ranks, denom),
        "combined": _metrics_from_ranks(combined_ranks, denom),
    }


def _write_semantic_ids(
    *,
    out: Path,
    track_ids: list[str],
    item_proj: np.ndarray,
    level_sizes: tuple[int, ...],
    iterations: int,
    seed: int,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    semantic_ids = build_hierarchical_semantic_ids(
        track_ids,
        item_proj,
        level_sizes=level_sizes,
        iterations=iterations,
        seed=seed,
    )
    rows = []
    for track_id in track_ids:
        code = semantic_ids[track_id]
        row = {
            "track_id": track_id,
            "semantic_id": "/".join(str(part) for part in code),
        }
        for idx, part in enumerate(code, start=1):
            row[f"sid_l{idx}"] = int(part)
        rows.append(row)
    pd.DataFrame(rows).to_parquet(out, index=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a lightweight hard-negative item/query projection from v10 candidate pools."
    )
    parser.add_argument("--train-dir", default="exp/analysis/rerank/v10/train_local")
    parser.add_argument("--db-uri", default="cache/lancedb")
    parser.add_argument("--table-name", default="music_track_catalog")
    parser.add_argument("--field", action="append", dest="fields", default=None)
    parser.add_argument("--input-dim", type=int, default=128)
    parser.add_argument("--output-dim", type=int, default=64)
    parser.add_argument("--base", choices=("lgbm_oof", "rrf"), default="lgbm_oof")
    parser.add_argument("--context-topn", type=int, default=20)
    parser.add_argument("--max-negatives", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--temperature", type=float, default=0.07)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--semantic-weight", action="append", type=float, dest="semantic_weights", default=None)
    parser.add_argument("--level-size", action="append", type=int, dest="level_sizes", default=None)
    parser.add_argument("--kmeans-iterations", type=int, default=25)
    parser.add_argument("--seed", type=int, default=29)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--out", default="exp/analysis/semantic_ids/hard_negative_projection_eval.json")
    parser.add_argument("--semantic-out", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    train_dir = Path(args.train_dir)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    fields = _parse_weighted_fields(args.fields or list(DEFAULT_FIELDS))
    track_ids = json.loads((train_dir / "trk_uniq.json").read_text())
    print("loading catalog vectors", file=sys.stderr, flush=True)
    item_vectors, field_meta = _load_catalog_vectors(
        db_uri=args.db_uri,
        table_name=args.table_name,
        track_ids=track_ids,
        weighted_fields=fields,
        input_dim=args.input_dim,
        seed=args.seed,
    )

    print("building hard-negative examples", file=sys.stderr, flush=True)
    groups, examples = _build_groups(
        train_dir=train_dir,
        item_vectors=item_vectors,
        base=args.base,
        context_topn=args.context_topn,
        max_negatives=args.max_negatives,
    )
    train_examples = [
        ex for group, ex in zip(groups, examples)
        if group.split == "train"
    ]
    split_counts = {
        split: sum(1 for group in groups if group.split == split)
        for split in ("train", "tune", "test")
    }
    if not train_examples:
        raise ValueError("no train examples after hard-negative filtering")

    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"training on {len(train_examples)} examples using {device}", file=sys.stderr, flush=True)
    model, history = _train_model(
        item_vectors=item_vectors,
        examples=train_examples,
        output_dim=args.output_dim,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        temperature=args.temperature,
        seed=args.seed,
        device=device,
    )

    item_proj = model.project_items(item_vectors, device=device)
    query_vectors = np.vstack([group.query_vector for group in groups]).astype(np.float32)
    query_proj = model.project_queries(query_vectors, device=device)

    weights = args.semantic_weights or [0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
    scored = []
    for weight in weights:
        tune = _evaluate(
            groups,
            item_proj=item_proj,
            query_proj_by_group=query_proj,
            split="tune",
            semantic_weight=weight,
            rrf_k=args.rrf_k,
        )
        test = _evaluate(
            groups,
            item_proj=item_proj,
            query_proj_by_group=query_proj,
            split="test",
            semantic_weight=weight,
            rrf_k=args.rrf_k,
        )
        scored.append({
            "semantic_weight": float(weight),
            "tune": tune,
            "test": test,
            "objective": float(tune["combined"]["ndcg@20"]),
        })
    scored.sort(key=lambda row: (row["objective"], row["tune"]["combined"]["hit@20"]), reverse=True)
    best_weight = float(scored[0]["semantic_weight"])
    all_metrics = _evaluate(
        groups,
        item_proj=item_proj,
        query_proj_by_group=query_proj,
        split="all",
        semantic_weight=best_weight,
        rrf_k=args.rrf_k,
    )

    semantic_out = Path(args.semantic_out) if args.semantic_out else None
    if semantic_out is not None:
        print("writing learned semantic IDs", file=sys.stderr, flush=True)
        _write_semantic_ids(
            out=semantic_out,
            track_ids=track_ids,
            item_proj=item_proj,
            level_sizes=tuple(args.level_sizes or [64, 16]),
            iterations=args.kmeans_iterations,
            seed=args.seed + 1,
        )

    result = {
        "config": {
            "train_dir": str(train_dir),
            "db_uri": args.db_uri,
            "table_name": args.table_name,
            "fields": field_meta,
            "base": args.base,
            "input_dim": args.input_dim,
            "output_dim": args.output_dim,
            "context_topn": args.context_topn,
            "max_negatives": args.max_negatives,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "temperature": args.temperature,
            "rrf_k": args.rrf_k,
            "seed": args.seed,
            "device": str(device),
            "semantic_out": str(semantic_out) if semantic_out else None,
        },
        "n_groups": len(groups),
        "split_counts": split_counts,
        "n_train_examples": len(train_examples),
        "training_history": history,
        "best": scored[0],
        "all_at_best_weight": all_metrics,
        "grid": scored,
        "evaluation_note": (
            "Diagnostic only: the pseudo-query is the centroid of current v10 top non-label "
            "candidates, and metrics are conditional on playable v10 feature rows."
        ),
    }
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
