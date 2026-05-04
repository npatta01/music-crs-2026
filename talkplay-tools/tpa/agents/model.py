"""Model abstractions and logits processing utilities for TalkPlay agents.

Provides the original local-HF `LLM` plus a LiteLLM-backed adapter that keeps
TalkPlay's existing tool-call text contract intact.
"""
import json
import os

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.utils import get_json_schema
from transformers import LogitsProcessor, LogitsProcessorList


class InsertToolTokenProcessor(LogitsProcessor):
	"""Logits processor that inserts a token sequence after a trigger id.
	This is used to inject the `<tools>` token sequence immediately after the
	Qwen end-of-thought token so the model emits tool calls.
	Args:
		trigger_id (int): Token id that starts insertion (e.g., end-of-think).
		insert_ids (list): Token ids to insert sequentially.
		prefix_len (int): Input prefix length in tokens at generation start.
	"""
	def __init__(self, trigger_id: int, insert_ids: list, prefix_len: int):
		self.trigger_id = trigger_id
		self.insert_ids = insert_ids
		self.prefix_len = prefix_len
		self.inserting = False
		self.idx = 0
	def __call__(self, input_ids, scores):
		"""Apply constrained decoding to insert tokens.
		Args:
			input_ids (torch.Tensor): Current sequence ids of shape (1, seq_len).
			scores (torch.Tensor): Logits for the next token of shape (1, vocab).
		Returns:
			torch.Tensor: Potentially modified scores to force target token ids.
		"""
		# batch size assumed 1
		seq_len = input_ids.shape[1]
		last_id = input_ids[0, -1].item()
		if self.inserting and self.insert_ids:
			target_id = self.insert_ids[self.idx]
			scores[:] = -float("inf")
			scores[0, target_id] = 0.0
			self.idx += 1
			if self.idx >= len(self.insert_ids):
				self.inserting = False
		return scores

class LLM:
    """
    A language model wrapper for music recommendation with tool calling capabilities.
    This class provides a unified interface for interacting with large language models
    to generate tool calls and responses for music recommendation tasks.
    Args:
        tools (list): List of available tools/functions that the model can call
        model_name (str, optional): HuggingFace model identifier. Defaults to "Qwen/Qwen3-4B-AWQ"
        device (str, optional): Device to run the model on. Defaults to "cuda"
        max_new_tokens (int, optional): Maximum number of new tokens to generate. Defaults to 8192
    """
    def __init__(self,
        tools: list,
        model_name="Qwen/Qwen3-4B",
        device="cuda",
        max_new_tokens=8192,
    ):
        self.tools = tools
        self.model_name = model_name
        self.device = device
        self.start_of_tools = "<tools>"
        self.end_of_tools = "</tools>"
        self.tool_functions = [get_json_schema(tool_config["function"]) for tool_config in self.tools.values()]
        self.model, self.tokenizer = self._load_model()
        if getattr(self.model, "hf_device_map", None) is None:
            self.model.to(self.device)
        self.end_of_think = self.tokenizer.convert_tokens_to_ids("</think>")  # qwen end of thought token
        self.tools_token_ids = self.tokenizer.encode(self.start_of_tools, add_special_tokens=False)
        self.qwen_sampling_params = {
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "do_sample": True,
        }

    def _load_model(self):
        """Load the model and tokenizer.
        Returns:
            tuple: `(model, tokenizer)` ready for inference.
        """
        model_kwargs = {
            "torch_dtype": torch.float16,
            "attn_implementation": "sdpa",
        }
        if self.device == "cpu":
            model_kwargs.pop("attn_implementation", None)
        else:
            model_kwargs["device_map"] = "auto"
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            **model_kwargs,
        )
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model.eval()
        return model, tokenizer

    def tool_calling_chat_completion(self, prompt, chat_history, message, incontext_examples=None, max_new_tokens=8192):
        """Generate tool-call content given a prompt and chat history.
        Args:
            prompt (str): System prompt to steer tool-calling behavior.
            chat_history (list[dict]): Prior conversation messages.
            message (str): Current user message.
            incontext_examples (str | None): Optional in-context examples.
            max_new_tokens (int): Maximum tokens to generate.
        Returns:
            tuple[str, int, str, str]: Model input text, token length, model
            thinking content, and raw tool-call markup.
        """
        messages = [{"role": "system", "content": prompt}]
        messages.extend(chat_history)
        if incontext_examples is None:
            messages.append({"role": "user", "content": message})
        else:
            messages.append({"role": "user", "content": message + "\n" + incontext_examples})
        model_input_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            tools=self.tool_functions,
            add_generation_prompt=True,
            enable_thinking=True
        )
        model_inputs = self.tokenizer(model_input_text,
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(self.device)
        model_input_token_len = model_inputs.input_ids.shape[1]
        logits_processor = LogitsProcessorList([
            InsertToolTokenProcessor(
                trigger_id=self.end_of_think,
                insert_ids=self.tools_token_ids,
                prefix_len=model_input_token_len
            )
        ])
        with torch.no_grad():
            generated_ids = self.model.generate(
                **model_inputs,
                max_new_tokens=max_new_tokens,
                logits_processor=logits_processor,
                **self.qwen_sampling_params
            )
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
        think_index = len(output_ids) - output_ids[::-1].index(self.end_of_think)
        thinking_content = self.tokenizer.decode(output_ids[:think_index], skip_special_tokens=True).strip("\n")
        tool_content = self.tokenizer.decode(output_ids[think_index:], skip_special_tokens=True).strip("\n")
        return model_input_text, model_input_token_len, thinking_content, tool_content

    def response_chat_completion(self, prompt, chat_history, message, recommend_track_metadata, max_new_tokens=8192):
        """Generate a natural-language response grounded in recommendation data.
        Args:
            prompt (str): System prompt to steer answer generation.
            chat_history (list[dict]): Prior conversation messages.
            message (str): Current user message.
            recommend_track_metadata (dict | str): Top recommendation metadata.
            max_new_tokens (int): Maximum tokens to generate.
        Returns:
            tuple[str, int, str, str]: Model input text, token length, model thinking content, and final answer text.
        """
        messages = [{"role": "system", "content": prompt}]
        messages.extend(chat_history)
        messages.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": f"{recommend_track_metadata}"}
        ])
        model_input_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True
        )
        model_inputs = self.tokenizer(model_input_text,
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(self.device)
        model_input_token_len = model_inputs.input_ids.shape[1]
        with torch.no_grad():
            generated_ids = self.model.generate(
                **model_inputs,
                max_new_tokens=max_new_tokens,
                **self.qwen_sampling_params
            )
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
        think_index = len(output_ids) - output_ids[::-1].index(self.end_of_think)
        thinking_content = self.tokenizer.decode(output_ids[:think_index], skip_special_tokens=True).strip("\n")
        answer_content = self.tokenizer.decode(output_ids[think_index:], skip_special_tokens=True).strip("\n")
        return model_input_text, model_input_token_len, thinking_content, answer_content


def _response_usage_prompt_tokens(response) -> int:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get("prompt_tokens") or 0)
    return int(getattr(usage, "prompt_tokens", 0) or 0)


def _message_content(message) -> str:
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    return content or ""


class LITELLM_LLM:
    """OpenAI-compatible direct client adapter for TalkPlay.

    This class talks directly to an OpenAI-compatible endpoint like OpenRouter
    and asks the model to emit TalkPlay's expected `<tool_call>...</tool_call>`
    text blocks directly.
    """

    def __init__(
        self,
        tools: list,
        model_name: str = "qwen/qwen3.5-9b",
        device: str = "cuda",
        max_new_tokens: int = 8192,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
    ):
        self.tools = tools
        self.model_name = model_name
        self.device = device
        self.max_new_tokens = int(max_new_tokens)
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE") or "https://openrouter.ai/api/v1"
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LITELLM_PROXY_KEY", "sk-anything")
        self.temperature = temperature
        self.tool_functions = [get_json_schema(tool_config["function"]) for tool_config in self.tools.values()]
        self._client = None

    def _messages_to_text(self, messages: list[dict]) -> str:
        return json.dumps(messages, ensure_ascii=False)

    def _tool_prompt_suffix(self) -> str:
        valid_tool_names = []
        tool_descriptions = []
        for tool_schema in self.tool_functions:
            function_schema = tool_schema.get("function", tool_schema)
            function_name = function_schema.get("name", "unknown_tool")
            description = function_schema.get("description", "")
            parameters = json.dumps(function_schema.get("parameters", {}), ensure_ascii=False)
            valid_tool_names.append(function_name)
            tool_descriptions.append(
                f"- {function_name}: {description}\n  parameters: {parameters}"
            )
        return (
            "\n\nAVAILABLE TOOLS:\n"
            + "\n".join(tool_descriptions)
            + "\n\nVALID TOOL NAMES ONLY:\n"
            + ", ".join(valid_tool_names)
            + "\n\nOUTPUT FORMAT REQUIREMENTS:\n"
            + "- Return one or more tool calls only.\n"
            + "- Each tool call must be formatted exactly as "
            + "<tool_call>{\"name\": \"tool_name\", \"arguments\": {...}}</tool_call>\n"
            + "- The tool name must exactly match one of the valid tool names above.\n"
            + "- Do not invent aliases like retrieval_tool, reranking_tool, search_tracks, or content_based_retrieval.\n"
            + "- Do not use markdown fences.\n"
            + "- Do not explain your answer outside the tool_call blocks.\n"
        )

    def _normalize_history(self, chat_history: list[dict]) -> list[dict]:
        normalized = []
        for message in chat_history:
            role = message.get("role", "assistant")
            content = message.get("content", "")
            if role == "music":
                normalized.append(
                    {
                        "role": "assistant",
                        "content": f"Previously recommended track: {content}",
                    }
                )
            elif role in {"system", "user", "assistant", "tool", "developer"}:
                normalized.append({"role": role, "content": content})
            else:
                normalized.append(
                    {
                        "role": "assistant",
                        "content": f"Previous {role} message: {content}",
                    }
                )
        return normalized

    def _completion_kwargs(self, max_new_tokens: int | None) -> dict:
        return {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": int(max_new_tokens) if max_new_tokens is not None else self.max_new_tokens,
        }

    def _client_kwargs(self) -> dict:
        kwargs = {
            "api_key": self.api_key,
            "base_url": self.api_base,
        }
        if "openrouter.ai" in self.api_base:
            kwargs["default_headers"] = {
                "HTTP-Referer": "https://github.com/npatta01/music-conversational-music-recomender-2026",
                "X-Title": "music-crs-talkplay",
            }
        return kwargs

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(**self._client_kwargs())
        return self._client

    def tool_calling_chat_completion(self, prompt, chat_history, message, incontext_examples=None, max_new_tokens=8192):
        messages = [{"role": "system", "content": prompt + self._tool_prompt_suffix()}]
        messages.extend(self._normalize_history(chat_history))
        if incontext_examples is None:
            user_content = message
        else:
            user_content = message + "\n" + incontext_examples
        messages.append({"role": "user", "content": user_content})

        response = self._get_client().chat.completions.create(
            messages=messages,
            **self._completion_kwargs(max_new_tokens),
        )
        response_message = response.choices[0].message
        return (
            self._messages_to_text(messages),
            _response_usage_prompt_tokens(response),
            "",
            _message_content(response_message).strip("\n"),
        )

    def response_chat_completion(self, prompt, chat_history, message, recommend_track_metadata, max_new_tokens=8192):
        messages = [{"role": "system", "content": prompt}]
        messages.extend(self._normalize_history(chat_history))
        messages.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": f"{recommend_track_metadata}"},
        ])
        response = self._get_client().chat.completions.create(
            messages=messages,
            **self._completion_kwargs(max_new_tokens),
        )
        response_message = response.choices[0].message
        return (
            self._messages_to_text(messages),
            _response_usage_prompt_tokens(response),
            "",
            _message_content(response_message).strip("\n"),
        )
