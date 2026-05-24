# Source Digest For Rebuilding Music-CRS

Audience: someone who does not already know CRS and suspects the current code is tangled.

Purpose: capture the useful ideas from the Gen-CRS 2025 tutorial PDF and the most relevant papers, then translate them into a practical rebuild plan for this competition.

## Bottom Line

Do not try to make a bad CRS codebase good by adding more prompt text.

The recurring pattern across the tutorial and papers is:

```text
conversation
  -> explicit state
  -> retrieval views
  -> grounded candidate generation
  -> fusion / reranking
  -> grounded response
  -> traces and stage-level evaluation
```

For Music-CRS, the best first rebuild is not a pure LLM recommender and not an agent loop. It is a modular, catalog-grounded system where each module has a narrow contract and leaves a trace.

## What The Competition Needs

The Music-CRS challenge is a multi-turn music recommendation task. The system must:

1. Read a conversation.
2. Recommend 20 track IDs from the provided catalog.
3. Generate a natural-language response.

The challenge page says the task uses TalkPlayData-Challenge, grounded in real music listening histories, and provides multimodal track/user embeddings plus metadata resources.

Practical implication:

- ranking quality matters directly
- valid catalog IDs matter directly
- response text should be grounded in selected tracks
- the code should make it obvious whether a failure came from state extraction, retrieval, ranking, or response generation

## Source Inventory

| Source | Link | Why it matters |
|---|---|---|
| Gen-CRS 2025 tutorial PDF | <https://recsys-lab.at/wp-content/uploads/2025/10/Gen-CRS2025_Tutorial.pdf> | Gives architecture vocabulary: unified, modular, agentic; state, RAG, simulation, evaluation, open challenges. |
| Music-CRS challenge | <https://nlp4musa.github.io/music-crs-challenge/> | Defines the actual task and available resources: conversations, track/user metadata, embeddings, baseline/evaluator code. |
| RA-Rec / semi-structured state tracking | <https://arxiv.org/abs/2406.00033> | Best direct design pattern for `ConversationState -> query -> retrieval -> grounded explanation`. |
| ReFICR / LLM retrieval instructions | <https://doi.org/10.1145/3640457.3688146> | Shows how to decompose CRS into retrieval and generation subtasks; useful as a future training direction. |
| Reindex-Then-Adapt | <https://arxiv.org/abs/2405.12119> | Strong warning that LLM item knowledge is distribution-misaligned; catalog control and RecSys gating matter. |
| MemoCRS | <https://arxiv.org/abs/2407.04960> | Useful memory design: compact entity/attitude/timestamp memory, retrieve relevant memory, avoid full-history noise. |
| RecLLM roadmap | <https://arxiv.org/abs/2305.07961> | Production-scale CRS component map: dialogue manager, retrieval, ranking/explanation, user profiles, simulator. |
| iEvaLM evaluation | <https://aclanthology.org/2023.emnlp-main.621/> | Static ground-truth evaluation is incomplete; stage-level and interactive-style evaluation reveal different failures. |
| EventChat | <https://arxiv.org/abs/2407.04472> | Practical warning: prompt-only LLM ranking can be costly, slow, and brittle; stage-based systems can be better than agents. |

## What To Steal From The Tutorial PDF

### 1. Architecture Taxonomy

The tutorial separates Gen-CRS systems into three broad families:

- Unified Gen-CRS: one LLM handles intent detection, retrieval, ranking, and response generation.
- Modular Gen-CRS: separate modules manage dialogue/state, retrieval/ranking, and generation.
- Agentic Gen-CRS: a central LLM plans and coordinates tools, agents, retrieval engines, memory, and APIs.

For Music-CRS:

- Unified is too risky as the main path because the system must output valid catalog IDs.
- Agentic is too heavy as the first path because it adds latency, nondeterminism, and many failure points.
- Modular is the useful default because it gives clean contracts and measurable stages.

### 2. Grounding Is Not Optional

The tutorial explicitly frames Gen-CRS as LLM-powered recommendation with grounding to reduce hallucination. For this competition, grounding means:

- recommended IDs must come from the official track catalog
- response text must describe selected tracks, not imagined tracks
- every candidate should carry evidence: why it was retrieved, which state field matched it, and which retriever produced it

### 3. State Tracking Is A First-Class Module

The tutorial's state/RAG examples show a loop:

```text
intent understanding
  -> dialogue state update
  -> action selection
  -> response generation
```

Music-CRS should translate this into:

```text
latest turn + conversation history
  -> ConversationState
  -> sparse_query_view + dense_query_view + filters + penalties
  -> candidate retrieval and ranking
```

### 4. Knowledge/Data Foundation Matters

The tutorial's knowledge section matters more than its pure generation section for this repo. Music-CRS already provides:

- track metadata
- user metadata
- track embeddings
- user embeddings
- conversation dataset

These should become the knowledge foundation. A better architecture should make those resources explicit rather than hiding them behind a single query string.

### 5. Evaluation Is Moving Beyond One Final Score

The tutorial distinguishes offline evaluation, simulation, online/user studies, automated metrics, and LLM-as-judge. For the challenge, leaderboard metrics are still central, but development should measure internal stages:

- state quality
- candidate recall
- fusion quality
- reranker quality
- response groundedness
- latency/cost if using LLM calls

### 6. Open Challenges That Directly Apply

The tutorial's open challenges map directly to this repo:

- semantic gap between recommendation and response generation
- scalable grounding methods
- knowledge updates
- evolving preferences
- diversity/novelty
- robust integration of multimodal data

## Paper Takeaways

### RA-Rec: Semi-Structured State + RAG

Paper: Retrieval-Augmented Conversational Recommendation with Prompt-based Semi-Structured Natural Language State Tracking.

Useful ideas:

- Keep a JSON-like semi-structured state.
- Use LLM-generated values inside a fixed schema, so the state can capture natural language nuance without becoming shapeless.
- Track hard constraints, soft constraints, recommended items, rejected items, and accepted items.
- Generate a natural-language retrieval query from state.
- Retrieve item evidence, then generate recommendation/explanation from item metadata and retrieved evidence.
- Use late fusion: score low-level evidence first, then aggregate to item-level scores.

Music-CRS translation:

```text
ConversationState:
  hard_constraints:
    artists_include, artists_exclude, track_anchors, language, era, explicit_required_tags
  soft_constraints:
    mood, energy, genre, instrumentation, vocal_style, similarity_description
  recommended_tracks:
    track IDs or mentioned candidates from previous assistant turns
  rejected_tracks:
    track IDs rejected by the user
  accepted_tracks:
    track IDs accepted or positively referenced by the user
  sparse_query_view:
    exact names, tags, lexical metadata terms
  dense_query_view:
    semantic taste description
  evidence:
    source turn IDs for every field
```

What to steal immediately:

- the state schema idea
- hard vs soft constraints
- accepted/rejected/recommended item tracking
- state-derived retrieval queries
- grounding response generation on retrieved catalog evidence

What not to copy blindly:

- restaurant-specific fields
- review-based retrieval if music review text is not available
- LLM-heavy query/QA loops before retrieval traces exist

### ReFICR: Turn CRS Into Retrieval + Generation Instructions

Paper: Unleashing the Retrieval Potential of Large Language Models in Conversational Recommender Systems.

Useful ideas:

- Decompose CRS into subtasks.
- Treat some subtasks as retrieval instructions and others as generation instructions.
- Retrieval tasks include:
  - conversation to item retrieval
  - conversation to similar conversation retrieval
- Generation tasks include:
  - dialogue management
  - ranking
  - response generation
- Candidate ranking should see candidate items, conversation context, and retrieved knowledge.
- Increasing candidate set size can hurt LLM ranking speed and difficulty; do not ask an LLM to rank huge candidate lists directly.

Music-CRS translation:

```text
Retrieval tasks:
  Conv2Track: retrieve track candidates from current ConversationState
  Conv2User/Conv2Session: retrieve similar users or sessions if useful

Generation tasks:
  StateUpdate: update ConversationState
  ResponseWrite: write response from final selected tracks
```

What to steal immediately:

- subtask names and boundaries
- instruction labels for retrieval views
- the idea that candidate retrieval and ranking are separate

What to defer:

- fine-tuning a retrievable LLM
- contrastive instruction tuning
- LLM listwise ranking over many candidates

### Reindex-Then-Adapt: LLM Knowledge Is Distribution-Misaligned

Paper: Reindex-Then-Adapt.

Useful ideas:

- LLMs can know popular item content but still recommend with the wrong target-platform distribution.
- Generating item titles token-by-token makes it hard to control the whole item set.
- Traditional RecSys strengths still matter: distribution control, bias terms, gating, popularity adaptation, and platform-specific item availability.

Music-CRS translation:

- Do not trust a general LLM to pick tracks just because it understands music language.
- Favor catalog retrieval over open-ended title generation.
- Add simple platform-aware features:
  - track popularity if available
  - user-track embedding similarity
  - candidate source count
  - sparse rank
  - dense rank
  - penalties for rejected artists/tracks/tags

What to steal immediately:

- distribution mismatch warning
- RecSys gating mindset
- item-set control

What to defer:

- reindexing tracks into LLM tokens
- LLM probability adaptation

### MemoCRS: Memory Must Be Compact And Retrieved

Paper: MemoCRS.

Useful ideas:

- Historical conversations are useful, but full history is noisy and redundant.
- Memory should be compact: entity, attitude, timestamp.
- Memory should support add, merge, retrieve, and delete.
- Use user-specific memory for personalized interests.
- Use general memory for shared collaborative knowledge and cold-start users.
- Retrieve only relevant memory for the current conversation.

Music-CRS translation:

For this competition, start with session-level memory inside `ConversationState`. If user metadata/history is available and legal for the split, add compact user memory later.

Minimal memory record:

```text
MemoryRecord:
  entity_type: track | artist | genre | tag | mood | era | language
  entity_value: string or ID
  attitude: liked | disliked | requested | rejected | accepted | uncertain
  source_turn_id: int
  timestamp_or_turn_index: int
  confidence: float
```

What to steal immediately:

- don't pass all history to the LLM
- summarize and retrieve relevant memory
- keep attitudes, not only entities

What to avoid:

- giant conversation-history prompts
- memory fields with no source turn
- permanent user memory before split leakage and rules are checked

### RecLLM: The Large-Scale System Map

Paper: Leveraging Large Language Models in Conversational Recommender Systems.

Useful ideas:

- A production CRS needs dialogue management, retrieval, ranking/explanation, user profiles, and sometimes simulation.
- The LLM can consume natural-language profiles to modulate session context.
- Large and evolving corpora make direct LLM recommendation impractical.
- Synthetic/user simulation can help when real conversational training data is scarce.

Music-CRS translation:

Use the paper as a component checklist, not as permission to build a giant system:

```text
Dialogue manager -> StateUpdate
Retrieval -> sparse/dense/user/profile branches
Ranking/explanation -> feature-aware ranker + grounded response writer
User profile -> user metadata and embeddings
Simulator -> optional later evaluation harness
```

What to steal immediately:

- component decomposition
- natural-language profile as an input to state extraction
- ranking/explanation separation

What to defer:

- broad multimodal UI behavior
- open-ended user simulator
- full production dialogue manager

### iEvaLM: Evaluation Needs Interaction Awareness

Paper: Rethinking the Evaluation for Conversational Recommendation in the Era of Large Language Models.

Useful ideas:

- Static ground-truth matching can underestimate interactive CRS behavior.
- Many CRS conversations are vague; systems may need clarification.
- LLM-based user simulators can evaluate multi-round behavior.
- Explainability/persuasiveness can be evaluated separately from item retrieval.

Music-CRS translation:

The challenge is offline, so do not replace official metrics. Instead, supplement them:

- final metrics: NDCG@20, Hit@20, Hit@1000, MRR
- candidate metrics: branch recall, union recall, fused recall
- state metrics: did state preserve the right anchors/constraints?
- response metrics: did response mention only selected tracks and known metadata?

What to steal immediately:

- do not judge only final text
- evaluate the interaction logic through traces
- separate recommendation accuracy from explanation quality

What to defer:

- full LLM user simulator
- LLM-as-judge as a leaderboard proxy

### EventChat: Practical LLM CRS Deployment Warnings

Paper: EventChat.

Useful ideas:

- Stage-based architecture can be more stable and cost-predictable than agentic orchestration.
- Prompt-only systems hit quality limits.
- LLM ranking inside RAG can dominate cost and latency.
- Logging token usage, latency, and module behavior is part of system design, not an afterthought.

Music-CRS translation:

Even if the challenge is offline, these constraints matter because batch inference can be expensive and slow:

- avoid per-candidate LLM calls
- avoid LLM ranking over 1000 candidates
- prefer deterministic retrieval/fusion first
- use LLMs for state extraction and response writing only if they improve measured metrics
- log latency and per-session LLM call counts

What to steal immediately:

- stage-based pipeline
- cost/latency instrumentation
- avoid unconstrained agents

What to defer:

- expensive LLM ranker until small candidate set and strong evidence
- UI/user-study evaluation

## Minimum Non-Garbage Architecture

The code should be reorganized around four data contracts.

### 1. ConversationState

This is the central contract. Everything else consumes it.

```text
ConversationState:
  session_id
  current_turn_id
  intent:
    lookup | refine | pivot | reject | accept | ask_info | unclear
  positive_anchors:
    tracks, artists, genres, tags, moods, prior_recommendation_refs
  negative_anchors:
    tracks, artists, genres, tags, moods
  hard_constraints:
    required_artists, banned_artists, language, era, explicit_track_refs
  soft_constraints:
    mood, energy, instrumentation, vocal_style, similarity_description
  recommendation_history:
    recommended_track_ids_by_turn
  accepted_tracks
  rejected_tracks
  user_profile_evidence:
    user metadata, user embedding references, known safe profile hints
  sparse_query_view
  dense_query_view
  uncertainty:
    missing_anchor, ambiguous_reference, conflicting_constraints
  evidence:
    field -> source_turn_ids
```

### 2. RetrievalResult

Every retriever returns the same shape.

```text
RetrievalResult:
  branch_name:
    bm25 | dense_track | user_embedding | collaborative | tag_filter
  query_used
  candidates:
    track_id
    rank
    score
    matched_fields
    evidence
```

### 3. CandidateFeatures

Fusion and reranking should not inspect retriever internals. They consume features.

```text
CandidateFeatures:
  track_id
  sparse_rank
  dense_rank
  user_similarity
  tag_overlap
  artist_match
  negative_penalty
  accepted_anchor_similarity
  rejected_anchor_similarity
  source_branch_count
  popularity_or_prior
```

### 4. Trace

Every prediction should leave a readable trace.

```text
Trace:
  state
  sparse_query_view
  dense_query_view
  retrieval_results_by_branch
  fusion_scores
  rerank_features
  final_20_track_ids
  response_evidence
  metrics_when_available
```

## Rebuild Plan

### Phase 0: Stop The Bleeding

Goal: make the existing system inspectable before changing ranking logic.

1. Freeze one known baseline output.
2. Add trace writing around current inference.
3. Record input conversation, query string, retrieved IDs, final IDs, response, and metric if available.
4. Do not change model behavior yet.

Success criterion:

- for any bad prediction, you can answer: what query was used, what candidates were retrieved, and where the target disappeared.

### Phase 1: Add ConversationState Without Changing Retrieval

Goal: introduce the main contract safely.

1. Create `ConversationState` schema.
2. Populate it with deterministic extraction where easy:
   - known mentioned track IDs
   - prior recommended IDs
   - explicit rejected/accepted track references
   - raw latest user turn
3. Add optional LLM extraction for fuzzy constraints, but keep source-turn evidence.
4. Derive the old query string from the new state, so behavior can stay close.

Success criterion:

- old system and state-backed system are comparable in output
- traces now show what the system believes the conversation means

### Phase 2: Split Sparse And Dense Views

Goal: stop forcing one string to serve every retriever.

1. `sparse_query_view`: exact names, tags, genres, lexical constraints.
2. `dense_query_view`: semantic mood/style/similarity description.
3. Run BM25/full-text retrieval from sparse view.
4. Run embedding retrieval from dense view.
5. Retrieve top 1000 from each branch.

Success criterion:

- measure branch Hit@1000 and union Hit@1000
- union should beat either branch alone

### Phase 3: Add Fusion Before Fancy Reranking

Goal: build a strong deterministic candidate pool.

1. Fuse branch lists with RRF.
2. Preserve branch rank features.
3. Penalize explicit negatives.
4. Boost accepted anchors and direct hard-constraint matches.

Success criterion:

- RRF/fusion improves or preserves Hit@1000
- NDCG@20 does not collapse

### Phase 4: Add A Small Feature-Aware Reranker

Goal: improve the final 20 without losing recall.

Start simple:

- linear weighted score
- LambdaMART or logistic model if enough labels and time
- no per-candidate LLM calls

Only add an LLM reranker after narrowing candidates to a small list and proving value on dev.

Success criterion:

- top-20 metrics improve
- failure traces still explain why

### Phase 5: Grounded Response Writer

Goal: make response generation safe.

Input to response writer:

- conversation
- selected top tracks
- catalog metadata for selected tracks
- state summary

Hard rule:

- the response may not recommend or describe tracks outside the selected catalog evidence.

## What Not To Build First

Avoid these until the modular baseline is working:

- pure LLM recommendation that generates track titles or IDs
- agentic planner with open-ended tools
- LLM reranker over hundreds or thousands of tracks
- one giant prompt that performs state, retrieval, ranking, and response
- long-term user memory without split/rules checks
- LLM-as-judge replacing NDCG/Hit/MRR
- synthetic simulator before dev-set trace failures are understood

## Practical "Your Code Is Garbage" Diagnosis

If the current code feels bad, the likely core problem is not style. It is probably boundary collapse:

- query understanding is mixed with retrieval
- retrieval is mixed with ranking
- ranking is mixed with response generation
- state is implicit in prompt text instead of explicit in data
- failures are visible only in final predictions

The fix is not a big rewrite for its own sake. The fix is to force the system through stable contracts:

```text
ConversationState
RetrievalResult
CandidateFeatures
Trace
```

Once those exist, the old code can be wrapped module by module. The repo can become less bad without stopping all experiments.

## Recommended Next Artifact

Create a concrete implementation spec:

```text
State-to-hybrid retrieval v0
  input: conversation session
  output: 20 track IDs + response + trace
  modules:
    state_builder
    retrieval_views
    bm25_branch
    dense_branch
    rrf_fusion
    response_writer
    trace_writer
```

First benchmark:

- compare against current BM25, dense, rewrite-only, and offline RRF runs
- measure NDCG@20, Hit@1000, branch recall, union recall
- inspect traces for sessions where candidate recall changed

This is the most source-backed way to turn the current code into a system that can actually improve.
