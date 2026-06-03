"""
Bulk-download artifacts from the music-crs-results Modal volume.

Examples:
    # Download one current run
    python modal/download_results.py --tid v0plus_compiler_all_retrievers_devset

    # Download all missing remote artifacts into evaluator/exp
    python modal/download_results.py

    # Preview the transfer first
    python modal/download_results.py --dry-run --verbose
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path


RESULTS_VOLUME_NAME = "music-crs-results"
SUPPORTED_ROOTS = ("inference", "scores", "ground_truth")
KIND_ALIASES = {
    "all": {"inference", "trace", "scores", "ground-truth"},
    "inference": {"inference"},
    "traces": {"trace"},
    "scores": {"scores"},
    "ground-truth": {"ground-truth"},
}

# Run-scoped shard suffix, e.g. ".run_20260603T074512Z-a3f91c.shard_0".
# run_id contains no dots (UTC stamp + hex, hyphen-joined); tids contain no dots.
_RUN_SHARD_RE = re.compile(r"\.run_(?P<run_id>[^.]+)\.shard_\d+$")


def _strip_run_shard(stem: str) -> str:
    return _RUN_SHARD_RE.sub("", stem)


def _run_id_from_name(name: str) -> str | None:
    stem = name
    for suffix in ("_trace.json", "_rewrite_audit.jsonl", "_rewrite_stats.json", ".json"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    match = _RUN_SHARD_RE.search(stem)
    return match.group("run_id") if match else None


@dataclass(frozen=True)
class RemoteArtifact:
    remote_path: str
    size: int
    kind: str
    split: str | None
    tid: str | None
    run_id: str | None = None


@dataclass(frozen=True)
class SyncSummary:
    planned: int
    downloaded: int
    skipped: int
    total_bytes: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download artifacts from the music-crs-results Modal volume.")
    parser.add_argument(
        "--tid",
        action="append",
        default=[],
        help="Task ID to download. May be passed multiple times.",
    )
    parser.add_argument(
        "--tid-file",
        help="Optional file containing one tid per line.",
    )
    parser.add_argument(
        "--split",
        action="append",
        default=[],
        help="Dataset split filter. May be passed multiple times or as a comma-separated list.",
    )
    parser.add_argument(
        "--kind",
        action="append",
        default=[],
        help="Artifact kind filter: inference, traces, scores, ground-truth, all. "
        "May be passed multiple times or as a comma-separated list.",
    )
    parser.add_argument(
        "--out-dir",
        default="evaluator/exp",
        help="Local output base directory. Defaults to evaluator/exp.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Only download artifacts whose filename carries this run id "
             "(run-scoped shard files: {tid}.run_{run_id}.shard_N.json).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download files even if they already exist locally.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be downloaded without writing files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print discovery and per-file progress details.",
    )
    return parser


def _parse_csv_args(values: list[str]) -> set[str]:
    parsed: set[str] = set()
    for value in values:
        for item in value.split(","):
            cleaned = item.strip()
            if cleaned:
                parsed.add(cleaned)
    return parsed


def _load_tids(cli_tids: list[str], tid_file: str | None) -> set[str] | None:
    tids = set(cli_tids)
    if tid_file:
        for line in Path(tid_file).read_text(encoding="utf-8").splitlines():
            cleaned = line.strip()
            if cleaned:
                tids.add(cleaned)
    return tids or None


def _normalize_kinds(kind_values: set[str]) -> set[str]:
    if not kind_values:
        return set(KIND_ALIASES["all"])
    normalized: set[str] = set()
    for kind in kind_values:
        if kind not in KIND_ALIASES:
            raise ValueError(f"Unsupported kind: {kind}")
        normalized.update(KIND_ALIASES[kind])
    return normalized


def _entry_path(entry) -> str:
    return str(getattr(entry, "path"))


def _entry_size(entry) -> int:
    return int(getattr(entry, "size", 0))


def _entry_is_file(entry) -> bool:
    entry_type = getattr(entry, "type", None)
    if entry_type is not None:
        type_name = getattr(entry_type, "name", str(entry_type))
        if type_name == "FILE":
            return True
        if type_name == "DIRECTORY":
            return False
    return "." in Path(_entry_path(entry)).name


def _maybe_listdir(volume, path: str, verbose: bool):
    try:
        return volume.listdir(path)
    except Exception as exc:
        if verbose:
            print(f"Skipping missing remote directory: {path} ({exc})")
        return None


def _artifact_kind(remote_path: str) -> str | None:
    path = Path(remote_path)
    top = path.parts[0]
    if top == "inference":
        if (
            path.name.endswith("_trace.json")
            or path.name.endswith("_rewrite_audit.jsonl")
            or path.name.endswith("_rewrite_stats.json")
        ):
            return "trace"
        if path.suffix == ".json":
            return "inference"
        return None
    if top == "scores" and path.suffix == ".json":
        return "scores"
    if top == "ground_truth":
        return "ground-truth"
    return None


def _artifact_tid(remote_path: str, kind: str) -> str | None:
    name = Path(remote_path).name
    if kind == "trace":
        for suffix in ("_trace.json", "_rewrite_audit.jsonl", "_rewrite_stats.json"):
            if name.endswith(suffix):
                return _strip_run_shard(name[: -len(suffix)])
    if kind in {"inference", "scores"} and name.endswith(".json"):
        return _strip_run_shard(name[:-5])
    return None


def _artifact_split(remote_path: str) -> str | None:
    parts = Path(remote_path).parts
    if len(parts) >= 3 and parts[0] in {"inference", "scores"}:
        return parts[1]
    return None


def discover_remote_artifacts(volume, splits: set[str] | None, verbose: bool) -> list[RemoteArtifact]:
    artifacts: list[RemoteArtifact] = []

    inference_splits: list[str] = []
    inference_entries = _maybe_listdir(volume, "/inference", verbose)
    if inference_entries:
        for entry in inference_entries:
            split_name = Path(_entry_path(entry)).name
            if not splits or split_name in splits:
                inference_splits.append(split_name)

    score_splits: list[str] = []
    score_entries = _maybe_listdir(volume, "/scores", verbose)
    if score_entries:
        for entry in score_entries:
            split_name = Path(_entry_path(entry)).name
            if not splits or split_name in splits:
                score_splits.append(split_name)

    for split_name in sorted(set(inference_splits)):
        entries = _maybe_listdir(volume, f"/inference/{split_name}", verbose)
        if not entries:
            continue
        for entry in entries:
            if not _entry_is_file(entry):
                continue
            remote_path = _entry_path(entry)
            kind = _artifact_kind(remote_path)
            if kind is None:
                continue
            artifacts.append(
                RemoteArtifact(
                    remote_path=remote_path,
                    size=_entry_size(entry),
                    kind=kind,
                    split=split_name,
                    tid=_artifact_tid(remote_path, kind),
                    run_id=_run_id_from_name(Path(remote_path).name),
                )
            )

    for split_name in sorted(set(score_splits)):
        entries = _maybe_listdir(volume, f"/scores/{split_name}", verbose)
        if not entries:
            continue
        for entry in entries:
            if not _entry_is_file(entry):
                continue
            remote_path = _entry_path(entry)
            kind = _artifact_kind(remote_path)
            if kind != "scores":
                continue
            artifacts.append(
                RemoteArtifact(
                    remote_path=remote_path,
                    size=_entry_size(entry),
                    kind=kind,
                    split=split_name,
                    tid=_artifact_tid(remote_path, kind),
                    run_id=_run_id_from_name(Path(remote_path).name),
                )
            )

    ground_truth_entries = _maybe_listdir(volume, "/ground_truth", verbose)
    if ground_truth_entries:
        for entry in ground_truth_entries:
            if not _entry_is_file(entry):
                continue
            remote_path = _entry_path(entry)
            kind = _artifact_kind(remote_path)
            if kind != "ground-truth":
                continue
            artifacts.append(
                RemoteArtifact(
                    remote_path=remote_path,
                    size=_entry_size(entry),
                    kind=kind,
                    split=_artifact_split(remote_path),
                    tid=None,
                )
            )

    return sorted(artifacts, key=lambda artifact: artifact.remote_path)


def select_artifacts(
    artifacts: list[RemoteArtifact],
    tids: set[str] | None,
    kinds: set[str],
    overwrite: bool,
    out_dir: Path,
    run_id: str | None = None,
) -> list[RemoteArtifact]:
    selected: list[RemoteArtifact] = []
    for artifact in artifacts:
        if artifact.kind not in kinds:
            continue
        if tids is not None and artifact.tid not in tids:
            continue
        if run_id is not None and artifact.run_id != run_id:
            continue
        local_path = out_dir / artifact.remote_path
        if not overwrite and local_path.exists():
            continue
        selected.append(artifact)
    return selected


def sync_artifacts(volume, artifacts: list[RemoteArtifact], out_dir: Path, dry_run: bool, verbose: bool) -> SyncSummary:
    total_bytes = sum(artifact.size for artifact in artifacts)
    if dry_run:
        print(f"Dry run: {len(artifacts)} file(s), {total_bytes} bytes")
        for artifact in artifacts:
            print(f"  {artifact.remote_path} -> {out_dir / artifact.remote_path}")
        return SyncSummary(planned=len(artifacts), downloaded=0, skipped=0, total_bytes=total_bytes)

    downloaded = 0
    for artifact in artifacts:
        local_path = out_dir / artifact.remote_path
        part_path = local_path.with_name(f"{local_path.name}.part")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if part_path.exists():
            part_path.unlink()

        if verbose:
            print(f"Downloading {artifact.remote_path} -> {local_path}")

        with open(part_path, "wb") as handle:
            for chunk in volume.read_file(artifact.remote_path):
                handle.write(chunk)

        os.replace(part_path, local_path)
        downloaded += 1

    print(f"Downloaded {downloaded} file(s) ({total_bytes} bytes) to {out_dir}")
    return SyncSummary(planned=len(artifacts), downloaded=downloaded, skipped=0, total_bytes=total_bytes)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    splits = _parse_csv_args(args.split) or None
    kind_values = _parse_csv_args(args.kind)
    kinds = _normalize_kinds(kind_values)
    tids = _load_tids(args.tid, args.tid_file)
    out_dir = Path(args.out_dir)

    import modal

    volume = modal.Volume.from_name(RESULTS_VOLUME_NAME)
    artifacts = discover_remote_artifacts(volume, splits=splits, verbose=args.verbose)
    selected = select_artifacts(
        artifacts,
        tids=tids,
        kinds=kinds,
        overwrite=args.overwrite,
        out_dir=out_dir,
        run_id=args.run_id,
    )
    if not selected:
        print("No matching artifacts to download.")
        return 0

    sync_artifacts(volume, selected, out_dir=out_dir, dry_run=args.dry_run, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
