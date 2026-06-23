import os
import time
import torch
from typing import Optional, Any, List, Dict
from mcrs.db_item import MusicCatalogDB
from mcrs.db_user import UserProfileDB
from mcrs.lm_modules import load_lm_module
from mcrs.response_context import format_state_block, is_metadata_echo, xml_track_item
from mcrs.qu_modules import load_qu_module

class CRS_BASELINE:
    """
    Conversational Recommender System (CRS) baseline that wires together an
    LLM module and a full-pipeline QU over a music catalog and user profiles.
    Attributes:
        cache_dir: Local path for caching artifacts and indices.
        lm_type: Identifier/name for the LLM backend to load.
        retrieval_type: Retained for config compatibility; CRS no longer
            loads a legacy standalone retrieval backend.
        item_db_name: Hugging Face dataset or DB name for item metadata.
        user_db_name: Hugging Face dataset or DB name for user metadata.
        split_types: Dataset split names to load (e.g., ["test_warm", "test_cold"]).
        corpus_types: Item fields used for retrieval (e.g., title, artist, album).
        device: Compute device for the LLM (e.g., "cuda", "cpu").
        dtype: Torch dtype used by the LLM.
        lm: Loaded LLM module used for response generation.
        item_db: Item metadata database accessor.
        user_db: User profile database accessor.
        prompts_dir: Directory containing prompt templates.
        role_prompt: Loaded prompt templates keyed by role.
        session_memory: In-memory list of message dicts for the current session.
    """
    @staticmethod
    def _qu_owns_retrieval(qu) -> bool:
        return hasattr(qu, "compile_track_ids") or hasattr(qu, "batch_compile_track_ids")

    def flush_caches(self) -> None:
        """Persist live-filled caches owned by the active query understanding stack."""
        flush = getattr(getattr(self, "qu", None), "flush_caches", None)
        if callable(flush):
            flush()

    def __init__(self,
        lm_type="meta-llama/Llama-3.2-1B-Instruct",
        retrieval_type="unused",
        qu_type="passthrough",
        item_db_name: str = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata",
        user_db_name: str = "talkpl-ai/TalkPlayData-Challenge-User-Metadata",
        track_split_types: list[str] = ["all_tracks"], # for test
        user_split_types: list[str] = ["all_users"],
        corpus_types: list[str] = ["track_name", "artist_name", "album_name"],
        cache_dir="./cache",
        device="cuda",
        attn_implementation="eager",
        dtype=torch.bfloat16,
        retrieval_topk: int = 20,
        retrieval_config: dict | None = None,
        qu_kwargs: Optional[dict[str, Any]] = None,
        lm_kwargs: Optional[dict[str, Any]] = None,
        response_kwargs: Optional[dict[str, Any]] = None,
    ):
        """Initialize the CRS baseline components.

        Args:
            lm_type: LLM model identifier to load for response generation.
            retrieval_type: Retained for config compatibility; ignored by the
                active full-pipeline QU path.
            item_db_name: Dataset/DB name for item metadata.
            user_db_name: Dataset/DB name for user metadata.
            split_types: Dataset split names to load.
            corpus_types: Item metadata fields used for retrieval.
            cache_dir: Local directory for caching artifacts/indices.
            device: Compute device for the LLM (e.g., "cuda", "cpu").
            dtype: Torch dtype for the LLM weights/tensors.
        """
        self.cache_dir = cache_dir
        self.lm_type = lm_type
        self.retrieval_type = retrieval_type
        self.qu_type = qu_type
        self.item_db_name = item_db_name
        self.user_db_name = user_db_name
        self.track_split_types = track_split_types
        self.user_split_types = user_split_types
        self.corpus_types = corpus_types
        self.device = device
        self.dtype = dtype
        self.attn_implementation = attn_implementation
        self.retrieval_topk = retrieval_topk
        self.retrieval_config = retrieval_config or {}
        # Response-generation options (default = legacy transcript behaviour).
        # Blind-A enables the validated best setup: state-conditioned input +
        # XML track item + echo-retry. See docs/research/2026-06-10-response-generation-bakeoff.md.
        _rk = response_kwargs or {}
        self.response_conditioning = _rk.get("conditioning", "transcript")  # "transcript" | "state"
        self.response_item_format = _rk.get("item_format", "plain")          # "plain" | "xml"
        self.response_max_tags = int(_rk.get("max_tags", 10))
        self.response_echo_retries = int(_rk.get("echo_retries", 0))
        self.qu_kwargs = qu_kwargs or {}
        self.lm_kwargs = lm_kwargs or {}
        self.lm = load_lm_module(
            self.lm_type,
            self.device,
            self.attn_implementation,
            self.dtype,
            lm_kwargs=self.lm_kwargs,
        )
        self.qu = load_qu_module(
            self.qu_type,
            cache_dir=self.cache_dir,
            device=self.device,
            attn_implementation=self.attn_implementation,
            dtype=self.dtype,
            **self.qu_kwargs,
        )
        if not self._qu_owns_retrieval(self.qu):
            raise ValueError(
                "CRS_BASELINE no longer loads legacy retrieval modules; "
                f"qu_type={self.qu_type!r} must provide compile_track_ids "
                "or batch_compile_track_ids."
            )
        self.retrieval = None
        self.item_db = MusicCatalogDB(self.item_db_name, self.track_split_types, self.corpus_types)
        self.user_db = UserProfileDB(self.user_db_name, self.user_split_types)
        self.prompts_dir = os.path.join(os.path.dirname(__file__), "system_prompts")
        self.role_prompt = {
            "role_play": open(f"{self.prompts_dir}/roleplay.txt", "r", encoding="utf-8").read(),
            "personalization": open(f"{self.prompts_dir}/personalization.txt", "r", encoding="utf-8").read(),
            "response_generation": open(f"{self.prompts_dir}/response_generation.txt", "r", encoding="utf-8").read(),
        }
        self.session_memory = []
        self.last_batch_timings: dict[str, float] = {}

    def _reset_session_memory(self):
        """Clear all messages stored in the current session memory.
        """
        self.session_memory = []

    def _upload_session_memory(self, chat_history: List[Dict[str, Any]]):
        """Upload the session memory to the database.
        """
        self.session_memory = chat_history

    def _get_system_prompt(self, user_id: Optional[str] = None) -> str:
        """Build the system prompt, optionally personalized with a user profile.
        Args:
            user_id: Optional user identifier. When provided, includes a personalization segment derived from the user's profile.
        Returns:
            The final system prompt string used for the LLM.
        """
        system_prompt = self.role_prompt["role_play"] + self.role_prompt["response_generation"]
        if user_id:
            user_profile_str = self.user_db.id_to_profile_str(user_id)
            system_prompt += self.role_prompt["personalization"] + '\n' + user_profile_str
        return system_prompt

    def chat(self, user_query: str, user_id: Optional[str] = None) -> dict[str, Any]:
        """Run a single CRS turn: retrieve items and generate a response.
        Args:
            user_query: The user's latest message or request.
            user_id: Optional user identifier for personalization.
        Returns:
            A dictionary with keys:
                - user_id: The user identifier (may be None).
                - user_query: Echo of the input query.
                - retrieval_items: List of retrieved item IDs (top candidates).
                - recommend_item: Metadata for the top recommended item.
                - response: The generated assistant response string.
        """
        self.session_memory.append({"role": "user", "content": user_query})
        # stage0. system prompt
        system_prompt = self._get_system_prompt(user_id)
        # stage1. retrieval
        # QUs that implement `compile_track_ids` (e.g. V0PlusCompilerQU) own
        # the full extract → resolve → compile → top-K pipeline and bypass
        # `self.retrieval` entirely.
        if hasattr(self.qu, "compile_track_ids"):
            import inspect
            sig = inspect.signature(self.qu.compile_track_ids)
            if "user_id" in sig.parameters:
                retrieval_items = self.qu.compile_track_ids(
                    self.session_memory, topk=self.retrieval_topk, user_id=user_id,
                )
            else:
                retrieval_items = self.qu.compile_track_ids(
                    self.session_memory, topk=self.retrieval_topk
                )
        else:
            raise RuntimeError("QU must provide compile_track_ids for CRS inference")
        traces = list(getattr(self.qu, "last_traces", []) or [])
        trace = traces[0] if traces else None
        final = trace.get("final_recommendation") if isinstance(trace, dict) else None
        if isinstance(final, dict) and final.get("track_ids"):
            retrieval_items = list(final["track_ids"][: self.retrieval_topk])
        # When retrieval comes back empty (e.g. v0+ extractor failed and the
        # compiler had no anchors), pass `recommend_item=None` to the LM
        # instead of crashing on `retrieval_items[0]`. Eval treats the empty
        # list as zero hits, which is the correct signal — popularity backfill
        # here would silently inflate metrics.
        recommend_item = self.item_db.id_to_metadata(retrieval_items[0]) if retrieval_items else None
        # stage2. response generation
        response = self.lm.response_generation(system_prompt, self.session_memory, recommend_item)
        return {
            "user_id": user_id,
            "user_query": user_query,
            "retrieval_items": retrieval_items,
            "recommend_item": recommend_item,
            "response": response,
        }

    def batch_chat(self, batch_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run multiple CRS turns in batch: retrieve items and generate responses.
        Args:
            batch_data: List of dictionaries, each containing:
                - user_query: The user's latest message or request.
                - user_id: Optional user identifier for personalization.
                - session_memory: List of chat history messages.
        Returns:
            A list of dictionaries, each with keys:
                - user_id: The user identifier (may be None).
                - user_query: Echo of the input query.
                - retrieval_items: List of retrieved item IDs (top candidates).
                - recommend_item: Metadata for the top recommended item.
                - response: The generated assistant response string.
        """
        timings: dict[str, float] = {}

        def add_elapsed(key: str, start: float) -> None:
            timings[key] = timings.get(key, 0.0) + (time.perf_counter() - start)

        # Prepare batch inputs
        start = time.perf_counter()
        sys_prompts = []
        session_memories = []
        user_ids: list[Any] = []
        session_meta: list[Any] = []

        for data in batch_data:
            user_query = data['user_query']
            user_id = data.get('user_id')
            session_memory = data['session_memory'].copy()
            session_memory.append({"role": "user", "content": user_query})

            sys_prompts.append(self._get_system_prompt(user_id))
            session_memories.append(session_memory)
            user_ids.append(user_id)
            # Raw dataset-row context (conversations with raw track ids,
            # profile, goal) for QUs whose online reranker needs the
            # session-history feature block. Optional; None is fine.
            session_meta.append(data.get('session_meta'))
        add_elapsed("prepare_inputs", start)

        # QUs that own the full pipeline (V0PlusCompilerQU) provide
        # `batch_compile_track_ids` and bypass `self.retrieval`. Forward
        # user_ids when the QU accepts the kwarg so user-source centroid
        # branches can look up the user's vector. Keep back-compat for
        # QUs that don't (signature inspection avoids a hard requirement).
        batch_traces: list[Any] = []
        start = time.perf_counter()
        if hasattr(self.qu, "batch_compile_track_ids"):
            import inspect
            sig = inspect.signature(self.qu.batch_compile_track_ids)
            kwargs: dict[str, Any] = {}
            if "user_ids" in sig.parameters:
                kwargs["user_ids"] = user_ids
            if "session_meta" in sig.parameters and any(m is not None for m in session_meta):
                kwargs["session_meta"] = session_meta
            batch_retrieval_items = self.qu.batch_compile_track_ids(
                session_memories, topk=self.retrieval_topk, **kwargs,
            )
            # V0PlusCompilerQU stashes per-session traces here as a side effect.
            batch_traces = list(getattr(self.qu, "last_traces", []) or [])
        elif hasattr(self.qu, "compile_track_ids"):
            import inspect
            sig = inspect.signature(self.qu.compile_track_ids)
            if "user_id" in sig.parameters:
                batch_retrieval_items = [
                    self.qu.compile_track_ids(sm, topk=self.retrieval_topk, user_id=uid)
                    for sm, uid in zip(session_memories, user_ids)
                ]
            else:
                batch_retrieval_items = [
                    self.qu.compile_track_ids(sm, topk=self.retrieval_topk)
                    for sm in session_memories
                ]
        else:
            raise RuntimeError("QU must provide batch_compile_track_ids or compile_track_ids")
        add_elapsed("retrieval", start)
        qu_timings = getattr(self.qu, "last_batch_timings", None)
        if isinstance(qu_timings, dict):
            for key, value in qu_timings.items():
                if isinstance(value, (int, float)):
                    timings[f"qu.{key}"] = timings.get(f"qu.{key}", 0.0) + float(value)

        # Pad traces to match batch length so non-v0+ QUs (which don't produce
        # traces) get `None` rather than IndexError.
        if len(batch_traces) < len(batch_data):
            batch_traces = batch_traces + [None] * (len(batch_data) - len(batch_traces))

        for i, trace in enumerate(batch_traces[: len(batch_retrieval_items)]):
            final = trace.get("final_recommendation") if isinstance(trace, dict) else None
            if isinstance(final, dict) and final.get("track_ids"):
                batch_retrieval_items[i] = list(final["track_ids"][: self.retrieval_topk])

        # Recommend-item formatting: plain metadata string (default) or a
        # delimited XML block with capped tags (echo-resistant; response_kwargs).
        start = time.perf_counter()
        def _safe_label(track_id):
            try:
                return self.item_db.id_to_metadata(track_id)
            except Exception:
                return track_id

        def _recommend_item(items):
            # See `chat` above — empty retrieval -> recommend_item=None, not a crash.
            if not items:
                return None
            track_id = items[0]
            if self.response_item_format == "xml":
                meta = getattr(self.item_db, "metadata_dict", {}).get(track_id)
                return xml_track_item(meta, track_id=track_id, max_tags=self.response_max_tags)
            return self.item_db.id_to_metadata(track_id)

        recommend_items = [_recommend_item(items) for items in batch_retrieval_items]
        add_elapsed("recommend_items", start)

        # Response context: raw transcript (default) or the compact structured
        # state block (state-conditioned — uses the per-session extracted state
        # the v0+ QU stashed in `last_traces`/`batch_traces`).
        start = time.perf_counter()
        if self.response_conditioning == "state":
            response_contexts = []
            for i in range(len(session_memories)):
                trace = batch_traces[i] if i < len(batch_traces) else None
                state = None
                if isinstance(trace, dict):
                    state = trace.get("extracted_state") or trace.get("state")
                block = format_state_block(state, _safe_label)
                response_contexts.append([{"role": "user", "content": block}])
        else:
            response_contexts = session_memories
        add_elapsed("response_context", start)

        # Stage 2: Batch response generation
        start = time.perf_counter()
        if hasattr(self.lm, 'batch_response_generation'):
            responses = self.lm.batch_response_generation(sys_prompts, response_contexts, recommend_items)
        else:
            # Fallback to sequential generation if batch method not available
            responses = [self.lm.response_generation(sys_prompts[i], response_contexts[i], recommend_items[i])
                        for i in range(len(batch_data))]
        add_elapsed("response_generation", start)

        # Regenerate any reply that echoed the track metadata or came back empty.
        start = time.perf_counter()
        if self.response_echo_retries > 0:
            for i, resp in enumerate(responses):
                attempts = 0
                while is_metadata_echo(resp) and attempts < self.response_echo_retries:
                    resp = self.lm.response_generation(
                        sys_prompts[i], response_contexts[i], recommend_items[i]
                    )
                    attempts += 1
                responses[i] = resp
        add_elapsed("echo_retry", start)

        # Prepare results
        start = time.perf_counter()
        results = []
        for i, data in enumerate(batch_data):
            results.append({
                "user_id": data.get('user_id'),
                "user_query": data['user_query'],
                "retrieval_items": batch_retrieval_items[i],
                "recommend_item": recommend_items[i],
                "response": responses[i],
                "trace": batch_traces[i],
            })
        add_elapsed("assemble_results", start)
        self.last_batch_timings = timings

        return results
