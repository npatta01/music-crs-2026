# Answer-First Retrospective Diagnosis Design

**Status:** Approved in conversation on 2026-07-13; written specification awaiting final user review.

**Extends:** `2026-07-13-visual-first-retrospective-pagination-design.md` and `2026-07-13-interactive-retrospective-deck-design.md`.

## Objective

Make the completed Music-CRS retrospective answer the team's central question early and clearly: **why did the Blind-B submission likely underperform?** The report must distinguish observed score gaps from plausible causes, show what the deployed system actually did, separate missing upstream evidence from missing reranker features, and preserve the complete commit-pinned audit behind progressive disclosure.

This is a retrospective and learning artifact, not a recovery plan. It may add vertical slides when one technical idea needs its own canvas.

## Evidence boundary

The report can verify architecture, documented feature families, validation lineage, and scored metric differences. It cannot causally attribute hidden-set failures without Blind-B relevance labels, counterfactual candidate traces, or per-session judge rationales.

Every diagnosis claim must be labeled by confidence:

- **Verified:** directly established by the pinned deployed configuration, source code, artifacts, or official score arithmetic.
- **Likely contributor:** consistent with the observed gap and leader comparisons, but not isolated experimentally on Blind-B.
- **Unknown:** not recoverable from the available evidence.

The report must preserve these corrections:

- The system **did convert conversation into structured state and constraints**. The defensible concern is incomplete or uneven operationalization across candidate sources, filters, and ranker signals.
- The system **did use LLM knowledge** in state extraction, generated artist known-for document text, and response prose. The concern is that this knowledge was not consistently grounded and reused as retrieval evidence, ranker evidence, verified track facts, or response-quality control.
- The system **did include behavioral evidence** through anchor and user CF/BPR centroids, CF similarities, discography, and era-popularity lookups. These are not equivalent to direct track co-occurrence or sequential-transition mechanisms.
- Full-data fitting and in-sample dev replay were a **measurement and selection-confidence failure**, not a proven sole cause of the Blind-B result.
- Feature counts describe implementation breadth, not feature usefulness or generalization quality.
- External data and multi-draft response generation were not universal among the leading teams; team-specific mechanisms must remain precise.
- `b1_cos` was a LightGBM feature and not a candidate-producing retrieval lane.
- The deployed ranker used the union of up to 500 hits from each traced branch. LightGBM, not RRF, produced the submitted final ordering.

## Answer-first information architecture

Reorder the primary narrative to:

1. Outcome and score.
2. Why we likely underperformed.
3. Our submitted system.
4. Conversation to query.
5. Retrieval and ranking.
6. Response generation.
7. Leading-team case studies.
8. Synthesis and evidence.

The diagnosis appears immediately after the result. Existing deep links remain valid through aliases. The complete deck remains locally accessible and self-contained.

## Two reading paths

### Read the retrospective

Provide a curated path of approximately 12–15 essential slides. It should cover:

- result and score decomposition;
- the six-slide diagnosis;
- the submitted pipeline;
- the most important cross-team retrieval, feature, knowledge, and response differences;
- lessons and acknowledgements.

The curated path is explicit navigation, not a separate or reduced artifact. A reader can leave it at any point to inspect the complete evidence.

### Explore the evidence audit

Retain every source-backed matrix, prompt excerpt, feature inventory, validation qualification, team limitation, pinned commit, and source link. The full 50-plus-slide chapter/depth navigation remains available.

## Six-slide diagnosis section

### 1. Where the score gap appeared

Use a compact annotated score visual rather than prose. It must state:

- ranking/nDCG and the LLM judge account for most of the arithmetic gap;
- catalog diversity is nearly neutral;
- lexical diversity varies by team;
- the decomposition identifies where points differ, not which implementation choice caused the difference.

Exact values and last-decimal reconciliation remain behind disclosure.

### 2. Where information was lost

Show one end-to-end bottleneck map:

```text
Conversation
  -> extracted state
  -> retriever-specific queries and constraints
  -> candidate sources
  -> candidate union
  -> LightGBM features
  -> top-1 track
  -> grounded response context
  -> one response draft
  -> final response
```

Mark four possible loss points:

1. Extracted facts did not always become source-specific actions.
2. No direct co-occurrence or transition lane supplied those candidates and signals.
3. Tracks absent from the candidate union were irrecoverable by LightGBM.
4. The final response had no independent selection, checking, or repair loop.

### 3. Extracted constraints versus operationalized constraints

Use a left-to-right wiring diagram rather than a paragraph.

The left side lists verified extracted state:

- current request;
- artist, album, track, and attribute facts;
- explicit hard and soft exclusions;
- played-track sentiment, acceptance, rejection, contrast, and pinned references;
- temporal constraints;
- lyrical theme when relevant;
- resolved catalog IDs and projected routing/profile fields.

The right side shows actual consumers:

- weighted BM25 clauses;
- field-aligned dense strings;
- audio and visual queries;
- anchor and user centroids;
- discography and era lookups;
- hard track rejection, tag demotion, artist veto, and soft era handling;
- LightGBM state, history, routing, rejection, and interaction features.

Use connection styles to distinguish direct enforcement, soft influence, and extracted evidence without a dedicated source action. The takeaway is **rich extraction, uneven execution**, not missing constraint conversion.

### 4. What the 142-feature reranker saw

Use a feature-family map with counts as a small badge rather than the headline. Show six families:

- retriever evidence: rank, raw score, presence, margin, ratio, percentile, standardized score, and source identity;
- semantic and multimodal evidence: `b1_cos`, Qwen metadata and lyric similarities, tag embeddings, CLAP audio, and SigLIP visual signals;
- behavioral and lookup evidence: anchor/user CF-BPR centroids, other CF similarities, discography, and era-popularity;
- catalog evidence: popularity, year, era, tags, artist, album, duration, culture, and age affinity;
- conversation/state evidence: request, intent, routing, rejection, new-artist preference, temporal constraints, history depth, and state overlap;
- agreement and interaction evidence: branch presence, best ranks, z-scores, percentiles, same-artist counts, and cross-feature terms.

State explicitly that 142 documented features constitute a substantial ranker; count alone does not establish liveness, importance, robustness, or held-out benefit.

### 5. Evidence the ranker could not see or recover

Separate three boundaries visually:

1. **Missing upstream source:** no direct track co-occurrence lane, no Markov/sequential-transition lane, no candidate-producing `b1` lane, and no systematic grounded LLM-description retrieval lane.
2. **Consequent missing feature:** no direct co-occurrence sums, maxima, probabilities, or lane membership; no transition probability; weaker direct artist/album/track history-continuity evidence; no grounded generated-description similarity; and less deliberate frequency or behavior-derived prior evidence.
3. **Not missing:** dense similarity, collaborative centroids, conversation-state features, rejection and temporal signals, metadata/popularity/era, and cross-source agreement.

The slide must explain that adding LightGBM columns cannot recreate a track or source signal that never entered the pipeline.

### 6. Response weakness and confidence-ranked diagnosis

Use a response-control lane and a three-tier diagnosis panel.

Verified response path:

```text
Top-1 ID fixed
  -> latest state and XML-delimited catalog metadata
  -> one temperature-zero Qwen call
  -> final response
```

Blind-B used `echo_retries=0`. No independent fact checker, multi-candidate selector, critic, contradiction/theme/citation repair, lexical pass, or post-edit integrity guard was documented.

The confidence panel summarizes:

- **Verified:** score-gap location, uneven constraint operationalization, partial behavioral evidence, `b1_cos` as feature only, single-pass generation, and weak validation confidence.
- **Likely:** insufficiently diverse behavioral evidence, under-productized LLM knowledge, distribution shift or objective mismatch, and thin response-quality control.
- **Unknown:** candidate recall on Blind-B, whether relevant candidates were misranked, per-session failure frequencies, and the causal effect of any one mechanism.

## Belief-update timeline

Include a compact timeline in the diagnosis or submitted-system chapter:

```text
Before submission
0.3844–0.4562 in-sample dev diagnostics encouraged confidence

Evidence already available
0.1970–0.2032 leakage-safe OOF results indicated weaker generalization

Blind-B result
0.2537 nDCG@20 and 3.30/5 judge score

Post-competition review
Candidate, constraint-execution, behavioral-evidence, and response-control gaps emerged
```

The timeline explains the team's belief update without suggesting that the post-competition comparison was known before submission.

## Failure-attribution taxonomy

Add a compact diagnostic taxonomy, either as a panel on slide 2 or as a seventh slide if readability requires it:

1. Relevant track never entered the candidate union.
2. Relevant track entered but was misranked.
3. Selected track was reasonable but its explanation was weak.
4. Both recommendation and explanation were weak.

Label all category frequencies **unknown** because hidden relevance labels and counterfactual traces are unavailable.

## Feature availability versus usefulness

Show the evidence ladder:

```text
Evidence source existed
  -> produced candidates
  -> became a ranker feature
  -> fired meaningfully on relevant sessions
  -> improved held-out performance
```

The report establishes the first three more strongly than the last two. Never infer importance from documented existence or column count. Keep exact inventories and validation lineage behind disclosure.

## Possible public-to-hidden shift

Add a small amber panel naming plausible but unverified shift surfaces:

- conversation and request mix;
- history availability;
- catalog and entity distribution;
- label or relevance behavior;
- response-judge cases.

The panel must not imply that shift is measured or proven.

## Deck-wide compression

### Conversation to query

Merge the two overlapping mechanism explainers into one slide. Keep the complete glossary, qualifications, prompt excerpts, and five-team query matrix behind disclosure or in the evidence path.

### Retrieval and feature taxonomy

Replace the visible ten-card feature glossary and repeated matrix narrative with:

1. one shared feature-family map;
2. one team-by-evidence heatmap that emphasizes differentiating sources;
3. complete inventories and exact validation lineage behind disclosure.

The heatmap distinguishes lexical, dense, collaborative, co-occurrence, transition, lookup, generated-description, metadata, conversation/state, agreement/routing, and prior evidence. Common families use neutral color; differentiating evidence uses team color. Feature counts appear as secondary badges.

### Response generation

Compress the primary response chapter to:

1. one shared selected-track-to-response lifecycle;
2. one five-team grounding and candidate-generation comparison;
3. one five-team selection, checking, repair, and lexical-control comparison.

Keep exact response matrices, pass counts, prompt details, and team walkthroughs behind disclosure.

### Leading-team case studies

Preserve the mechanism-specific retrieval diagrams and expandable insight cards. Convert each outcome/query/data page into a compact system card containing:

- result badge;
- conversation-to-query mechanism;
- distinctive data or knowledge sources;
- retrieval/ranking differentiator;
- response-control differentiator;
- evidence limitation.

Long walkthroughs, limitations, and citations remain expandable.

### Score interpretation

Replace the prose-heavy interpretation page with three annotated findings: ranking and judge dominate, catalog diversity is neutral, and the decomposition is arithmetic rather than causal. Keep exact arithmetic behind disclosure.

## Reusable visual grammar

Use three deterministic, accessible visual forms throughout:

1. **Evidence heatmap:** team-by-mechanism differences, with text or icons redundant to color.
2. **Pipeline lane:** ordered mechanisms, decisions, and quality-control passes.
3. **Provenance stack:** official challenge data, external structured data, generated artifacts, latent LLM knowledge, and verification shields.

All visuals are native HTML/CSS or deterministic SVG. Decorative or abstract raster artwork is out of scope. Images may explain a system only when every factual claim is also represented as accessible text.

## Navigation behavior

- Add a prominent `Why we underperformed` jump from the executive answer.
- Add explicit `Read the retrospective` and `Explore the evidence audit` controls.
- Preserve horizontal chapter and vertical depth navigation.
- Keep existing hashes working through aliases after chapter reordering or slide merging.
- The curated path must support previous/next, keyboard, touch, and direct-link navigation without trapping the reader.
- Linear, print, and JavaScript-disabled modes show the complete canonical evidence, not only the curated path.

## Evidence and acknowledgements

- Display the pinned submission commit on diagnosis slides so current `main` improvements are not confused with the Blind-B deployment.
- State that repository documentation depth can bias `Not documented` comparisons.
- Preserve exact official-result sources, repository SHAs, and team-specific evidence links.
- Credit TalkPlayData-1, LRCLIB, Genius, and MusicBrainz where the reviewed systems used them.
- Preserve competitor and organizer acknowledgements.
- Add internal contributors or tool ecosystems only when names and roles can be verified; do not infer them.

## Progressive-disclosure contract

Keep these details complete but off the primary reading path:

- exact leaderboard values and score reconciliation;
- complete five-team query, provenance, retrieval, feature, and response matrices;
- exact prompt excerpts and reviewed-file inventories;
- all 142 submitted features and per-team feature inventories;
- validation lineage and OOF/full-data qualifications;
- exact response pass counts and source links;
- per-team limitations and `Not documented` findings;
- complete caveats, source records, and pinned commits.

Disclosure labels must name the content they reveal. Opening a disclosure may lengthen the active slide but may not introduce nested vertical scrolling.

## Responsive and accessibility requirements

- One primary visual or comparison per slide.
- Large headings and readable labels; avoid paragraph walls.
- No internal vertical scrollbars.
- Tables become labeled cards on narrow screens when semantics permit.
- Color is always redundant with labels, icons, line styles, or position.
- DOM order matches visual reading order.
- Essential text is never baked only into an image.
- Controls remain at least 44px on touch devices.
- Preserve reduced-motion, forced-color, keyboard, print, linear, and JavaScript-disabled behavior.

## Acceptance checks

### Content and evidence

- The diagnosis appears immediately after the outcome.
- All diagnosis claims are classified as Verified, Likely contributor, or Unknown.
- The report never claims the system lacked constraints, behavioral evidence, or LLM knowledge.
- Candidate-generation gaps and reranker-feature gaps are visibly distinct.
- `b1_cos` is identified as a reranker feature, not a deployed candidate lane.
- The candidate boundary consistently describes up to 500 hits from each branch entering the union.
- Full-data fitting is described as a measurement/confidence problem, not a sole causal explanation.
- Team-specific external-data and response-generation claims remain precise.
- The pinned submission commit and documentation-depth caveat are visible.

### Structure and navigation

- The curated path contains approximately 12–15 slides and reaches the diagnosis in the first chapter transition.
- The evidence path retains every canonical block and source record exactly once.
- Old hashes resolve to the intended new slide or disclosure.
- Both reading modes work through controls, keyboard, touch, direct links, and browser history.

### Visual quality

At 1,533×903, 1,280×800, 1,024×768, and 390×844 in light and dark themes:

- no clipped visual, table, card, or disclosure;
- no nested vertical scrollbar;
- no unintended document-level horizontal overflow;
- diagnosis slides use the canvas intentionally;
- heatmaps, lanes, and provenance stacks remain legible without zooming out;
- primary slides contain no intimidating text blocks;
- complete evidence remains reachable within two interactions from its summary.

### Regression and integrity

- Existing source URLs, SHAs, iframe payloads, and compressed artifact data are preserved.
- Static, linear, print, JavaScript-disabled, and self-contained HTML behavior remain correct.
- Automated structural and browser tests cover the new order, curated path, aliases, feature distinctions, confidence labels, and responsive overflow.

## Non-goals

- No recovery plan, new experiment roadmap, or claim about how to win a future competition.
- No causal attribution beyond available evidence.
- No decorative, abstract, or stock imagery.
- No removal of the complete technical audit.
- No public deployment or change to sharing permissions.
