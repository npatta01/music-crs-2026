"""Package the file-per-turn state extraction cache for a GitHub release.

The release asset is intentionally generated from the ignored shared cache
tree, not committed to Git. It unpacks into repo root as:

    cache/state_extraction/...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcrs.conversation_state.schema import ConversationStateV0Plus


DEFAULT_SPLITS = ("blindset_A", "blindset_B", "devset", "trainset")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_override(path: Path) -> bool:
    return path.name.endswith("_override.json")


def _state_files(split_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in split_dir.glob("*/turn_*.json")
        if path.is_file()
    )


def _validate_state_file(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "state" not in payload:
        raise ValueError(f"{path} must contain a top-level 'state'")
    ConversationStateV0Plus.model_validate(payload["state"])


def _split_manifest(cache_root: Path, split: str, *, validate: bool) -> dict[str, Any]:
    split_dir = cache_root / split
    if not split_dir.exists():
        raise FileNotFoundError(f"missing state cache split: {split_dir}")
    files = _state_files(split_dir)
    if validate:
        for path in files:
            _validate_state_file(path)
    raw_files = [path for path in files if not _is_override(path)]
    override_files = [path for path in files if _is_override(path)]
    sessions = {path.parent.name for path in raw_files}
    turn_numbers = sorted(
        {
            int(path.stem.removeprefix("turn_").removesuffix("_override"))
            for path in files
        }
    )
    return {
        "split": split,
        "sessions": len(sessions),
        "raw_files": len(raw_files),
        "override_files": len(override_files),
        "total_json_files": len(files),
        "turn_numbers_observed": turn_numbers,
    }


def _write_manifest(
    cache_root: Path,
    *,
    version: str,
    splits: list[str],
    validate: bool,
) -> dict[str, Any]:
    split_entries = [
        _split_manifest(cache_root, split, validate=validate)
        for split in splits
    ]
    manifest = {
        "version": version,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "layout": "cache/state_extraction/<split>/<session_id>/turn_<turn_number>.json",
        "override_layout": (
            "cache/state_extraction/<split>/<session_id>/"
            "turn_<turn_number>_override.json"
        ),
        "cache_precedence": ["override", "original", "litellm"],
        "splits": split_entries,
        "notes": [
            "Blind sets are final-turn only.",
            "Devset and trainset include all cached turns.",
            "Generated raw cache files stay out of Git and are distributed as a release asset.",
            "Manual corrections live beside raw files as *_override.json and are read first.",
        ],
    }
    manifest_path = cache_root / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_checksums(cache_root: Path, splits: list[str]) -> None:
    files: list[Path] = []
    for split in splits:
        files.extend(_state_files(cache_root / split))
    files.append(cache_root / "MANIFEST.json")

    lines = []
    repo_root = cache_root.parent.parent
    for path in sorted(files):
        rel = path.relative_to(repo_root)
        lines.append(f"{_sha256(path)}  {rel.as_posix()}")
    (cache_root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_release_notes(cache_root: Path, manifest: dict[str, Any]) -> None:
    lines = [
        f"# {manifest['version']}",
        "",
        "File-per-turn state extraction cache.",
        "",
        "Install from repo root:",
        "",
        "```bash",
        f"tar --zstd -xf cache/releases/{manifest['version']}.tar.zst",
        "sha256sum -c cache/state_extraction/SHA256SUMS",
        "```",
        "",
        "Contents:",
        "",
    ]
    for split in manifest["splits"]:
        lines.append(
            "- {split}: {raw_files} raw, {override_files} overrides, {sessions} sessions".format(
                **split
            )
        )
    lines.extend(
        [
            "",
            "Cache lookup precedence is `_override`, then raw/original, then LiteLLM.",
            "Generated raw files are release artifacts; do not commit them to Git.",
            "",
        ]
    )
    (cache_root / "RELEASE_NOTES.md").write_text("\n".join(lines), encoding="utf-8")


def _create_archive(
    repo_root: Path,
    cache_root: Path,
    output: Path,
    splits: list[str],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    members = [
        f"cache/state_extraction/{split}"
        for split in splits
    ] + [
        "cache/state_extraction/MANIFEST.json",
        "cache/state_extraction/SHA256SUMS",
        "cache/state_extraction/RELEASE_NOTES.md",
    ]
    cmd = ["tar", "--zstd", "-cf", str(output), *members]
    subprocess.run(cmd, cwd=repo_root, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-root",
        default="cache/state_extraction",
        help="State cache root relative to repo root.",
    )
    parser.add_argument(
        "--version",
        default="state_extraction_cache_v1_2026-06-28",
        help="Release asset basename and manifest version.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Archive path. Default: cache/releases/<version>.tar.zst",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=list(DEFAULT_SPLITS),
        help="State-cache splits to include.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip ConversationStateV0Plus validation before packaging.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Write MANIFEST/SHA256SUMS/RELEASE_NOTES without creating the archive.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path.cwd()
    cache_root = (repo_root / args.cache_root).resolve()
    output = (
        Path(args.output)
        if args.output
        else repo_root / "cache" / "releases" / f"{args.version}.tar.zst"
    )
    splits = list(args.splits)

    manifest = _write_manifest(
        cache_root,
        version=args.version,
        splits=splits,
        validate=not args.no_validate,
    )
    _write_checksums(cache_root, splits)
    _write_release_notes(cache_root, manifest)
    if not args.manifest_only:
        _create_archive(repo_root, cache_root, output, splits)
        print(f"archive: {output}")
        print(f"size_bytes: {output.stat().st_size}")
    print(f"manifest: {cache_root / 'MANIFEST.json'}")
    print(f"checksums: {cache_root / 'SHA256SUMS'}")
    print(f"release_notes: {cache_root / 'RELEASE_NOTES.md'}")


if __name__ == "__main__":
    main()
