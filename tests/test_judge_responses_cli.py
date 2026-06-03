from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "judge_responses", Path("scripts/judge_responses.py")
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_render_markdown_table_sorts_by_combined_desc():
    reports = [
        {"tag": "weak", "distinct2": 0.2, "personalization_panel": 0.1,
         "explanation_panel": 0.1, "combined": 0.1, "n_turns": 8,
         "personalization_by_judge": {"gemini": 0.1, "neutral": 0.1},
         "explanation_by_judge": {"gemini": 0.1, "neutral": 0.1}},
        {"tag": "strong", "distinct2": 0.5, "personalization_panel": 0.9,
         "explanation_panel": 0.8, "combined": 0.85, "n_turns": 8,
         "personalization_by_judge": {"gemini": 0.95, "neutral": 0.85},
         "explanation_by_judge": {"gemini": 0.8, "neutral": 0.8}},
    ]
    md = mod.render_markdown(reports)
    assert md.index("strong") < md.index("weak")
    assert "Distinct-2" in md and "Combined" in md
