from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "modal" / "download_results.py"
    spec = importlib.util.spec_from_file_location("modal_download_results", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class _Entry:
    path: str
    size: int
    type: SimpleNamespace


class _FakeVolume:
    def __init__(self, entries: dict[str, list[_Entry]], file_bytes: dict[str, bytes]):
        self.entries = entries
        self.file_bytes = file_bytes

    def listdir(self, path: str):
        if path not in self.entries:
            raise FileNotFoundError(path)
        return list(self.entries[path])

    def read_file(self, path: str):
        payload = self.file_bytes[path]
        midpoint = max(1, len(payload) // 2)
        for chunk in (payload[:midpoint], payload[midpoint:]):
            if chunk:
                yield chunk


def _file(path: str, size: int) -> _Entry:
    return _Entry(path=path, size=size, type=SimpleNamespace(name="FILE"))


def _fake_modal_module(volume):
    return SimpleNamespace(Volume=SimpleNamespace(from_name=lambda _: volume))


def test_discover_remote_files_includes_supported_artifact_kinds():
    module = _load_module()
    volume = _FakeVolume(
        entries={
            "/inference": [_file("inference/devset", 0)],
            "/inference/devset": [
                _file("inference/devset/foo_devset.json", 11),
                _file("inference/devset/foo_devset_rewrite_audit.jsonl", 7),
                _file("inference/devset/foo_devset_rewrite_stats.json", 5),
            ],
            "/scores": [_file("scores/devset", 0)],
            "/scores/devset": [_file("scores/devset/foo_devset.json", 3)],
            "/ground_truth": [_file("ground_truth/devset.json", 2)],
        },
        file_bytes={},
    )

    artifacts = module.discover_remote_artifacts(volume, splits=None, verbose=False)

    assert [artifact.remote_path for artifact in artifacts] == [
        "ground_truth/devset.json",
        "inference/devset/foo_devset.json",
        "inference/devset/foo_devset_rewrite_audit.jsonl",
        "inference/devset/foo_devset_rewrite_stats.json",
        "scores/devset/foo_devset.json",
    ]


def test_select_artifacts_for_tid_includes_prediction_and_traces():
    module = _load_module()
    artifacts = [
        module.RemoteArtifact("inference/devset/foo_devset.json", 10, "inference", "devset", "foo_devset"),
        module.RemoteArtifact(
            "inference/devset/foo_devset_rewrite_audit.jsonl", 4, "trace", "devset", "foo_devset"
        ),
        module.RemoteArtifact(
            "inference/devset/foo_devset_rewrite_stats.json", 3, "trace", "devset", "foo_devset"
        ),
        module.RemoteArtifact("scores/devset/foo_devset.json", 5, "scores", "devset", "foo_devset"),
        module.RemoteArtifact("inference/devset/bar_devset.json", 9, "inference", "devset", "bar_devset"),
    ]

    selected = module.select_artifacts(
        artifacts,
        tids={"foo_devset"},
        kinds={"inference", "trace", "scores"},
        overwrite=False,
        out_dir=Path("/tmp/out"),
    )

    assert [artifact.remote_path for artifact in selected] == [
        "inference/devset/foo_devset.json",
        "inference/devset/foo_devset_rewrite_audit.jsonl",
        "inference/devset/foo_devset_rewrite_stats.json",
        "scores/devset/foo_devset.json",
    ]


def test_select_artifacts_skips_existing_files_by_default(tmp_path):
    module = _load_module()
    out_dir = tmp_path / "exp"
    existing = out_dir / "inference" / "devset" / "foo_devset.json"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("already here", encoding="utf-8")

    artifacts = [
        module.RemoteArtifact("inference/devset/foo_devset.json", 10, "inference", "devset", "foo_devset"),
        module.RemoteArtifact("inference/devset/bar_devset.json", 9, "inference", "devset", "bar_devset"),
    ]

    selected = module.select_artifacts(
        artifacts,
        tids=None,
        kinds={"inference"},
        overwrite=False,
        out_dir=out_dir,
    )

    assert [artifact.remote_path for artifact in selected] == ["inference/devset/bar_devset.json"]


def test_discover_remote_artifacts_ignores_missing_optional_directories(capsys):
    module = _load_module()
    volume = _FakeVolume(
        entries={
            "/inference": [_file("inference/devset", 0)],
            "/inference/devset": [_file("inference/devset/foo_devset.json", 11)],
        },
        file_bytes={},
    )

    artifacts = module.discover_remote_artifacts(volume, splits=None, verbose=True)

    assert [artifact.remote_path for artifact in artifacts] == ["inference/devset/foo_devset.json"]
    assert "Skipping missing remote directory: /scores" in capsys.readouterr().out


def test_sync_artifacts_dry_run_reports_total_bytes(tmp_path, capsys):
    module = _load_module()
    volume = _FakeVolume(entries={}, file_bytes={})
    artifact = module.RemoteArtifact("inference/devset/foo_devset.json", 12, "inference", "devset", "foo_devset")

    summary = module.sync_artifacts(
        volume,
        [artifact],
        out_dir=tmp_path / "exp",
        dry_run=True,
        verbose=False,
    )

    assert summary.downloaded == 0
    assert summary.planned == 1
    assert summary.total_bytes == 12
    assert "Dry run: 1 file(s), 12 bytes" in capsys.readouterr().out


def test_sync_artifacts_uses_part_file_and_atomic_rename(tmp_path):
    module = _load_module()
    payload = b"abcdef"
    volume = _FakeVolume(
        entries={},
        file_bytes={"inference/devset/foo_devset.json": payload},
    )
    artifact = module.RemoteArtifact("inference/devset/foo_devset.json", len(payload), "inference", "devset", "foo_devset")
    out_dir = tmp_path / "exp"

    summary = module.sync_artifacts(volume, [artifact], out_dir=out_dir, dry_run=False, verbose=False)

    local_path = out_dir / "inference" / "devset" / "foo_devset.json"
    assert summary.downloaded == 1
    assert local_path.read_bytes() == payload
    assert not local_path.with_name("foo_devset.json.part").exists()


def test_main_supports_legacy_single_tid_usage(tmp_path, monkeypatch, capsys):
    module = _load_module()
    payload = b"legacy"
    volume = _FakeVolume(
        entries={
            "/inference": [_file("inference/devset", 0)],
            "/inference/devset": [_file("inference/devset/foo_devset.json", len(payload))],
        },
        file_bytes={"inference/devset/foo_devset.json": payload},
    )
    monkeypatch.setitem(sys.modules, "modal", _fake_modal_module(volume))

    exit_code = module.main(["--tid", "foo_devset", "--out-dir", str(tmp_path / "exp"), "--kind", "inference"])

    assert exit_code == 0
    assert (tmp_path / "exp" / "inference" / "devset" / "foo_devset.json").read_bytes() == payload
    assert "Downloaded 1 file(s)" in capsys.readouterr().out


def test_main_reads_tid_file_for_bulk_selection(tmp_path, monkeypatch):
    module = _load_module()
    tid_file = tmp_path / "tids.txt"
    tid_file.write_text("foo_devset\n\nbar_devset\n", encoding="utf-8")
    volume = _FakeVolume(
        entries={
            "/inference": [_file("inference/devset", 0)],
            "/inference/devset": [
                _file("inference/devset/foo_devset.json", 3),
                _file("inference/devset/bar_devset.json", 4),
                _file("inference/devset/baz_devset.json", 5),
            ],
        },
        file_bytes={
            "inference/devset/foo_devset.json": b"foo",
            "inference/devset/bar_devset.json": b"bars",
            "inference/devset/baz_devset.json": b"other",
        },
    )
    monkeypatch.setitem(sys.modules, "modal", _fake_modal_module(volume))

    exit_code = module.main(
        ["--tid-file", str(tid_file), "--out-dir", str(tmp_path / "exp"), "--kind", "inference"]
    )

    assert exit_code == 0
    assert (tmp_path / "exp" / "inference" / "devset" / "foo_devset.json").exists()
    assert (tmp_path / "exp" / "inference" / "devset" / "bar_devset.json").exists()
    assert not (tmp_path / "exp" / "inference" / "devset" / "baz_devset.json").exists()


def test_download_artifacts_skill_references_downloader_script():
    skill_path = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "download-artifacts" / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")

    assert "python modal/download_results.py" in content
    assert "evaluator/exp" in content
