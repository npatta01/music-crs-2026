# Approach-Only Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trim `docs/approach.html` into a nine-slide organizer deck that explains only the submitted system approach while leaving RCA content to the existing separate artifact.

**Architecture:** Keep the reviewed architecture, successful walkthrough, and detailed system chapters in the canonical `docs/approach/source.html`. Remove the examples/gaps/lessons sections and their validation/CSS contracts, reorder evaluation before compute placement, regenerate the self-contained output, and verify responsive presentation.

**Tech Stack:** Semantic HTML5, responsive CSS, Python 3.12 standard library, `unittest`/`pytest`, headless Google Chrome, Git/GitHub CLI.

## Global Constraints

- Required section order: `overview, walkthrough, state, compile, ranking, response, evaluation, infrastructure, reproduce`.
- Remove `section#examples`, `section#gaps`, and `section#lessons` entirely.
- Keep one visibly scoped verified successful walkthrough; do not add a success gallery.
- Keep LightGBM as the submitted final orderer; weighted-RRF is internal candidate-pool assembly only.
- LLM-as-judge evaluates response quality and does not rank serving tracks.
- Keep the architecture opening, typed-state detail, response provenance, compute placement, reproduction sources, and progressive disclosures.
- Remove validator requirements and CSS used only by gap/failure sections.
- Preserve self-contained output, repository-contained links, semantic accessibility, print behavior, and mobile navigation containment.
- Edit `docs/approach/source.html`; regenerate `docs/approach.html` only through `scripts/build_approach_report.py`.
- Do not modify the existing RCA/retrospective artifact.

---

### Task 1: Lock the Approach-Only Structure with Regression Tests

**Files:**
- Modify: `tests/test_approach_report.py`
- Modify: `scripts/validate_approach_report.py`

**Interfaces:**
- Consumes: `validate(report: Path) -> list[str]`, `SECTION_IDS`, and `REPORT_SOURCE`.
- Produces: a nine-section structural contract with no RCA-only section or gap-status requirement.

- [ ] **Step 1: Add failing source and validator tests**

```python
def test_source_is_an_approach_only_deck(self) -> None:
    source = REPORT_SOURCE.read_text(encoding="utf-8")
    required = [
        "overview", "walkthrough", "state", "compile", "ranking",
        "response", "evaluation", "infrastructure", "reproduce",
    ]
    positions = [source.index(f'id="{section_id}"') for section_id in required]
    self.assertEqual(positions, sorted(positions))
    for removed in ("examples", "gaps", "lessons"):
        self.assertNotIn(f'id="{removed}"', source)


def test_directory_contains_only_approach_slides(self) -> None:
    source = REPORT_SOURCE.read_text(encoding="utf-8")
    directory = source[source.index('<nav class="directory') : source.index("</nav>")]
    labels = [
        "Architecture", "Worked example", "State", "Retrieval", "Ranking",
        "Response", "Evaluation", "Compute", "Reproduce",
    ]
    self.assertEqual(directory.count("<li>"), len(labels))
    positions = [directory.index(f">{label}<") for label in labels]
    self.assertEqual(positions, sorted(positions))
```

Update `valid_report()` to emit the nine required sections and remove the four gap-status pills. Add a validation test asserting a nine-section fixture passes without gap statuses.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
PYTHONPATH=. uv run --no-sync python -m unittest \
  tests.test_approach_report.ApproachReportBuildTests.test_source_is_an_approach_only_deck \
  tests.test_approach_report.ApproachReportBuildTests.test_directory_contains_only_approach_slides -v
```

Expected: failure because the source still contains examples, gaps, lessons, and the old ordering.

- [ ] **Step 3: Update the validator contract**

Set:

```python
SECTION_IDS = (
    "overview",
    "walkthrough",
    "state",
    "compile",
    "ranking",
    "response",
    "evaluation",
    "infrastructure",
    "reproduce",
)
```

Remove `GAP_STATUSES`, `ReportParser.gap_statuses`, and the final loop that requires each gap status. Keep evidence-status collection and all link/resource validation.

- [ ] **Step 4: Run validator tests and verify GREEN for the contract**

```bash
PYTHONPATH=. uv run --no-sync python -m unittest tests.test_approach_report.ApproachReportValidationTests -v
```

Expected: all validator fixture tests pass with nine sections and no gap-status markers.

- [ ] **Step 5: Commit**

```bash
git add tests/test_approach_report.py scripts/validate_approach_report.py
git commit -m "test: define approach-only report structure"
```

---

### Task 2: Remove RCA Slides and Tighten Navigation

**Files:**
- Modify: `docs/approach/source.html`
- Modify: `docs/approach.html` through the build script
- Modify: `tests/test_approach_report.py` only if implementation reveals a missing structural assertion

**Interfaces:**
- Consumes: the structural contract from Task 1.
- Produces: a nine-slide source and generated deck with evaluation before compute placement.

- [ ] **Step 1: Remove the three RCA-only semantic sections**

Delete the complete blocks beginning with:

```html
<section class="chapter" id="examples" ...>
<section class="chapter" id="gaps" ...>
<section class="chapter" id="lessons" ...>
```

Do not move their failure cards, gap map, or lessons copy into another slide.

- [ ] **Step 2: Move evaluation before infrastructure**

The source order after `section#response` must be:

```html
<section class="chapter" id="evaluation" ...>...</section>
<section class="chapter" id="infrastructure" ...>...</section>
<section class="future" id="reproduce" ...>...</section>
```

Preserve each section's evidence content and disclosures. Renumber visible chapter numbers to 07 Evaluation, 08 Compute design, and 09 Reproduce.

- [ ] **Step 3: Replace the directory with nine links**

```html
<li><a href="#overview">Architecture</a></li>
<li><a href="#walkthrough">Worked example</a></li>
<li><a href="#state">State</a></li>
<li><a href="#compile">Retrieval</a></li>
<li><a href="#ranking">Ranking</a></li>
<li><a href="#response">Response</a></li>
<li><a href="#evaluation">Evaluation</a></li>
<li><a href="#infrastructure">Compute</a></li>
<li><a href="#reproduce">Reproduce</a></li>
```

Update the deep-dive boundary subtitle to `Worked example, state, retrieval, ranking, response, evaluation, compute, and reproduction.`

- [ ] **Step 4: Remove CSS used only by deleted slides**

Delete selectors whose elements no longer exist, including `.example-stack`, `.example-card`, `.gap-map`, `.gap-card`, `.status-pill`, `.boundary-compare`, `.signal-path`, and deleted-section-only mobile/print rules. Retain shared `.trace`, `.story-card`, `.status-pill` only if an element still uses it; confirm with `rg` before removal.

- [ ] **Step 5: Run source tests, build, and validator**

```bash
PYTHONPATH=. uv run --no-sync python -m unittest tests.test_approach_report -v
uv run --no-sync python scripts/build_approach_report.py
PYTHONPATH=. uv run --no-sync python scripts/validate_approach_report.py docs/approach.html
git diff --check
```

Expected: all focused tests pass, the validator prints `approach report valid`, and the generated report contains nine required sections.

- [ ] **Step 6: Commit**

```bash
git add docs/approach/source.html docs/approach.html tests/test_approach_report.py
git commit -m "docs: trim approach report to system deck"
```

---

### Task 3: Visual QA, Full Verification, and PR Update

**Files:**
- Modify only if QA exposes a defect: `docs/approach/source.html`, `docs/approach.html`, `tests/test_approach_report.py`
- Verify: all files changed by Tasks 1–2

**Interfaces:**
- Consumes: the nine-slide generated deck.
- Produces: reviewed desktop/mobile renders, a fresh full test run, and updated draft PR #201/public preview.

- [ ] **Step 1: Render desktop and mobile screenshots**

```bash
mkdir -p /var/tmp/approach-only-qa
TMPDIR=/var/tmp google-chrome --headless=new --no-sandbox --disable-gpu \
  --hide-scrollbars --allow-file-access-from-files --window-size=1533,5000 \
  --screenshot=/var/tmp/approach-only-qa/desktop.png file://$PWD/docs/approach.html
TMPDIR=/var/tmp google-chrome --headless=new --no-sandbox --disable-gpu \
  --hide-scrollbars --allow-file-access-from-files --window-size=390,6000 \
  --screenshot=/var/tmp/approach-only-qa/mobile.png file://$PWD/docs/approach.html
```

- [ ] **Step 2: Inspect both screenshots**

Use `view_image` and verify architecture readability, example scope, navigation containment, evaluation-before-compute order, no RCA/gap content, no clipping/overlap, and a coherent final reproduction slide. Patch and rerender if any concrete defect appears.

- [ ] **Step 3: Run fresh full verification**

```bash
uv run --no-sync python scripts/build_approach_report.py
PYTHONPATH=. uv run --no-sync python scripts/validate_approach_report.py docs/approach.html
PYTHONPATH=. /home/npatta01/data/competitions/music-conversational-music-recomender-2026/.venv/bin/python -m pytest -q
git diff --check
```

Expected: build and validation pass, full suite has zero failures, and diff check is clean.

- [ ] **Step 4: Commit any QA correction**

If QA required a change:

```bash
git add docs/approach/source.html docs/approach.html tests/test_approach_report.py
git commit -m "docs: polish approach-only deck"
```

Do not create an empty commit when no correction was required.

- [ ] **Step 5: Push and verify PR/public preview**

```bash
git push -u origin codex/system-approach-report
HEAD_SHA=$(git rev-parse HEAD)
gh pr view 201 --json url,isDraft,state,headRefOid
curl -L -sS -o /dev/null \
  -w 'preview_status=%{http_code} preview_bytes=%{size_download}\n' \
  "https://raw.githack.com/npatta01/music-crs-2026/${HEAD_SHA}/docs/approach.html"
```

Expected: PR remains open/draft at matching head and immutable preview returns HTTP 200 with non-zero bytes.
