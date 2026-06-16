from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import lancedb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcrs.analysis.semantic_ids import build_hierarchical_semantic_ids


DEFAULT_FIELDS = (
    "cf_bpr:1.0",
    "metadata_qwen3_embedding_0_6b:0.75",
    "attributes_qwen3_embedding_0_6b:0.50",
)


def _parse_weighted_fields(values: list[str]) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for value in values:
        if ":" in value:
            field, raw_weight = value.rsplit(":", 1)
            out.append((field, float(raw_weight)))
        else:
            out.append((value, 1.0))
    return out


def _row_vector(value) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=np.float32)
    if arr.size == 0:
        return None
    return arr


def _normalise_rows(values: np.ndarray) -> np.ndarray:
    values = np.nan_to_num(values, copy=False)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    np.divide(values, norms, out=values, where=norms > 0)
    return values


def _project_field(
    df: pd.DataFrame,
    *,
    field: str,
    weight: float,
    projection_dim: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict]:
    has_col = f"has_{field}"
    present = df[has_col].astype(bool).to_numpy() if has_col in df else np.ones(len(df), dtype=bool)
    first = None
    for ok, raw in zip(present, df[field]):
        if not ok:
            continue
        first = _row_vector(raw)
        if first is not None:
            break
    if first is None:
        raise ValueError(f"field {field!r} has no non-empty vectors")

    mat = np.zeros((len(df), len(first)), dtype=np.float32)
    filled = 0
    for idx, (ok, raw) in enumerate(zip(present, df[field])):
        if not ok:
            continue
        vec = _row_vector(raw)
        if vec is None:
            continue
        if len(vec) != mat.shape[1]:
            raise ValueError(f"field {field!r} has inconsistent vector length at row {idx}")
        mat[idx] = vec
        filled += 1

    _normalise_rows(mat)
    projection = rng.normal(
        loc=0.0,
        scale=1.0 / np.sqrt(projection_dim),
        size=(mat.shape[1], projection_dim),
    ).astype(np.float32)
    projected = mat @ projection
    projected *= float(weight)
    return projected.astype(np.float32, copy=False), {
        "field": field,
        "weight": float(weight),
        "source_dim": int(mat.shape[1]),
        "non_empty_rows": int(filled),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build hierarchical semantic IDs from LanceDB track vectors.")
    parser.add_argument("--db-uri", default="cache/lancedb")
    parser.add_argument("--table-name", default="music_track_catalog")
    parser.add_argument("--out", default="exp/analysis/semantic_ids/semantic_ids.parquet")
    parser.add_argument("--meta-out", default=None)
    parser.add_argument("--field", action="append", dest="fields", default=None,
                        help="Vector field with optional weight, e.g. cf_bpr:1.0. Repeatable.")
    parser.add_argument("--projection-dim", type=int, default=96)
    parser.add_argument("--level-size", action="append", type=int, dest="level_sizes", default=None)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--seed", type=int, default=13)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    weighted_fields = _parse_weighted_fields(args.fields or list(DEFAULT_FIELDS))
    level_sizes = tuple(args.level_sizes or [64, 16])
    out = Path(args.out)
    meta_out = Path(args.meta_out) if args.meta_out else out.with_suffix(".meta.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    db = lancedb.connect(args.db_uri)
    table = db.open_table(args.table_name)
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
    track_ids = [str(v) for v in df["track_id"]]
    rng = np.random.default_rng(args.seed)
    combined = np.zeros((len(df), args.projection_dim), dtype=np.float32)
    field_meta = []
    for field, weight in weighted_fields:
        projected, meta = _project_field(
            df,
            field=field,
            weight=weight,
            projection_dim=args.projection_dim,
            rng=rng,
        )
        combined += projected
        field_meta.append(meta)
    _normalise_rows(combined)

    semantic_ids = build_hierarchical_semantic_ids(
        track_ids,
        combined,
        level_sizes=level_sizes,
        iterations=args.iterations,
        seed=args.seed + 1,
    )

    rows = []
    level_counts = [Counter(code[: level + 1] for code in semantic_ids.values())
                    for level in range(len(level_sizes))]
    for track_id in track_ids:
        code = semantic_ids[track_id]
        row = {
            "track_id": track_id,
            "semantic_id": "/".join(str(part) for part in code),
        }
        for idx, part in enumerate(code, start=1):
            row[f"sid_l{idx}"] = int(part)
            row[f"sid_l{idx}_size"] = int(level_counts[idx - 1][code[:idx]])
        rows.append(row)

    pd.DataFrame(rows).to_parquet(out, index=False)
    meta = {
        "db_uri": args.db_uri,
        "table_name": args.table_name,
        "n_tracks": len(track_ids),
        "fields": field_meta,
        "projection_dim": args.projection_dim,
        "level_sizes": list(level_sizes),
        "iterations": args.iterations,
        "seed": args.seed,
        "output": str(out),
    }
    meta_out.write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
