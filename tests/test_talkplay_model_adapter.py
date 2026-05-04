import sys
import importlib.util
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = REPO_ROOT / "talkplay-tools" / "tpa" / "agents" / "model.py"
SPEC = importlib.util.spec_from_file_location("talkplay_model_module", MODEL_PATH)
MODEL_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODEL_MODULE)
LITELLM_LLM = MODEL_MODULE.LITELLM_LLM


def test_litellm_tool_calling_normalizes_history_and_avoids_native_tools(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='<tool_call>{"name":"bm25","arguments":{"query":"calm piano","corpus_type":"lyrics","topk":20}}</tool_call>'
                    )
                )
            ],
            usage={"prompt_tokens": 123},
        )

    class _FakeCompletions:
        def create(self, **kwargs):
            return fake_completion(**kwargs)

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = _FakeChat()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_FakeOpenAI))

    def fake_bm25(query: str, corpus_type: str, topk: int):
        """BM25 retrieval.

        Args:
            query: Search query string.
            corpus_type: Corpus field to search.
            topk: Number of ids to return.
        """
        return [query, corpus_type, topk]

    tools = {
        "bm25": {
            "function": fake_bm25,
        }
    }

    llm = LITELLM_LLM(
        tools=tools,
        model_name="openrouter/qwen/qwen3.5-9b",
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-test",
    )

    _, prompt_tokens, _, tool_content = llm.tool_calling_chat_completion(
        prompt="Base prompt",
        chat_history=[
            {"role": "user", "content": "find mellow music"},
            {"role": "music", "content": "track_id:123"},
        ],
        message="more piano",
        max_new_tokens=64,
    )

    assert prompt_tokens == 123
    assert "<tool_call>" in tool_content
    assert "tools" not in captured
    assert captured["client_kwargs"]["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["client_kwargs"]["api_key"] == "sk-test"
    assert "unknown_tool" not in captured["messages"][0]["content"]
    assert "fake_bm25" in captured["messages"][0]["content"]
    assert captured["messages"][1] == {"role": "user", "content": "find mellow music"}
    assert captured["messages"][2] == {
        "role": "assistant",
        "content": "Previously recommended track: track_id:123",
    }
