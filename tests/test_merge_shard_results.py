from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "merge_shard_results.py"
    spec = importlib.util.spec_from_file_location("merge_shard_results_mod", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(base: Path, name: str, rows: list[dict]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / name).write_text(json.dumps(rows), encoding="utf-8")


def _pred(session_id: str, turn: int) -> dict:
    return {"session_id": session_id, "turn_number": turn,
            "predicted_track_ids": ["t1"], "predicted_response": "r"}


def _trace(session_id: str, turn: int) -> dict:
    return {"session_id": session_id, "turn_number": turn, "trace": {"x": 1}}


def test_merge_run_scoped_devset_predictions_and_traces(tmp_path):
    module = _load_module()
    base = tmp_path / "inference" / "devset"
    rid = "20260603T074512Z-a3f91c"
    _write(base, f"foo_devset.run_{rid}.shard_0.json", [_pred("s0", 1)])
    _write(base, f"foo_devset.run_{rid}.shard_1.json", [_pred("s1", 1)])
    _write(base, f"foo_devset.run_{rid}.shard_0_trace.json", [_trace("s0", 1)])
    _write(base, f"foo_devset.run_{rid}.shard_1_trace.json", [_trace("s1", 1)])

    module.main([
        "--tid", "foo_devset", "--num_shards", "2", "--run_id", rid,
        "--split", "devset", "--exp-dir", str(tmp_path),
    ])

    preds = json.loads((base / "foo_devset.json").read_text())
    traces = json.loads((base / "foo_devset_trace.json").read_text())
    assert {r["session_id"] for r in preds} == {"s0", "s1"}
    assert {r["session_id"] for r in traces} == {"s0", "s1"}


def test_merge_requires_all_shards_for_run_id(tmp_path):
    module = _load_module()
    base = tmp_path / "inference" / "devset"
    rid = "20260603T074512Z-a3f91c"
    _write(base, f"foo_devset.run_{rid}.shard_0.json", [_pred("s0", 1)])
    # shard_1 deliberately missing

    with pytest.raises(FileNotFoundError, match="shard_1"):
        module.main([
            "--tid", "foo_devset", "--num_shards", "2", "--run_id", rid,
            "--split", "devset", "--exp-dir", str(tmp_path),
        ])


def test_merge_blindset_without_traces(tmp_path):
    module = _load_module()
    base = tmp_path / "inference" / "blindset_A"
    rid = "20260603T074512Z-a3f91c"
    _write(base, f"foo_blindset_A.run_{rid}.shard_0.json", [_pred("s0", 1)])
    _write(base, f"foo_blindset_A.run_{rid}.shard_1.json", [_pred("s1", 1)])
    # no trace shards

    module.main([
        "--tid", "foo_blindset_A", "--num_shards", "2", "--run_id", rid,
        "--split", "blindset_A", "--exp-dir", str(tmp_path),
    ])

    preds = json.loads((base / "foo_blindset_A.json").read_text())
    assert {r["session_id"] for r in preds} == {"s0", "s1"}
    assert not (base / "foo_blindset_A_trace.json").exists()
