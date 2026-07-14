# Organizer-First Approach Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the opening and chapter order of `docs/approach.html` so competition organizers can understand the final submitted Music-CRS architecture, one verified example, and the evaluation loop within one minute.

**Architecture:** Keep `docs/approach/source.html` as the canonical semantic HTML and generate the self-contained `docs/approach.html` with the existing build script. Replace decorative PNGs with native HTML/CSS diagrams, distinguish compiler candidate-pool assembly from the final LightGBM ordering, then preserve the detailed chapters as vertically stacked, progressively disclosed slides.

**Tech Stack:** Semantic HTML5, responsive CSS, Python 3.12 standard library, `unittest`/`pytest`, headless Google Chrome, Git.

## Global Constraints

- The final submitted config is `configs/state_ranker_v10_lgbm_blindset_B.yaml` with `ranking.mode: lgbm`; the overview must state that LightGBM determines the delivered ordering.
- Label the compiler stage `Candidate pool assembly`; weighted-RRF mechanics belong only in the retrieval deep dive and must not be presented as the final ranker.
- Remove decorative bitmap illustrations from the visible report.
- The first-minute map must include the online serving path and a visually separate offline evaluation loop.
- State must visibly include intent mode, policy, routing, resolved entities, positive/negative facets, hard constraints, and history treatment.
- Response generation explains rank one and cannot select another track.
- Local, hosted API, and Modal are small placement badges, not the architecture's organizing principle.
- Preserve evidence labels and distinguish verified, reconstructed/inferred, illustrative, and unknown claims.
- Keep core content usable without JavaScript and without external runtime resources.
- Keep the page vertically readable on mobile with no page-level horizontal scrolling.
- Do not edit `docs/approach.html` by hand; regenerate it from `docs/approach/source.html`.

---

### Task 1: Remove the Decorative-Image Build Contract

**Files:**
- Modify: `scripts/build_approach_report.py`
- Modify: `scripts/validate_approach_report.py`
- Modify: `tests/test_approach_report.py`
- Modify: `docs/approach/source.html`

**Interfaces:**
- Consumes: `build(source_path: Path, output_path: Path) -> int` and `validate(report: Path) -> list[str]`.
- Produces: a deterministic self-contained build that accepts a report containing zero runtime images and rejects any non-data runtime resource.

- [ ] **Step 1: Write failing build and validation tests**

Add tests that remove both template placeholders from the source fixture and require a zero-image report to validate:

```python
def test_build_supports_a_report_without_decorative_assets(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "docs" / "approach" / "source.html"
        output = root / "docs" / "approach.html"
        source.parent.mkdir(parents=True)
        source.write_text("<main>No decorative images</main>", encoding="utf-8")

        build_approach_report.build(source, output)

        self.assertEqual(output.read_text(encoding="utf-8"), "<main>No decorative images</main>")


def test_zero_embedded_pngs_are_allowed(self) -> None:
    report = valid_report().replace(f'<img src="{PNG_DATA}" alt="one">', "")
    report = report.replace(f'<img src="{PNG_DATA}" alt="two">', "")
    self.assertEqual(self.validate_fixture(report), [])
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest \
  tests.test_approach_report.ApproachReportBuildTests.test_build_supports_a_report_without_decorative_assets \
  tests.test_approach_report.ApproachReportValidationTests.test_zero_embedded_pngs_are_allowed -v
```

Expected: the build test fails because the builder still requires both placeholders; the validator test fails because it expects exactly two embedded PNGs.

- [ ] **Step 3: Make assets optional and remove the PNG-count requirement**

Change the builder loop so it replaces an asset only when its placeholder exists, while still rejecting duplicates:

```python
for placeholder, asset_path in ASSETS:
    count = packaged.count(placeholder)
    if count > 1:
        raise ValueError(
            f"expected placeholder at most once: {placeholder}; found {count}"
        )
    if count == 1:
        packaged = packaged.replace(placeholder, png_data_uri(asset_path))
```

Delete the validator's `len(parser.png_data_uris) != 2` error. Retain base64 and PNG-signature validation for any embedded PNG that remains.

Remove both `<figure>` blocks containing `{{HERO_DATA_URI}}` and `{{ALIGNMENT_DATA_URI}}` from `docs/approach/source.html`; remove their image-specific CSS and print rules.

- [ ] **Step 4: Run focused tests and report validation**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest tests.test_approach_report -v
uv run --no-sync python scripts/build_approach_report.py
PYTHONPATH=. uv run --no-sync python scripts/validate_approach_report.py docs/approach.html
```

Expected: all approach-report tests pass and the validator prints `approach report valid`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_approach_report.py scripts/validate_approach_report.py \
  tests/test_approach_report.py docs/approach/source.html docs/approach.html
git commit -m "docs: remove decorative report images"
```

---

### Task 2: Build the First-Minute Architecture Map

**Files:**
- Modify: `docs/approach/source.html`
- Modify: `tests/test_approach_report.py`

**Interfaces:**
- Consumes: the existing `section#overview`, evidence-backed system facts, and the active Blind-B config.
- Produces: `.architecture-map`, `.online-path`, `.retrieval-mesh`, `.offline-loop`, and `.architecture-invariants` elements before `.deep-dive-boundary`.

- [ ] **Step 1: Replace the old five-stage test with architecture-contract tests**

Add a helper and tests that inspect only the content before the deep-dive boundary:

```python
def report_opening() -> str:
    source = REPORT_SOURCE.read_text(encoding="utf-8")
    return source[source.index('<header class="hero">') : source.index(
        '<div class="deep-dive-boundary"'
    )]


def test_opening_contains_complete_submitted_architecture(self) -> None:
    opening = report_opening()
    for label in (
        "Conversation",
        "LLM state",
        "V1 → V0Plus projection",
        "Entity resolution",
        "Query compiler",
        "Retrieval mesh",
        "Candidate pool assembly",
        "LightGBM LambdaMART",
        "Final artist guard",
        "Top 20",
        "Top-1 explanation",
    ):
        self.assertIn(label, opening)
    self.assertIn('class="offline-loop"', opening)
    self.assertIn("LLM-as-judge", opening)


def test_opening_does_not_present_rrf_as_the_final_ranker(self) -> None:
    opening = report_opening()
    self.assertNotIn("Weighted RRF", opening)
    self.assertIn("LightGBM determines the final order", opening)


def test_opening_has_no_decorative_image(self) -> None:
    self.assertNotIn("<img", report_opening())
```

- [ ] **Step 2: Run the architecture tests and verify RED**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest \
  tests.test_approach_report.ApproachReportBuildTests.test_opening_contains_complete_submitted_architecture \
  tests.test_approach_report.ApproachReportBuildTests.test_opening_does_not_present_rrf_as_the_final_ranker \
  tests.test_approach_report.ApproachReportBuildTests.test_opening_has_no_decorative_image -v
```

Expected: failures for the missing architecture classes/labels and the old five-stage content.

- [ ] **Step 3: Replace the compact hero and five boxes with the semantic map**

Use this semantic structure in `section#overview`:

```html
<div class="architecture-map" aria-label="Final submitted Music-CRS architecture">
  <div class="architecture-head">
    <p class="eyebrow">First-minute system map</p>
    <h2 id="overview-title">Serving path and evaluation loop</h2>
  </div>
  <ol class="online-path" aria-label="Online recommendation path">
    <li class="architecture-node">Conversation</li>
    <li class="architecture-node state-node">LLM state → V1 → V0Plus projection → Entity resolution</li>
    <li class="architecture-node">Query compiler</li>
    <li class="architecture-node retrieval-mesh">Retrieval mesh</li>
    <li class="architecture-node">Candidate pool assembly</li>
    <li class="architecture-node rank-node">LightGBM LambdaMART</li>
    <li class="architecture-node">Final artist guard and Top 20</li>
    <li class="architecture-node response-node">Top-1 explanation</li>
  </ol>
  <div class="offline-loop" aria-label="Offline evaluation and improvement loop">
    <span>Saved traces and staged replay</span>
    <span>Ranking metrics and boundary analysis</span>
    <span>LLM-as-judge response evaluation</span>
    <span>Next experiment</span>
  </div>
  <ul class="architecture-invariants">
    <li>Retrieval sets the candidate ceiling.</li>
    <li>LightGBM determines the final order.</li>
    <li>Generation explains rank one; it does not select.</li>
  </ul>
</div>
```

Inside `.retrieval-mesh`, render compact labelled branches for BM25, Qwen metadata/attributes, lyrics, CLAP, SigLIP2, track/user centroids, resolved-artist discography, and era/popularity. Mark local/API/Modal only with `.placement-badge` elements.

- [ ] **Step 4: Add responsive map CSS**

On desktop, use a horizontal `grid` for `.online-path`; allow the retrieval node to be wider and show its branches as a three-column subgrid. At `max-width: 719px`, use one column, change connector arrows from `→` to `↓`, and make the offline loop a vertical stack. Do not set a fixed pixel width on the page or map.

- [ ] **Step 5: Run tests, rebuild, and inspect the opening source**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest tests.test_approach_report -v
uv run --no-sync python scripts/build_approach_report.py
PYTHONPATH=. uv run --no-sync python scripts/validate_approach_report.py docs/approach.html
```

Expected: all tests pass; the architecture labels appear before the deep-dive boundary; no decorative image remains.

- [ ] **Step 6: Commit**

```bash
git add docs/approach/source.html docs/approach.html tests/test_approach_report.py
git commit -m "docs: add first-minute system architecture"
```

---

### Task 3: Expand the Verified Example State

**Files:**
- Modify: `docs/approach/source.html`
- Modify: `tests/test_approach_report.py`
- Reference: `docs/approach/evidence.json`

**Interfaces:**
- Consumes: `primaryTrace.alignedGood` from `docs/approach/evidence.json`.
- Produces: `.executive-example` containing listener request, full captured-state summary, verified retrieval/ranking path, top pick, and response provenance.

- [ ] **Step 1: Write a failing state-coverage test**

```python
def test_executive_example_exposes_meaningful_state(self) -> None:
    opening = report_opening()
    for label in (
        "Intent mode",
        "Exploration policy",
        "Routing",
        "Resolved entities",
        "Positive facets",
        "Negative facets",
        "Hard constraints",
        "History treatment",
    ):
        self.assertIn(label, opening)
    self.assertIn("Pumped Up Kicks", opening)
    self.assertIn("BM25 rank 1", opening)
    self.assertIn("reference conversation text", opening)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest \
  tests.test_approach_report.ApproachReportBuildTests.test_executive_example_exposes_meaningful_state -v
```

Expected: failure because the old state cell contains only four positive tags.

- [ ] **Step 3: Replace `.quick-example` with `.executive-example`**

Render the verified fields exactly as supported by evidence:

```html
<div class="executive-example" aria-label="Verified Pumped Up Kicks devset example">
  <div><span class="mini-label">Listener</span><p>Energetic indie rock, popular, with a memorable whistle or a really strong bassline, maybe Foster The People or Cage The Elephant.</p></div>
  <div class="captured-state">
    <span class="mini-label">Captured state</span>
    <dl>
      <div><dt>Intent mode</dt><dd>refinement</dd></div>
      <div><dt>Exploration policy</dt><dd>diversify artists</dd></div>
      <div><dt>Routing</dt><dd>feature articulation</dd></div>
      <div><dt>Resolved entities</dt><dd>Foster The People · Cage The Elephant</dd></div>
      <div><dt>Positive facets</dt><dd>energetic · indie rock · popular · whistle · strong bassline · driving</dd></div>
      <div><dt>Negative facets</dt><dd>none recorded</dd></div>
      <div><dt>Hard constraints</dt><dd>none</dd></div>
      <div><dt>History treatment</dt><dd>no stale entities; diversify from the prior artist</dd></div>
    </dl>
  </div>
  <div><span class="mini-label">Retrieval and ranking</span><p>BM25 rank 1 → compiler candidate rank 1 → LightGBM final rank 1.</p></div>
  <div><span class="mini-label">Top pick</span><p><strong>Pumped Up Kicks</strong> — Foster The People</p></div>
  <div><span class="mini-label">Response provenance</span><p>The visible reply summary is reference conversation text; a generated response from this frozen run was not stored.</p></div>
</div>
```

- [ ] **Step 4: Add desktop and mobile state styling**

Use a two-column `<dl>` inside the wide captured-state cell on desktop. Collapse it to one column on mobile. Keep `dt` visibly distinct from `dd`, and do not encode positive/negative meaning through color alone.

- [ ] **Step 5: Run tests and rebuild**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest tests.test_approach_report -v
uv run --no-sync python scripts/build_approach_report.py
PYTHONPATH=. uv run --no-sync python scripts/validate_approach_report.py docs/approach.html
```

Expected: all report tests pass and the verified state labels are visible in the generated HTML.

- [ ] **Step 6: Commit**

```bash
git add docs/approach/source.html docs/approach.html tests/test_approach_report.py
git commit -m "docs: expand executive state example"
```

---

### Task 4: Reorder the Slides and Navigation

**Files:**
- Modify: `docs/approach/source.html`
- Modify: `scripts/validate_approach_report.py`
- Modify: `tests/test_approach_report.py`

**Interfaces:**
- Consumes: existing section IDs and internal fragment links.
- Produces: organizer order `overview → walkthrough → state → compile → ranking → response → infrastructure → evaluation → examples → gaps → lessons → reproduce` with sticky horizontal navigation and vertical chapter flow.

- [ ] **Step 1: Write failing section-order and navigation tests**

Set the expected section sequence in the validator and add:

```python
def test_source_uses_organizer_slide_order(self) -> None:
    source = REPORT_SOURCE.read_text(encoding="utf-8")
    ids = [
        "overview", "walkthrough", "state", "compile", "ranking", "response",
        "infrastructure", "evaluation", "examples", "gaps", "lessons", "reproduce",
    ]
    positions = [source.index(f'id="{section_id}"') for section_id in ids]
    self.assertEqual(positions, sorted(positions))


def test_directory_links_follow_organizer_order(self) -> None:
    source = REPORT_SOURCE.read_text(encoding="utf-8")
    directory = source[source.index('<nav class="directory') : source.index("</nav>")]
    labels = [
        "Architecture", "Worked example", "State", "Retrieval", "Ranking",
        "Response", "Compute", "Evaluation", "Examples", "Gaps", "Lessons", "Reproduce",
    ]
    positions = [directory.index(f">{label}<") for label in labels]
    self.assertEqual(positions, sorted(positions))
```

- [ ] **Step 2: Run the order tests and verify RED**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest \
  tests.test_approach_report.ApproachReportBuildTests.test_source_uses_organizer_slide_order \
  tests.test_approach_report.ApproachReportBuildTests.test_directory_links_follow_organizer_order -v
```

Expected: failure because infrastructure currently appears immediately after overview.

- [ ] **Step 3: Move whole semantic sections without changing their evidence content**

Move `section#walkthrough` directly after the directory, followed by state, compile, ranking, and response. Move `section#infrastructure` after response and before evaluation. Update `SECTION_IDS` in `scripts/validate_approach_report.py` to the exact organizer sequence above.

Change directory labels and order to:

```html
<a href="#overview">Architecture</a>
<a href="#walkthrough">Worked example</a>
<a href="#state">State</a>
<a href="#compile">Retrieval</a>
<a href="#ranking">Ranking</a>
<a href="#response">Response</a>
<a href="#infrastructure">Compute</a>
<a href="#evaluation">Evaluation</a>
<a href="#examples">Examples</a>
<a href="#gaps">Gaps</a>
<a href="#lessons">Lessons</a>
<a href="#reproduce">Reproduce</a>
```

- [ ] **Step 4: Add slide-like chapter hierarchy**

Give each chapter one outcome-led heading, one principal visual, and one short visible interpretation. Preserve long prompts, JSON, feature inventories, full candidate lists, and evidence ledgers inside existing `details` disclosures. Keep `.directory-shell` sticky above `56rem`; on smaller screens make `.directory ul` horizontally scrollable inside the navigation container without creating page-level overflow.

- [ ] **Step 5: Run report tests, build, and validator**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest tests.test_approach_report -v
uv run --no-sync python scripts/build_approach_report.py
PYTHONPATH=. uv run --no-sync python scripts/validate_approach_report.py docs/approach.html
```

Expected: all report tests pass; required sections appear once in organizer order; every internal link resolves.

- [ ] **Step 6: Commit**

```bash
git add docs/approach/source.html docs/approach.html \
  scripts/validate_approach_report.py tests/test_approach_report.py
git commit -m "docs: reorder approach report for organizers"
```

---

### Task 5: Correct Deep-Dive Ranking Language and Preserve Progressive Disclosure

**Files:**
- Modify: `docs/approach/source.html`
- Modify: `tests/test_approach_report.py`

**Interfaces:**
- Consumes: final Blind-B config, compiler mechanics, existing ranking trace, and existing disclosure components.
- Produces: accurate candidate-pool and final-ranking copy, plus explicit online/offline LLM-judge separation.

- [ ] **Step 1: Write failing terminology tests**

```python
def test_ranking_chapter_names_the_final_submitted_orderer(self) -> None:
    source = REPORT_SOURCE.read_text(encoding="utf-8")
    ranking = source[source.index('<section class="chapter" id="ranking"') : source.index(
        '<section class="chapter" id="response"'
    )]
    self.assertIn("ranking.mode: lgbm", ranking)
    self.assertIn("LightGBM determines the delivered order", ranking)
    self.assertIn("candidate pool assembly", ranking)


def test_evaluation_separates_ranking_metrics_from_llm_judging(self) -> None:
    source = REPORT_SOURCE.read_text(encoding="utf-8")
    evaluation = source[source.index('<section class="chapter" id="evaluation"') : source.index(
        '<section class="chapter" id="examples"'
    )]
    self.assertIn("Ranking relevance", evaluation)
    self.assertIn("Response quality", evaluation)
    self.assertIn("LLM-as-judge", evaluation)
    self.assertIn("does not rank tracks", evaluation)
```

- [ ] **Step 2: Run the terminology tests and verify RED**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest \
  tests.test_approach_report.ApproachReportBuildTests.test_ranking_chapter_names_the_final_submitted_orderer \
  tests.test_approach_report.ApproachReportBuildTests.test_evaluation_separates_ranking_metrics_from_llm_judging -v
```

Expected: at least one exact accuracy statement is absent.

- [ ] **Step 3: Correct visible ranking and evaluation copy**

In the ranking chapter, state:

```html
<p><code>ranking.mode: lgbm</code> is the submitted final path. The compiler first assembles a candidate pool from specialist branches; the goal-free LightGBM LambdaMART bundle then determines the delivered order, followed by the same-turn artist guard.</p>
```

Keep the compiler's internal weighted-RRF formula inside the compile chapter's disclosure titled `How candidate pool assembly combines branch evidence`. Do not call that formula the final ranker.

In evaluation, display two adjacent semantic groups:

```html
<article><h3>Ranking relevance</h3><p>Recall and nDCG evaluate whether relevant tracks are retrieved and ordered.</p></article>
<article><h3>Response quality</h3><p>LLM-as-judge evaluates listener-facing prose; it does not rank tracks in the serving pipeline.</p></article>
```

- [ ] **Step 4: Replace the alignment bitmap with a native boundary comparison**

In the gaps chapter, render two semantic paths: aligned signal and first-broken-boundary signal. Use ordered lists with explicit text labels, not an image. The failure path must name state, candidate coverage, final ranking, and response grounding as possible boundaries without claiming every boundary failed in one run.

- [ ] **Step 5: Run report tests and rebuild**

Run:

```bash
PYTHONPATH=. uv run --no-sync python -m unittest tests.test_approach_report -v
uv run --no-sync python scripts/build_approach_report.py
PYTHONPATH=. uv run --no-sync python scripts/validate_approach_report.py docs/approach.html
git diff --check
```

Expected: all tests pass, validation succeeds, and no whitespace errors remain.

- [ ] **Step 6: Commit**

```bash
git add docs/approach/source.html docs/approach.html tests/test_approach_report.py
git commit -m "docs: clarify candidate and final ranking stages"
```

---

### Task 6: Visual QA, Full Verification, and PR Update

**Files:**
- Modify only if QA finds a defect: `docs/approach/source.html`, `docs/approach.html`, `tests/test_approach_report.py`
- Verify: all files changed by Tasks 1–5

**Interfaces:**
- Consumes: completed organizer-first report.
- Produces: visually inspected desktop/mobile renders, a clean full test run, and an updated draft PR #201.

- [ ] **Step 1: Render desktop and mobile screenshots**

Run:

```bash
mkdir -p /var/tmp/approach-organizer-qa
TMPDIR=/var/tmp google-chrome --headless=new --no-sandbox --disable-gpu \
  --hide-scrollbars --allow-file-access-from-files --window-size=1533,5000 \
  --screenshot=/var/tmp/approach-organizer-qa/desktop.png \
  file://$PWD/docs/approach.html
TMPDIR=/var/tmp google-chrome --headless=new --no-sandbox --disable-gpu \
  --hide-scrollbars --allow-file-access-from-files --window-size=390,6000 \
  --screenshot=/var/tmp/approach-organizer-qa/mobile.png \
  file://$PWD/docs/approach.html
```

Expected: both PNG files are created with non-zero size.

- [ ] **Step 2: Inspect both screenshots**

Use `view_image` on both files. Verify:

- the architecture map and expanded example are understandable before the deep-dive boundary;
- no text is clipped or overlaps connectors;
- retrieval fans out and reconverges on desktop;
- mobile stages read vertically without page-level horizontal overflow;
- the sticky directory does not obscure section headings;
- infrastructure appears after response, not before the system story;
- no decorative illustration remains.

If a defect is visible, add a regression assertion when practical, patch only the responsible CSS/HTML, rebuild, and rerender both viewports.

- [ ] **Step 3: Run fresh full verification**

Run:

```bash
uv run --no-sync python scripts/build_approach_report.py
PYTHONPATH=. uv run --no-sync python scripts/validate_approach_report.py docs/approach.html
PYTHONPATH=. /home/npatta01/data/competitions/music-conversational-music-recomender-2026/.venv/bin/python -m pytest -q
git diff --check
```

Expected: report validation succeeds, the full test suite has zero failures, and `git diff --check` emits no output.

- [ ] **Step 4: Commit any QA-only correction**

If Step 2 required a correction:

```bash
git add docs/approach/source.html docs/approach.html tests/test_approach_report.py
git commit -m "docs: polish organizer report layout"
```

If no correction was required, do not create an empty commit.

- [ ] **Step 5: Push and verify the public preview**

```bash
git push -u origin codex/system-approach-report
gh pr view 201 --json url,isDraft,headRefOid
COMMIT=$(git rev-parse HEAD)
curl -L -sS -o /dev/null -w 'preview_status=%{http_code} preview_bytes=%{size_download}\n' \
  "https://raw.githack.com/npatta01/music-crs-2026/${COMMIT}/docs/approach.html"
```

Expected: PR #201 remains open, the head OID matches `HEAD`, and the immutable preview returns HTTP 200 with non-zero bytes.
