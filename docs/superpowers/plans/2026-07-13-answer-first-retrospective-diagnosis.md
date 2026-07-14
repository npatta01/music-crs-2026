# Answer-First Retrospective Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder the Music-CRS retrospective around an evidence-tiered explanation of likely underperformance, add six visual diagnosis slides and a curated reading path, and compress repeated prose without losing any canonical evidence.

**Architecture:** Keep the portable HTML report and its 74 canonical blocks as the immutable evidence layer. Extend `scripts/report/retrospective_deck.mjs` as the deterministic presentation layer: new slide configuration objects supply diagnosis content, reusable renderers create pipeline/heatmap/provenance visuals, and a curated-path controller changes navigation without creating a second artifact. Regenerate `retrospective.html` from the enhancer after every approved presentation change.

**Tech Stack:** Node.js ES modules and `node:test`; self-contained HTML/CSS/JavaScript; Python `pytest`; Playwright with `/usr/bin/google-chrome`; existing portable artifact payload and source-backed HTML.

## Global Constraints

- The diagnosis appears immediately after the outcome and before detailed system chapters.
- Every diagnosis claim is labeled **Verified**, **Likely contributor**, or **Unknown**.
- Never claim the submitted system lacked constraints, behavioral evidence, or LLM knowledge.
- Distinguish missing candidate-generation evidence from missing LightGBM feature columns.
- Identify `b1_cos` as a reranker feature, not a deployed candidate-producing lane.
- Describe the deployed pool consistently as the union of up to 500 hits from each traced branch; LightGBM, not RRF, produced the final order.
- Describe full-data fitting as a measurement and selection-confidence failure, not the sole Blind-B cause.
- Preserve all 74 canonical blocks, ten source records, source URLs, repository SHAs, iframe source documents, and the compressed artifact payload.
- Preserve exact team-specific differences: external data and multi-draft generation were not universal among leaders.
- Primary slides use native technical visuals, large labels, and bounded prose; decorative or abstract images are prohibited.
- Complete matrices, prompts, feature inventories, limitations, and evidence remain available through named disclosures or the audit path.
- Preserve keyboard, touch, browser history, direct links, reduced motion, forced colors, print, linear, and JavaScript-disabled behavior.
- Do not publish the report or change sharing permissions.

---

## File Structure

- Modify `scripts/report/retrospective_deck.mjs`: chapter order, diagnosis data, curated path, reusable visual renderers, styling, aliases, and runtime navigation.
- Modify `tests/report/retrospective_deck.test.mjs`: structural, evidence-copy, ordering, curated-path, and deterministic-generation tests.
- Modify `tests/report/test_retrospective_deck_browser.py`: visual component, navigation, accessibility, disclosure, responsive, and integrity tests.
- Regenerate `retrospective.html`: committed self-contained artifact produced by the enhancer; do not hand-edit its injected deck CSS or runtime.
- Modify `docs/superpowers/plans/2026-07-13-answer-first-retrospective-diagnosis.md`: mark completed checkboxes during execution.

---

### Task 1: Define the answer-first chapter map and diagnosis evidence model

**Files:**
- Modify: `tests/report/retrospective_deck.test.mjs`
- Modify: `scripts/report/retrospective_deck.mjs`

**Interfaces:**
- Produces: exported `DIAGNOSIS_SLIDES`, `CURATED_PATH`, `CONFIDENCE_LEVELS`, and reordered `CHAPTERS`.
- Consumes: existing `slide()` helper, canonical block IDs, `validateChapterMap()`, and `LEGACY_ALIASES`.
- Later tasks rely on diagnosis slide options named `diagnosisKind`, `confidence`, `stages`, `connections`, `featureFamilies`, and `boundaries`.

- [ ] **Step 1: Write failing structural tests for order, content, and evidence language**

Add imports and tests to `tests/report/retrospective_deck.test.mjs`:

```js
import {
  CHAPTERS,
  CONFIDENCE_LEVELS,
  CURATED_PATH,
  DIAGNOSIS_SLIDES,
  LEGACY_ALIASES,
  PAGE_ARCHETYPES,
  enhanceHtml,
  resolveSlug,
  stripDeckInjection,
  validateChapterMap,
} from "../../scripts/report/retrospective_deck.mjs";

test("answer-first order puts diagnosis directly after outcome", () => {
  assert.deepEqual(CHAPTERS.slice(0, 3).map(({ slug }) => slug), ["outcome", "diagnosis", "ours"]);
  assert.equal(CHAPTERS.find(({ slug }) => slug === "diagnosis").slides.length, 6);
  assert.deepEqual(
    DIAGNOSIS_SLIDES.map(({ slug }) => slug),
    ["score-location", "information-loss", "constraint-wiring", "features-seen", "evidence-missed", "confidence"],
  );
});

test("answer-first deck keeps a complete content-aware chapter map", async () => {
  const html = await readFile(REPORT, "utf8");
  const result = validateChapterMap(CHAPTERS, stripDeckInjection(html));
  assert.equal(CHAPTERS.length, 8);
  assert.equal(result.pageCount, 56);
  assert.deepEqual(result.chapterCounts, [6, 6, 7, 7, 7, 5, 13, 5]);
  assert.equal(result.mappedIds.length, 74);
});

test("diagnosis copy preserves evidence boundaries", () => {
  const copy = JSON.stringify(DIAGNOSIS_SLIDES);
  assert.match(copy, /rich extraction, uneven execution/i);
  assert.match(copy, /grounded and reused/i);
  assert.match(copy, /direct track co-occurrence/i);
  assert.match(copy, /sequential|Markov|transition/i);
  assert.match(copy, /b1_cos.*feature/i);
  assert.doesNotMatch(copy, /did not convert conversation into constraints/i);
  assert.doesNotMatch(copy, /did not use LLM world knowledge/i);
  assert.deepEqual([...CONFIDENCE_LEVELS], ["verified", "likely", "unknown"]);
});

test("curated path is short, answer-first, and references canonical slides", () => {
  const allSlugs = new Set(CHAPTERS.flatMap((chapter) => chapter.slides.map((entry) => `${chapter.slug}/${entry.slug}`)));
  assert.ok(CURATED_PATH.length >= 12 && CURATED_PATH.length <= 15);
  assert.equal(CURATED_PATH[0], "outcome/executive-answer");
  assert.equal(CURATED_PATH[1], "outcome/gap-chart");
  assert.equal(CURATED_PATH[2], "diagnosis/score-location");
  assert.ok(CURATED_PATH.every((slug) => allSlugs.has(slug)));
});
```

- [ ] **Step 2: Run the structural tests and confirm the new exports are missing**

Run:

```bash
node --test tests/report/retrospective_deck.test.mjs
```

Expected: FAIL with an import/export error for `CONFIDENCE_LEVELS`, `CURATED_PATH`, or `DIAGNOSIS_SLIDES`.

- [ ] **Step 3: Add the diagnosis data model and reorder chapters**

In `scripts/report/retrospective_deck.mjs`, define the exported constants before `CHAPTERS`:

```js
export const CONFIDENCE_LEVELS = new Set(["verified", "likely", "unknown"]);

export const DIAGNOSIS_SLIDES = [
  slide("score-location", "Where the score gap appeared", "visual", [], {
    diagnosisKind: "score",
    takeaway: "Ranking and judge terms explain most of the arithmetic gap; the chart does not prove which mechanism caused it.",
  }),
  slide("information-loss", "Where information was lost", "visual", [], {
    diagnosisKind: "bottleneck",
    stages: ["Conversation", "Extracted state", "Retriever actions", "Candidate sources", "Candidate union", "LightGBM", "Top-1 track", "Grounded context", "One draft", "Final response"],
    losses: [
      { after: "Extracted state", label: "Some facts remained soft or lacked a dedicated source action", confidence: "verified" },
      { after: "Candidate sources", label: "No direct co-occurrence or transition lane", confidence: "verified" },
      { after: "Candidate union", label: "Absent tracks were irrecoverable downstream", confidence: "verified" },
      { after: "One draft", label: "No independent selection, checking, or repair", confidence: "verified" },
    ],
  }),
  slide("constraint-wiring", "Extracted constraints versus operationalized constraints", "visual", [], {
    diagnosisKind: "wiring",
    takeaway: "Rich extraction, uneven execution: not every fact became a filter, source-specific query, or dedicated candidate signal.",
  }),
  slide("features-seen", "What the 142-feature reranker saw", "visual", [], {
    diagnosisKind: "feature-map",
    featureFamilies: ["Retriever evidence", "Semantic and multimodal", "Behavioral and lookup", "Catalog", "Conversation and state", "Agreement and interactions"],
    takeaway: "The ranker was substantial; column count alone does not establish liveness, importance, robustness, or held-out benefit.",
  }),
  slide("evidence-missed", "Evidence the ranker could not see or recover", "visual", [], {
    diagnosisKind: "boundaries",
    boundaries: ["Missing upstream source", "Consequent missing feature", "Not missing"],
    takeaway: "Adding LightGBM columns cannot recreate a track or source signal that never entered the pipeline.",
  }),
  slide("confidence", "Response weakness and confidence-ranked diagnosis", "visual", [], {
    diagnosisKind: "confidence",
    confidence: {
      verified: ["Ranking and judge dominate the score gap", "Constraint execution was uneven", "Behavioral evidence was partial", "b1_cos was a reranker feature only", "Blind-B used one response call with echo_retries=0"],
      likely: ["Evidence diversity mattered more than feature count", "LLM knowledge was not consistently grounded and reused", "Distribution shift or objective mismatch contributed", "Response quality control was too thin"],
      unknown: ["Blind-B candidate recall", "Present-but-misranked frequency", "Per-session failure archetypes", "Causal effect of any one mechanism"],
    },
  }),
];

export const CURATED_PATH = [
  "outcome/executive-answer", "outcome/gap-chart",
  ...DIAGNOSIS_SLIDES.map(({ slug }) => `diagnosis/${slug}`),
  "ours/inference-rail", "retrieval/evidence-heatmap", "response/control-heatmap",
  "leaders/volart-retrieval", "synthesis/lessons",
];
```

Insert a `diagnosis` chapter immediately after `outcome`, move `ours` before `query`, and use `DIAGNOSIS_SLIDES` as its `slides`. Add aliases from prior hashes to merged slides and keep every canonical block assigned once.

Lock in the final 56-slide structure during this task so later renderer work does not churn navigation:

- query: merge `query-glossary` into `lifecycle`, add blockless `provenance-stacks`, and keep the exact query/data matrices and prompt audit assigned once;
- retrieval: keep the mechanism, add blockless `evidence-heatmap`, retain one shared feature-family map plus exact matrix/inventory disclosures;
- response: keep the cover and lifecycle, replace the three pairwise/team-only visual pages with `grounding-heatmap` and `control-heatmap`, and retain the complete trade-offs audit;
- add aliases from `query/query-glossary`, `response/author-volart`, `response/niwatori-swyoo`, and `response/team2` to their surviving summary or audit slides.

Update the pre-existing exact-count assertions in both report test files from seven chapters/51 slides to eight chapters/56 slides and `[6, 6, 7, 7, 7, 5, 13, 5]`.

- [ ] **Step 4: Run the structural tests and chapter-map check**

Run:

```bash
node --test tests/report/retrospective_deck.test.mjs
node scripts/report/retrospective_deck.mjs --check retrospective.html
```

Expected: all Node tests PASS and the check reports `PASS: 74 blocks mapped into 8 chapters`.

- [ ] **Step 5: Commit the answer-first structure**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/retrospective_deck.test.mjs
git commit -m "feat: add answer-first diagnosis structure"
```

---

### Task 2: Render the six diagnosis visuals and belief-update evidence

**Files:**
- Modify: `tests/report/test_retrospective_deck_browser.py`
- Modify: `scripts/report/retrospective_deck.mjs`

**Interfaces:**
- Consumes: `entry.diagnosisKind` and the diagnosis option shapes from Task 1.
- Produces: `.deck-diagnosis`, `.deck-bottleneck`, `.deck-wiring`, `.deck-feature-map`, `.deck-boundary-map`, `.deck-confidence-grid`, `.deck-belief-timeline`, and `.deck-failure-taxonomy` DOM structures.

- [ ] **Step 1: Add failing browser tests for all diagnosis visual forms**

Add to `tests/report/test_retrospective_deck_browser.py`:

```python
def test_diagnosis_is_visual_evidence_not_paragraph_prose(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#diagnosis/information-loss")
    assert browser_page.locator("[data-chapter='diagnosis'] .deck-slide").count() == 6
    assert browser_page.locator("#diagnosis\\/information-loss .deck-bottleneck-stage").count() == 10
    assert browser_page.locator("#diagnosis\\/constraint-wiring .deck-wiring-link").count() >= 8
    assert browser_page.locator("#diagnosis\\/features-seen .deck-feature-family").count() == 6
    assert browser_page.locator("#diagnosis\\/evidence-missed .deck-boundary-column").count() == 3
    assert browser_page.locator("#diagnosis\\/confidence .deck-confidence-column").count() == 3
    for slug in ("score-location", "information-loss", "constraint-wiring", "features-seen", "evidence-missed", "confidence"):
        words = browser_page.locator(f"#diagnosis\\/{slug}").evaluate(
            "node => [...node.querySelectorAll('p')].filter(p => p.offsetParent !== null).map(p => p.textContent).join(' ').split(/\\s+/).filter(Boolean).length"
        )
        assert words <= 120
    assert errors == []


def test_diagnosis_confidence_and_unknown_boundaries_are_explicit(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#diagnosis/confidence")
    text = browser_page.locator("#diagnosis\\/confidence").inner_text()
    for phrase in ("Verified", "Likely contributor", "Unknown", "candidate recall", "echo_retries=0"):
        assert phrase in text
    assert "sole cause" not in text.lower()
```

- [ ] **Step 2: Run the browser tests and confirm the visual classes are absent**

Run:

```bash
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k diagnosis
```

Expected: FAIL because `.deck-bottleneck-stage` and the other diagnosis structures do not exist.

- [ ] **Step 3: Add deterministic diagnosis renderers**

In `runtimeMain()`, add a renderer called from the existing slide construction loop:

```js
const renderDiagnosis = (inner, entry) => {
  const root = document.createElement("section");
  root.className = `deck-diagnosis deck-diagnosis--${entry.diagnosisKind}`;
  root.setAttribute("aria-label", entry.title);
  if (entry.diagnosisKind === "bottleneck") root.append(renderBottleneck(entry));
  if (entry.diagnosisKind === "wiring") root.append(renderConstraintWiring());
  if (entry.diagnosisKind === "feature-map") root.append(renderFeatureMap(entry.featureFamilies));
  if (entry.diagnosisKind === "boundaries") root.append(renderEvidenceBoundaries());
  if (entry.diagnosisKind === "confidence") root.append(renderConfidence(entry.confidence), renderBeliefTimeline(), renderFailureTaxonomy());
  if (entry.diagnosisKind === "score") root.append(renderScoreFindings());
  if (entry.takeaway) root.append(renderTakeaway(entry.takeaway));
  inner.append(root);
};
```

Use native ordered lists and headings for every stage. `renderConstraintWiring()` must include the verified extraction and consumer labels from the spec, with `data-link-kind="direct|soft|feature-only"`. `renderEvidenceBoundaries()` must show direct co-occurrence, transition probability, generated-description similarity, and frequency priors as missing/limited while explicitly listing dense similarity, CF/BPR centroids, state, rejection, temporal, metadata, and agreement evidence as present.

- [ ] **Step 4: Add accessible technical styling**

Extend `DECK_STYLE` with component classes using the existing palette:

```css
.deck-diagnosis{display:grid;gap:18px;min-width:0}
.deck-bottleneck{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}
.deck-bottleneck-stage,.deck-feature-family,.deck-boundary-column,.deck-confidence-column{min-width:0;padding:16px;border:1px solid var(--portable-border);border-radius:14px;background:var(--portable-surface)}
.deck-loss{padding:9px 11px;border-left:5px solid #c98612;border-radius:9px;background:color-mix(in srgb,#c98612 12%,var(--portable-surface))}
.deck-wiring{display:grid;grid-template-columns:minmax(0,1fr) minmax(160px,.5fr) minmax(0,1fr);gap:16px}
.deck-wiring-link[data-link-kind="direct"]{border-color:#15945b}.deck-wiring-link[data-link-kind="soft"]{border-style:dashed;border-color:#c98612}.deck-wiring-link[data-link-kind="feature-only"]{border-style:dotted;border-color:#6f54c7}
.deck-feature-map{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.deck-boundary-map,.deck-confidence-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.deck-confidence-column[data-confidence="verified"]{border-top:5px solid #15945b}.deck-confidence-column[data-confidence="likely"]{border-top:5px solid #c98612}.deck-confidence-column[data-confidence="unknown"]{border-top:5px solid var(--portable-muted)}
@media(max-width:900px){.deck-bottleneck,.deck-feature-map{grid-template-columns:repeat(2,minmax(0,1fr))}.deck-wiring,.deck-boundary-map,.deck-confidence-grid{grid-template-columns:1fr}}
@media(max-width:600px){.deck-bottleneck,.deck-feature-map{grid-template-columns:1fr}}
```

Do not use color without text labels or line styles.

- [ ] **Step 5: Run focused browser and structural tests**

```bash
node --test tests/report/retrospective_deck.test.mjs
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k 'diagnosis or content_aware or visual_first'
```

Expected: all selected tests PASS with no browser errors.

- [ ] **Step 6: Commit the diagnosis visuals**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/test_retrospective_deck_browser.py
git commit -m "feat: visualize retrospective diagnosis"
```

---

### Task 3: Add curated retrospective navigation without duplicating evidence

**Files:**
- Modify: `tests/report/retrospective_deck.test.mjs`
- Modify: `tests/report/test_retrospective_deck_browser.py`
- Modify: `scripts/report/retrospective_deck.mjs`

**Interfaces:**
- Consumes: `CURATED_PATH`, `bySlug`, `goTo()`, `updateCurrent()`, and existing linear/deck modes.
- Produces: `setReadingPath(mode: "curated" | "audit")`, `currentReadingPath(): string`, topbar `[data-action="reading-path"]`, and `?path=curated|audit` URL state.

- [ ] **Step 1: Add failing runtime navigation tests**

Add to `tests/report/test_retrospective_deck_browser.py`:

```python
def test_curated_path_is_explicit_and_can_open_full_audit(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "?path=curated#outcome/executive-answer")
    assert browser_page.locator("html").get_attribute("data-reading-path") == "curated"
    assert browser_page.get_by_role("button", name="Explore evidence audit").is_visible()
    browser_page.get_by_role("button", name="Next").click()
    browser_page.wait_for_url("**#outcome/gap-chart")
    browser_page.get_by_role("button", name="Explore evidence audit").click()
    assert browser_page.locator("html").get_attribute("data-reading-path") == "audit"
    assert browser_page.get_by_role("button", name="Read retrospective").is_visible()
    assert errors == []


def test_curated_path_does_not_hide_audit_from_jump_or_direct_links(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "?path=curated#diagnosis/features-seen")
    browser_page.get_by_role("button", name="Jump").click()
    palette = browser_page.get_by_role("dialog", name="Jump anywhere")
    palette.get_by_role("searchbox").fill("prompt and file audit")
    palette.get_by_role("button", name=re.compile("Prompt and file audit", re.I)).click()
    browser_page.wait_for_url("**#query/prompt-audit")
    assert browser_page.locator("html").get_attribute("data-reading-path") == "audit"
```

- [ ] **Step 2: Run the focused tests and verify the reading-path control is absent**

```bash
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k curated_path
```

Expected: FAIL because `[data-reading-path]` and the reading-path button do not exist.

- [ ] **Step 3: Implement curated/audit navigation state**

Pass `curatedPath: CURATED_PATH` in the injected config. Add the topbar control:

```js
topbar.innerHTML = '<strong class="deck-title">Music-CRS retrospective</strong><span class="deck-mobile-orientation"></span><span class="deck-breadcrumb"></span><span class="deck-progress"></span><button class="deck-button" type="button" data-action="reading-path">Read retrospective</button><button class="deck-button" type="button" data-action="linear">Linear view</button><button class="deck-button" type="button" data-action="jump">Jump</button>';
```

Add runtime state:

```js
let readingPath = new URL(location.href).searchParams.get("path") === "curated" ? "curated" : "audit";
const navigationItems = () => readingPath === "curated" ? CONFIG.curatedPath.map((slug) => bySlug.get(slug)).filter(Boolean) : slides;
const setReadingPath = (mode) => {
  readingPath = mode === "curated" ? "curated" : "audit";
  html.dataset.readingPath = readingPath;
  const url = new URL(location.href);
  url.searchParams.set("path", readingPath);
  history.replaceState(history.state, "", url.href);
  topbar.querySelector('[data-action="reading-path"]').textContent = readingPath === "curated" ? "Explore evidence audit" : "Read retrospective";
  updateCurrent(active, false);
};
```

When `previous` or `next` is clicked in curated mode, navigate within `navigationItems()`. Horizontal/vertical arrows retain spatial chapter navigation. Direct navigation or Jump to a non-curated slide switches to audit mode so the selected evidence remains reachable. Expose `setReadingPath` and `currentReadingPath` on `window.__retrospectiveDeck`.

- [ ] **Step 4: Run navigation, history, keyboard, and print tests**

```bash
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k 'curated_path or buttons_keys_hash_and_history or direct_and_invalid_hashes or linear_and_print_modes or gesture_navigation'
```

Expected: all selected tests PASS. Existing arrow-key and direct-hash semantics remain unchanged.

- [ ] **Step 5: Commit the two reading paths**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/retrospective_deck.test.mjs tests/report/test_retrospective_deck_browser.py
git commit -m "feat: add curated retrospective reading path"
```

---

### Task 4: Replace repeated feature, provenance, and response prose with reusable visual comparisons

**Files:**
- Modify: `tests/report/retrospective_deck.test.mjs`
- Modify: `tests/report/test_retrospective_deck_browser.py`
- Modify: `scripts/report/retrospective_deck.mjs`

**Interfaces:**
- Produces: `visualKind: "heatmap" | "provenance" | "control-lanes"`, `.deck-evidence-heatmap`, `.deck-provenance-stack`, and `.deck-control-lanes`.
- Consumes: existing normalized team comparison data already encoded in `CHAPTERS`; complete canonical matrices remain attached through `DISCLOSURES`.

- [ ] **Step 1: Add failing structural and browser tests for the three visual grammars**

Add to `tests/report/retrospective_deck.test.mjs`:

```js
test("primary comparisons use evidence heatmaps, provenance stacks, and control lanes", () => {
  const pages = new Map(CHAPTERS.flatMap((chapter) => chapter.slides.map((entry) => [`${chapter.slug}/${entry.slug}`, entry])));
  assert.equal(pages.get("retrieval/evidence-heatmap").visualKind, "heatmap");
  assert.equal(pages.get("query/provenance-stacks").visualKind, "provenance");
  assert.equal(pages.get("response/control-heatmap").visualKind, "control-lanes");
});
```

Add to `tests/report/test_retrospective_deck_browser.py`:

```python
def test_reusable_visual_grammars_compare_all_five_teams(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    for slug, selector in (
        ("query/provenance-stacks", ".deck-provenance-stack"),
        ("retrieval/evidence-heatmap", ".deck-evidence-heatmap"),
        ("response/control-heatmap", ".deck-control-lanes"),
    ):
        open_deck(browser_page, enhanced_report, f"#{slug}")
        assert browser_page.locator(f"#{slug.replace('/', r'\\/')} {selector}").count() == 1
        assert browser_page.locator(f"#{slug.replace('/', r'\\/')} [data-team]").count() == 5
    assert errors == []
```

- [ ] **Step 2: Run the focused tests and verify the new slides/renderers are missing**

```bash
node --test tests/report/retrospective_deck.test.mjs
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k reusable_visual_grammars
```

Expected: FAIL because the new slugs and visual classes do not exist.

- [ ] **Step 3: Merge overlapping query explainers and add provenance stacks**

Keep one shared query mechanism slide. Move `query_heading`, `query_explainer`, and `lifecycle_*` blocks into named disclosures on that slide without duplicating IDs. Add `query/provenance-stacks` with five team rows and these layers:

```js
const provenanceLayers = ["Official challenge data", "External structured data", "Generated artifacts", "Latent LLM knowledge", "Verification boundary"];
```

Populate team-specific labels from the existing `data-matrix` evidence, including TalkPlayData-1 for niwatori and LRCLIB/Genius/MusicBrainz for swyoo. Do not imply those resources were used by every leader.

- [ ] **Step 4: Replace the visible feature taxonomy with a differentiating-evidence heatmap**

Add `retrieval/evidence-heatmap` with columns:

```js
const evidenceColumns = ["Lexical", "Dense", "Collaborative", "Co-occurrence", "Transition", "Lookup", "Generated description", "Metadata", "Conversation/state", "Agreement/routing", "Priors"];
```

Each cell uses `present`, `partial`, or `not-documented` plus a short accessible label. Keep `feature_matrix` and `feature_details` in named disclosures or audit slides. Feature-count badges are secondary: npatta01 142, volart 69, niwatori 176, team2_s2 37, and swyoo exact submitted count not established.

- [ ] **Step 5: Compress response comparisons into lifecycle and control lanes**

Keep one shared lifecycle. Add two visual slides:

```js
const responseColumns = ["Grounding", "Drafts", "Selection", "Verification", "Repair", "Lexical control"];
```

Represent the five systems precisely:

- npatta01: latest state/catalog metadata, one draft, no independent selector/checker/repair documented;
- volart: three temperature-diverse candidates, critic, selective rewrite/hardening, lexical pass;
- niwatori: ten seeded candidates, lexical-diversity selection, not a factual critic;
- swyoo: deterministic PAS proposals plus one PAS prediction, theme/citation validation and repair, not best-of-N critique;
- team2_s2: verified fact bundle, first response, Gemini Pro refinement.

Move exact matrices, walkthroughs, and pass-count qualifications behind disclosure.

- [ ] **Step 6: Add generic renderers and responsive styling**

Implement one renderer per grammar:

```js
const renderHeatmap = ({ columns, teams }) => renderTeamGrid("deck-evidence-heatmap", columns, teams);
const renderProvenance = ({ layers, teams }) => renderTeamStacks("deck-provenance-stack", layers, teams);
const renderControlLanes = ({ columns, teams }) => renderTeamGrid("deck-control-lanes", columns, teams);
```

Use native table/grid semantics and `data-status` labels. At widths below 900px, each team becomes a labeled card. Do not create horizontal document overflow or nested vertical scrolling.

- [ ] **Step 7: Run comparison, disclosure, and bounded-prose tests**

```bash
node --test tests/report/retrospective_deck.test.mjs
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k 'reusable_visual_grammars or dense_topics or progressive_disclosure or visual_first_default or exact_dense_evidence'
```

Expected: all selected tests PASS. Complete evidence remains reachable and primary visible prose remains within 120 words per slide.

- [ ] **Step 8: Commit the visual comparison grammar**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/retrospective_deck.test.mjs tests/report/test_retrospective_deck_browser.py
git commit -m "feat: compress evidence into reusable visual comparisons"
```

---

### Task 5: Convert leader introductions and score interpretation into concise answer cards

**Files:**
- Modify: `tests/report/test_retrospective_deck_browser.py`
- Modify: `scripts/report/retrospective_deck.mjs`

**Interfaces:**
- Produces: `.deck-system-card`, `.deck-score-findings`, compact leader summary options, and visible pinned-commit/evidence-boundary labels.
- Consumes: existing leader blocks, retrieval diagrams, insight-card transformer, official score chart, and source disclosures.

- [ ] **Step 1: Add failing browser tests for team cards and concise score interpretation**

```python
def test_leader_introductions_are_compact_system_cards(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    for slug in ("volart-outcome", "niwatori-outcome", "swyoo-outcome", "team2-outcome"):
        open_deck(browser_page, enhanced_report, f"#leaders/{slug}")
        card = browser_page.locator(f"#leaders\\/{slug} .deck-system-card")
        assert card.count() == 1
        assert card.locator("[data-system-field]").count() >= 5
    assert errors == []


def test_score_interpretation_is_three_findings_with_exact_math_disclosed(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#outcome/gap-interpretation")
    assert browser_page.locator("#outcome\\/gap-interpretation .deck-score-finding").count() == 3
    text = browser_page.locator("#outcome\\/gap-interpretation").inner_text()
    assert "arithmetic, not causal" in text.lower()
    assert browser_page.locator("#outcome\\/gap-interpretation details[data-disclosure-for='gap_interpretation']").count() == 1
```

- [ ] **Step 2: Run focused tests and verify the cards are absent**

```bash
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k 'leader_introductions or score_interpretation'
```

Expected: FAIL because `.deck-system-card` and `.deck-score-finding` do not exist.

- [ ] **Step 3: Render compact system cards while preserving detailed blocks**

For each leader outcome slide, add configuration fields populated with the reviewed evidence:

```js
const LEADER_SYSTEM_CARDS = {
  volart: {
    result: "0.5866 composite · 0.3965 nDCG@20 · 4.90/5 judge",
    query: "GPT-4o-mini produced one cached retrieval rewrite plus positive entity and era JSON.",
    knowledge: "Official records, train co-occurrence and frequency/MOVES priors, plus generated track descriptions.",
    retrieval: "Five lanes fed a top-500 LambdaMART boundary with direct co-occurrence features.",
    response: "Three drafts, independent critique, selective rewrite, hardening, and lexical control.",
    limit: "Structured musical-fact verification was not documented.",
  },
  niwatori: {
    result: "0.5859 composite · 0.4934 nDCG@20 · 4.45/5 judge",
    query: "Source-specific safe text, full played history, and last-track transition keys; no LLM retrieval rewrite documented.",
    knowledge: "Official records plus mapped TalkPlayData-1 co-occurrence and transition statistics.",
    retrieval: "Fourteen-source union, direct co-occurrence, Markov transition, and 176 documented features with OOF artifacts.",
    response: "Ten seeded drafts selected for lexical diversity.",
    limit: "The selector was not a factual critic; response fact checking was not documented.",
  },
  swyoo: {
    result: "0.5784 composite · 0.3829 nDCG@20 · 4.85/5 judge",
    query: "Separate BM25, QEmb, and two-tower representations with an optional cached session summary.",
    knowledge: "LRCLIB, Genius, and MusicBrainz enriched lyrics, identifiers, tags, labels, countries, and dates.",
    retrieval: "Three independently rendered pools with group-aware OOF routing for learned sources.",
    response: "PAS generation with theme/citation validation and repair.",
    limit: "One PAS prediction was used; no best-of-N independent critic was documented.",
  },
  team2_s2: {
    result: "0.5759 composite · 0.4452 nDCG@20 · 4.65/5 judge",
    query: "Conversation BM25, live text, recent item vectors, ALS history, and cached structured lists.",
    knowledge: "Official catalog, conversations, users, labels, and embeddings; no external music dataset documented.",
    retrieval: "Live and structured sources fed routed rankers with covariate-shift weighting and 37 documented features.",
    response: "Verified catalog facts grounded a first draft followed by Gemini Pro refinement.",
    limit: "No independent structured fact or recommendation-ID integrity check was documented.",
  },
};
```

Render the card before the canonical block disclosure. Keep the mechanism-specific retrieval diagrams unchanged because they are the approved reference treatment.

- [ ] **Step 4: Replace gap prose with three findings and expose the pinned submission boundary**

Render:

```js
const findings = [
  ["Ranking + judge", "These terms dominate each leader's arithmetic advantage."],
  ["Catalog diversity", "The contribution is nearly neutral."],
  ["Evidence boundary", "The decomposition is arithmetic, not causal."],
];
```

Put `gap_interpretation` behind its named disclosure. Add a visible badge on diagnosis slides reading `Blind-B deployed evidence · 2ecc45a7`, plus a short note that repository documentation depth can bias `Not documented` comparisons.

- [ ] **Step 5: Run leader, score, insight-card, and source tests**

```bash
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k 'leader_introductions or score_interpretation or dense_walkthroughs or progressive_disclosure_and_sources'
```

Expected: all selected tests PASS and the ten-source list remains complete.

- [ ] **Step 6: Commit concise team and score cards**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/test_retrospective_deck_browser.py
git commit -m "style: make leader and score evidence answer-first"
```

---

### Task 6: Regenerate the artifact and run complete structural, browser, and repository verification

**Files:**
- Modify: `retrospective.html`
- Modify: `docs/superpowers/plans/2026-07-13-answer-first-retrospective-diagnosis.md`
- Test: `tests/report/retrospective_deck.test.mjs`
- Test: `tests/report/test_retrospective_deck_browser.py`

**Interfaces:**
- Consumes: the completed enhancer and unchanged portable evidence layer.
- Produces: the final self-contained `retrospective.html` and a completed implementation checklist.

- [ ] **Step 1: Regenerate the committed HTML deterministically**

```bash
node scripts/report/retrospective_deck.mjs --input retrospective.html --output retrospective.html
node scripts/report/retrospective_deck.mjs --check retrospective.html
```

Expected:

```text
wrote retrospective.html
PASS: 74 blocks mapped into 8 chapters
```

- [ ] **Step 2: Run Node structural tests**

```bash
node --test tests/report/retrospective_deck.test.mjs
```

Expected: all tests PASS; no skipped or failing tests.

- [ ] **Step 3: Run the complete report browser suite with the stable Playwright temp directory**

```bash
mkdir -p /var/tmp/mcrs-playwright-tmp
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py
```

Expected: all report browser tests PASS with no page errors or external requests.

- [ ] **Step 4: Run responsive overflow checks at every required viewport**

Add this parametrized browser test so every diagnosis and reusable-visual slide is covered:

```python
@pytest.mark.parametrize("viewport", [(1533, 903), (1280, 800), (1024, 768), (390, 844)])
def test_answer_first_slides_have_no_overflow(viewport, enhanced_report: Path) -> None:
    width, height = viewport
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": width, "height": height})
        for slug in (
            "diagnosis/score-location", "diagnosis/information-loss", "diagnosis/constraint-wiring",
            "diagnosis/features-seen", "diagnosis/evidence-missed", "diagnosis/confidence",
            "query/provenance-stacks", "retrieval/evidence-heatmap", "response/control-heatmap",
        ):
            open_deck(page, enhanced_report, f"#{slug}")
            slide = page.locator(f"#{slug.replace('/', r'\\/')}")
            assert slide.evaluate("node => node.scrollWidth <= node.clientWidth + 2")
            assert slide.locator("*:visible").evaluate_all(
                "nodes => nodes.every(node => getComputedStyle(node).overflowY !== 'scroll' || node.scrollHeight <= node.clientHeight + 2)"
            )
        browser.close()
```

Run:

```bash
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k answer_first_slides_have_no_overflow
```

Expected: four viewport cases PASS.

- [ ] **Step 5: Verify payload, canonical blocks, links, iframes, and deterministic regeneration**

```bash
node --test tests/report/retrospective_deck.test.mjs --test-name-pattern 'deterministic|preserves payload|assigns all'
TMPDIR=/var/tmp/mcrs-playwright-tmp pytest -q tests/report/test_retrospective_deck_browser.py -k 'enhancer_does_not_change_embedded_payload or javascript_disabled or no_external_requests'
git diff --check
```

Expected: all selected tests PASS and `git diff --check` emits no output.

- [ ] **Step 6: Run the repository test suite**

```bash
uv run pytest -q
```

Expected: no failures; at least the prior baseline of 788 passed and one skipped test, with only the two pre-existing Pydantic deprecation warnings plus any explicitly explained environment warning.

- [ ] **Step 7: Mark plan checkboxes complete and commit the final artifact**

Use `apply_patch` to change completed plan steps from `- [ ]` to `- [x]`, then run:

```bash
git add retrospective.html scripts/report/retrospective_deck.mjs tests/report/retrospective_deck.test.mjs tests/report/test_retrospective_deck_browser.py docs/superpowers/plans/2026-07-13-answer-first-retrospective-diagnosis.md
git commit -m "feat: deliver answer-first retrospective report"
```

- [ ] **Step 8: Verify clean worktree and served artifact parity**

```bash
git status --short
sha256sum retrospective.html
curl -fsS http://127.0.0.1:8766/ | sha256sum
```

Expected: `git status --short` emits no output and both SHA-256 values match. If the private viewer is not running, start the existing local-only viewer on port 8766 before the parity check; do not expose or publish a new service.

---

## Completion Criteria

- The report opens with outcome followed immediately by the six-slide diagnosis.
- The curated 12–15-slide path and complete audit path both work.
- The candidate-versus-feature boundary is visually explicit.
- The submitted 142-feature families and the missing/differentiating evidence are clearly separated.
- Conversation-state extraction is shown as rich, with uneven operationalization rather than falsely described as absent.
- LLM knowledge is shown as present but insufficiently grounded and reused.
- Response generation is accurately shown as one Blind-B call with no independent quality-control loop.
- Belief update, failure taxonomy, shift uncertainty, and candidate-recall unknowns are visible.
- Repeated prose is compressed into heatmaps, pipeline lanes, provenance stacks, system cards, and named disclosures.
- Every canonical block, source record, link, iframe document, and artifact payload remains intact.
- All structural, browser, responsive, and repository tests pass.
