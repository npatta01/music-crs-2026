# Blind-B Retrospective Report — Design Spec

**Date:** 2026-07-12
**Status:** Written design pending user review
**Audience:** Personal retrospective
**Delivery:** Private, self-contained HTML report

## 1. Purpose

Create a detailed but accessible retrospective explaining why the final Music-CRS
Blind-B submission underperformed the leading public-code systems. The report is
for the author's own future reference, so it should be candid about mistakes,
preserve the technical evidence, and turn the comparison into reusable lessons.

The report must answer four questions:

1. What happened on the final leaderboard?
2. Which decisions most likely caused the gap?
3. What did the leading teams do better?
4. Which lessons are worth carrying into future ML competitions?

## 2. Reader and tone

The report will use plain language and define specialized terms before relying on
them. It will be written as a constructive first-person retrospective rather than
an external audit or blame-oriented postmortem.

The tone should be:

- honest about methodological mistakes;
- specific about verified evidence;
- respectful toward the work that was done well;
- clear about the difference between facts, inferences, and unknowns;
- focused on transferable lessons rather than hindsight criticism.

## 3. Report structure

The HTML report will follow this reading path:

1. **Title and Executive Summary** — the short answer and the two main causes.
2. **How the challenge was scored** — an accessible explanation of nDCG,
   diversity, the LLM judge, and the composite formula.
3. **The final result** — exact metrics for this submission and the four leading
   public-code entries.
4. **What my system actually built** — a concise explanation of state extraction,
   retrieval branches, RRF, LightGBM reranking, and response generation, paired
   with a labeled end-to-end architecture visual.
5. **What worked** — candidate coverage, traceability, multimodal breadth,
   reproducibility, and other strengths worth retaining.
6. **The central evaluation mistake** — why training on all labeled dev turns and
   then reporting performance on those turns produced an in-sample number rather
   than a generalization estimate.
7. **Why ranking underperformed** — limited ranker training population, candidate
   truncation, missing sequential/co-occurrence lanes, and underuse of the trained
   bi-encoder.
8. **Why response generation underperformed** — Blind-A template selection did
   not generalize, responses were under-grounded, and a single deterministic pass
   lacked the leaders' selection and critique stages.
9. **Four competitor case studies** — separate, detailed sections for volart,
   niwatori, swyoo, and team2_s2. Each case study will combine an architecture
   visual, an accessible technical walkthrough, the team's distinctive choices,
   and a clear comparison with my system.
10. **Cross-team synthesis** — a side-by-side matrix showing which teams used
    behavioral retrieval, learned retrieval, leakage-safe validation, rich
    reranker features, generation sampling, factual grounding, and response
    selection or critique.
11. **What I would preserve and what I would reconsider** — retrospective
    judgments about the current architecture, without turning them into an
    implementation roadmap.
12. **Lessons for future ML competitions** — reusable principles about clean
    validation, public-leaderboard overfitting, simple behavioral signals, and
    optimizing every scored component.
13. **Caveats and evidence** — the limits imposed by an 80-session hidden set and
    the absence of per-session Blind-B labels.

## 4. Evidence and calculations

The report will use:

- the official final-results CSV;
- `origin/main` at commit `2ecc45a` for the local system;
- the deployed Blind-B config and reranker bundle metadata;
- the reranker training protocol and documented OOF results;
- the exact submitted Blind-B responses;
- the current public `main` branches of the four competitor repositories.

The composite gap will be independently reconciled using:

`0.50 × nDCG@20 + 0.10 × catalog diversity + 0.10 × lexical diversity + 0.30 × (judge − 1) / 4`

Claims will be labeled using three evidence levels:

- **Verified:** directly supported by leaderboard data, code, artifacts, or docs.
- **Strong inference:** supported by architecture differences and released
  ablations, but not provable per Blind-B session.
- **Unknown:** requires hidden labels or experiments that are not available.

## 5. Visual design

The report will be a responsive, single-column document that remains readable on
phones and through remote file access. It will include:

- a compact headline metric strip after the Executive Summary;
- a stacked bar chart decomposing each competitor's composite lead into ranking,
  LLM-judge, lexical-diversity, and catalog-diversity contributions;
- an exact leaderboard comparison table;
- a detailed visual of my own pipeline so the comparisons have a common baseline;
- one detailed architecture visual for each of the four competitor systems;
- a cross-team comparison matrix using the same categories for every system;
- a retrospective table separating choices to preserve, reconsider, and avoid in
  future competitions.

The five architecture visuals will share one visual grammar so they can be read
side by side. Each will show, where the public evidence permits:

1. how the conversation is represented;
2. the candidate-generation or retrieval lanes;
3. candidate fusion and reranking;
4. the training and validation strategy relevant to ranking;
5. response generation, sampling, grounding, and selection;
6. the design choice that most clearly distinguished that system.

The competitor visuals will be detailed enough to explain the actual approach,
but they will not imply that undocumented implementation details are known.
Verified components will use solid styling, strong inferences will use dashed
styling, and unknowns will be omitted or explicitly labeled. On narrow screens,
each pipeline will stack vertically rather than require horizontal scrolling.

The visual emphasis for each case study will be:

- **My system:** state extraction, retrieval branches, RRF pool construction,
  the 500-candidate reranker boundary, `b1_cos`, LightGBM, and the single-pass
  response generator.
- **volart:** five retrieval lanes, track co-occurrence and priors, 69-feature
  LambdaMART, disjoint validation, and best-of-three generation followed by
  critic/refine stages.
- **niwatori:** fourteen candidate sources, out-of-fold two-tower retrieval,
  history artist/album and transition signals, a 176-feature ranker, and ten
  response candidates selected for diversity.
- **swyoo:** five-fold QLoRA two-tower training, leakage-safe out-of-fold
  features, regularized LightGBM, and the PAS response strategy with lexical
  stabilization.
- **team2_s2:** multiple BGE retrievers, collaborative and acoustic evidence,
  routed LightGBM plus CatBoost, blind-like shift weighting, and two-pass
  fact-grounded Gemini generation.

Charts will use restrained colors, explicit units, direct labels where practical,
and a semantic table fallback so the report remains understandable without
JavaScript. Every visual will have adjacent prose explaining what it shows and why
it matters.

## 6. Delivery and privacy

The result will be one self-contained HTML file built through the Data Analytics
portable-report workflow. It will embed its reviewed data and source metadata, make
no network calls at viewing time, and require no local server. It will remain local
and private; it will not be published, deployed, or given public sharing settings.

The canonical report artifact will live outside the tracked project source unless
the user later requests that the finished retrospective be checked into the repo.

## 7. Quality checks

Before handoff, the report must pass these checks:

- the opening summary directly answers what went wrong;
- uncommon terms are defined on first use;
- every important number reconciles with the official formula;
- verified facts and inferences are visibly distinguishable;
- the report acknowledges what the system did well;
- each competitor is compared using the same dimensions;
- retrospective conclusions follow from the evidence and avoid prescribing new
  implementation work;
- the HTML is self-contained and passes the packaged artifact validator;
- desktop and narrow-width verification passes when a compatible browser is
  available, with structural verification as the documented fallback.

## 8. Non-goals

This report will not:

- implement ranking or response-generation changes;
- prescribe a recovery plan or post-competition implementation roadmap;
- claim per-session Blind-B root causes without labels;
- treat longer responses as automatically better;
- present architectural differences as causal proof when only correlation is
  available;
- publish or share the report externally.
