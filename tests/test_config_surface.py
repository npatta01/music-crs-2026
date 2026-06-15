from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DEVSET_TID = "state_ranker_v10_lgbm_devset"
CANONICAL_RRF_DEVSET_TID = "state_ranker_v10_rrf_devset"
CANONICAL_BLINDSET_TID = "state_ranker_v10_lgbm_blindset_A"
DELETED_DEVSET_TID = "v0plus_compiler_image_devset"


def test_current_config_surface_has_no_deleted_devset_references():
    configs = sorted(path.name for path in (PROJECT_ROOT / "configs").glob("*.yaml"))
    assert configs == [
        "state_ranker_v10_lgbm_blindset_A.yaml",
        "state_ranker_v10_lgbm_devset.yaml",
        "state_ranker_v10_rrf_devset.yaml",
    ]

    checked_paths = [
        "AGENTS.md",
        "CLAUDE.md",
        "readme.md",
        "docs/mac_dev.md",
        "docs/modal_setup.md",
        "run_inference_devset.py",
        "run_inference_blindset.py",
        "evaluator/evaluate_devset.py",
        "modal/app.py",
        "streamlit_app.py",
    ]
    expected_mentions = {
        "AGENTS.md": {CANONICAL_RRF_DEVSET_TID, CANONICAL_DEVSET_TID, CANONICAL_BLINDSET_TID},
        "CLAUDE.md": {CANONICAL_RRF_DEVSET_TID, CANONICAL_DEVSET_TID, CANONICAL_BLINDSET_TID},
        "readme.md": {CANONICAL_RRF_DEVSET_TID, CANONICAL_DEVSET_TID, CANONICAL_BLINDSET_TID},
        "docs/mac_dev.md": {CANONICAL_RRF_DEVSET_TID, CANONICAL_DEVSET_TID},
        "docs/modal_setup.md": {CANONICAL_RRF_DEVSET_TID, CANONICAL_DEVSET_TID, CANONICAL_BLINDSET_TID},
        "run_inference_devset.py": {CANONICAL_RRF_DEVSET_TID, CANONICAL_DEVSET_TID},
        "evaluator/evaluate_devset.py": {CANONICAL_RRF_DEVSET_TID, CANONICAL_DEVSET_TID},
        "modal/app.py": {CANONICAL_RRF_DEVSET_TID, CANONICAL_DEVSET_TID, CANONICAL_BLINDSET_TID},
        "streamlit_app.py": {CANONICAL_RRF_DEVSET_TID, CANONICAL_DEVSET_TID, CANONICAL_BLINDSET_TID},
        "run_inference_blindset.py": {CANONICAL_BLINDSET_TID},
    }
    for rel_path in checked_paths:
        text = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        assert DELETED_DEVSET_TID not in text, rel_path
        for tid in expected_mentions[rel_path]:
            assert tid in text, rel_path


def test_state_ranker_v10_configs_are_active_and_do_not_use_v0plus_qu_type():
    expected = {
        "state_ranker_v10_rrf_devset.yaml",
        "state_ranker_v10_lgbm_devset.yaml",
        "state_ranker_v10_lgbm_blindset_A.yaml",
    }
    config_dir = PROJECT_ROOT / "configs"
    existing = {path.name for path in config_dir.glob("state_ranker_v10_*.yaml")}
    assert existing == expected

    for config_name in expected:
        config = yaml.safe_load((config_dir / config_name).read_text(encoding="utf-8"))
        assert config["qu_type"] == "state_ranker"
        assert config["qu_kwargs"]["ranking"]["mode"] in {"rrf", "lgbm"}
        assert "reranker" not in config["qu_kwargs"]
        if config["qu_kwargs"]["ranking"]["mode"] == "rrf":
            assert "model_path" not in config["qu_kwargs"]["ranking"]
        else:
            assert "models/reranker_v10" in config["qu_kwargs"]["ranking"]["model_path"]
