# Music-CRS Approach-Only Deck — Design Spec

**Date:** 2026-07-15

**Status:** Approved in conversation

**Audience:** Music-CRS competition organizers and participants

**Artifact:** `docs/approach.html`

## 1. Purpose

Turn the current combined approach/RCA report into a focused explanation of
what the team submitted and how it works. An organizer should understand the
system from the opening architecture map and be able to complete the visible
deck in a few minutes without entering failure analysis.

The existing RCA artifact remains separate and unchanged. `approach.html` must
not duplicate its failure gallery, root-cause analysis, gap map, or lessons.

## 2. Content boundary

The approach deck answers only:

1. What is the final submitted architecture?
2. How does a conversation become typed state?
3. How does state become retrieval work and a candidate pool?
4. How does the final LightGBM model order candidates?
5. What crosses the top-one response-generation handoff?
6. How are ranking and response quality evaluated?
7. Why are selected workloads local, hosted, or on Modal?
8. How can another participant inspect or reproduce the system?

The deck contains one verified successful walkthrough as a concrete teaching
example. It does not include a gallery of successes, failure traces, RCA,
capability gaps, or proposed remediations.

## 3. Slide order

The HTML remains one vertically scrolling document, with each section behaving
like one slide and carrying one primary visual:

1. **System in one minute** — online serving path and separate offline
   evaluation loop.
2. **One successful turn** — the verified frozen-devset “Pumped Up Kicks”
   conversation, state, rank path, top pick, and response provenance.
3. **Typed conversation state** — extractor prompt intent, V1 state, V0Plus
   projection, entity roles, constraints, and routing.
4. **Retrieval and candidate assembly** — query compiler, specialist branches,
   fired/skipped behavior, candidate filtering, internal branch combination,
   and backfill.
5. **Final learned ranking** — `ranking.mode: lgbm`, feature families,
   `b1_cos`, LambdaMART ordering, and final artist guard.
6. **Top-one response handoff** — selected item, state context, production
   prompt excerpt, and grounded listener-facing response.
7. **Evaluation** — ranking metrics and LLM-as-judge response evaluation as
   distinct lenses; the judge does not rank serving tracks.
8. **Compute placement** — local orchestration/caches, hosted APIs, Modal model
   workloads, and staged replay. This remains supporting system information.
9. **Reproduce and inspect** — active config, schemas, prompts, compiler,
   retrievers, ranker bundle, commands, glossary, and evidence boundary.

The sticky directory uses exactly these nine destinations. Compute appears
after evaluation so infrastructure never interrupts the serving explanation.

## 4. Opening contract

The first screen keeps the reviewed organizer-first architecture:

```text
conversation
  -> LLM state extraction
  -> V1-to-V0Plus projection
  -> entity resolution
  -> query compiler
  -> specialist retrieval mesh
  -> candidate pool assembly
  -> LightGBM LambdaMART
  -> final artist guard
  -> top 20
  -> top-1 explanation
```

The offline lane remains visually separate:

```text
saved traces and staged replay
  -> ranking metrics
  -> LLM-as-judge response evaluation
  -> next experiment
```

The overview must preserve three explicit invariants:

- retrieval sets the candidate ceiling;
- LightGBM determines the submitted final order;
- generation explains rank one and cannot choose another track.

The frozen-devset example remains visibly scoped and must not be attributed to
the submitted LightGBM path when its evidence does not identify that ranker.

## 5. Progressive disclosure

Organizers can read the complete approach without opening disclosures. Native
`details` elements retain exact prompts, full state JSON, compiled queries,
branch inventories, full top 20, source excerpts, and reproduction detail.

Visible paragraphs should explain the stage contract and result, not restate
the full audit trail. Every slide should fit one coherent visual story rather
than becoming a wall of cards.

## 6. Accuracy and evidence

- `configs/state_ranker_v10_lgbm_blindset_B.yaml` is the final configuration
  source of truth.
- The compiler's weighted-RRF mechanics are internal candidate-pool assembly,
  not the final ranker.
- LightGBM determines the delivered ordering, followed by the same-turn artist
  guard.
- The response model explains the already selected rank-one track.
- LLM-as-judge is an evaluation mechanism and does not select or rank tracks.
- Frozen-devset outcome evidence and submitted Blind-B mechanics remain clearly
  separated.
- Ignored local artifacts may appear as non-clickable provenance paths, never
  as broken publication links.

## 7. Visual and interaction design

- Preserve the warm editorial visual system and native HTML/CSS diagrams.
- Keep the wide architecture path on desktop, a reflowed tablet layout, and a
  vertical mobile path.
- Keep horizontal sticky navigation on desktop and contained horizontal
  scrolling on mobile.
- Remove CSS and validation contracts used only by the deleted RCA/gap slides.
- No decorative bitmap imagery, external runtime resources, or JavaScript-only
  content.
- Preserve keyboard focus, contrast, reduced-motion, print, and semantic table
  behavior.

## 8. Implementation boundary

Remove these sections from `docs/approach/source.html` and the generated report:

- `section#examples`
- `section#gaps`
- `section#lessons`

Update the report validator's required section order to:

```text
overview, walkthrough, state, compile, ranking, response,
evaluation, infrastructure, reproduce
```

Remove validator requirements for gap-status pills because gaps no longer
belong in this artifact. Keep evidence-status validation and all resource,
anchor, containment, and self-contained-output checks.

The canonical source remains `docs/approach/source.html`; regenerate
`docs/approach.html` only through `scripts/build_approach_report.py`.

## 9. Success criteria

The approach deck is complete when:

1. the first-minute architecture is accurate and readable at desktop, tablet,
   and mobile widths;
2. one verified successful turn makes the stage contracts concrete;
3. every visible chapter explains submitted-system mechanics rather than RCA;
4. no examples gallery, failure trace, gap map, or lessons section remains;
5. navigation contains only the nine approach slides;
6. the report remains self-contained and all publication-facing links are
   valid;
7. focused report tests, the structural validator, the full project suite, and
   desktop/mobile visual inspection pass before PR update.
