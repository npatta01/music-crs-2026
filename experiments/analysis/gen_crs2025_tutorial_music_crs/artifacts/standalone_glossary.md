# Standalone Glossary

This glossary defines the terms used in the Gen-CRS tutorial notes and deck.

## A

### Agentic system

A system where an LLM acts as a controller or planner. It can choose tools, call APIs, use memory, and decide what to do next. This is powerful but can be slower and harder to debug.

### Anchor

A piece of conversation history that should influence future recommendations. A positive anchor is something the user liked. A negative anchor is something the user disliked.

## B

### BM25

A keyword search algorithm. It scores documents by how well their words match the query. In Music-CRS, the documents are track metadata strings such as track name, artist name, album name, and tags.

## C

### Candidate generation

The step that finds a broad pool of possible items. For example, retrieve the top 1,000 tracks that might fit the conversation.

### Catalog

The official set of items the system can recommend. In Music-CRS, this is the fixed track catalog.

### ConversationState

A structured representation of what the user currently wants, based on the whole conversation. It can include liked tracks, rejected tracks, active constraints, and derived retrieval queries.

### CRS

Conversational Recommender System. A recommender system that interacts with the user through dialogue.

## D

### Dense retrieval

Embedding-based retrieval. Text or items are converted into vectors, then the system retrieves items with similar vectors.

### Dev set

A development set used to test system quality before submitting to the official blind test.

## E

### Embedding

A vector representation of text, audio, an image, a user, or a track. Similar things should have similar vectors.

## F

### Fusion

Combining results from multiple retrievers. For example, combine a BM25 list and a dense retrieval list.

## G

### Gen-CRS

Generative Conversational Recommender System. A conversational recommender that uses generative AI, usually an LLM, in some part of the pipeline.

### Grounding

Making sure an LLM response is based on retrieved or known data. For Music-CRS, grounding means recommended track IDs and mentioned facts must come from the catalog.

## H

### Hit@K

Whether the correct item appears in the top K recommendations. `Hit@20` asks: did the correct track appear in the first 20?

### Hybrid retrieval

Combining different retrieval methods, usually sparse keyword retrieval and dense vector retrieval.

## L

### LLM

Large Language Model, such as GPT, Llama, Qwen, Gemma, or Claude.

## M

### MRR

Mean Reciprocal Rank. A ranking metric that rewards placing the correct item early.

### Multimodal

Using multiple kinds of data, such as text, audio, images, and collaborative signals.

## N

### NDCG@K

Normalized Discounted Cumulative Gain at K. A ranking metric that rewards putting the correct item near the top of the list.

## R

### RAG

Retrieval-Augmented Generation. Retrieve relevant data first, then generate an answer using that data.

### Recall@K

Whether the correct item is included somewhere in the top K candidates. With one correct target, Recall@K is similar to Hit@K.

### Reranking

Taking a candidate list and reordering it with additional signals.

### RRF

Reciprocal Rank Fusion. A simple way to combine ranked lists. Items that appear high in multiple lists get stronger scores.

## S

### Sparse retrieval

Keyword-based retrieval. BM25 is a sparse retriever.

### State tracking

Keeping track of the user's preferences, constraints, and prior feedback over multiple conversation turns.
