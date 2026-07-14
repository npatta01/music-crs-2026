# Synthesis Matrix Decoder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a visual slide after the synthesis matrix that plainly defines reranker evidence breadth, full candidate union or late fusion, and factual grounding while naming the submitted system's concrete strengths and gaps.

**Architecture:** Extend the existing declarative slide manifest with a `matrix-decoder` visual kind and three evidence-bounded card records. Render the records with one focused DOM renderer and responsive CSS, then regenerate the self-contained HTML using the existing enhancer. No canonical report blocks or external assets are added.

**Tech Stack:** Node.js ES modules, browser DOM APIs, CSS Grid, Python Playwright tests, Node's built-in test runner.

## Global Constraints

- The existing synthesis matrix remains compact and unchanged.
- The decoder follows `synthesis/matrix` in audit and curated navigation.
- Every card visibly contains a definition, mechanism, **We had**, **We lacked**, and **Why it matters**.
- The submitted candidate path is “up to 500 hits from each traced branch → union → LightGBM final ordering”; do not claim RRF fed LightGBM.
- “Missing” means not documented in the reviewed deployed path unless explicitly stated otherwise.
- The slide must not claim that feature count or any one mechanism caused the hidden Blind-B result.
- Definitions and contrasts are visible text, never hover-only.
- Desktop/tablet use a balanced grid; narrow screens stack without horizontal overflow.

---

### Task 1: Define the Decoder Slide Contract

**Files:**
- Modify: `tests/report/retrospective_deck.test.mjs`
- Modify: `scripts/report/retrospective_deck.mjs`

**Interfaces:**
- Consumes: `slide(slug, title, archetype, blocks, options)`, `CHAPTERS`, and `CURATED_PATH`.
- Produces: `synthesis/decoder` with `visualKind: "matrix-decoder"` and `concepts: Array<{ term, definition, stages, had, lacked, why }>`.

- [ ] **Step 1: Write the failing manifest test**

Add:

```javascript
test("synthesis decoder makes compressed matrix terms concrete", () => {
  const synthesis = CHAPTERS.find(({ slug }) => slug === "synthesis");
  const matrixIndex = synthesis.slides.findIndex(({ slug }) => slug === "matrix");
  const decoder = synthesis.slides[matrixIndex + 1];
  assert.equal(decoder.slug, "decoder");
  assert.equal(decoder.visualKind, "matrix-decoder");
  assert.equal(decoder.concepts.length, 3);
  const copy = JSON.stringify(decoder);
  for (const phrase of [
    "direct track co-occurrence",
    "Markov transition probability",
    "learned-retriever",
    "generated-description similarity",
    "up to 500 hits from each traced branch",
    "LightGBM",
    "verified fact bundle",
    "checker or repair",
  ]) assert.match(copy, new RegExp(phrase, "i"));
  assert.doesNotMatch(copy, /RRF.{0,80}LightGBM|LightGBM.{0,80}RRF/i);
  assert.ok(CURATED_PATH.includes("synthesis/decoder"));
  assert.ok(CURATED_PATH.indexOf("synthesis/decoder") < CURATED_PATH.indexOf("synthesis/lessons"));
});
```

Update the existing page-count expectations from 56 to 57 and synthesis chapter count from 5 to 6.

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
node --test --test-name-pattern="synthesis decoder|visual-first manifest|complete content-aware" tests/report/retrospective_deck.test.mjs
```

Expected: FAIL because `synthesis/decoder` is absent and the page count remains 56.

- [ ] **Step 3: Add the declarative slide data**

Insert `"synthesis/decoder"` before `"synthesis/lessons"` in `CURATED_PATH`. Insert this slide immediately after the matrix:

```javascript
slide("decoder", "Decode three important rows", "visual", [], {
  visualKind: "matrix-decoder",
  concepts: [
    {
      term: "Reranker evidence breadth",
      definition: "Signals LightGBM can inspect for candidates that already reached it; richness means diverse decision evidence, not just more columns.",
      stages: ["Candidate in union", "Feature evidence", "LightGBM score"],
      had: ["142 documented features", "Branch ranks/scores and agreement", "Dense, multimodal, CF/BPR centroid, state, and catalog evidence"],
      lacked: ["Direct track co-occurrence sum/max/probability or lane membership", "Markov transition probability", "Candidate-producing learned-retriever rank/score", "Grounded generated-description similarity", "Stronger explicit behavior-derived priors"],
      why: "A reranker cannot use source evidence that was never generated or attached to a candidate.",
    },
    {
      term: "Full candidate union / late fusion",
      definition: "A full union keeps every deduplicated source candidate; late fusion keeps source evidence separate until a later scorer combines it.",
      stages: ["Up to 500 hits from each traced branch", "Filtered candidate union", "LightGBM final ordering"],
      had: ["Multiple deployed retrieval branches", "Per-branch candidate evidence", "LightGBM final ordering of the union"],
      lacked: ["Tracks never emitted by a deployed branch", "Tracks removed before the union", "A candidate-producing lane from the trained two-tower"],
      why: "Anything outside the ranker's union was unrecoverable, regardless of downstream model quality.",
    },
    {
      term: "Factual grounding",
      definition: "Response claims are constrained to facts traceable to the selected track, conversation state, catalog, or another verified record.",
      stages: ["Selected track", "Verified fact bundle", "Allowed claims", "Checker or repair", "Final response"],
      had: ["Selected track", "Latest conversation state", "Track and catalog metadata"],
      lacked: ["Independent structured fact checker", "Theme or citation validation", "Repair pass for unsupported claims", "Selection among multiple grounded drafts"],
      why: "Our response had grounded inputs, so coverage is Partial; it lacked independent verification and repair controls.",
    },
  ],
}),
```

- [ ] **Step 4: Run the manifest tests and verify GREEN**

Run the command from Step 2.

Expected: PASS.

- [ ] **Step 5: Commit the contract**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/retrospective_deck.test.mjs
git commit -m "feat: define synthesis matrix decoder"
```

---

### Task 2: Render and Verify the Visual Decoder

**Files:**
- Modify: `tests/report/test_retrospective_deck_browser.py`
- Modify: `scripts/report/retrospective_deck.mjs`
- Regenerate: `retrospective.html`

**Interfaces:**
- Consumes: the `matrix-decoder` concept contract from Task 1.
- Produces: `renderMatrixDecoder(entry) -> HTMLElement`, using `.deck-matrix-decoder`, `.deck-decoder-card`, `.deck-decoder-flow`, `.deck-decoder-had`, and `.deck-decoder-lacked`.

- [ ] **Step 1: Write failing browser tests**

Add:

```python
def test_synthesis_decoder_defines_terms_and_concrete_gaps(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report, "?path=curated#synthesis/decoder")
    slide = browser_page.locator("[id='synthesis/decoder']")
    assert slide.is_visible()
    assert slide.locator(".deck-decoder-card").count() == 3
    text = slide.inner_text()
    for phrase in (
        "Reranker evidence breadth",
        "Direct track co-occurrence",
        "Markov transition probability",
        "candidate-producing learned-retriever",
        "Full candidate union / late fusion",
        "Up to 500 hits from each traced branch",
        "LightGBM final ordering",
        "Factual grounding",
        "Verified fact bundle",
        "Checker or repair",
        "We had",
        "We lacked",
        "Why it matters",
    ):
        assert phrase.lower() in text.lower()
    assert "RRF" not in text
    assert errors == []


@pytest.mark.parametrize("viewport", [(1533, 903), (1024, 768), (390, 844)])
def test_synthesis_decoder_has_no_horizontal_overflow(page, enhanced_report: Path, viewport) -> None:
    browser_page, errors = page
    browser_page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
    open_deck(browser_page, enhanced_report, "#synthesis/decoder")
    overflow = browser_page.locator("[id='synthesis/decoder'] .deck-slide-inner").evaluate(
        "node => node.scrollWidth - node.clientWidth"
    )
    assert overflow <= 1
    assert errors == []
```

- [ ] **Step 2: Run the browser tests and verify RED**

Run:

```bash
TMPDIR=/var/tmp/mcrs-playwright-tmp uv run pytest -q tests/report/test_retrospective_deck_browser.py -k synthesis_decoder
```

Expected: FAIL because the slide has no decoder DOM.

- [ ] **Step 3: Implement the renderer and responsive CSS**

Add a `renderMatrixDecoder` function beside the other focused visual renderers. It must:

1. create a `section.deck-matrix-decoder`;
2. create one `article.deck-decoder-card` per concept;
3. render `definition` as a paragraph;
4. render `stages` as an ordered horizontal flow;
5. render `had` and `lacked` as labeled lists; and
6. render `why` beneath a visible “Why it matters” label.

Call it from the visual dispatch:

```javascript
if (entry.visualKind === "matrix-decoder") inner.append(renderMatrixDecoder(entry));
```

Add CSS Grid styles that use three columns on wide canvases, reduce to one column under the existing tablet breakpoint, stack flow stages on narrow screens, and use green/amber borders plus text labels so meaning is not color-only.

- [ ] **Step 4: Regenerate the artifact**

```bash
node scripts/report/retrospective_deck.mjs --input retrospective.html --output retrospective.html
```

Expected: `wrote retrospective.html`.

- [ ] **Step 5: Run focused tests and verify GREEN**

```bash
node --test tests/report/retrospective_deck.test.mjs
TMPDIR=/var/tmp/mcrs-playwright-tmp uv run pytest -q tests/report/test_retrospective_deck_browser.py -k "synthesis_decoder or synthesis_matrix"
```

Expected: all selected tests PASS.

- [ ] **Step 6: Run full verification**

```bash
TMPDIR=/var/tmp/mcrs-playwright-tmp uv run pytest -q
node scripts/report/retrospective_deck.mjs --check retrospective.html
git diff --check
```

Expected: repository tests PASS, mapping reports 74 blocks across 8 chapters, and `git diff --check` emits no output.

- [ ] **Step 7: Commit and update the PR branch**

```bash
git add scripts/report/retrospective_deck.mjs tests/report/retrospective_deck.test.mjs tests/report/test_retrospective_deck_browser.py retrospective.html
git commit -m "feat: explain synthesis matrix terms"
git push
```

Expected: branch `codex/retrospective-report` updates PR #198.
