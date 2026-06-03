# Response-Generation Model Bake-off Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compare 10 candidate response-generation models on a fixed 8-session slice — holding retrieval constant — scored by a Gemini+neutral judge panel (G-Eval rubric) plus Distinct-2, to pick the best generator before flipping a config off `lm_type: "dummy"`.

**Architecture:** Decoupled replay. Retrieval output is reused from the existing `v0plus_compiler_all_retrievers_devset.json` predictions; only the natural-language response step is re-run per candidate. Generation reuses `LITELLM_LM.response_generation` and the production `chat_history_parser`; track metadata comes from a lightweight HF-backed lookup injected into the parser (no LanceDB build needed). A separate judge script scores the saved responses.

**Tech Stack:** Python 3.10, litellm (→ OpenRouter via `OPENROUTER_API_KEY`), HuggingFace `datasets`, pytest, PyYAML.

**Spec:** `docs/superpowers/specs/2026-06-03-response-gen-bakeoff-design.md`

---

## File Structure

- **Modify** `mcrs/lm_modules/litellm_chat.py` — `LITELLM_LM`: add `completion_kwargs` passthrough; fix `api_base` so it's only forwarded when truthy.
- **Create** `tests/test_litellm_lm_passthrough.py` — unit tests for the above (mocked litellm).
- **Create** `mcrs/bakeoff/__init__.py` — package marker.
- **Create** `mcrs/bakeoff/track_lookup.py` — `TrackMetadataLookup` with `id_to_metadata(track_id) -> str`, buildable from rows (testable) or from HF.
- **Create** `tests/test_bakeoff_track_lookup.py`
- **Create** `mcrs/bakeoff/replay.py` — `build_turn_inputs(...)` and `generate_for_model(...)` (pure-ish, mockable).
- **Create** `tests/test_bakeoff_replay.py`
- **Create** `mcrs/bakeoff/judge.py` — rubric prompt builder, response parser, normalization, report aggregation.
- **Create** `tests/test_bakeoff_judge.py`
- **Create** `configs/bakeoff/models.yaml` — generator + judge registry.
- **Create** `scripts/response_bakeoff.py` — CLI: load slice/predictions/dataset → generate per model → `exp/bakeoff/responses/{tag}.json`.
- **Create** `scripts/judge_responses.py` — CLI: judge saved responses → `exp/bakeoff/report.{md,json}`.

Outputs live under `exp/bakeoff/` (gitignored like the rest of `exp/`).

---

## Task 1: `LITELLM_LM` passthrough + api_base fix

**Files:**
- Modify: `mcrs/lm_modules/litellm_chat.py`
- Test: `tests/test_litellm_lm_passthrough.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_litellm_lm_passthrough.py
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest


def _install_fake_litellm(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            id="c1",
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion))
    return calls


def test_completion_kwargs_merge_through(monkeypatch):
    calls = _install_fake_litellm(monkeypatch)
    from mcrs.lm_modules.litellm_chat import LITELLM_LM

    lm = LITELLM_LM(
        model_name="openrouter/qwen/qwen3-8b",
        api_key="or-test",
        temperature=0.0,
        max_tokens=64,
        completion_kwargs={"extra_body": {"reasoning": {"enabled": False}}},
    )
    out = lm.response_generation("sys", [{"role": "user", "content": "hi"}], {"title": "X"})
    assert out == "ok"
    sent = calls[0]
    assert sent["model"] == "openrouter/qwen/qwen3-8b"
    assert sent["extra_body"] == {"reasoning": {"enabled": False}}
    assert sent["max_tokens"] == 64


def test_api_base_omitted_when_unset(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_BASE", raising=False)
    calls = _install_fake_litellm(monkeypatch)
    from mcrs.lm_modules.litellm_chat import LITELLM_LM

    lm = LITELLM_LM(model_name="openrouter/google/gemma-3-4b-it", api_key="or-test")
    lm.response_generation("sys", [], {"title": "X"})
    assert "api_base" not in calls[0]


def test_api_base_forwarded_when_proxy_env_set(monkeypatch):
    monkeypatch.setenv("LITELLM_PROXY_BASE", "http://localhost:4000")
    calls = _install_fake_litellm(monkeypatch)
    from mcrs.lm_modules.litellm_chat import LITELLM_LM

    lm = LITELLM_LM(model_name="proxy/model", api_key="k")
    lm.response_generation("sys", [], {"title": "X"})
    assert calls[0]["api_base"] == "http://localhost:4000"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd .claude/worktrees/response-gen-bakeoff && python -m pytest tests/test_litellm_lm_passthrough.py -v`
Expected: FAIL — `test_completion_kwargs_merge_through` errors (no `completion_kwargs` param / `extra_body` not sent); `test_api_base_omitted_when_unset` fails (api_base present as `http://localhost:4000`).

- [ ] **Step 3: Implement the change**

In `mcrs/lm_modules/litellm_chat.py`, edit `LITELLM_LM.__init__` and `_completion_kwargs`:

```python
    def __init__(
        self,
        model_name: str,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        completion_kwargs: dict | None = None,
        **_unused,
    ):
        self.model_name = model_name
        # Only use a proxy base when explicitly configured (arg or env).
        # No hardcoded localhost fallback — lets direct openrouter/... calls
        # authenticate via OPENROUTER_API_KEY (issue #96 §4).
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE")
        self.api_key = api_key or os.environ.get("LITELLM_PROXY_KEY")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.completion_kwargs = dict(completion_kwargs or {})

    def _completion_kwargs(self, max_new_tokens: int | None) -> dict:
        kwargs = {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": int(max_new_tokens) if max_new_tokens is not None else self.max_tokens,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        # User-supplied params (reasoning_effort, extra_body, top_p, ...) win,
        # but cannot clobber model/messages (messages set at call time).
        kwargs.update(self.completion_kwargs)
        kwargs.pop("messages", None)
        return kwargs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_litellm_lm_passthrough.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the existing litellm test to confirm no regression**

Run: `python -m pytest tests/test_litellm_chat_client.py tests/test_litellm_cache_setup.py -v`
Expected: PASS (unchanged — those cover `LiteLLMChatClient`, a different class)

- [ ] **Step 6: Commit**

```bash
git add mcrs/lm_modules/litellm_chat.py tests/test_litellm_lm_passthrough.py
git commit -m "feat(lm): LITELLM_LM completion_kwargs passthrough + api_base fix (#96)"
```

---

## Task 2: `TrackMetadataLookup`

**Files:**
- Create: `mcrs/bakeoff/__init__.py` (empty)
- Create: `mcrs/bakeoff/track_lookup.py`
- Test: `tests/test_bakeoff_track_lookup.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bakeoff_track_lookup.py
from __future__ import annotations

from mcrs.bakeoff.track_lookup import TrackMetadataLookup


def _rows():
    return [
        {"track_id": "t1", "track_name": ["Buena"], "artist_name": ["Morphine"],
         "album_name": ["Yes"], "tag_list": ["smoky", "lounge"]},
        {"track_id": "t2", "track_name": ["Cure for Pain"], "artist_name": ["Morphine"],
         "album_name": ["Cure for Pain"], "tag_list": []},
    ]


def test_id_to_metadata_formats_known_track():
    lk = TrackMetadataLookup.from_rows(_rows())
    s = lk.id_to_metadata("t1")
    assert "Buena" in s and "Morphine" in s and "Yes" in s and "smoky" in s


def test_id_to_metadata_unknown_track_returns_placeholder():
    lk = TrackMetadataLookup.from_rows(_rows())
    assert lk.id_to_metadata("nope") == "track=nope"


def test_id_to_metadata_handles_empty_tags():
    lk = TrackMetadataLookup.from_rows(_rows())
    s = lk.id_to_metadata("t2")
    assert "Cure for Pain" in s and "Morphine" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bakeoff_track_lookup.py -v`
Expected: FAIL — `ModuleNotFoundError: mcrs.bakeoff.track_lookup`

- [ ] **Step 3: Implement**

```python
# mcrs/bakeoff/__init__.py
```

```python
# mcrs/bakeoff/track_lookup.py
"""Lightweight track-metadata lookup for the response bake-off.

Provides `id_to_metadata(track_id) -> str`, the interface `chat_history_parser`
(mcrs/inference_utils.py) expects on `music_crs.item_db`. Backed by the HF
`TalkPlayData-Challenge-Track-Metadata` rows so the bake-off does not require a
local LanceDB build. The metadata string carries the track facts the LM needs;
exact formatting need not byte-match the LanceDB catalog.
"""
from __future__ import annotations

from typing import Any, Iterable


def _first(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return str(value[0]).strip() if value else ""
    return str(value).strip() if value is not None else ""


class TrackMetadataLookup:
    def __init__(self, by_id: dict[str, dict]):
        self._by_id = by_id

    @classmethod
    def from_rows(cls, rows: Iterable[dict]) -> "TrackMetadataLookup":
        by_id = {str(r["track_id"]): r for r in rows}
        return cls(by_id)

    @classmethod
    def from_hf(cls, dataset_name: str = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata",
                split: str = "all_tracks") -> "TrackMetadataLookup":
        from datasets import load_dataset
        ds = load_dataset(dataset_name, split=split)
        return cls.from_rows(ds)

    def id_to_metadata(self, track_id: str) -> str:
        meta = self._by_id.get(str(track_id))
        if meta is None:
            return f"track={track_id}"
        title = _first(meta.get("track_name"))
        artist = _first(meta.get("artist_name"))
        album = _first(meta.get("album_name"))
        tags = meta.get("tag_list") or []
        tag_str = ", ".join(str(t) for t in tags if t)
        parts = []
        if title:
            parts.append(f"title: {title}")
        if artist:
            parts.append(f"artist: {artist}")
        if album:
            parts.append(f"album: {album}")
        if tag_str:
            parts.append(f"tags: {tag_str}")
        return " | ".join(parts) if parts else f"track={track_id}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bakeoff_track_lookup.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add mcrs/bakeoff/__init__.py mcrs/bakeoff/track_lookup.py tests/test_bakeoff_track_lookup.py
git commit -m "feat(bakeoff): HF-backed TrackMetadataLookup with id_to_metadata"
```

---

## Task 3: Replay core (`build_turn_inputs` + `generate_for_model`)

**Files:**
- Create: `mcrs/bakeoff/replay.py`
- Test: `tests/test_bakeoff_replay.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bakeoff_replay.py
from __future__ import annotations

from mcrs.bakeoff.replay import build_turn_inputs
from mcrs.bakeoff.track_lookup import TrackMetadataLookup


def _conversations():
    # turn 1: user asks, music recommended, assistant replies; turn 2: user follows up
    return [
        {"turn_number": 1, "role": "user", "content": "play smoky lounge"},
        {"turn_number": 1, "role": "music", "content": "t1"},
        {"turn_number": 1, "role": "assistant", "content": "Here's a smoky one."},
        {"turn_number": 2, "role": "user", "content": "another like it"},
        {"turn_number": 2, "role": "music", "content": "t2"},
        {"turn_number": 2, "role": "assistant", "content": "Try this."},
    ]


def _lookup():
    return TrackMetadataLookup.from_rows([
        {"track_id": "t1", "track_name": ["Buena"], "artist_name": ["Morphine"],
         "album_name": ["Yes"], "tag_list": ["smoky"]},
        {"track_id": "t9", "track_name": ["Rec"], "artist_name": ["A"],
         "album_name": ["B"], "tag_list": []},
    ])


def test_build_turn_inputs_history_and_recommend_item():
    sys_prompt, chat_history, recommend_item = build_turn_inputs(
        conversations=_conversations(),
        target_turn_number=2,
        top_track_id="t9",
        lookup=_lookup(),
        system_prompt="SYS",
    )
    assert sys_prompt == "SYS"
    # history is everything before turn 2; music turn rewritten to metadata
    roles = [m["role"] for m in chat_history]
    assert roles == ["user", "music", "assistant"]
    assert "Buena" in chat_history[1]["content"]  # t1 rewritten via lookup
    assert "Rec" in recommend_item  # top track t9 metadata
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bakeoff_replay.py -v`
Expected: FAIL — `ModuleNotFoundError: mcrs.bakeoff.replay`

- [ ] **Step 3: Implement**

```python
# mcrs/bakeoff/replay.py
"""Replay response generation over fixed retrieval results."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from mcrs.bakeoff.track_lookup import TrackMetadataLookup
from mcrs.inference_utils import chat_history_parser


def build_turn_inputs(
    conversations: list[dict],
    target_turn_number: int,
    top_track_id: str,
    lookup: TrackMetadataLookup,
    system_prompt: str,
) -> tuple[str, list[dict], str]:
    """Return (system_prompt, chat_history, recommend_item) for one turn,
    reusing the production chat_history_parser with `lookup` as item_db."""
    music_crs = SimpleNamespace(item_db=lookup)
    chat_history, _user_query = chat_history_parser(
        conversations, music_crs, target_turn_number
    )
    recommend_item = lookup.id_to_metadata(top_track_id)
    return system_prompt, chat_history, recommend_item


def generate_for_model(lm: Any, turns: list[dict], system_prompt: str,
                       lookup: TrackMetadataLookup, conversations_by_session: dict,
                       max_new_tokens: int = 256) -> list[dict]:
    """For each turn record {session_id, turn_number, top_track_id}, generate a
    response with `lm` (a LITELLM_LM). Returns enriched records with `response`."""
    out = []
    for t in turns:
        convs = conversations_by_session[t["session_id"]]
        sys_p, history, item = build_turn_inputs(
            convs, t["turn_number"], t["top_track_id"], lookup, system_prompt
        )
        resp = lm.response_generation(sys_p, history, item, max_new_tokens=max_new_tokens)
        out.append({**t, "response": resp})
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bakeoff_replay.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Add a generate_for_model test with a fake LM**

Append to `tests/test_bakeoff_replay.py`:

```python
def test_generate_for_model_uses_lm():
    from mcrs.bakeoff.replay import generate_for_model

    class FakeLM:
        def response_generation(self, sys_p, history, item, max_new_tokens=256):
            return f"resp:{item[:10]}"

    convs = {"s1": _conversations()}
    turns = [{"session_id": "s1", "turn_number": 2, "top_track_id": "t9"}]
    recs = generate_for_model(FakeLM(), turns, "SYS", _lookup(), convs)
    assert recs[0]["response"].startswith("resp:")
    assert recs[0]["session_id"] == "s1"
```

Run: `python -m pytest tests/test_bakeoff_replay.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add mcrs/bakeoff/replay.py tests/test_bakeoff_replay.py
git commit -m "feat(bakeoff): replay core reusing chat_history_parser"
```

---

## Task 4: Judge rubric, parsing, normalization

**Files:**
- Create: `mcrs/bakeoff/judge.py`
- Test: `tests/test_bakeoff_judge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bakeoff_judge.py
from __future__ import annotations

import pytest

from mcrs.bakeoff.judge import (
    build_judge_prompt,
    parse_judge_json,
    normalize_score,
    aggregate_model_report,
)


def test_normalize_score_maps_1_to_0_and_5_to_1():
    assert normalize_score(1) == 0.0
    assert normalize_score(5) == 1.0
    assert normalize_score(3) == 0.5


def test_parse_judge_json_extracts_scores():
    raw = 'Sure: {"personalization": 4, "explanation": 2}'
    d = parse_judge_json(raw)
    assert d == {"personalization": 4, "explanation": 2}


def test_parse_judge_json_clamps_and_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_judge_json("no json here")


def test_build_judge_prompt_contains_response_and_axes():
    p = build_judge_prompt(
        conversation="user: hi", response="Try this jazzy track.", track="title: X"
    )
    assert "Try this jazzy track." in p
    assert "personalization" in p.lower()
    assert "explanation" in p.lower()


def test_aggregate_model_report_averages_axes_and_panel():
    # two turns, two judges
    per_turn = [
        {"turn": 1, "judges": {"gemini": {"personalization": 5, "explanation": 5},
                                "neutral": {"personalization": 3, "explanation": 3}}},
        {"turn": 2, "judges": {"gemini": {"personalization": 1, "explanation": 1},
                                "neutral": {"personalization": 1, "explanation": 1}}},
    ]
    rep = aggregate_model_report("gemma-27b", per_turn, distinct2=0.42)
    assert rep["tag"] == "gemma-27b"
    assert rep["distinct2"] == 0.42
    # gemini personalization avg over turns = (1.0 + 0.0)/2 = 0.5
    assert rep["personalization_by_judge"]["gemini"] == pytest.approx(0.5)
    # panel personalization = mean of judge means: (0.5 + 0.25)/2 = 0.375
    assert rep["personalization_panel"] == pytest.approx(0.375)
    # combined = mean(personalization_panel, explanation_panel)
    assert rep["combined"] == pytest.approx(
        (rep["personalization_panel"] + rep["explanation_panel"]) / 2
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bakeoff_judge.py -v`
Expected: FAIL — `ModuleNotFoundError: mcrs.bakeoff.judge`

- [ ] **Step 3: Implement**

```python
# mcrs/bakeoff/judge.py
"""G-Eval-style proxy judge for the response bake-off.

The official server-side judge prompt is undisclosed; this is a reconstructed
proxy for RELATIVE ranking only. Two axes scored 1-5: personalization and
explanation quality. Normalized (s-1)/4.
"""
from __future__ import annotations

import json
import re
from statistics import mean

JUDGE_SYSTEM = (
    "You are a strict evaluator of a music chatbot's reply. Score the reply on "
    "two axes, each an integer 1-5:\n"
    "- personalization: is it tailored to the listener's stated taste/request/history, "
    "and is it in the listener's language?\n"
    "- explanation: is the 'why this track' clear, honest about any mismatch (not "
    "overselling), natural, and non-repetitive?\n"
    'Respond ONLY with JSON: {"personalization": <1-5>, "explanation": <1-5>}'
)


def build_judge_prompt(conversation: str, response: str, track: str) -> str:
    return (
        f"{JUDGE_SYSTEM}\n\n"
        f"[CONVERSATION SO FAR]\n{conversation}\n\n"
        f"[RECOMMENDED TRACK]\n{track}\n\n"
        f"[CHATBOT REPLY TO SCORE]\n{response}\n\n"
        "JSON:"
    )


def parse_judge_json(raw: str) -> dict:
    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object in judge output: {raw!r}")
    obj = json.loads(m.group(0))
    out = {}
    for axis in ("personalization", "explanation"):
        if axis not in obj:
            raise ValueError(f"missing axis {axis} in {obj!r}")
        out[axis] = max(1, min(5, int(round(float(obj[axis])))))
    return out


def normalize_score(s: float) -> float:
    return (float(s) - 1.0) / 4.0


def aggregate_model_report(tag: str, per_turn: list[dict], distinct2: float) -> dict:
    """per_turn: [{turn, judges: {judge_name: {personalization, explanation}}}]"""
    judge_names = sorted({j for t in per_turn for j in t["judges"]})
    by_judge = {axis: {} for axis in ("personalization", "explanation")}
    for axis in ("personalization", "explanation"):
        for jn in judge_names:
            vals = [normalize_score(t["judges"][jn][axis]) for t in per_turn if jn in t["judges"]]
            by_judge[axis][jn] = mean(vals) if vals else 0.0
    pers_panel = mean(by_judge["personalization"].values()) if judge_names else 0.0
    expl_panel = mean(by_judge["explanation"].values()) if judge_names else 0.0
    return {
        "tag": tag,
        "distinct2": distinct2,
        "personalization_by_judge": by_judge["personalization"],
        "explanation_by_judge": by_judge["explanation"],
        "personalization_panel": pers_panel,
        "explanation_panel": expl_panel,
        "combined": (pers_panel + expl_panel) / 2,
        "n_turns": len(per_turn),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bakeoff_judge.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add mcrs/bakeoff/judge.py tests/test_bakeoff_judge.py
git commit -m "feat(bakeoff): G-Eval proxy judge rubric, parsing, aggregation"
```

---

## Task 5: Models registry config

**Files:**
- Create: `configs/bakeoff/models.yaml`
- Test: `tests/test_bakeoff_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bakeoff_config.py
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
    # thinking explicitly disabled where needed
    qwen8 = next(g for g in gens if g["tag"] == "qwen3-8b")
    assert qwen8["completion_kwargs"]["extra_body"]["reasoning"]["enabled"] is False
    nano = next(g for g in gens if g["tag"] == "gpt5-nano")
    assert nano["completion_kwargs"]["reasoning_effort"] == "minimal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bakeoff_config.py -v`
Expected: FAIL — file not found

- [ ] **Step 3: Implement**

```yaml
# configs/bakeoff/models.yaml
# Response-generation bake-off candidate registry. All via OpenRouter
# (OPENROUTER_API_KEY). All generators run non-thinking.
generators:
  - tag: llama-1b
    model_name: openrouter/meta-llama/llama-3.2-1b-instruct
    completion_kwargs: {}
  - tag: gemma-4b
    model_name: openrouter/google/gemma-3-4b-it
    completion_kwargs: {}
  - tag: llama-3b
    model_name: openrouter/meta-llama/llama-3.2-3b-instruct
    completion_kwargs: {}
  - tag: qwen3-8b
    model_name: openrouter/qwen/qwen3-8b
    completion_kwargs:
      extra_body:
        reasoning:
          enabled: false
  - tag: deepseek-flash
    model_name: openrouter/deepseek/deepseek-v4-flash
    completion_kwargs: {}
  - tag: gemma-12b
    model_name: openrouter/google/gemma-3-12b-it
    completion_kwargs: {}
  - tag: gemma-27b
    model_name: openrouter/google/gemma-3-27b-it
    completion_kwargs: {}
  - tag: qwen3-30b-a3b
    model_name: openrouter/qwen/qwen3-30b-a3b-instruct-2507
    completion_kwargs: {}
  - tag: gpt5-nano
    model_name: openrouter/openai/gpt-5-nano
    completion_kwargs:
      reasoning_effort: minimal
  - tag: gemini-flash-lite
    model_name: openrouter/google/gemini-2.5-flash-lite
    completion_kwargs: {}

judges:
  gemini:
    model_name: openrouter/google/gemini-2.5-flash
  neutral:
    model_name: openrouter/openai/gpt-5-mini

defaults:
  temperature: 0.7
  max_tokens: 256
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bakeoff_config.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add configs/bakeoff/models.yaml tests/test_bakeoff_config.py
git commit -m "feat(bakeoff): candidate + judge model registry"
```

---

## Task 6: Generation CLI (`scripts/response_bakeoff.py`)

**Files:**
- Create: `scripts/response_bakeoff.py`
- Test: `tests/test_response_bakeoff_cli.py`

- [ ] **Step 1: Write the failing test (collect_turns helper)**

```python
# tests/test_response_bakeoff_cli.py
from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "response_bakeoff", Path("scripts/response_bakeoff.py")
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_collect_turns_filters_slice_and_takes_top1():
    predictions = [
        {"session_id": "s1", "turn_number": 1, "predicted_track_ids": ["a", "b"]},
        {"session_id": "s1", "turn_number": 2, "predicted_track_ids": ["c"]},
        {"session_id": "s2", "turn_number": 1, "predicted_track_ids": ["d"]},
    ]
    turns = mod.collect_turns(predictions, session_ids={"s1"})
    assert turns == [
        {"session_id": "s1", "turn_number": 1, "top_track_id": "a"},
        {"session_id": "s1", "turn_number": 2, "top_track_id": "c"},
    ]


def test_collect_turns_skips_empty_predictions():
    predictions = [{"session_id": "s1", "turn_number": 1, "predicted_track_ids": []}]
    assert mod.collect_turns(predictions, session_ids={"s1"}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_response_bakeoff_cli.py -v`
Expected: FAIL — file not found / `collect_turns` missing

- [ ] **Step 3: Implement**

```python
# scripts/response_bakeoff.py
"""Replay response generation across candidate models on a fixed slice.

Reads existing retrieval predictions (top-1 track per turn), reconstructs the
production prompt inputs, and generates a response per candidate model. Outputs
one JSON per model under exp/bakeoff/responses/.

Usage:
  python scripts/response_bakeoff.py \
    --predictions exp/inference/devset/v0plus_compiler_all_retrievers_devset.json \
    --slice exp/subsets/bakeoff_smoke_8.json \
    --models configs/bakeoff/models.yaml \
    --out_dir exp/bakeoff/responses
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def collect_turns(predictions: list[dict], session_ids: set[str]) -> list[dict]:
    turns = []
    for r in predictions:
        if r["session_id"] not in session_ids:
            continue
        ids = r.get("predicted_track_ids") or []
        if not ids:
            continue
        turns.append({
            "session_id": r["session_id"],
            "turn_number": r["turn_number"],
            "top_track_id": ids[0],
        })
    turns.sort(key=lambda t: (t["session_id"], t["turn_number"]))
    return turns


def _load_system_prompt(prompts_dir: Path) -> str:
    roleplay = (prompts_dir / "roleplay.txt").read_text(encoding="utf-8")
    response = (prompts_dir / "response_generation.txt").read_text(encoding="utf-8")
    return roleplay + response


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--slice", required=True)
    ap.add_argument("--models", default="configs/bakeoff/models.yaml")
    ap.add_argument("--prompts_dir", default="mcrs/system_prompts")
    ap.add_argument("--out_dir", default="exp/bakeoff/responses")
    ap.add_argument("--only", default=None, help="comma-separated tags to run")
    args = ap.parse_args()

    predictions = json.loads(Path(args.predictions).read_text())
    session_ids = set(json.loads(Path(args.slice).read_text())["session_ids"])
    cfg = yaml.safe_load(Path(args.models).read_text())
    defaults = cfg.get("defaults", {})
    turns = collect_turns(predictions, session_ids)
    print(f"slice sessions={len(session_ids)} turns={len(turns)}")

    # Conversations + metadata from HF (no LanceDB needed).
    from datasets import load_dataset
    from mcrs.bakeoff.track_lookup import TrackMetadataLookup
    from mcrs.bakeoff.replay import generate_for_model
    from mcrs.lm_modules.litellm_chat import LITELLM_LM

    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    convs_by_session = {r["session_id"]: r["conversations"]
                        for r in ds if r["session_id"] in session_ids}
    lookup = TrackMetadataLookup.from_hf()
    system_prompt = _load_system_prompt(Path(args.prompts_dir))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None

    for g in cfg["generators"]:
        if only and g["tag"] not in only:
            continue
        print(f"== generating: {g['tag']} ({g['model_name']})")
        lm = LITELLM_LM(
            model_name=g["model_name"],
            temperature=defaults.get("temperature", 0.7),
            max_tokens=defaults.get("max_tokens", 256),
            completion_kwargs=g.get("completion_kwargs") or {},
        )
        recs = generate_for_model(
            lm, turns, system_prompt, lookup, convs_by_session,
            max_new_tokens=defaults.get("max_tokens", 256),
        )
        (out_dir / f"{g['tag']}.json").write_text(json.dumps(recs, indent=2))
        print(f"   wrote {len(recs)} responses -> {out_dir / (g['tag'] + '.json')}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_response_bakeoff_cli.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/response_bakeoff.py tests/test_response_bakeoff_cli.py
git commit -m "feat(bakeoff): response generation CLI (replay over fixed slice)"
```

---

## Task 7: Judge CLI (`scripts/judge_responses.py`)

**Files:**
- Create: `scripts/judge_responses.py`
- Test: `tests/test_judge_responses_cli.py`

- [ ] **Step 1: Write the failing test (report rendering)**

```python
# tests/test_judge_responses_cli.py
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
    assert md.index("strong") < md.index("weak")  # sorted by combined desc
    assert "Distinct-2" in md and "Combined" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_judge_responses_cli.py -v`
Expected: FAIL — file not found / `render_markdown` missing

- [ ] **Step 3: Implement**

```python
# scripts/judge_responses.py
"""Judge bake-off responses with a Gemini+neutral panel + Distinct-2.

Usage:
  python scripts/judge_responses.py \
    --responses_dir exp/bakeoff/responses \
    --models configs/bakeoff/models.yaml \
    --out_dir exp/bakeoff
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from evaluator.metrics.metrics_diversity import compute_lexical_diversity
from mcrs.bakeoff.judge import (
    aggregate_model_report,
    build_judge_prompt,
    parse_judge_json,
)


def _conversation_text(convs: list[dict], turn_number: int) -> str:
    lines = []
    for c in convs:
        if c["turn_number"] >= turn_number:
            break
        if c["role"] in ("user", "assistant"):
            lines.append(f"{c['role']}: {c['content']}")
    return "\n".join(lines)


def render_markdown(reports: list[dict]) -> str:
    rows = sorted(reports, key=lambda r: r["combined"], reverse=True)
    out = ["# Response bake-off report", "",
           "| Model | Distinct-2 | Personalization (panel) | Explanation (panel) | Combined | turns |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(
            f"| {r['tag']} | {r['distinct2']:.3f} | {r['personalization_panel']:.3f} "
            f"| {r['explanation_panel']:.3f} | {r['combined']:.3f} | {r['n_turns']} |"
        )
    out += ["", "## Per-judge (personalization / explanation)", ""]
    for r in rows:
        out.append(
            f"- **{r['tag']}**: "
            + ", ".join(
                f"{jn}={r['personalization_by_judge'][jn]:.2f}/{r['explanation_by_judge'][jn]:.2f}"
                for jn in sorted(r["personalization_by_judge"])
            )
        )
    out += ["", "_Proxy judge — relative ranking only; official Gemini prompt is undisclosed._"]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses_dir", default="exp/bakeoff/responses")
    ap.add_argument("--models", default="configs/bakeoff/models.yaml")
    ap.add_argument("--out_dir", default="exp/bakeoff")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.models).read_text())
    judges = cfg["judges"]

    from datasets import load_dataset
    from mcrs.lm_modules.litellm_client import LiteLLMChatClient
    from mcrs.bakeoff.track_lookup import TrackMetadataLookup

    lookup = TrackMetadataLookup.from_hf()
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    convs_by_session = {r["session_id"]: r["conversations"] for r in ds}

    judge_clients = {
        name: LiteLLMChatClient(model_name=spec["model_name"], temperature=0.0, max_tokens=32)
        for name, spec in judges.items()
    }

    reports = []
    for resp_file in sorted(Path(args.responses_dir).glob("*.json")):
        tag = resp_file.stem
        recs = json.loads(resp_file.read_text())
        per_turn = []
        for rec in recs:
            convs = convs_by_session.get(rec["session_id"], [])
            conv_text = _conversation_text(convs, rec["turn_number"])
            track = lookup.id_to_metadata(rec["top_track_id"])
            prompt = build_judge_prompt(conv_text, rec["response"], track)
            judges_scores = {}
            for jn, client in judge_clients.items():
                raw = client.chat(messages=[{"role": "user", "content": prompt}])
                try:
                    judges_scores[jn] = parse_judge_json(raw)
                except ValueError:
                    judges_scores[jn] = {"personalization": 1, "explanation": 1}
            per_turn.append({"turn": rec["turn_number"], "judges": judges_scores})
        distinct2 = compute_lexical_diversity([r["response"] for r in recs])
        reports.append(aggregate_model_report(tag, per_turn, distinct2))
        print(f"judged {tag}: combined={reports[-1]['combined']:.3f}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(reports, indent=2))
    (out_dir / "report.md").write_text(render_markdown(reports))
    print(f"wrote {out_dir/'report.md'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_judge_responses_cli.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Run the full bake-off test suite**

Run: `python -m pytest tests/test_litellm_lm_passthrough.py tests/test_bakeoff_track_lookup.py tests/test_bakeoff_replay.py tests/test_bakeoff_judge.py tests/test_bakeoff_config.py tests/test_response_bakeoff_cli.py tests/test_judge_responses_cli.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add scripts/judge_responses.py tests/test_judge_responses_cli.py
git commit -m "feat(bakeoff): panel judge CLI + Distinct-2 report"
```

---

## Task 8: Smoke run (real API — integration, manual)

**Files:** none (uses the artifacts above)

This is the actual experiment, not a unit test. Requires `OPENROUTER_API_KEY` in the env and network/HF access.

- [ ] **Step 1: Sanity-run one cheap model on the slice**

`exp/...` artifacts live in the **main checkout** (gitignored), so reference them via `$MAIN`:

```bash
export OPENROUTER_API_KEY=...   # must be set
MAIN=/Users/npatta01/data/projects/music-conversational-music-recomender-2026
python scripts/response_bakeoff.py \
  --predictions "$MAIN/exp/inference/devset/v0plus_compiler_all_retrievers_devset.json" \
  --slice "$MAIN/exp/subsets/bakeoff_smoke_8.json" \
  --only gemma-4b
```
Expected: writes `exp/bakeoff/responses/gemma-4b.json` with ~64 non-empty responses. Eyeball 2-3.

- [ ] **Step 2: Verify thinking is disabled where required**

Run `--only qwen3-8b` and `--only gpt5-nano`; confirm responses are 1-3 sentences with no visible reasoning preamble. If a preamble leaks, the `completion_kwargs` for that model needs adjustment before the full run.

- [ ] **Step 3: Run all generators**

```bash
MAIN=/Users/npatta01/data/projects/music-conversational-music-recomender-2026
python scripts/response_bakeoff.py \
  --predictions "$MAIN/exp/inference/devset/v0plus_compiler_all_retrievers_devset.json" \
  --slice "$MAIN/exp/subsets/bakeoff_smoke_8.json"
```
Expected: 10 files under `exp/bakeoff/responses/`.

- [ ] **Step 4: Judge + report**

```bash
python scripts/judge_responses.py --responses_dir exp/bakeoff/responses
```
Expected: `exp/bakeoff/report.md` ranks models; the `llama-1b` control sits clearly below the mid-tier models (rubric discriminates). Inspect per-judge columns for the Gemini self-preference gap.

- [ ] **Step 5: Record the outcome**

Summarize the ranked table back to the user. Do NOT auto-flip any production config — choosing the winner and wiring issue #96 §B is a follow-up decision.

---

## Notes / known limitations (from spec)

- **English-only slice** — multilingual ability is NOT tested here; add non-English sessions before any blind submission.
- **Proxy judge ≠ official judge** — undisclosed prompt; relative ranking signal only.
- **Retrieval held fixed** — does not test full-pipeline integration with the LM on (issue #96 §B).
- Metadata strings from `TrackMetadataLookup` carry the track facts but need not byte-match the LanceDB catalog's formatting.
