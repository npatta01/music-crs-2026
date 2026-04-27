import json

import pytest

from mcrs.qu_modules import load_qu_module
from mcrs.qu_modules.llm_rewrite import LLMRewriteQU, build_model_adapter


class _FakeAdapter:
    def __init__(self, outputs=None, error=None):
        self.outputs = list(outputs or [])
        self.error = error
        self.calls = []

    def generate_batch(self, messages_list, max_new_tokens):
        self.calls.append(
            {
                "messages_list": messages_list,
                "max_new_tokens": max_new_tokens,
            }
        )
        if self.error is not None:
            raise self.error
        return self.outputs


def _sample_memory():
    return [
        {"role": "user", "content": "Need mellow electronic"},
        {"role": "assistant", "content": "How about this?"},
        {"role": "music", "content": "track_name: first song, artist_name: first artist"},
        {"role": "user", "content": "More instrumental please"},
    ]


def test_existing_qu_modules_remain_unchanged():
    session_memory = _sample_memory()

    assert load_qu_module("passthrough").transform_query(session_memory) == (
        "user: Need mellow electronic\n"
        "assistant: How about this?\n"
        "assistant: track_name: first song, artist_name: first artist\n"
        "user: More instrumental please"
    )
    assert load_qu_module("last_user_turn").transform_query(session_memory) == "More instrumental please"
    assert load_qu_module("user_turns_only").transform_query(session_memory) == (
        "Need mellow electronic\nMore instrumental please"
    )
    assert load_qu_module("last_2_user_turns").transform_query(session_memory) == (
        "Need mellow electronic\nMore instrumental please"
    )
    assert load_qu_module("no_music_history").transform_query(session_memory) == (
        "user: Need mellow electronic\nassistant: How about this?\nuser: More instrumental please"
    )


def test_llm_rewrite_parses_query_and_writes_sidecars(tmp_path):
    adapter = _FakeAdapter(outputs=["analysis\nQUERY: instrumental downtempo female vocals"])
    audit_path = tmp_path / "audit.jsonl"
    stats_path = tmp_path / "stats.json"
    qu = LLMRewriteQU(
        model_name="HuggingFaceTB/SmolLM2-1.7B-Instruct",
        prompt_name="preserve_entities_v1",
        max_new_tokens=96,
        device="cpu",
        attn_implementation="eager",
        dtype=None,
        audit_path=str(audit_path),
        stats_path=str(stats_path),
        adapter=adapter,
    )

    rewritten = qu.transform_query(_sample_memory())

    assert rewritten == "instrumental downtempo female vocals"
    stats = json.loads(stats_path.read_text())
    assert stats["total_queries"] == 1
    assert stats["fallback_count"] == 0
    assert stats["parse_failure_count"] == 0
    audit_record = json.loads(audit_path.read_text().splitlines()[0])
    assert audit_record["rewritten_query"] == "instrumental downtempo female vocals"
    assert audit_record["used_fallback"] is False


def test_llm_rewrite_falls_back_when_query_is_missing(tmp_path):
    adapter = _FakeAdapter(outputs=["no query prefix here"])
    audit_path = tmp_path / "audit.jsonl"
    stats_path = tmp_path / "stats.json"
    qu = LLMRewriteQU(
        model_name="HuggingFaceTB/SmolLM2-1.7B-Instruct",
        prompt_name="preserve_entities_v1",
        max_new_tokens=96,
        device="cpu",
        attn_implementation="eager",
        dtype=None,
        audit_path=str(audit_path),
        stats_path=str(stats_path),
        adapter=adapter,
    )

    fallback = qu.transform_query(_sample_memory())

    assert fallback.startswith("user: Need mellow electronic")
    stats = json.loads(stats_path.read_text())
    assert stats["total_queries"] == 1
    assert stats["fallback_count"] == 1
    assert stats["parse_failure_count"] == 1
    audit_record = json.loads(audit_path.read_text().splitlines()[0])
    assert audit_record["used_fallback"] is True
    assert audit_record["fallback_reason"] == "missing_query_prefix"


def test_llm_rewrite_batch_preserves_order_and_falls_back_per_item(tmp_path):
    adapter = _FakeAdapter(
        outputs=[
            "QUERY: first rewrite",
            "garbled output",
            "QUERY: third rewrite",
        ]
    )
    stats_path = tmp_path / "stats.json"
    qu = LLMRewriteQU(
        model_name="HuggingFaceTB/SmolLM2-1.7B-Instruct",
        prompt_name="preserve_entities_v1",
        max_new_tokens=96,
        device="cpu",
        attn_implementation="eager",
        dtype=None,
        stats_path=str(stats_path),
        adapter=adapter,
    )
    memories = [
        _sample_memory(),
        [{"role": "user", "content": "Need upbeat synthpop"}],
        [{"role": "user", "content": "Need late-night jazz"}],
    ]

    rewritten = qu.batch_transform_queries(memories)

    assert rewritten[0] == "first rewrite"
    assert rewritten[1] == "user: Need upbeat synthpop"
    assert rewritten[2] == "third rewrite"
    stats = json.loads(stats_path.read_text())
    assert stats["total_queries"] == 3
    assert stats["fallback_count"] == 1


def test_gemma4_adapter_uses_processor_and_disables_thinking(monkeypatch):
    calls = {}

    class FakeInputs(dict):
        def to(self, device):
            calls["device"] = device
            return self

    class FakeProcessor:
        def __init__(self):
            self.last_text = None

        def apply_chat_template(self, messages, tokenize, add_generation_prompt, enable_thinking):
            calls["apply_chat_template"] = {
                "messages": messages,
                "tokenize": tokenize,
                "add_generation_prompt": add_generation_prompt,
                "enable_thinking": enable_thinking,
            }
            return "PROMPT"

        def __call__(self, text, return_tensors):
            self.last_text = text
            return FakeInputs(
                {
                    "input_ids": pytest.importorskip("torch").tensor([[1, 2, 3]]),
                    "attention_mask": pytest.importorskip("torch").tensor([[1, 1, 1]]),
                }
            )

        def decode(self, tokens, skip_special_tokens):
            calls["decode"] = {"skip_special_tokens": skip_special_tokens}
            return "QUERY: gemma rewrite"

    class FakeModel:
        device = "cpu"

        def generate(self, **kwargs):
            calls["generate"] = kwargs
            torch = pytest.importorskip("torch")
            return torch.tensor([[1, 2, 3, 4, 5]])

    monkeypatch.setattr(
        "mcrs.qu_modules.llm_rewrite.AutoProcessor.from_pretrained",
        lambda model_name: FakeProcessor(),
    )
    monkeypatch.setattr(
        "mcrs.qu_modules.llm_rewrite.AutoModelForCausalLM.from_pretrained",
        lambda model_name, attn_implementation=None, torch_dtype=None: FakeModel(),
    )

    adapter = build_model_adapter(
        model_name="google/gemma-4-E2B-it",
        device="cpu",
        attn_implementation="eager",
        dtype=None,
    )
    output = adapter.generate_batch(
        [[{"role": "system", "content": "Rewrite"}, {"role": "user", "content": "hello"}]],
        max_new_tokens=32,
    )

    assert output == ["QUERY: gemma rewrite"]
    assert calls["apply_chat_template"]["enable_thinking"] is False
