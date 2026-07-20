# Conversation Semantic Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate whether actual conversation/state/prior-track inputs can generate useful semantic candidates for the Music-CRS devset.

**Architecture:** Build a reusable example builder that turns session context, v10 traces, ground truth, and catalog vectors into supervised examples. Run two offline experiments: a conversation-to-item retriever that ranks the full catalog by projected query/item similarity, and a constrained semantic-ID decoder that predicts valid level-1/level-2 code tokens and expands them to catalog tracks.

**Tech Stack:** Python, NumPy, PyTorch, LanceDB catalog vectors, existing v10 trace/ground-truth artifacts, pytest.

---

### Task 1: Conversation Input Builder

**Files:**
- Create: `mcrs/analysis/conversation_semantic.py`
- Create: `tests/test_conversation_semantic.py`

- [ ] Write tests for compact state text, prior-track formatting, and deterministic text hashing.
- [ ] Implement helpers:
  - `state_to_text(trace_state: dict) -> str`
  - `conversation_input_text(session: dict, trace: dict, turn_number: int, view: str, track_lookup: dict[str, str]) -> str`
  - `hashed_text_vector(text: str, dim: int) -> np.ndarray`
- [ ] Verify with `pytest tests/test_conversation_semantic.py -q`.

### Task 2: Conversation-To-Item Retriever

**Files:**
- Create: `scripts/semantic_ids/train_conversation_retriever.py`
- Modify: `mcrs/analysis/conversation_semantic.py`
- Test: `tests/test_conversation_semantic.py`

- [ ] Add tested helpers for building multimodal query vectors from hashed text plus prior-track CF centroid.
- [ ] Load dev sessions through `scripts/rerank/build_features.load_sessions(split="test")`.
- [ ] Load GT and v10 trace rows.
- [ ] Load catalog `cf_bpr` vectors and optional learned hard-neg item projection.
- [ ] Train a small PyTorch query projector with sampled in-batch/catalog negatives.
- [ ] Evaluate recall@20/50/100/500 for all turns, playable turns, and non-playable turns.

### Task 3: Constrained Semantic-ID Decoder

**Files:**
- Create: `scripts/semantic_ids/train_semantic_id_decoder.py`
- Modify: `mcrs/analysis/conversation_semantic.py`
- Test: `tests/test_conversation_semantic.py`

- [ ] Reuse the examples from Task 2.
- [ ] Load a semantic-ID parquet and build valid `l1 -> l2 -> track_ids` maps.
- [ ] Train one classifier for `sid_l1` and one conditional classifier for `sid_l2`.
- [ ] Decode top valid `(l1, l2)` pairs only, expand them to tracks, and rank tracks by item/query score inside predicted leaves.
- [ ] Evaluate recall@20/50/100/500 on all/playable/non-playable turns.

### Task 4: Report And Verify

**Files:**
- Modify: `exp/analysis/semantic_ids/README.md`

- [ ] Add a section comparing input views: `last_turn`, `state`, `last_turn_state`, `last_turn_state_prior`, `full_conversation_state_prior`.
- [ ] Add the best option-2 and option-3 recall results.
- [ ] Run `py_compile` for new scripts and modules.
- [ ] Run focused tests plus existing semantic/ranker smoke tests.
