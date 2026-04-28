import json
import os
import time
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoProcessor, AutoTokenizer

from .base import PassthroughQU


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "system_prompts" / "query_rewrite"


class TextCausalAdapter:
    def __init__(self, model_name: str, device: str, attn_implementation: str, dtype):
        self.model_name = model_name
        self.device = device
        self.dtype = dtype
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            attn_implementation=attn_implementation,
            torch_dtype=dtype,
        )
        if hasattr(self.model, "eval"):
            self.model.eval()
        if hasattr(self.model, "to"):
            self.model.to(self.device)
            if dtype is not None:
                self.model.to(dtype=dtype)

    def generate_batch(self, messages_list: list[list[dict[str, str]]], max_new_tokens: int) -> list[str]:
        formatted = [
            self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            for messages in messages_list
        ]
        token_inputs = self.tokenizer(
            formatted,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        input_ids = token_inputs.input_ids.to(self.device)
        attention_mask = token_inputs.attention_mask.to(self.device)
        with torch.inference_mode():
            outputs = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        generated = outputs[:, input_ids.shape[1] :]
        return self.tokenizer.batch_decode(generated, skip_special_tokens=True)


class Gemma4TextAdapter:
    def __init__(self, model_name: str, device: str, attn_implementation: str, dtype):
        self.model_name = model_name
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            attn_implementation=attn_implementation,
            torch_dtype=dtype,
        )
        if hasattr(self.model, "eval"):
            self.model.eval()
        if hasattr(self.model, "to"):
            self.model.to(device)
            if dtype is not None:
                self.model.to(dtype=dtype)

    def generate_batch(self, messages_list: list[list[dict[str, str]]], max_new_tokens: int) -> list[str]:
        formatted = [
            self.processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            for messages in messages_list
        ]
        try:
            inputs = self.processor(text=formatted, return_tensors="pt", padding=True)
        except TypeError:
            inputs = self.processor(text=formatted, return_tensors="pt")
        inputs = inputs.to(self.model.device)
        input_len = inputs["input_ids"].shape[-1]
        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        generated = outputs[:, input_len:]
        if hasattr(self.processor, "batch_decode"):
            return self.processor.batch_decode(generated, skip_special_tokens=True)
        return [self.processor.decode(tokens, skip_special_tokens=True) for tokens in generated]


class LiteLLMTextAdapter:
    def __init__(
        self,
        model_name: str,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        **_unused,
    ):
        self.model_name = model_name
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE", "http://localhost:4000")
        self.api_key = api_key or os.environ.get("LITELLM_PROXY_KEY", "sk-anything")
        self.temperature = temperature

    def generate_batch(self, messages_list: list[list[dict[str, str]]], max_new_tokens: int) -> list[str]:
        import litellm

        responses = litellm.batch_completion(
            model=self.model_name,
            messages=messages_list,
            api_base=self.api_base,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=int(max_new_tokens),
        )
        outputs: list[str] = []
        for response in responses:
            try:
                outputs.append(response.choices[0].message.content or "")
            except Exception:
                outputs.append("")
        return outputs


def build_model_adapter(
    model_name: str,
    device: str,
    attn_implementation: str,
    dtype,
    backend: str = "local",
    api_base: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.0,
):
    if backend == "litellm":
        return LiteLLMTextAdapter(
            model_name,
            api_base=api_base,
            api_key=api_key,
            temperature=temperature,
        )
    if model_name.startswith("google/gemma-4-"):
        return Gemma4TextAdapter(model_name, device, attn_implementation, dtype)
    return TextCausalAdapter(model_name, device, attn_implementation, dtype)


class LLMRewriteQU:
    def __init__(
        self,
        model_name: str,
        prompt_name: str,
        max_new_tokens: int = 96,
        device: str = "cpu",
        attn_implementation: str = "eager",
        dtype=None,
        audit_path: str | None = None,
        stats_path: str | None = None,
        adapter=None,
    ):
        self.model_name = model_name
        self.prompt_name = prompt_name
        self.max_new_tokens = max_new_tokens
        self.audit_path = audit_path
        self.stats_path = stats_path
        self.prompt_text = self._load_prompt(prompt_name)
        self.passthrough = PassthroughQU()
        self.adapter = adapter or build_model_adapter(model_name, device, attn_implementation, dtype)
        self.stats = {
            "model_name": model_name,
            "prompt_name": prompt_name,
            "total_queries": 0,
            "rewrite_success_count": 0,
            "fallback_count": 0,
            "parse_failure_count": 0,
            "generation_failure_count": 0,
            "total_rewrite_latency_ms": 0.0,
            "mean_rewrite_latency_ms": 0.0,
        }

    def _load_prompt(self, prompt_name: str) -> str:
        prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Unknown rewrite prompt: {prompt_name}")
        return prompt_path.read_text(encoding="utf-8")

    def _build_messages(self, raw_query: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.prompt_text},
            {"role": "user", "content": f"Conversation:\n{raw_query}"},
        ]

    def _extract_query(self, generated_text: str) -> tuple[str | None, str | None]:
        for line in generated_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("QUERY:"):
                query = stripped.partition("QUERY:")[2].strip()
                if query:
                    return query, None
                return None, "empty_query"
        return None, "missing_query_prefix"

    def _write_audit_records(self, records: list[dict[str, Any]]) -> None:
        if not self.audit_path:
            return
        os.makedirs(os.path.dirname(self.audit_path), exist_ok=True)
        with open(self.audit_path, "a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _write_stats(self) -> None:
        if not self.stats_path:
            return
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        total = self.stats["total_queries"]
        self.stats["mean_rewrite_latency_ms"] = (
            self.stats["total_rewrite_latency_ms"] / total if total else 0.0
        )
        with open(self.stats_path, "w", encoding="utf-8") as handle:
            json.dump(self.stats, handle, ensure_ascii=False, indent=2)

    def transform_query(self, session_memory: list) -> str:
        return self.batch_transform_queries([session_memory])[0]

    def batch_transform_queries(self, session_memories: list[list]) -> list[str]:
        raw_queries = [self.passthrough.transform_query(memory) for memory in session_memories]
        if not raw_queries:
            return []

        messages_list = [self._build_messages(raw_query) for raw_query in raw_queries]
        start = time.perf_counter()
        try:
            generated_outputs = self.adapter.generate_batch(messages_list, self.max_new_tokens)
        except Exception:
            batch_latency_ms = (time.perf_counter() - start) * 1000.0
            per_query_latency_ms = batch_latency_ms / len(raw_queries)
            self.stats["total_queries"] += len(raw_queries)
            self.stats["fallback_count"] += len(raw_queries)
            self.stats["generation_failure_count"] += len(raw_queries)
            self.stats["total_rewrite_latency_ms"] += batch_latency_ms
            records = [
                {
                    "model_name": self.model_name,
                    "prompt_name": self.prompt_name,
                    "raw_query": raw_query,
                    "rewritten_query": raw_query,
                    "generated_text": None,
                    "used_fallback": True,
                    "fallback_reason": "generation_error",
                    "latency_ms": per_query_latency_ms,
                }
                for raw_query in raw_queries
            ]
            self._write_audit_records(records)
            self._write_stats()
            return raw_queries

        batch_latency_ms = (time.perf_counter() - start) * 1000.0
        per_query_latency_ms = batch_latency_ms / len(raw_queries)
        rewritten_queries = []
        audit_records = []

        self.stats["total_queries"] += len(raw_queries)
        self.stats["total_rewrite_latency_ms"] += batch_latency_ms

        for raw_query, generated_text in zip(raw_queries, generated_outputs):
            parsed_query, parse_error = self._extract_query(generated_text)
            if parsed_query is None:
                rewritten_queries.append(raw_query)
                self.stats["fallback_count"] += 1
                self.stats["parse_failure_count"] += 1
                audit_records.append(
                    {
                        "model_name": self.model_name,
                        "prompt_name": self.prompt_name,
                        "raw_query": raw_query,
                        "rewritten_query": raw_query,
                        "generated_text": generated_text,
                        "used_fallback": True,
                        "fallback_reason": parse_error,
                        "latency_ms": per_query_latency_ms,
                    }
                )
                continue

            rewritten_queries.append(parsed_query)
            self.stats["rewrite_success_count"] += 1
            audit_records.append(
                {
                    "model_name": self.model_name,
                    "prompt_name": self.prompt_name,
                    "raw_query": raw_query,
                    "rewritten_query": parsed_query,
                    "generated_text": generated_text,
                    "used_fallback": False,
                    "fallback_reason": None,
                    "latency_ms": per_query_latency_ms,
                }
            )

        self._write_audit_records(audit_records)
        self._write_stats()
        return rewritten_queries
