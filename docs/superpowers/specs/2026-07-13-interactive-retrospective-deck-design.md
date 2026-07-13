# Interactive Retrospective Deck Design

**Date:** 2026-07-13
**Status:** Approved interaction direction; written specification pending final review
**Target:** repository-root `retrospective.html` on `codex/retrospective-report`

## Purpose

Turn the complete Music-CRS retrospective into a less intimidating, explorable two-dimensional chapter deck without deleting, weakening, or duplicating its evidence.

The reader moves horizontally between seven major questions and vertically through increasing depth inside each chapter. Every chapter begins with a short answer. Detailed matrices, prompts, feature inventories, and audit evidence remain available through explicit disclosure controls and direct navigation.

## Success criteria

- The final deliverable remains one self-contained `retrospective.html` at repository root.
- All 74 canonical report blocks, eight datasets, ten sources, calculations, diagrams, acknowledgements, caveats, and evidence links remain available.
- Horizontal navigation changes major chapters.
- Vertical navigation moves through the current chapter's overview, analysis, and audit sub-slides.
- A searchable jump palette reaches every chapter and sub-slide directly.
- URL hashes make every location bookmarkable and restore browser back/forward behavior.
- Desktop, keyboard, trackpad, touch, reduced-motion, narrow-screen, linear-reading, and print use cases remain supported.
- The report makes no network requests and requires no server after the HTML file has been generated.
- The interaction layer introduces no new factual claims and does not alter `artifact.json` or `evidence.json` unless a separately reviewed content correction is required.

## Non-goals

- Do not shorten the retrospective by deleting technical or evidentiary detail.
- Do not turn the retrospective into a recovery roadmap, work plan, or new competition proposal.
- Do not create a wrapper directory such as `music-crs-2026/`.
- Do not require Reveal.js, a CDN, a framework runtime, external fonts, analytics, or remote assets.
- Do not publish, deploy publicly, or change repository sharing.
- Do not replace the report with screenshots or rasterized slides.

## Chosen interaction model

### Two-dimensional chapter deck

The approved model has seven horizontal chapters. Each chapter contains a vertical stack of sub-slides. Horizontal scroll snap is mandatory at chapter boundaries; vertical snap is proximity-based so long technical content still scrolls naturally.

The interface exposes four equivalent navigation methods:

1. horizontal/vertical trackpad or touch gestures;
2. left/right and up/down arrow keys;
3. persistent previous/next controls;
4. a searchable jump palette.

Each sub-slide opens with its existing heading or takeaway. Dense content uses progressive disclosure rather than being removed.

## Chapter and block map

Every canonical block is assigned exactly once. The build must fail if a configured block is missing, duplicated, or left unassigned.

### Chapter 1 — Outcome and score

**Question:** What happened, and which metric terms made the gap?

1. **Executive answer**
   - `title`
   - `executive_summary`
   - `headline_metrics`
   - `section_directory` — retained as a collapsed original outline because the jump palette supersedes it in deck mode
2. **Official result**
   - `how_scoring_works`
   - `final_result_heading`
   - `leaderboard_chart`
   - `leaderboard_table`
3. **Gap decomposition**
   - `gap_contribution_chart`
   - `gap_interpretation`

### Chapter 2 — Conversation to query

**Question:** How did each system turn dialogue into retriever inputs?

1. **Shared lifecycle**
   - `lifecycle_heading`
   - `lifecycle_map`
   - `lifecycle_takeaway`
2. **Query comparison**
   - `query_heading`
   - `query_explainer`
   - `query_matrix`
3. **Data and model knowledge**
   - `data_knowledge_heading`
   - `data_knowledge_glossary`
   - `data_knowledge_matrix`
   - `data_knowledge_interpretation`
4. **Prompt and file audit**
   - `query_evidence_details`

### Chapter 3 — Retrieval and ranking

**Question:** What candidates and features could the rankers actually see?

1. **Retriever inputs and constraints**
   - `retrieval_heading`
   - `retrieval_glossary`
   - `retrieval_matrix`
2. **Feature families and validation lineage**
   - `features_heading`
   - `feature_glossary`
   - `feature_matrix`
3. **Complete feature inventories**
   - `feature_details`

### Chapter 4 — Response generation

**Question:** How did a selected track become grounded, checked prose?

1. **Response subsystem overview**
   - `response_heading`
   - `response_explainer`
2. **Five-team response matrix**
   - `response_matrix`
3. **Generation, selection, and repair pipelines**
   - `response_walkthroughs`
4. **Trade-offs and source boundary**
   - `response_tradeoffs`

### Chapter 5 — Our submission

**Question:** What did we build, what worked, and where did confidence fail?

1. **System diagram**
   - `own_system_heading`
   - `own_system_diagram`
2. **Complete walkthrough**
   - `own_system_walkthrough`
3. **What worked**
   - `what_worked`
4. **Evaluation mistake**
   - `evaluation_mistake`
5. **Best-supported contributors**
   - `ranking_contributors`
   - `response_contributors`

### Chapter 6 — Leading teams

**Question:** What did the leading public systems document differently?

1. **Case-study index**
   - `competitor_case_studies_heading`
2. **volart**
   - `volart_heading`
   - `volart_outcome`
   - `volart_diagram`
   - `volart_walkthrough`
   - `volart_comparison`
   - `volart_limits`
3. **niwatori**
   - `niwatori_heading`
   - `niwatori_outcome`
   - `niwatori_diagram`
   - `niwatori_walkthrough`
   - `niwatori_comparison`
   - `niwatori_limits`
4. **swyoo**
   - `swyoo_heading`
   - `swyoo_outcome`
   - `swyoo_diagram`
   - `swyoo_walkthrough`
   - `swyoo_comparison`
   - `swyoo_limits`
5. **team2_s2**
   - `team2_s2_heading`
   - `team2_s2_outcome`
   - `team2_s2_diagram`
   - `team2_s2_walkthrough`
   - `team2_s2_comparison`
   - `team2_s2_limits`

### Chapter 7 — Synthesis and evidence

**Question:** What should the team preserve, reconsider, avoid, and credit?

1. **Cross-team synthesis**
   - `cross_team_heading`
   - `cross_team_matrix`
2. **Retrospective choices**
   - `preserve_reconsider_avoid`
   - `retrospective_choices_table`
3. **Transferable lessons**
   - `future_competition_lessons`
4. **Acknowledgements**
   - `acknowledgements_heading`
   - `acknowledgements`
5. **Caveats and complete evidence**
   - `caveats`
   - `evidence_notes`
   - the portable report's complete source list, which is outside the 74-block manifest

## Interface anatomy

### Persistent top bar

- report title;
- current chapter and sub-slide breadcrumb;
- chapter/sub-slide progress;
- Jump button;
- Linear view toggle.

### Chapter rail

- desktop: visible chapter labels or compact chapter progress across the top;
- narrow screens: current chapter label plus previous/next controls;
- left/right movement updates the URL hash and focus target.

### Vertical rail

- desktop: visible numbered dots for the current chapter's sub-slides;
- mobile: compact `n of m` indicator;
- labels appear on hover/focus and remain available to screen readers.

### Jump palette

- opens from the Jump button, `Ctrl/Cmd+K`, or `J` when focus is not in a form control;
- lists all seven chapters and every sub-slide;
- filters by chapter, team, topic, and sub-slide title;
- moves focus to the selected sub-slide and closes;
- closes with Escape and returns focus to the opener.

### Previous and next controls

- bottom-edge controls name the neighboring chapter or sub-slide;
- controls remain available when scroll gestures are unavailable or ambiguous;
- reaching the last vertical sub-slide does not silently change horizontal chapters.

## Scrolling behavior

- The deck is a horizontal scroll container with `scroll-snap-type: x mandatory`.
- Every chapter is a full-width column containing a vertical scroll container.
- Vertical stacks use `scroll-snap-type: y proximity`, not mandatory, so tall matrices and prose scroll naturally.
- Trackpad/touch horizontal gestures change chapters; ordinary wheel/touch vertical gestures move within a chapter.
- Arrow keys navigate only when focus is not inside an interactive control, table scroller, disclosure, or iframe.
- Tables retain their own horizontal overflow. A gesture that begins in a table does not change chapters until the table reaches its horizontal edge.
- Motion is immediate rather than animated when `prefers-reduced-motion: reduce` is active.

## Progressive disclosure

The deck may wrap existing blocks but must not rewrite their factual content.

- Short-answer and heading blocks remain visible.
- Full comparison tables, prompt excerpts, feature inventories, audit details, caveats, and the complete source list may be collapsed by default behind descriptive controls.
- Controls say what they reveal, such as `Open the complete five-team feature matrix`; they do not use vague labels such as `More`.
- A direct hash to collapsed content opens the disclosure before focusing it.
- Linear and print views show the complete report in original order.

## Deep links and history

Canonical hashes use readable chapter/sub-slide slugs, for example:

- `#outcome/summary`
- `#query/data-knowledge`
- `#retrieval/features`
- `#response/pipelines`
- `#ours/evaluation-mistake`
- `#leaders/volart`
- `#synthesis/caveats-evidence`

Navigation pushes browser history only after the destination settles. Intermediate scroll events replace the current hash to avoid flooding history. Invalid hashes resolve to `#outcome/summary` without displaying an error page.

## Accessibility

- A skip link moves directly to the current sub-slide.
- Chapters and sub-slides use semantic `section` elements with labelled headings.
- The current location uses `aria-current` and an unobtrusive live-region announcement.
- Every control is keyboard reachable and has a visible focus style.
- Focus moves only after explicit navigation; passive scrolling does not steal focus.
- Iframes retain descriptive titles and do not receive deck-level arrow shortcuts while focused.
- Status is communicated with text and structure, never color alone.
- Touch targets are at least 44 by 44 CSS pixels on narrow screens.
- The deck respects reduced motion, forced colors, zoom, and 200% text scaling.

## Mobile behavior

- The active chapter occupies the viewport width.
- The top bar reduces to chapter title, progress, Jump, and Linear view.
- The vertical rail becomes an `n of m` indicator.
- Horizontal swipe remains available outside nested horizontal table scrollers.
- Previous/next buttons remain visible after every sub-slide.
- Dense tables and diagrams scroll within bounded cards rather than widening the page.

## Linear and print modes

The original portable fallback is the progressive-enhancement baseline.

- `?view=linear` and the Linear view control disable deck layout while preserving the same grouped DOM content.
- If the deck script fails, the fallback remains visible as a conventional linear report.
- Print CSS removes deck chrome, disclosures, fixed heights, and scroll snapping; it expands all report content into the original reading order.
- The dynamic portable reader remains embedded for payload reproducibility but is hidden while the fallback-based deck is active.

## Build architecture

### Sources of truth

1. canonical report content: artifact workspace `artifact.json` and `evidence.json`;
2. interaction mapping and behavior: one tracked deck-enhancer script in the project repository;
3. generated deliverable: root `retrospective.html`.

### Build flow

1. Run the existing portable builder from canonical `artifact.json` to produce the verified linear HTML.
2. Run the deterministic deck enhancer against that file.
3. The enhancer validates the block map, injects scoped inline CSS and JavaScript, and writes the same output path atomically.
4. Run structural and browser acceptance checks against the enhanced file.

The enhancer must not parse or rewrite prose, tables, charts, source URLs, iframe `srcdoc`, the compressed artifact payload, or the portable runtime. It only:

- validates and groups existing `data-artifact-block-id` elements;
- moves the portable source list into the final evidence sub-slide;
- adds deck navigation metadata and controls;
- wraps configured dense blocks in accessible disclosures;
- injects scoped deck CSS and behavior.

The enhancer contains no timestamp or environment-specific path, so identical input produces identical output.

## Failure handling

- Missing, duplicate, or unassigned manifest block: fail the build with the exact block ID.
- Duplicate chapter/sub-slide slug: fail the build.
- Missing portable fallback, block stack, source list, or payload template: fail the build.
- Invalid runtime hash: navigate to the overview and replace the bad hash.
- Unsupported scroll snap: navigation buttons, jump palette, and linear view remain functional.
- Script initialization failure: leave the complete linear fallback visible.

## Verification strategy

### Source and build checks

- canonical artifact still has 74 blocks, eight datasets, and ten sources;
- the chapter map assigns every block exactly once;
- all configured block IDs exist in generated HTML;
- the enhanced report contains every original block ID and external evidence URL exactly as required;
- compressed artifact payload is byte-equal to the portable builder output;
- enhancer output is deterministic across two builds;
- only the reader-facing root `retrospective.html` is generated.

### Browser checks

Run at desktop and narrow/mobile widths:

- horizontal chapter navigation by buttons, keys, and programmatic scroll;
- vertical sub-slide navigation and natural scrolling of tall content;
- jump palette opening, filtering, selection, Escape handling, and focus return;
- valid and invalid deep links;
- browser back/forward;
- disclosure controls and direct links into collapsed content;
- table and diagram overflow isolation;
- source links remain native top-document anchors;
- visible focus, skip link, live-region behavior, and iframe keyboard isolation;
- reduced-motion behavior;
- linear view and print layout;
- no browser errors, zero external requests, and no unintended body overflow.

### Regression checks

- five composite scores and four signed score gaps still reconcile;
- all normalized five-team evidence projections remain unchanged;
- all four public repositories and the organizers remain acknowledged;
- the metadata-echo retry boundary remains correctly described;
- the full project test suite still passes;
- both the canonical artifact repository and project worktree are clean after commits.

## Delivery

- Replace the current root `retrospective.html` on the feature branch after verification.
- Preserve the existing `readme.md` link.
- Restart the private LAN/Tailscale preview server so it serves the enhanced file.
- Do not merge, push, publish, or remove the isolated worktree without a separate user choice.
