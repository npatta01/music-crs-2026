from types import SimpleNamespace
import copy

import pytest


def _tool_call(name: str, arguments: dict, tool_call_id: str = "call-1"):
    function = SimpleNamespace(name=name, arguments=__import__("json").dumps(arguments))
    return SimpleNamespace(id=tool_call_id, function=function)


def _response_with_tool_call(name: str, arguments: dict, tool_call_id: str = "call-1"):
    message = SimpleNamespace(tool_calls=[_tool_call(name, arguments, tool_call_id)])
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _response_with_tool_calls(tool_calls):
    message = SimpleNamespace(tool_calls=tool_calls)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _response_without_tool_call(content: str = "done"):
    message = SimpleNamespace(content=content, tool_calls=[])
    choice = SimpleNamespace(message=message, finish_reason="stop")
    return SimpleNamespace(choices=[choice])


def _executor_with_ranking(retrieval_track_ids: list[str]):
    def _execute(tool_name, arguments, track_pool):
        return {
            "ok": True,
            "tool_name": tool_name,
            "tool_args": arguments,
            "track_ids": list(retrieval_track_ids),
            "content": {"track_ids": list(retrieval_track_ids), "result_count": len(retrieval_track_ids)},
        }

    return _execute


def _tool_schemas(*names: str):
    return [{"function": {"name": name}} for name in names]


def test_agentic_session_executes_two_native_tool_calls():
    from mcrs.agentic import AgenticSession

    calls = iter(
        [
            _response_with_tool_calls(
                [
                    _tool_call("bm25_search", {"query": "calm piano", "corpus_type": "title", "topk": 3}, "call-1"),
                    _tool_call("sql_filter", {"sql_query": "SELECT track_id FROM tracks ORDER BY popularity DESC", "topk": 3}, "call-2"),
                ]
            ),
        ]
    )
    planner = SimpleNamespace(create_completion=lambda **kwargs: next(calls))

    def _execute(tool_name, arguments, track_pool):
        if tool_name == "bm25_search":
            return {
                "ok": True,
                "tool_name": tool_name,
                "tool_args": arguments,
                "track_ids": ["track-2", "track-3", "track-4"],
                "content": {"track_ids": ["track-2", "track-3", "track-4"], "result_count": 3},
            }
        if tool_name == "sql_filter":
            assert track_pool == ["track-2", "track-3", "track-4"]
            return {
                "ok": True,
                "tool_name": tool_name,
                "tool_args": arguments,
                "track_ids": ["track-3", "track-2"],
                "content": {"track_ids": ["track-3", "track-2"], "result_count": 2},
            }
        pytest.fail("unexpected tool")

    executor = SimpleNamespace(execute_tool_call=_execute, tool_schemas=_tool_schemas("bm25_search", "sql_filter"))

    session = AgenticSession(
        planner=planner,
        tool_executor=executor,
        catalog_track_ids=["track-1", "track-2", "track-3", "track-4"],
        prediction_depth=4,
        max_planning_steps=4,
        allow_prediction_backfill=True,
    )

    result = session.run_turn(
        system_prompt="You are a retrieval planner.",
        chat_history=[{"role": "user", "content": "Find mellow piano tracks"}],
        user_message="More like this please",
    )

    assert result["retrieval_items"] == ["track-3", "track-2", "track-1", "track-4"]
    assert result["response"] == ""
    assert result["tool_trace"]["tool_names"] == ["bm25_search", "sql_filter"]
    assert result["tool_trace"]["backfilled_count"] == 2
    assert result["tool_trace"]["final_tool_name"] == "sql_filter"


def test_agentic_session_repairs_missing_tool_call_once():
    from mcrs.agentic import AgenticSession

    calls = iter(
        [
            _response_without_tool_call("I think these are good."),
            _response_with_tool_calls(
                [
                    _tool_call("bm25_search", {"query": "upbeat songs", "corpus_type": "metadata", "topk": 2}, "call-1"),
                    _tool_call("bm25_search", {"query": "upbeat songs", "corpus_type": "metadata", "topk": 2}, "call-2"),
                ]
            ),
        ]
    )
    planner = SimpleNamespace(create_completion=lambda **kwargs: next(calls))
    executor = SimpleNamespace(
        execute_tool_call=_executor_with_ranking(["track-2", "track-3"]),
        tool_schemas=_tool_schemas("bm25_search"),
    )

    session = AgenticSession(
        planner=planner,
        tool_executor=executor,
        catalog_track_ids=["track-1", "track-2", "track-3"],
        prediction_depth=3,
        max_planning_steps=2,
        allow_prediction_backfill=True,
    )

    result = session.run_turn(
        system_prompt="You are a retrieval planner.",
        chat_history=[],
        user_message="Find upbeat songs",
    )

    assert result["retrieval_items"] == ["track-2", "track-3", "track-1"]
    assert result["tool_trace"]["final_tool_name"] == "bm25_search"
    assert result["tool_trace"]["tool_names"] == ["bm25_search", "bm25_search"]
    assert result["tool_trace"]["repair_retry_used"] is True


def test_agentic_missing_tool_call_repair_is_terse_and_does_not_replay_prose():
    from mcrs.agentic import AgenticSession

    captured_messages = []
    calls = iter(
        [
            _response_without_tool_call("Here are some tracks you might like."),
            _response_with_tool_calls(
                [
                    _tool_call("bm25_search", {"query": "upbeat songs", "corpus_type": "metadata", "topk": 2}, "call-1"),
                    _tool_call("bm25_search", {"query": "upbeat songs", "corpus_type": "metadata", "topk": 2}, "call-2"),
                ]
            ),
        ]
    )

    def _create_completion(**kwargs):
        captured_messages.append(copy.deepcopy(kwargs["messages"]))
        return next(calls)

    planner = SimpleNamespace(create_completion=_create_completion)
    executor = SimpleNamespace(
        execute_tool_call=_executor_with_ranking(["track-2", "track-3"]),
        tool_schemas=_tool_schemas("bm25_search"),
    )

    session = AgenticSession(
        planner=planner,
        tool_executor=executor,
        catalog_track_ids=["track-1", "track-2", "track-3"],
        prediction_depth=3,
        max_planning_steps=2,
        allow_prediction_backfill=True,
    )

    result = session.run_turn(
        system_prompt="You are a retrieval planner.",
        chat_history=[],
        user_message="Find upbeat songs",
    )

    assert result["tool_trace"]["repair_retry_used"] is True
    assert len(captured_messages) == 2
    repaired_messages = captured_messages[1]
    assert repaired_messages[-1]["role"] == "user"
    assert repaired_messages[-1]["content"] == "Return exactly two tool calls. First retrieval from the full catalog, then reranking over that candidate pool. No prose."
    assert all(message.get("content") != "Here are some tracks you might like." for message in repaired_messages)


def test_agentic_session_requires_exactly_two_tool_calls():
    from mcrs.agentic import AgenticSession

    calls = iter(
        [
            _response_with_tool_call(
                "bm25_search",
                {"query": "calm piano", "corpus_type": "title", "topk": 3},
            ),
        ]
    )
    planner = SimpleNamespace(create_completion=lambda **kwargs: next(calls))
    executor = SimpleNamespace(
        execute_tool_call=_executor_with_ranking(["track-2", "track-3", "track-1"]),
        tool_schemas=_tool_schemas("bm25_search"),
    )

    session = AgenticSession(
        planner=planner,
        tool_executor=executor,
        catalog_track_ids=["track-1", "track-2", "track-3"],
        prediction_depth=3,
        max_planning_steps=4,
        allow_prediction_backfill=True,
    )

    result = session.run_turn(
        system_prompt="You are a retrieval planner.",
        chat_history=[],
        user_message="Find upbeat songs",
    )

    assert result["tool_trace"]["fallback_used"] is True
    assert result["tool_trace"]["fallback_reason"] == "tool_call_missing"
    assert "exactly two tool calls" in result["tool_trace"]["error_message"]


def test_agentic_session_feeds_tool_error_back_into_planning_loop():
    from mcrs.agentic import AgenticSession

    calls = iter(
        [
            _response_with_tool_calls(
                [
                    _tool_call(
                        "sql_filter",
                        {"sql_query": "SELECT track_id FROM tracks WHERE 'instrumental' IN tag_list", "topk": 3},
                        "call-1",
                    ),
                    _tool_call(
                        "bm25_search",
                        {"query": "dark instrumental synthwave", "corpus_type": "attributes", "topk": 3},
                        "call-2",
                    ),
                ]
            ),
        ]
    )
    planner = SimpleNamespace(create_completion=lambda **kwargs: next(calls))

    def _execute(tool_name, arguments, track_pool):
        if tool_name == "sql_filter":
            return {
                "ok": False,
                "tool_name": tool_name,
                "tool_args": arguments,
                "track_ids": list(track_pool),
                "content": {
                    "error": "sql_filter treats tag_list as a text column.",
                    "result_count": 0,
                    "track_ids": [],
                },
                "error_message": "sql_filter treats tag_list as a text column.",
            }
        pytest.fail("unexpected tool")

    executor = SimpleNamespace(execute_tool_call=_execute, tool_schemas=_tool_schemas("sql_filter", "bm25_search"))

    session = AgenticSession(
        planner=planner,
        tool_executor=executor,
        catalog_track_ids=["track-1", "track-2", "track-3"],
        prediction_depth=3,
        max_planning_steps=2,
        allow_prediction_backfill=True,
    )

    result = session.run_turn(
        system_prompt="You are a retrieval planner.",
        chat_history=[],
        user_message="Find dark instrumental synthwave",
    )

    assert result["tool_trace"]["fallback_used"] is True
    assert result["tool_trace"]["tool_names"] == ["sql_filter"]
    assert result["tool_trace"]["steps"][0]["tool_error"] == "sql_filter treats tag_list as a text column."
    assert result["retrieval_items"] == ["track-1", "track-2", "track-3"]


def test_openai_chat_completions_planner_uses_pydantic_tools_and_proxy_aliases():
    from mcrs.agentic import OpenAIChatCompletionsPlanner

    captured = {}

    class _FakeCompletions:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[]))])

    fake_client = SimpleNamespace(beta=SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions())))
    planner = OpenAIChatCompletionsPlanner(
        model_name="openai/qwen3.5-9b",
        client=fake_client,
        temperature=0.0,
        max_tokens=256,
    )

    planner.create_completion(
        messages=[{"role": "user", "content": "Find calm piano tracks"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "bm25_search",
                    "description": "Search music tracks",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "corpus_type": {"type": "string"},
                            "topk": {"type": "integer"},
                        },
                        "required": ["query", "corpus_type", "topk"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
    )

    assert captured["model"] == "openai/qwen3.5-9b"
    assert captured["tool_choice"] == "required"
    assert captured["parallel_tool_calls"] is True
    assert captured["tools"][0]["function"]["name"] == "bm25_search"
    assert captured["tools"][0]["function"]["strict"] is True


def test_agentic_session_executes_structured_two_step_plan():
    from mcrs.agentic import AgenticSession

    planner = SimpleNamespace(
        create_structured_plan=lambda **kwargs: SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        parsed=SimpleNamespace(
                            model_dump=lambda: {
                                "step1": {
                                    "tool_name": "bm25_search",
                                    "arguments": {"query": "calm piano", "corpus_type": "title", "topk": 3},
                                },
                                "step2": {
                                    "tool_name": "sql_filter",
                                    "arguments": {"sql_query": "SELECT track_id FROM tracks ORDER BY popularity DESC", "topk": 3},
                                },
                            }
                        )
                    )
                )
            ]
        )
    )

    def _execute(tool_name, arguments, track_pool):
        if tool_name == "bm25_search":
            return {
                "ok": True,
                "tool_name": tool_name,
                "tool_args": arguments,
                "track_ids": ["track-2", "track-3", "track-4"],
                "content": {"track_ids": ["track-2", "track-3", "track-4"], "result_count": 3},
            }
        if tool_name == "sql_filter":
            assert track_pool == ["track-2", "track-3", "track-4"]
            return {
                "ok": True,
                "tool_name": tool_name,
                "tool_args": arguments,
                "track_ids": ["track-4", "track-2"],
                "content": {"track_ids": ["track-4", "track-2"], "result_count": 2},
            }
        pytest.fail("unexpected tool")

    executor = SimpleNamespace(
        execute_tool_call=_execute,
        tool_schemas=[
            {"function": {"name": "bm25_search"}},
            {"function": {"name": "sql_filter"}},
        ],
    )

    session = AgenticSession(
        planner=planner,
        tool_executor=executor,
        catalog_track_ids=["track-1", "track-2", "track-3", "track-4"],
        prediction_depth=4,
        max_planning_steps=4,
        allow_prediction_backfill=True,
        planner_protocol="structured_two_step_plan",
    )

    result = session.run_turn(
        system_prompt="You are a retrieval planner.",
        chat_history=[],
        user_message="Find upbeat songs",
    )

    assert result["retrieval_items"] == ["track-4", "track-2", "track-1", "track-3"]
    assert result["tool_trace"]["tool_names"] == ["bm25_search", "sql_filter"]
    assert result["tool_trace"]["final_tool_name"] == "sql_filter"


def test_agentic_session_executes_specialized_retrieval_plan_with_optional_bm25_boost():
    from mcrs.agentic import AgenticSession

    planner = SimpleNamespace(
        create_specialized_retrieval_plan=lambda **kwargs: SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        parsed=SimpleNamespace(
                            model_dump=lambda: {
                                "retrieval_mode": "bm25_search",
                                "retrieval_query": "calm piano",
                                "retrieval_corpus_type": "title",
                                "use_bm25_boost": True,
                                "boost_query": "solo piano",
                                "boost_corpus_type": "metadata",
                            }
                        )
                    )
                )
            ]
        )
    )

    def _execute(tool_name, arguments, track_pool):
        assert tool_name == "bm25_search"
        return {
            "ok": True,
            "tool_name": tool_name,
            "tool_args": arguments,
            "track_ids": ["track-2", "track-3", "track-4", "track-1"],
            "content": {"track_ids": ["track-2", "track-3", "track-4", "track-1"], "result_count": 4},
        }

    def _rerank_with_bm25_boost(**kwargs):
        assert kwargs["track_pool"] == ["track-2", "track-3", "track-4", "track-1"]
        assert kwargs["query"] == "solo piano"
        return {
            "ok": True,
            "track_ids": ["track-3", "track-2", "track-4", "track-1"],
            "content": {
                "track_ids": ["track-3", "track-2", "track-4", "track-1"],
                "result_count": 4,
                "boost_match_count": 2,
                "max_bm25_score": 1.0,
                "mean_bm25_score": 0.4,
            },
        }

    executor = SimpleNamespace(
        execute_tool_call=_execute,
        rerank_with_bm25_boost=_rerank_with_bm25_boost,
        tool_schemas=[{"function": {"name": "bm25_search"}}],
    )

    session = AgenticSession(
        planner=planner,
        tool_executor=executor,
        catalog_track_ids=["track-1", "track-2", "track-3", "track-4"],
        prediction_depth=4,
        max_planning_steps=4,
        allow_prediction_backfill=True,
        planner_protocol="structured_retrieval_bm25_boost",
        bm25_boost_weight=0.35,
    )

    result = session.run_turn(
        system_prompt="You are a retrieval planner.",
        chat_history=[],
        user_message="Find calm piano songs",
    )

    assert result["retrieval_items"] == ["track-3", "track-2", "track-4", "track-1"]
    assert result["tool_trace"]["tool_names"] == ["bm25_search", "bm25_boost"]
    assert result["tool_trace"]["final_tool_name"] == "bm25_boost"
    assert result["tool_trace"]["boost_used"] is True
    assert result["tool_trace"]["final_ranking_source"] == "retrieval_plus_bm25_boost"


def test_specialized_plan_backfills_from_retrieval_pool_not_global_catalog():
    from mcrs.agentic import AgenticSession

    planner = SimpleNamespace(
        create_specialized_retrieval_plan=lambda **kwargs: SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        parsed=SimpleNamespace(
                            model_dump=lambda: {
                                "retrieval_mode": "bm25_search",
                                "retrieval_query": "country",
                                "retrieval_corpus_type": "metadata",
                                "use_bm25_boost": True,
                                "boost_query": "popular country",
                                "boost_corpus_type": "metadata",
                            }
                        )
                    )
                )
            ]
        )
    )

    executor = SimpleNamespace(
        execute_tool_call=lambda *args, **kwargs: {
            "ok": True,
            "track_ids": ["retr-1", "retr-2", "retr-3", "retr-4"],
            "content": {"track_ids": ["retr-1", "retr-2", "retr-3", "retr-4"], "result_count": 4},
        },
        rerank_with_bm25_boost=lambda **kwargs: {
            "ok": True,
            "track_ids": ["retr-3", "retr-1"],
            "content": {
                "track_ids": ["retr-3", "retr-1"],
                "result_count": 2,
                "boost_match_count": 1,
                "max_bm25_score": 1.0,
                "mean_bm25_score": 0.2,
            },
        },
        tool_schemas=[{"function": {"name": "bm25_search"}}],
    )

    session = AgenticSession(
        planner=planner,
        tool_executor=executor,
        catalog_track_ids=["global-1", "global-2", "retr-1", "retr-2", "retr-3", "retr-4"],
        prediction_depth=4,
        max_planning_steps=4,
        allow_prediction_backfill=True,
        planner_protocol="structured_retrieval_bm25_boost",
        bm25_boost_weight=0.35,
    )

    result = session.run_turn(
        system_prompt="You are a retrieval planner.",
        chat_history=[],
        user_message="Find country hits",
    )

    assert result["retrieval_items"] == ["retr-3", "retr-1", "retr-2", "retr-4"]
    assert "global-1" not in result["retrieval_items"]
    assert "global-2" not in result["retrieval_items"]
    assert result["tool_trace"]["backfilled_count"] == 2


def test_sql_filter_tool_uses_track_metadata_fields(monkeypatch, tmp_path):
    from mcrs.agentic import SQLFilterTool

    fake_rows = [
        {
            "track_id": "track-1",
            "track_name": ["Heavy Metal Machine"],
            "artist_name": ["The Smashing Pumpkins"],
            "album_name": ["Machina"],
            "tag_list": ["alternative rock", "heavy"],
            "popularity": 70.0,
            "release_date": "2000-02-29",
            "duration": 240000,
        },
        {
            "track_id": "track-2",
            "track_name": ["Wound"],
            "artist_name": ["The Smashing Pumpkins"],
            "album_name": ["Machina"],
            "tag_list": ["alternative rock", "atmospheric"],
            "popularity": 60.0,
            "release_date": "2000-02-29",
            "duration": 250000,
        },
    ]

    monkeypatch.setattr("mcrs.agentic.load_dataset", lambda *args, **kwargs: {"all_tracks": fake_rows})

    tool = SQLFilterTool(
        dataset_name="ignored",
        split_types=["all_tracks"],
        cache_dir=str(tmp_path),
    )

    results = tool.search(
        sql_query=(
            "SELECT track_id FROM tracks "
            "WHERE album_name LIKE '%machina%' AND tag_list LIKE '%atmospheric%' "
            "ORDER BY popularity DESC"
        ),
        topk=5,
        track_pool=["track-1", "track-2"],
    )

    assert results == ["track-2"]


def test_sql_filter_tool_rejects_invalid_tag_list_syntax(monkeypatch, tmp_path):
    from mcrs.agentic import SQLFilterTool

    fake_rows = [
        {
            "track_id": "track-1",
            "track_name": ["War Against Machines"],
            "artist_name": ["Perturbator"],
            "album_name": ["Dangerous Days"],
            "tag_list": ["instrumental", "darkwave", "synthwave"],
            "popularity": 70.0,
            "release_date": "2014-06-17",
            "duration": 240000,
        }
    ]

    monkeypatch.setattr("mcrs.agentic.load_dataset", lambda *args, **kwargs: {"all_tracks": fake_rows})

    tool = SQLFilterTool(
        dataset_name="ignored",
        split_types=["all_tracks"],
        cache_dir=str(tmp_path),
    )

    with pytest.raises(ValueError, match="tag_list"):
        tool.search(
            sql_query=(
                "SELECT track_id FROM tracks "
                "WHERE 'instrumental' IN tag_list"
            ),
            topk=5,
            track_pool=["track-1"],
        )


def test_sql_filter_tool_rejects_non_track_id_projection(monkeypatch, tmp_path):
    from mcrs.agentic import SQLFilterTool

    fake_rows = [
        {
            "track_id": "track-1",
            "track_name": ["War Against Machines"],
            "artist_name": ["Perturbator"],
            "album_name": ["Dangerous Days"],
            "tag_list": ["instrumental", "darkwave", "synthwave"],
            "popularity": 70.0,
            "release_date": "2014-06-17",
            "duration": 240000,
        }
    ]

    monkeypatch.setattr("mcrs.agentic.load_dataset", lambda *args, **kwargs: {"all_tracks": fake_rows})

    tool = SQLFilterTool(
        dataset_name="ignored",
        split_types=["all_tracks"],
        cache_dir=str(tmp_path),
    )

    with pytest.raises(ValueError, match="track_id"):
        tool.search(
            sql_query=(
                "SELECT track_id, track_name FROM tracks "
                "WHERE LOWER(tag_list) LIKE '%instrumental%'"
            ),
            topk=5,
            track_pool=["track-1"],
        )
