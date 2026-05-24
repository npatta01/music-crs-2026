# Gen-CRS 2025 Tutorial Takeaways for Music-CRS

Status: `analyzed + expanded literature review`

Audience: someone who does not already know conversational recommender systems.

Source: [Gen-CRS2025 tutorial PDF](https://recsys-lab.at/wp-content/uploads/2025/10/Gen-CRS2025_Tutorial.pdf) from the [tutorial page](https://recsys-lab.at/gen-conv-recsys-tutorial/).

Purpose: explain, in standalone form, what parts of the Gen-CRS tutorial are useful for the RecSys Challenge 2026 Music-CRS competition, what the main architecture ideas mean, which links matter, and what experiment we should build next.

## Detailed Literature Review

For the competition-focused paper review, use:

- [literature_review.html](literature_review.html)
- [artifacts/detailed_literature_review.md](artifacts/detailed_literature_review.md)

The HTML page is the easiest version to read in the browser. The Markdown file is the editable source. The review goes paper by paper and explains:

- what each source is saying
- why it matters for Music-CRS
- what to steal now
- what to defer
- what experiments each paper implies
- how the literature translates into a cleaner architecture for this repo

## Plain-English Summary

A recommender system chooses items for a user. Spotify recommending songs, Netflix recommending movies, and Amazon recommending products are all recommender systems.

A conversational recommender system, abbreviated `CRS`, does that through a conversation. Instead of only receiving one search query, it sees multiple turns like:

```text
User: I want something chill, maybe electronic.
Assistant: Try this ambient track.
Music: <track id that was recommended>
User: Nice, but can you make it a little warmer and more acoustic?
```

The system has to understand not only the latest user message, but also what happened earlier: what was suggested, what the user accepted, what the user rejected, and what preferences are still active.

The Music-CRS competition asks us to build exactly this kind of system for music. Given a multi-turn conversation, the system must:

1. Recommend 20 tracks from a fixed catalog of about 47,000 tracks.
2. Generate a natural language response to the user.
3. Use the provided conversation, user data, track metadata, and embeddings.

The Gen-CRS tutorial is useful because it explains the modern design space for these systems. Its strongest message for this competition is:

> Do not let an LLM freely invent recommendations. Use the LLM to understand the conversation, but keep recommendation grounded in the catalog through retrieval and reranking.

## What Problem Are We Solving?

The competition is not simple search. A simple search problem might be:

```text
Query: "Beatles songs"
Return: Beatles tracks
```

Music-CRS is harder because the target track may depend on the whole conversation:

```text
Turn 1: I like moody 90s rock.
Turn 2: That was too heavy.
Turn 3: More like the second song, but less gloomy.
Turn 4: Something with a female vocalist would be nice.
```

The final turn cannot be understood by itself. "More like the second song" requires the system to remember the earlier recommendation. "Too heavy" is a negative constraint. "Female vocalist" is an active constraint. A good system needs a structured memory of the conversation.

This is why the key architecture recommendation is:

```text
conversation history
  -> structured conversation state
  -> sparse and dense retrieval queries
  -> hybrid candidate pool
  -> reranking
  -> grounded natural language response
```

## Important Terms

### Recommender system

A system that chooses items for a user. Items can be songs, movies, products, restaurants, news articles, or courses.

### RecSys

Short for recommender systems. The competition is part of the RecSys community.

### CRS

Conversational Recommender System. A recommender that works through a multi-turn conversation.

### Gen-CRS

Generative Conversational Recommender System. A CRS that uses generative AI, usually a large language model, for some part of the system: understanding the user, generating responses, planning tool calls, or reranking candidates.

### LLM

Large Language Model. Examples include GPT, Llama, Qwen, Gemma, and Claude. An LLM is good at language and reasoning, but it is not automatically good at selecting valid items from a fixed music catalog.

### Grounding

Grounding means forcing the system to base its recommendations and response on real data it has retrieved, not on whatever the LLM can imagine. For Music-CRS, grounding means recommended track IDs must come from the official catalog.

### Retrieval

Retrieval is the step that finds candidate tracks from the catalog. A retriever might return 1,000 possible tracks, and a later step chooses the final 20.

### Reranking

Reranking takes a candidate list and reorders it using extra signals. For example, a reranker might combine text relevance, user preference, track popularity, and audio similarity.

### BM25

A classic keyword-based search method. It is strong when the conversation mentions exact artist names, track names, album names, or tags.

### Dense retrieval

Dense retrieval uses vector embeddings. It is strong when the user says semantic things like "dreamy", "late-night drive", "melancholic but not sad", or "sounds like the previous song".

### Hybrid retrieval

Hybrid retrieval combines multiple retrieval methods, usually keyword retrieval plus dense/vector retrieval. This is useful because music conversations contain both exact entities and fuzzy mood/style descriptions.

### RAG

Retrieval-Augmented Generation. The system retrieves relevant data first, then asks the LLM to generate an answer using that retrieved evidence.

### NDCG, Hit, Recall, MRR

These are ranking metrics. In plain English:

- `Hit@20`: did the correct track appear in the top 20?
- `Recall@1000`: did the correct track appear anywhere in the top 1,000 candidate pool?
- `NDCG@20`: did the correct track appear high in the top 20, with higher positions rewarded more?
- `MRR`: how early did the first correct result appear?

The exact formulas matter less than the diagnosis: `Hit@1000` tells us whether candidate generation found the answer at all; `NDCG@20` tells us whether final ranking put it near the top.

## What The Tutorial Says That Matters

The tutorial organizes Gen-CRS systems into three architecture families.

### 1. Unified Gen-CRS

In a unified system, one LLM tries to do everything:

```text
conversation -> LLM -> recommendation list and response
```

Why it is attractive:

- Simple pipeline.
- Natural language output is easy.
- The model can reason over the conversation.

Why it is risky for this competition:

- The LLM may recommend songs that are not in the 47,000-track catalog.
- It may prefer popular songs because they are common in pretraining data.
- It may not use collaborative or embedding signals well.
- It is hard to debug whether failure came from understanding, retrieval, ranking, or response generation.

Use this idea only as inspiration, not as the main implementation.

### 2. Modular Gen-CRS

In a modular system, different components do different jobs:

```text
conversation
  -> state tracker or query-understanding module
  -> retrieval module
  -> reranking module
  -> response-generation module
```

Why it is the best fit:

- Retrieval remains grounded in the official catalog.
- We can use specialized tools for keyword search, embeddings, user vectors, and audio features.
- Each stage can be evaluated separately.
- We can inspect why a run got better or worse.

This is the architecture the tutorial most strongly supports for Music-CRS.

### 3. Agentic Gen-CRS

In an agentic system, an LLM acts like a controller:

```text
conversation -> LLM planner -> tool calls -> memory updates -> response
```

Why it is interesting:

- The model can choose tools dynamically.
- It can plan multiple steps.
- It can use memory and feedback.

Why it is not the next best sprint:

- More latency.
- More prompt and tool-call failure modes.
- Harder to reproduce.
- More difficult to compare fairly against simpler baselines.

This can be explored later, but the next competition improvement should be simpler and more traceable.

## The Architecture We Should Build Toward

### Step 1: ConversationState

The first important object is a structured summary of the conversation.

Instead of passing the entire conversation as one flat string, create a state object like:

```yaml
intent_mode: refinement
positive_anchors:
  tracks: ["track id from turn 2"]
  artists: ["artist name user liked"]
  tags: ["ambient", "warm"]
negative_anchors:
  tags: ["too heavy", "too gloomy"]
active_constraints:
  mood: ["chill", "warm"]
  instrumentation: ["more acoustic"]
  vocal: ["female vocalist"]
history_carryover:
  still_relevant: ["second recommendation"]
  no_longer_relevant: ["first recommendation"]
sparse_query_view: "artist track ambient warm acoustic female vocalist"
dense_query_view: "warm chill acoustic electronic song with female vocals similar to the accepted second recommendation"
response_evidence_view:
  allowed_track_facts: ["track name", "artist", "album", "tags"]
```

Why this helps:

- Positive anchors preserve examples the user liked.
- Negative anchors prevent repeating bad suggestions.
- Active constraints preserve what the user currently wants.
- Separate sparse and dense views let different retrievers do what they are good at.
- Response evidence prevents the LLM from hallucinating track details.

Tutorial connection: this maps to the semi-structured state tracking and RAG material around the state-tracking slides.

### Step 2: Sparse retrieval

Sparse retrieval means keyword-style retrieval. In this repo, the useful sparse baseline is BM25 over track metadata and tags.

Good for:

- exact artist names
- exact track names
- album names
- genre or mood tags
- lexical constraints like "90s", "piano", "ambient"

Weak for:

- fuzzy similarity
- "more like this"
- mood descriptions that do not use catalog words

### Step 3: Dense retrieval

Dense retrieval means embedding-based retrieval. Text is converted into vectors, and similar vectors are retrieved.

Good for:

- mood and style
- semantic similarity
- "sounds like the previous song"
- lyrics/story requests
- vague preference language

Weak for:

- exact entity matching when the model does not preserve the entity
- rare names
- constraints that require strict filtering

### Step 4: Hybrid candidate generation

Because sparse and dense retrieval are good at different things, combine them.

The current local evidence already supports this:

| Run | What it does | NDCG@20 | Hit@1000 |
|---|---|---:|---:|
| `bm25_devset_retrieval_only_with_tag_list` | sparse retrieval | `0.0970` | `0.6311` |
| `dense_qwen3_embedding_8b_devset` | dense retrieval | `0.1025` | `0.6934` |
| offline RRF hybrid | sparse + dense fusion | `0.1072` | `0.7210` |

The important number is not only `NDCG@20`. The hybrid also improves `Hit@1000`, which means the correct answer appears somewhere in the candidate pool more often. A reranker cannot recover a track that candidate generation never found.

### Step 5: Fusion and reranking

Fusion combines multiple ranked lists. The simplest useful method is `RRF`, reciprocal rank fusion.

Plain English RRF:

- If a track appears near the top of several lists, it gets a strong score.
- If it appears in only one list, it can still survive if it ranks highly there.
- It does not require training data.

After RRF, add a feature-aware reranker:

- sparse rank
- dense rank
- user-track similarity
- collaborative filtering score
- audio similarity
- lyrics/metadata embedding score
- popularity
- penalties for rejected artists/tags/tracks

This is safer than jumping straight to an LLM reranker because it is cheaper, more reproducible, and easier to ablate.

### Step 6: Grounded response generation

The final response can be generated by an LLM, but it should only see:

- the user conversation
- the selected top track or top few tracks
- known catalog metadata
- maybe the state summary

It should not invent song facts or recommend extra tracks outside the selected candidate list.

## Why The Current Repo Evidence Points Here

The current experiment history already says the hard part is conversation state plus hybrid retrieval.

### Query-intent analysis

A previous analysis labeled the dev-set conversations and found:

- most sessions are iterative refinement or transition/pivot, not one-shot lookup
- almost all sessions depend on both prior user turns and prior assistant/music turns
- the most common evidence need is hybrid retrieval
- long-range callbacks and hidden targets are common failure risks

Plain meaning: the system must remember what happened earlier and use both exact metadata and semantic similarity.

### Retrieval experiments

The strongest sparse system and the strongest dense system find partly different correct tracks. This means they are complementary.

Useful local finding:

```text
Both sparse and dense find the answer: 55.0%
Dense-only finds the answer:          14.3%
Sparse-only finds the answer:          8.1%
Both miss:                            22.6%
```

Plain meaning: neither retriever dominates. A hybrid system can recover tracks that either system alone misses.

### Rewrite experiments

LLM query rewriting improved head ranking in some runs, but sometimes reduced deep candidate coverage.

Plain meaning: a good-looking rewrite can make the top 20 better while losing many candidates deeper in the pool. This is why a single rewritten string should not replace structured state and branch-level retrieval.

## Detailed Source Links

Primary source links:

- Tutorial page: <https://recsys-lab.at/gen-conv-recsys-tutorial/>
- Tutorial PDF: <https://recsys-lab.at/wp-content/uploads/2025/10/Gen-CRS2025_Tutorial.pdf>
- Music-CRS challenge: <https://nlp4musa.github.io/music-crs-challenge/>

Tutorial references most relevant to this repo:

- Large Language Models as Zero-Shot Conversational Recommenders, CIKM 2023: <https://doi.org/10.1145/3583780.3614949>
- Reindex-Then-Adapt: Improving Large Language Models for Conversational Recommendation, WSDM 2025: <https://doi.org/10.1145/3701551.3703573>
- Unleashing the Retrieval Potential of Large Language Models in Conversational Recommender Systems, RecSys 2024: <https://doi.org/10.1145/3640457.3688146>
- Retrieval-Augmented Conversational Recommendation with Prompt-based Semi-Structured Natural Language State Tracking, SIGIR 2024: <https://doi.org/10.1145/3626772.3657670>
- MemoCRS: Memory-enhanced Sequential Conversational Recommender Systems with Large Language Models, CIKM 2024: <https://doi.org/10.1145/3627673.3679599>
- EventChat: LLM-driven conversational recommender system for leisure events, arXiv 2024: <https://doi.org/10.48550/arXiv.2407.04472>
- CoRE-CoG: Conversational Recommendation of Entities using Constrained Generation, arXiv 2023: <https://doi.org/10.48550/arXiv.2311.08511>
- MMCRec: Multi-modal Generative AI in Conversational Recommendation, ECIR 2024: <https://doi.org/10.1007/978-3-031-56063-7_23>

## What To Ignore For Now

These ideas are interesting, but they are not the best next competition move:

- Pure direct ID generation by an LLM.
- Free-form item-title generation.
- Large full fine-tuning projects before exhausting retrieval and fusion.
- Fully agentic multi-agent orchestration as the main recommender path.
- Human-subject evaluation.
- LLM-as-judge as a replacement for NDCG, Hit, Recall, or MRR.

Why: they add complexity before fixing the basic candidate generation and state tracking problem.

## Proposed Next Experiment

Build and evaluate:

```text
ConversationState
  -> sparse_query_view
  -> dense_query_view
  -> BM25/LanceDB FTS + Qwen dense retrieval
  -> RRF union pool
  -> feature-aware reranker using user/track embeddings and popularity
  -> grounded top-20 response generation
```

Minimal first slice:

1. Implement a stateless `ConversationState` extractor that recomputes from session history.
2. Derive `sparse_query_view` and `dense_query_view`.
3. Run sparse and dense retrieval at `topk=1000`.
4. Fuse with RRF and compare against existing sparse, dense, rewrite, and offline RRF baselines.
5. Add feature-aware reranking only after confirming the union pool improves `Hit@1000`.

Success criteria:

- improve `NDCG@10` and `NDCG@20`
- improve or preserve `Hit@1000`
- improve late-turn metrics without sacrificing turn 1
- produce trace files that explain whether the change helped state extraction, candidate generation, reranking, or response grounding

## Deliverables

- [HTML brief](index.html)
- [Presentation deck](artifacts/gen_crs2025_music_crs_takeaways.pptx)
- [Source digest for rebuild](artifacts/source_digest_for_rebuild.md)
- [Standalone slide notes](artifacts/standalone_slide_notes.md)
- [Source and architecture notes](artifacts/relevant_links_and_architecture.md)
- [Standalone glossary](artifacts/standalone_glossary.md)
