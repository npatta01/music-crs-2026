from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

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


def test_run_flushes_msg_store_at_shutdown(tmp_path, monkeypatch):
    module = _load_module("replay_lgbm_flush_msg_store", "scripts/rerank/replay_lgbm.py")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.txt").write_text("fake", encoding="utf-8")
    (model_dir / "meta.json").write_text(json.dumps({"cols": ["score"]}), encoding="utf-8")
    (model_dir / "cat_maps.json").write_text("{}", encoding="utf-8")
    (model_dir / "branch_names.json").write_text("[]", encoding="utf-8")
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "s1",
                "user_id": "u1",
                "turn_number": 1,
                "trace": {"final_recommendation": {"track_ids": ["t1"]}},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class FakeBooster:
        def __init__(self, model_file):
            self.model_file = model_file

        def num_feature(self):
            return 1

        def predict(self, x):
            return np.ones(x.shape[0], dtype=np.float32)

    class FakeCatalog:
        def __init__(self, db_uri, table_name):
            self.meta = {"t1": {"artists": ()}}

    class FakeMemo:
        instances = []

        def __init__(self, path):
            self.flushed = False
            self.__class__.instances.append(self)

        def flush(self):
            self.flushed = True

    class FakeMsgStore:
        instances = []

        def __init__(self, path):
            self.flushed = False
            self.__class__.instances.append(self)

        def flush(self):
            self.flushed = True

    class FakeTagEmbeddingIndex:
        tags = []
        matrix = np.empty((0, 1), dtype=np.float32)

        @classmethod
        def load(cls, path):
            return cls()

    monkeypatch.setitem(sys.modules, "lightgbm", SimpleNamespace(Booster=FakeBooster))
    monkeypatch.setitem(
        sys.modules,
        "build_features",
        SimpleNamespace(
            Catalog=FakeCatalog,
            EmbedMemo=FakeMemo,
            NpzEmbedStore=FakeMsgStore,
            load_sessions=lambda dataset_name, split: {},
            load_user_cf=lambda: {},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "features_v9",
        SimpleNamespace(
            TurnContext=lambda *args, **kwargs: SimpleNamespace(cat=args[0]),
            compute_turn_features=lambda row, ctx, gt=None: ([{"track_id": "t1", "score": 1.0}], True),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "mcrs.qu_modules.tag_resolver",
        SimpleNamespace(
            TagEmbeddingIndex=FakeTagEmbeddingIndex,
            TieredTagResolver=lambda **kwargs: object(),
        ),
    )

    module.run(
        SimpleNamespace(
            trace=trace_path,
            out_exp_dir=tmp_path / "out",
            out_tid="tid",
            split="devset",
            model_ref=model_dir,
            model_version="lgbm_test",
            db_uri="db",
            table_name="table",
            tag_index="tag.npz",
            embed_memo=tmp_path / "memo.json",
            msg_store=tmp_path / "msg_store",
            dataset_name="talkpl-ai/Test",
            dataset_split="test",
            pool_k=500,
            top_k_out=1000,
            output_topk=20,
            num_shards=1,
            shard_id=0,
            output_suffix="",
            no_trace_output=True,
            offline=True,
        )
    )

    assert FakeMemo.instances[0].flushed
    assert FakeMsgStore.instances[0].flushed
