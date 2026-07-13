# Revised Blind-B Retrospective HTML Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revise the existing Music-CRS Blind-B retrospective into a detailed, accessible, evidence-backed, self-contained `retrospective.html` at repository root, with readable system diagrams and full comparisons of conversation-to-query conversion, data and LLM knowledge, ranker features, and response generation.

**Architecture:** Preserve and patch the existing canonical `artifact.json` and `evidence.json` in the private visualization workspace. The canonical artifact remains the only report source; the shared Data Analytics portable builder packages it directly to the repository-root `retrospective.html`, and `readme.md` links to that generated file. Evidence is commit-pinned and normalized before prose or visuals are changed, then the report is rendered and validated as a whole.

**Tech Stack:** Canonical Data Analytics report JSON, self-contained HTML/CSS blocks, semantic HTML tables and ordered lists, Node.js validation scripts, `rg`, Git, and the shared portable-report Chromium verifier.

## Global Constraints

- Deliver exactly one reader-facing report file at repository root: `retrospective.html`.
- Modify the existing lowercase `readme.md`; do not create `README.md` or a `music-crs-2026/` directory.
- Keep the report private/local. Do not publish, deploy, change sharing, or expose a server.
- Patch the current full report artifact in place. Preserve existing leaderboard calculations, claims, case studies, caveats, sources, datasets, and stable block IDs unless the approved revision directly changes them.
- Use the official final-results CSV and these reviewed repository commits:
  - author: `2ecc45a7d5ea83535f0504b48352b009b3379139`
  - volart: `781ca9942b7c233255ac4a68da12fe42ec340b3a`
  - niwatori: `5679a718c100aaf7779f122bb2eb65f702160f40`
  - swyoo: `33dfe44dd36515e14e74116a8d23d059856d2d04`
  - team2_s2: `e8ca96f67279a44aa38c614f51b4a015a65a2a90`
- Label claims only as `Verified`, `Inferred`, or `Not documented`. Do not convert architecture differences into hidden-session causal proof.
- Keep challenge-provided data, external structured/public data, generated artifacts, and latent LLM world knowledge as four separate concepts.
- Explain feature families before feature counts. Counts alone are not an argument for model quality.
- Treat response generation as a fully scored subsystem and distinguish independent drafts, random seeds, critique, validation/repair, second-pass polishing, and lexical post-processing.
- Offline and inference rails must be stacked at full width. A rail may show no more than three stage cards per row at desktop width, two at tablet width, and one at narrow width. Stage cards must remain at least approximately 220 px wide when multiple cards share a row.
- Use visible text, numbering, and structure in addition to color. The architecture card list itself must be a semantic `<ol>`.
- Core findings, case-study summaries, caveats, and acknowledgements stay visible. Exact prompts, complete feature inventories, file lists, and audit detail may use `<details>`.
- Keep the finished report retrospective. Do not add owners, milestones, experiment schedules, a recovery roadmap, or competition-recovery recommendations.
- The technical-report template's “recommended next steps” role is intentionally fulfilled by `What we would preserve, reconsider, and avoid` plus `Transferable lessons and further questions`; this is a retrospective judgment section, not a delivery plan.
- Package from the canonical artifact using the shared portable builder. Do not hand-author a second HTML implementation or add runtime sidecars.
- Treat generated `retrospective.html` as output. Make content and layout corrections in `artifact.json`, then regenerate.

## File Structure

### Canonical artifact workspace

`/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json`
: Commit-pinned leaderboard values, score-gap calculations, claims, and the four normalized cross-team comparison datasets.

`/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json`
: Canonical ordered report manifest, source metadata, bounded snapshot datasets, narratives, tables, charts, details blocks, and responsive architecture diagrams.

### Project repository

`retrospective.html`
: Generated self-contained report committed at repository root.

`readme.md`
: Existing repository overview; receives one prominent retrospective link.

`docs/superpowers/specs/2026-07-12-blind-b-retrospective-report-design.md`
: Approved design contract; read-only during implementation.

`docs/superpowers/plans/2026-07-12-blind-b-retrospective-html.md`
: This execution plan.

### Read-only evidence checkouts

`/tmp/music-crs-retrospective-sources/volart/`
: volart at `781ca9942b7c233255ac4a68da12fe42ec340b3a`.

`/tmp/music-crs-retrospective-sources/niwatori/`
: niwatori at `5679a718c100aaf7779f122bb2eb65f702160f40`.

`/tmp/music-crs-retrospective-sources/swyoo/`
: swyoo at `33dfe44dd36515e14e74116a8d23d059856d2d04`.

`/tmp/music-crs-retrospective-sources/team2/`
: team2_s2 at `e8ca96f67279a44aa38c614f51b4a015a65a2a90`.

---

### Task 1: Expand and Normalize the Commit-Pinned Evidence Ledger

**Files:**
- Modify: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json`
- Read: `configs/state_ranker_v10_lgbm_blindset_B.yaml`
- Read: `mcrs/conversation_state/schema.py`
- Read: `mcrs/conversation_state/prompts/current.py`
- Read: `mcrs/qu_modules/compiler.py`
- Read: `mcrs/qu_modules/retrieval_compiler.py`
- Read: `mcrs/qu_modules/post_fusion_features.py`
- Read: `mcrs/qu_modules/lgbm_reranker.py`
- Read: `mcrs/response_context.py`
- Read: `models/reranker_v12_goalfree/meta.json`
- Read: `docs/architectures/session_state.md`
- Read: `docs/architectures/v0plus_retrieval.md`
- Read: `docs/architectures/biencoder.md`
- Read: `docs/architectures/explanation_generation.md`
- Read: `/tmp/music-crs-retrospective-sources/volart/src/retrieval/query_rewriter.py`
- Read: `/tmp/music-crs-retrospective-sources/volart/src/retrieval/entity_extractor.py`
- Read: `/tmp/music-crs-retrospective-sources/volart/src/retrieval/retrieve.py`
- Read: `/tmp/music-crs-retrospective-sources/volart/src/reranker/lambdamart/features.py`
- Read: `/tmp/music-crs-retrospective-sources/volart/src/explanation/explain.py`
- Read: `/tmp/music-crs-retrospective-sources/volart/src/explanation/quality_critic.py`
- Read: `/tmp/music-crs-retrospective-sources/volart/src/explanation/refine_responses.py`
- Read: `/tmp/music-crs-retrospective-sources/volart/src/explanation/harden_responses.py`
- Read: `/tmp/music-crs-retrospective-sources/volart/src/explanation/lexdiv_pass.py`
- Read: `/tmp/music-crs-retrospective-sources/niwatori/docs/method.md`
- Read: `/tmp/music-crs-retrospective-sources/niwatori/retriever/bm25_5field_thought/README.md`
- Read: `/tmp/music-crs-retrospective-sources/niwatori/retriever/tag_intent_bm25/README.md`
- Read: `/tmp/music-crs-retrospective-sources/niwatori/retriever/two_tower_lora_thought/README.md`
- Read: `/tmp/music-crs-retrospective-sources/niwatori/src/recsys2026/reranker_features.py`
- Read: `/tmp/music-crs-retrospective-sources/niwatori/src/recsys2026/responder_ensemble.py`
- Read: `/tmp/music-crs-retrospective-sources/niwatori/responder/qwen36_27b/README.md`
- Read: `/tmp/music-crs-retrospective-sources/swyoo/mymodule/feature/user_profile.py`
- Read: `/tmp/music-crs-retrospective-sources/swyoo/mymodule/feature/crawl/sources.py`
- Read: `/tmp/music-crs-retrospective-sources/swyoo/mymodule/strategies/twotower/synth_doc.py`
- Read: `/tmp/music-crs-retrospective-sources/swyoo/mymodule/strategies/rerank/gbm/build_features.py`
- Read: `/tmp/music-crs-retrospective-sources/swyoo/mymodule/strategies/rerank/gbm/oof_features.py`
- Read: `/tmp/music-crs-retrospective-sources/swyoo/mymodule/strategies/response/pas/generator.py`
- Read: `/tmp/music-crs-retrospective-sources/swyoo/mymodule/strategies/response/pas/select.py`
- Read: `/tmp/music-crs-retrospective-sources/team2/recommender/text.py`
- Read: `/tmp/music-crs-retrospective-sources/team2/recommender/sources.py`
- Read: `/tmp/music-crs-retrospective-sources/team2/recommender/features.py`
- Read: `/tmp/music-crs-retrospective-sources/team2/recommender/ranker.py`
- Read: `/tmp/music-crs-retrospective-sources/team2/response_gen/track_facts.py`
- Read: `/tmp/music-crs-retrospective-sources/team2/response_gen/prompts.py`
- Read: `/tmp/music-crs-retrospective-sources/team2/response_gen/gemini.py`
- Read: `/tmp/music-crs-retrospective-sources/team2/response_gen/gemini_pro_refiner.py`

**Interfaces:**
- Consumes: Existing `leaderboard`, `gapContributions`, `repositories`, and `claims` fields plus the five pinned source trees.
- Produces: Existing claims augmented with a `topic` field and four five-row comparison arrays named `queryComparisons`, `dataKnowledgeComparisons`, `featureFamilyComparisons`, and `responseComparisons`.

- [ ] **Step 1: Verify all five source trees are pinned to the approved commits**

Run:

```bash
git rev-parse 2ecc45a7d5ea83535f0504b48352b009b3379139
git -C /tmp/music-crs-retrospective-sources/volart rev-parse HEAD
git -C /tmp/music-crs-retrospective-sources/niwatori rev-parse HEAD
git -C /tmp/music-crs-retrospective-sources/swyoo rev-parse HEAD
git -C /tmp/music-crs-retrospective-sources/team2 rev-parse HEAD
```

Expected, in order:

```text
2ecc45a7d5ea83535f0504b48352b009b3379139
781ca9942b7c233255ac4a68da12fe42ec340b3a
5679a718c100aaf7779f122bb2eb65f702160f40
33dfe44dd36515e14e74116a8d23d059856d2d04
e8ca96f67279a44aa38c614f51b4a015a65a2a90
```

- [ ] **Step 2: Add a `topic` to every existing and new claim**

Use `apply_patch` on `evidence.json`. Preserve every current claim ID and add exactly one of these values:

```json
"topic": "query"
"topic": "data"
"topic": "retrieval"
"topic": "features"
"topic": "response"
"topic": "validation"
```

Add claim records when the existing ledger does not yet cover these facts:

- conversation window and state/query transformation;
- retriever-specific query representations and constraints;
- external public/structured data, including its pipeline stage;
- LLM-generated descriptions, profiles, rewrites, labels, or summaries;
- latent LLM world knowledge and whether it was verified;
- feature-family definitions and validation lineage;
- response drafting, grounding, checking, selection, rewriting, lexical control, and recommendation-ID integrity.

Use the existing claim shape without renaming fields:

```json
{
  "id": "volart-query-rewriter",
  "rail": "inference",
  "topic": "query",
  "label": "LLM query rewriting",
  "status": "Verified",
  "summary": "The retrieval path rewrites the dialogue into retrieval-oriented text before handing variants to downstream retrievers.",
  "sourceUrl": "https://github.com/artvolgin/music-crs-recsys2026/blob/781ca9942b7c233255ac4a68da12fe42ec340b3a/src/retrieval/query_rewriter.py",
  "sourceNote": "Query-rewriter implementation"
}
```

For a negative evidence boundary, record `Not documented` and describe the reviewed scope; do not invent a prompt, source, or model:

```json
{
  "id": "team-response-id-integrity-undocumented",
  "rail": "inference",
  "topic": "response",
  "label": "Recommendation-ID integrity",
  "status": "Not documented",
  "summary": "The reviewed public files do not establish an independent guard that checks whether response editing changes the selected recommendation IDs.",
  "sourceUrl": "",
  "sourceNote": "Evidence boundary after review of the documented response pipeline"
}
```

Create the exact claim ID `swyoo-crawl-sources` from
`mymodule/feature/crawl/sources.py`. Its summary must name LRCLIB and Genius as
lyrics sources and MusicBrainz as structured metadata, while its accompanying
guardrail claim cites `mymodule/feature/crawl/guardrails.py` and explains the
documented quality checks. This claim supplies the external-data evidence used
by the normalized swyoo row below.

- [ ] **Step 3: Add the five normalized conversation-to-query rows**

Add `queryComparisons` with one row each for `npatta01`, `volart`, `niwatori`, `swyoo`, and `team2_s2`. Every row must have this exact shape:

```json
{
  "team": "volart",
  "conversationWindow": "Full documented dialogue context or the narrower verified window",
  "interpretation": "Entities, intent, preferences, exclusions, satisfaction, or Not documented",
  "llmQueryWork": "Rewriting, expansion, labeling, description generation, none, or Not documented",
  "queryVariants": "The verified count/type of variants, or Not documented",
  "retrieverQueries": "What lexical, dense, collaborative, co-occurrence, transition, metadata, and lookup branches actually receive",
  "historyHandling": "How accepted, rejected, and previously mentioned artists/tracks are used",
  "constraints": "Hard and soft artist, genre, mood, era, popularity, novelty, and exclusion handling",
  "status": "Verified",
  "evidenceIds": ["volart-query-rewriter"]
}
```

Replace the example wording with commit-pinned summaries. Do not write “full history” unless the call site proves that the full history is passed. If a field is not established, write `Not documented` in that field while keeping the row.

- [ ] **Step 4: Add the five normalized data-and-knowledge rows**

Add `dataKnowledgeComparisons` with this exact shape:

```json
{
  "team": "swyoo",
  "challengeData": "Catalog, conversations, labels, and interactions actually used",
  "externalStructuredData": "Named public dataset/API/crawl source and stage, or Not documented",
  "generatedArtifacts": "LLM-generated profiles, documents, labels, rewrites, or summaries",
  "latentLLMKnowledge": "Where model parameters supply music facts or associations without a cited record",
  "verification": "Catalog check, structured-fact check, critic/repair, or Not documented",
  "pipelineStages": "Training; query; retrieval; ranking; grounding; response",
  "reproducibilityNotes": "Cost, cache, leakage, availability, and factual-reliability implications",
  "status": "Verified",
  "evidenceIds": ["swyoo-crawl-sources"]
}
```

The four knowledge categories must remain separate even when one team uses more than one in the same stage. A model name alone does not prove use of world knowledge; describe the prompt/output role that allows latent knowledge to enter.

- [ ] **Step 5: Add the five normalized feature-family rows**

Add `featureFamilyComparisons`. Each row must contain these fields:

```json
{
  "team": "niwatori",
  "retrieverSignals": "Rank, score, reciprocal rank, presence, and branch identity features",
  "denseSignals": "Semantic and learned-retriever similarity features",
  "behavioralSignals": "Collaborative, BPR, co-occurrence, transition, artist/album-history, and train-prior features",
  "metadataSignals": "Acoustic, genre, mood, era, popularity, artist, album, and catalog fields",
  "conversationSignals": "State, intent, constraint, satisfaction, pivot, and novelty features",
  "agreementSignals": "Overlap, consensus, cross-retriever, routing, shift, and scenario indicators",
  "validationLineage": "OOF, held out, in-sample, routed, ensembled, or Not documented",
  "documentedCount": "176 features",
  "status": "Verified",
  "evidenceIds": ["niwatori-lgbm-176", "niwatori-oof-two-tower"]
}
```

For the author's behavioral coverage, preserve this exact distinction in the evidence:

- two CF/BPR behavioral centroid branches: anchor centroid and user centroid;
- discography and era-popularity lookups;
- no documented direct track co-occurrence lane or sequential-transition lane in the submitted path;
- matrix status `Partial` for direct co-occurrence/sequential evidence because behavioral centroid similarity is related but is not the same mechanism.

- [ ] **Step 6: Add the five normalized response-pipeline rows**

Add `responseComparisons` using this exact shape:

```json
{
  "team": "team2_s2",
  "inputs": "Conversation/state, selected IDs, catalog facts, external data, and generated descriptions",
  "drafting": "Model, prompt role, passes, candidate count, and seed behavior",
  "grounding": "Catalog facts, verified facts, citations, or latent model knowledge",
  "checkingRepair": "Theme, contradiction, fact, citation, or second-pass correction",
  "selectionCritique": "Independent critic, best-of-N, diversity selection, or no documented selector",
  "rewritingLexical": "Polish, selective rewrite, length/style constraints, and lexical stabilization",
  "idIntegrity": "How selected recommendation IDs are protected from text edits",
  "finalHandoff": "Single draft, selected candidate, repaired draft, or polished second pass",
  "status": "Verified",
  "evidenceIds": ["team2-two-pass-gemini"]
}
```

The visible summaries must preserve these verified distinctions:

- author: one top-1 single-pass response; no documented fact-verification layer, multi-candidate generation, or independent selector/critic;
- volart: candidate generation, independent critique, selective refinement, hardening, and lexical-diversity handling without changing track IDs;
- niwatori: ten seeded candidates followed by diversity-based selection;
- swyoo: PAS-structured grounded generation with validation/repair and deterministic lexical stabilization;
- team2_s2: verified track facts in the prompt followed by a second-pass polish/refinement step.

- [ ] **Step 7: Validate ledger shape, commit pins, cross-references, and topic coverage**

Run:

```bash
node - <<'NODE'
const fs = require('fs');
const p = '/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json';
const e = JSON.parse(fs.readFileSync(p));
const teams = ['npatta01','volart','niwatori','swyoo','team2_s2'];
const topics = new Set(['query','data','retrieval','features','response','validation']);
const statuses = new Set(['Verified','Inferred','Not documented']);
const ids = new Set();
for (const team of teams) {
  if (!Array.isArray(e.claims[team]) || e.claims[team].length < 8) throw Error(`claim coverage: ${team}`);
  for (const c of e.claims[team]) {
    for (const k of ['id','rail','topic','label','status','summary','sourceNote']) if (typeof c[k] !== 'string' || !c[k]) throw Error(`${team}/${c.id || 'missing'}: ${k}`);
    if (!topics.has(c.topic)) throw Error(`${team}/${c.id}: topic`);
    if (!statuses.has(c.status)) throw Error(`${team}/${c.id}: status`);
    if (c.status !== 'Not documented' && !/^https:\/\/github\.com\/.+\/blob\/[0-9a-f]{40}\//.test(c.sourceUrl || '')) throw Error(`${team}/${c.id}: unpinned source`);
    if (ids.has(c.id)) throw Error(`duplicate claim id: ${c.id}`);
    ids.add(c.id);
  }
}
for (const key of ['queryComparisons','dataKnowledgeComparisons','featureFamilyComparisons','responseComparisons']) {
  if (!Array.isArray(e[key]) || e[key].length !== 5) throw Error(`${key}: expected five rows`);
  if (e[key].map(r => r.team).join('|') !== teams.join('|')) throw Error(`${key}: team order`);
  for (const row of e[key]) for (const id of row.evidenceIds || []) if (!ids.has(id)) throw Error(`${key}/${row.team}: unknown ${id}`);
}
console.log('PASS: normalized five-team evidence ledger is complete and commit-pinned');
NODE
```

Expected: `PASS: normalized five-team evidence ledger is complete and commit-pinned`.

- [ ] **Step 8: Commit the normalized evidence ledger in the artifact workspace**

Run:

```bash
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective add evidence.json
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective commit -m "data: expand retrospective evidence ledger"
```

Expected: one commit containing only `evidence.json`.

---

### Task 2: Restructure the Report for Progressive Disclosure

**Files:**
- Modify: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json`
- Read: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json`

**Interfaces:**
- Consumes: The four normalized comparison arrays and expanded claim ledger from Task 1.
- Produces: Existing 48-block report plus a section directory and first-class lifecycle, query, data/knowledge, retrieval, features, response, acknowledgements, and evidence-boundary blocks.

- [ ] **Step 1: Preserve the current artifact before changing structure**

Run:

```bash
node - <<'NODE'
const fs = require('fs');
const p = '/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json';
const a = JSON.parse(fs.readFileSync(p));
const required = ['title','executive_summary','headline_metrics','leaderboard_table','gap_contribution_chart','own_system_diagram','volart_diagram','niwatori_diagram','swyoo_diagram','team2_s2_diagram','cross_team_matrix','preserve_reconsider_avoid','caveats','evidence_notes'];
const ids = new Set(a.manifest.blocks.map(b => b.id));
for (const id of required) if (!ids.has(id)) throw Error(`missing baseline block ${id}`);
console.log(`PASS: baseline has ${a.manifest.blocks.length} blocks and ${Object.keys(a.snapshot.datasets).length} datasets`);
NODE
```

Expected: `PASS: baseline has 48 blocks and 4 datasets`.

- [ ] **Step 2: Add the normalized datasets to the canonical snapshot**

Use `apply_patch` to add these exact snapshot dataset IDs, copying the reviewed rows from `evidence.json` without paraphrasing them again:

```text
query_comparisons
data_knowledge_comparisons
feature_family_comparisons
response_comparisons
```

Keep the existing `leaderboard`, `gap_contributions`, `cross_team_matrix`, and `retrospective_choices` datasets unchanged except for direct dependent corrections justified by the new ledger.

- [ ] **Step 3: Add a visible section directory after the headline metrics**

Add an HTML block with ID `section_directory`. Its visible links must use this order:

```text
Final result
Complete system lifecycle
Conversation to query
Data and model knowledge
Retrieval and candidate construction
Ranker feature families
Response generation
Our submitted system
Public-team case studies
Cross-team synthesis
Retrospective lessons
Acknowledgements
Caveats and evidence
```

Use anchor links and a compact wrapping list. Keep the directory visible at all widths; do not hide it in a menu.

- [ ] **Step 4: Add the complete lifecycle chapter**

Insert these blocks after `gap_interpretation`:

```text
lifecycle_heading
lifecycle_map
lifecycle_takeaway
```

The lifecycle map must show this common comparison grammar without implying identical implementations:

```text
conversation → interpretation/state → query variants → candidate sources → ranking/fusion → selected track IDs → response pipeline
```

The takeaway must explicitly say that retrieval quality and response quality are separate scored boundaries, while both depend on how the conversation was interpreted upstream.

- [ ] **Step 5: Add first-class query, data, retrieval, features, and response chapters**

Add the following stable block IDs before `own_system_heading`:

```text
query_heading
query_explainer
query_matrix
query_evidence_details
data_knowledge_heading
data_knowledge_glossary
data_knowledge_matrix
data_knowledge_interpretation
retrieval_heading
retrieval_glossary
retrieval_matrix
features_heading
feature_glossary
feature_matrix
feature_details
response_heading
response_explainer
response_matrix
response_walkthroughs
response_tradeoffs
```

Use one visible heading block per chapter. The matrices must be semantic tables bound to the four new datasets. Put exact prompt excerpts, complete source-file inventories, and long per-team feature lists inside clearly labeled `<details>` blocks.

- [ ] **Step 6: Replace the three identified prose blobs with accessible card groups**

Use three short cards for the direct co-occurrence distinction:

```text
What our submitted path contained
Two CF/BPR behavioral centroid branches—anchor and user—plus discography and era-popularity lookups.

What the leaders documented
Direct track co-occurrence, artist/album history, sequential or Markov transitions, collaborative filtering, and train-frequency priors appeared in one or more released systems.

Why the matrix says Partial
Our centroids supplied related behavioral evidence, but centroid similarity is not a direct track co-occurrence mechanism and is not a sequential-transition lane.
```

Use a glossary-plus-inventory pattern for feature richness. The visible explanation must name retriever ranks/scores, dense similarity, collaborative and sequence signals, artist/album affinity, popularity/frequency priors, acoustic/genre/era matches, state/constraint matches, cross-retriever agreement, routing/shift indicators, and OOF/ensemble outputs before mentioning `69` or `176` features.

Use one short pipeline per team for response generation rather than one paragraph:

```text
Our submission: selected top-1 track → one grounded draft → final response
volart: generate candidates → independent critic → selective refinement → hardening → lexical pass
niwatori: generate ten seeded candidates → score/select for diversity → final response
swyoo: PAS-structured generation → validate/repair grounding → deterministic lexical stabilization
team2_s2: prompt with verified track facts → first draft → second-pass polish/refinement
```

Every pipeline must include a nearby evidence-status/source marker and a separate “What this stage buys” explanation.

- [ ] **Step 7: Add acknowledgements and strengthen the evidence boundary**

Add `acknowledgements_heading` and `acknowledgements` immediately before `caveats`. Credit and link:

- volart / `artvolgin/music-crs-recsys2026` for hybrid retrieval, validation, ranker, and editorial-pipeline detail;
- niwatori / `ryowk/recsys2026-niwatori` for the broad candidate union, history/transition features, rich reranker, and response selection detail;
- swyoo / `yoobros/music-crs-challenge` for leakage-safe folds, learned retrieval, generated/profile evidence, and grounded lexical response design;
- team2_s2 / `lopsandrea/music-crs-team2` for routed rankers, collaborative/acoustic evidence, shift weighting, verified facts, and two-pass response generation;
- the Music-CRS challenge organizers for the task, data, metrics, and final results.

State that this retrospective is possible because the teams released code and technical detail. Keep the tone appreciative and specific.

- [ ] **Step 8: Validate new datasets, block order, progressive disclosure, and retrospective scope**

Run:

```bash
node - <<'NODE'
const fs = require('fs');
const p = '/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json';
const a = JSON.parse(fs.readFileSync(p));
const ids = a.manifest.blocks.map(b => b.id);
const required = ['section_directory','lifecycle_heading','lifecycle_map','query_heading','query_matrix','data_knowledge_heading','data_knowledge_matrix','retrieval_heading','retrieval_matrix','features_heading','feature_matrix','response_heading','response_matrix','response_walkthroughs','acknowledgements_heading','acknowledgements'];
for (const id of required) if (!ids.includes(id)) throw Error(`missing block ${id}`);
for (const id of ['query_comparisons','data_knowledge_comparisons','feature_family_comparisons','response_comparisons']) if (!Array.isArray(a.snapshot.datasets[id]) || a.snapshot.datasets[id].length !== 5) throw Error(`dataset ${id}`);
const before = (aId,bId) => ids.indexOf(aId) < ids.indexOf(bId);
if (!before('section_directory','final_result_heading') || !before('query_heading','own_system_heading') || !before('acknowledgements','caveats')) throw Error('reading order');
const body = a.manifest.blocks.map(b => String(b.body || b.html || '')).join('\n');
for (const bad of [/recovery roadmap/i,/implementation roadmap/i,/assigned owner/i,/delivery milestone/i]) if (bad.test(body)) throw Error(`roadmap language: ${bad}`);
for (const phrase of ['What our submitted path contained','Why the matrix says Partial','generate ten seeded candidates','prompt with verified track facts']) if (!body.includes(phrase)) throw Error(`missing required explanation: ${phrase}`);
console.log('PASS: revised report structure and progressive disclosure are present');
NODE
```

Expected: `PASS: revised report structure and progressive disclosure are present`.

- [ ] **Step 9: Commit the structural and narrative revision in the artifact workspace**

Run:

```bash
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective add artifact.json
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective commit -m "docs: expand retrospective technical comparisons"
```

Expected: one commit containing only `artifact.json`.

---

### Task 3: Replace the Compressed Architecture Visuals

**Files:**
- Modify: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json`

**Interfaces:**
- Consumes: Existing diagram claims and the new lifecycle/query/response comparisons.
- Produces: Five full-width, responsive, semantic system diagrams using one shared visual grammar.

- [ ] **Step 1: Remove the known failing two-column/equal-slice CSS**

In `own_system_diagram`, `volart_diagram`, `niwatori_diagram`, `swyoo_diagram`, and `team2_s2_diagram`, remove patterns equivalent to:

```css
.rails { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.flow { grid-template-columns: repeat(var(--steps), minmax(0, 1fr)); }
```

The first pattern halves the available width; the second divides the remaining width by five or six and caused the vertical character stacks in the rejected rendering.

- [ ] **Step 2: Apply the full-width rail and stage-card contract**

Use this layout contract in each diagram HTML block, adapting only colors and content:

```css
.system-rails {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
}
.rail {
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 1rem;
}
.stage-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: .875rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.stage-card {
  min-width: 0;
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: .625rem;
}
.stage-card h4 {
  margin: 0;
  overflow-wrap: normal;
  word-break: normal;
  hyphens: none;
}
.stage-card ul {
  margin: 0;
  padding-inline-start: 1.1rem;
}
.stage-footer {
  align-self: end;
  border-top: 1px solid var(--line);
  padding-top: .5rem;
}
@media (max-width: 840px) {
  .stage-grid { grid-template-columns: repeat(2, minmax(220px, 1fr)); }
}
@media (max-width: 560px) {
  .stage-grid { grid-template-columns: minmax(0, 1fr); }
}
```

Use `<ol class="stage-grid">` with `<li class="stage-card">` children. Restore visible ordering with numbered step badges because `list-style` is visually suppressed. Put `Verified`, `Inferred`, or `Not documented` plus the source marker only in `.stage-footer`.

- [ ] **Step 3: Rewrite every stage as a short heading plus two to four bullets**

Use stage headings such as `Extract conversation state`, `Build candidate union`, `Rerank the pool`, `Generate response candidates`, and `Select and polish`. Do not put model names, counts, arrows, and status text into the heading when they can be bullets or footer metadata.

Every system must begin with a query stage and end with a response stage. Preserve different topologies:

- author: structured state → branch-specific queries → RRF pool → LightGBM → one response;
- volart: query rewrite/entity path → five retrieval lanes → RRF/69-feature ranker → candidate/critic/refine/harden/lexical path;
- niwatori: thought/tag/history query forms → fourteen-source ordered union → 176-feature ranker → ten-candidate selection;
- swyoo: generated/user-profile query evidence → pool/two-tower/OOF ranker path → PAS validate/repair/lexical path;
- team2_s2: conversation text and structured evidence → BGE/collaborative/acoustic sources → routed rankers → fact-grounded two-pass response.

- [ ] **Step 4: Validate diagram semantics and the layout contract before packaging**

Run:

```bash
node - <<'NODE'
const fs = require('fs');
const p = '/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json';
const a = JSON.parse(fs.readFileSync(p));
for (const id of ['own_system_diagram','volart_diagram','niwatori_diagram','swyoo_diagram','team2_s2_diagram']) {
  const b = a.manifest.blocks.find(x => x.id === id);
  const html = String(b.body || b.html || '');
  for (const required of ['system-rails','stage-grid','stage-card','stage-footer','<ol','max-width: 840px','max-width: 560px','minmax(220px, 1fr)']) if (!html.includes(required)) throw Error(`${id}: missing ${required}`);
  if (/repeat\(2,\s*minmax\(0,\s*1fr\)\)/.test(html) && html.includes('.rails')) throw Error(`${id}: side-by-side rails remain`);
  if (/repeat\(var\(--steps\)/.test(html)) throw Error(`${id}: equal stage slicing remains`);
  if (!/Verified|Inferred|Not documented/.test(html)) throw Error(`${id}: no evidence state`);
}
console.log('PASS: five semantic diagrams use full-width responsive rails');
NODE
```

Expected: `PASS: five semantic diagrams use full-width responsive rails`.

- [ ] **Step 5: Commit the diagram correction in the artifact workspace**

Run:

```bash
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective add artifact.json
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective commit -m "fix: make retrospective diagrams readable"
```

Expected: one commit containing only `artifact.json`.

---

### Task 4: Deepen the Five Team Case Studies and Cross-Team Synthesis

**Files:**
- Modify: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json`
- Read: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json`

**Interfaces:**
- Consumes: Normalized evidence datasets and corrected system diagrams.
- Produces: Five comparable technical walkthroughs, four detailed public-team case studies, reusable implementation-pattern notes, and balanced limits.

- [ ] **Step 1: Expand the author's case study using the public-team template**

Keep the existing `own_system_*`, `what_worked`, `evaluation_mistake`, `ranking_contributors`, and `response_contributors` IDs. Make the visible walkthrough answer:

1. How did conversation history become structured state and retriever-specific queries?
2. Which challenge data, generated state, external data, and latent model knowledge entered the submitted path?
3. Which candidate branches and constraints were used?
4. Which actual ranker feature families were present?
5. Which evaluation evidence was in-sample versus OOF?
6. How did the single-pass response path work, and what layers were not documented?

Preserve strengths: explicit state, multi-branch retrieval, useful CF/BPR centroids, multimodal and catalog evidence, a learned reranker, and honest constraints against overselling a poor fit.

- [ ] **Step 2: Expand every public-team case study with the same ten visible roles**

Within each existing six-block case-study group, make the visible content cover:

```text
Acknowledged contribution
Verified final outcome
Conversation-to-query path
Data and model knowledge
Retrieval and candidate construction
Ranker and feature families
Response-generation subsystem
What differed from our submission
Transferable implementation patterns
Limits and undocumented details
```

Do not add a feature simply because a README uses a large count. Name feature families and show their source/validation lineage. Do not say a team used external data or world knowledge unless the source role is documented.

- [ ] **Step 3: Make the cross-team tables answer distinct questions**

Keep `cross_team_matrix` as the high-level orientation table. Use the four new matrices for these non-overlapping questions:

- `query_matrix`: How did dialogue become one or more search representations?
- `data_knowledge_matrix`: Where did facts and descriptive knowledge come from, and were they verified?
- `feature_matrix`: What signals could the ranker learn from, and how were learned signals validated?
- `response_matrix`: How many stages/candidates existed after track selection, and what grounding/selection/repair occurred?

The high-level behavioral/co-occurrence cell for the author must remain `Partial`, with the three-card explanation from Task 2 adjacent to the matrix. Do not replace `Partial` with `No`.

- [ ] **Step 4: Add concrete reusable patterns without creating a recovery plan**

Each public-team case study must name two to four source-backed patterns a future project could study, such as:

- build retriever-specific query representations instead of one universal string;
- expose candidate-source scores and presence indicators to the ranker;
- carry direct co-occurrence and sequence signals separately from centroid similarity;
- generate learned features out of fold;
- rerank a broad union or combine specialized routed rankers;
- ground response prompts in verified track facts;
- generate multiple candidates only when a documented selector or critic uses them;
- preserve selected recommendation IDs through editorial passes;
- treat lexical diversity as a corpus-level scored property.

Phrase these as lessons and implementation patterns, not assigned work.

- [ ] **Step 5: Validate equal coverage, acknowledgements, and causal restraint**

Run:

```bash
node - <<'NODE'
const fs = require('fs');
const p = '/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json';
const a = JSON.parse(fs.readFileSync(p));
const byId = new Map(a.manifest.blocks.map(b => [b.id, String(b.body || b.html || '')]));
for (const team of ['volart','niwatori','swyoo','team2_s2']) {
  const text = ['heading','outcome','diagram','walkthrough','comparison','limits'].map(s => byId.get(`${team}_${s}`) || '').join('\n');
  for (const concept of ['query','feature','response','Not documented']) if (!new RegExp(concept,'i').test(text)) throw Error(`${team}: missing ${concept}`);
}
const all = [...byId.values()].join('\n');
for (const credit of ['artvolgin/music-crs-recsys2026','ryowk/recsys2026-niwatori','yoobros/music-crs-challenge','lopsandrea/music-crs-team2','challenge organizers']) if (!all.toLowerCase().includes(credit.toLowerCase())) throw Error(`acknowledgement: ${credit}`);
for (const bad of [/caused the Blind-B gap/i,/proves that/i,/would have recovered/i]) if (bad.test(all)) throw Error(`causal overclaim: ${bad}`);
console.log('PASS: team case studies are balanced, credited, and evidence-bounded');
NODE
```

Expected: `PASS: team case studies are balanced, credited, and evidence-bounded`.

- [ ] **Step 6: Commit the case-study revision in the artifact workspace**

Run:

```bash
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective add artifact.json
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective commit -m "docs: deepen retrospective team case studies"
```

Expected: one commit containing only `artifact.json`.

---

### Task 5: Reconcile the Analysis and Package the Root-Level HTML

**Files:**
- Read: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json`
- Read: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json`
- Generate: `retrospective.html`
- Generate on failure only: `/tmp/music-crs-retrospective-verification-failure.png`

**Interfaces:**
- Consumes: Completed canonical artifact and evidence ledger.
- Produces: Verified self-contained `retrospective.html` at repository root.

- [ ] **Step 1: Independently reconcile all published composites and signed gap terms**

Run:

```bash
node - <<'NODE'
const fs = require('fs');
const p = '/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json';
const e = JSON.parse(fs.readFileSync(p));
const mine = e.leaderboard.find(x => x.entry === 'npatta01');
for (const r of e.leaderboard) {
  const composite = .5*r.ndcg20 + .1*r.catalogDiversity + .1*r.lexicalDiversity + .3*(r.llmJudge-1)/4;
  if (Math.abs(composite-r.composite) > 2e-9) throw Error(`composite ${r.entry}`);
}
for (const g of e.gapContributions) {
  const sum = g.ndcg20 + g.llmJudge + g.lexicalDiversity + g.catalogDiversity;
  const row = e.leaderboard.find(x => x.entry === g.entry);
  if (Math.abs(sum-g.totalGap) > 2e-9) throw Error(`gap terms ${g.entry}`);
  if (Math.abs((row.composite-mine.composite)-g.totalGap) > 2e-9) throw Error(`gap total ${g.entry}`);
}
console.log('PASS: five composites and four signed score gaps reconcile');
NODE
```

Expected: `PASS: five composites and four signed score gaps reconcile`.

- [ ] **Step 2: Validate the final canonical artifact against the approved design**

Run:

```bash
node - <<'NODE'
const fs = require('fs');
const aPath = '/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json';
const a = JSON.parse(fs.readFileSync(aPath));
const ids = new Set(a.manifest.blocks.map(b => b.id));
const required = ['executive_summary','section_directory','leaderboard_table','gap_contribution_chart','lifecycle_map','query_matrix','data_knowledge_matrix','retrieval_matrix','feature_matrix','response_matrix','own_system_diagram','volart_diagram','niwatori_diagram','swyoo_diagram','team2_s2_diagram','preserve_reconsider_avoid','acknowledgements','caveats','evidence_notes'];
for (const id of required) if (!ids.has(id)) throw Error(`missing ${id}`);
for (const [id,rows] of Object.entries(a.snapshot.datasets)) if (!Array.isArray(rows)) throw Error(`dataset ${id}`);
if (a.surface !== 'report') throw Error('surface');
if (!a.manifest.title) throw Error('title');
const body = a.manifest.blocks.map(b => String(b.body || b.html || '')).join('\n');
for (const label of ['Verified','Inferred','Not documented']) if (!body.includes(label)) throw Error(`missing status ${label}`);
for (const term of ['external structured','generated artifacts','latent LLM world knowledge','conversation-to-query','response generation']) if (!body.toLowerCase().includes(term.toLowerCase())) throw Error(`missing concept ${term}`);
console.log(`PASS: canonical artifact has ${a.manifest.blocks.length} blocks and ${Object.keys(a.snapshot.datasets).length} datasets`);
NODE
```

Expected: `PASS: canonical artifact has 74 blocks and 8 datasets`.

- [ ] **Step 3: Package and browser-verify the canonical artifact directly to repository root**

Run:

```bash
node /home/npatta01/.codex/plugins/cache/openai-curated-remote/data-analytics/0.2.8-13ceeea1f599/skills/build-report/scripts/deliver_portable_artifact.mjs \
  --input /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json \
  --output /home/npatta01/data/competitions/music-conversational-music-recomender-2026/retrospective.html \
  --screenshot /tmp/music-crs-retrospective-verification-failure.png
```

Expected receipt:

```text
validation: passed
packaging: passed
verification: passed
```

The verifier must report desktop and narrow viewport checks, zero external requests, no overflow, no zero-size required blocks, no browser errors, and exact embedded-payload equality. If it fails, patch `artifact.json` and rerun this same command; never patch generated `retrospective.html`.

- [ ] **Step 4: Verify the generated file is self-contained and contains the corrected report**

Run:

```bash
test -s retrospective.html
rg -n "Music-CRS Blind-B|Conversation to query|Data and model knowledge|Response generation|Acknowledgements" retrospective.html
if rg -n "repeat\(var\(--steps\)|music-crs-2026/" retrospective.html; then exit 1; fi
```

Expected: the five report headings match; the rejected equal-slice CSS and unwanted subfolder path do not.

---

### Task 6: Link the Report, Perform Final QA, and Commit the Repository Artifact

**Files:**
- Modify: `readme.md`
- Verify: `retrospective.html`

**Interfaces:**
- Consumes: Verified root-level HTML from Task 5.
- Produces: Discoverable report and a minimal repository diff containing only the intended retrospective deliverables and approved documentation.

- [ ] **Step 1: Add the report link near the top of `readme.md`**

Use `apply_patch` to insert this line after the challenge/dataset/scores link list and before the first horizontal rule:

```markdown
- **Competition retrospective**: [what we built, where we fell short, and what the leading public teams did differently](retrospective.html)
```

Do not duplicate the project introduction or create a new report directory.

- [ ] **Step 2: Run repository-level acceptance checks**

Run:

```bash
git diff --check -- readme.md retrospective.html
test -f retrospective.html
test ! -d music-crs-2026
rg -n "Competition retrospective.*retrospective\.html" readme.md
rg -n "artvolgin/music-crs-recsys2026|ryowk/recsys2026-niwatori|yoobros/music-crs-challenge|lopsandrea/music-crs-team2" retrospective.html
git status --short
```

Expected:

- `retrospective.html` exists and is non-empty;
- `readme.md` contains exactly one report link;
- all four public repositories appear in acknowledgements;
- no `music-crs-2026/` directory exists;
- only `readme.md` and `retrospective.html` are the new implementation changes in the project repository;
- the pre-existing untracked `.repro/` directory and reproduction archives remain untouched.

- [ ] **Step 3: Confirm artifact-workspace and project-workspace cleanliness separately**

Run:

```bash
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective status --short
git status --short
```

Expected: the artifact workspace is clean; the project workspace shows only the two intended implementation files plus the user's pre-existing untracked reproduction artifacts.

- [ ] **Step 4: Commit only the root report and README link**

Run:

```bash
git add -- readme.md retrospective.html
git commit -m "docs: add Music-CRS competition retrospective"
```

Expected: the commit includes only `readme.md` and `retrospective.html`.

- [ ] **Step 5: Verify the committed handoff**

Run:

```bash
git show --stat --oneline --summary HEAD
git diff HEAD^ --name-only
git status --short --branch
```

Expected changed paths:

```text
readme.md
retrospective.html
```

The final status may still show the user's unrelated `.repro/` directory and reproduction archives as untracked; they must not be staged, modified, or removed.
