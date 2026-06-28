import json
import sys
import types

import pytest

import mcrs.debug.rerank as debug_rerank
import mcrs.debug.runtime as debug_runtime
from mcrs.conversation_state.schema import ConversationStateV0Plus, MentionedEntity
from mcrs.debug.cli import main
from mcrs.debug.formatting import _track_payload
from mcrs.debug.artifacts import (
    _catalog_hit,
    _first_str,
    _str_values,
    _surface_key,
    catalog_search,
    load_run_aliases,
    resolve_run_alias,
    resolve_session_prefix,
)


def test_resolve_run_alias_expands_relative_paths(tmp_path):
    run_file = tmp_path / "runs.json"
    run_file.write_text(
        json.dumps(
            {
                "blind-b-current": {
                    "trace": "exp/inference/run_trace.jsonl",
                    "prediction": "exp/inference/run.json",
                    "audit": "exp/analysis/audit.json",
                }
            }
        ),
        encoding="utf-8",
    )

    aliases = load_run_aliases(run_file)
    resolved = resolve_run_alias(aliases, "blind-b-current", base_dir=tmp_path)

    assert resolved.trace == tmp_path / "exp/inference/run_trace.jsonl"
    assert resolved.prediction == tmp_path / "exp/inference/run.json"
    assert resolved.audit == tmp_path / "exp/analysis/audit.json"
    assert resolved.catalog_db_uri == tmp_path / "cache/lancedb"
    assert resolved.catalog_table == "music_track_catalog"


def test_resolve_session_prefix_rejects_ambiguous_prefixes():
    session_ids = [
        "dacd3a58-34a0-439b-90eb-7b6aa7ec6fb7",
        "dacd9999-34a0-439b-90eb-7b6aa7ec6fb7",
    ]

    with pytest.raises(ValueError, match="ambiguous session prefix"):
        resolve_session_prefix(session_ids, "dacd")


def test_catalog_search_separates_title_only_from_artist_constrained_matches():
    rows = {
        "t-seether": {
            "track_name": "Fallen",
            "artist_name": ["Seether"],
            "album_name": "Finding Beauty In Negative Spaces",
            "tag_list": ["rock"],
        },
        "t-sarah": {
            "track_name": "Hold On",
            "artist_name": ["Sarah McLachlan"],
            "album_name": "Closer",
            "tag_list": ["folk"],
        },
    }

    result = catalog_search(rows, track="Fallen", artist="Sarah McLachlan")

    assert result.exact == []
    assert [hit.track_id for hit in result.title_or_album_only] == ["t-seether"]
    assert result.contains == []


def test_catalog_search_finds_exact_artist_and_track_match():
    rows = {
        "t-puk": {
            "track_name": "Pumped Up Kicks",
            "artist_name": ["Foster The People"],
            "album_name": "Torches",
            "tag_list": ["whistling", "alternative rock"],
        }
    }

    result = catalog_search(rows, track="Pumped Up Kicks", artist="Foster The People")

    assert [hit.track_id for hit in result.exact] == ["t-puk"]
    assert result.title_or_album_only == []


def test_catalog_search_artist_only_returns_artist_matches():
    rows = {
        "t-one": {
            "track_name": "One",
            "artist_name": ["Target Artist"],
            "album_name": "Album A",
            "tag_list": ["rock"],
        },
        "t-two": {
            "track_name": "Two",
            "artist_name": ["Other Artist"],
            "album_name": "Album B",
            "tag_list": ["pop"],
        },
    }

    result = catalog_search(rows, artist="Target Artist")

    assert [hit.track_id for hit in result.exact] == ["t-one"]
    assert result.title_or_album_only == []
    assert result.contains == []


def test_debug_cli_shim_exports_legacy_surface():
    import mcrs.debug_cli as legacy_debug_cli

    assert legacy_debug_cli.DEFAULT_RUN_FILE == "mcrs_debug_runs.json"
    assert legacy_debug_cli.DEFAULT_CATALOG_DB_URI == "cache/lancedb"
    assert legacy_debug_cli.DEFAULT_CATALOG_TABLE == "music_track_catalog"
    assert legacy_debug_cli.RunArtifacts.__name__ == "RunArtifacts"
    assert legacy_debug_cli.catalog_search is catalog_search
    assert callable(legacy_debug_cli.trace_row)
    assert callable(legacy_debug_cli._load_config_for_args)


def test_debug_tools_shim_exports_legacy_private_helpers():
    import mcrs.debug_tools as legacy_debug_tools

    assert legacy_debug_tools._surface_key is _surface_key
    assert legacy_debug_tools._catalog_hit is _catalog_hit
    assert legacy_debug_tools._first_str is _first_str
    assert legacy_debug_tools._str_values is _str_values


def test_dense_search_command_embeds_query_and_returns_catalog_rows(tmp_path, monkeypatch):
    class FakeEncoder:
        def embed_batch(self, texts):
            assert texts == ["bold abstract cover art with geometric shapes"]
            return [[0.1, 0.2, 0.3]]

    class FakeRetriever:
        def search_embedding(self, query_vector, *, vector_field, topk, distance_type, filter_missing):
            assert query_vector == [0.1, 0.2, 0.3]
            assert vector_field == "image_siglip2"
            assert topk == 2
            assert distance_type == "cosine"
            assert filter_missing is True
            return [("t-cover", 0.91), ("t-other", 0.72)]

    class FakeCatalog:
        def feature_rows(self):
            return {
                "t-cover": {
                    "track_name": "Cover Song",
                    "artist_name": ["Painter"],
                    "album_name": "Abstract Shapes",
                    "tag_list": ["art pop"],
                },
                "t-other": {
                    "track_name": "Other Song",
                    "artist_name": ["Other Artist"],
                    "album_name": "Other Album",
                    "tag_list": ["pop"],
                },
            }

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "qu_kwargs:\n"
        "  encoders:\n"
        "    siglip2_text:\n"
        "      backend: fake\n"
        "  lancedb:\n"
        "    db_uri: fake-db\n"
        "    table_name: fake-table\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "dense.json"
    monkeypatch.setattr(
        debug_runtime,
        "_build_debug_encoder_from_config",
        lambda config, encoder_id, allow_cache_write=False: FakeEncoder(),
        raising=False,
    )
    monkeypatch.setattr(
        debug_runtime,
        "_build_debug_lancedb_retriever",
        lambda config, run, args: FakeRetriever(),
        raising=False,
    )
    monkeypatch.setattr(
        debug_runtime,
        "_load_debug_lancedb_catalog",
        lambda config, run, args: FakeCatalog(),
        raising=False,
    )

    rc = main(
        [
            "dense-search",
            "--config",
            str(config_path),
            "--query",
            "bold abstract cover art with geometric shapes",
            "--encoder-id",
            "siglip2_text",
            "--vector-field",
            "image_siglip2",
            "--limit",
            "2",
            "--out",
            str(out_path),
        ]
    )

    assert rc == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["query"] == "bold abstract cover art with geometric shapes"
    assert payload["encoder_id"] == "siglip2_text"
    assert payload["vector_field"] == "image_siglip2"
    assert payload["hits"][0]["track_id"] == "t-cover"
    assert payload["hits"][0]["score"] == 0.91
    assert payload["hits"][0]["track_name"] == "Cover Song"
    assert payload["hits"][0]["artist_name"] == "Painter"


def test_debug_cli_shim_monkeypatches_still_drive_main(tmp_path, monkeypatch):
    import mcrs.debug_cli as legacy_debug_cli

    class FakeEncoder:
        def embed_batch(self, texts):
            return [[0.4, 0.5]]

    class FakeRetriever:
        def search_embedding(self, query_vector, *, vector_field, topk, distance_type, filter_missing):
            assert query_vector == [0.4, 0.5]
            return [("t-legacy", 0.99)]

    class FakeCatalog:
        def feature_rows(self):
            return {
                "t-legacy": {
                    "track_name": "Legacy Patch",
                    "artist_name": ["Shim Artist"],
                    "album_name": "Compat",
                    "tag_list": ["debug"],
                }
            }

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "qu_kwargs:\n"
        "  encoders:\n"
        "    siglip2_text:\n"
        "      backend: fake\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "legacy-dense.json"
    monkeypatch.setattr(
        legacy_debug_cli,
        "_build_debug_encoder_from_config",
        lambda config, encoder_id, allow_cache_write=False: FakeEncoder(),
    )
    monkeypatch.setattr(
        legacy_debug_cli,
        "_build_debug_lancedb_retriever",
        lambda config, run, args: FakeRetriever(),
    )
    monkeypatch.setattr(
        legacy_debug_cli,
        "_load_debug_lancedb_catalog",
        lambda config, run, args: FakeCatalog(),
    )

    rc = legacy_debug_cli.main(
        [
            "dense-search",
            "--config",
            str(config_path),
            "--query",
            "legacy shim patch",
            "--out",
            str(out_path),
        ]
    )

    assert rc == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["hits"][0]["track_id"] == "t-legacy"
    assert payload["hits"][0]["artist_name"] == "Shim Artist"


def test_dense_search_disables_configured_encoder_cache_by_default(monkeypatch):
    seen = []

    def fake_build_encoder(cfg):
        seen.append(cfg)
        return object()

    monkeypatch.setitem(
        sys.modules,
        "mcrs.qu_modules.compiler_v0plus_qu",
        types.SimpleNamespace(_build_encoder=fake_build_encoder),
    )
    config = {
        "qu_kwargs": {
            "encoders": {
                "siglip2_text": {
                    "backend": "modal_multimodal",
                    "method": "embed_siglip_text",
                    "cache": True,
                }
            }
        }
    }

    debug_runtime._build_debug_encoder_from_config(config, "siglip2_text")

    assert seen[0]["cache"] is False


def test_case_command_prints_focused_turn_from_run_alias(tmp_path, capsys):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "dacd3a58-34a0-439b-90eb-7b6aa7ec6fb7",
                "user_id": "u1",
                "turn_number": 4,
                "trace": {
                    "extracted_state": {
                        "facts": [
                            {
                                "type": "track",
                                "value": "Fallen",
                                "role": "current_target",
                                "relation": "exact_target",
                            }
                        ]
                    },
                    "compiled_state": {"retrieval_profile": "exact_probe"},
                    "resolver": {"anchor_track_values": ["Fallen"]},
                    "routing_tags": {"exact_entity_probe": True},
                    "retrieval": {
                        "branch_queries": {"bm25": {"kind": "bm25"}},
                        "branch_status": {"bm25": {"fired": True, "n_raw_hits": 1000}},
                    },
                    "ranking": {
                        "stages": [
                            {
                                "name": "candidate_fusion",
                                "track_ids": ["t-hold"],
                                "scores": [["t-hold", 1.0]],
                            }
                        ],
                        "final_stage": "candidate_fusion",
                    },
                    "final_recommendation": {"track_ids": ["t-hold"]},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "session_id": "dacd3a58-34a0-439b-90eb-7b6aa7ec6fb7",
                        "turn_number": 4,
                        "latest_user_text": "Please play Sarah McLachlan's Fallen.",
                        "current_request_summary": "Play Fallen by Sarah McLachlan.",
                        "request_type": "exact_track",
                        "llm_judgment": {"verdict": "bad", "reason": "Exact track absent."},
                        "items": [
                            {
                                "rank": 1,
                                "track": {
                                    "track_id": "t-hold",
                                    "track_name": "Hold On",
                                    "artist_name": "Sarah McLachlan",
                                    "album_name": "Closer",
                                    "tags": ["folk"],
                                    "popularity": 38,
                                },
                                "candidate_fusion_rank": 3,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    run_file = tmp_path / "runs.json"
    run_file.write_text(
        json.dumps({"blind": {"trace": str(trace_path), "audit": str(audit_path)}}),
        encoding="utf-8",
    )

    rc = main(["--run-file", str(run_file), "--run", "blind", "case", "dacd3a58", "4"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "Please play Sarah McLachlan's Fallen." in out
    assert "Exact track absent." in out
    assert "Hold On / Sarah McLachlan" in out


def test_track_payload_handles_array_like_tags_without_truthiness():
    class ArrayLike:
        def __bool__(self):
            raise ValueError("ambiguous")

        def tolist(self):
            return ["beautiful", "Dance"]

    payload = _track_payload(
        "t-puk",
        {
            "track_name": "Pumped Up Kicks",
            "artist_name": ["Foster The People"],
            "album_name": "Torches",
            "tag_list": ArrayLike(),
        },
    )

    assert payload["tags"] == ["beautiful", "Dance"]


def _debug_state() -> ConversationStateV0Plus:
    return ConversationStateV0Plus(
        turn_intent="play Morphine",
        intent_mode="new_request",
        track_feedback=[],
        referenced_track_ids=[],
        mentioned_entities=[MentionedEntity(type="artist", value="Morphine", sentiment=1)],
        hard_filters=[],
        explicit_rejections=[],
    )


def test_extract_state_command_writes_state_json(tmp_path, monkeypatch):
    class FakeExtractor:
        def extract(self, conversation, played_track_ids):
            assert conversation == [{"turn": 1, "role": "user", "text": "play Morphine"}]
            assert played_track_ids == ["t-old"]
            return _debug_state()

    config_path = tmp_path / "config.yaml"
    config_path.write_text("qu_kwargs: {}\n", encoding="utf-8")
    conversation_path = tmp_path / "conversation.json"
    conversation_path.write_text(
        json.dumps(
            {
                "conversation": [{"role": "user", "content": "play Morphine"}],
                "played_track_ids": ["t-old"],
            }
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "state.json"
    monkeypatch.setattr(debug_runtime, "_build_extractor_from_config", lambda config: FakeExtractor())

    rc = main(
        [
            "extract-state",
            "--config",
            str(config_path),
            "--conversation",
            str(conversation_path),
            "--out",
            str(out_path),
        ]
    )

    assert rc == 0
    state = json.loads(out_path.read_text(encoding="utf-8"))
    assert state["turn_intent"] == "play Morphine"
    assert state["entities"][0]["value"] == "Morphine"


def test_retrieve_state_command_writes_trace_and_compiled_state(tmp_path, monkeypatch):
    class FakeQU:
        def __init__(self):
            self.extractor = None
            self.last_traces = []

        def batch_compile_track_ids(self, session_memories, topk, user_ids=None, session_meta=None):
            state = self.extractor.state
            assert state.turn_intent == "play Morphine"
            assert session_memories == [[
                {"role": "music", "content": "t-old", "turn_number": 3},
                {"role": "user", "content": "", "turn_number": 4},
            ]]
            assert topk == 20
            assert user_ids == ["u1"]
            assert session_meta == [
                {
                    "session_id": "sid-1",
                    "turn_number": 4,
                    "user_id": "u1",
                    "conversations": [
                        {"role": "music", "turn_number": 3, "content": "t-old"},
                        {"role": "user", "turn_number": 4, "content": ""},
                    ],
                }
            ]
            trace = {
                "extracted_state": state.model_dump(mode="json"),
                "compiled_state": {"retrieval_profile": "artist_probe"},
                "retrieval": {"branches": []},
                "final_recommendation": {"track_ids": ["t-morphine"]},
            }
            self.last_traces = [trace]
            return [["t-morphine"]]

    config_path = tmp_path / "config.yaml"
    config_path.write_text("qu_kwargs: {}\n", encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(_debug_state().model_dump_json(), encoding="utf-8")
    trace_out = tmp_path / "trace.json"
    compiled_out = tmp_path / "compiled.json"
    monkeypatch.setattr(debug_runtime, "_build_state_ranker_from_config", lambda config: FakeQU())

    rc = main(
        [
            "retrieve-state",
            "--config",
            str(config_path),
            "--state",
            str(state_path),
            "--played-track-id",
            "t-old",
            "--session-id",
            "sid-1",
            "--turn",
            "4",
            "--user-id",
            "u1",
            "--trace-out",
            str(trace_out),
            "--compiled-out",
            str(compiled_out),
        ]
    )

    assert rc == 0
    replay_trace = json.loads(trace_out.read_text(encoding="utf-8"))
    assert replay_trace["final_recommendation"]["track_ids"] == ["t-morphine"]
    assert replay_trace["conversations"][0] == {
        "role": "music",
        "turn_number": 3,
        "content": "t-old",
    }
    assert json.loads(compiled_out.read_text(encoding="utf-8")) == {
        "retrieval_profile": "artist_probe"
    }


def test_replay_turn_command_retrieves_from_saved_trace_state(tmp_path, monkeypatch):
    class FakeQU:
        def __init__(self):
            self.extractor = None
            self.last_traces = []

        def batch_compile_track_ids(self, session_memories, topk, user_ids=None, session_meta=None):
            assert self.extractor.state.turn_intent == "play Morphine"
            assert session_memories == [[
                {"role": "music", "content": "t-old", "turn_number": 3},
                {"role": "user", "content": "", "turn_number": 4},
            ]]
            assert user_ids == ["u1"]
            assert session_meta == [
                {
                    "session_id": "sid-1",
                    "turn_number": 4,
                    "user_id": "u1",
                    "conversations": [
                        {"role": "music", "turn_number": 3, "content": "t-old"},
                        {"role": "user", "turn_number": 4, "content": ""},
                    ],
                    "user_profile": {"age_group": "30s"},
                    "conversation_goal": {"category": "discover"},
                    "session_date": "2026-06-28",
                }
            ]
            self.last_traces = [
                {
                    "compiled_state": {"retrieval_profile": "replayed"},
                    "final_recommendation": {"track_ids": ["t-replay"]},
                }
            ]
            return [["t-replay"]]

    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "sid-1",
                "turn_number": 4,
                "user_id": "u1",
                "user_profile": {"age_group": "30s"},
                "conversation_goal": {"category": "discover"},
                "session_date": "2026-06-28",
                "trace": {
                    "extracted_state": _debug_state().model_dump(mode="json"),
                    "resolver": {"played_track_ids": ["t-old"]},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_file = tmp_path / "runs.json"
    run_file.write_text(json.dumps({"blind": {"trace": str(trace_path)}}), encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("qu_kwargs: {}\n", encoding="utf-8")
    trace_out = tmp_path / "replay.json"
    monkeypatch.setattr(debug_runtime, "_build_state_ranker_from_config", lambda config: FakeQU())

    rc = main(
        [
            "--run-file",
            str(run_file),
            "--run",
            "blind",
            "replay-turn",
            "sid",
            "4",
            "--config",
            str(config_path),
            "--trace-out",
            str(trace_out),
        ]
    )

    assert rc == 0
    assert json.loads(trace_out.read_text(encoding="utf-8"))["final_recommendation"]["track_ids"] == [
        "t-replay"
    ]


def test_rerank_subset_command_filters_trace_and_injects_missing_candidate(tmp_path, monkeypatch):
    class FakeReranker:
        def __init__(self):
            self.seen_trace = None
            self.seen_meta = None
            self.seen_fallback = None

        def rerank(self, trace, session_meta, user_id, hard_drop, fallback):
            self.seen_trace = trace
            self.seen_meta = session_meta
            self.seen_fallback = fallback
            assert user_id == "u1"
            assert hard_drop == set()
            pool_hits = trace["branches"]["pools"][0]["hits"]
            assert [hit[0] for hit in pool_hits] == ["t-keep", "t-missing"]
            assert [item[0] for item in trace["branches"]["fused"]] == ["t-keep", "t-missing"]
            return ["t-missing", "t-keep"]

    class FakeQU:
        def __init__(self):
            self.rr = FakeReranker()

        def _get_reranker(self):
            return self.rr

    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "sid-1",
                "turn_number": 4,
                "user_id": "u1",
                "trace": {
                    "resolver": {},
                    "retrieval": {
                        "branches": [
                            {
                                "name": "bm25",
                                "hits": [["t-keep", 9.0], ["t-drop", 8.0]],
                            }
                        ],
                        "branch_queries": {"bm25": {"kind": "bm25"}},
                    },
                    "ranking": {
                        "stages": [
                            {
                                "name": "candidate_fusion",
                                "track_ids": ["t-keep", "t-drop"],
                                "scores": [["t-keep", 1.0], ["t-drop", 0.5]],
                            }
                        ]
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text("qu_kwargs: {}\n", encoding="utf-8")
    out_path = tmp_path / "rerank.json"
    monkeypatch.setattr(debug_runtime, "_build_state_ranker_from_config", lambda config: FakeQU())

    rc = main(
        [
            "rerank-subset",
            "--config",
            str(config_path),
            "--trace",
            str(trace_path),
            "--candidate",
            "t-keep",
            "--candidate",
            "t-missing",
            "--inject-missing",
            "--inject-branch",
            "bm25",
            "--user-id",
            "u1",
            "--out",
            str(out_path),
        ]
    )

    assert rc == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ranked_track_ids"] == ["t-missing", "t-keep"]
    assert payload["injected_missing_ids"] == ["t-missing"]


def test_rerank_subset_runs_reranker_offline_by_default_and_restores(tmp_path, monkeypatch):
    class FakeCtx:
        offline = False

    class FakeReranker:
        def __init__(self):
            self.ctx = FakeCtx()

        def rerank(self, trace, session_meta, user_id, hard_drop, fallback):
            assert self.ctx.offline is True
            return list(fallback)

    class FakeQU:
        def __init__(self):
            self.rr = FakeReranker()

        def _get_reranker(self):
            return self.rr

    fake_qu = FakeQU()
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "sid-1",
                "turn_number": 4,
                "trace": {
                    "resolver": {},
                    "retrieval": {
                        "branches": [{"name": "bm25", "hits": [["t-keep", 1.0]]}],
                    },
                    "ranking": {
                        "stages": [
                            {
                                "name": "candidate_fusion",
                                "track_ids": ["t-keep"],
                                "scores": [["t-keep", 1.0]],
                            }
                        ]
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text("qu_kwargs: {}\n", encoding="utf-8")
    monkeypatch.setattr(debug_runtime, "_build_state_ranker_from_config", lambda config: fake_qu)

    rc = main(
        [
            "rerank-subset",
            "--config",
            str(config_path),
            "--trace",
            str(trace_path),
            "--candidate",
            "t-keep",
        ]
    )

    assert rc == 0
    assert fake_qu.rr.ctx.offline is False


def test_session_meta_from_wrapper_preserves_dataset_style_fields():
    conversations = [{"role": "user", "turn_number": 1, "content": "hello"}]
    user_profile = {"age": 31, "age_group": "30s"}
    conversation_goal = {"category": "discover", "specificity": "visual"}
    wrapper = {
        "session_id": "sid-1",
        "turn_number": 4,
        "conversations": conversations,
        "user_profile": user_profile,
        "conversation_goal": conversation_goal,
        "session_date": "2026-06-28",
    }

    meta = debug_rerank._session_meta_from_wrapper(wrapper, None, None)

    assert meta["conversations"] == conversations
    assert meta["user_profile"] == user_profile
    assert meta["conversation_goal"] == conversation_goal
    assert meta["session_date"] == "2026-06-28"


def test_reranker_debug_policy_uses_b1_cache_read_only_and_restores():
    from mcrs.embeddings.embedding_cache import make_key

    class FakeStore:
        def __init__(self):
            self.values = {make_key("b1-test", "cached"): [1.0, 0.0]}
            self.writes = []

        def get(self, key):
            return self.values.get(key)

        def set(self, key, vec):
            self.writes.append((key, vec))

    class FakeEnc:
        def __init__(self):
            self._store = FakeStore()
            self._namespace = "b1-test"

    class FakeCtx:
        offline = False

    class FakeB1:
        enc = FakeEnc()

    class FakeReranker:
        ctx = FakeCtx()
        b1 = FakeB1()

    reranker = FakeReranker()
    original_enc = reranker.b1.enc
    policy = debug_rerank._set_reranker_debug_policy(reranker, allow_cache_write=False)

    assert reranker.ctx.offline is True
    assert reranker.b1.enc.embed_batch(["cached"]) == [[1.0, 0.0]]
    with pytest.raises(ValueError, match="read-only debug mode"):
        reranker.b1.enc.embed_batch(["missing"])
    assert original_enc._store.writes == []

    debug_rerank._restore_reranker_debug_policy(reranker, policy)

    assert reranker.ctx.offline is False
    assert reranker.b1.enc is original_enc


def test_rerank_feature_payload_reports_encoded_and_raw_model_features(monkeypatch):
    class FakeBooster:
        def predict(self, matrix, pred_contrib=False):
            assert matrix == [[2.0, 1.5]]
            if pred_contrib:
                return [[0.2, 0.3, 0.1]]
            return [0.7]

    class FakeReranker:
        cols = ["age_group", "score_feature"]
        booster = FakeBooster()

        def _assemble(self, rows):
            assert rows[0]["age_group"] == "young"
            return [[2.0, 1.5]]

    monkeypatch.setattr(
        debug_rerank,
        "_compute_rerank_feature_rows",
        lambda reranker, feature_trace, session_meta, user_id, hard_drop: [
            {"track_id": "t-1", "age_group": "young", "score_feature": 1.5}
        ],
    )

    payload = debug_rerank._compute_rerank_feature_payload(
        FakeReranker(),
        {},
        None,
        None,
        set(),
        include_contrib=True,
    )

    candidate = payload["candidates"][0]
    assert candidate["raw_model_features"]["age_group"] == "young"
    assert candidate["model_features"] == {"age_group": 2.0, "score_feature": 1.5}
    assert candidate["contrib"] == {"age_group": 0.2, "score_feature": 0.3, "bias": 0.1}


def test_load_trace_document_selects_jsonl_row_by_session_and_turn(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "sid-1",
                "turn_number": 1,
                "trace": {"final_recommendation": {"track_ids": ["t-one"]}},
            }
        )
        + "\n"
        + json.dumps(
            {
                "session_id": "sid-2",
                "turn_number": 4,
                "trace": {"final_recommendation": {"track_ids": ["t-two"]}},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    wrapper, trace = debug_rerank._load_trace_document(
        trace_path,
        session_id="sid-2",
        turn_number=4,
    )

    assert wrapper["session_id"] == "sid-2"
    assert trace["final_recommendation"]["track_ids"] == ["t-two"]


def test_rerank_features_command_reports_scores_features_and_diff(tmp_path, monkeypatch):
    class FakeQU:
        def _get_reranker(self):
            return object()

    def fake_compute(reranker, feature_trace, session_meta, user_id, hard_drop, include_contrib):
        assert session_meta == {"session_id": "sid-1", "turn_number": 4}
        assert user_id == "u1"
        assert hard_drop == set()
        assert include_contrib is True
        assert [hit[0] for hit in feature_trace["branches"]["pools"][0]["hits"]] == [
            "t-target",
            "t-winner",
            "t-other",
        ]
        return {
            "columns": ["b1_cos", "rank__bm25", "same_artist_session"],
            "candidates": [
                {
                    "track_id": "t-target",
                    "rerank_score": 0.25,
                    "features": {
                        "track_id": "t-target",
                        "b1_cos": 0.85,
                        "rank__bm25": 2.0,
                        "same_artist_session": 0.0,
                    },
                    "model_features": {
                        "b1_cos": 0.85,
                        "rank__bm25": 2.0,
                        "same_artist_session": 0.0,
                    },
                    "contrib": {"b1_cos": 0.12, "rank__bm25": -0.05, "bias": 0.01},
                },
                {
                    "track_id": "t-winner",
                    "rerank_score": 0.75,
                    "features": {
                        "track_id": "t-winner",
                        "b1_cos": 0.2,
                        "rank__bm25": 1.5,
                        "same_artist_session": 0.0,
                    },
                    "model_features": {
                        "b1_cos": 0.2,
                        "rank__bm25": 1.5,
                        "same_artist_session": 0.0,
                    },
                    "contrib": {"b1_cos": -0.03, "rank__bm25": 0.2, "bias": 0.01},
                },
            ],
        }

    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "sid-1",
                "turn_number": 4,
                "user_id": "u1",
                "trace": {
                    "resolver": {},
                    "retrieval": {
                        "branches": [
                            {
                                "name": "bm25",
                                "hits": [["t-target", 9.0], ["t-winner", 8.0], ["t-other", 7.0]],
                            }
                        ],
                        "branch_queries": {"bm25": {"kind": "bm25"}},
                    },
                    "ranking": {
                        "stages": [
                            {
                                "name": "candidate_fusion",
                                "track_ids": ["t-target", "t-winner", "t-other"],
                                "scores": [["t-target", 1.0], ["t-winner", 0.5], ["t-other", 0.25]],
                            }
                        ]
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text("qu_kwargs: {}\n", encoding="utf-8")
    out_path = tmp_path / "features.json"
    monkeypatch.setattr(debug_runtime, "_build_state_ranker_from_config", lambda config: FakeQU())
    monkeypatch.setattr(debug_rerank, "_compute_rerank_feature_payload", fake_compute, raising=False)

    rc = main(
        [
            "rerank-features",
            "--config",
            str(config_path),
            "--trace",
            str(trace_path),
            "--candidate",
            "t-other",
            "--diff",
            "t-target",
            "t-winner",
            "--contrib",
            "--out",
            str(out_path),
        ]
    )

    assert rc == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ranked_track_ids"] == ["t-winner", "t-target"]
    assert payload["candidates_by_id"]["t-target"]["rerank_rank"] == 2
    assert payload["candidates_by_id"]["t-target"]["model_features"]["b1_cos"] == 0.85
    assert payload["candidates_by_id"]["t-target"]["contrib"]["b1_cos"] == 0.12
    assert payload["diff"]["left_track_id"] == "t-target"
    assert payload["diff"]["right_track_id"] == "t-winner"
    assert payload["diff"]["features"][0] == {
        "feature": "b1_cos",
        "left": 0.85,
        "right": 0.2,
        "delta": 0.6499999999999999,
        "abs_delta": 0.6499999999999999,
    }


def test_diff_trace_command_reports_state_branch_and_target_rank_changes(tmp_path, capsys):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(
        json.dumps(
            {
                "compiled_state": {"retrieval_profile": "continuation"},
                "retrieval": {"branches": [{"name": "bm25", "hits": [["t-other", 2.0], ["t-target", 1.0]]}]},
                "ranking": {"stages": [{"name": "candidate_fusion", "track_ids": ["t-other", "t-target"]}]},
                "final_recommendation": {"track_ids": ["t-other", "t-target"]},
            }
        ),
        encoding="utf-8",
    )
    after.write_text(
        json.dumps(
            {
                "compiled_state": {"retrieval_profile": "exact_probe"},
                "retrieval": {
                    "branches": [
                        {"name": "bm25", "hits": [["t-target", 3.0], ["t-other", 1.0]]},
                        {"name": "exact_entity", "hits": [["t-target", 10.0]]},
                    ]
                },
                "ranking": {"stages": [{"name": "candidate_fusion", "track_ids": ["t-target", "t-other"]}]},
                "final_recommendation": {"track_ids": ["t-target", "t-other"]},
            }
        ),
        encoding="utf-8",
    )

    rc = main(["--format", "json", "diff-trace", str(before), str(after), "--target-track-id", "t-target"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["compiled_state_changes"][0]["path"] == "retrieval_profile"
    assert payload["branch_changes"]["added"] == ["exact_entity"]
    assert payload["target_rank_changes"]["final"]["before"] == 2
    assert payload["target_rank_changes"]["final"]["after"] == 1


def test_bundle_case_command_writes_replay_files(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "sid-1",
                "turn_number": 4,
                "user_id": "u1",
                "trace": {
                    "extracted_state": {"turn_intent": "play Target Song"},
                    "compiled_state": {"retrieval_profile": "exact_probe"},
                    "resolver": {"played_track_ids": ["t-old"]},
                    "ranking": {
                        "stages": [
                            {
                                "name": "candidate_fusion",
                                "track_ids": ["t-candidate", "t-target"],
                                "scores": [["t-candidate", 1.0], ["t-target", 0.5]],
                            }
                        ]
                    },
                    "final_recommendation": {"track_ids": ["t-candidate", "t-target"]},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "session_id": "sid-1",
                        "turn_number": 4,
                        "latest_user_text": "Play Target Song.",
                        "items": [
                            {
                                "rank": 1,
                                "track": {
                                    "track_id": "t-candidate",
                                    "track_name": "Candidate",
                                    "artist_name": "Artist A",
                                },
                            },
                            {
                                "rank": 2,
                                "track": {
                                    "track_id": "t-target",
                                    "track_name": "Target Song",
                                    "artist_name": "Target Artist",
                                },
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    run_file = tmp_path / "runs.json"
    run_file.write_text(
        json.dumps({"blind": {"trace": str(trace_path), "audit": str(audit_path)}}),
        encoding="utf-8",
    )
    out_dir = tmp_path / "case"

    rc = main(
        [
            "--run-file",
            str(run_file),
            "--run",
            "blind",
            "bundle-case",
            "sid",
            "4",
            "--out",
            str(out_dir),
            "--config",
            "configs/example.yaml",
            "--target-track-id",
            "t-target",
        ]
    )

    assert rc == 0
    assert json.loads((out_dir / "state.json").read_text(encoding="utf-8")) == {
        "turn_intent": "play Target Song"
    }
    assert json.loads((out_dir / "compiled.json").read_text(encoding="utf-8")) == {
        "retrieval_profile": "exact_probe"
    }
    assert (out_dir / "candidates.txt").read_text(encoding="utf-8").splitlines() == [
        "t-candidate",
        "t-target",
    ]
    conversation = json.loads((out_dir / "conversation.json").read_text(encoding="utf-8"))
    assert conversation["latest_user_text"] == "Play Target Song."
    assert conversation["played_track_ids"] == ["t-old"]
    commands = (out_dir / "commands.sh").read_text(encoding="utf-8")
    assert "retrieve-state" in commands
    assert "target-audit" in commands
    assert "rerank-features" in commands
    assert "rerank-subset --config configs/example.yaml --trace replay_trace.json --candidates candidates.txt --session-id sid-1 --turn 4 --user-id u1" in commands
    assert "rerank-features --config configs/example.yaml --trace replay_trace.json --candidates candidates.txt --session-id sid-1 --turn 4 --user-id u1" in commands
    assert "--target-track-id t-target" in commands


def test_bundle_case_without_target_omits_target_audit_command(tmp_path):
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "session_id": "sid-1",
                "turn_number": 4,
                "user_id": "u1",
                "trace": {
                    "extracted_state": {"turn_intent": "find something"},
                    "compiled_state": {},
                    "ranking": {
                        "stages": [
                            {
                                "name": "candidate_fusion",
                                "track_ids": ["t-candidate"],
                                "scores": [["t-candidate", 1.0]],
                            }
                        ]
                    },
                    "final_recommendation": {"track_ids": ["t-candidate"]},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_file = tmp_path / "runs.json"
    run_file.write_text(json.dumps({"blind": {"trace": str(trace_path)}}), encoding="utf-8")
    out_dir = tmp_path / "case"

    rc = main(
        [
            "--run-file",
            str(run_file),
            "--run",
            "blind",
            "bundle-case",
            "sid",
            "4",
            "--out",
            str(out_dir),
            "--config",
            "configs/example.yaml",
        ]
    )

    assert rc == 0
    commands = (out_dir / "commands.sh").read_text(encoding="utf-8")
    assert "target-audit" not in commands
    assert "--target-track-id" not in commands
    assert "rerank-features" in commands


def test_target_audit_command_reports_catalog_retrieval_and_final_ranks(tmp_path, monkeypatch, capsys):
    class FakeCatalog:
        def feature_rows(self):
            return {
                "t-target": {
                    "track_name": "Target Song",
                    "artist_name": ["Target Artist"],
                    "album_name": "Target Album",
                    "tag_list": ["rock"],
                }
            }

    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "retrieval": {
                    "branches": [
                        {"name": "bm25", "hits": [["t-other", 2.0], ["t-target", 1.0]]}
                    ],
                    "hard_drop": ["t-dropped"],
                },
                "ranking": {
                    "stages": [
                        {
                            "name": "candidate_fusion",
                            "track_ids": ["t-other", "t-target"],
                            "scores": [["t-other", 1.0], ["t-target", 0.5]],
                        }
                    ]
                },
                "final_recommendation": {"track_ids": ["t-target", "t-other"]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(debug_runtime, "_load_catalog", lambda run, args: FakeCatalog())

    rc = main(
        [
            "--format",
            "json",
            "target-audit",
            "--trace",
            str(trace_path),
            "--target-track-id",
            "t-target",
            "--track",
            "Target Song",
            "--artist",
            "Target Artist",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["catalog"]["found"] is True
    assert payload["catalog"]["exact_match_ids"] == ["t-target"]
    assert payload["retrieval"]["branch_ranks"] == {"bm25": 2}
    assert payload["ranking"]["stage_ranks"]["candidate_fusion"] == 2
    assert payload["ranking"]["final_rank"] == 1
    assert payload["policy"]["hard_dropped"] is False
