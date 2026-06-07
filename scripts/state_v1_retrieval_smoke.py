#!/usr/bin/env python
"""Small retrieval smoke for ConversationStateV1 projections.

This intentionally avoids paid LLM and text-embedding calls. It reuses a saved
live V1 extraction audit, projects those facts through the current bridge, and
compiles a focused set of turns through local retriever variants:

- tags_only: BM25 + lookup pools, no centroid anchors.
- centroid_no_style: adds local centroid branches from played/reference tracks.
- centroid_style_safe: enables similar-artist centroid anchors on the current
  production-safe intent gate.
- centroid_style_broad: same as above, but also allows refinement turns so we
  can see whether the gate is leaving useful anchors unused.

The goal is not official devset scoring. It is a cheap answer to: "does the
cleaner state get to retriever-consumable candidate pools, and which retriever
consumption gap remains?"
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

import yaml

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
DEFAULT_MAIN_LANCEDB = Path(
    "/Users/npatta01/data/projects/music-conversational-music-recomender-2026/cache/lancedb"
)

DEFAULT_SAMPLE_IDS = [
    "0b9d547f-e748-464a-90e2-2199149f915c::t6",
    "5f085552-b56b-440e-830b-b4e40b58f854::t6",
    "0858f444-c9af-4f08-a9fc-2a731a24182b::t5",
    "88beb200-0334-4aba-be15-8e1303725766::t6",
    "daeef24e-b041-4140-9101-882820c63408::t7",
    "a930da0d-07f1-46c6-909d-e4fd95ae1148::t6",
    "b466a64b-b3cc-4c62-8a70-8261434f915f::t2",
    "d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5",
    "f2d85aa5-2086-4b1e-9974-d188c43621db::t8",
    "1c567917-f931-4609-9695-a9c0f8e39f3d::t2",
    "a9b423bf-d05c-418d-98af-2a3b1e1d7917::t1",
    "737a65cf-9c45-4b1d-910d-2f1f1ef5eab7::t8",
]


class DisabledEmbeddingClient:
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError(
            "state_v1_retrieval_smoke disabled text embedding calls; "
            "enable_dense must stay false"
        )


@dataclass(frozen=True)
class Variant:
    name: str
    centroid: bool
    similar_artist_anchors: bool
    similar_artist_intents: tuple[str, ...] = ("open_explore", "pivot")
    centroid_weight: float = 1.0


VARIANTS = [
    Variant("tags_only", centroid=False, similar_artist_anchors=False),
    Variant("centroid_no_style", centroid=True, similar_artist_anchors=False),
    Variant("centroid_style_safe", centroid=True, similar_artist_anchors=True),
    Variant(
        "centroid_style_broad",
        centroid=True,
        similar_artist_anchors=True,
        similar_artist_intents=("open_explore", "pivot", "refinement"),
    ),
    Variant(
        "centroid_style_broad_w3",
        centroid=True,
        similar_artist_anchors=True,
        similar_artist_intents=("open_explore", "pivot", "refinement"),
        centroid_weight=3.0,
    ),
    Variant(
        "centroid_style_broad_w5",
        centroid=True,
        similar_artist_anchors=True,
        similar_artist_intents=("open_explore", "pivot", "refinement"),
        centroid_weight=5.0,
    ),
]


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
    return any(target in {track_id for track_id, _score in pool.hits[:k]} for pool in branch_pools)


def _variant_qu_kwargs(base_qu_kwargs: dict[str, Any], variant: Variant, lancedb_uri: Path) -> dict[str, Any]:
    qu_kwargs = copy.deepcopy(base_qu_kwargs)
    qu_kwargs.setdefault("lancedb", {})
    qu_kwargs["lancedb"]["db_uri"] = str(lancedb_uri)
    qu_kwargs["lancedb"]["eager_vector_fields"] = [
        "audio_laion_clap",
        "image_siglip2",
        "cf_bpr",
    ]

    comp = qu_kwargs.setdefault("compiler", {})
    comp["enable_dense"] = False
    comp["dense_branches"] = []
    comp["branch_trace_topk"] = 1000
    comp["bm25_k"] = 1000
    comp["final_topk"] = 1000
    comp["enable_era_popularity"] = True
    comp["enable_resolved_artist_discography"] = True
    comp["enable_similar_artist_anchors"] = variant.similar_artist_anchors
    comp["similar_artist_anchor_intents"] = list(variant.similar_artist_intents)
    comp["similar_artist_anchor_topk"] = 3
    comp["similar_artist_max_artists"] = 5
    if variant.centroid:
        comp["centroid_only_branches"] = [
            {
                "vector_field": "audio_laion_clap",
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
    else:
        comp["centroid_only_branches"] = []
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
    status_counts: dict[str, int] = {}
    for status in result.branch_status.values():
        key = "fired" if status.get("fired") else status.get("skip_reason", "skipped")
        status_counts[key] = status_counts.get(key, 0) + 1
    return {
        "final_rank": final_rank,
        "fused_rank": fused_rank,
        "best_branch": best_branch,
        "best_branch_rank": best_branch_rank,
        "union20": _union_hit(result.branch_pools, target, 20),
        "union100": _union_hit(result.branch_pools, target, 100),
        "union200": _union_hit(result.branch_pools, target, 200),
        "union1000": _union_hit(result.branch_pools, target, 1000),
        "n_branch_pools": len(result.branch_pools),
        "branch_status_counts": status_counts,
    }


def _summary(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    scoped = [row for row in rows if row["variant"] == variant]
    n = len(scoped)
    if n == 0:
        return {"variant": variant, "n": 0}
    return {
        "variant": variant,
        "n": n,
        "final@20": sum((row["final_rank"] or 10**9) <= 20 for row in scoped) / n,
        "final@100": sum((row["final_rank"] or 10**9) <= 100 for row in scoped) / n,
        "union@20": sum(row["union20"] for row in scoped) / n,
        "union@100": sum(row["union100"] for row in scoped) / n,
        "union@200": sum(row["union200"] for row in scoped) / n,
        "union@1000": sum(row["union1000"] for row in scoped) / n,
        "best_branch@100": sum((row["best_branch_rank"] or 10**9) <= 100 for row in scoped) / n,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# State V1 Retrieval Smoke",
        "",
        "This is a focused, local smoke test. It uses saved live V1 extraction output and local LanceDB retrieval. Dense text embedding branches are disabled to avoid paid embedding calls; the tested retrievers are BM25, lookup pools, era-popularity, and local centroid branches.",
        "",
        "## Summary",
        "",
        "| Variant | n | final@20 | final@100 | union@20 | union@100 | union@200 | union@1000 | best branch@100 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]:
        lines.append(
            "| `{variant}` | {n} | {final20:.3f} | {final100:.3f} | {union20:.3f} | {union100:.3f} | {union200:.3f} | {union1000:.3f} | {best100:.3f} |".format(
                variant=row["variant"],
                n=row["n"],
                final20=row.get("final@20", 0.0),
                final100=row.get("final@100", 0.0),
                union20=row.get("union@20", 0.0),
                union100=row.get("union@100", 0.0),
                union200=row.get("union@200", 0.0),
                union1000=row.get("union@1000", 0.0),
                best100=row.get("best_branch@100", 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Read",
            "",
            "- If `centroid_style_*` improves over `centroid_no_style`, the remaining gap is retriever consumption of V1 style-reference anchors.",
            "- If none of these variants improve, the next candidate-generation work likely needs text dense query templates, branch weighting, or a larger all-retrievers smoke rather than more state extraction.",
            "- Compare these rows against each turn's official all-retrievers baseline only directionally; this smoke disables paid dense text branches.",
            "",
            "## Per-Sample Results",
            "",
            "| Sample | Pack | GT | Official baseline | Variant | final rank | fused rank | best branch rank | best branch | union@20 | union@100 | union@200 |",
            "|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|",
        ]
    )
    turn_meta = payload["turn_meta"]
    for row in payload["rows"]:
        meta = turn_meta[row["sample_id"]]
        baseline = meta["baseline"]
        official = (
            f"final={baseline.get('final_rank')} fused={baseline.get('fused_rank')} "
            f"best={baseline.get('best_branch_rank')}:{baseline.get('best_branch')}"
        )
        lines.append(
            "| `{sample}` | `{pack}` | {gt} | {official} | `{variant}` | {final} | {fused} | {best_rank} | `{best}` | {u20} | {u100} | {u200} |".format(
                sample=row["sample_id"],
                pack=meta["pack"],
                gt=f"{meta['gt_track']} / {meta['gt_artist']}",
                official=official,
                variant=row["variant"],
                final=row["final_rank"] or "",
                fused=row["fused_rank"] or "",
                best_rank=row["best_branch_rank"] or "",
                best=row["best_branch"] or "",
                u20=int(row["union20"]),
                u100=int(row["union100"]),
                u200=int(row["union200"]),
            )
        )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--lancedb-uri", type=Path, default=DEFAULT_MAIN_LANCEDB)
    parser.add_argument("--sample-id", action="append", dest="sample_ids")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    audit_path = args.analysis_dir / "state_v1_bridge_deepseek_full56_audit_reprojected.jsonl"
    pack_path = args.analysis_dir / "state_role_v2_pack56.json"
    if not audit_path.exists():
        raise SystemExit(f"missing audit path: {audit_path}")
    if not pack_path.exists():
        raise SystemExit(f"missing pack path: {pack_path}")
    if not args.lancedb_uri.exists():
        raise SystemExit(f"missing LanceDB URI: {args.lancedb_uri}")

    audit_rows = _load_jsonl(audit_path)
    pack = json.loads(pack_path.read_text())
    turn_meta = {turn["sample_id"]: turn for turn in pack["turns"]}

    sample_ids = args.sample_ids or DEFAULT_SAMPLE_IDS
    if args.limit is not None:
        sample_ids = sample_ids[: args.limit]
    missing = [sid for sid in sample_ids if sid not in audit_rows or sid not in turn_meta]
    if missing:
        raise SystemExit(f"sample ids missing from audit/pack: {missing}")

    base_cfg = yaml.safe_load(args.config.read_text())
    base_qu_kwargs = base_cfg["qu_kwargs"]

    rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        print(f"building variant: {variant.name}", flush=True)
        qu_kwargs = _variant_qu_kwargs(base_qu_kwargs, variant, args.lancedb_uri)
        qu = build_v0plus_compiler_qu(
            qu_kwargs,
            _overrides={"encoders": {"default": DisabledEmbeddingClient()}},
        )
        for idx, sid in enumerate(sample_ids, start=1):
            meta = turn_meta[sid]
            print(f"  [{idx}/{len(sample_ids)}] {sid}", flush=True)
            result = _compile_variant(qu, audit_rows[sid], meta["gt_track_id"])
            rows.append(
                {
                    "sample_id": sid,
                    "variant": variant.name,
                    **result,
                }
            )

    payload = {
        "samples": sample_ids,
        "variants": [variant.name for variant in VARIANTS],
        "summary": [_summary(rows, variant.name) for variant in VARIANTS],
        "rows": rows,
        "turn_meta": {
            sid: {
                "pack": turn_meta[sid]["pack"],
                "gt_track_id": turn_meta[sid]["gt_track_id"],
                "gt_track": turn_meta[sid]["gt_track"],
                "gt_artist": turn_meta[sid]["gt_artist"],
                "baseline": turn_meta[sid]["baseline"],
            }
            for sid in sample_ids
        },
    }

    output_json = args.output_json or args.analysis_dir / "state_v1_retrieval_smoke.json"
    output_md = args.output_md or args.analysis_dir / "state_v1_retrieval_smoke.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _write_report(output_md, payload)

    print(json.dumps({"summary": payload["summary"], "json": str(output_json), "md": str(output_md)}, indent=2))


if __name__ == "__main__":
    main()
