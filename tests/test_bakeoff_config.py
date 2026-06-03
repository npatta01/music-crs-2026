from __future__ import annotations

from pathlib import Path

import yaml


def test_models_yaml_has_generators_and_judges():
    cfg = yaml.safe_load(Path("configs/bakeoff/models.yaml").read_text())
    gens = cfg["generators"]
    assert len(gens) == 10
    tags = {g["tag"] for g in gens}
    assert {"llama-1b", "gemma-27b", "qwen3-30b-a3b", "gpt5-nano", "gemini-flash-lite"} <= tags
    for g in gens:
        assert g["model_name"].startswith("openrouter/")
    judges = cfg["judges"]
    assert "gemini" in judges and "neutral" in judges
    qwen8 = next(g for g in gens if g["tag"] == "qwen3-8b")
    assert qwen8["completion_kwargs"]["extra_body"]["reasoning"]["enabled"] is False
    nano = next(g for g in gens if g["tag"] == "gpt5-nano")
    assert nano["completion_kwargs"]["reasoning_effort"] == "minimal"
