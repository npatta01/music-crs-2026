from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mcrs.conversation_state.schema import ConversationStateV0Plus


def _load_script_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "extract_state.py"
    spec = importlib.util.spec_from_file_location("extract_state_script", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_extract_state_cli_is_config_and_sessions_only():
    module = _load_script_module()

    args = module.build_parser().parse_args(
        ["--tid", "local_state", "--sessions-file", "sessions.json"]
    )

    assert args.tid == "local_state"
    assert args.sessions_file == "sessions.json"
    with pytest.raises(SystemExit):
        module.build_parser().parse_args(["--text", "play smoky jazz"])


def test_extract_state_cli_supports_optional_sessions_file_and_file_output():
    module = _load_script_module()

    args = module.build_parser().parse_args(
        [
            "--tid",
            "state_ranker_v10_lgbm_blindset_B",
            "--turn-scope",
            "final",
            "--output-dir",
            "cache/state_extraction/blindset_B",
            "--litellm-cache-only",
            "--skip-existing",
        ]
    )

    assert args.sessions_file is None
    assert args.turn_scope == "final"
    assert args.output_dir == "cache/state_extraction/blindset_B"
    assert args.litellm_cache_only is True
    assert args.skip_existing is True


def test_extract_state_loads_config_and_defaults_ollama_without_api_key(tmp_path, monkeypatch):
    module = _load_script_module()
    monkeypatch.setenv("LITELLM_PROXY_KEY", "proxy-key-from-env")
    config_path = tmp_path / "local_state.yaml"
    config_path.write_text(
        "\n".join(
            [
                "test_dataset_name: talkpl-ai/TalkPlayData-Challenge-Dataset",
                "qu_kwargs:",
                "  extractor:",
                "    model_name: ollama_chat/qwen3:8b",
                "    temperature: 0.2",
                "    extra_params:",
                "      keep_alive: 30m",
                "state_extraction:",
                "  cache_dir: cache/litellm-state",
            ]
        ),
        encoding="utf-8",
    )

    loaded = module.load_config(config_path=config_path, tid=None, config_dir=tmp_path)
    extractor = module.extractor_config_from_config(loaded)

    assert extractor["model_name"] == "ollama_chat/qwen3:8b"
    assert extractor["api_base"] == "http://localhost:11434"
    assert extractor["api_key"] is None
    assert extractor["temperature"] == 0.2
    assert extractor["extra_params"] == {"keep_alive": "30m"}


def test_extract_state_run_loads_dotenv_before_building_extractor(tmp_path, monkeypatch):
    module = _load_script_module()
    monkeypatch.delenv("LITELLM_PROXY_KEY", raising=False)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text("LITELLM_PROXY_KEY=from-dotenv\n", encoding="utf-8")
    config_path = tmp_path / "local_state.yaml"
    config_path.write_text(
        "\n".join(
            [
                "test_dataset_name: ignored-dataset",
                "qu_kwargs:",
                "  extractor:",
                "    model_name: openrouter/google/gemma-3-12b-it",
                "state_extraction:",
                "  cache_dir: ''",
                "  metadata_dataset: ignored-metadata",
                "  metadata_split: all_tracks",
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "states.jsonl"
    dataset = [
        {
            "session_id": "s1",
            "conversations": [
                {"turn_number": 1, "role": "user", "content": "play Morphine"},
            ],
        }
    ]
    metadata = [{"track_id": "t-morphine-1", "artist_name": ["Morphine"], "track_name": ["Cure for Pain"]}]
    seen: dict[str, str | None] = {}

    monkeypatch.setattr(
        module,
        "load_dataset",
        lambda name, split: metadata if name == "ignored-metadata" else dataset,
    )
    monkeypatch.setattr(module, "setup_litellm_cache", lambda **kwargs: False)

    class FakeExtractor:
        def extract(self, conversation, played_track_ids):
            return ConversationStateV0Plus(turn_intent="play Morphine", intent_mode="open_explore")

    def fake_build_extractor(config):
        seen["api_key"] = config["api_key"]
        return FakeExtractor()

    monkeypatch.setattr(module, "build_extractor", fake_build_extractor)

    module.run(
        SimpleNamespace(
            config=str(config_path),
            tid=None,
            config_dir=str(tmp_path),
            sessions_file=None,
            output=str(output_path),
            output_dir=None,
            turn_scope="all",
        )
    )

    assert seen["api_key"] == "from-dotenv"


def test_extract_state_file_output_skips_error_rows(tmp_path):
    module = _load_script_module()
    rows = [
        {
            "session_id": "s1",
            "turn_number": 1,
            "state": {"turn_intent": "play Morphine", "intent_mode": "open_explore"},
            "error": None,
        },
        {
            "session_id": "s1",
            "turn_number": 2,
            "state": None,
            "error": "LiteLLM cache miss",
        },
    ]

    written = module._write_file_output(tmp_path, rows)

    assert written == 1
    assert (tmp_path / "s1" / "turn_1.json").exists()
    assert not (tmp_path / "s1" / "turn_2.json").exists()


def test_extract_state_loads_session_ids_file(tmp_path):
    module = _load_script_module()
    object_path = tmp_path / "sessions_object.json"
    object_path.write_text(json.dumps({"session_ids": ["s1", "s2"]}), encoding="utf-8")
    list_path = tmp_path / "sessions_list.json"
    list_path.write_text(json.dumps(["s3"]), encoding="utf-8")

    assert module.load_session_ids(object_path) == {"s1", "s2"}
    assert module.load_session_ids(list_path) == {"s3"}


def test_extract_state_builds_cases_for_requested_sessions():
    module = _load_script_module()
    dataset = [
        {
            "session_id": "s1",
            "conversations": [
                {"turn_number": 1, "role": "user", "content": "play Morphine"},
                {"turn_number": 1, "role": "music", "content": "t-morphine-1"},
                {"turn_number": 1, "role": "assistant", "content": "try this"},
                {"turn_number": 2, "role": "user", "content": "more like that"},
            ],
        },
        {
            "session_id": "s2",
            "conversations": [
                {"turn_number": 1, "role": "user", "content": "ignore me"},
            ],
        },
    ]

    cases = module.build_extraction_cases(
        dataset,
        session_ids={"s1"},
        track_labels={"t-morphine-1": "Morphine - Cure for Pain"},
    )

    assert [(case.session_id, case.turn_number) for case in cases] == [("s1", 1), ("s1", 2)]
    assert cases[0].conversation == [{"turn": 1, "role": "user", "text": "play Morphine"}]
    assert cases[0].played_track_ids == []
    assert cases[1].played_track_ids == ["t-morphine-1"]
    assert cases[1].conversation[-1] == {"turn": 2, "role": "user", "text": "more like that"}
    assert cases[1].conversation[1] == {
        "turn": 1,
        "role": "music",
        "track_id": "t-morphine-1",
        "label": "Morphine - Cure for Pain",
    }


def test_extract_state_builds_final_turn_cases_for_all_sessions():
    module = _load_script_module()
    dataset = [
        {
            "session_id": "s1",
            "conversations": [
                {"turn_number": 1, "role": "user", "content": "play Morphine"},
                {"turn_number": 1, "role": "music", "content": "t-morphine-1"},
                {"turn_number": 2, "role": "user", "content": "more like that"},
            ],
        },
        {
            "session_id": "s2",
            "conversations": [
                {"turn_number": 3, "role": "user", "content": "final request"},
            ],
        },
    ]

    cases = module.build_extraction_cases(
        dataset,
        session_ids=None,
        track_labels={"t-morphine-1": "Morphine - Cure for Pain"},
        turn_scope="final",
    )

    assert [(case.session_id, case.turn_number) for case in cases] == [("s1", 2), ("s2", 3)]
    assert cases[0].played_track_ids == ["t-morphine-1"]
    assert cases[0].conversation[-1] == {"turn": 2, "role": "user", "text": "more like that"}


def test_extract_state_run_writes_jsonl_for_configured_sessions(tmp_path, monkeypatch):
    module = _load_script_module()
    config_path = tmp_path / "local_state.yaml"
    config_path.write_text(
        "\n".join(
            [
                "test_dataset_name: ignored-dataset",
                "qu_kwargs:",
                "  extractor:",
                "    model_name: ollama_chat/qwen3:8b",
                "state_extraction:",
                "  cache_dir: ''",
                "  metadata_dataset: ignored-metadata",
                "  metadata_split: all_tracks",
            ]
        ),
        encoding="utf-8",
    )
    sessions_path = tmp_path / "sessions.json"
    sessions_path.write_text(json.dumps({"session_ids": ["s1"]}), encoding="utf-8")
    output_path = tmp_path / "states.jsonl"

    dataset = [
        {
            "session_id": "s1",
            "conversations": [
                {"turn_number": 1, "role": "user", "content": "play Morphine"},
            ],
        }
    ]
    metadata = [{"track_id": "t-morphine-1", "artist_name": ["Morphine"], "track_name": ["Cure for Pain"]}]

    monkeypatch.setattr(
        module,
        "load_dataset",
        lambda name, split: metadata if name == "ignored-metadata" else dataset,
    )
    monkeypatch.setattr(module, "setup_litellm_cache", lambda **kwargs: False)

    class FakeExtractor:
        def extract(self, conversation, played_track_ids):
            return ConversationStateV0Plus(turn_intent="play Morphine", intent_mode="open_explore")

    monkeypatch.setattr(module, "build_extractor", lambda config: FakeExtractor())

    rows = module.run(
        SimpleNamespace(
            config=str(config_path),
            tid=None,
            config_dir=str(tmp_path),
            sessions_file=str(sessions_path),
            output=str(output_path),
        )
    )

    assert len(rows) == 1
    written = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert written[0]["session_id"] == "s1"
    assert written[0]["turn_number"] == 1
    assert written[0]["state"]["turn_intent"] == "play Morphine"
    assert written[0]["error"] is None


def test_extract_state_run_writes_file_per_turn_output_dir(tmp_path, monkeypatch):
    module = _load_script_module()
    config_path = tmp_path / "local_state.yaml"
    config_path.write_text(
        "\n".join(
            [
                "test_dataset_name: ignored-dataset",
                "qu_kwargs:",
                "  extractor:",
                "    model_name: ollama_chat/qwen3:8b",
                "state_extraction:",
                "  cache_dir: ''",
                "  metadata_dataset: ignored-metadata",
                "  metadata_split: all_tracks",
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "state_cache"

    dataset = [
        {
            "session_id": "s1",
            "conversations": [
                {"turn_number": 1, "role": "user", "content": "play Morphine"},
                {"turn_number": 1, "role": "music", "content": "t-morphine-1"},
                {"turn_number": 2, "role": "user", "content": "more like that"},
            ],
        }
    ]
    metadata = [{"track_id": "t-morphine-1", "artist_name": ["Morphine"], "track_name": ["Cure for Pain"]}]

    monkeypatch.setattr(
        module,
        "load_dataset",
        lambda name, split: metadata if name == "ignored-metadata" else dataset,
    )
    monkeypatch.setattr(module, "setup_litellm_cache", lambda **kwargs: False)

    class FakeExtractor:
        def extract(self, conversation, played_track_ids, cache_context=None):
            turn = cache_context["turn_number"]
            return ConversationStateV0Plus(
                turn_intent=f"turn {turn}",
                intent_mode="open_explore",
            )

    monkeypatch.setattr(module, "build_extractor", lambda config: FakeExtractor())

    rows = module.run(
        SimpleNamespace(
            config=str(config_path),
            tid=None,
            config_dir=str(tmp_path),
            sessions_file=None,
            output=None,
            output_dir=str(output_dir),
            turn_scope="all",
        )
    )

    assert len(rows) == 2
    turn1_path = output_dir / "s1" / "turn_1.json"
    turn2_path = output_dir / "s1" / "turn_2.json"
    assert turn1_path.exists()
    assert turn2_path.exists()
    assert json.loads(turn1_path.read_text(encoding="utf-8"))["state"]["turn_intent"] == "turn 1"
    assert json.loads(turn2_path.read_text(encoding="utf-8"))["state"]["turn_intent"] == "turn 2"


def test_extract_state_run_skip_existing_avoids_extractor_for_existing_files(tmp_path, monkeypatch):
    module = _load_script_module()
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    config_path = tmp_path / "local_state.yaml"
    config_path.write_text(
        "\n".join(
            [
                "test_dataset_name: ignored-dataset",
                "qu_kwargs:",
                "  extractor:",
                "    model_name: ollama_chat/qwen3:8b",
                "state_extraction:",
                "  cache_dir: ''",
                "  metadata_dataset: ignored-metadata",
                "  metadata_split: all_tracks",
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "state_cache"
    existing_path = output_dir / "s1" / "turn_1.json"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_text(
        json.dumps(
            {
                "session_id": "s1",
                "turn_number": 1,
                "state": {
                    "turn_intent": "existing state",
                    "intent_mode": "open_explore",
                },
                "error": None,
            }
        ),
        encoding="utf-8",
    )

    dataset = [
        {
            "session_id": "s1",
            "conversations": [
                {"turn_number": 1, "role": "user", "content": "play Morphine"},
            ],
        }
    ]
    metadata = [{"track_id": "t-morphine-1", "artist_name": ["Morphine"], "track_name": ["Cure for Pain"]}]

    monkeypatch.setattr(
        module,
        "load_dataset",
        lambda name, split: metadata if name == "ignored-metadata" else dataset,
    )
    monkeypatch.setattr(module, "setup_litellm_cache", lambda **kwargs: False)

    class FailingExtractor:
        def extract(self, conversation, played_track_ids, cache_context=None):
            raise AssertionError("existing file should be reused")

    monkeypatch.setattr(module, "build_extractor", lambda config: FailingExtractor())

    rows = module.run(
        SimpleNamespace(
            config=str(config_path),
            tid=None,
            config_dir=str(tmp_path),
            sessions_file=None,
            output=None,
            output_dir=str(output_dir),
            turn_scope="all",
            skip_existing=True,
        )
    )

    assert len(rows) == 1
    assert rows[0]["state"]["turn_intent"] == "existing state"
