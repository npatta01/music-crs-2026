# Two-Slide Visual Retrospective Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace dense paragraph- and matrix-first retrospective pages with an approved two-slide teaching sequence while preserving every canonical fact, source, link, and audit block.

**Architecture:** Keep the 74 canonical portable-report blocks unchanged and enhance them at runtime in `scripts/report/retrospective_deck.mjs`. Add manifest-driven native visual summaries for mechanisms and team differences, wrap the original dense blocks in accessible disclosures, and retain their canonical order in linear and print modes. Extend the existing browser tests so layout, accessibility, evidence integrity, and the corrected 500-per-branch candidate boundary are verified before regenerating `retrospective.html`.

**Tech Stack:** Node.js ES modules, native DOM/CSS, self-contained portable HTML, Playwright/Chromium through pytest, Node's built-in test runner, Git.

## Global Constraints

- Preserve all 74 canonical blocks, ten source records, commit-pinned acknowledgements, calculations, links, iframe documents, and evidence boundaries.
- Use at least 50 vertical pages across the existing seven horizontal chapters; add a page only for a distinct teaching or comparison purpose.
- Dense subjects follow `mechanism slide → differences slide → expandable exact evidence`.
- Visual summaries use native accessible HTML; no abstract or decorative raster imagery.
- No internal vertical scrollbar, clipped evidence object, or unintended document-level horizontal overflow at 1,440×900, 1,280×800, 1,024×768, or 390×844.
- Teal means shared/verified, blue and violet identify stages, amber identifies limits or unbounded model knowledge, and neutral gray means not documented; every color has a redundant text label or structural cue.
- Preserve deck, linear, print, keyboard, history, direct-hash, reduced-motion, forced-color, and JavaScript-disabled behavior.
- Keep the report private and local; do not publish or alter sharing permissions.

---

## File map

- `scripts/report/retrospective_deck.mjs` — page manifest, visual-summary data, native DOM renderers, disclosure wrapping, responsive styles, and build entrypoint.
- `tests/report/retrospective_deck.test.mjs` — manifest, evidence-integrity, corrected candidate-pool semantics, and deterministic-build tests.
- `tests/report/test_retrospective_deck_browser.py` — rendered structure, progressive disclosure, sizing, overflow, accessibility, and navigation tests.
- `retrospective.html` — regenerated self-contained output; never hand-edited.
- `docs/superpowers/specs/2026-07-13-visual-first-retrospective-pagination-design.md` — approved design source; no further content change expected.

### Task 1: Lock the approved information architecture and factual correction

**Files:**
- Modify: `tests/report/retrospective_deck.test.mjs`
- Modify: `scripts/report/retrospective_deck.mjs`

**Interfaces:**
- Consumes: existing `CHAPTERS`, `DISCLOSURES`, `validateChapterMap()`, and the 74 canonical block IDs.
- Produces: slide options `visualKind`, `takeaway`, `common`, `different`, and `teams`; at least 51 pages; corrected inference wording `Top 500 from each branch → candidate union`.

- [x] **Step 1: Write failing manifest tests**

Add tests equivalent to:

```js
test("dense comparison topics use teach-then-compare pairs", () => {
  const pairs = [
    ["query/lifecycle", "query/query-matrix"],
    ["query/data-glossary", "query/data-matrix"],
    ["retrieval/retriever-mechanism", "retrieval/retriever-matrix"],
    ["response/overview", "response/matrix"],
  ];
  const pages = new Map(CHAPTERS.flatMap(chapter => chapter.slides.map(entry => [`${chapter.slug}/${entry.slug}`, entry])));
  for (const [mechanismSlug, comparisonSlug] of pairs) {
    assert.equal(pages.get(mechanismSlug)?.visualKind, "mechanism");
    assert.equal(pages.get(comparisonSlug)?.visualKind, "comparison");
    assert.ok(pages.get(comparisonSlug)?.teams?.length >= 4);
  }
});

test("submitted inference takes five hundred candidates from every branch", () => {
  const lane = CHAPTERS.find(chapter => chapter.slug === "ours")
    .slides.find(entry => entry.slug === "inference-rail").lanes[0];
  assert.ok(lane.steps.includes("Top 500 from each branch → candidate union"));
  assert.equal(lane.steps.some(step => /union \(up to 500\)/i.test(step)), false);
});
```

- [x] **Step 2: Run the tests and confirm the intended failures**

Run: `node --test tests/report/retrospective_deck.test.mjs`

Expected: FAIL because the visual metadata, retrieval mechanism page, and corrected branch wording do not exist.

- [x] **Step 3: Update the manifest with complete visual data**

In `CHAPTERS`:

- mark query lifecycle, data provenance, retrieval mechanism, and response overview as `visualKind: "mechanism"`;
- mark the query, data, retrieval, and response matrix slides as `visualKind: "comparison"`;
- add `retrieval/retriever-mechanism`, making the chapter counts `[6, 7, 6, 7, 7, 13, 5]` and total page count 51;
- supply concise `common`, `different`, and five-team rows using only already reviewed claims;
- keep the original matrix block on its comparison page and register it in `DISCLOSURES`;
- change the submitted inference steps to:

```js
[
  "DeepSeek state extraction",
  "BM25, multimodal ANN, and lookup branches",
  "Top 500 from each branch → candidate union",
  "LightGBM LambdaMART reorders the union",
  "Top-1 selected track",
  "Single-pass response",
]
```

- [x] **Step 4: Run the manifest tests**

Run: `node --test tests/report/retrospective_deck.test.mjs`

Expected: PASS with 74 blocks assigned exactly once and 51 pages.

- [x] **Step 5: Commit the manifest contract**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/retrospective_deck.test.mjs
git commit -m "test: define two-slide retrospective structure"
```

### Task 2: Build reusable native visual-summary components

**Files:**
- Modify: `tests/report/test_retrospective_deck_browser.py`
- Modify: `scripts/report/retrospective_deck.mjs`

**Interfaces:**
- Consumes: slide options from Task 1 and the existing `.deck-flow`, `.deck-disclosure`, and `.deck-slide-inner` containers.
- Produces: `.deck-mechanism`, `.deck-comparison`, `.deck-team-row`, `.deck-common-different`, and accessible disclosure DOM; `renderMechanism(entry)` and `renderComparison(entry)` local runtime helpers.

- [x] **Step 1: Write failing browser tests for the two-slide components**

Add tests equivalent to:

```python
def test_dense_topics_teach_then_compare(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#query/lifecycle")
    for mechanism, comparison in (
        ("query/lifecycle", "query/query-matrix"),
        ("query/data-glossary", "query/data-matrix"),
        ("retrieval/retriever-mechanism", "retrieval/retriever-matrix"),
        ("response/overview", "response/matrix"),
    ):
        assert browser_page.locator(f"[id='{mechanism}'] .deck-mechanism").count() == 1
        assert browser_page.locator(f"[id='{comparison}'] .deck-comparison").count() == 1
        assert browser_page.locator(f"[id='{comparison}'] .deck-team-row").count() >= 4
        assert browser_page.locator(f"[id='{comparison}'] .deck-common-different").count() == 1
    assert errors == []

def test_exact_dense_evidence_is_progressively_disclosed(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#query/query-matrix")
    details = browser_page.locator("[id='query/query-matrix'] details[data-disclosure-for='query_matrix']")
    assert details.count() == 1
    assert not details.is_open()
    assert not details.locator("[data-artifact-block-id='query_matrix']").is_visible()
    details.locator("summary").click()
    assert details.locator("[data-artifact-block-id='query_matrix']").is_visible()
```

- [x] **Step 2: Run the focused browser tests and confirm failure**

Run: `uv run pytest -q tests/report/test_retrospective_deck_browser.py -k 'teach_then_compare or progressively_disclosed'`

Expected: FAIL because the components and actual disclosure wrappers do not exist.

- [x] **Step 3: Implement accessible DOM renderers and disclosure wrapping**

In `runtimeMain(CONFIG)`:

```js
const wrapDisclosure = (node, label) => {
  if (!label) return node;
  const details = document.createElement("details");
  details.className = "deck-disclosure";
  details.dataset.disclosureFor = node.dataset.artifactBlockId;
  const summary = document.createElement("summary");
  summary.textContent = label;
  details.append(summary, node);
  return details;
};
```

Implement `renderMechanism(entry)` as a semantic `<section>` with an ordered stage list and a short takeaway. Implement `renderComparison(entry)` as a `<section>` containing labeled team rows and a final two-column `Common`/`Different` region. Text must come from manifest data, use native text nodes, and never use `innerHTML` for factual content.

Call these renderers after the page heading and before canonical blocks. Replace the identity `disclosure` helper with `wrapDisclosure`.

- [x] **Step 4: Add responsive, color-redundant presentation styles**

Add scoped CSS with these behaviors:

```css
.deck-mechanism-stages{display:grid;grid-template-columns:repeat(var(--stage-count),minmax(0,1fr));gap:26px;list-style:none;padding:0}
.deck-mechanism-stage{position:relative;min-height:132px;padding:18px;border:1px solid var(--portable-border);border-top:4px solid var(--stage-color);border-radius:14px;background:var(--portable-surface)}
.deck-comparison{display:grid;gap:12px}
.deck-team-row{display:grid;grid-template-columns:minmax(100px,.5fr) repeat(3,minmax(0,1fr));gap:14px;padding:14px 16px;border-left:5px solid var(--team-color);border-radius:12px;background:var(--portable-surface)}
.deck-common-different{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:900px){.deck-mechanism-stages,.deck-team-row,.deck-common-different{grid-template-columns:1fr}.deck-mechanism-stage:not(:last-child)::after{content:"↓"}}
```

Use text headings (`Shared`, `Difference`, `Limit`, `Not documented`) so meaning does not depend on color.

- [x] **Step 5: Run focused and full browser tests**

Run:

```bash
uv run pytest -q tests/report/test_retrospective_deck_browser.py -k 'teach_then_compare or progressively_disclosed'
uv run pytest -q tests/report/test_retrospective_deck_browser.py
```

Expected: all browser tests PASS with no page errors.

- [x] **Step 6: Commit the reusable visual layer**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/test_retrospective_deck_browser.py
git commit -m "feat: add layered visual comparison slides"
```

### Task 3: Compact the leaderboard and remaining text-heavy pages

**Files:**
- Modify: `tests/report/test_retrospective_deck_browser.py`
- Modify: `scripts/report/retrospective_deck.mjs`

**Interfaces:**
- Consumes: canonical leaderboard table, existing progressive insight cards, and reusable disclosure styles from Task 2.
- Produces: `.deck-scoreboard`, `.deck-score-row`, compact exact-table disclosure, and presentation-scale summaries for the reported dense pages.

- [x] **Step 1: Write failing compact-layout tests**

Add tests equivalent to:

```python
def test_leaderboard_uses_compact_ranked_rows(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "#outcome/leaderboard-table")
    rows = browser_page.locator("[id='outcome/leaderboard-table'] .deck-score-row")
    assert rows.count() == 5
    assert browser_page.locator("[id='outcome/leaderboard-table'] .deck-scoreboard").count() == 1
    box = browser_page.locator("[id='outcome/leaderboard-table'] .deck-scoreboard").bounding_box()
    assert box is not None and box["height"] < 430
    assert browser_page.locator("[id='outcome/leaderboard-table'] details[data-disclosure-for='leaderboard_table']").count() == 1
    assert errors == []

def test_visual_first_default_has_bounded_visible_prose(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    for slug in ("query/query-glossary", "query/data-matrix", "retrieval/retriever-matrix", "response/matrix"):
        text = browser_page.locator(f"[id='{slug}']").evaluate(
            "node => [...node.querySelectorAll('p')].filter(p => p.offsetParent !== null).map(p => p.textContent).join(' ')"
        )
        assert len(text.split()) <= 120
```

- [x] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest -q tests/report/test_retrospective_deck_browser.py -k 'leaderboard_uses_compact or bounded_visible_prose'`

Expected: FAIL because the scoreboard does not exist and dense blocks remain visible by default.

- [x] **Step 3: Render the numeric leaderboard as compact native rows**

Build `.deck-scoreboard` from the five canonical table rows at runtime. Each row displays rank, team, composite, nDCG@20, catalog diversity, lexical diversity, and LLM judge in one horizontal band; composite gets a proportional bar. Keep the original table inside `details[data-disclosure-for="leaderboard_table"]` and label it `Open exact values and repository links`.

Do not duplicate or hard-code score values: read cell text and headers from the canonical table before moving it into the disclosure.

- [x] **Step 4: Reduce visible prose without deleting evidence**

- put `query_heading`, `query_explainer`, `data_knowledge_heading`, `data_knowledge_glossary`, `retrieval_heading`, `retrieval_glossary`, `response_heading`, and `response_explainer` behind named disclosures;
- preserve volart-style architecture diagrams unchanged;
- preserve progressive insight cards on the submitted-system and leader response pages;
- remove only redundant visible orientation sentences generated by the deck enhancer, never canonical evidence.

- [x] **Step 5: Run the compact-layout and regression tests**

Run:

```bash
node --test tests/report/retrospective_deck.test.mjs
uv run pytest -q tests/report/test_retrospective_deck_browser.py
```

Expected: all tests PASS.

- [x] **Step 6: Commit the compact default view**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/test_retrospective_deck_browser.py
git commit -m "style: compact retrospective evidence overviews"
```

### Task 4: Regenerate, verify, and hand off the portable artifact

**Files:**
- Modify: `retrospective.html`
- Verify: `scripts/report/retrospective_deck.mjs`
- Verify: `tests/report/retrospective_deck.test.mjs`
- Verify: `tests/report/test_retrospective_deck_browser.py`

**Interfaces:**
- Consumes: completed enhancer and the existing self-contained portable report.
- Produces: updated `retrospective.html`, unchanged embedded artifact payload, passing browser suite, and a working private LAN viewer.

- [x] **Step 1: Regenerate the self-contained HTML idempotently**

Run twice:

```bash
node scripts/report/retrospective_deck.mjs --input retrospective.html --output retrospective.html
node scripts/report/retrospective_deck.mjs --input retrospective.html --output retrospective.html
```

Expected: both commands print `wrote retrospective.html`; the second run produces no additional structural changes.

- [x] **Step 2: Run structural, browser, and repository checks**

Run:

```bash
node --test tests/report/retrospective_deck.test.mjs
uv run pytest -q tests/report/test_retrospective_deck_browser.py
node scripts/report/retrospective_deck.mjs --check retrospective.html
git diff --check
```

Expected: Node tests PASS, browser tests PASS, enhancer check reports 74 mapped blocks across seven chapters, and `git diff --check` exits 0.

- [x] **Step 3: Inspect target viewports and supplied failure pages**

Capture or inspect these hashes at 1,533×903, 1,280×800, 1,024×768, and 390×844:

```text
#outcome/leaderboard-table
#query/lifecycle
#query/query-matrix
#query/data-glossary
#query/data-matrix
#retrieval/retriever-mechanism
#retrieval/retriever-matrix
#ours/inference-rail
#leaders/volart-retrieval
#leaders/volart-response
#synthesis/matrix
```

Confirm large type, intentional canvas use, no nested scrolling, readable mobile stacking, visible `Common`/`Different` summaries, exact evidence disclosures, and the phrase `Top 500 from each branch → candidate union`.

- [x] **Step 4: Verify the private viewer serves the latest file**

Run:

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8766/
curl -fsS http://127.0.0.1:8766/ | sha256sum
sha256sum retrospective.html
```

Expected: HTTP 200 and identical SHA-256 values. If the viewer is not running, restart the existing private no-store Node viewer on port 8766 without publishing it externally.

- [x] **Step 5: Commit the generated artifact**

```bash
git add retrospective.html
git commit -m "feat: render visual-first retrospective deck"
```

- [x] **Step 6: Final evidence-based handoff**

Report the exact test counts, the final page count, the corrected branch-pool wording, the LAN URL, and links to `retrospective.html`, the approved spec, and this plan. Do not claim completion until all commands above pass.
