# Visual-First Retrospective Pagination Design

**Status:** Proposed for user review

**Supersedes:** The page-density and embedded-content layout portions of `2026-07-13-interactive-retrospective-deck-design.md`. The seven horizontal chapters, canonical evidence, hashes, accessibility contract, linear fallback, and local-only delivery remain in force.

## Objective

Turn the current retrospective into a visual-first, content-aware deck of at least 50 vertical pages, starting with the specified 50-page structure and adding pages only when evidence needs a cleaner split. Each page should communicate one idea without cropped content, nested vertical scrollbars, intimidating walls of prose, or unused canvas. The report must still preserve all 74 canonical blocks, ten source records, commit-pinned acknowledgements, calculations, and evidence boundaries.

## Diagnosed layout failure

The current deck applies one page template to incompatible content types:

- every page has a viewport-height minimum and the same 1,180px content cap;
- custom HTML remains inside fixed-height sandboxed iframes;
- tables and diagrams therefore scroll inside a small box while the outer page remains mostly empty;
- wide matrix cells do not reflow enough, so meaningful columns are clipped;
- long audit content receives the same page treatment as short summaries.

The redesign must correct the shared layout system rather than add per-screenshot height patches.

## Design principles

1. **One page, one idea.** A normal page contains one primary visual or one primary evidence object, followed by no more than roughly 120–140 visible words.
2. **Visual first.** Conceptual pages lead with an image, chart, diagram, or compact comparison before explanatory prose.
3. **Evidence follows interpretation.** A short visual explanation may point down to the next page containing the complete matrix, audit, or calculation.
4. **One vertical scroller.** The active chapter owns vertical scrolling. No iframe, card, diagram, audit, or disclosure may introduce a second vertical scrollbar.
5. **Full canvas for evidence.** Tables and diagrams may use up to 1,520px on large screens. Narrative prose remains limited to about 78 characters per line.
6. **No factual compression by omission.** Visual summaries never replace the exact evidence; they provide a faster entry point to it.
7. **Images do not carry unique claims.** Every factual statement shown visually also appears in accessible HTML text, a chart data table, or the following evidence page.

## Visual language

### Explanatory visual systems

Visuals exist to explain what each system does—not to add abstract atmosphere. Prefer deterministic, report-native diagrams with exact HTML labels:

- chapter covers use a compact map of the chapter's evidence pages;
- conversation-to-query pages show the inputs, interpretation step, query variants, and downstream candidate boundary;
- retrieval-and-ranking pages distinguish candidate sources, union or fusion, features, ranking, and selected track IDs;
- response pages show candidate generation, verification or critique, repair or polishing, selection, and the final response;
- the submitted system and each leading team receive readable, mechanism-specific architecture diagrams.

Use the report's violet, teal, amber, and neutral palette to distinguish stages and evidence types. Decorative raster artwork is out of scope. A visual may summarize exact evidence, but every mechanism and qualification remains available as accessible HTML text or in the following evidence page.

### Precise technical visuals

Score charts, system pipelines, comparison matrices, and evidence statuses remain deterministic report-native visuals. They may be redesigned, but their labels and values come directly from canonical data—not generative imagery.

### Text limits

- cover page: title, one-sentence question, and at most three short takeaways;
- visual interpretation page: at most 140 visible words outside labels;
- matrix/audit page: a two-sentence orientation plus the evidence object;
- longer qualifications move to the next page or a clearly named disclosure.

## Page archetypes

### 1. Chapter cover

A full-width evidence map occupies roughly 55–65% of the usable canvas. The chapter title, question, and reading cues occupy the remainder. This page previews the actual mechanisms and evidence sequence rather than adding decoration.

### 2. Visual evidence page

A chart or deterministic diagram occupies the primary canvas. Interpretation appears in a compact side panel on screens wider than 1,100px and below the visual on smaller screens.

### 3. Matrix page

The table uses the full canvas. Cells wrap at word boundaries; the identifying column remains visible; row height grows naturally. On narrow screens, each row becomes a labeled card unless the table is primarily numeric, in which case horizontal scrolling is allowed with a visible cue.

### 4. Story page

Used for an executive answer, evaluation lesson, or team comparison. It uses a strong headline, 2–4 concise claims, and optional metric or evidence cards. Long paragraphs are prohibited.

### 5. Audit page

Long prompt or file evidence is split into meaningful pages. Desktop uses two balanced columns where reading order remains unambiguous; mobile uses one column. Each page expands naturally in the chapter scroller and never has an internal vertical scrollbar.

## Exact 50-page structure

### Chapter 1 — Outcome and score: 6 pages

1. Explanatory chapter map and executive orientation.
2. Executive answer and headline metrics.
3. Composite formula plus official leaderboard chart.
4. Exact leaderboard table.
5. Full-size gap-decomposition chart.
6. Gap interpretation, arithmetic boundary, and chart source.

### Chapter 2 — Conversation to query: 7 pages

1. Explanatory chapter map: dialogue becoming structured search evidence.
2. Shared query lifecycle diagram and takeaway.
3. Query concepts and glossary.
4. Full five-team query matrix.
5. Data/model-knowledge concepts and glossary.
6. Full data/model-knowledge matrix plus practical boundary.
7. Prompt excerpts and reviewed-file audit, divided internally into readable prompt and inventory sections without nested scrolling.

### Chapter 3 — Retrieval and ranking: 5 pages

1. Explanatory chapter map: many signals becoming a ranked list.
2. Retriever glossary and five-team retrieval matrix.
3. Feature-family glossary.
4. Feature-family matrix.
5. Per-team feature inventories and validation lineage.

### Chapter 4 — Response generation: 7 pages

1. Explanatory chapter map: selected track becoming checked prose.
2. Response subsystem overview.
3. Complete five-team response matrix.
4. Author and volart generation/selection paths.
5. niwatori and swyoo generation/selection paths.
6. team2_s2 generation/polishing path.
7. Cross-team response trade-offs and source boundary.

### Chapter 5 — Our submission: 7 pages

1. Explanatory chapter map and submitted-system thesis.
2. Offline evidence rail.
3. Inference rail.
4. Complete walkthrough and ranking handoff.
5. What worked.
6. Evaluation mistake and confidence boundary.
7. Ranking and response contributors.

### Chapter 6 — Leading teams: 13 pages

1. Explanatory chapter map and acknowledged case-study index.
2–4. volart: outcome/query/data; retrieval/ranking diagram; response/comparison/limits.
5–7. niwatori: outcome/query/data; retrieval/ranking diagram; response/comparison/limits.
8–10. swyoo: outcome/query/data; retrieval/ranking diagram; response/comparison/limits.
11–13. team2_s2: outcome/query/data; retrieval/ranking diagram; response/comparison/limits.

### Chapter 7 — Synthesis and evidence: 5 pages

1. Explanatory chapter map and cross-team thesis.
2. Cross-team synthesis matrix.
3. Preserve, reconsider, and avoid.
4. Transferable lessons and acknowledgements.
5. Caveats, complete evidence notes, and complete source list.

Total: **50 vertical pages**.

## Embedded-content strategy

The portable builder's static fallback remains untouched and complete. In deck mode, custom HTML blocks are promoted into responsive embedded documents that expand to their intrinsic content height.

Implementation must preserve iframe sandboxing or provide an equivalently isolated, script-free rendering boundary. It may not solve the problem by granting arbitrary scripts or dropping the source CSP. The chosen implementation must:

- eliminate internal vertical scrolling;
- resize after fonts and responsive layout settle;
- keep diagrams and tables within the page width;
- wrap matrix prose without changing text;
- return to the original safe iframe fallback when responsive promotion fails.

## Navigation

- Horizontal movement still changes the seven chapters.
- Vertical movement traverses the 50 content-aware pages.
- The desktop rail shows the current page number and meaningful label on focus/hover.
- Mobile shows `Chapter name · page n/m`.
- Jump search indexes every page title, team name, topic, and preserved block content.
- Existing hashes remain valid through aliases when a former page is split.

## Responsive behavior

### Large desktop, 1,280px and wider

- content canvas uses `min(1,520px, viewport minus chrome and gutters)`;
- visual evidence pages may use a 2:1 visual-to-interpretation layout;
- matrices use the full width and wrapped cells;
- audit pages may use two columns.

### Tablet, 701–1,279px

- visual and interpretation regions stack;
- matrices retain labels and wrap aggressively;
- chapter controls remain compact.

### Mobile, up to 700px

- one-column layout;
- no vertical rail;
- tables become cards when semantic integrity allows;
- explanatory diagrams stack into their DOM reading order and never hide essential content;
- all controls remain at least 44px.

## Accessibility and evidence integrity

- Explanatory diagrams use native headings and ordered lists with accessible names.
- No essential text is baked into a raster image.
- Exact data remains available in native tables or accessible disclosures.
- Visual and DOM reading order match.
- Page focus moves to the new page heading after navigation.
- Reduced-motion, forced-color, print, linear, JavaScript-disabled, and keyboard behavior remain supported.
- Linear and print modes retain exact canonical block order and display all ten sources.

## Verification

### Structural

- all 74 canonical blocks assigned exactly once;
- exactly 50 deck pages across seven chapters;
- seven readable chapter maps plus mechanism-specific system and subsystem diagrams;
- no factual URLs, source records, iframe source documents, or compressed payload lost;
- deterministic enhancement and self-contained final HTML.

### Browser and visual

At 1,440×900, 1,280×800, 1,024×768, 390×844, light, and dark themes:

- no embedded vertical scrollbar on any page;
- no clipped chart, matrix, diagram, or audit content;
- no unintended document-level horizontal overflow;
- matrix rows and audit sections are readable without zooming out;
- short pages use the canvas intentionally rather than leaving accidental dead zones;
- all 50 pages can be reached by controls, keys, scroll, and Jump search;
- history, direct links, interrupted navigation, print, linear mode, and JavaScript-disabled fallback remain correct.

For the four supplied failure states, capture same-viewport before/after comparisons and inspect them side by side before handoff.

## Non-goals

- No recovery plan or new competition strategy section.
- No rewrite of factual conclusions or evidence boundaries.
- No public deployment or sharing-permission change.
- No summary visual used as a substitute for the exact leaderboard, source list, prompt excerpt, or repository acknowledgement.
