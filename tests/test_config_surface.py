from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DEVSET_TID = "v0plus_compiler_all_retrievers_devset"
DELETED_DEVSET_TID = "v0plus_compiler_image_devset"


def test_current_config_surface_has_no_deleted_devset_references():
    configs = sorted(path.name for path in (PROJECT_ROOT / "configs").glob("*.yaml"))
    assert configs == [
        "v0plus_compiler_all_retrievers_devset.yaml",
        "v0plus_compiler_blindset_A.yaml",
        "v0plus_compiler_blindset_A_rr2.yaml",
        "v0plus_compiler_devset_rr2.yaml",
        "v0plus_compiler_pruned_resolved_tags_devset.yaml",
    ]

    checked_paths = [
        "AGENTS.md",
        "CLAUDE.md",
        "readme.md",
        "docs/mac_dev.md",
        "docs/modal_setup.md",
        "run_inference_devset.py",
        "evaluator/evaluate_devset.py",
        "modal/app.py",
        "streamlit_app.py",
    ]
    for rel_path in checked_paths:
        text = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        assert DELETED_DEVSET_TID not in text, rel_path
        assert CANONICAL_DEVSET_TID in text, rel_path
