"""Dry-run-first cleanup for old Music CRS Modal artifacts.

Only allowlisted old v0plus/v9 result and training scratch paths are eligible.
The script never deletes ground truth, LanceDB, tag indexes, q06 memos, raw
message stores, or whole Modal volumes.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from download_results import (
    RemoteArtifact,
    _entry_path,
    _maybe_listdir,
    discover_remote_artifacts,
)

RESULTS_VOLUME_NAME = "music-crs-results"
CACHE_VOLUME_NAME = "music-crs-cache"

OLD_V0PLUS_TIDS = {
    "v0plus_compiler_pruned_resolved_tags_devset",
    "v0plus_compiler_devset_rr2",
    "v0plus_compiler_blindset_A",
    "v0plus_compiler_blindset_A_rr2",
}


@dataclass(frozen=True)
class CleanupAction:
    volume_name: str
    remote_path: str
    recursive: bool = False


def _family_tids(family: str) -> set[str]:
    if family != "old-v0plus":
        raise ValueError(f"Unsupported cleanup family: {family!r}")
    return set(OLD_V0PLUS_TIDS)


def select_result_cleanup(
    artifacts: list[RemoteArtifact],
    *,
    family: str,
) -> list[CleanupAction]:
    tids = _family_tids(family)
    actions: list[CleanupAction] = []
    for artifact in artifacts:
        if artifact.kind not in {"inference", "trace", "scores"}:
            continue
        if artifact.tid not in tids:
            continue
        actions.append(CleanupAction(RESULTS_VOLUME_NAME, artifact.remote_path, False))
    return actions


def plan_training_cleanup(*, family: str) -> list[CleanupAction]:
    _family_tids(family)
    return [
        CleanupAction(CACHE_VOLUME_NAME, "rerank/features_v9", True),
        CleanupAction(CACHE_VOLUME_NAME, "rerank/constraint_features.parquet", False),
        CleanupAction(CACHE_VOLUME_NAME, "rerank/label_weights_v9.parquet", False),
        CleanupAction(CACHE_VOLUME_NAME, "rerank/train_v9", True),
    ]


def filter_existing_training_cleanup(
    volume,
    actions: list[CleanupAction],
    *,
    verbose: bool,
) -> list[CleanupAction]:
    entries_by_parent: dict[str, set[str]] = {}
    existing: list[CleanupAction] = []
    for action in actions:
        parent = Path(action.remote_path).parent
        parent_path = "/" if str(parent) == "." else f"/{parent.as_posix()}"
        if parent_path not in entries_by_parent:
            entries = _maybe_listdir(volume, parent_path, verbose)
            entries_by_parent[parent_path] = {
                _entry_path(entry).lstrip("/") for entry in (entries or [])
            }
        if action.remote_path.lstrip("/") in entries_by_parent[parent_path]:
            existing.append(action)
    return existing


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", default="old-v0plus", choices=["old-v0plus"])
    parser.add_argument("--include-results", action="store_true")
    parser.add_argument("--include-training", action="store_true")
    parser.add_argument("--delete", action="store_true", help="Actually remove planned paths.")
    parser.add_argument(
        "--confirm-v10-validated",
        action="store_true",
        help="Required with --delete after v10 inference/evaluation has been validated.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def _discover_result_actions(family: str, verbose: bool) -> list[CleanupAction]:
    import modal

    volume = modal.Volume.from_name(RESULTS_VOLUME_NAME)
    artifacts = discover_remote_artifacts(volume, splits=None, verbose=verbose)
    return select_result_cleanup(artifacts, family=family)


def _discover_training_actions(family: str, verbose: bool) -> list[CleanupAction]:
    import modal

    volume = modal.Volume.from_name(CACHE_VOLUME_NAME)
    return filter_existing_training_cleanup(
        volume,
        plan_training_cleanup(family=family),
        verbose=verbose,
    )


def _remove(action: CleanupAction) -> None:
    import modal

    volume = modal.Volume.from_name(action.volume_name)
    volume.remove_file(action.remote_path, recursive=action.recursive)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.delete and not args.confirm_v10_validated:
        raise SystemExit(
            "--delete requires --confirm-v10-validated after v10 inference/evaluation validation"
        )
    if not args.include_results and not args.include_training:
        args.include_results = True
        args.include_training = True

    actions: list[CleanupAction] = []
    if args.include_results:
        actions.extend(_discover_result_actions(args.family, args.verbose))
    if args.include_training:
        actions.extend(_discover_training_actions(args.family, args.verbose))

    if not actions:
        print("No cleanup actions matched.")
        return 0

    mode = "DELETE" if args.delete else "DRY RUN"
    print(f"{mode}: {len(actions)} cleanup action(s)")
    for action in actions:
        flag = " -r" if action.recursive else ""
        print(f"  modal volume rm{flag} {action.volume_name} {action.remote_path}")

    if not args.delete:
        print(
            "No files deleted. Re-run with --delete --confirm-v10-validated "
            "after v10 validation to remove these allowlisted paths."
        )
        return 0

    for action in actions:
        _remove(action)
    print(f"Deleted {len(actions)} allowlisted path(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
