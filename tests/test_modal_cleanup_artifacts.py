from __future__ import annotations

import importlib.util
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest


def _load_module(name: str):
    module_path = Path(__file__).resolve().parents[1] / "modal" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_select_result_cleanup_only_allows_old_v0plus_tids():
    cleanup = _load_module("cleanup_artifacts")
    download = _load_module("download_results")
    artifacts = [
        download.RemoteArtifact("inference/devset/v0plus_compiler_devset_rr2.json", 1, "inference", "devset", "v0plus_compiler_devset_rr2"),
        download.RemoteArtifact("inference/devset/state_ranker_v10_rrf_devset.json", 1, "inference", "devset", "state_ranker_v10_rrf_devset"),
        download.RemoteArtifact("ground_truth/devset.json", 1, "ground-truth", None, None),
        download.RemoteArtifact("scores/devset/v0plus_compiler_devset_rr2.json", 1, "scores", "devset", "v0plus_compiler_devset_rr2"),
    ]

    actions = cleanup.select_result_cleanup(artifacts, family="old-v0plus")

    assert actions == [
        cleanup.CleanupAction("music-crs-results", "inference/devset/v0plus_compiler_devset_rr2.json", False),
        cleanup.CleanupAction("music-crs-results", "scores/devset/v0plus_compiler_devset_rr2.json", False),
    ]


def test_training_cleanup_is_allowlisted_and_preserves_warm_caches():
    cleanup = _load_module("cleanup_artifacts")

    actions = cleanup.plan_training_cleanup(family="old-v0plus")

    assert actions == [
        cleanup.CleanupAction("music-crs-cache", "rerank/features_v9", True),
        cleanup.CleanupAction("music-crs-cache", "rerank/constraint_features.parquet", False),
        cleanup.CleanupAction("music-crs-cache", "rerank/label_weights_v9.parquet", False),
        cleanup.CleanupAction("music-crs-cache", "rerank/train_v9", True),
    ]
    assert all("q06_memo" not in action.remote_path for action in actions)
    assert all("raw_msg_store" not in action.remote_path for action in actions)


def test_training_cleanup_filters_missing_remote_paths():
    cleanup = _load_module("cleanup_artifacts")

    class FakeVolume:
        def listdir(self, path):
            assert path == "/rerank"
            return [
                SimpleNamespace(path="/rerank/features_v9"),
                SimpleNamespace(path="/rerank/q06_memo.json"),
                SimpleNamespace(path="/rerank/v10"),
            ]

    actions = cleanup.filter_existing_training_cleanup(
        FakeVolume(),
        cleanup.plan_training_cleanup(family="old-v0plus"),
        verbose=False,
    )

    assert actions == [
        cleanup.CleanupAction("music-crs-cache", "rerank/features_v9", True),
    ]


def test_delete_requires_v10_validation_confirmation():
    cleanup = _load_module("cleanup_artifacts")

    with pytest.raises(SystemExit, match="confirm-v10-validated"):
        cleanup.main(["--include-training", "--delete"])
