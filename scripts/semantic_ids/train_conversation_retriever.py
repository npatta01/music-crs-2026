from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import lancedb
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
RERANK_DIR = ROOT / "scripts" / "rerank"
for path in (ROOT, RERANK_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_features import load_sessions  # noqa: E402
from mcrs.analysis.conversation_semantic import (  # noqa: E402
    combine_text_and_prior_vectors,
    conversation_input_text,
    hashed_text_vector,
    prior_track_centroid,
)
from mcrs.analysis.semantic_hard_negatives import session_split  # noqa: E402


DEFAULT_VIEWS = (
    "last_turn",
    "state",
    "last_turn_state",
    "last_turn_state_prior",
    "full_conversation_state_prior",
)


@dataclass(frozen=True)
class Example:
    session_id: str
    turn_number: int
    split: str
    playable: bool
    target_code: int
    features: np.ndarray
    hard_negative_codes: np.ndarray


class QueryProjector(torch.nn.Module):
    def __init__(self, input_dim: int, item_dim: int):
        super().__init__()
        hidden = max(item_dim * 2, 128)
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_dim, hidden),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden, item_dim),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return torch.nn.functional.normalize(self.net(values), dim=-1)


def _normalise_rows(values: np.ndarray) -> np.ndarray:
    values = np.nan_to_num(np.asarray(values, dtype=np.float32), copy=False)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    np.divide(values, norms, out=values, where=norms > 0)
    return values


def _row_vector(value) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=np.float32)
    return arr if arr.size else None


def _track_label(row) -> str:
    track = row.track_name
    artist = row.artist_name
    if isinstance(track, (list, tuple, np.ndarray)):
        track = " / ".join(str(v) for v in track if v)
    if isinstance(artist, (list, tuple, np.ndarray)):
        artist = " / ".join(str(v) for v in artist if v)
    if artist and track:
        return f"{artist} - {track}"
    return str(track or row.track_id)


def _load_catalog(db_uri: str, table_name: str, vector_field: str) -> tuple[list[str], dict[str, str], np.ndarray]:
    db = lancedb.connect(db_uri)
    table = db.open_table(table_name)
    schema_names = {field.name for field in table.schema}
    cols = ["track_id", vector_field]
    for col in ("track_name", "artist_name"):
        if col in schema_names:
            cols.append(col)
    has_col = f"has_{vector_field}"
    if has_col in schema_names:
        cols.append(has_col)
    df = table.search().select(cols).limit(0).to_pandas()
    df["track_id"] = df["track_id"].astype(str)

    first = None
    present = df[has_col].astype(bool).to_numpy() if has_col in df else np.ones(len(df), dtype=bool)
    for ok, raw in zip(present, df[vector_field]):
        if ok:
            first = _row_vector(raw)
            if first is not None:
                break
    if first is None:
        raise ValueError(f"catalog field {vector_field!r} has no non-empty vectors")

    vectors = np.zeros((len(df), len(first)), dtype=np.float32)
    for idx, (ok, raw) in enumerate(zip(present, df[vector_field])):
        if not ok:
            continue
        vec = _row_vector(raw)
        if vec is None:
            continue
        vectors[idx] = vec
    track_ids = [str(v) for v in df["track_id"]]
    labels = {str(row.track_id): _track_label(row) for row in df.itertuples()}
    return track_ids, labels, _normalise_rows(vectors)


def _load_trace_rows(trace_path: Path) -> dict[tuple[str, int], dict]:
    rows = {}
    with trace_path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows[(str(row["session_id"]), int(row["turn_number"]))] = row
    return rows


def _candidate_fusion_ids(trace: dict, limit: int) -> list[str]:
    ranking = (trace.get("trace") or {}).get("ranking") or {}
    stages = ranking.get("stages") or []
    stage = next(
        (s for s in stages if isinstance(s, dict) and s.get("name") == "candidate_fusion"),
        stages[0] if stages else {},
    )
    ids = stage.get("track_ids") or []
    return [str(track_id) for track_id in ids[:limit]]


def _load_playable(train_dir: Path) -> set[tuple[str, int]]:
    ranks = pd.read_parquet(train_dir / "per_turn_ranks.parquet")
    return {(str(row.session_id), int(row.turn_number)) for row in ranks.itertuples()}


def _build_examples(
    *,
    view: str,
    sessions: dict,
    trace_rows: dict[tuple[str, int], dict],
    ground_truth: list[dict],
    playable: set[tuple[str, int]],
    track_ids: list[str],
    track_lookup: dict[str, str],
    item_vectors: np.ndarray,
    text_dim: int,
    hard_negative_limit: int,
) -> list[Example]:
    track_to_code = {track_id: idx for idx, track_id in enumerate(track_ids)}
    examples: list[Example] = []
    for row in ground_truth:
        session_id = str(row["session_id"])
        turn_number = int(row["turn_number"])
        target = str(row["ground_truth_track_id"])
        target_code = track_to_code.get(target)
        session = sessions.get(session_id)
        trace = trace_rows.get((session_id, turn_number))
        if target_code is None or session is None or trace is None:
            continue
        text = conversation_input_text(
            session,
            trace.get("trace") or {},
            turn_number=turn_number,
            view=view,
            track_lookup=track_lookup,
        )
        text_vec = hashed_text_vector(text, dim=text_dim)
        prior_vec = prior_track_centroid(
            session,
            turn_number=turn_number,
            track_to_code=track_to_code,
            item_vectors=item_vectors,
        )
        hard = []
        for track_id in _candidate_fusion_ids(trace, hard_negative_limit + 1):
            code = track_to_code.get(track_id)
            if code is not None and code != target_code:
                hard.append(code)
            if len(hard) >= hard_negative_limit:
                break
        examples.append(Example(
            session_id=session_id,
            turn_number=turn_number,
            split=session_split(session_id),
            playable=(session_id, turn_number) in playable,
            target_code=int(target_code),
            features=combine_text_and_prior_vectors(text_vec, prior_vec),
            hard_negative_codes=np.asarray(hard, dtype=np.int32),
        ))
    return examples


def _sample_candidate_codes(
    examples: list[Example],
    batch_indices: np.ndarray,
    *,
    n_items: int,
    random_negatives: int,
    hard_negatives: int,
    rng: np.random.Generator,
) -> np.ndarray:
    width = 1 + hard_negatives + random_negatives
    codes = np.zeros((len(batch_indices), width), dtype=np.int64)
    for out_idx, ex_idx in enumerate(batch_indices):
        ex = examples[int(ex_idx)]
        codes[out_idx, 0] = ex.target_code
        fill = 1
        for code in ex.hard_negative_codes[:hard_negatives]:
            if fill >= 1 + hard_negatives:
                break
            codes[out_idx, fill] = int(code)
            fill += 1
        while fill < width:
            code = int(rng.integers(0, n_items))
            if code != ex.target_code:
                codes[out_idx, fill] = code
                fill += 1
    return codes


def _train(
    *,
    examples: list[Example],
    item_vectors: np.ndarray,
    epochs: int,
    batch_size: int,
    hard_negatives: int,
    random_negatives: int,
    lr: float,
    temperature: float,
    seed: int,
    device: torch.device,
) -> tuple[QueryProjector, list[dict]]:
    train_indices = np.asarray([idx for idx, ex in enumerate(examples) if ex.split == "train"], dtype=np.int32)
    if len(train_indices) == 0:
        raise ValueError("no train examples")
    features = np.vstack([ex.features for ex in examples]).astype(np.float32)
    model = QueryProjector(features.shape[1], item_vectors.shape[1]).to(device)
    item_tensor = torch.from_numpy(item_vectors).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    history = []

    for epoch in range(1, epochs + 1):
        perm = rng.permutation(train_indices)
        total_loss = 0.0
        total = 0
        correct = 0
        model.train()
        for start in range(0, len(perm), batch_size):
            batch_indices = perm[start:start + batch_size]
            candidate_codes = _sample_candidate_codes(
                examples,
                batch_indices,
                n_items=len(item_vectors),
                random_negatives=random_negatives,
                hard_negatives=hard_negatives,
                rng=rng,
            )
            x = torch.from_numpy(features[batch_indices]).to(device)
            c = torch.from_numpy(candidate_codes).to(device)
            q = model(x)
            cand = item_tensor[c]
            logits = torch.einsum("bd,bnd->bn", q, cand) / float(temperature)
            target = torch.zeros(len(batch_indices), dtype=torch.long, device=device)
            loss = torch.nn.functional.cross_entropy(logits, target)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            rows = len(batch_indices)
            total += rows
            total_loss += float(loss.detach().cpu()) * rows
            correct += int((logits.argmax(dim=1) == 0).sum().detach().cpu())
        history.append({
            "epoch": epoch,
            "loss": total_loss / max(total, 1),
            "sampled_train_top1": correct / max(total, 1),
        })
    return model, history


@torch.no_grad()
def _rank_examples(
    model: QueryProjector,
    examples: list[Example],
    item_vectors: np.ndarray,
    *,
    batch_size: int,
    device: torch.device,
) -> np.ndarray:
    features = np.vstack([ex.features for ex in examples]).astype(np.float32)
    item_tensor = torch.from_numpy(item_vectors).to(device)
    ranks = np.zeros(len(examples), dtype=np.int32)
    model.eval()
    for start in range(0, len(examples), batch_size):
        stop = min(start + batch_size, len(examples))
        x = torch.from_numpy(features[start:stop]).to(device)
        q = model(x)
        scores = q @ item_tensor.T
        targets = torch.tensor([ex.target_code for ex in examples[start:stop]], dtype=torch.long, device=device)
        gt = scores[torch.arange(stop - start, device=device), targets]
        ranks[start:stop] = ((scores > gt[:, None]).sum(dim=1) + 1).cpu().numpy().astype(np.int32)
    return ranks


def _metrics(ranks: np.ndarray, mask: np.ndarray) -> dict[str, float | int]:
    selected = ranks[mask]
    denom = int(mask.sum())
    out: dict[str, float | int] = {"denom": denom}
    for k in (20, 50, 100, 500, 1000):
        out[f"recall@{k}"] = float((selected <= k).sum() / denom) if denom else 0.0
    out["median_rank"] = float(np.median(selected)) if denom else 0.0
    return out


def _evaluate(ranks: np.ndarray, examples: list[Example]) -> dict[str, dict[str, float | int]]:
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
    parser = argparse.ArgumentParser(description="Train conversation-conditioned item retrievers.")
    parser.add_argument("--trace", default="exp/inference/devset/state_ranker_v10_lgbm_devset_trace.jsonl")
    parser.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    parser.add_argument("--train-dir", default="exp/analysis/rerank/v10/train_local")
    parser.add_argument("--db-uri", default="cache/lancedb")
    parser.add_argument("--table-name", default="music_track_catalog")
    parser.add_argument("--vector-field", default="cf_bpr")
    parser.add_argument("--view", action="append", dest="views", default=None)
    parser.add_argument("--text-dim", type=int, default=512)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--eval-batch-size", type=int, default=256)
    parser.add_argument("--hard-negatives", type=int, default=64)
    parser.add_argument("--random-negatives", type=int, default=128)
    parser.add_argument("--hard-negative-limit", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--temperature", type=float, default=0.07)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--out", default="exp/analysis/semantic_ids/conversation_retriever_eval.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else ("cpu" if args.device == "auto" else args.device))

    print("loading catalog", file=sys.stderr, flush=True)
    track_ids, track_lookup, item_vectors = _load_catalog(args.db_uri, args.table_name, args.vector_field)
    print("loading sessions/traces", file=sys.stderr, flush=True)
    sessions = load_sessions(split="test")
    trace_rows = _load_trace_rows(Path(args.trace))
    ground_truth = json.loads(Path(args.ground_truth).read_text())
    playable = _load_playable(Path(args.train_dir))

    result = {
        "config": vars(args) | {"device": str(device), "n_tracks": len(track_ids)},
        "views": {},
        "evaluation_note": "Full-catalog recall from conversation/state/prior-track inputs; v10 playable labels come from train_local/per_turn_ranks.parquet.",
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
        split_counts = {
            name: sum(1 for ex in examples if ex.split == name)
            for name in ("train", "tune", "test")
        }
        print(f"training {view}: {len(examples)} examples {split_counts}", file=sys.stderr, flush=True)
        model, history = _train(
            examples=examples,
            item_vectors=item_vectors,
            epochs=args.epochs,
            batch_size=args.batch_size,
            hard_negatives=args.hard_negatives,
            random_negatives=args.random_negatives,
            lr=args.lr,
            temperature=args.temperature,
            seed=args.seed,
            device=device,
        )
        ranks = _rank_examples(
            model,
            examples,
            item_vectors,
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
