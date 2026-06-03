"""Modal GPU cross-encoder reranker — vLLM backend for fast offline reranking.

Uses vLLM with `task="score"` for Qwen3-Reranker. Wins over HF transformers:
- automatic prefix caching (huge for our case: 200 candidates per turn share
  the full system+instruction+query prefix; only the document differs)
- continuous batching across requests
- paged attention + flash attention kernels
- one container handles many concurrent requests via `@modal.concurrent`

(no `from __future__ import annotations` — modal.parameter type-resolution
requires real class objects, not stringified forward refs.)

Run with:
    modal run modal/rerank.py::rerank \\
        --base-tid v0plus_compiler_bm25_image_audio_cfbpr_metadata_devset \\
        --model Qwen/Qwen3-Reranker-4B \\
        --query-template structured \\
        --instruction-mode policy \\
        --num-sessions 30
"""

import modal

APP_NAME = "music-crs-rerank"
HF_CACHE_VOLUME = "music-crs-hf-cache"
HF_CACHE_DIR = "/root/.cache/huggingface"

# A10 (24GB) fits Qwen3-Reranker-4B fp16 (~8GB weights + KV cache + headroom).
# Bump to A100 if running -8B with high concurrency or larger context.
QWEN3_RERANKER_GPU = "A10"

app = modal.App(APP_NAME)
hf_cache_vol = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        # vLLM 0.10.0 had a tokenizer-attribute mismatch with transformers ≥4.51
        # (called `all_special_tokens_extended` which was removed). 0.11+ targets
        # modern transformers. Let pip pull the matched transformers automatically.
        "vllm>=0.11.1",
        "huggingface-hub>=0.26",
    )
    .env({
        "HF_HOME": HF_CACHE_DIR,
        "VLLM_LOGGING_LEVEL": "WARNING",
    })
)


# ---------------------------------------------------------------------------
# Qwen3-Reranker template (from the model card / vLLM docs).
# Prefix + suffix are FIXED by the model's training; only the instruction
# field is user-controllable. vLLM detects the shared prefix across calls
# automatically and reuses the KV cache (this is the main throughput win).
# ---------------------------------------------------------------------------

QWEN3_PREFIX = (
    "<|im_start|>system\n"
    "Judge whether the Document meets the requirements based on the Query and "
    'the Instruct provided. Note that the answer can only be "yes" or "no".'
    "<|im_end|>\n<|im_start|>user\n"
)
QWEN3_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


def format_query_text(instruction: str, query: str) -> str:
    """text_1 side: prefix + instruction + query (shared across all candidates for a turn)."""
    return f"{QWEN3_PREFIX}<Instruct>: {instruction}\n<Query>: {query}\n"


def format_doc_text(doc: str) -> str:
    """text_2 side: just the document body + suffix (differs per candidate)."""
    return f"<Document>: {doc}{QWEN3_SUFFIX}"


# ---------------------------------------------------------------------------
# vLLM-backed reranker service
# ---------------------------------------------------------------------------


@app.cls(
    image=image,
    gpu=QWEN3_RERANKER_GPU,
    volumes={HF_CACHE_DIR: hf_cache_vol},
    cpu=4,
    memory=32768,
    # Per-input timeout: 600s. With local rate-limiting in the entrypoint,
    # Modal's timeout clock only starts when a call actually dispatches
    # (no queueing on Modal's side). 600s = 10 min ceiling, plenty for
    # a single .score(200 pairs) call (~5-30s expected).
    timeout=600,
    min_containers=0,
    # 8 containers × max_inputs=1 = 8 in-flight at peak — concurrency
    # moved from "within container" to "across containers" because vLLM
    # 0.11's runner=pooling crashed with ZMQ router-socket assertion
    # under concurrent in-container requests (`Assertion failed:
    # !_current_out (src/router.cpp:166)`).
    max_containers=8,
    scaledown_window=300,
)
# Down from 4 → 1: vLLM 0.11 + pooling task crashed under concurrent
# in-flight requests per container. Single-input-per-container is stable.
# We lose vLLM's continuous batching across calls but keep prefix caching
# within a single .score(200 pairs) call (the bigger win anyway).
@modal.concurrent(max_inputs=1)
class Qwen3RerankerService:
    """vLLM-backed Qwen3-Reranker. Set `model_name` at construction time."""

    model_name: str = modal.parameter(default="Qwen/Qwen3-Reranker-4B")

    @modal.enter()
    def setup(self):
        import os
        from vllm import LLM

        os.environ.setdefault("HF_HOME", HF_CACHE_DIR)

        print(f"loading {self.model_name} via vLLM (task=score)...")
        self.llm = LLM(
            model=self.model_name,
            # vLLM ≥0.11: `task=` is replaced by `runner="pooling"` for
            # scoring / cross-encoder models. The hf_overrides route the
            # checkpoint to Qwen3ForSequenceClassification + yes/no logit head.
            runner="pooling",
            dtype="float16",
            gpu_memory_utilization=0.85,
            # Trimmed from 4096 → 1024. Actual avg tokens per pair is ~500
            # (prefix ~320 + doc ~100 + suffix ~30). 1024 leaves headroom for
            # the long tail without pre-allocating wasted KV slots. Smaller
            # max_model_len = more concurrent inputs fit safely on A10's 24GB.
            max_model_len=1024,
            enable_prefix_caching=True,
            hf_overrides={
                "architectures": ["Qwen3ForSequenceClassification"],
                "classifier_from_token": ["no", "yes"],
                "is_original_qwen3_reranker": True,
            },
            disable_log_stats=True,
        )
        # Tiny warm-up: score one pair so the first user call is hot.
        _ = self.llm.score(
            [format_query_text("Score how well a music track matches a request.", "test")],
            [format_doc_text("Test Artist - Test Song | 2020 | rock")],
        )
        print("ready")

    @modal.method()
    def score(
        self,
        pairs: list[tuple[str, str]],
        instruction: str,
    ) -> list[float]:
        """Score (query, doc) pairs with `instruction`.

        For a single turn with 200 candidates, all queries are IDENTICAL
        (same prefix + instruction + turn query) — vLLM's prefix cache will
        compute the prefix attention ONCE and reuse it across the 200 calls.
        """
        if not pairs:
            return []
        queries = [format_query_text(instruction, q) for q, _ in pairs]
        docs = [format_doc_text(d) for _, d in pairs]
        outputs = self.llm.score(queries, docs)
        return [float(o.outputs.score) for o in outputs]


# ---------------------------------------------------------------------------
# Prompt templates (unchanged from prior version)
# ---------------------------------------------------------------------------

GENERIC_INSTRUCTION = (
    "Score how well a candidate music track matches the user's next desired "
    "recommendation in this multi-turn music conversation. Consider stylistic "
    "match (genre, era, mood), similarity to recently played tracks, and the "
    "user's stated preferences."
)


POLICY_INSTRUCTIONS: dict = {
    "exploit": (
        "Score how well a candidate music track matches the user's request. "
        "The user wants MORE FROM THE SAME ARTIST OR ALBUM as their recent plays "
        "— prefer tracks by the same artist."
    ),
    "diversify_artists": (
        "Score how well a candidate music track matches the user's request. "
        "The user wants the SAME STYLE BUT A DIFFERENT ARTIST than the ones "
        "already played in this session — prefer cross-artist style matches."
    ),
    "diversify_albums": (
        "Score how well a candidate music track matches the user's request. "
        "The user wants tracks by a different album than the ones already played "
        "— the same artist is acceptable, but different albums are preferred."
    ),
    "balanced": GENERIC_INSTRUCTION,
}


def build_query_basic(state: dict) -> str:
    return (state.get("turn_intent") or "").strip()


def build_query_structured(
    state: dict,
    history_with_metadata: list,
) -> str:
    parts: list = []
    intent = (state.get("turn_intent") or "").strip()
    if intent:
        parts.append(f"Request: {intent}")

    if history_with_metadata:
        parts.append(f'Just heard: {history_with_metadata[-1]}')
        recent = history_with_metadata[-3:]
        if len(recent) > 1:
            parts.append(f'Recent: {"; ".join(recent)}')

    me = state.get("mentioned_entities") or []
    likes = [m.get("value") for m in me if (m.get("sentiment") or 0) > 0 and m.get("value")]
    likes = list(dict.fromkeys(likes))[:6]
    if likes:
        parts.append(f"User likes: {', '.join(likes)}")

    pc = state.get("process_constraints") or {}
    policy = pc.get("exploration_policy") or "balanced"
    if policy == "diversify_artists":
        parts.append("Policy: prefer a different artist from the ones already played.")
    elif policy == "exploit":
        parts.append("Policy: prefer more from the same artist as the recent plays.")
    elif policy == "diversify_albums":
        parts.append("Policy: prefer a different album from the ones already played.")
    return "\n".join(parts)


def select_instruction(mode: str, state: dict) -> str:
    if mode == "policy":
        pc = state.get("process_constraints") or {}
        policy = pc.get("exploration_policy") or "balanced"
        return POLICY_INSTRUCTIONS.get(policy, GENERIC_INSTRUCTION)
    return GENERIC_INSTRUCTION


# ---------------------------------------------------------------------------
# Minimal smoke entrypoint
# ---------------------------------------------------------------------------


@app.local_entrypoint()
def smoke(model: str = "Qwen/Qwen3-Reranker-4B"):
    """One-call sanity check. Pass when model loads + 3 pairs return sensible scores."""
    print(f"smoke: instantiating Qwen3RerankerService({model})...")
    service = Qwen3RerankerService(model_name=model)
    instruction = (
        "Score how well a candidate music track matches the user's music recommendation request."
    )
    pairs = [
        ("popular alternative rock from the 2010s",
         "Arctic Monkeys - Do I Wanna Know | AM (2013) | indie rock, alternative"),
        ("popular alternative rock from the 2010s",
         "Mozart - Eine kleine Nachtmusik | 1787 | classical, orchestral"),
        ("popular alternative rock from the 2010s",
         "The Strokes - Last Nite | Is This It (2001) | indie rock, garage rock"),
    ]
    import time
    t0 = time.time()
    scores = service.score.remote(pairs, instruction)
    print(f"smoke: scores={scores}  (elapsed {time.time()-t0:.2f}s)")
    print("smoke: expected best→worst: Arctic Monkeys > The Strokes > Mozart")
    assert len(scores) == len(pairs)
    print("smoke: OK")


# ---------------------------------------------------------------------------
# Local entrypoint — reads predictions+traces, builds pairs, calls service,
# writes reranked output. Predictions stay local; only pairs ship over network.
# ---------------------------------------------------------------------------


@app.local_entrypoint()
def rerank(
    base_tid: str,
    model: str = "Qwen/Qwen3-Reranker-4B",
    query_template: str = "structured",
    instruction_mode: str = "generic",
    rerank_top_k: int = 200,
    fusion_xenc_weight: float = 0.5,
    fusion_rrf_weight: float = 1.0,
    fusion_k: int = 60,
    num_sessions: int = 30,
    exp_dir: str = "evaluator/exp",
):
    """Run a Modal-backed Qwen3-Reranker rerank against saved predictions."""
    import json
    import re
    import sys
    import time
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    base_dir = Path(exp_dir) / "inference" / "devset"
    pred_path = base_dir / f"{base_tid}.json"
    trace_path = base_dir / f"{base_tid}_trace.jsonl"
    if not pred_path.exists():
        raise SystemExit(f"predictions not found: {pred_path}")
    if not trace_path.exists():
        raise SystemExit(f"trace not found: {trace_path}")

    print(f"loading predictions: {pred_path}")
    preds = json.loads(pred_path.read_text())
    print(f"loading traces:      {trace_path}")
    trace_rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]

    states: dict = {}
    played_by_turn: dict = {}
    for r in trace_rows:
        sid = r.get("session_id")
        tn = r.get("turn_number")
        tr = r.get("trace") or {}
        st = (tr.get("state") or {})
        res = (tr.get("resolver") or {})
        if sid is not None and tn is not None:
            states[(sid, int(tn))] = st
            played = res.get("played_track_ids") or []
            played_by_turn[(sid, int(tn))] = [str(p) for p in played]
    print(f"  {len(preds)} predictions, {len(states)} trace states")

    from scripts.rerank_offline import build_track_text_dict
    track_text = build_track_text_dict(max_tags=15)

    print("building history-metadata dict (year + top 3 tags)...")
    from datasets import load_dataset
    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Track-Metadata", split="all_tracks")
    history_meta = {}
    for row in ds:
        tid = str(row["track_id"])
        a = row.get("artist_name") or []
        t = row.get("track_name") or []
        artist = (a[0] if isinstance(a, list) and a else str(a or "")).strip()
        track = (t[0] if isinstance(t, list) and t else str(t or "")).strip()
        rd = row.get("release_date")
        year = str(rd)[:4] if rd and str(rd)[:4].isdigit() else ""
        tags = row.get("tag_list") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        tags = [str(x).strip() for x in tags if x][:3]
        meta_str = f'"{artist} - {track}"'
        bits = []
        if year:
            bits.append(year)
        if tags:
            bits.extend(tags)
        if bits:
            meta_str += f" ({', '.join(bits)})"
        history_meta[tid] = meta_str

    rows_to_rerank = preds[: num_sessions * 8] if num_sessions > 0 else preds

    work = []
    for row in rows_to_rerank:
        sid = row.get("session_id")
        tn = row.get("turn_number")
        pred_ids = row.get("predicted_track_ids") or []
        st = states.get((sid, int(tn))) if tn is not None else {}
        if st is None:
            st = {}
        played = played_by_turn.get((sid, int(tn)), []) if tn is not None else []
        history_with_meta = [history_meta.get(p, p) for p in played]

        if query_template == "basic":
            query = build_query_basic(st)
        else:
            query = build_query_structured(st, history_with_meta)

        instruction = select_instruction(instruction_mode, st)
        work.append((query, instruction, pred_ids[:rerank_top_k]))

    print(f"reranking {len(work)} turns | template={query_template} | instruction={instruction_mode}")

    service = Qwen3RerankerService(model_name=model)

    out_rows = []
    n_no_query = 0
    n_empty = 0
    n_timeout = 0
    n_error = 0
    t0 = time.time()

    # Local rate-limit: ThreadPool with max_workers = peak concurrency.
    # Each worker calls service.score.remote() which blocks until result.
    # Crucially: Modal's per-input timeout clock only STARTS when .remote()
    # actually dispatches (i.e., when a container slot is free). With this
    # pattern there's no upfront-spawn queue race against the timeout —
    # the per-input wall is bounded by container availability, not by total
    # queue depth.
    from concurrent.futures import ThreadPoolExecutor

    MAX_IN_FLIGHT = 8  # = max_containers (8) × @modal.concurrent.max_inputs (1)
    sample_logged = [False]

    def score_one(turn_idx):
        nonlocal n_no_query, n_empty, n_timeout, n_error
        query, instruction, head_ids = work[turn_idx]
        if not query:
            return turn_idx, ("skip", "no_query")
        if not head_ids:
            return turn_idx, ("skip", "empty_pool")
        if not sample_logged[0]:
            print(f"\nSAMPLE turn-idx {turn_idx}:\n  instruction: {instruction[:200]}\n  query: {query[:400]}\n")
            sample_logged[0] = True
        pairs = [(query, track_text.get(tid, "")) for tid in head_ids]
        try:
            scores = service.score.remote(pairs, instruction)
            return turn_idx, ("ok", scores)
        except modal.exception.FunctionTimeoutError:
            return turn_idx, ("timeout", None)
        except Exception as e:
            return turn_idx, ("error", f"{type(e).__name__}: {e}")

    scores_by_turn = {}
    n_done = 0
    with ThreadPoolExecutor(max_workers=MAX_IN_FLIGHT) as pool:
        for turn_idx, (status, payload) in pool.map(score_one, range(len(work))):
            n_done += 1
            if status == "ok":
                scores_by_turn[turn_idx] = payload
            elif status == "timeout":
                n_timeout += 1
                print(f"  turn {turn_idx} timed out — passthrough to RRF order")
            elif status == "error":
                n_error += 1
                print(f"  turn {turn_idx} failed: {payload}")
            elif status == "skip":
                if payload == "no_query":
                    n_no_query += 1
                elif payload == "empty_pool":
                    n_empty += 1
            if n_done % 20 == 0:
                print(f"  {n_done}/{len(work)} turns done ({n_done/(time.time()-t0):.2f} turns/sec)")

    print(f"all turns scored in {time.time()-t0:.1f}s")

    n_length_mismatch = 0
    for turn_idx, (_, _, head_ids) in enumerate(work):
        row = rows_to_rerank[turn_idx]
        pred_ids = row.get("predicted_track_ids") or []
        if turn_idx not in scores_by_turn:
            out_rows.append(row)
            continue
        scores = scores_by_turn[turn_idx]
        head = head_ids
        # Defensive: vLLM occasionally returns fewer scores than pairs sent
        # (e.g. mid-cancellation when the container scales down). Skip
        # reranking these turns rather than crashing — they fall back to
        # the RRF passthrough order, same as a timeout.
        if not isinstance(scores, list) or len(scores) != len(head):
            n_length_mismatch += 1
            out_rows.append(row)
            continue
        tail = pred_ids[rerank_top_k:]
        xenc_rank_by_tid = {
            tid: r
            for r, (tid, _) in enumerate(sorted(zip(head, scores), key=lambda x: -x[1]))
        }
        fused = []
        for rrf_rank, tid in enumerate(head):
            xenc_rank = xenc_rank_by_tid[tid]
            s = fusion_rrf_weight / (fusion_k + rrf_rank) + fusion_xenc_weight / (fusion_k + xenc_rank)
            fused.append((tid, s))
        fused.sort(key=lambda x: -x[1])
        new_pred_ids = [tid for tid, _ in fused] + tail
        out_rows.append({**row, "predicted_track_ids": new_pred_ids})

    if num_sessions > 0 and len(rows_to_rerank) < len(preds):
        out_rows.extend(preds[len(rows_to_rerank):])

    def slugify(name: str) -> str:
        s = name.replace("/", "_").replace(":", "_")
        return re.sub(r"[^A-Za-z0-9_.\-]", "_", s)

    out_tid = f"{base_tid}.modal-rerank_{slugify(model)}_{query_template}_{instruction_mode}"
    out_path = base_dir / f"{out_tid}.json"
    out_path.write_text(json.dumps(out_rows))
    print(f"\nwrote {out_path} ({len(out_rows)} rows)")
    print(
        f"summary: no_query={n_no_query} empty_pool={n_empty} "
        f"timed_out={n_timeout} errored={n_error} length_mismatch={n_length_mismatch}"
    )
