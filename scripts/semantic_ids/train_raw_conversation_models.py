from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
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
from mcrs.analysis.conversation_semantic import (  # noqa: E402
    combine_text_and_prior_vectors,
    conversation_input_text,
    hashed_text_vector,
    prior_track_centroid,
)
from train_conversation_retriever import (  # noqa: E402
    QueryProjector,
    _evaluate as evaluate_retriever,
    _load_catalog,
    _load_playable,
    _rank_examples,
    _train as train_retriever,
)
from train_semantic_id_decoder import (  # noqa: E402
    _decode_ranks,
    _evaluate as evaluate_decoder,
    _load_leaf_targets,
    _train as train_decoder,
)


RAW_VIEWS = (
    "last_turn",
    "last_turn_state_prior",
    "full_conversation_state_prior",
)


@dataclass(frozen=True)
class RawExample:
    session_id: str
    turn_number: int
    split: str
    playable: bool
    target_code: int
    features: np.ndarray
    hard_negative_codes: np.ndarray


def _build_raw_examples(
    *,
    sessions: dict,
    split_name: str,
    playable: set[tuple[str, int]],
    view: str,
    track_ids: list[str],
    track_lookup: dict[str, str],
    item_vectors: np.ndarray,
    text_dim: int,
) -> list[RawExample]:
    track_to_code = {track_id: idx for idx, track_id in enumerate(track_ids)}
    examples: list[RawExample] = []
    for session_id, session in sessions.items():
        played = session.get("played_by_turn") or {}
        for raw_turn in sorted(played):
            try:
                turn_number = int(raw_turn)
            except Exception:
                continue
            target_ids = played.get(raw_turn) or []
            if not target_ids:
                continue
            target_id = str(target_ids[0])
            target_code = track_to_code.get(target_id)
            if target_code is None:
                continue
            text = conversation_input_text(
                session,
                {},
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
            examples.append(RawExample(
                session_id=str(session_id),
                turn_number=turn_number,
                split=split_name,
                playable=(str(session_id), turn_number) in playable,
                target_code=int(target_code),
                features=combine_text_and_prior_vectors(text_vec, prior_vec),
                hard_negative_codes=np.zeros(0, dtype=np.int32),
            ))
    return examples


def _metrics_from_ranks(ranks: np.ndarray, examples: list[RawExample]) -> dict[str, dict[str, float | int]]:
    return evaluate_retriever(ranks, examples)


def _best_test_view(result: dict, model_name: str) -> str | None:
    best = None
    best_score = -1.0
    for view, row in result[model_name].items():
        score = float(row["metrics"]["test"]["recall@100"])
        if score > best_score:
            best = view
            best_score = score
    return best


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train raw-conversation retriever and semantic-ID decoder on HF train, evaluate on devset.")
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--eval-split", default="test")
    parser.add_argument("--train-dir", default="exp/analysis/rerank/v10/train_local")
    parser.add_argument("--db-uri", default="cache/lancedb")
    parser.add_argument("--table-name", default="music_track_catalog")
    parser.add_argument("--vector-field", default="cf_bpr")
    parser.add_argument("--semantic-ids", default="exp/analysis/semantic_ids/semantic_ids_cf_l64_l16.parquet")
    parser.add_argument("--view", action="append", dest="views", default=None)
    parser.add_argument("--text-dim", type=int, default=512)
    parser.add_argument("--retriever-epochs", type=int, default=5)
    parser.add_argument("--decoder-epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--eval-batch-size", type=int, default=512)
    parser.add_argument("--random-negatives", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.07)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--top-leaves", type=int, default=64)
    parser.add_argument("--max-candidates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=67)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--skip-retriever", action="store_true")
    parser.add_argument("--skip-decoder", action="store_true")
    parser.add_argument("--out", default="exp/analysis/semantic_ids/raw_conversation_models_eval.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else ("cpu" if args.device == "auto" else args.device))

    print("loading catalog", file=sys.stderr, flush=True)
    track_ids, track_lookup, item_vectors = _load_catalog(args.db_uri, args.table_name, args.vector_field)
    playable = _load_playable(Path(args.train_dir))
    print("loading HF sessions", file=sys.stderr, flush=True)
    train_sessions = load_sessions(split=args.train_split)
    eval_sessions = load_sessions(split=args.eval_split)
    leaf_target_by_code, leaf_tracks, leaves = _load_leaf_targets(Path(args.semantic_ids), track_ids)

    result = {
        "config": vars(args) | {
            "device": str(device),
            "n_tracks": len(track_ids),
            "n_leaves": len(leaves),
        },
        "retriever": {},
        "decoder": {},
        "evaluation_note": (
            "Train examples come from HF train conversations without extracted state. "
            "Evaluation uses all HF test/dev turns and marks v10 playable turns from per_turn_ranks.parquet."
        ),
    }
    views = args.views or list(RAW_VIEWS)
    for view in views:
        print(f"building raw examples for {view}", file=sys.stderr, flush=True)
        train_examples = _build_raw_examples(
            sessions=train_sessions,
            split_name="train",
            playable=set(),
            view=view,
            track_ids=track_ids,
            track_lookup=track_lookup,
            item_vectors=item_vectors,
            text_dim=args.text_dim,
        )
        eval_examples = _build_raw_examples(
            sessions=eval_sessions,
            split_name="test",
            playable=playable,
            view=view,
            track_ids=track_ids,
            track_lookup=track_lookup,
            item_vectors=item_vectors,
            text_dim=args.text_dim,
        )
        examples = train_examples + eval_examples
        print(f"{view}: train={len(train_examples)} eval={len(eval_examples)}", file=sys.stderr, flush=True)

        if not args.skip_retriever:
            model, history = train_retriever(
                examples=examples,
                item_vectors=item_vectors,
                epochs=args.retriever_epochs,
                batch_size=args.batch_size,
                hard_negatives=0,
                random_negatives=args.random_negatives,
                lr=args.lr,
                temperature=args.temperature,
                seed=args.seed,
                device=device,
            )
            ranks = _rank_examples(
                model,
                eval_examples,
                item_vectors,
                batch_size=args.eval_batch_size,
                device=device,
            )
            result["retriever"][view] = {
                "n_train_examples": len(train_examples),
                "n_eval_examples": len(eval_examples),
                "n_eval_playable": sum(1 for ex in eval_examples if ex.playable),
                "n_eval_non_playable": sum(1 for ex in eval_examples if not ex.playable),
                "training_history": history,
                "metrics": _metrics_from_ranks(ranks, eval_examples),
            }
            out.write_text(json.dumps(result, indent=2) + "\n")

        if not args.skip_decoder:
            dec_train = [ex for ex in train_examples if leaf_target_by_code[ex.target_code] >= 0]
            dec_eval = [ex for ex in eval_examples if leaf_target_by_code[ex.target_code] >= 0]
            dec_examples = dec_train + dec_eval
            features = np.vstack([ex.features for ex in dec_examples]).astype(np.float32)
            target_codes = np.asarray([ex.target_code for ex in dec_examples], dtype=np.int32)
            leaf_targets = leaf_target_by_code[target_codes]
            train_idx = np.arange(len(dec_train), dtype=np.int32)
            decoder, history = train_decoder(
                features=features,
                targets=leaf_targets,
                train_indices=train_idx,
                n_leaves=len(leaves),
                epochs=args.decoder_epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                seed=args.seed + 1,
                device=device,
            )
            eval_features = features[len(dec_train):]
            eval_target_codes = target_codes[len(dec_train):]
            ranks = _decode_ranks(
                model=decoder,
                features=eval_features,
                target_codes=eval_target_codes,
                item_vectors=item_vectors,
                leaf_tracks=leaf_tracks,
                top_leaves=args.top_leaves,
                max_candidates=args.max_candidates,
                batch_size=args.eval_batch_size,
                device=device,
            )
            result["decoder"][view] = {
                "n_train_examples": len(dec_train),
                "n_eval_examples": len(dec_eval),
                "n_eval_playable": sum(1 for ex in dec_eval if ex.playable),
                "n_eval_non_playable": sum(1 for ex in dec_eval if not ex.playable),
                "training_history": history,
                "metrics": evaluate_decoder(ranks, dec_eval),
            }
            out.write_text(json.dumps(result, indent=2) + "\n")

    result["best_by_test_recall100"] = {
        "retriever": _best_test_view(result, "retriever") if result["retriever"] else None,
        "decoder": _best_test_view(result, "decoder") if result["decoder"] else None,
    }
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
