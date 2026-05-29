"""Cross-encoder reranker for the top-N of a fused candidate list.

Architecture: a separate stage AFTER PostFusionReranker. Takes the top-N from
the fused list, runs a cross-encoder model on `(state.turn_intent, candidate_text)`
pairs, and re-sorts the head by the model's relevance score. Items beyond
`rerank_top_k` pass through at their RRF positions.

Multiple backends are supported via the RerankerBackend protocol:
  - SentenceTransformersBackend: works for MiniLM, BGE-base, BGE-v2-m3
  - FlagEmbeddingBackend: BGE-v2-gemma and other FlagReranker models
  - Qwen3RerankerBackend: instruction-style scoring for Qwen3-Reranker family

The backend is selected by `model_name` prefix at construction time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol


logger = logging.getLogger(__name__)


class CatalogTextProtocol(Protocol):
    """Minimal catalog interface the reranker needs."""

    def track_text(self, track_id: str) -> str: ...


class StateProtocol(Protocol):
    """Minimal state interface the reranker needs."""

    turn_intent: str


class RerankerBackend(Protocol):
    """Backend abstraction. Each backend loads its model lazily and exposes
    a uniform `score(pairs)` interface."""

    def score(self, pairs: list[tuple[str, str]]) -> list[float]: ...


# ---------------------------------------------------------------------------
# Sentence-Transformers backend (MiniLM, bge-reranker-base, bge-reranker-v2-m3)
# ---------------------------------------------------------------------------


@dataclass
class SentenceTransformersBackend:
    model_name: str
    batch_size: int = 32
    device: str | None = None
    max_length: int = 512
    _model: object = field(default=None, init=False, repr=False)

    def _load(self):
        if self._model is not None:
            return
        from sentence_transformers import CrossEncoder
        device = self.device or _auto_device()
        logger.info("Loading CrossEncoder %r on %s", self.model_name, device)
        self._model = CrossEncoder(
            self.model_name, device=device, max_length=self.max_length
        )

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        self._load()
        scores = self._model.predict(
            pairs, batch_size=self.batch_size, show_progress_bar=False
        )
        # CrossEncoder.predict returns numpy array; coerce to list[float]
        return [float(s) for s in scores]


# ---------------------------------------------------------------------------
# FlagEmbedding backend (bge-reranker-v2-gemma, layerwise rerankers)
# ---------------------------------------------------------------------------


@dataclass
class FlagEmbeddingBackend:
    model_name: str
    batch_size: int = 16
    device: str | None = None
    use_fp16: bool = True
    _model: object = field(default=None, init=False, repr=False)

    def _load(self):
        if self._model is not None:
            return
        from FlagEmbedding import FlagReranker
        device = self.device or _auto_device()
        logger.info("Loading FlagReranker %r on %s", self.model_name, device)
        self._model = FlagReranker(
            self.model_name, use_fp16=self.use_fp16, device=device
        )

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        self._load()
        # FlagReranker accepts list[list[str]] of [query, doc]
        flag_pairs = [[q, d] for q, d in pairs]
        scores = self._model.compute_score(flag_pairs, batch_size=self.batch_size)
        if isinstance(scores, float):
            return [scores]
        return [float(s) for s in scores]


# ---------------------------------------------------------------------------
# DeepInfra hosted-reranker backend (HTTP API)
# ---------------------------------------------------------------------------


@dataclass
class DeepInfraRerankerBackend:
    """Calls DeepInfra's hosted reranker endpoints (e.g. Qwen3-Reranker-4B/8B).

    No local model load — every batch is an HTTP POST to
    `https://api.deepinfra.com/v1/inference/{model_name}` with
    `{queries: [...], documents: [...]}` and gets back `{scores: [...]}`.

    Pairing is 1:1 — to score a single query against N documents, we send
    the query N times. (Confirmed via API testing; the alternative would be
    cross-product but DeepInfra uses paired form.)

    Concurrency: when `max_in_flight > 1`, batches are dispatched in parallel
    via a ThreadPoolExecutor. Default 1 (serial) for safety; set 4-8 for
    full-devset throughput.
    """

    model_name: str
    batch_size: int = 32
    api_base: str = "https://api.deepinfra.com/v1/inference"
    api_key: str | None = None  # default: env DEEPINFRA_API_KEY
    timeout_s: float = 60.0
    max_retries: int = 3
    max_in_flight: int = 1
    # `device` is unused for HTTP backend but accepted for API symmetry
    device: str | None = None

    def _auth_token(self) -> str:
        import os
        tok = self.api_key or os.environ.get("DEEPINFRA_API_KEY")
        if not tok:
            raise RuntimeError("DEEPINFRA_API_KEY not set and no api_key provided")
        return tok

    def _post_batch(self, queries: list[str], documents: list[str]) -> list[float]:
        import time
        import requests
        url = f"{self.api_base}/{self.model_name}"
        body = {"queries": queries, "documents": documents}
        headers = {
            "Authorization": f"bearer {self._auth_token()}",
            "Content-Type": "application/json",
        }
        for attempt in range(self.max_retries):
            try:
                r = requests.post(url, json=body, headers=headers, timeout=self.timeout_s)
                if r.status_code == 200:
                    data = r.json()
                    return [float(s) for s in data["scores"]]
                if r.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise RuntimeError(f"DeepInfra reranker {r.status_code}: {r.text[:200]}")
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise RuntimeError(f"DeepInfra reranker network error: {e}") from e
        raise RuntimeError("DeepInfra reranker exhausted retries")

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []

        # Slice into batches
        batches: list[tuple[list[str], list[str]]] = []
        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i : i + self.batch_size]
            batches.append(([q for q, _ in batch], [d for _, d in batch]))

        if self.max_in_flight <= 1:
            # Serial path
            out: list[float] = []
            for queries, documents in batches:
                out.extend(self._post_batch(queries, documents))
            return out

        # Concurrent path: dispatch batches via ThreadPoolExecutor while
        # preserving input order in the returned scores.
        from concurrent.futures import ThreadPoolExecutor
        results: list[list[float] | None] = [None] * len(batches)
        with ThreadPoolExecutor(max_workers=self.max_in_flight) as pool:
            futs = {
                pool.submit(self._post_batch, q, d): idx
                for idx, (q, d) in enumerate(batches)
            }
            for fut in futs:
                idx = futs[fut]
                results[idx] = fut.result()
        out = []
        for r in results:
            out.extend(r or [])
        return out


# ---------------------------------------------------------------------------
# Qwen3-Reranker backend (instruction-style autoregressive scoring)
# ---------------------------------------------------------------------------


@dataclass
class Qwen3RerankerBackend:
    """Qwen3-Reranker uses a binary yes/no token-prob scoring pattern with an
    instruction template. See https://huggingface.co/Qwen/Qwen3-Reranker-0.6B."""

    model_name: str
    batch_size: int = 16
    device: str | None = None
    instruction: str = (
        "Given a user query for a music recommendation and a candidate track, "
        "score how well the track matches the user's request."
    )
    _tokenizer: object = field(default=None, init=False, repr=False)
    _model: object = field(default=None, init=False, repr=False)
    _yes_id: int = field(default=0, init=False, repr=False)
    _no_id: int = field(default=0, init=False, repr=False)
    _prefix_ids: list[int] = field(default_factory=list, init=False, repr=False)
    _suffix_ids: list[int] = field(default_factory=list, init=False, repr=False)

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        device = self.device or _auto_device()
        logger.info("Loading Qwen3-Reranker %r on %s", self.model_name, device)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, padding_side="left")
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device).eval()
        self._yes_id = self._tokenizer.convert_tokens_to_ids("yes")
        self._no_id = self._tokenizer.convert_tokens_to_ids("no")
        prefix = "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        self._prefix_ids = self._tokenizer.encode(prefix, add_special_tokens=False)
        self._suffix_ids = self._tokenizer.encode(suffix, add_special_tokens=False)

    def _format_pair(self, query: str, doc: str) -> str:
        return f"<Instruct>: {self.instruction}\n<Query>: {query}\n<Document>: {doc}"

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        self._load()
        import torch
        device = next(self._model.parameters()).device

        all_scores: list[float] = []
        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i : i + self.batch_size]
            texts = [self._format_pair(q, d) for q, d in batch]
            enc = self._tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=8192,
                return_tensors="pt",
                add_special_tokens=False,
            )
            # Prepend prefix and append suffix ids
            input_ids_list = []
            for ids in enc.input_ids:
                merged = self._prefix_ids + ids.tolist() + self._suffix_ids
                input_ids_list.append(merged)
            # Re-pad
            max_len = max(len(x) for x in input_ids_list)
            pad_id = self._tokenizer.pad_token_id or self._tokenizer.eos_token_id
            padded = [[pad_id] * (max_len - len(x)) + x for x in input_ids_list]
            attn = [[0] * (max_len - len(x)) + [1] * len(x) for x in input_ids_list]
            input_ids = torch.tensor(padded, device=device)
            attention_mask = torch.tensor(attn, device=device)
            with torch.no_grad():
                logits = self._model(input_ids, attention_mask=attention_mask).logits[:, -1]
            yes = logits[:, self._yes_id]
            no = logits[:, self._no_id]
            # Softmax over {yes, no} → probability of yes
            stacked = torch.stack([no, yes], dim=-1)
            probs = torch.softmax(stacked, dim=-1)[:, 1]
            all_scores.extend(probs.cpu().tolist())
        return all_scores


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def _auto_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def build_backend(
    model_name: str,
    *,
    backend: str | None = None,
    batch_size: int = 32,
    device: str | None = None,
    max_in_flight: int = 1,
) -> RerankerBackend:
    """Pick the right backend based on `model_name` (or explicit `backend` arg).

    Selection rules:
      - explicit `backend` always wins
      - model_name contains "qwen" and "reranker" → Qwen3RerankerBackend
      - model_name contains "v2-gemma" or "v2-minicpm" → FlagEmbeddingBackend
      - everything else → SentenceTransformersBackend (default; works for
        MiniLM, bge-base, bge-v2-m3, mxbai-rerank)
    """
    name = model_name.lower()
    if backend == "sentence-transformers" or backend == "st":
        return SentenceTransformersBackend(model_name, batch_size=batch_size, device=device)
    if backend == "flag" or backend == "flagembedding":
        return FlagEmbeddingBackend(model_name, batch_size=batch_size, device=device)
    if backend == "qwen3":
        return Qwen3RerankerBackend(model_name, batch_size=batch_size, device=device)
    if backend == "deepinfra":
        return DeepInfraRerankerBackend(
            model_name, batch_size=batch_size, device=device, max_in_flight=max_in_flight,
        )
    # Auto-detect — DeepInfra wins when explicit (Qwen/Qwen3-Reranker-...)
    # because that's the cheapest hosted path for those models.
    if "v2-gemma" in name or "v2-minicpm" in name:
        return FlagEmbeddingBackend(model_name, batch_size=batch_size, device=device)
    if "qwen" in name and "reranker" in name:
        # Default to local Qwen3RerankerBackend; pass --backend deepinfra to use API
        return Qwen3RerankerBackend(model_name, batch_size=batch_size, device=device)
    return SentenceTransformersBackend(model_name, batch_size=batch_size, device=device)


# ---------------------------------------------------------------------------
# The reranker itself
# ---------------------------------------------------------------------------


@dataclass
class CrossEncoderReranker:
    """Replace the score of the top-N from a fused list with cross-encoder scores.

    Items beyond `rerank_top_k` pass through at their original (RRF) positions.
    `state.turn_intent` is the query; `catalog.track_text(tid)` is the doc.

    Loaded lazily — the backend's model only loads on first `rerank()` call.
    """

    model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    rerank_top_k: int = 200
    batch_size: int = 32
    device: str | None = None
    backend_name: str | None = None  # optional override for backend selection
    max_in_flight: int = 1  # HTTP-backend concurrency (DeepInfra only)
    # Score fusion: "replace" (default — xenc score replaces RRF score),
    # or "rrf" (RRF rank fusion of RRF rank and xenc rank, preserves ensemble signal).
    fusion: str = "replace"
    fusion_k: int = 60  # RRF dampening constant for fusion="rrf"
    fusion_xenc_weight: float = 1.0  # weight of the xenc-rank term in fusion="rrf"
    fusion_rrf_weight: float = 1.0   # weight of the RRF-rank term in fusion="rrf"
    # `backend` is normally auto-built from model_name in __post_init__, but
    # tests can pass a stub backend directly. None at construction time means
    # "build it for me".
    backend: RerankerBackend | None = None

    def __post_init__(self):
        if self.backend is None:
            self.backend = build_backend(
                self.model_name,
                backend=self.backend_name,
                batch_size=self.batch_size,
                device=self.device,
                max_in_flight=self.max_in_flight,
            )

    def rerank(
        self,
        fused: list[tuple[str, float]],
        state: StateProtocol,
        catalog: CatalogTextProtocol,
    ) -> list[tuple[str, float]]:
        if not fused:
            return fused
        query = (state.turn_intent or "").strip()
        if not query:
            return fused
        head = fused[: self.rerank_top_k]
        tail = fused[self.rerank_top_k :]
        pairs = [(query, catalog.track_text(tid)) for tid, _ in head]
        scores = self.backend.score(pairs)
        head_tids = [tid for tid, _ in head]

        if self.fusion == "rrf":
            # RRF-rank fusion: combine RRF rank (position in `head`) with xenc rank
            # (rank by score within `head`). Preserves the multi-branch ensemble
            # signal that pure-replace destroys.
            xenc_rank_by_tid = {
                tid: r for r, (tid, _) in enumerate(
                    sorted(zip(head_tids, scores), key=lambda x: -x[1])
                )
            }
            k = self.fusion_k
            wr = self.fusion_rrf_weight
            wx = self.fusion_xenc_weight
            fused_scores = []
            for rrf_rank, tid in enumerate(head_tids):
                xenc_rank = xenc_rank_by_tid[tid]
                s = wr / (k + rrf_rank) + wx / (k + xenc_rank)
                fused_scores.append((tid, s))
            reranked_head = sorted(fused_scores, key=lambda x: -x[1])
        else:
            # fusion == "replace" — xenc score replaces RRF score
            reranked_head = sorted(
                zip(head_tids, [float(s) for s in scores]),
                key=lambda x: -x[1],
            )
        return reranked_head + tail
