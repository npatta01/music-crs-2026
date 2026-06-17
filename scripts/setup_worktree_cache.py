"""Link shared local caches into a Music-CRS git worktree.

The script is intentionally source-root agnostic. Configure the shared root with
one of:

  1. ``--source /path/to/cache-owner``
  2. ``MCRS_SHARED_ROOT=/path/to/cache-owner``
  3. ``git config --global mcrs.sharedRoot /path/to/cache-owner``
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GIT_CONFIG_KEY = "mcrs.sharedRoot"


@dataclass(frozen=True)
class LinkSpec:
    source: Path
    target: Path
    required: tuple[Path, ...]


@dataclass(frozen=True)
class SetupResult:
    changed: int
    ok: int
    skipped: int


def git_config_shared_root() -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "config", "--get", GIT_CONFIG_KEY],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return None
    value = proc.stdout.strip()
    return Path(value).expanduser() if proc.returncode == 0 and value else None


def resolve_source(cli_source: str | Path | None) -> Path:
    if cli_source:
        return Path(cli_source).expanduser().resolve()
    env_source = os.environ.get("MCRS_SHARED_ROOT")
    if env_source:
        return Path(env_source).expanduser().resolve()
    git_source = git_config_shared_root()
    if git_source:
        return git_source.resolve()
    raise ValueError(
        "Shared cache root is not configured. Pass --source, set MCRS_SHARED_ROOT, "
        f"or run: git config --global {GIT_CONFIG_KEY} /path/to/cache-owner"
    )


def link_specs(target_root: Path, source_root: Path) -> list[LinkSpec]:
    return [
        LinkSpec(
            source=source_root / "cache",
            target=target_root / "cache",
            required=(
                source_root / "cache" / "lancedb",
                source_root / "cache" / "tag_embedding_index",
            ),
        ),
        LinkSpec(
            source=source_root / "exp" / "analysis" / "rerank",
            target=target_root / "exp" / "analysis" / "rerank",
            required=(
                source_root / "exp" / "analysis" / "rerank" / "q06_memo.json",
                source_root / "exp" / "analysis" / "rerank" / "raw_msg_store",
            ),
        ),
        LinkSpec(
            source=source_root / ".env",
            target=target_root / ".env",
            required=(source_root / ".env",),
        ),
    ]


def _is_expected_target(target: Path, source: Path) -> bool:
    try:
        return target.resolve() == source.resolve()
    except FileNotFoundError:
        return False


def _validate_source(spec: LinkSpec) -> None:
    missing = [path for path in spec.required if not path.exists()]
    if missing:
        rendered = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Shared source is missing required artifact(s): {rendered}")


def _remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def ensure_link(spec: LinkSpec, *, force: bool = False) -> str:
    _validate_source(spec)
    if _is_expected_target(spec.target, spec.source):
        return "ok"
    if spec.target.exists() or spec.target.is_symlink():
        if not force:
            raise FileExistsError(
                f"{spec.target} already exists and does not point to {spec.source}. "
                "Move it aside or rerun with --force."
            )
        _remove_existing(spec.target)
    spec.target.parent.mkdir(parents=True, exist_ok=True)
    spec.target.symlink_to(spec.source, target_is_directory=spec.source.is_dir())
    return "changed"


def setup_worktree_cache(
    target_root: str | Path,
    source_root: str | Path,
    *,
    force: bool = False,
) -> SetupResult:
    target = Path(target_root).expanduser().resolve()
    source = Path(source_root).expanduser().resolve()
    changed = 0
    ok = 0
    skipped = 0
    for spec in link_specs(target, source):
        status = ensure_link(spec, force=force)
        if status == "changed":
            changed += 1
        elif status == "ok":
            ok += 1
        else:
            skipped += 1
    return SetupResult(changed=changed, ok=ok, skipped=skipped)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=None, help="Shared cache owner root.")
    parser.add_argument(
        "--target",
        default=str(PROJECT_ROOT),
        help="Worktree root to link into.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing target paths that do not already point to the shared root.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source = resolve_source(args.source)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = setup_worktree_cache(args.target, source, force=args.force)
    print(
        f"worktree cache links: changed={result.changed} "
        f"ok={result.ok} skipped={result.skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
