# Music-CRS System Approach Report — Design Spec

**Date:** 2026-07-14

**Status:** Approved in conversation

**Audience:** Music-CRS competition participants, recommender-system practitioners,
the project team, and future maintainers

**Delivery:** One self-contained HTML report at `docs/approach.html`, published
for review through the report branch and pull request

## 1. Purpose

Create a detailed, approachable explanation of the final submitted Music-CRS
system. The report complements `docs/retrospective.html`: the retrospective
compares leaderboard outcomes and public systems, while this report explains
our own system from conversation to recommendation and response.

The report must answer:

1. What did the final system do, in one minute and in full technical detail?
2. Why did the system use Modal, caching, and staged replay?
3. How did a conversation become structured state?
4. How did state become retriever-specific queries and candidate pools?
5. How did the ranker choose the top track?
6. What did the response model see and what was it allowed to claim?
7. How did the LLM judge affect the competition objective?
8. Where did the pipeline work well across several representative cases?
9. What capability gaps, observed failures, and uncertain boundaries remained?
10. How can another participant inspect or reproduce the implementation?

## 2. Scope and evidence stance

The main subject is the final submitted Blind-B system, not a chronological
history of every experiment. Earlier approaches appear only when needed to
explain a final design choice or a verified failure mode.

Important claims must be grounded in source code, active configs, prompts,
traces, evaluation results, or committed documentation. The report must label
claims as **Verified**, **Inferred**, or **Illustrative** where the distinction
matters. A pedagogical example must never be presented as an observed run.

The report will prefer real devset conversations and saved pipeline traces for
examples. If no trace provides all intermediate artifacts, it may combine a
real conversation with a clearly marked reconstructed walkthrough, provided
every transformation follows the submitted code and config.

The user authorized publishing the report branch and a public HTML preview for
competition-participant review.

## 3. Reader experience

The page follows one vertical reading path at every viewport size. Desktop
layout must not turn the story into multiple competing columns. A technical
stage may briefly fan out to show parallel retrievers, but the branches must
reconverge visibly before the reader continues downward.

The report uses progressive disclosure:

- the visible layer contains the complete narrative and the principal result
  of every stage;
- `details` disclosures contain full prompts, JSON, configs, candidate tables,
  feature inventories, commands, and evidence ledgers;
- a sticky or compact section directory supports navigation without changing
  the vertical narrative;
- every visual has adjacent explanatory prose and a semantic text fallback.

Specialized terms such as BM25, ANN, centroid, reciprocal-rank fusion,
LambdaMART, bi-encoder, nDCG, and LLM judge are defined on first use.

### 3.1 Organizer-first executive summary

The opening must let an organizer understand the submitted system within one
minute without reading the remainder of the report. Before the deep-dive
boundary it contains, in order:

1. the title, one-sentence positioning, and four compact system facts;
2. one complete architecture map covering the serving path and offline
   evaluation loop;
3. one compact, verified example showing the request, meaningful captured
   state, retrieval/ranking outcome, selected track, and response provenance;
4. a clearly labelled transition into the deep technical material.

The architecture map uses a horizontal serving path on wide screens and a
vertical path on narrow screens. Retrieval branches fan out and reconverge
visibly. The offline trace/replay, ranking metrics, and LLM-as-judge response
evaluation form a separate lane so they cannot be confused with online
selection. Local, hosted-API, and Modal execution appear only as small placement
badges; deployment infrastructure is not the map's organizing principle.

The final submitted config uses `ranking.mode: lgbm`; LightGBM determines the
delivered order. The compiler internally assembles the candidate pool using its
configured branch-combination, soft-adjustment, filtering, and backfill logic.
The overview labels this stage **candidate pool assembly**, not “the RRF
ranker.” Internal weighted-RRF mechanics may be documented in the retrieval
deep dive, but must never be presented as the final ordering model.

Decorative hero imagery is removed. The opening spends its visual budget on
accurate, searchable native HTML/CSS system design. The report directory sits
directly below the executive architecture and remains horizontally sticky on
desktop; individual chapters retain vertical stage flow.

## 4. Information architecture

### 4.1 Hero and orientation

- Title: `Inside Our Music-CRS Recommender`
- Subtitle: a plain-language statement that the system turns a multi-turn
  conversation into twenty ranked tracks and one grounded response.
- Four compact facts: 47k-track catalog, 20 returned tracks, structured
  conversation state, and a separately generated top-track explanation or
  another verified final-system quantity.
- A reader map offering a short path and a deep technical path without
  splitting the page into separate experiences.

### 4.2 First-minute system map

A single diagram shows the full online path:

```text
conversation
  -> LLM state extraction
  -> V1-to-V0Plus projection
  -> catalog entity resolution
  -> retriever-specific query compilation
  -> multimodal retrieval mesh
  -> candidate pool assembly
  -> LambdaMART reranking
  -> final artist guard
  -> top-20 recommendations
  -> top-1 response generation
```

The same map contains a separate offline lane:

```text
saved traces and staged replay
  -> ranking metrics and boundary analysis
  -> LLM-as-judge response evaluation
  -> next experiment
```

The overview identifies the contracts passed between stages, expands the typed
state enough to show intent mode, exploration policy, routing, resolved
entities, positive/negative facets, hard constraints, and history treatment,
and makes three invariants visually explicit:

1. retrieval sets the candidate ceiling;
2. LightGBM determines the final ordering in the submitted config;
3. response generation explains rank one and cannot select another track.

### 4.3 One recommendation under the microscope

Use one real, representative conversation as the report's spine. Follow it
through every stage:

1. rendered multi-turn conversation;
2. extracted V1 state;
3. projected compiler-facing state;
4. resolved entity IDs and feedback anchors;
5. compiled BM25 and dense query strings;
6. centroid and lookup inputs;
7. candidate-pool overlap and union;
8. selected reranker features;
9. top-five before/after ranking movement;
10. final top twenty and highlighted top pick;
11. response-model context and final listener-facing response;
12. evaluation interpretation.

The visible layer shows a curated subset. Expandable disclosures preserve the
full state, compiled queries, top-20 table, feature values, trace provenance,
and relevant configuration fragments.

### 4.4 Why the infrastructure looks this way

Explain the practical constraint: the project host did not provide a suitable
local discrete GPU for the original competition workflow. Modal supplied
on-demand GPU execution for expensive model and embedding workloads. Local
caches, file-per-turn state artifacts, and staged replay reduced repeated calls,
cost, and turnaround time.

Infrastructure is a supporting chapter after the system design, not the opening
story. It shows a compact placement map and must not imply that every model call
ran on Modal. Each workload is labelled local, hosted API, or Modal according to
the final config and code.

### 4.5 Understanding the conversation

Explain the state extractor as a fact-first interpreter for the next
recommendation, not a transcript summarizer. Include a meaningful excerpt of
the production prompt covering:

- the next-recommendation boundary;
- request types;
- fact roles and anchor use;
- explicit exclusions and negative style cues;
- played-track feedback and positional references;
- temporal constraints and lyrical themes;
- the rule that compatibility fields are derived later.

Show annotated input/output state cards and explain why the V1 state is
projected onto the V0Plus compiler contract.

### 4.6 Resolving and compiling state

Show how surface names become catalog IDs and how compiler-facing state becomes
different search representations. Explain:

- BM25 field clauses;
- metadata, attribute, lyric, sonic, and visual dense queries;
- anchor-track and user centroids;
- resolved-artist discography and era/popularity lookups;
- played/rejected-track removal;
- release-date masking and soft adjustments;
- popularity backfill.

The diagram may fan out vertically into branch cards, but it must reconverge
into one candidate union before ranking.

### 4.7 Ranking and selection

Explain that retrieval defines the candidates the ranker is allowed to rescue.
Show the final LambdaMART stage and feature families rather than presenting a
raw feature-count contest:

- retriever rank, score, reciprocal-rank, and presence;
- dense and centroid similarity;
- behavioral CF/BPR signals;
- metadata, state, constraint, popularity, and consensus features;
- the fine-tuned bi-encoder `b1_cos` feature;
- candidate-source agreement and coverage.

Use a vertical ranking ladder to show a small set of candidates moving before
and after reranking. End with the top twenty and make clear that response
generation receives the top-ranked recommendation, not permission to select a
different track.

The chapter must distinguish three different concepts:

- compiler candidate-pool assembly, which includes internal branch combination,
  soft adjustments, filtering, and backfill;
- `ranking.mode: lgbm`, the submitted final ordering model;
- the final same-turn artist guard applied to the top twenty.

### 4.8 Response generation

Document the response context and include a meaningful excerpt of
`mcrs/system_prompts/response_generation.txt`. Explain:

- the response model is a track explainer;
- the recommendation system has already selected the track;
- the response should acknowledge the latest request and explain fit;
- it must remain brief, match the listener's language, and avoid unsupported
  claims or metadata dumps;
- the submitted path was a single top-1, single-pass response without a
  separately documented fact checker or independent selector/critic.

Show the structured recommended-track input beside the final natural-language
output, then explain the grounding and reliability boundary.

### 4.9 Evaluation and LLM-as-judge

Explain all challenge metrics and the composite formula. Give the LLM response
judge a dedicated, approachable explanation because it contributes 30% of the
normalized composite. Distinguish:

- retrieval relevance measured by nDCG@20;
- catalog and lexical diversity;
- the challenge's LLM judge of listener-facing response quality;
- any development-time LLM judgments or labels used for analysis/training.

The report must not describe all of these as the same “LLM-as-judge” mechanism.

### 4.10 Example gallery

The gallery remains in the single vertical flow and contains several strong
examples as well as failure cases:

1. **Primary full good trace:** the report's end-to-end spine, where state,
   candidate recall, ranking, and response align.
2. **Strong exact-entity trace:** a named track, album, or artist is grounded
   correctly and reaches an appropriate top pick.
3. **Strong refinement trace:** the system keeps useful qualities from a prior
   track while honoring the user's new constraints.
4. **Strong pivot/new-artist trace:** a liked prior item informs taste without
   becoming an overbearing anchor after the user asks for someone different.
5. **Strong lyrical-theme trace:** lyrics or meaning, rather than generic
   metadata, drives the relevant retrieval branch.
6. **Strong hidden-target trace:** half-remembered constraints persist across
   turns and narrow the search coherently.
7. **Full bad trace:** a verified weak case where the first broken boundary is
   identified and downstream recoverability is explained.
8. **Additional failure traces:** compact examples of distinct state,
   candidate-recall, ranking, or response failures when verified evidence is
   available.

Each compact trace card uses the same grammar:

```text
user signal -> extracted belief -> branches activated -> top pick -> outcome
```

The primary good and bad examples receive full stage-by-stage treatment. The
other five strong examples remain concise but substantive, and link to
expandable state/query/candidate detail. Additional failure examples must not
repeat the same failure boundary merely to increase the example count.

### 4.11 Gap map: where the submitted system remained incomplete

Add an explicit vertical gap map after the example gallery. It compares the
intended capability with the submitted implementation and the available
evidence at each boundary:

```text
reader intent
  -> state understanding gap
  -> entity/constraint grounding gap
  -> candidate coverage gap
  -> ranking/feature gap
  -> response grounding/selection gap
  -> evaluation and model-selection gap
  -> infrastructure/reproducibility gap
```

Each gap card must contain:

- **Expected capability:** what a robust conversational recommender should do;
- **Submitted behavior:** what the final code and config actually did;
- **Evidence:** trace, metric, source file, experiment result, or documented
  absence;
- **User-visible consequence:** how the gap can affect recommendations or prose;
- **Downstream recoverability:** whether later stages could realistically fix it;
- **Status:** Observed failure, Architectural limitation, Measurement gap, or
  Unknown impact.

The gap map must cover at least candidate recall, ranking, and response quality,
plus state extraction or anchoring where supported. It must distinguish “the
system lacks this mechanism” from “this missing mechanism caused the Blind-B
score.” Hidden-set causality remains unknown without labels or counterfactuals.

### 4.12 What worked, what failed, and what remains uncertain

Use three labelled groups:

- **Preserve:** structured state, multimodal candidate generation, explicit
  handoffs, traceability, staged replay, cache-first reproducibility.
- **Fragile or failed:** only evidence-backed issues, including over-anchoring,
  missed candidate recall, ranker boundary failures, in-sample development
  estimates, weak single-pass response generation, or operational complexity.
- **Unknown:** effects that cannot be isolated without hidden per-session labels
  or controlled counterfactuals.

This section synthesizes the example gallery and gap map into a retrospective
engineering assessment, not a roadmap.

### 4.13 Reproduce and inspect

End with a source map linking active configs, prompts, state schema, compiler,
retrievers, ranker, response generation, cache documentation, and reproduction
commands. Include a glossary and an evidence boundary.

### 4.14 Organizer-visible slide order

Although delivered as one responsive HTML document, each major chapter behaves
like a vertically stacked slide with one takeaway and one primary visual:

1. **System in one minute:** complete serving path plus offline learning loop.
2. **One successful turn:** conversation through response in one vertical trace.
3. **Conversation state:** prompt intent and the typed state contract.
4. **Resolution and compilation:** entity roles, constraints, gates, and queries.
5. **Retrieval mesh:** specialist branches, fired/skipped status, and inputs.
6. **Candidate pool assembly:** deduplication, filtering, soft adjustment, and
   backfill before learned ranking.
7. **Learned ranking:** feature families, `b1_cos`, LambdaMART, artist guard,
   and final top twenty.
8. **Response handoff:** top-one context, prompt excerpt, and generated prose.
9. **Compute design:** local/API/Modal placement and cache/replay rationale.
10. **Evaluation:** ranking metrics versus LLM-as-judge response evaluation.
11. **Good examples:** several verified request classes using a common grammar.
12. **Failure anatomy:** first broken boundary and downstream recoverability.
13. **Gaps and limitations:** observed, architectural, measurement, and unknown.
14. **Lessons:** preserve, change, and validate next.
15. **Reproduction appendix:** source map, commands, glossary, and evidence ledger.

The sticky horizontal directory exposes these major chapters. The document
itself remains vertical, and every technical diagram collapses into a vertical
reading order on mobile. Progressive disclosure keeps prompts, full JSON,
feature inventories, and audit tables available without forcing organizers to
read them.

## 5. Visual design

The page matches the established retrospective's editorial report language:
warm neutral background, dark ink, restrained accent colors, generous spacing,
compact metric cards, semantic tables, evidence badges, and expandable audit
detail. It is not a pixel clone; it is a sibling report.

Decorative bitmap illustrations are removed from the visible report. The
organizer-facing visual budget is reserved for accurate system diagrams,
verified examples, and compact evidence summaries.

Technical visuals remain native HTML/CSS/SVG-like markup so text stays accurate,
searchable, responsive, and accessible:

- first-minute serving-path and offline-loop architecture map;
- local/API/Modal compute map;
- annotated state transformation;
- branch fan-out and reconvergence;
- candidate funnel and overlap;
- before/after ranking ladder;
- top-20 recommendation stack;
- response grounding boundary;
- evaluation formula and metric contribution diagram;
- good/bad boundary comparison;
- vertical capability-gap map with evidence and recoverability labels.

No diagram may depend on color alone. Every diagram must retain reading order
and a usable semantic fallback at narrow widths.

## 6. Interaction and accessibility

- One vertical document; no horizontal scrolling at ordinary mobile widths.
- A compact sticky table of contents that collapses on small screens.
- Native `details`/`summary` for disclosures.
- Keyboard-visible focus styles.
- Sufficient contrast and reduced-motion support.
- Alt text for any informative images retained outside the native diagrams.
- Tables use captions and proper headers; wide audit tables receive contained
  scrolling without making the page itself scroll horizontally.
- Print styles preserve the visible story and identify collapsed audit sections.
- The report remains useful with JavaScript disabled; JavaScript may enhance
  navigation or disclosures but may not carry core content.

## 7. Content sourcing

Primary sources include:

- `configs/state_ranker_v10_lgbm_blindset_B.yaml`;
- `docs/architectures/v0plus_retrieval.md`;
- `docs/architectures/session_state.md`;
- `docs/architectures/biencoder.md`;
- `docs/architectures/explanation_generation.md`;
- `docs/state_extraction_cache.md`;
- `mcrs/conversation_state/schema.py`;
- `mcrs/conversation_state/prompts/current.py`;
- `mcrs/qu_modules/compiler.py` and supporting ranker/compiler modules;
- `mcrs/qu_modules/lgbm_reranker.py`;
- `mcrs/system_prompts/response_generation.txt`;
- active model metadata and saved experiment traces;
- official challenge scoring documentation and results where metrics are
  discussed.

Prompt excerpts will be long enough to explain behavior but shorter than the
full prompt in the visible layer. The complete local prompt may appear in an
expandable source disclosure when useful.

## 8. Implementation contract

- Deliver one self-contained `docs/approach.html` with embedded CSS, scripts,
  and image data or otherwise self-contained image assets.
- Do not introduce a runtime build requirement for readers.
- Do not publish or deploy the report.
- Preserve unrelated worktree changes and untracked reproduction artifacts.
- Validate internal anchors, absence of external runtime dependencies, semantic
  structure, mobile layout, and representative desktop/mobile screenshots.
- Verify every example label and important technical claim against its cited
  source or trace before completion.

## 9. Success criteria

The report is successful when a competition participant can:

1. understand the complete submitted serving path and evaluation loop in roughly
   one minute from the overview;
2. follow a complete recommendation vertically without opening disclosures;
3. inspect meaningful prompt, state, query, ranking, and response details;
4. understand that LightGBM, not the compiler's internal candidate-assembly
   order, determines the final submitted ranking;
5. understand why and where Modal was used without mistaking deployment for the
   system architecture;
6. distinguish the challenge LLM judge from development-time LLM judgments;
7. inspect several strong examples spanning distinct conversational intents;
8. compare strong and weak traces at the first failing boundary;
9. distinguish observed failures from architectural, measurement, and unknown
   gaps;
10. reproduce or inspect the implementation from linked local sources;
11. read the report comfortably on a phone or laptop.
