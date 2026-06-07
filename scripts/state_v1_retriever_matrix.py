#!/usr/bin/env python
"""Focused retriever matrix for V1 state projection.

This reuses saved live V1 extraction output, projects it through the current
bridge, and compiles a focused pack through candidate-generation variants.

The goal is to measure branch-pool recall, especially union@20 and union@50.
Those metrics only improve when a branch's own top-k changes, so this script
tests query templates and branch composition separately from RRF/ranker tuning.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.conversation_state.schema import (  # noqa: E402
    ConversationStateV1,
    project_v1_to_v0plus,
)
from mcrs.qu_modules.compiler_v0plus_qu import build_v0plus_compiler_qu  # noqa: E402


V1_KEYS = {
    "current_request",
    "facts",
    "exclusions",
    "track_feedback",
    "referenced_track_ids",
    "temporal_constraint",
    "lyrical_theme",
}

DEFAULT_ANALYSIS_DIR = Path(
    "experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06"
)
DEFAULT_CONFIG = Path("configs/v0plus_compiler_all_retrievers_devset.yaml")
DEFAULT_MAIN_LANCEDB = Path("cache/lancedb")

KS = (20, 50, 100, 200, 1000)


@dataclass(frozen=True)
class DenseSpec:
    vector_field: str
    encoder_id: str
    query_id: str
    weight: float = 1.0
    distance_type: str = "cosine"

    def to_config(self) -> dict[str, Any]:
        return {
            "vector_field": self.vector_field,
            "encoder_id": self.encoder_id,
            "query_id": self.query_id,
            "weight": self.weight,
            "distance_type": self.distance_type,
        }


@dataclass(frozen=True)
class Variant:
    name: str
    dense_branches: tuple[DenseSpec, ...] = ()
    centroid: bool = False
    centroid_weight: float = 1.0
    similar_artist_anchors: bool = False
    similar_artist_intents: tuple[str, ...] = ("open_explore", "pivot", "refinement")
    lookups: bool = True


QWEN06_METADATA = "metadata_qwen3_embedding_0_6b"
QWEN06_ATTRIBUTES = "attributes_qwen3_embedding_0_6b"
QWEN8_METADATA = "metadata_qwen3_embedding_8b"
QWEN8_ATTRIBUTES = "attributes_qwen3_embedding_8b"
CLAP_AUDIO = "audio_laion_clap"


VARIANTS: dict[str, Variant] = {
    "bm25_lookup": Variant("bm25_lookup", lookups=True),
    "centroid_style": Variant(
        "centroid_style",
        centroid=True,
        similar_artist_anchors=True,
    ),
    "clap_sonic": Variant(
        "clap_sonic",
        dense_branches=(DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),),
    ),
    "clap_sonic_nl": Variant(
        "clap_sonic_nl",
        dense_branches=(DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),),
    ),
    "clap_sonic_nl_enriched": Variant(
        "clap_sonic_nl_enriched",
        dense_branches=(DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),),
    ),
    "clap_all": Variant(
        "clap_all",
        dense_branches=(
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
    ),
    "clap_centroid": Variant(
        "clap_centroid",
        dense_branches=(
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
        centroid=True,
        similar_artist_anchors=True,
    ),
    "qwen06_metadata": Variant(
        "qwen06_metadata",
        dense_branches=(DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),),
    ),
    "qwen06_metadata_intent": Variant(
        "qwen06_metadata_intent",
        dense_branches=(DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),),
    ),
    "qwen06_attributes": Variant(
        "qwen06_attributes",
        dense_branches=(DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes"),),
    ),
    "qwen06_attributes_enriched": Variant(
        "qwen06_attributes_enriched",
        dense_branches=(
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
        ),
    ),
    "qwen06_intent_attr_enriched": Variant(
        "qwen06_intent_attr_enriched",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
        ),
    ),
    "qwen8_metadata": Variant(
        "qwen8_metadata",
        dense_branches=(DenseSpec(QWEN8_METADATA, "qwen_8b", "metadata"),),
    ),
    "qwen8_metadata_intent": Variant(
        "qwen8_metadata_intent",
        dense_branches=(DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),),
    ),
    "qwen8_attributes": Variant(
        "qwen8_attributes",
        dense_branches=(DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes"),),
    ),
    "qwen8_attributes_enriched": Variant(
        "qwen8_attributes_enriched",
        dense_branches=(
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
        ),
    ),
    "qwen8_intent_attr_enriched": Variant(
        "qwen8_intent_attr_enriched",
        dense_branches=(
            DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
        ),
    ),
    "qwen06_clap_centroid": Variant(
        "qwen06_clap_centroid",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
        centroid=True,
        similar_artist_anchors=True,
    ),
    "all_candidate_recall": Variant(
        "all_candidate_recall",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "metadata"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
        centroid=True,
        similar_artist_anchors=True,
    ),
}


DEFAULT_VARIANTS = (
    "bm25_lookup",
    "centroid_style",
    "clap_sonic",
    "clap_sonic_nl",
    "clap_sonic_nl_enriched",
    "qwen06_metadata",
    "qwen06_metadata_intent",
    "qwen06_attributes",
    "qwen06_attributes_enriched",
)


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["sample_id"]] = row
    return rows


def _rank(ids: list[str], target: str) -> int | None:
    try:
        return ids.index(target) + 1
    except ValueError:
        return None


def _branch_rank(branch_pools, target: str) -> tuple[str | None, int | None]:
    best_name: str | None = None
    best_rank: int | None = None
    for pool in branch_pools:
        ids = [track_id for track_id, _score in pool.hits]
        rank = _rank(ids, target)
        if rank is not None and (best_rank is None or rank < best_rank):
            best_name = pool.name
            best_rank = rank
    return best_name, best_rank


def _union_hit(branch_pools, target: str, k: int) -> bool:
    return any(
        target in {track_id for track_id, _score in pool.hits[:k]}
        for pool in branch_pools
    )


def _variant_qu_kwargs(
    base_qu_kwargs: dict[str, Any],
    variant: Variant,
    lancedb_uri: Path,
) -> dict[str, Any]:
    qu_kwargs = copy.deepcopy(base_qu_kwargs)
    qu_kwargs.setdefault("lancedb", {})
    qu_kwargs["lancedb"]["db_uri"] = str(lancedb_uri)
    # Keep local runs RAM-light. Dense ANN search does not require
    # LanceDbCatalog eager vectors; only centroid construction does. Loading
    # every vector column for every matrix variant can exhaust a laptop.
    eager_vector_fields: list[str] = []
    if variant.centroid:
        eager_vector_fields = [CLAP_AUDIO, "image_siglip2", "cf_bpr"]
    qu_kwargs["lancedb"]["eager_vector_fields"] = eager_vector_fields

    # Avoid instantiating unused remote encoder clients in each variant.
    base_encoders = dict(base_qu_kwargs.get("encoders") or {})
    needed_encoder_ids = {branch.encoder_id for branch in variant.dense_branches}
    if not needed_encoder_ids:
        fallback = base_encoders.get("qwen_0_6b") or next(iter(base_encoders.values()))
        qu_kwargs["encoders"] = {"qwen_0_6b": fallback}
    else:
        missing = sorted(needed_encoder_ids - set(base_encoders))
        if missing:
            raise KeyError(f"variant {variant.name!r} needs missing encoders {missing}")
        qu_kwargs["encoders"] = {
            encoder_id: base_encoders[encoder_id]
            for encoder_id in sorted(needed_encoder_ids)
        }

    comp = qu_kwargs.setdefault("compiler", {})
    comp["branch_trace_topk"] = 1000
    comp["bm25_k"] = 1000
    comp["dense_k"] = 1000
    comp["final_topk"] = 1000
    comp["enable_dense"] = bool(variant.dense_branches)
    comp["dense_branches"] = [branch.to_config() for branch in variant.dense_branches]
    comp["enable_era_popularity"] = variant.lookups
    comp["enable_resolved_artist_discography"] = variant.lookups
    comp["enable_similar_artist_anchors"] = variant.similar_artist_anchors
    comp["similar_artist_anchor_intents"] = list(variant.similar_artist_intents)
    comp["similar_artist_anchor_topk"] = 3
    comp["similar_artist_max_artists"] = 5
    comp["centroid_only_branches"] = []
    if variant.centroid:
        comp["centroid_only_branches"] = [
            {
                "vector_field": CLAP_AUDIO,
                "weight": variant.centroid_weight,
                "topk": 1000,
                "distance_type": "cosine",
            },
            {
                "vector_field": "image_siglip2",
                "weight": variant.centroid_weight,
                "topk": 1000,
                "distance_type": "cosine",
            },
            {
                "vector_field": "cf_bpr",
                "weight": variant.centroid_weight,
                "topk": 1000,
                "distance_type": "cosine",
            },
        ]
    return qu_kwargs


def _state_from_audit(row: dict[str, Any]):
    raw = row["new_state"]
    v1_payload = {key: raw[key] for key in V1_KEYS if key in raw}
    return project_v1_to_v0plus(ConversationStateV1.model_validate(v1_payload))


def _compile_variant(qu, row: dict[str, Any], target: str) -> dict[str, Any]:
    state = _state_from_audit(row)
    played = [tf.track_id for tf in state.track_feedback]
    rs = qu.resolver.resolve(state, played_track_ids=played)
    result = qu.compiler._compile(rs, user_id=None)
    final_rank = _rank(result.ranked, target)
    fused_rank = _rank([track_id for track_id, _score in result.fused], target)
    best_branch, best_branch_rank = _branch_rank(result.branch_pools, target)
    out: dict[str, Any] = {
        "final_rank": final_rank,
        "fused_rank": fused_rank,
        "best_branch": best_branch,
        "best_branch_rank": best_branch_rank,
        "n_branch_pools": len(result.branch_pools),
    }
    for k in KS:
        out[f"final@{k}"] = final_rank is not None and final_rank <= k
        out[f"union@{k}"] = _union_hit(result.branch_pools, target, k)
    return out


def _summary(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    scoped = [row for row in rows if row["variant"] == variant]
    n = len(scoped)
    out: dict[str, Any] = {"variant": variant, "n": n}
    if n == 0:
        return out
    for k in KS:
        out[f"final@{k}"] = sum(row[f"final@{k}"] for row in scoped) / n
        out[f"union@{k}"] = sum(row[f"union@{k}"] for row in scoped) / n
        out[f"best_branch@{k}"] = (
            sum((row["best_branch_rank"] or 10**9) <= k for row in scoped) / n
        )
    return out


def _baseline_union_at(baseline: dict[str, Any], k: int) -> bool | None:
    direct = baseline.get(f"union{k}")
    if direct is not None:
        return bool(direct)
    # The saved packs predate union@50. When union@20 and union@100 agree for a
    # row, monotonicity makes union@50 inferable for that row.
    if k == 50 and baseline.get("union20") is not None and baseline.get("union100") is not None:
        u20 = bool(baseline["union20"])
        u100 = bool(baseline["union100"])
        if u20 == u100:
            return u20
    return None


def _baseline_summary(turn_meta: dict[str, dict[str, Any]], sample_ids: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"variant": "official_trace_baseline", "n": len(sample_ids)}
    for k in KS:
        union_values = [
            _baseline_union_at(turn_meta[sid]["baseline"], k) for sid in sample_ids
        ]
        if all(value is not None for value in union_values):
            out[f"union@{k}"] = sum(bool(value) for value in union_values) / len(sample_ids)
        out[f"final@{k}"] = sum(
            (turn_meta[sid]["baseline"].get("final_rank") or 10**9) <= k
            for sid in sample_ids
        ) / len(sample_ids)
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "sample_id",
        "pack",
        "variant",
        "gt_track",
        "gt_artist",
        "final_rank",
        "fused_rank",
        "best_branch_rank",
        "best_branch",
        "n_branch_pools",
    ] + [f"union@{k}" for k in KS] + [f"final@{k}" for k in KS]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    if value is None:
        return ""
    return str(value)


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# State V1 Retriever Matrix",
        "",
        "Focused candidate-generation matrix over saved V1 extraction states.",
        "The main gate is branch union@20/50; RRF/final ranking is reported separately.",
        "",
        "## Summary",
        "",
        "| Variant | n | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]:
        lines.append(
            "| `{variant}` | {n} | {final20} | {final50} | {union20} | {union50} | {union100} | {union200} | {union1000} | {best50} |".format(
                variant=row["variant"],
                n=row["n"],
                final20=_fmt(row.get("final@20")),
                final50=_fmt(row.get("final@50")),
                union20=_fmt(row.get("union@20")),
                union50=_fmt(row.get("union@50")),
                union100=_fmt(row.get("union@100")),
                union200=_fmt(row.get("union@200")),
                union1000=_fmt(row.get("union@1000")),
                best50=_fmt(row.get("best_branch@50")),
            )
        )

    lines.extend([
        "",
        "## Per-Sample Rows",
        "",
        "| Sample | Pack | GT | Variant | final rank | best branch rank | best branch | union@20 | union@50 | union@100 |",
        "|---|---|---|---|---:|---:|---|---:|---:|---:|",
    ])
    for row in payload["rows"]:
        lines.append(
            "| `{sample_id}` | `{pack}` | {gt_track} / {gt_artist} | `{variant}` | {final_rank} | {best_branch_rank} | `{best_branch}` | {u20} | {u50} | {u100} |".format(
                sample_id=row["sample_id"],
                pack=row["pack"],
                gt_track=row["gt_track"],
                gt_artist=row["gt_artist"],
                variant=row["variant"],
                final_rank=row["final_rank"] or "",
                best_branch_rank=row["best_branch_rank"] or "",
                best_branch=row["best_branch"] or "",
                u20=int(bool(row["union@20"])),
                u50=int(bool(row["union@50"])),
                u100=int(bool(row["union@100"])),
            )
        )
    path.write_text("\n".join(lines) + "\n")


def _encoder_has_vllm_endpoint(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("vllm_endpoint"))


def _qu_kwargs_has_vllm_endpoint(qu_kwargs: dict[str, Any]) -> bool:
    if _encoder_has_vllm_endpoint(qu_kwargs.get("encoder")):
        return True
    encoders = qu_kwargs.get("encoders")
    if not isinstance(encoders, dict):
        return False
    return any(_encoder_has_vllm_endpoint(value) for value in encoders.values())


def _resolve_vllm_endpoints_in_qu_kwargs(qu_kwargs: dict[str, Any]) -> None:
    if not _qu_kwargs_has_vllm_endpoint(qu_kwargs):
        return
    import importlib.util

    vllm_path = Path(__file__).resolve().parent.parent / "modal" / "vllm_serve.py"
    spec = importlib.util.spec_from_file_location("mcrs_vllm_serve", vllm_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load vLLM endpoint resolver from {vllm_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.resolve_vllm_endpoints_in_qu_kwargs(qu_kwargs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--lancedb-uri", type=Path, default=DEFAULT_MAIN_LANCEDB)
    parser.add_argument("--audit-jsonl", type=Path)
    parser.add_argument("--pack-json", type=Path)
    parser.add_argument("--variant", action="append", dest="variants")
    parser.add_argument("--sample-id", action="append", dest="sample_ids")
    parser.add_argument("--sample-id-file", type=Path)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()

    audit_path = args.audit_jsonl or (
        args.analysis_dir / "state_v1_goal_current_all110_reprojected_audit.jsonl"
    )
    pack_path = args.pack_json or (args.analysis_dir / "state_experiment_pack.json")
    if not audit_path.exists():
        raise SystemExit(f"missing audit path: {audit_path}")
    if not pack_path.exists():
        raise SystemExit(f"missing pack path: {pack_path}")
    if not args.lancedb_uri.exists():
        raise SystemExit(f"missing LanceDB URI: {args.lancedb_uri}")

    unknown_variants = sorted(set(args.variants or ()) - set(VARIANTS))
    if unknown_variants:
        raise SystemExit(
            f"unknown variants {unknown_variants}; available: {sorted(VARIANTS)}"
        )

    audit_rows = _load_jsonl(audit_path)
    pack = json.loads(pack_path.read_text())
    turn_meta = {turn["sample_id"]: turn for turn in pack["turns"]}
    sample_ids: list[str] = []
    if args.sample_ids:
        sample_ids.extend(args.sample_ids)
    if args.sample_id_file:
        sample_ids.extend(
            line.strip()
            for line in args.sample_id_file.read_text().splitlines()
            if line.strip()
        )
    if not sample_ids:
        sample_ids = list(turn_meta)
    if args.limit is not None:
        sample_ids = sample_ids[: args.limit]
    missing = [sid for sid in sample_ids if sid not in audit_rows or sid not in turn_meta]
    if missing:
        raise SystemExit(f"sample ids missing from audit/pack: {missing}")

    variant_names = args.variants or list(DEFAULT_VARIANTS)
    base_cfg = OmegaConf.load(args.config)
    base_qu_kwargs = OmegaConf.to_container(base_cfg["qu_kwargs"], resolve=True)
    _resolve_vllm_endpoints_in_qu_kwargs(base_qu_kwargs)

    rows: list[dict[str, Any]] = []
    for variant_name in variant_names:
        variant = VARIANTS[variant_name]
        print(f"building variant: {variant.name}", flush=True)
        qu_kwargs = _variant_qu_kwargs(base_qu_kwargs, variant, args.lancedb_uri)
        qu = build_v0plus_compiler_qu(qu_kwargs)
        for idx, sid in enumerate(sample_ids, start=1):
            meta = turn_meta[sid]
            print(f"  [{idx}/{len(sample_ids)}] {sid}", flush=True)
            result = _compile_variant(qu, audit_rows[sid], meta["gt_track_id"])
            rows.append(
                {
                    "sample_id": sid,
                    "pack": meta["pack"],
                    "variant": variant.name,
                    "gt_track": meta["gt_track"],
                    "gt_artist": meta["gt_artist"],
                    **result,
                }
            )

    summary = [_baseline_summary(turn_meta, sample_ids)]
    summary.extend(_summary(rows, name) for name in variant_names)
    payload = {
        "samples": sample_ids,
        "variants": variant_names,
        "summary": summary,
        "rows": rows,
    }

    output_json = args.output_json or args.analysis_dir / "state_v1_retriever_matrix.json"
    output_md = args.output_md or args.analysis_dir / "state_v1_retriever_matrix.md"
    output_csv = args.output_csv or args.analysis_dir / "state_v1_retriever_matrix.csv"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _write_csv(output_csv, rows)
    _write_report(output_md, payload)
    print(
        json.dumps(
            {
                "summary": payload["summary"],
                "json": str(output_json),
                "md": str(output_md),
                "csv": str(output_csv),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
