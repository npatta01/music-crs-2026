from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


def _load_module(name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def test_output_paths_include_suffix_and_can_disable_trace(tmp_path):
    module = _load_module("replay_lgbm_output_paths", "scripts/rerank/replay_lgbm.py")

    pred_path, trace_path = module.output_paths(
        tmp_path,
        "devset",
        "tid",
        ".run_abc.shard_2",
        write_trace=False,
    )

    assert pred_path == tmp_path / "inference" / "devset" / "tid.run_abc.shard_2.json"
    assert trace_path is None


def test_should_process_row_uses_modulo_shards():
    module = _load_module("replay_lgbm_shard_filter", "scripts/rerank/replay_lgbm.py")

    assert [
        index
        for index in range(10)
        if module.should_process_row(index, num_shards=3, shard_id=1)
    ] == [1, 4, 7]


def test_fallback_track_ids_prefers_final_recommendation():
    module = _load_module("replay_lgbm_fallback", "scripts/rerank/replay_lgbm.py")

    assert module.fallback_track_ids(
        {
            "final_recommendation": {"track_ids": ["final-1"]},
            "ranking": {
                "stages": [
                    {"name": "candidate_fusion", "track_ids": ["cand-1"]},
                ]
            },
        }
    ) == ["final-1"]

def test_fallback_track_ids_uses_candidate_stage_without_final():
    module = _load_module("replay_lgbm_candidate", "scripts/rerank/replay_lgbm.py")

    assert module.fallback_track_ids(
        {
            "ranking": {
                "stages": [
                    {"name": "candidate_fusion", "track_ids": ["cand-1", "cand-2"]},
                ]
            }
        }
    ) == ["cand-1", "cand-2"]

def test_hard_drop_ids_prefers_serialized_retrieval_hard_drop_and_unions_rejections():
    module = _load_module("replay_lgbm_hard_drop", "scripts/rerank/replay_lgbm.py")

    assert module.hard_drop_ids(
        {
            "retrieval": {"hard_drop": ["played-track", "resolved-rejection"]},
            "resolver": {"rejected_track_ids": ["explicit-rejection"]},
        }
    ) == {"played-track", "resolved-rejection", "explicit-rejection"}

def test_add_constraint_features_marks_rejections_and_new_artist_violation():
    module = _load_module("replay_lgbm_constraints", "scripts/rerank/replay_lgbm.py")
    rows = [
        {
            "track_id": "t1",
            "_artists": ("a1",),
            "target_artist_mode": "new_artist",
            "same_artist_session": 1.0,
        }
    ]

    module.add_constraint_features(
        rows,
        {
            "resolver": {
                "played_track_ids": ["t1"],
                "rejected_track_ids": ["t2"],
                "rejected_artist_ids": ["a1"],
            }
        },
    )

    assert rows[0]["is_played_track"] == 1.0
    assert rows[0]["rejected_track_exact"] == 0.0
    assert rows[0]["rejected_artist_exact"] == 1.0
    assert rows[0]["violates_new_artist"] == 1.0

def test_assemble_matrix_maps_categoricals_and_missing_numeric_to_nan():
    module = _load_module("replay_lgbm_assemble", "scripts/rerank/replay_lgbm.py")

    x = module.assemble_matrix(
        [{"age_group": "18-24", "score": None}],
        ["age_group", "score"],
        {"age_group": {"18-24": 3}},
    )

    assert x.shape == (1, 2)
    assert x[0, 0] == 3.0
    assert np.isnan(x[0, 1])

def test_update_trace_for_rerank_sets_final_stage():
    module = _load_module("replay_lgbm_trace", "scripts/rerank/replay_lgbm.py")

    trace = module.update_trace_for_rerank(
        {"ranking": {"stages": [{"name": "candidate_fusion", "track_ids": ["a"]}]}},
        ["b", "a"],
        model_version="lgbm_test",
    )

    assert trace["ranking"]["final_stage"] == "lgbm_test"
    assert trace["ranking"]["stages"][-1]["name"] == "lgbm_test"
    assert trace["final_recommendation"]["track_ids"] == ["b", "a"]
    assert trace["final_recommendation"]["ranking_mode"] == "lgbm"
