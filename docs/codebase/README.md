# Music-CRS Codebase Documentation

Music-CRS is the RecSys Challenge 2026 baseline for conversational music recommendation. Given a multi-turn conversation, the system retrieves 20 tracks from a 47k-track catalog and generates a natural-language response. The pipeline transforms session memory into a query understanding state, resolves it against the track catalog through multi-modal retrieval (BM25 + dense ANN) with weighted RRF fusion, and hands the top recommendations to a language-model response generator. This documentation set indexes the per-module references, the end-to-end execution paths, and the verified bug audit.

## Module docs

| Module | Summary |
|---|---|
| [Query Understanding / Compiler](modules/Query Understanding / Compiler.md) | Transforms multi-turn conversation session memory into a top-1000 ranked track_id list via LLM state extraction, entity resolution, multi-modal retrieval (BM25 + dense ANN), weighted RRF fusion, and soft re-ranking. |
| [Retrieval Modules](modules/Retrieval Modules.md) | Pluggable retrieval backends that map a text query to a ranked list of track IDs, with a legacy CRS interface (text_to_item_retrieval) used by the baseline pipeline and a v0+ Retriever Protocol (search/search_embedding) used by the compiler. |
| [Embeddings](modules/Embeddings.md) | Provider-neutral embedding backends (local HF, LiteLLM API, Modal GPU) that encode query strings into dense vectors for ANN retrieval in the v0+ compiler pipeline. |
| [lm_modules](modules/lm_modules.md) | Natural-language response generation layer that wraps local Llama, LiteLLM proxy, and a no-op dummy backend behind a single factory function and a uniform two-method protocol (response_generation / batch_response_generation). |
| [LanceDB indexing + retrieval](modules/LanceDB indexing + retrieval.md) | Builds and queries the LanceDB vector store that serves as the canonical track catalog for v0+ retrieval: index build from HuggingFace datasets with schema-pinned Arrow types and tantivy FTS indexes, plus a CPU-only retriever implementing both a declarative multi-search/RRF path and the typed Retriever Protocol (BM25 FieldQuery + dense ANN) consumed by the v0+ compiler. |
| [Milvus indexing](modules/Milvus indexing.md) | Offline Milvus collection builder and online retrieval class for the 47k-track catalog, providing an alternative vector-store path to LanceDB with combined BM25-sparse and dense ANN hybrid search. |
| [Data layer (catalog, user, corpus formatters)](modules/Data layer (catalog, user, corpus formatters).md) | Provides in-memory read-only access to the HuggingFace track-metadata and user-metadata datasets, and a pluggable text formatter that serializes track fields for BM25/dense indexing and LLM prompt construction. |
| [Pipeline orchestration & services](modules/Pipeline orchestration & services.md) | Wires the QU, retrieval, and LM modules into the end-to-end CRS pipeline and provides offline evaluation, a Modal-compatible retrieval facade, and the Streamlit dashboard entry point. |
| [CLI entrypoints](modules/CLI entrypoints.md) | Outermost CLI layer that parses configs, orchestrates local/Modal inference runs over the HuggingFace test dataset, and persists prediction JSON results for evaluation. |
| [Evaluation & metrics](modules/Evaluation & metrics.md) | Standalone offline scoring harness that computes nDCG@k, Hit@k, MRR, catalog coverage, and Distinct-2 lexical diversity against held-out ground truth, producing a structured score JSON and per-sample CSV for each experiment run. |
| [Modal / Scripts / Infra](modules/Modal / Scripts / Infra.md) | Provisions cloud GPU execution on Modal, manages persistent volumes (HF cache, LanceDB index, results, LiteLLM cache), and provides operational scripts for index building, result merging, artifact download, split creation, and service smoke-testing. |

## Execution

See [code-paths.md](code-paths.md) for the end-to-end execution paths through the system.

## Bugs

See [bugs.md](bugs.md) for the code audit. 9 issues were initially confirmed; after follow-up, **7 are fixed** (issue #70 → PRs #66/#71, plus the `id_to_metadata` refactor), **1 was retracted as a false positive** (#1, ground-truth parser — verified correct against the real dataset), and **1 remains open** (#9, `prepare_submission.sh` hardcoded split).
