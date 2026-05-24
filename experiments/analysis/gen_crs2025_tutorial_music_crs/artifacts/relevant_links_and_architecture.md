# Relevant Links and Architectures

This source pack is standalone. It defines the links and architecture ideas used in the notes, HTML brief, and presentation deck.

## Primary Links

- Gen-CRS 2025 tutorial page: <https://recsys-lab.at/gen-conv-recsys-tutorial/>
- Gen-CRS 2025 tutorial PDF: <https://recsys-lab.at/wp-content/uploads/2025/10/Gen-CRS2025_Tutorial.pdf>
- Music-CRS Challenge 2026: <https://nlp4musa.github.io/music-crs-challenge/>
- Challenge dataset: <https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Dataset>
- Track metadata: <https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Track-Metadata>
- User metadata: <https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-User-Metadata>
- Track embeddings: <https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Track-Embeddings>
- User embeddings: <https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-User-Embeddings>

## Paper Links From Useful Tutorial Sections

| Paper | Link | Why it matters here |
|---|---|---|
| Large Language Models as Zero-Shot Conversational Recommenders | <https://doi.org/10.1145/3583780.3614949> | Useful warning that LLMs have content knowledge but can struggle with collaborative knowledge, popularity bias, and dataset alignment. |
| Reindex-Then-Adapt | <https://doi.org/10.1145/3701551.3703573> | Useful warning about item-set control and distribution mismatch when LLMs directly generate recommendations. |
| Unleashing the Retrieval Potential of LLMs in CRS | <https://doi.org/10.1145/3640457.3688146> | Relevant to conversation-aware retrieval and retrieve-then-rerank systems. |
| Retrieval-Augmented CRS with Prompt-based Semi-Structured Natural Language State Tracking | <https://doi.org/10.1145/3626772.3657670> | Closest tutorial reference for `ConversationState -> retrieval views -> grounded response`. |
| MemoCRS | <https://doi.org/10.1145/3627673.3679599> | Relevant to memory-enhanced user modeling and using LLMs to generate user representations. |
| EventChat | <https://doi.org/10.48550/arXiv.2407.04472> | Relevant to tool/RAG systems and latency/cost concerns in real deployments. |
| CoRE-CoG | <https://doi.org/10.48550/arXiv.2311.08511> | Relevant to constrained generation for recommendation entities. |
| MMCRec | <https://doi.org/10.1007/978-3-031-56063-7_23> | Relevant to multimodal generative AI in conversational recommendation. |

## Architecture 1: Unified Gen-CRS

```text
conversation
  -> one LLM
  -> recommended item list and response
```

What it means:

The language model reads the conversation and directly generates recommendations and text.

Why the tutorial discusses it:

It is simple and can produce fluent responses. It shows how much recommendation ability pretrained LLMs already have.

Why it is risky for Music-CRS:

- The LLM may recommend items outside the official catalog.
- It may prefer globally popular music rather than the competition target.
- It may fail to use collaborative or embedding signals.
- It hides the failure source because understanding, retrieval, ranking, and response are mixed together.

Use in this repo:

Not the primary path. Only use as a small comparison or as inspiration for query/state generation.

## Architecture 2: Modular Gen-CRS

```text
conversation
  -> query understanding or state tracking
  -> retrieval module
  -> reranking module
  -> response generator
```

What it means:

The system is split into specialized parts. The LLM may help with state and language, while retrieval and ranking stay grounded in known catalog data.

Why it fits Music-CRS:

- The output must be valid track IDs.
- The catalog is fixed.
- The challenge provides track metadata, user metadata, and embeddings.
- We need to debug score changes stage by stage.

Recommended version:

```text
conversation history
  -> ConversationState
  -> sparse_query_view and dense_query_view
  -> sparse retrieval + dense retrieval + user/item signals
  -> RRF/fusion/reranking
  -> top 20 valid track IDs
  -> grounded response
```

## Architecture 3: Agentic Gen-CRS

```text
conversation
  -> LLM planner
  -> tool selection
  -> retrieval/search/database calls
  -> memory update
  -> response
```

What it means:

An LLM orchestrates tools and decides which subtask to do next.

Why it is useful:

- Can be flexible.
- Can decompose tasks.
- Can call different tools depending on the conversation.

Why it is not the next best competition move:

- Higher latency.
- More prompt failures.
- Harder reproducibility.
- Harder ablation.

Use later if:

The modular retrieval/reranking system has hit a ceiling and we can isolate a specific tool-selection problem.

## Architecture 4: Semi-Structured State Tracking + RAG

```text
dialogue history
  -> semi-structured state dictionary
  -> generated retrieval views
  -> grounded item retrieval
  -> contextualized response
```

Beginner explanation:

The LLM turns the messy conversation into a structured note card. Retrieval uses the note card. The response generator is only allowed to talk about retrieved items.

Example state:

```yaml
intent_mode: find_more_like_this
positive_anchors:
  tracks: ["previous recommendation user liked"]
negative_anchors:
  tags: ["too slow"]
active_constraints:
  mood: ["uplifting"]
  genre: ["indie pop"]
sparse_query_view: "indie pop uplifting previous artist"
dense_query_view: "upbeat indie pop track similar to the liked recommendation but less slow"
```

Why it matters:

A flat query can lose what the user rejected or what earlier item "this" refers to. A state object keeps those pieces separate.

## Architecture 5: Hybrid Retrieve-and-Rerank

```text
ConversationState
  -> sparse retriever
  -> dense retriever
  -> user/item embedding signals
  -> union pool
  -> RRF / feature-aware reranker
  -> top 20 track IDs
```

Beginner explanation:

Use several search methods, combine their candidate lists, then reorder the combined list. This helps because exact names and fuzzy moods require different tools.

Why it matters:

- Sparse retrieval catches exact names and tags.
- Dense retrieval catches semantic similarity and mood.
- User/item embeddings add personalization and collaborative information.
- Fusion gives a cheap first pass before more expensive reranking.

## Architecture 6: Evaluation Split

```text
final result
  = state quality
  + candidate generation ceiling
  + reranking quality
  + response grounding
  + late-turn robustness
```

Beginner explanation:

If the final score changes, we need to know why. Did the system understand the conversation better? Did it retrieve the right track somewhere in the top 1,000? Did reranking move it into the top 20? Did the response stay faithful to the selected track?

Recommended artifacts:

- `state_audit.jsonl`
- `candidate_pool_metrics.json`
- `fusion_ablation.json`
- `response_grounding_audit.jsonl`
- per-turn metrics for turns 1 through 8
