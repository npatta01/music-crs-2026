"""Helpers for uploading a local LanceDB directory to a Modal volume."""

from pathlib import Path
from typing import Any


def normalize_modal_volume_dir(remote_dir: str) -> str:
    """Return an absolute Modal volume directory path, rejecting the volume root."""
    normalized = str(remote_dir).strip("/")
    if not normalized:
        raise ValueError("remote_dir must not resolve to the volume root")
    return f"/{normalized}"


def upload_lancedb_directory_to_volume(
    volume: Any,
    local_db_dir: str | Path,
    *,
    remote_dir: str = "lancedb",
    overwrite: bool = False,
    volume_name: str = "",
) -> str:
    """Upload a local LanceDB directory to a Modal volume and return the remote path."""
    local_path = Path(local_db_dir).expanduser().resolve()
    if not local_path.exists():
        raise FileNotFoundError(f"Local LanceDB directory does not exist: {local_path}")
    if not local_path.is_dir():
        raise NotADirectoryError(f"Local LanceDB path is not a directory: {local_path}")

    remote_path = normalize_modal_volume_dir(remote_dir)
    volume_label = f"{volume_name}:{remote_path}" if volume_name else remote_path

    if overwrite:
        try:
            volume.remove_file(remote_path, recursive=True)
        except FileNotFoundError:
            print(f"No existing volume path to remove at {volume_label}")
        else:
            print(f"Removed existing volume path {volume_label}")

    with volume.batch_upload() as batch:
        batch.put_directory(str(local_path), remote_path)
    print(f"Uploaded {local_path} to volume {volume_label}")
    return remote_path
