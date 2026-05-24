# Detailed Literature Review for the Music-CRS Competition

Status: `expanded literature review`

Audience: a builder who does not already know conversational recommender systems, but needs to make the current Music-CRS codebase less fragile.

Primary question:

```text
Which ideas from the Gen-CRS tutorial and nearby papers are actually useful for the RecSys Challenge 2026 Music-CRS competition?
```

Short answer:

```text
Build a modular, catalog-grounded conversational recommender.

Use LLMs mainly for:
  - understanding the conversation
  - maintaining structured state
  - writing the final response from retrieved evidence

Do not rely on an LLM to freely invent tracks.
Do not start with an agent loop.
Do not hide retrieval, ranking, and response generation inside one prompt.
```

## 1. Competition Context

The competition is a conversational music recommendation task. Given a dialogue history and user context, the system must output:

- exactly 20 ranked track IDs
- track IDs from the provided catalog
- a natural language response

The official challenge page frames the task as a bridge between natural language understanding and high-precision recommender systems. That phrasing matters: this is not only an NLP task and not only a retrieval task. The system needs both.

The repo docs currently describe the core local catalog as:

- `15,199` train sessions
- `test`, `blind_a`, and `blind_b` evaluation splits
- `47,071` tracks in the `all_tracks` catalog used here
- user metadata fields such as age, country, gender, preferred language, and preferred musical culture
- track metadata fields such as track name, artist, album, tags, popularity, release date, duration, ISRC, artist ID, and album ID
- precomputed track embeddings for audio, image, collaborative filtering, attributes, lyrics, and metadata
- precomputed user collaborative filtering embeddings

The practical shape of the challenge is therefore:

```text
multi-turn dialogue
  + user profile
  + track metadata
  + track embeddings
  + user embeddings
  -> ranked top-20 valid track IDs
  -> grounded natural language response
```

This review evaluates papers by whether they improve one of those arrows.

## 2. Literature Map By Usefulness

The most useful literature for this competition falls into seven buckets.

| Bucket | Main lesson | Competition relevance |
|---|---|---|
| CRS foundations | A CRS is a multi-component system, not just a chatbot | Helps choose stable architecture boundaries |
| Gen-CRS tutorial | Modern CRS can be unified, modular, or agentic | Strongly supports modular build for this repo |
| State tracking and RAG | Keep explicit preference state, then retrieve evidence | Highest immediate value |
| LLM retrieval/ranking | LLMs can help interpret queries but need catalog control | Useful, but avoid huge LLM rankers first |
| Memory and personalization | Memory should be compact, source-backed, and retrieved | Useful after session state is working |
| Music-specific CRS | Music needs multimodal and audio-aware signals | Useful because challenge provides embeddings |
| Evaluation | Final score is not enough to debug CRS failures | Essential for fixing a bad codebase |

## 3. Strongest Overall Recommendation

The tutorial and papers converge on this architecture:

```text
Conversation history
  -> ConversationState
  -> retrieval views
       - sparse lexical view
       - dense semantic view
       - user/profile view
       - prior accepted/rejected item view
  -> branch retrieval
       - BM25 / full text search
       - metadata embeddings
       - lyrics/attributes embeddings
       - collaborative user-track scoring
       - optional audio/image embeddings
  -> fusion
       - reciprocal rank fusion first
       - candidate source count
       - negative penalties
       - direct constraint boosts
  -> small reranker
       - feature-aware deterministic model first
       - LLM reranker only for small candidate sets later
  -> grounded response writer
       - use selected tracks and catalog metadata only
  -> trace
       - state, queries, candidates, scores, final IDs, response evidence
```

This is the opposite of a one-prompt system. The goal is not to make the model sound smarter. The goal is to make the recommendation path measurable.

## 4. Paper-by-Paper Review

### 4.1 Jannach et al., "A Survey on Conversational Recommender Systems"

Link: <https://doi.org/10.1145/3453154>

Type: foundation / survey.

Core idea:

Conversational recommender systems differ from traditional one-shot recommenders because they allow interactive preference elicitation, feedback, questions, and refinement. The survey categorizes CRS work by supported user intents, background knowledge, technical approach, and evaluation method.

Why it matters for Music-CRS:

The challenge conversations are not independent search queries. They contain preference elicitation, feedback, and refinement. A user can say:

```text
that was too mellow
more like the second one
something with a warmer vocal
not that artist again
```

Those utterances only make sense if the system keeps track of:

- what was recommended earlier
- which item the user refers to
- what was liked
- what was rejected
- which constraints are still active
- which constraints were superseded

What to steal:

- Treat CRS as an interaction problem, not only a ranking problem.
- Support user intents explicitly: request, refine, reject, accept, compare, ask for more information, and pivot.
- Separate dialogue understanding from recommendation ranking.
- Evaluate both recommendation quality and conversation behavior.

What not to overbuild:

- Do not build a full question-asking dialogue policy before the offline ranked retrieval task works.
- Do not optimize for a real-time interactive user study before the challenge metrics are under control.

Implementation priority:

`now`, as architecture framing.

Concrete code implication:

Create an enum or schema field like:

```text
intent_mode:
  lookup
  refine
  pivot
  reject
  accept
  compare
  ask_info
  unclear
```

Use that state to choose retrieval strategy. A `refine` turn should preserve accepted anchors and apply new constraints; a `pivot` turn should reduce carryover; a `reject` turn should add explicit penalties.

Risk if ignored:

The system turns every user message into a flat query. That fails on anaphora, negative feedback, and late-turn refinement.

### 4.2 Gen-CRS 2025 Tutorial, Kolb et al.

Links:

- Tutorial page: <https://recsys-lab.at/gen-conv-recsys-tutorial/>
- Slides PDF: <https://recsys-lab.at/wp-content/uploads/2025/10/Gen-CRS2025_Tutorial.pdf>

Type: tutorial / architecture map.

Core idea:

The tutorial organizes modern generative conversational recommenders into a few broad patterns:

- unified systems
- modular systems
- agentic systems
- retrieval-augmented and knowledge-grounded systems
- systems that need better evaluation, memory, grounding, and safety

Why it matters for Music-CRS:

This competition is exactly where the tutorial's architecture taxonomy becomes practical. The output has to be valid catalog track IDs, so a pure generative system is unsafe. The task is offline batch inference, so an open-ended agent loop is likely overkill. A modular system fits the contest:

```text
state tracking -> retrieval -> reranking -> response generation
```

What to steal:

- Use modular Gen-CRS as the default architecture.
- Use RAG-style grounding for the response.
- Treat knowledge/data foundation as a first-class part of the system.
- Evaluate internal stages, not only final output.
- Keep hallucination control explicit.

What not to steal first:

- Agentic orchestration with many tool calls.
- Fully unified LLM recommendation.
- Large LLM-as-ranker loops over hundreds or thousands of candidates.

Implementation priority:

`now`, as the architecture blueprint.

Concrete code implication:

The codebase should expose contracts like:

```text
ConversationState
RetrievalResult
CandidateFeatures
RankedRecommendation
ResponseEvidence
Trace
```

If a function cannot be described as one of those contracts, it is probably mixing responsibilities.

Risk if ignored:

The code stays tangled. When NDCG changes, you cannot tell whether the cause was query understanding, candidate recall, fusion, reranking, or response generation.

### 4.3 RA-Rec, "Retrieval-Augmented Conversational Recommendation with Prompt-based Semi-Structured Natural Language State Tracking"

Link: <https://arxiv.org/abs/2406.00033>

Type: state tracking + retrieval augmented recommendation.

Core idea:

RA-Rec uses LLMs for semi-structured dialogue state tracking and retrieval-augmented recommendation. The paper's important move is not "ask an LLM for the answer"; it is "use an LLM to keep a structured state that can drive retrieval."

The paper highlights that user preferences in natural language can be indirect, rich, and hard to match with only metadata. It proposes an LLM-driven dialogue state tracking system where the state remains semi-structured, rather than disappearing into free text.

Why it matters for Music-CRS:

This is the closest paper-level design pattern for the competition. The challenge conversations require:

- resolving references to prior recommendations
- remembering accepted and rejected tracks
- carrying forward soft preferences
- recognizing hard constraints
- turning all of that into retrieval queries

Music examples:

```text
"More like that, but less gloomy."
"The previous one was too electronic."
"Keep the chill mood, but give me something with vocals."
"I liked the artist, not the song."
```

A flat query is not enough for these turns.

What to steal:

- Semi-structured state.
- Natural-language values inside a fixed schema.
- Hard constraints separate from soft preferences.
- Accepted items separate from rejected items.
- State-derived retrieval queries.
- Response generation grounded in retrieved item evidence.

Music-CRS translation:

```text
ConversationState:
  session_id
  user_id
  current_turn_number
  intent_mode

  positive_anchors:
    track_ids
    artists
    albums
    tags
    moods
    natural_language_descriptions

  negative_anchors:
    track_ids
    artists
    albums
    tags
    moods
    natural_language_descriptions

  hard_constraints:
    required_artist_ids
    banned_artist_ids
    required_languages
    release_year_min
    release_year_max
    explicit_track_refs

  soft_constraints:
    genre
    mood
    energy
    instrumentation
    vocal_style
    era
    similarity_description

  recommendation_history:
    turn_number -> track_id

  sparse_query_view:
    exact artist/title/album/tag/release terms

  dense_query_view:
    semantic description of desired sound

  evidence:
    state_field -> source turn ids
```

What not to copy blindly:

- Restaurant/product-specific fields.
- Review retrieval if we do not have comparable music review text.
- LLM-heavy reasoning before retrieval traces exist.

Implementation priority:

`now`, highest priority.

Concrete experiment:

Compare three candidate-generation setups:

```text
A. latest user turn -> BM25
B. full conversation string -> BM25
C. ConversationState -> sparse_query_view + dense_query_view -> hybrid retrieval
```

Track:

- Hit@1000 by turn
- NDCG@20 by turn
- target disappeared at retrieval vs rerank
- failures involving "previous one", rejection, or refinement

Risk if ignored:

The system remains unable to tell the difference between "more like this", "not this", and "forget that, new direction".

### 4.4 TalkPlayData 2, "An Agentic Synthetic Data Pipeline for Multimodal Conversational Music Recommendation"

Link: <https://arxiv.org/abs/2509.09685>

Type: dataset / synthetic data generation / music CRS.

Core idea:

TalkPlayData 2 presents a synthetic dataset for multimodal conversational music recommendation generated by an agentic pipeline. Multiple LLM agents play specialized roles, including listener and recommender roles, with access to different information. Conversations are conditioned on listener profiles, goals, and music items.

Why it matters for Music-CRS:

The challenge uses TalkPlayData-Challenge, which is downstream of this research direction. That means the dataset is not a random collection of human chats. It likely has structure induced by:

- listener goals
- recommender behavior
- multimodal item evidence
- profile-conditioned dialogue
- multi-agent generation patterns

This affects modeling strategy. A system should exploit the dataset schema rather than treating the conversation as generic text.

What to steal:

- Condition state extraction on the listener goal and user profile.
- Treat each session as goal-directed.
- Expect repeated conversational patterns because the data was generated by a pipeline.
- Use multimodal music resources if available, especially track embeddings.

What to be careful about:

- Synthetic conversations can contain artifacts. A model can overfit to stylistic patterns rather than real preference logic.
- If the listener and recommender agents used specific phrasing templates, lexical retrieval can pick up spurious signals.
- Blind sets may expose whether the model learned robust state or only generation artifacts.

Implementation priority:

`now`, as data interpretation.

Concrete code implication:

Include the session `conversation_goal` in state extraction:

```text
goal_context:
  category
  specificity
  listener_goal
```

Use it carefully as context, not as a replacement for turn-level evidence.

Risk if ignored:

The model may miss that the session has a goal trajectory. It may overreact to the latest turn and underuse profile/goal fields.

### 4.5 TALKPLAY, "Multimodal Music Recommendation with Large Language Models"

Link: <https://arxiv.org/abs/2502.13713>

Type: music-specific unified LLM recommender.

Core idea:

TALKPLAY reformulates music recommendation as token generation with LLMs. It extends an LLM with multimodal music tokens derived from audio, lyrics, metadata, semantic tags, and playlist co-occurrence signals. This is a unified approach: the model recommends and responds in one architecture.

Why it matters for Music-CRS:

The paper is highly relevant as background because it is from the same music CRS research neighborhood and directly addresses multimodal music recommendation with LLMs.

However, it is not the most practical next step for this repo.

What to steal:

- Music recommendation should use multimodal item signals.
- Metadata-only systems miss important audio and cultural signals.
- Long conversation context matters.
- Joint recommendation plus language response is possible when the model is trained for it.

What not to copy now:

- Training a unified LLM recommender with expanded music vocabulary.
- Generating recommendations as unconstrained item tokens unless the repo has the infrastructure to guarantee catalog validity.
- Treating the challenge as solved by a single LLM architecture.

Implementation priority:

`later`, unless the team has time and compute for model training.

Near-term translation:

Use TALKPLAY as a justification for branch retrieval over multiple track representations:

```text
metadata-qwen retrieval
attributes-qwen retrieval
lyrics-qwen retrieval
cf-bpr user-track scoring
audio-laion retrieval for sound/mood turns
image-siglip2 only if album-art semantics appear useful
```

Risk if ignored:

The system may stay stuck in lexical metadata retrieval and fail on music-language concepts like "warm", "nocturnal", "washed out", "driving", "intimate", or "crunchy guitar".

### 4.6 MusiCRS, "Benchmarking Audio-Centric Conversational Recommendation"

Link: <https://arxiv.org/abs/2509.19469>

Type: music CRS benchmark / audio grounding.

Core idea:

MusiCRS argues that music is a special CRS domain because effective recommendation may require reasoning over audio content, not only text or metadata. It provides an audio-centric benchmark and finds that current systems struggle with cross-modal integration.

Why it matters for Music-CRS:

The challenge provides precomputed multimodal track embeddings, including audio and lyrics. That means the competition designers likely expect participants to go beyond simple text matching.

What to steal:

- Treat audio and lyrics embeddings as real retrieval branches, not decoration.
- Test modality-specific performance instead of assuming "more modalities always helps".
- Build ablations for text-only, audio-only, collaborative-only, and fused retrieval.

What not to overclaim:

- Audio embeddings are not automatically better. MusiCRS explicitly warns that cross-modal integration is hard.
- Blindly concatenating every embedding can hurt.

Implementation priority:

`next`, after state and base hybrid retrieval are traceable.

Concrete experiment:

Run candidate recall by branch:

```text
metadata-qwen
attributes-qwen
lyrics-qwen
audio-laion_clap
cf-bpr user-track
BM25 tags/artist/title
RRF union
```

Then segment failures by utterance type:

- exact artist/title
- mood/style
- similarity to prior track
- lyrics/theme
- audio texture/instrumentation
- demographic or cultural preference

Risk if ignored:

The system may fail on exactly the music-specific language that differentiates this challenge from generic movie or product CRS.

### 4.7 ReFICR, "Unleashing the Retrieval Potential of Large Language Models in Conversational Recommender Systems"

Link: <https://doi.org/10.1145/3640457.3688146>

Type: LLM retrieval instruction tuning / decomposition.

Core idea:

ReFICR decomposes CRS into subtasks and distinguishes retrieval-oriented instructions from generation-oriented instructions. The relevant lesson is that retrieval and generation should have different roles.

Why it matters for Music-CRS:

This paper supports a clean split:

```text
Retrieval instructions:
  - conversation -> tracks
  - conversation -> similar sessions
  - state -> query views

Generation instructions:
  - state update
  - response writing
  - optional explanation
```

What to steal:

- Name subtasks explicitly.
- Do not make one model call responsible for every behavior.
- Candidate retrieval and candidate ranking are different problems.
- If using LLMs, feed them narrow instructions and narrow candidate sets.

What to defer:

- Fine-tuning a retrievable LLM.
- Contrastive instruction tuning.
- LLM ranking over very large candidate pools.

Implementation priority:

`next`, as design vocabulary and optional future training direction.

Concrete code implication:

Put prompt templates, if any, behind task names:

```text
StateUpdatePrompt
SparseQueryPrompt
DenseQueryPrompt
ResponseGroundingPrompt
SmallCandidateRerankPrompt
```

Do not have one `recommend_prompt` that does all of these.

Risk if ignored:

The system becomes impossible to debug because every failure is "the prompt did it".

### 4.8 Reindex-Then-Adapt

Link: <https://arxiv.org/abs/2405.12119>

Type: LLM item-set control / recommendation distribution adaptation.

Core idea:

LLMs can understand complex conversational contexts and item content, but controlling the distribution of recommended items is difficult when the model generates item titles autoregressively. Reindex-Then-Adapt converts item titles into single tokens and adapts probability distributions, combining LLM understanding with RecSys-style control.

Why it matters for Music-CRS:

The warning transfers directly: an LLM may understand the user's taste and still recommend the wrong item distribution, invalid titles, or popular-but-wrong tracks. The challenge needs valid catalog IDs and high ranking metrics.

What to steal:

- Catalog control matters.
- Platform/item distribution matters.
- Traditional RecSys scoring signals still matter.
- Use LLMs for understanding, but keep item selection gated by catalog retrieval and ranking.

What not to build now:

- Reindexing every track into custom LLM tokens.
- Full probability adaptation over item tokens.

Implementation priority:

`now`, as a guardrail.

Concrete code implication:

Never let response generation introduce new recommendation IDs. The response writer receives:

```text
selected_track_ids
selected_track_metadata
ConversationState
```

and is only allowed to talk about those selected tracks.

Risk if ignored:

The model can sound impressive while recommending invalid or distributionally poor items.

### 4.9 "Large Language Models as Zero-Shot Conversational Recommenders"

Link: <https://arxiv.org/abs/2308.10053>

Type: empirical LLM baseline / warning and opportunity.

Core idea:

The paper studies LLMs as zero-shot conversational recommenders and finds that LLMs can perform surprisingly well in some conversational recommendation settings, while also exposing limitations such as popularity bias, dataset effects, and gaps in collaborative knowledge.

Why it matters for Music-CRS:

This is a useful reminder that LLMs are not useless. They can interpret natural language, infer preferences, and generate persuasive explanations. But the competition's catalog constraint changes the risk profile.

What to steal:

- LLMs are strong at understanding conversation context.
- Use them for state extraction and explanation.
- Probe for popularity bias and collaborative weakness.

What not to rely on:

- Zero-shot LLM recommendation as the final item selector.
- Generated track titles as submission IDs.
- Popularity-biased output as if it were personalization.

Implementation priority:

`now`, as a bounded component.

Concrete experiment:

Use an LLM to produce only structured state:

```json
{
  "intent_mode": "refine",
  "positive_anchors": ["..."],
  "negative_anchors": ["..."],
  "active_constraints": ["..."],
  "sparse_query_view": "...",
  "dense_query_view": "..."
}
```

Then compare retrieval metrics against deterministic extraction. Do not ask the LLM to output final track IDs.

Risk if ignored:

Either extreme is bad: a pure LLM recommender loses catalog control, while a no-LLM pipeline may miss nuanced language.

### 4.10 MemoCRS

Link: <https://arxiv.org/abs/2407.04960>

Type: memory-enhanced sequential CRS.

Core idea:

MemoCRS argues that user preferences have continuity across sessions, but raw historical dialogue is redundant and noisy. It proposes user-specific memory and general memory to retrieve relevant preference information while reducing noise and helping cold-start users.

Why it matters for Music-CRS:

The immediate competition input is session-level dialogue, but user metadata and embeddings are also available. Long-term user memory may or may not be legal/useful depending on split and data access, but session memory is definitely needed.

What to steal:

- Memory should be compact.
- Memory should store entity plus attitude.
- Memory should be retrievable.
- Historical data should not be blindly pasted into prompts.
- Cold-start and user-specific cases may need different paths.

Music-CRS memory record:

```text
MemoryRecord:
  entity_type: track | artist | album | tag | genre | mood | era | language | instrumentation
  entity_value: string or ID
  attitude: requested | liked | disliked | rejected | accepted | uncertain
  source_turn_number: int
  source_role: user | assistant | music
  confidence: float
```

What to defer:

- Permanent cross-session user memory until split leakage is checked.
- Complex memory merging.
- LLM memory agents.

Implementation priority:

`now` for session memory, `later` for cross-session memory.

Concrete code implication:

Represent prior recommendations and user feedback explicitly:

```text
recommendation_history:
  turn 1 -> track_a
  turn 2 -> track_b

feedback_events:
  turn 3:
    refers_to: track_b
    attitude: liked
    constraint_delta: "more acoustic"
```

Risk if ignored:

The system treats "that one" and "the second song" as meaningless text.

### 4.11 RecLLM, "Leveraging Large Language Models in Conversational Recommender Systems"

Link: <https://arxiv.org/abs/2305.07961>

Type: production CRS architecture / roadmap.

Core idea:

RecLLM presents a roadmap for building a large-scale LLM-based CRS. It emphasizes user preference understanding, dialogue management, retrieval from external sources, explainable recommendations, natural-language user profiles, and user simulation when conversational data is scarce.

Why it matters for Music-CRS:

This is a component checklist for the repo. The challenge already has conversational data, user profiles, and catalog resources, so the system does not need a full simulator first. But it does need the same architectural pieces.

What to steal:

- Dialogue manager maps to `ConversationState`.
- Retrieval/ranking should be external and controllable.
- User profiles can be represented in natural language for LLM state extraction.
- Explanations should be grounded in candidate evidence.
- Simulation is useful later for stress tests, not a first priority.

What to defer:

- Full production dialogue manager.
- Broad interactive user simulator.
- Complex UI behavior.

Implementation priority:

`now`, as component checklist.

Concrete code implication:

Add a profile view to state extraction:

```text
user_profile_view:
  age_group
  country_name
  preferred_language
  preferred_musical_culture
  optional user embedding id
```

Use it as a weak personalization signal, not as a hard filter.

Risk if ignored:

The system loses available personalization and treats every user as anonymous even when the challenge provides profile/context.

### 4.12 iEvaLM, "Rethinking the Evaluation for Conversational Recommendation in the Era of Large Language Models"

Link: <https://aclanthology.org/2023.emnlp-main.621/>

Type: evaluation.

Core idea:

iEvaLM argues that existing CRS evaluation overemphasizes matching static ground-truth items and underrepresents the interactive nature of CRS. It proposes LLM-based user simulation and emphasizes explainability evaluation.

Why it matters for Music-CRS:

The official competition metrics still matter most. Do not replace NDCG@20 or the leaderboard with an LLM judge. But for development, the paper's core warning is crucial: final ranked output alone does not explain CRS failures.

What to steal:

- Separate recommendation accuracy from explanation quality.
- Inspect interaction behavior, not only final IDs.
- Use trace-level diagnostics for multi-turn failures.
- Response quality is a distinct dimension from retrieval quality.

What not to do now:

- Build a full LLM user simulator as the main evaluator.
- Optimize for LLM-as-judge text score while recommendation quality is bad.

Implementation priority:

`now`, for diagnostics.

Concrete evaluation dashboard:

```text
For each session-turn:
  state_ok:
    were anchors resolved?
    were rejections captured?
    were constraints retained?

  retrieval_ok:
    target in BM25 top 1000?
    target in dense top 1000?
    target in fused pool?

  ranking_ok:
    target final rank
    candidate features for target
    negative penalties applied?

  response_ok:
    mentions only selected tracks?
    uses real artist/title/tag metadata?
```

Risk if ignored:

You can improve final prose while recommendation quality stays bad, or improve candidate recall while final NDCG drops, without knowing why.

### 4.13 EventChat

Link: <https://arxiv.org/abs/2407.04472>

Type: deployed LLM-driven CRS / cost and latency warning.

Core idea:

EventChat describes an LLM-driven CRS in a real SME setting. It reports user-facing promise but also practical problems: latency, cost, response quality, and the expense of using a strong LLM as a ranker inside a RAG pipeline.

Why it matters for Music-CRS:

Even though the challenge is offline, batch inference can still become slow and expensive. If the code uses per-candidate LLM ranking or agentic tool loops, it may become impractical for dev and blind submissions.

What to steal:

- Stage-based design.
- Latency and token-count logging.
- Be skeptical of prompt-only quality.
- Avoid using an advanced LLM as a large-candidate ranker unless proven necessary.

What to defer:

- Live UI quality studies.
- Per-interaction user satisfaction metrics.

Implementation priority:

`now`, as engineering discipline.

Concrete code implication:

Every run should report:

```text
sessions processed
LLM calls per session
tokens per session
retrieval latency
reranking latency
response latency
total cost estimate if applicable
```

Risk if ignored:

The best-looking architecture on paper may be too slow, expensive, or nondeterministic to run before the deadline.

## 5. The Main Disagreement In The Literature

The literature does not say one thing. It has a tension:

```text
Unified LLM systems:
  attractive because they can jointly understand context and generate responses
  risky because item validity, distribution control, and debuggability are weak

Modular systems:
  less glamorous
  easier to debug
  better fit for fixed-catalog ranked retrieval

Agentic systems:
  flexible
  expensive and nondeterministic
  better after the basic retrieval/ranking pipeline is strong
```

For this competition, the tie-breaker is the fixed catalog and metric structure. We should choose the system that lets us measure retrieval and ranking.

## 6. What The Review Says To Build

### 6.1 ConversationState v0

Start with a small but useful state. Do not wait for the perfect ontology.

```text
ConversationState:
  ids:
    session_id
    user_id
    current_turn_number

  context:
    user_profile
    conversation_goal

  intent:
    mode
    confidence

  anchors:
    liked_track_ids
    disliked_track_ids
    referenced_prior_track_ids
    liked_artists
    disliked_artists
    liked_tags
    disliked_tags

  constraints:
    hard_positive
    hard_negative
    soft_positive
    soft_negative

  retrieval_views:
    sparse_query_view
    dense_query_view
    profile_query_view

  evidence:
    field -> source_turn_numbers
```

Minimum viable behavior:

- capture prior `role="music"` track IDs
- map "previous", "that", "second one", and "last song" to prior track IDs when possible
- capture explicit "not", "too", "less", "avoid" as negatives
- preserve liked anchors across refinement
- create separate sparse and dense query views

### 6.2 Retrieval Branches

The literature strongly supports multiple retrieval branches. Each branch should return the same `RetrievalResult` schema.

Immediate branches:

```text
bm25_metadata:
  query: sparse_query_view
  fields: track_name, artist_name, album_name, release_date, tag_list

dense_metadata:
  query: dense_query_view
  vectors: metadata-qwen3_embedding_0.6b

dense_attributes:
  query: dense_query_view
  vectors: attributes-qwen3_embedding_0.6b

dense_lyrics:
  query: dense_query_view
  vectors: lyrics-qwen3_embedding_0.6b

user_cf:
  query: user_id
  vectors: user cf-bpr against track cf-bpr
```

Next branches:

```text
audio_clap:
  use for sound, mood, instrumentation, texture, energy

accepted_anchor_similarity:
  retrieve tracks similar to liked prior tracks

negative_anchor_filter:
  penalize tracks similar to rejected prior tracks
```

Do not blend all signals too early. Keep branch-level ranks visible.

### 6.3 Fusion First, Learned Rerank Later

Start with reciprocal rank fusion because it is simple, robust, and traceable.

Candidate features:

```text
track_id
bm25_rank
metadata_dense_rank
attributes_dense_rank
lyrics_dense_rank
audio_rank
user_cf_rank
source_branch_count
artist_exact_match
tag_overlap
popularity
accepted_anchor_similarity
rejected_anchor_similarity
negative_constraint_penalty
hard_constraint_violation
```

Then add a small feature-aware reranker. Options:

- weighted linear score
- logistic regression
- LambdaMART / LightGBM ranker
- small neural reranker only after enough labels and traces exist

Avoid:

- LLM reranking over 1000 candidates
- prompt-only reranking as the primary top-20 selector
- opaque rerank features

### 6.4 Grounded Response Writer

The response writer should not decide recommendations. It should verbalize them.

Inputs:

```text
ConversationState
top_20_track_ids
metadata for top recommended tracks
evidence snippets:
  matched tags
  matched artist/title
  matched mood/genre
  accepted anchor similarity if available
```

Rules:

- mention only selected tracks or selected artists
- do not invent catalog facts
- do not promise exact audio qualities unless supported by tags/metadata/embedding explanation
- keep response aligned with current intent

This directly follows the tutorial's grounding theme and the Reindex-Then-Adapt warning about item-set control.

## 7. What To Measure

The review implies this evaluation stack:

| Level | Metric or diagnostic | Question answered |
|---|---|---|
| Retrieval branch | Hit@1000 per branch | Can this branch find the target at all? |
| Candidate union | Hit@1000 union | Does hybrid retrieval increase coverage? |
| Fusion | target fused rank | Did fusion bury the target? |
| Final top 20 | NDCG@20, Hit@20, MRR | Did final ranking solve the official task? |
| Diversity | unique recommended tracks / catalog | Are we collapsing to popular items? |
| State | anchor/constraint audit | Did the system understand the conversation? |
| Response | groundedness audit | Does text only use selected catalog evidence? |
| Cost | LLM calls, tokens, latency | Can this run at blind-set scale? |

## 8. Ablations This Literature Review Implies

Run these before building anything fancy:

1. Latest turn BM25 vs full conversation BM25.
2. Full conversation BM25 vs state-derived sparse query.
3. State-derived sparse query vs state-derived dense query.
4. BM25 only vs dense only vs RRF union.
5. Metadata dense vs attributes dense vs lyrics dense vs audio dense.
6. No user profile vs profile text in state extraction.
7. No user embedding vs user CF branch.
8. No negative penalties vs explicit rejection penalties.
9. No accepted anchor retrieval vs accepted-anchor similarity branch.
10. RRF fusion vs weighted feature score.
11. Response-only LLM vs LLM state extraction plus deterministic retrieval.
12. No trace logging vs full trace logging for failure analysis.

The first six are probably the highest return.

## 9. What Is Less Useful Right Now

### Pure unified LLM recommendation

Tempting because it is simple to prototype. Weak because the challenge requires valid IDs and ranking control.

Use later only if:

- the model is trained with catalog item tokens
- valid ID generation is guaranteed
- it beats modular retrieval on dev metrics

### Agentic CRS

Tempting because the tutorial and TalkPlayData pipeline use agentic ideas. Weak as a first competition system because agent loops add latency, nondeterminism, and debugging burden.

Use later for:

- automatic failure analysis
- query rewriting experiments
- interactive simulation

Not for:

- first ranked retrieval pipeline

### Full LLM reranker

Tempting because LLMs understand subtle preference text. Risky because candidate sets are large and cost/latency can dominate.

Use later only after:

- candidate set is narrowed to perhaps 20-100 items
- deterministic reranker is already measured
- prompt output is stable and parseable

### Long-term user memory

Tempting because MemoCRS shows value. Risky because split leakage and available-history rules need careful checking.

Use now only as:

- session memory
- current conversation memory
- profile metadata
- provided user embeddings

## 10. Suggested Build Order

### Sprint 1: Traceable baseline

Goal: make current failures visible.

Deliverables:

- trace file per prediction
- query used
- retrieved candidates
- final 20
- response evidence
- target rank if labels are available

### Sprint 2: ConversationState v0

Goal: make conversation understanding explicit.

Deliverables:

- deterministic state extraction for prior music turns and explicit feedback
- optional LLM state extraction for fuzzy constraints
- sparse and dense query views
- source-turn evidence for state fields

### Sprint 3: Hybrid retrieval v0

Goal: improve candidate recall.

Deliverables:

- BM25 branch
- metadata dense branch
- attributes dense branch
- lyrics dense branch
- RRF fusion
- branch-level Hit@1000 report

### Sprint 4: Personalization and negatives

Goal: stop recommending against the conversation.

Deliverables:

- rejection penalties
- accepted-anchor similarity
- user CF branch if embeddings are reliable
- profile-aware rerank features

### Sprint 5: Small reranker

Goal: improve NDCG@20.

Deliverables:

- feature table
- simple weighted model
- learned reranker if enough labels
- per-turn analysis

### Sprint 6: Grounded response

Goal: avoid response hallucination and improve judge dimensions.

Deliverables:

- selected-track metadata pack
- response prompt that cannot invent recommendations
- response groundedness checks

## 11. Practical Interpretation For A Messy Codebase

If the code feels like garbage, the likely architectural smell is boundary collapse:

```text
conversation understanding mixed with retrieval
retrieval mixed with ranking
ranking mixed with generation
generation mixed with item selection
evaluation mixed with final prediction only
```

The literature points to the same repair pattern repeatedly:

```text
make state explicit
make retrieval branches explicit
make ranking features explicit
make response evidence explicit
make traces unavoidable
```

You do not need a grand rewrite to start. The first useful move is a wrapper:

```text
existing input
  -> new ConversationState object
  -> derive the old query from state
  -> run existing retrieval
  -> log trace
```

That lets you introduce better contracts without stopping experiments.

## 12. Ranked Source Priority

| Priority | Source | Use it for | Build impact |
|---|---|---|---|
| 1 | RA-Rec | ConversationState and state-derived retrieval | Very high |
| 2 | Gen-CRS tutorial | Modular architecture and grounding | Very high |
| 3 | Music-CRS challenge docs | Exact task, resources, evaluation | Very high |
| 4 | TalkPlayData 2 | Dataset generation assumptions and goal/profile context | High |
| 5 | MusiCRS | Audio/multimodal retrieval ablations | High |
| 6 | Reindex-Then-Adapt | Catalog control and distribution warning | High |
| 7 | MemoCRS | Compact session memory and attitude tracking | Medium-high |
| 8 | RecLLM | Component checklist and profile-aware CRS | Medium |
| 9 | ReFICR | Retrieval/generation subtask split | Medium |
| 10 | iEvaLM | Stage-level and interaction-aware evaluation | Medium |
| 11 | EventChat | Cost, latency, and prompt-only warnings | Medium |
| 12 | Zero-shot LLM CRS | Bounded use of LLMs for understanding | Medium |

## 13. One-Page Design This Review Supports

```text
Input:
  conversation, user_profile, conversation_goal

State:
  ConversationState with positive anchors, negatives, constraints, prior track refs

Retrieval:
  BM25 over metadata/tag text
  dense metadata/attributes/lyrics/audio branches
  user CF branch
  accepted-anchor similarity branch

Fusion:
  RRF + branch count + direct constraints + negative penalties

Rerank:
  feature-aware score, trained later if useful

Output:
  top 20 valid track IDs
  response generated only from selected-track evidence

Trace:
  all state fields, source turns, branch results, fusion scores, final rank
```

## 14. Bottom Line

The most useful literature does not say "use a bigger LLM." It says:

```text
Use language models to understand conversation.
Use recommender machinery to control item selection.
Use retrieval to ground the response.
Use traces to know where the system failed.
```

For this competition, the next serious architecture should be:

```text
state-first hybrid retrieval with grounded response generation
```

That is the best compromise between the Gen-CRS tutorial, the music-specific papers, and the fixed-catalog evaluation reality of Music-CRS.

## Sources

- Gen-CRS tutorial page: <https://recsys-lab.at/gen-conv-recsys-tutorial/>
- Gen-CRS tutorial slides: <https://recsys-lab.at/wp-content/uploads/2025/10/Gen-CRS2025_Tutorial.pdf>
- RecSys Challenge 2026 Music-CRS: <https://www.recsyschallenge.com/2026/>
- Music-CRS challenge site: <https://nlp4musa.github.io/music-crs-challenge/>
- TalkPlayData 2: <https://arxiv.org/abs/2509.09685>
- TALKPLAY: <https://arxiv.org/abs/2502.13713>
- MusiCRS: <https://arxiv.org/abs/2509.19469>
- RA-Rec: <https://arxiv.org/abs/2406.00033>
- ReFICR: <https://doi.org/10.1145/3640457.3688146>
- Reindex-Then-Adapt: <https://arxiv.org/abs/2405.12119>
- Large Language Models as Zero-Shot Conversational Recommenders: <https://arxiv.org/abs/2308.10053>
- MemoCRS: <https://arxiv.org/abs/2407.04960>
- RecLLM: <https://arxiv.org/abs/2305.07961>
- iEvaLM: <https://aclanthology.org/2023.emnlp-main.621/>
- EventChat: <https://arxiv.org/abs/2407.04472>
- A Survey on Conversational Recommender Systems: <https://doi.org/10.1145/3453154>
