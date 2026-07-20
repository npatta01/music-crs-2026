from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
RERANK_DIR = ROOT / "scripts" / "rerank"
for path in (ROOT, SCRIPT_DIR, RERANK_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_features import load_sessions  # noqa: E402
from mcrs.analysis.conversation_semantic import (  # noqa: E402
    conversation_input_text,
    prior_track_centroid,
)
from mcrs.analysis.qwen_semantic_generator import (  # noqa: E402
    CompactNpzEmbeddingCache,
    SemanticIdSequenceGenerator,
    build_prior_code_tokens,
    rank_tracks_from_code_beams,
)
from train_conversation_retriever import (  # noqa: E402
    _load_catalog,
    _load_playable,
    _load_trace_rows,
)
from train_semantic_id_decoder import _load_leaf_targets  # noqa: E402


RAW_VIEWS = (
    "last_turn_state_prior",
    "full_conversation_state_prior",
)


@dataclass(frozen=True)
class QwenExample:
    session_id: str
    turn_number: int
    split: str
    playable: bool
    text: str
    prior_tokens: tuple[int, ...]
    prior_vector: np.ndarray
    target_code: int
    target_l1: int
    target_l2: int


def _track_to_semantic_codes(semantic_path: Path) -> dict[str, tuple[int, int]]:
    import pandas as pd

    df = pd.read_parquet(semantic_path)
    return {
        str(row.track_id): (int(row.sid_l1), int(row.sid_l2))
        for row in df.itertuples()
        if int(row.sid_l1) >= 0 and int(row.sid_l2) >= 0
    }


def _leaf_tracks_from_codes(
    track_ids: list[str],
    track_to_codes: Mapping[str, tuple[int, int]],
) -> dict[tuple[int, int], list[int]]:
    out: dict[tuple[int, int], list[int]] = {}
    for code, track_id in enumerate(track_ids):
        semantic = track_to_codes.get(track_id)
        if semantic is None:
            continue
        out.setdefault((int(semantic[0]), int(semantic[1])), []).append(int(code))
    return out


def _iter_session_turns(sessions: Mapping) -> list[tuple[str, Mapping, int, str]]:
    rows: list[tuple[str, Mapping, int, str]] = []
    for session_id, session in sessions.items():
        played = session.get("played_by_turn") or {}
        for raw_turn in sorted(played):
            try:
                turn_number = int(raw_turn)
            except Exception:
                continue
            target_ids = played.get(raw_turn) or []
            if target_ids:
                rows.append((str(session_id), session, turn_number, str(target_ids[0])))
    return rows


def _subsample_rows(
    rows: list[tuple[str, Mapping, int, str]],
    *,
    limit: int,
    seed: int,
) -> list[tuple[str, Mapping, int, str]]:
    if limit <= 0 or len(rows) <= limit:
        return rows
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(rows), size=int(limit), replace=False))
    return [rows[int(i)] for i in idx]


def _build_examples(
    *,
    sessions: Mapping,
    split_name: str,
    playable: set[tuple[str, int]],
    view: str,
    trace_rows: Mapping[tuple[str, int], dict],
    track_ids: list[str],
    track_lookup: dict[str, str],
    item_vectors: np.ndarray,
    track_to_codes: Mapping[str, tuple[int, int]],
    n_l1: int,
    n_l2: int,
    max_prior_tracks: int,
    limit: int,
    seed: int,
) -> list[QwenExample]:
    track_to_code = {track_id: idx for idx, track_id in enumerate(track_ids)}
    rows = _subsample_rows(_iter_session_turns(sessions), limit=limit, seed=seed)
    examples: list[QwenExample] = []
    for session_id, session, turn_number, target_id in rows:
        target_code = track_to_code.get(target_id)
        semantic = track_to_codes.get(target_id)
        if target_code is None or semantic is None:
            continue
        trace = trace_rows.get((session_id, turn_number), {})
        text = conversation_input_text(
            session,
            trace.get("trace") or trace,
            turn_number=turn_number,
            view=view,
            track_lookup=track_lookup,
        )
        prior_tokens = tuple(build_prior_code_tokens(
            session,
            turn_number=turn_number,
            track_to_codes=track_to_codes,
            n_l1=n_l1,
            n_l2=n_l2,
            max_prior_tracks=max_prior_tracks,
        ))
        prior_vector = prior_track_centroid(
            session,
            turn_number=turn_number,
            track_to_code=track_to_code,
            item_vectors=item_vectors,
        )
        examples.append(QwenExample(
            session_id=session_id,
            turn_number=int(turn_number),
            split=split_name,
            playable=(session_id, int(turn_number)) in playable,
            text=text,
            prior_tokens=prior_tokens,
            prior_vector=prior_vector,
            target_code=int(target_code),
            target_l1=int(semantic[0]),
            target_l2=int(semantic[1]),
        ))
    return examples


def _make_embedder(args):
    if args.embedding_source == "offline":
        return None
    if args.embedding_source == "litellm":
        from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

        return LiteLLMEmbeddingClient(
            model_name=args.embedding_model,
            api_base=args.embedding_api_base,
            api_key=args.embedding_api_key or os.environ.get("DEEPINFRA_API_KEY"),
            batch_size=args.embedding_batch_size,
            encoding_format=args.embedding_encoding_format,
        )
    if args.embedding_source == "local":
        from mcrs.embeddings.qwen3_embedding import Qwen3EmbeddingClient

        return Qwen3EmbeddingClient(
            model_name=args.local_model,
            device=args.local_embedding_device,
            torch_dtype_name=args.local_dtype,
            batch_size=args.embedding_batch_size,
            max_length=args.local_max_length,
        )
    if args.embedding_source == "modal":
        from mcrs.embeddings.modal_qwen3_client import ModalQwen3EmbeddingClient

        return ModalQwen3EmbeddingClient(
            app_name=args.modal_app_name,
            cls_name=args.modal_cls_name,
        )
    raise ValueError(f"unknown embedding source: {args.embedding_source}")


def _pad_prior_tokens(examples: list[QwenExample], max_prior_tokens: int) -> np.ndarray:
    values = np.full((len(examples), int(max_prior_tokens)), -1, dtype=np.int64)
    for row, ex in enumerate(examples):
        tokens = list(ex.prior_tokens)[-int(max_prior_tokens):]
        if tokens:
            values[row, -len(tokens):] = np.asarray(tokens, dtype=np.int64)
    return values


def _train(
    *,
    model: SemanticIdSequenceGenerator,
    text_embeddings: np.ndarray,
    prior_tokens: np.ndarray,
    targets_l1: np.ndarray,
    targets_l2: np.ndarray,
    train_indices: np.ndarray,
    epochs: int,
    batch_size: int,
    lr: float,
    seed: int,
    device: torch.device,
) -> list[dict]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    history: list[dict] = []
    for epoch in range(1, int(epochs) + 1):
        perm = rng.permutation(train_indices)
        total = 0
        total_loss = 0.0
        top1_l1 = 0
        top1_l2 = 0
        top1_leaf = 0
        model.train()
        for start in range(0, len(perm), int(batch_size)):
            idx = perm[start:start + int(batch_size)]
            x = torch.from_numpy(text_embeddings[idx]).to(device)
            p = torch.from_numpy(prior_tokens[idx]).to(device)
            y1 = torch.from_numpy(targets_l1[idx].astype(np.int64)).to(device)
            y2 = torch.from_numpy(targets_l2[idx].astype(np.int64)).to(device)
            logits_l1, logits_l2 = model(x, p, l1_tokens=y1)
            loss_l1 = torch.nn.functional.cross_entropy(logits_l1, y1)
            loss_l2 = torch.nn.functional.cross_entropy(logits_l2, y2)
            loss = loss_l1 + loss_l2
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            rows = len(idx)
            pred_l1 = logits_l1.argmax(dim=1)
            pred_l2 = logits_l2.argmax(dim=1)
            total += rows
            total_loss += float(loss.detach().cpu()) * rows
            top1_l1 += int((pred_l1 == y1).sum().detach().cpu())
            top1_l2 += int((pred_l2 == y2).sum().detach().cpu())
            top1_leaf += int(((pred_l1 == y1) & (pred_l2 == y2)).sum().detach().cpu())
        history.append({
            "epoch": epoch,
            "loss": total_loss / max(total, 1),
            "train_l1_top1": top1_l1 / max(total, 1),
            "train_l2_top1": top1_l2 / max(total, 1),
            "train_leaf_top1": top1_leaf / max(total, 1),
        })
    return history


@torch.no_grad()
def _rank_examples(
    *,
    model: SemanticIdSequenceGenerator,
    examples: list[QwenExample],
    text_embeddings: np.ndarray,
    prior_tokens: np.ndarray,
    item_vectors: np.ndarray,
    rank_vectors: np.ndarray | None,
    leaf_tracks: Mapping[tuple[int, int], list[int]],
    top_l1: int,
    top_l2: int,
    max_candidates: int,
    expansion_strategy: str,
    batch_size: int,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray]:
    ranks = np.full(len(examples), int(max_candidates) + 1, dtype=np.int32)
    leaf_hit = np.zeros(len(examples), dtype=bool)
    model.eval()
    for start in range(0, len(examples), int(batch_size)):
        stop = min(start + int(batch_size), len(examples))
        x = torch.from_numpy(text_embeddings[start:stop]).to(device)
        p = torch.from_numpy(prior_tokens[start:stop]).to(device)
        logits_l1, _ = model(x, p)
        l1_k = min(int(top_l1), int(logits_l1.shape[1]))
        l2_k = int(top_l2)
        top_l1_values, top_l1_idx = torch.topk(logits_l1, k=l1_k, dim=1)
        repeated_x = x.repeat_interleave(l1_k, dim=0)
        repeated_p = p.repeat_interleave(l1_k, dim=0)
        l1_flat = top_l1_idx.reshape(-1)
        _, logits_l2_flat = model(repeated_x, repeated_p, l1_tokens=l1_flat)
        l1_idx_np = top_l1_idx.detach().cpu().numpy()
        l1_value_np = top_l1_values.detach().cpu().numpy()
        l2_np = logits_l2_flat.reshape(stop - start, l1_k, -1).detach().cpu().numpy()
        for local, ex in enumerate(examples[start:stop]):
            row = start + local
            beams = []
            for l1_pos, l1_code in enumerate(l1_idx_np[local]):
                l2_scores = l2_np[local, l1_pos]
                l2_order = np.argsort(-l2_scores, kind="mergesort")[:l2_k]
                for l2_code in l2_order:
                    beams.append((
                        (int(l1_code), int(l2_code)),
                        float(l1_value_np[local, l1_pos] + l2_scores[int(l2_code)]),
                    ))
            beams.sort(key=lambda item: (-item[1], item[0]))
            leaf_hit[row] = any(leaf == (ex.target_l1, ex.target_l2) for leaf, _ in beams)
            ranked = rank_tracks_from_code_beams(
                beams,
                leaf_tracks=leaf_tracks,
                item_vectors=item_vectors,
                prior_vector=ex.prior_vector,
                max_candidates=int(max_candidates),
                strategy=expansion_strategy,
                rank_vectors=rank_vectors,
                query_vector=text_embeddings[row],
            )
            for rank, code in enumerate(ranked, start=1):
                if int(code) == int(ex.target_code):
                    ranks[row] = rank
                    break
    return ranks, leaf_hit


def _metrics(ranks: np.ndarray, leaf_hit: np.ndarray, mask: np.ndarray) -> dict[str, float | int]:
    selected = ranks[mask]
    selected_leaf = leaf_hit[mask]
    denom = int(mask.sum())
    out: dict[str, float | int] = {"denom": denom}
    for k in (20, 50, 100, 500, 1000):
        out[f"recall@{k}"] = float((selected <= k).sum() / denom) if denom else 0.0
    out["leaf_beam_recall"] = float(selected_leaf.sum() / denom) if denom else 0.0
    out["median_rank_capped"] = float(np.median(selected)) if denom else 0.0
    return out


def _evaluate(ranks: np.ndarray, leaf_hit: np.ndarray, examples: list[QwenExample]) -> dict[str, dict[str, float | int]]:
    split = np.asarray([ex.split for ex in examples], dtype=object)
    playable = np.asarray([ex.playable for ex in examples], dtype=bool)
    return {
        "all": _metrics(ranks, leaf_hit, np.ones(len(examples), dtype=bool)),
        "train": _metrics(ranks, leaf_hit, split == "train"),
        "test": _metrics(ranks, leaf_hit, split == "test"),
        "playable": _metrics(ranks, leaf_hit, playable),
        "non_playable": _metrics(ranks, leaf_hit, ~playable),
        "test_playable": _metrics(ranks, leaf_hit, (split == "test") & playable),
        "test_non_playable": _metrics(ranks, leaf_hit, (split == "test") & ~playable),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a Qwen-embedded conversation-to-semantic-ID generator.")
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--eval-split", default="test")
    parser.add_argument("--train-dir", default="exp/analysis/rerank/v10/train_local")
    parser.add_argument("--eval-trace", default="")
    parser.add_argument("--db-uri", default="cache/lancedb")
    parser.add_argument("--table-name", default="music_track_catalog")
    parser.add_argument("--vector-field", default="cf_bpr")
    parser.add_argument("--rank-vector-field", default="")
    parser.add_argument("--semantic-ids", default="exp/analysis/semantic_ids/semantic_ids_cf_l64_l16.parquet")
    parser.add_argument("--view", action="append", dest="views", default=None)
    parser.add_argument("--embedding-cache-dir", default="exp/analysis/semantic_ids/qwen_text_embedding_cache")
    parser.add_argument("--embedding-source", choices=("litellm", "local", "modal", "offline"), default="litellm")
    parser.add_argument("--embedding-model", default="openai/Qwen/Qwen3-Embedding-0.6B")
    parser.add_argument("--embedding-api-base", default="https://api.deepinfra.com/v1/openai")
    parser.add_argument("--embedding-api-key", default="")
    parser.add_argument("--embedding-encoding-format", default="float")
    parser.add_argument("--embedding-batch-size", type=int, default=64)
    parser.add_argument("--local-model", default="Qwen/Qwen3-Embedding-0.6B")
    parser.add_argument("--local-embedding-device", default="cpu")
    parser.add_argument("--local-dtype", default="float32")
    parser.add_argument("--local-max-length", type=int, default=512)
    parser.add_argument("--modal-app-name", default="music-crs")
    parser.add_argument("--modal-cls-name", default="Qwen3Encoder")
    parser.add_argument("--max-train-examples", type=int, default=0)
    parser.add_argument("--max-eval-examples", type=int, default=0)
    parser.add_argument("--max-prior-tracks", type=int, default=8)
    parser.add_argument("--max-prior-tokens", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--eval-batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--d-model", type=int, default=256)
    parser.add_argument("--nhead", type=int, default=8)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--top-l1", type=int, default=16)
    parser.add_argument("--top-l2", type=int, default=16)
    parser.add_argument("--max-candidates", type=int, default=1000)
    parser.add_argument("--expansion-strategy", choices=("leaf_block", "round_robin"), default="leaf_block")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--out", default="exp/analysis/semantic_ids/qwen_semantic_id_generator_eval.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else ("cpu" if args.device == "auto" else args.device))

    print("loading catalog and semantic IDs", file=sys.stderr, flush=True)
    track_ids, track_lookup, item_vectors = _load_catalog(args.db_uri, args.table_name, args.vector_field)
    rank_vectors = None
    if args.rank_vector_field:
        rank_track_ids, _rank_lookup, rank_vectors = _load_catalog(args.db_uri, args.table_name, args.rank_vector_field)
        if rank_track_ids != track_ids:
            raise ValueError(f"rank vector field {args.rank_vector_field!r} returned a different track order")
    leaf_target_by_code, _leaf_tracks_list, leaves = _load_leaf_targets(Path(args.semantic_ids), track_ids)
    del leaf_target_by_code, _leaf_tracks_list
    track_to_codes = _track_to_semantic_codes(Path(args.semantic_ids))
    leaf_tracks = _leaf_tracks_from_codes(track_ids, track_to_codes)
    n_l1 = max(l1 for l1, _l2 in track_to_codes.values()) + 1
    n_l2 = max(l2 for _l1, l2 in track_to_codes.values()) + 1

    print("loading HF sessions", file=sys.stderr, flush=True)
    train_sessions = load_sessions(split=args.train_split)
    eval_sessions = load_sessions(split=args.eval_split)
    playable = _load_playable(Path(args.train_dir))
    trace_rows = _load_trace_rows(Path(args.eval_trace)) if args.eval_trace else {}
    embedder = _make_embedder(args)

    result = {
        "config": vars(args) | {
            "device": str(device),
            "n_tracks": len(track_ids),
            "rank_vector_dim": int(rank_vectors.shape[1]) if rank_vectors is not None else 0,
            "n_l1": int(n_l1),
            "n_l2": int(n_l2),
            "n_leaves": len(leaves),
            "n_leaf_tracks": len(leaf_tracks),
        },
        "views": {},
        "evaluation_note": (
            "Text is embedded with Qwen3-Embedding-0.6B (unless embedding_source=offline, which requires a prefilled cache). "
            "The model is a Transformer semantic-ID generator conditioned on the Qwen text vector plus prior accepted-track semantic-ID tokens. "
            "It predicts l1 and then predicts l2 conditioned on l1, expands valid leaves to tracks, then ranks within leaves by prior-track CF centroid similarity."
        ),
    }

    for view in args.views or list(RAW_VIEWS):
        print(f"building examples for {view}", file=sys.stderr, flush=True)
        train_examples = _build_examples(
            sessions=train_sessions,
            split_name="train",
            playable=set(),
            view=view,
            trace_rows={},
            track_ids=track_ids,
            track_lookup=track_lookup,
            item_vectors=item_vectors,
            track_to_codes=track_to_codes,
            n_l1=n_l1,
            n_l2=n_l2,
            max_prior_tracks=args.max_prior_tracks,
            limit=args.max_train_examples,
            seed=args.seed,
        )
        eval_examples = _build_examples(
            sessions=eval_sessions,
            split_name="test",
            playable=playable,
            view=view,
            trace_rows=trace_rows,
            track_ids=track_ids,
            track_lookup=track_lookup,
            item_vectors=item_vectors,
            track_to_codes=track_to_codes,
            n_l1=n_l1,
            n_l2=n_l2,
            max_prior_tracks=args.max_prior_tracks,
            limit=args.max_eval_examples,
            seed=args.seed + 1,
        )
        examples = train_examples + eval_examples
        cache_path = Path(args.embedding_cache_dir) / f"{view}_{args.embedding_source}_{args.embedding_model.replace('/', '__')}.npz"
        cache = CompactNpzEmbeddingCache(cache_path)
        print(
            f"{view}: train={len(train_examples)} eval={len(eval_examples)} cache_size_before={cache.size}",
            file=sys.stderr,
            flush=True,
        )
        text_embeddings = cache.get_many([ex.text for ex in examples], embedder=embedder, offline=args.embedding_source == "offline")
        cache.flush()
        prior_tokens = _pad_prior_tokens(examples, args.max_prior_tokens)
        targets_l1 = np.asarray([ex.target_l1 for ex in examples], dtype=np.int32)
        targets_l2 = np.asarray([ex.target_l2 for ex in examples], dtype=np.int32)
        train_idx = np.arange(len(train_examples), dtype=np.int32)

        model = SemanticIdSequenceGenerator(
            text_dim=text_embeddings.shape[1],
            n_l1=n_l1,
            n_l2=n_l2,
            d_model=args.d_model,
            nhead=args.nhead,
            num_layers=args.num_layers,
            max_prior_tokens=args.max_prior_tokens,
            dropout=args.dropout,
        )
        print(f"training {view}", file=sys.stderr, flush=True)
        history = _train(
            model=model,
            text_embeddings=text_embeddings,
            prior_tokens=prior_tokens,
            targets_l1=targets_l1,
            targets_l2=targets_l2,
            train_indices=train_idx,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            seed=args.seed,
            device=device,
        )
        eval_start = len(train_examples)
        ranks, leaf_hit = _rank_examples(
            model=model,
            examples=eval_examples,
            text_embeddings=text_embeddings[eval_start:],
            prior_tokens=prior_tokens[eval_start:],
            item_vectors=item_vectors,
            rank_vectors=rank_vectors,
            leaf_tracks=leaf_tracks,
            top_l1=args.top_l1,
            top_l2=args.top_l2,
            max_candidates=args.max_candidates,
            expansion_strategy=args.expansion_strategy,
            batch_size=args.eval_batch_size,
            device=device,
        )
        result["views"][view] = {
            "n_train_examples": len(train_examples),
            "n_eval_examples": len(eval_examples),
            "n_eval_playable": sum(1 for ex in eval_examples if ex.playable),
            "n_eval_non_playable": sum(1 for ex in eval_examples if not ex.playable),
            "embedding_cache": str(cache_path),
            "embedding_dim": int(text_embeddings.shape[1]),
            "training_history": history,
            "metrics": _evaluate(ranks, leaf_hit, eval_examples),
        }
        out.write_text(json.dumps(result, indent=2) + "\n")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
