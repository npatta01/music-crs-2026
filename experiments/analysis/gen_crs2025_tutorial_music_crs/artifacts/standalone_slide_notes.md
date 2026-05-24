# Standalone Slide Notes: Gen-CRS Tutorial -> Music-CRS

These notes explain the presentation deck for a reader who does not already know conversational recommender systems.

Primary sources:

- Gen-CRS tutorial page: <https://recsys-lab.at/gen-conv-recsys-tutorial/>
- Gen-CRS 2025 tutorial PDF: <https://recsys-lab.at/wp-content/uploads/2025/10/Gen-CRS2025_Tutorial.pdf>
- Music-CRS challenge: <https://nlp4musa.github.io/music-crs-challenge/>

## One-Page Takeaway

The Music-CRS competition is a catalog-grounded conversational recommendation task. The system receives a multi-turn music conversation and must output 20 track IDs from a fixed catalog, plus a natural-language response.

The Gen-CRS tutorial is useful because it organizes modern conversational recommendation systems into patterns:

1. Unified LLM systems, where one model does most of the work.
2. Modular systems, where state tracking, retrieval, ranking, and response generation are separate.
3. Agentic systems, where an LLM plans and calls tools.

For this competition, the safest high-value path is the modular pattern:

```text
conversation
  -> ConversationState
  -> sparse retrieval view + dense retrieval view
  -> hybrid candidate pool
  -> fusion and reranking
  -> grounded natural-language response
```

The reason is simple: an LLM can understand language, but it can also invent plausible tracks. The competition requires valid catalog IDs. Therefore, recommendation should be grounded in retrieval and ranking over the official catalog.

## Slide Notes

### Slide 1: What is useful for this competition?

The deck's thesis is that the tutorial is most useful as architecture guidance, not as a direct recipe to let an LLM generate recommendations freely. Music-CRS needs valid track IDs, so the system should move from conversation to structured state, then to catalog retrieval, ranking, and grounded response writing.

Use this slide to introduce the core pipeline:

- Conversation: the full history of user and assistant turns.
- State: a structured memory of what the user wants.
- Hybrid retrieval: search the catalog with both exact matching and semantic matching.
- Grounded output: submit 20 catalog track IDs and generate a response from known metadata.

### Slide 2: A recommender system chooses items for a user

A recommender system ranks items from a catalog. The user evidence can be clicks, listening history, ratings, profile features, or conversation text. The catalog is the allowed item universe. The ranking model scores candidate items, and the output is an ordered recommendation list.

For Music-CRS, this matters because the catalog boundary is strict. A musically plausible answer is not enough if it points to a track that is not in the official catalog.

### Slide 3: A CRS is a recommender that remembers a conversation

CRS means Conversational Recommender System. The hard part is that later turns depend on earlier turns. A sentence like "more like the second one, but less sleepy" cannot be interpreted without knowing which track was second and what "sleepy" refers to.

The system needs to track:

- What the user liked.
- What the user rejected.
- Which previous recommendations became anchors.
- Which constraints are still active.
- Which constraints were changed or relaxed.

### Slide 4: Music-CRS asks for 20 track IDs plus a grounded response

This slide frames the competition mechanics. The input is a music conversation. The output is a list of 20 track IDs and a response. The ranking metrics reward placing the hidden target track high in the 20-track list.

The LLM can help interpret the conversation and write the answer, but the track IDs should come from catalog retrieval. Treat retrieval quality as the main scoring surface.

### Slide 5: Multi-turn music recommendation needs explicit state

The recommended design is to extract a ConversationState object before retrieval. A single rewritten query can accidentally drop important information. Structured state keeps the important parts separate and inspectable.

Useful state fields include:

- Intent: lookup, refinement, pivot, continuation, or constraint change.
- Positive anchors: liked tracks, accepted recommendations, artists, genres, tags.
- Negative anchors: rejected tracks, banned artists, disliked moods.
- Constraints: era, language, energy, acousticness, vocal style, mood.
- Sparse query view: exact words and metadata terms for keyword retrieval.
- Dense query view: semantic description for embedding retrieval.
- Evidence pointers: which conversation turn produced each state field.

### Slide 6: The Gen-CRS tutorial gives three system families

The tutorial's architecture taxonomy is useful:

- Unified LLM: one model reads the conversation and generates recommendations. This is fast to prototype but risky for catalog validity.
- Modular pipeline: separate state, retrieval, ranking, and response components. This is the best fit for Music-CRS because each stage can be evaluated.
- Agentic system: a planner calls tools and decides what to do next. This can be powerful but adds latency and debugging complexity.

The recommended path is modular first, agentic later only if traces prove that planning is needed.

### Slide 7: Pure LLM recommendation is risky for catalog-grounded scoring

Pure LLM recommendation has three risks:

1. Hallucination: the model recommends plausible songs that are not valid catalog rows.
2. Weak recall: the model does not search broadly enough, so the target never enters the candidate list.
3. Poor ablation: a single prompt makes it hard to tell which part failed.

The safer pattern is Retrieval-Augmented Generation (RAG): retrieve evidence first, then generate an answer from that evidence.

### Slide 8: A modular grounded Gen-CRS maps cleanly to the repo

This is the implementation architecture slide. It maps the tutorial to a Music-CRS pipeline:

1. Conversation input.
2. State tracker.
3. Hybrid retrieval.
4. Fusion and reranking.
5. Response generator.

The benefit is debugging. If a run fails, we can ask:

- Did state tracking capture the right request?
- Did retrieval include the target in top 1000?
- Did reranking move the target into top 20?
- Did the response describe selected catalog tracks only?

### Slide 9: ConversationState is the reusable contract

ConversationState should be the shared object that modules consume. It should not be an opaque prompt. It should contain explicit fields that can be logged, tested, and ablated.

The example on the slide shows why this matters. The user says "more like the second one, but less sleepy." A good state object turns that into:

- Anchor: previous second recommendation.
- Keep: warm/chill/electronic/female vocal, if supported by prior turns.
- Change: raise energy.
- Avoid: sleepy or too ambient.
- Sparse query view: exact tags and terms.
- Dense query view: semantic description for embedding search.

### Slide 10: Sparse and dense retrieval solve different problems

Sparse retrieval means keyword or lexical retrieval, such as BM25 or full-text search. It is strong for exact names, tags, and constraints.

Dense retrieval means vector search with embeddings. It is strong for meaning, mood, vibe, and similarity.

Music conversations need both. A user might mention an exact artist and also say "same late-night feeling but brighter." One branch should preserve exact words; the other should represent fuzzy taste.

### Slide 11: Local runs already support hybrid retrieval

The current local evidence supports combining sparse and dense retrieval:

- BM25 + tags: NDCG@20 0.0970, Hit@1000 0.6311.
- Qwen dense: NDCG@20 0.1025, Hit@1000 0.6934.
- Offline RRF hybrid: NDCG@20 0.1072, Hit@1000 0.7210.

The key diagnostic is Hit@1000. If the correct track is missing from the candidate pool, the reranker cannot recover it. Hybrid retrieval improves the odds that the correct item is available for later ranking.

### Slide 12: The challenge data already contains a knowledge foundation

The challenge data should be treated as the system's knowledge base:

- Track metadata supports sparse search and response grounding.
- Conversation data supports state tracking.
- Embeddings support dense retrieval.
- Optional legal signals can support reranking, such as collaborative patterns, audio descriptors, lyrics, popularity, or multimodal fields.

The state object should decide which fields each branch uses.

### Slide 13: Measure each stage, not only the final score

The final leaderboard score is not enough for development. The pipeline needs stage-level metrics:

- State quality: did the system capture the right active constraints?
- Candidate recall: did the target appear in top 1000?
- Top-20 ranking: did the reranker place the target in the submitted list?
- Response grounding: did the text describe the selected catalog evidence?

Trace fields should include state JSON, sparse query, dense query, branch ranks, fused ranks, reranker features, rejected evidence, final IDs, and response evidence.

### Slide 14: Build state-to-hybrid retrieval with traces

The next experiment should be a state-to-hybrid retrieval run:

1. Parse ConversationState for each session.
2. Derive sparse and dense retrieval views.
3. Run sparse and dense topk=1000 retrieval.
4. Fuse with Reciprocal Rank Fusion (RRF).
5. Rerank and generate a grounded response.
6. Compare against BM25, dense, rewrite-only, and offline RRF baselines.

Success means improving candidate recall without losing top-20 ranking and producing traces that explain what changed.

### Slide 15: Relevant links and papers to keep close

Use the source pack as a map:

- The tutorial page and PDF provide architecture vocabulary.
- The Music-CRS challenge page defines the actual task boundary.
- The paper links provide targeted ideas for state tracking, retrieval, memory, and multimodal recommendation.

The rule of thumb is to let the tutorial inspire architecture, then let local metrics decide what stays.

## Implementation Checklist

For a first implementation pass, prioritize:

1. Define a minimal ConversationState schema.
2. Add state extraction with source-turn evidence.
3. Produce separate sparse and dense query views.
4. Run branch retrieval at topk=1000.
5. Fuse with RRF.
6. Log trace files that preserve state, queries, branch ranks, and final ranking.
7. Compare NDCG@20 and Hit@1000 against existing BM25, dense, rewrite-only, and offline RRF baselines.
8. Only add a heavier reranker after the candidate pool improves.

## Common Mistakes To Avoid

- Letting an LLM invent track IDs.
- Collapsing the whole conversation into one rewrite string.
- Optimizing NDCG@20 while losing Hit@1000.
- Judging only final predictions without reading traces.
- Mixing response quality with retrieval quality.
- Adding an agent loop before a modular traceable baseline exists.
