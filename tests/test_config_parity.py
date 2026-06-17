from __future__ import annotations

from pathlib import Path

from omegaconf import OmegaConf


def _load_config(relative_path: str) -> dict:
    root = Path(__file__).resolve().parents[1]
    return OmegaConf.to_container(OmegaConf.load(root / relative_path), resolve=True)


def test_fastlocal_keeps_visual_dense_branch_from_canonical_lgbm_config():
    canonical = _load_config("configs/state_ranker_v10_lgbm_devset.yaml")
    fastlocal = _load_config("configs/state_ranker_v10_lgbm_devset_fastlocal.yaml")

    canonical_visual = [
        branch
        for branch in canonical["qu_kwargs"]["compiler"]["dense_branches"]
        if branch.get("query_id") == "visual_nl"
    ]
    fastlocal_visual = [
        branch
        for branch in fastlocal["qu_kwargs"]["compiler"]["dense_branches"]
        if branch.get("query_id") == "visual_nl"
    ]

    assert canonical_visual
    assert fastlocal["qu_kwargs"]["encoders"]["siglip2_text"]
    assert fastlocal_visual == canonical_visual
