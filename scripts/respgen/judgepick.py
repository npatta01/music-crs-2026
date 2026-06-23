from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from scripts.respgen import common
from scripts.respgen.common import (
    distinct_n,
    extract_avoid_hints,
    load_dataset_rows_by_session,
    load_predictions,
    load_track_metadata,
    load_traces,
    select_response_track,
    summarize_audits,
    write_predictions,
    write_submission_zip,
)


DEFAULT_DATASET = "talkpl-ai/TalkPlayData-Challenge-Blind-A"
DEFAULT_TRACK_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"


def _key(row: dict[str, Any]) -> tuple[str, int]:
    return (row["session_id"], int(row["turn_number"]))


def _combined_score(judge: dict[str, Any] | None) -> float | None:
    if not judge:
        return None
    top1_keys = (
        "top1_faithfulness",
        "latest_request_alignment",
        "constraint_respect",
        "grounded_explanation",
        "language_match",
        "response_quality",
    )
    if all(key in judge for key in top1_keys):
        try:
            return sum(float(judge[key]) for key in top1_keys) / len(top1_keys)
        except Exception:
            return None
    try:
        return (
            float(judge["personalization"])
            + float(judge["explanation"])
            + float(judge["constraint_following"])
        ) / 3.0
    except Exception:
        return None


def judge_scores_by_key(judge_report: dict[str, Any]) -> dict[tuple[str, int], float]:
    scores: dict[tuple[str, int], float] = {}
    for row in judge_report.get("rows") or []:
        score = _combined_score(row.get("judge"))
        if score is not None:
            scores[(row["session_id"], int(row["turn_number"]))] = score
    return scores


def build_judgepick_rows(
    base_rows: Sequence[dict[str, Any]],
    variant_rows: Sequence[dict[str, Any]],
    base_scores: dict[tuple[str, int], float],
    variant_scores: dict[tuple[str, int], float],
) -> tuple[list[dict[str, Any]], list[tuple[str, int]], list[float]]:
    variant_by_key = {_key(row): row for row in variant_rows}
    rows: list[dict[str, Any]] = []
    selected_keys: list[tuple[str, int]] = []
    selected_scores: list[float] = []
    for base_row in base_rows:
        key = _key(base_row)
        if key not in variant_by_key:
            raise KeyError(f"missing variant row for {key}")
        out = dict(base_row)
        base_score = base_scores.get(key)
        variant_score = variant_scores.get(key)
        if variant_score is not None and (base_score is None or variant_score > base_score):
            out["predicted_response"] = variant_by_key[key].get("predicted_response") or ""
            selected_keys.append(key)
            selected_scores.append(variant_score)
        else:
            selected_scores.append(base_score or 0.0)
        rows.append(out)
    return rows, selected_keys, selected_scores


def _all_track_ids(rows: Sequence[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        for track_id in row.get("predicted_track_ids") or []:
            if track_id and track_id not in seen:
                seen.add(track_id)
                out.append(track_id)
    return out


def promote_selected_safe_candidates(
    rows: Sequence[dict[str, Any]],
    selected_keys: set[tuple[str, int]],
    dataset_rows_by_session: dict[str, dict[str, Any]],
    metadata_by_id: dict[str, dict[str, Any]],
    traces: dict[tuple[str, int], dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    promoted_rows: list[dict[str, Any]] = []
    promotions: list[dict[str, Any]] = []
    for row in rows:
        key = _key(row)
        out = dict(row)
        if key in selected_keys:
            dataset_row = dataset_rows_by_session[row["session_id"]]
            latest = common._latest_user(dataset_row.get("conversations") or [])
            latest_text = latest.get("content", "") if latest else ""
            trace = ((traces or {}).get(key) or {}).get("trace")
            avoid_hints = set(extract_avoid_hints(latest_text))
            avoid_hints.update(common._avoid_hints_from_trace(trace))
            selected = select_response_track(
                row.get("predicted_track_ids") or [],
                metadata_by_id,
                avoid_hints,
                promote=True,
            )
            if selected.changed:
                old_top = (row.get("predicted_track_ids") or [None])[0]
                out["predicted_track_ids"] = selected.track_ids
                promotions.append(
                    {
                        "session_id": key[0],
                        "turn_number": key[1],
                        "from": old_top,
                        "to": selected.track_id,
                        "reason": selected.reason,
                    }
                )
        promoted_rows.append(out)
    return promoted_rows, promotions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build judge-picked hybrid response submissions.")
    parser.add_argument("--base", required=True, help="Base prediction .zip or .json.")
    parser.add_argument("--variant", required=True, help="Variant prediction .zip or .json.")
    parser.add_argument("--base-judge", required=True, help="Offline judge JSON for the base predictions.")
    parser.add_argument("--variant-judge", required=True, help="Offline judge JSON for the variant predictions.")
    parser.add_argument("--out", required=True, help="Output prediction JSON path.")
    parser.add_argument("--zip-out", help="Optional CodaBench zip output path.")
    parser.add_argument("--metadata-out", help="Optional metadata JSON path.")
    parser.add_argument("--promote-selected-safe-candidates", action="store_true")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--dataset-split", default="test")
    parser.add_argument("--track-dataset", default=DEFAULT_TRACK_DATASET)
    parser.add_argument("--track-split", default="all_tracks")
    parser.add_argument("--trace", help="Trace sidecar JSONL, required for trace-derived safe promotions.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_rows = load_predictions(args.base)
    variant_rows = load_predictions(args.variant)
    if len(base_rows) != len(variant_rows):
        raise ValueError(f"row count mismatch: base={len(base_rows)} variant={len(variant_rows)}")

    with open(args.base_judge, "r", encoding="utf-8") as handle:
        base_scores = judge_scores_by_key(json.load(handle))
    with open(args.variant_judge, "r", encoding="utf-8") as handle:
        variant_scores = judge_scores_by_key(json.load(handle))

    rows, selected_keys, selected_scores = build_judgepick_rows(base_rows, variant_rows, base_scores, variant_scores)
    promotions: list[dict[str, Any]] = []
    if args.promote_selected_safe_candidates:
        dataset_rows = load_dataset_rows_by_session(args.dataset, split=args.dataset_split)
        metadata = load_track_metadata(_all_track_ids(rows), dataset_name=args.track_dataset, split=args.track_split)
        traces = load_traces(args.trace) if args.trace else None
        rows, promotions = promote_selected_safe_candidates(
            rows,
            set(selected_keys),
            dataset_rows,
            metadata,
            traces,
        )

    write_predictions(rows, args.out)
    if args.zip_out:
        write_submission_zip(rows, args.zip_out)

    metadata = {
        "base": args.base,
        "variant": args.variant,
        "base_judge": args.base_judge,
        "variant_judge": args.variant_judge,
        "out": args.out,
        "zip_out": args.zip_out,
        "n_rows": len(rows),
        "picked_variant_rows": len(selected_keys),
        "kept_base_rows": len(rows) - len(selected_keys),
        "selected_keys": selected_keys,
        "mean_proxy_combined_from_components": sum(selected_scores) / len(selected_scores) if selected_scores else None,
        "lexical_diversity": distinct_n((row.get("predicted_response") or "" for row in rows), n=2),
        "heuristic_summary": summarize_audits(rows),
        "promote_selected_safe_candidates": args.promote_selected_safe_candidates,
        "promoted_rows": len(promotions),
        "promotions": promotions,
    }
    if args.metadata_out:
        Path(args.metadata_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.metadata_out).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in metadata.items() if k not in {"selected_keys", "promotions"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
