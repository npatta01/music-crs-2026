# Blind-B Retrospective Report — Revised Design Spec

**Original date:** 2026-07-12

**Revised:** 2026-07-13

**Status:** Approved in conversation; revised after rendered-report review

**Audience:** The Music-CRS project team and the author's future self

**Delivery:** One private, self-contained HTML report tracked at repository root as `retrospective.html`

## 1. Purpose

Create a detailed but accessible team retrospective explaining why the final
Music-CRS Blind-B submission underperformed four leading public-code systems.
The report must preserve enough technical detail for the team to reuse the
public implementations' ideas without turning the retrospective into a recovery
roadmap for a finished competition.

The report must answer seven questions:

1. What happened on the final leaderboard, and which scored terms made up the gap?
2. What did our submitted system actually do from conversation to response?
3. How did each team convert a conversation into one or more retrieval queries?
4. Which challenge data, external data, generated data, and LLM world knowledge did each team use?
5. Which retrieval, reranking, and response-generation mechanisms did the leading teams document?
6. What did those teams do especially well, and what remains undocumented?
7. Which principles and implementation patterns are worth carrying into future work?

## 2. Reader, voice, and evidence stance

The report is for teammates who understand machine learning but may not know
every recommender-system term. It will define specialized concepts before using
them, explain feature families rather than merely listing counts, and preserve
exact technical evidence behind progressive disclosure.

The voice will be first-person plural where the work was a team effort and
first-person singular only for personal judgment. It will be:

- candid about methodological and architectural weaknesses;
- explicit about what the submitted system did well;
- respectful and appreciative toward the released teams;
- precise about Verified, Inferred, and Not documented claims;
- careful not to convert architecture differences into hidden-set causal proof;
- focused on reusable learning rather than blame or a post-competition recovery plan.

The report will explicitly acknowledge that it depends on the openness of the
four teams and the challenge organizers.

## 3. Delivery and repository placement

The finished report will be the single tracked file:

```text
retrospective.html
```

It will live at repository root because the entire repository is the Music-CRS
competition project. No additional `music-crs-2026/` folder will be created.
The repository README will link to `retrospective.html` using a short
"Competition retrospective" entry.

The HTML must be self-contained: no local server, sibling assets, CDN, runtime
sidecars, or network calls at view time. The editable canonical artifact and
claim ledger may remain in the private visualization workspace; only the final
HTML and the README link are added to the project repository.

The report remains private/local unless the user separately authorizes
publishing or sharing.

## 4. Reader-facing information architecture

The report will follow this order:

1. **Title and Executive Summary** — the short answer and the strongest evidence-backed explanations.
2. **How the challenge was scored** — plain-language definitions and the composite formula.
3. **Final result and signed gap decomposition** — exact leaderboard values and the four-panel contribution visual.
4. **The complete system lifecycle** — one compact map from conversation to query, candidates, ranking, and response.
5. **From conversation to search query** — a systematic comparison of how all five systems represented and transformed dialogue.
6. **Data, generated artifacts, and model knowledge** — challenge data, external sources, synthetic/LLM-generated data, verified facts, and latent LLM world knowledge.
7. **Retrieval and candidate construction** — the actual retriever families, history signals, behavioral priors, and fusion boundaries.
8. **What the rankers learned from** — concrete feature families, validation lineage, routing, late fusion, and ensembles.
9. **Response generation was a full scored subsystem** — a team-by-team account of drafting, grounding, verification, selection, critique, rewriting, and lexical control.
10. **What our system built, what worked, and what failed methodologically** — submitted architecture, strengths, evaluation error, and evidence-bounded contributors.
11. **Four detailed public-team case studies** — volart, niwatori, swyoo, and team2_s2, using the same comparison template.
12. **Cross-team synthesis** — matrices for query construction, data/knowledge, retrieval/ranking, and response generation.
13. **What we would preserve, reconsider, and avoid** — retrospective judgments, not scheduled work.
14. **Transferable lessons** — principles for future recommender and ML competition work.
15. **Acknowledgements** — teams, repository authors, organizers, and the value of the released code.
16. **Caveats and evidence boundary** — 80 hidden sessions, no per-session labels, and no controlled counterfactuals.

The top of the report will include a compact section directory. The core story
and conclusions remain visible. Exact prompts, source-file inventories,
feature lists, model settings, and implementation details use expandable
`details` sections so technical readers can go deeper without forcing every
reader through one long wall of text.

## 5. From conversation to query

This will be a first-class technical chapter, not a detail hidden inside the
retrieval diagrams. Every system will be described using the same trace:

```text
conversation history
  -> interpretation or state extraction
  -> query construction or rewriting
  -> retriever-specific query representations
  -> filters and constraints
  -> candidate sources
```

For each team, the report will document:

1. **Conversation window:** full history, latest turn, selected turns, summaries, or another documented subset.
2. **Interpretation:** intent, entities, preferences, exclusions, satisfaction, pivots, novelty, and other state fields.
3. **LLM involvement:** model, prompt purpose, query rewriting, expansion, labeling, description generation, or no documented LLM transformation.
4. **Query representation:** raw text, structured JSON/state, field-specific text, multiple generated queries, learned query embeddings, or retriever-specific templates.
5. **History handling:** how earlier artists/tracks, accepted items, rejected items, and current-turn requests affect the query.
6. **Retriever handoff:** which representation goes to lexical, dense, collaborative, co-occurrence, transition, metadata, or lookup branches.
7. **Constraints:** genre, mood, year, artist, album, popularity, novelty, exclusions, and whether enforcement is hard or soft.
8. **Evidence boundary:** exact implementation, strong inference, or Not documented.

The visible comparison table will contain:

| Team | Conversation window | Interpreter/state | LLM query work | Query variants | Retriever-specific queries | History handling | Constraints |
|---|---|---|---|---|---|---|---|

Repository-provided prompt excerpts and examples may appear in expandable
details. The report will not reconstruct undocumented prompts or imply that all
teams used the same definition of a query.

## 6. Data, generated artifacts, and LLM knowledge

The report will not collapse all non-catalog information into "external data."
It will use four distinct categories:

1. **Challenge-provided data:** catalog, conversations, labels, and challenge training interactions.
2. **External structured or public data:** third-party metadata, public corpora, APIs, or other sources explicitly documented by a repository.
3. **Generated artifacts:** LLM-generated descriptions, rewritten queries, pseudo-labels, synthetic training examples, judgments, or summaries.
4. **Latent LLM world knowledge:** facts, associations, genres, themes, or descriptive knowledge supplied implicitly by a model's parameters rather than a cited record.

For each team and each pipeline stage, the report will state:

- the source or model, where documented;
- whether it entered training, query construction, retrieval, reranking, grounding, or response generation;
- whether the output was verified against catalog/structured facts;
- whether the source affects reproducibility, leakage risk, cost, or factual reliability;
- Verified, Inferred, or Not documented status.

The cross-team data/knowledge matrix will keep external structured data,
LLM-generated artifacts, and latent world knowledge in separate columns.

## 7. Retrieval and ranking feature inventory

The report will explain features as signals available to the ranker, not as a
feature-count contest. For each team, it will inventory documented feature
families and show where they came from:

- retriever rank, score, reciprocal rank, and presence indicators;
- dense semantic similarities and learned-retriever scores;
- collaborative-filtering and BPR signals;
- track co-occurrence, transition, and sequential-history features;
- artist, album, and listening-history affinity;
- popularity, frequency, and train-prior features;
- acoustic, genre, era, and metadata matches;
- conversation-state and constraint-satisfaction features;
- agreement, overlap, and consensus across retrievers;
- routing, shift, or scenario indicators;
- out-of-fold predictions and other leakage-safe feature lineage;
- late-fusion and ensemble outputs.

The feature chapter will include:

1. a plain-language feature-family glossary;
2. a team-by-feature-family matrix;
3. a detailed expandable inventory for every team;
4. the documented feature count only after the feature meanings are explained;
5. a validation-lineage column showing whether a learned feature was OOF,
   held out, in-sample, routed, or Not documented.

Counts alone will never be treated as evidence of quality. The interpretation
will emphasize signal diversity, behavioral relevance, clean validation, and
how candidate/feature coverage interacted with the ranker boundary.

## 8. Response generation as a scored subsystem

Because the response judge contributes materially to the composite and every
team used an LLM response path, response generation will receive a full chapter.
Each system will be compared across the same stages:

1. **Inputs:** conversation, latest state, selected track IDs, catalog metadata, external data, and generated descriptions.
2. **Drafting:** model(s), prompt role, number of calls, seeds, candidates, or passes.
3. **Grounding:** catalog facts, verified facts, citations, model world knowledge, or Not documented.
4. **Fact checking and repair:** validation, contradiction/theme checks, citation checks, or second-pass correction.
5. **Selection or critique:** independent critic, scoring, diversity selection, best-of-N selection, or no documented selector.
6. **Rewriting and style control:** polishing, selective rewriting, length/style constraints, lexical-diversity controls, and repetition handling.
7. **Recommendation-ID integrity:** how the pipeline prevented text editing from changing the selected track IDs.
8. **Final handoff:** one final response, chosen candidate, or multi-stage output.

The report will explicitly distinguish:

- multiple independently generated drafts;
- multiple seeds for the same prompt;
- a draft-plus-critic workflow;
- validation and repair of one draft;
- a two-pass polish;
- lexical post-processing.

These are different mechanisms and must not be summarized as merely "multiple
LLM calls." The chapter will include a stage-by-stage comparison table and an
accessible walkthrough of what each stage buys, what it costs, and what remains
unverified.

## 9. Public-team case-study template

Each of the four case studies will use the same visible template:

1. **Acknowledged contribution:** what the team released and what was especially useful to learn from.
2. **Verified final outcome:** exact official metrics.
3. **Conversation-to-query path:** window, state/parser, LLM transformations, query variants, and constraints.
4. **Data and knowledge:** challenge data, external sources, generated artifacts, latent world knowledge, and verification.
5. **Retrieval and candidate construction:** actual lanes, behavioral/history signals, and union/fusion behavior.
6. **Ranker and features:** model, feature families, count, OOF/validation lineage, routing, and late fusion.
7. **Response subsystem:** drafting, grounding, checking, selection/critique, rewriting, and final handoff.
8. **What they did better or differently:** evidence-supported comparison with our submitted path.
9. **Transferable implementation patterns:** concrete ideas the team can study or reuse.
10. **Limits:** per-session causality, missing ablations, and undocumented details.

Every exact count or model/pipeline claim will have a commit-pinned source
marker. Missing public evidence will remain Not documented rather than being
filled with assumptions.

## 10. Visual and interaction design

The report will be a responsive single-column document. The current compressed
architecture diagrams are rejected: placing two half-width rails side by side
and then splitting one rail into five or six equal-width columns produces
unreadable vertical word fragments at ordinary laptop widths.

The replacement diagram contract is:

- Offline and inference rails are stacked at full report width.
- Each rail uses at most three stage cards per row on wide screens.
- Stage cards have a practical minimum content width of approximately 220 px.
- Four or more stages wrap into additional rows without changing reading order.
- At narrow widths, all stages become one vertical timeline.
- Stage headings are short; technical detail appears as two to four bullets.
- Status and source markers occupy a separate footer area and never shrink the title.
- Connectors show order without forcing text into narrow boxes.
- Every diagram has a semantic ordered-list fallback.
- Core diagram meaning is carried by text and structure, not color alone.

The five system visuals will share this grammar while preserving different
topologies. Each begins with conversation-to-query, then candidate construction,
ranking, and response generation; the offline rail shows the training and
validation lineage that produced the serving components.

Quantitative visuals will include:

- exact leaderboard table and compact comparison chart;
- four-panel signed score-gap decomposition with centered zero baselines;
- conversation-to-query comparison matrix;
- data/knowledge-source matrix;
- feature-family matrix;
- response-generation stage matrix;
- preserve/reconsider/avoid retrospective table.

Every quantitative visual has adjacent prose. Exact values remain available in
semantic tables. Negative signed contributions must remain visibly negative.

## 11. Progressive disclosure

The visible report must remain readable without opening anything. Progressive
disclosure is reserved for audit detail:

- exact prompt excerpts;
- complete retriever and feature inventories;
- model parameters and training settings;
- external/generated data source detail;
- source-marker maps and commit-pinned file lists;
- additional implementation notes and documented unknowns.

Each team section will show its outcome, architecture, strongest choices, and
comparison by default. Expandable details will use clear labels such as
"Conversation-to-query evidence," "Complete feature inventory," "Response
pipeline details," and "Pinned sources." Core caveats and acknowledgements will
not be hidden.

## 12. Evidence and calculations

The report will use:

- the official final-results CSV;
- the submitted system pinned at commit `2ecc45a7d5ea83535f0504b48352b009b3379139`;
- the deployed Blind-B configuration and reranker bundle metadata;
- documented OOF diagnostics and evaluation protocol;
- the four public repositories pinned to their reviewed HEADs;
- direct file-level sources for query construction, data sources, feature
  definitions, validation, and response generation.

At the time of the revised design review, all four public repository HEADs still
matched the previously pinned commits:

- volart: `781ca9942b7c233255ac4a68da12fe42ec340b3a`
- niwatori: `5679a718c100aaf7779f122bb2eb65f702160f40`
- swyoo: `33dfe44dd36515e14e74116a8d23d059856d2d04`
- team2_s2: `e8ca96f67279a44aa38c614f51b4a015a65a2a90`

The composite gap will be independently reconciled using:

`0.50 × nDCG@20 + 0.10 × catalog diversity + 0.10 × lexical diversity + 0.30 × (judge − 1) / 4`

Evidence labels are:

- **Verified:** directly supported by official data, code, artifacts, or docs.
- **Inferred:** supported by documented steps or architecture differences but not stated verbatim or provable per Blind-B session.
- **Not documented:** the reviewed public sources do not establish the claim.

## 13. Acknowledgements

The report will contain a dedicated acknowledgements section that:

- credits volart / `artvolgin/music-crs-recsys2026`;
- credits niwatori / `ryowk/recsys2026-niwatori`;
- credits swyoo / `yoobros/music-crs-challenge`;
- credits team2_s2 / `lopsandrea/music-crs-team2`;
- credits the Music-CRS challenge organizers;
- states that the depth of the retrospective is possible because these teams
  released implementation details and code;
- links to the commit-pinned repositories and highlights the specific ideas each
  release made available to learn from.

Acknowledgement language will be appreciative and specific, not ceremonial or
competitive in tone.

## 14. Quality and acceptance checks

Before handoff, the revised report must pass all of the following:

- `retrospective.html` exists at repository root and the README links to it.
- No extra competition-named report folder is created.
- The opening directly answers what went wrong and what the team should learn.
- The conversation-to-query chapter covers all five teams using the same fields.
- External structured data, generated artifacts, and latent LLM world knowledge remain distinct.
- The response chapter compares all five systems stage by stage and distinguishes drafts, seeds, passes, critique, repair, and lexical post-processing.
- The ranking chapter explains actual feature families before showing feature counts.
- Every exact count, model, external source, prompt behavior, and response-pass claim has a commit-pinned source marker.
- Architecture stages remain readable without single-character vertical wrapping at laptop, tablet, and narrow widths.
- Offline and inference rails are full-width, ordered, and semantically available as lists.
- Core findings remain visible; expandable sections contain only deeper audit detail.
- Every team receives a balanced acknowledgement, technical walkthrough, comparison, and limits section.
- Official metrics and signed score contributions reconcile within disclosed published-value rounding.
- Evaluation reuse is described as a measurement/confidence failure, not a direct cause of hidden performance.
- Architecture differences remain contributor hypotheses rather than causal proof.
- The HTML is self-contained, embeds the canonical reviewed artifact, and makes zero external requests at view time.
- Packaged desktop and narrow-width verification passes with no overflow, zero-size blocks, browser errors, or payload mismatch.
- The final repository diff includes only the intended report, README link, and approved design/plan documentation.

## 15. Non-goals

This work will not:

- implement ranking, retrieval, query, or response-generation changes;
- prescribe a recovery plan, owners, milestones, experiments, or delivery schedule;
- claim per-session Blind-B root causes without hidden labels;
- imply that more features, more LLM calls, more data, or longer responses are automatically better;
- infer undocumented external data or prompts;
- treat latent LLM knowledge as verified factual grounding;
- publish, deploy, or change sharing permissions.
