from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
RERANK_DIR = ROOT / "scripts" / "rerank"
for path in (ROOT, SCRIPT_DIR, RERANK_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_features import load_sessions  # noqa: E402
from train_conversation_retriever import (  # noqa: E402
    DEFAULT_VIEWS,
    _build_examples,
    _load_catalog,
    _load_playable,
    _load_trace_rows,
)


class LeafDecoder(torch.nn.Module):
    def __init__(self, input_dim: int, n_leaves: int):
        super().__init__()
        hidden = max(256, input_dim // 2)
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_dim, hidden),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.05),
            torch.nn.Linear(hidden, n_leaves),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.net(values)


def _load_leaf_targets(semantic_path: Path, track_ids: list[str]) -> tuple[np.ndarray, list[list[int]], list[tuple[int, int]]]:
    df = pd.read_parquet(semantic_path)
    by_track = {
        str(row.track_id): (int(row.sid_l1), int(row.sid_l2))
        for row in df.itertuples()
    }
    leaves = sorted(set(by_track.values()))
    leaf_to_idx = {leaf: idx for idx, leaf in enumerate(leaves)}
    target_by_code = np.full(len(track_ids), -1, dtype=np.int32)
    leaf_tracks: list[list[int]] = [[] for _ in leaves]
    for code, track_id in enumerate(track_ids):
        leaf = by_track.get(track_id)
        if leaf is None:
            continue
        leaf_idx = leaf_to_idx[leaf]
        target_by_code[code] = leaf_idx
        leaf_tracks[leaf_idx].append(code)
    return target_by_code, leaf_tracks, leaves


def _train(
    *,
    features: np.ndarray,
    targets: np.ndarray,
    train_indices: np.ndarray,
    n_leaves: int,
    epochs: int,
    batch_size: int,
    lr: float,
    seed: int,
    device: torch.device,
) -> tuple[LeafDecoder, list[dict]]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = LeafDecoder(features.shape[1], n_leaves).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    history = []
    for epoch in range(1, epochs + 1):
        perm = rng.permutation(train_indices)
        total_loss = 0.0
        total = 0
        correct = 0
        model.train()
        for start in range(0, len(perm), batch_size):
            idx = perm[start:start + batch_size]
            x = torch.from_numpy(features[idx]).to(device)
            y = torch.from_numpy(targets[idx].astype(np.int64)).to(device)
            logits = model(x)
            loss = torch.nn.functional.cross_entropy(logits, y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            rows = len(idx)
            total += rows
            total_loss += float(loss.detach().cpu()) * rows
            correct += int((logits.argmax(dim=1) == y).sum().detach().cpu())
        history.append({
            "epoch": epoch,
            "loss": total_loss / max(total, 1),
            "train_leaf_top1": correct / max(total, 1),
        })
    return model, history


@torch.no_grad()
def _decode_ranks(
    *,
    model: LeafDecoder,
    features: np.ndarray,
    target_codes: np.ndarray,
    item_vectors: np.ndarray,
    leaf_tracks: list[list[int]],
    top_leaves: int,
    max_candidates: int,
    batch_size: int,
    device: torch.device,
) -> np.ndarray:
    ranks = np.full(len(features), max_candidates + 1, dtype=np.int32)
    model.eval()
    for start in range(0, len(features), batch_size):
        stop = min(start + batch_size, len(features))
        x = torch.from_numpy(features[start:stop]).to(device)
        logits = model(x).cpu().numpy()
        for local, scores in enumerate(logits):
            row = start + local
            prior = features[row][-item_vectors.shape[1]:]
            leaf_order = np.argsort(-scores, kind="mergesort")[:top_leaves]
            selected: list[int] = []
            seen: set[int] = set()
            for leaf_idx in leaf_order:
                codes = leaf_tracks[int(leaf_idx)]
                if len(codes) == 0:
                    continue
                if np.linalg.norm(prior) > 0:
                    code_arr = np.asarray(codes, dtype=np.int32)
                    inner = item_vectors[code_arr] @ prior
                    ordered_codes = code_arr[np.argsort(-inner, kind="mergesort")]
                else:
                    ordered_codes = codes
                for code in ordered_codes:
                    code = int(code)
                    if code not in seen:
                        seen.add(code)
                        selected.append(code)
                    if len(selected) >= max_candidates:
                        break
                if len(selected) >= max_candidates:
                    break
            target = int(target_codes[row])
            for rank, code in enumerate(selected, start=1):
                if code == target:
                    ranks[row] = rank
                    break
    return ranks


def _metrics(ranks: np.ndarray, mask: np.ndarray) -> dict[str, float | int]:
    selected = ranks[mask]
    denom = int(mask.sum())
    out: dict[str, float | int] = {"denom": denom}
    for k in (20, 50, 100, 500, 1000):
        out[f"recall@{k}"] = float((selected <= k).sum() / denom) if denom else 0.0
    out["median_rank_capped"] = float(np.median(selected)) if denom else 0.0
    return out


def _evaluate(ranks: np.ndarray, examples) -> dict[str, dict[str, float | int]]:
    split = np.asarray([ex.split for ex in examples], dtype=object)
    playable = np.asarray([ex.playable for ex in examples], dtype=bool)
    return {
        "all": _metrics(ranks, np.ones(len(examples), dtype=bool)),
        "train": _metrics(ranks, split == "train"),
        "tune": _metrics(ranks, split == "tune"),
        "test": _metrics(ranks, split == "test"),
        "playable": _metrics(ranks, playable),
        "non_playable": _metrics(ranks, ~playable),
        "test_playable": _metrics(ranks, (split == "test") & playable),
        "test_non_playable": _metrics(ranks, (split == "test") & ~playable),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a constrained conversation-to-semantic-ID decoder.")
    parser.add_argument("--trace", default="exp/inference/devset/state_ranker_v10_lgbm_devset_trace.jsonl")
    parser.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    parser.add_argument("--train-dir", default="exp/analysis/rerank/v10/train_local")
    parser.add_argument("--db-uri", default="cache/lancedb")
    parser.add_argument("--table-name", default="music_track_catalog")
    parser.add_argument("--vector-field", default="cf_bpr")
    parser.add_argument("--semantic-ids", default="exp/analysis/semantic_ids/semantic_ids_cf_l64_l16.parquet")
    parser.add_argument("--view", action="append", dest="views", default=None)
    parser.add_argument("--text-dim", type=int, default=512)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--eval-batch-size", type=int, default=512)
    parser.add_argument("--top-leaves", type=int, default=32)
    parser.add_argument("--max-candidates", type=int, default=1000)
    parser.add_argument("--hard-negative-limit", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=53)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--out", default="exp/analysis/semantic_ids/semantic_id_decoder_eval.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else ("cpu" if args.device == "auto" else args.device))

    print("loading catalog and semantic IDs", file=sys.stderr, flush=True)
    track_ids, track_lookup, item_vectors = _load_catalog(args.db_uri, args.table_name, args.vector_field)
    leaf_target_by_code, leaf_tracks, leaves = _load_leaf_targets(Path(args.semantic_ids), track_ids)
    print("loading sessions/traces", file=sys.stderr, flush=True)
    sessions = load_sessions(split="test")
    trace_rows = _load_trace_rows(Path(args.trace))
    ground_truth = json.loads(Path(args.ground_truth).read_text())
    playable = _load_playable(Path(args.train_dir))

    result = {
        "config": vars(args) | {
            "device": str(device),
            "n_tracks": len(track_ids),
            "n_leaves": len(leaves),
        },
        "views": {},
        "evaluation_note": "Constrained decoder predicts valid semantic-ID leaves, expands tracks in predicted leaves, and ranks inside leaves by prior-track CF similarity.",
    }
    for view in args.views or list(DEFAULT_VIEWS):
        print(f"building examples for {view}", file=sys.stderr, flush=True)
        examples = _build_examples(
            view=view,
            sessions=sessions,
            trace_rows=trace_rows,
            ground_truth=ground_truth,
            playable=playable,
            track_ids=track_ids,
            track_lookup=track_lookup,
            item_vectors=item_vectors,
            text_dim=args.text_dim,
            hard_negative_limit=args.hard_negative_limit,
        )
        examples = [ex for ex in examples if leaf_target_by_code[ex.target_code] >= 0]
        features = np.vstack([ex.features for ex in examples]).astype(np.float32)
        target_codes = np.asarray([ex.target_code for ex in examples], dtype=np.int32)
        leaf_targets = leaf_target_by_code[target_codes]
        train_idx = np.asarray([idx for idx, ex in enumerate(examples) if ex.split == "train"], dtype=np.int32)
        split_counts = {
            name: sum(1 for ex in examples if ex.split == name)
            for name in ("train", "tune", "test")
        }
        print(f"training {view}: {len(examples)} examples {split_counts}", file=sys.stderr, flush=True)
        model, history = _train(
            features=features,
            targets=leaf_targets,
            train_indices=train_idx,
            n_leaves=len(leaves),
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            seed=args.seed,
            device=device,
        )
        ranks = _decode_ranks(
            model=model,
            features=features,
            target_codes=target_codes,
            item_vectors=item_vectors,
            leaf_tracks=leaf_tracks,
            top_leaves=args.top_leaves,
            max_candidates=args.max_candidates,
            batch_size=args.eval_batch_size,
            device=device,
        )
        result["views"][view] = {
            "n_examples": len(examples),
            "split_counts": split_counts,
            "n_playable": sum(1 for ex in examples if ex.playable),
            "n_non_playable": sum(1 for ex in examples if not ex.playable),
            "training_history": history,
            "metrics": _evaluate(ranks, examples),
        }
        out.write_text(json.dumps(result, indent=2) + "\n")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
