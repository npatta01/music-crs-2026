# Interactive Retrospective Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the complete self-contained Music-CRS retrospective into a seven-chapter, two-dimensional interactive deck while preserving every canonical block, source, calculation, and linear-reading fallback.

**Architecture:** Keep the canonical `artifact.json` and `evidence.json` unchanged. Run the existing portable builder first, then a deterministic Node.js enhancer that validates the 73 stable fallback block IDs plus the builder-rendered page header representing the canonical `title` block, injects a scoped CSS/JavaScript deck shell, and leaves the compressed artifact payload untouched. Use Node's built-in test runner for transformation contracts and Python Playwright with installed Chrome for browser behavior.

**Tech Stack:** Node.js ESM and built-in `node:test`; browser-native HTML/CSS/JavaScript; CSS scroll snap; URL History API; Python 3.12, pytest, and Playwright; existing Data Analytics portable-report builder; Git.

## Global Constraints

- Deliver one reader-facing file at repository root: `retrospective.html`.
- Do not create a `music-crs-2026/` wrapper directory or a second reader-facing report.
- Preserve all 74 canonical blocks—including the `title` block rendered by the builder as the page header—eight datasets, ten sources, evidence links, calculations, diagrams, acknowledgements, caveats, and evidence boundaries.
- Do not change canonical factual content in `artifact.json` or `evidence.json` for this interaction-only revision.
- Do not add runtime dependencies, CDN assets, external fonts, analytics, remote calls, or network requirements.
- Keep the final HTML self-contained and compatible with direct `file://` opening.
- Keep the complete linear report available through `?view=linear`, a visible Linear view control, JavaScript failure, and print.
- Horizontal navigation changes chapters; vertical navigation changes depth inside the current chapter.
- Use readable hashes in the form `#chapter/sub-slide`; preserve browser back/forward.
- Dense matrices and audit blocks may be collapsed, but their factual content must remain byte-preserved inside the generated HTML.
- Respect keyboard use, visible focus, reduced motion, forced colors, touch targets, zoom, and narrow screens.
- Treat generated `retrospective.html` as output: correct canonical facts upstream and correct interaction behavior in the enhancer.
- Keep the preview private to the existing LAN/Tailscale server; do not publish, push, merge, or change sharing.

## File Structure

`scripts/report/retrospective_deck.mjs`
: Owns the exhaustive chapter map, disclosure labels, transformation validation, deterministic CSS/JavaScript injection, atomic CLI write, and `--check` mode.

`tests/report/retrospective_deck.test.mjs`
: Tests pure mapping and HTML transformation contracts with Node's built-in test runner.

`tests/report/test_retrospective_deck_browser.py`
: Builds a temporary enhanced report and tests rendered structure, scrolling, navigation, hashes, history, accessibility, linear mode, print, mobile behavior, errors, and network isolation in Chrome.

`retrospective.html`
: Regenerated portable report plus deterministic deck enhancement; the only reader-facing deliverable.

`readme.md`
: Read-only in this plan; its existing root report link must remain byte-unchanged.

`docs/superpowers/specs/2026-07-13-interactive-retrospective-deck-design.md`
: Approved interaction contract; read-only during implementation.

---

### Task 1: Add the Deterministic Structural Enhancer

**Files:**
- Create: `scripts/report/retrospective_deck.mjs`
- Create: `tests/report/retrospective_deck.test.mjs`
- Read: `retrospective.html`
- Read: `docs/superpowers/specs/2026-07-13-interactive-retrospective-deck-design.md`

**Interfaces:**
- Consumes: a portable report HTML string containing `.portable-block-stack`, `.portable-sources`, `.portable-page-header`, the compressed artifact templates, and exactly 73 approved `data-artifact-block-id` values; `.portable-page-header` is the rendered form of canonical block `title`.
- Produces: `CHAPTERS`, `DISCLOSURES`, `validateChapterMap(chapters, html)`, `stripDeckInjection(html)`, `enhanceHtml(html)`, and a CLI accepting `--input PATH --output PATH` or `--check PATH`.

- [ ] **Step 1: Write the failing structural tests**

Create `tests/report/retrospective_deck.test.mjs`:

```js
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  CHAPTERS,
  enhanceHtml,
  stripDeckInjection,
  validateChapterMap,
} from "../../scripts/report/retrospective_deck.mjs";

const REPORT = new URL("../../retrospective.html", import.meta.url);
const payload = (html) =>
  html.match(/<template id="data-analytics-portable-artifact-payload-source"[\s\S]*?<\/template>/)?.[0];
const blockIds = (html) =>
  [...html.matchAll(/data-artifact-block-id="([^"]+)"/g)].map((match) => match[1]);
const hrefs = (html) =>
  [...html.matchAll(/<a\b[^>]*href="([^"]+)"/g)].map((match) => match[1]).sort();
const srcdocs = (html) =>
  [...html.matchAll(/\bsrcdoc="([^"]*)"/g)].map((match) => match[1]);

test("chapter map assigns all 74 report blocks exactly once", async () => {
  const html = await readFile(REPORT, "utf8");
  const result = validateChapterMap(CHAPTERS, stripDeckInjection(html));
  assert.equal(result.reportIds.length, 74);
  assert.deepEqual(result.mappedIds.sort(), result.reportIds.sort());
});

test("enhancement is deterministic and idempotent", async () => {
  const html = await readFile(REPORT, "utf8");
  const once = enhanceHtml(html);
  const twice = enhanceHtml(once);
  assert.equal(twice, once);
  assert.equal((once.match(/retrospective-deck-style:start/g) ?? []).length, 1);
  assert.equal((once.match(/retrospective-deck-script:start/g) ?? []).length, 1);
});

test("enhancement preserves payload, blocks, links, and iframe documents", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const enhanced = enhanceHtml(html);
  assert.equal(payload(enhanced), payload(html));
  assert.deepEqual(blockIds(enhanced), blockIds(html));
  assert.deepEqual(hrefs(enhanced), hrefs(html));
  assert.deepEqual(srcdocs(enhanced), srcdocs(html));
});

test("missing report block fails with its exact ID", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const broken = html.replace('data-artifact-block-id="own_system_diagram"', 'data-artifact-block-id="removed"');
  assert.throws(
    () => validateChapterMap(CHAPTERS, broken),
    /missing configured block: own_system_diagram/,
  );
});

test("duplicate mapping fails before injection", async () => {
  const html = stripDeckInjection(await readFile(REPORT, "utf8"));
  const duplicate = structuredClone(CHAPTERS);
  duplicate[0].slides[0].blocks.push("executive_summary");
  assert.throws(
    () => validateChapterMap(duplicate, html),
    /duplicate configured block: executive_summary/,
  );
});
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```bash
node --test tests/report/retrospective_deck.test.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `scripts/report/retrospective_deck.mjs`.

- [ ] **Step 3: Implement the exhaustive map, validation, injection, and CLI**

Create `scripts/report/retrospective_deck.mjs` with these exact public constants and functions:

```js
#!/usr/bin/env node
import { readFile, rename, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const slide = (slug, title, blocks) => ({ slug, title, blocks });

export const CHAPTERS = [
  {
    slug: "outcome",
    title: "Outcome & score",
    question: "What happened, and which metric terms made the gap?",
    slides: [
      slide("summary", "Executive answer", ["title", "executive_summary", "headline_metrics", "section_directory"]),
      slide("official-result", "Official result", ["how_scoring_works", "final_result_heading", "leaderboard_chart", "leaderboard_table"]),
      slide("gap", "Gap decomposition", ["gap_contribution_chart", "gap_interpretation"]),
    ],
  },
  {
    slug: "query",
    title: "Conversation → query",
    question: "How did each system turn dialogue into retriever inputs?",
    slides: [
      slide("lifecycle", "Shared lifecycle", ["lifecycle_heading", "lifecycle_map", "lifecycle_takeaway"]),
      slide("comparison", "Query comparison", ["query_heading", "query_explainer", "query_matrix"]),
      slide("data-knowledge", "Data and model knowledge", ["data_knowledge_heading", "data_knowledge_glossary", "data_knowledge_matrix", "data_knowledge_interpretation"]),
      slide("prompt-audit", "Prompt and file audit", ["query_evidence_details"]),
    ],
  },
  {
    slug: "retrieval",
    title: "Retrieval & ranking",
    question: "What candidates and features could the rankers actually see?",
    slides: [
      slide("retrievers", "Retriever inputs and constraints", ["retrieval_heading", "retrieval_glossary", "retrieval_matrix"]),
      slide("features", "Feature families and validation lineage", ["features_heading", "feature_glossary", "feature_matrix"]),
      slide("feature-audit", "Complete feature inventories", ["feature_details"]),
    ],
  },
  {
    slug: "response",
    title: "Response generation",
    question: "How did a selected track become grounded, checked prose?",
    slides: [
      slide("overview", "Response subsystem overview", ["response_heading", "response_explainer"]),
      slide("matrix", "Five-team response matrix", ["response_matrix"]),
      slide("pipelines", "Generation, selection, and repair pipelines", ["response_walkthroughs"]),
      slide("tradeoffs", "Trade-offs and source boundary", ["response_tradeoffs"]),
    ],
  },
  {
    slug: "ours",
    title: "Our submission",
    question: "What did we build, what worked, and where did confidence fail?",
    slides: [
      slide("system", "System diagram", ["own_system_heading", "own_system_diagram"]),
      slide("walkthrough", "Complete walkthrough", ["own_system_walkthrough"]),
      slide("strengths", "What worked", ["what_worked"]),
      slide("evaluation-mistake", "Evaluation mistake", ["evaluation_mistake"]),
      slide("contributors", "Best-supported contributors", ["ranking_contributors", "response_contributors"]),
    ],
  },
  {
    slug: "leaders",
    title: "Leading teams",
    question: "What did the leading public systems document differently?",
    slides: [
      slide("index", "Case-study index", ["competitor_case_studies_heading"]),
      slide("volart", "volart", ["volart_heading", "volart_outcome", "volart_diagram", "volart_walkthrough", "volart_comparison", "volart_limits"]),
      slide("niwatori", "niwatori", ["niwatori_heading", "niwatori_outcome", "niwatori_diagram", "niwatori_walkthrough", "niwatori_comparison", "niwatori_limits"]),
      slide("swyoo", "swyoo", ["swyoo_heading", "swyoo_outcome", "swyoo_diagram", "swyoo_walkthrough", "swyoo_comparison", "swyoo_limits"]),
      slide("team2", "team2_s2", ["team2_s2_heading", "team2_s2_outcome", "team2_s2_diagram", "team2_s2_walkthrough", "team2_s2_comparison", "team2_s2_limits"]),
    ],
  },
  {
    slug: "synthesis",
    title: "Synthesis & evidence",
    question: "What should the team preserve, reconsider, avoid, and credit?",
    slides: [
      slide("cross-team", "Cross-team synthesis", ["cross_team_heading", "cross_team_matrix"]),
      slide("choices", "Retrospective choices", ["preserve_reconsider_avoid", "retrospective_choices_table"]),
      slide("lessons", "Transferable lessons", ["future_competition_lessons"]),
      slide("acknowledgements", "Acknowledgements", ["acknowledgements_heading", "acknowledgements"]),
      slide("caveats-evidence", "Caveats and complete evidence", ["caveats", "evidence_notes"]),
    ],
  },
];

export const DISCLOSURES = {
  section_directory: "Open the original chapter outline",
  how_scoring_works: "Open the composite-score formula",
  leaderboard_table: "Open the exact leaderboard table",
  query_matrix: "Open the complete five-team query matrix",
  query_evidence_details: "Open prompt excerpts and the reviewed file inventory",
  data_knowledge_matrix: "Open the complete data and model-knowledge matrix",
  retrieval_matrix: "Open the complete retrieval matrix",
  feature_matrix: "Open the complete feature-family matrix",
  feature_details: "Open the per-team feature inventories",
  response_matrix: "Open the complete response-generation matrix",
  own_system_walkthrough: "Open the complete submitted-system walkthrough",
  evidence_notes: "Open the complete evidence notes",
};

const STYLE_START = "<!-- retrospective-deck-style:start -->";
const STYLE_END = "<!-- retrospective-deck-style:end -->";
const SCRIPT_START = "<!-- retrospective-deck-script:start -->";
const SCRIPT_END = "<!-- retrospective-deck-script:end -->";

const removeRange = (html, start, end) => {
  const pattern = new RegExp(`${start.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[\\s\\S]*?${end.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\n?`, "g");
  return html.replace(pattern, "");
};

export function stripDeckInjection(html) {
  return removeRange(removeRange(html, STYLE_START, STYLE_END), SCRIPT_START, SCRIPT_END);
}

export function validateChapterMap(chapters, html) {
  const mappedIds = chapters.flatMap((chapter) => chapter.slides.flatMap((entry) => entry.blocks));
  const seen = new Set();
  for (const id of mappedIds) {
    if (seen.has(id)) throw new Error(`duplicate configured block: ${id}`);
    seen.add(id);
  }
  const renderedIds = [...html.matchAll(/data-artifact-block-id="([^"]+)"/g)].map((match) => match[1]);
  const renderedSet = new Set(renderedIds);
  if (renderedIds.length !== renderedSet.size) throw new Error("duplicate report block ID");
  if (renderedSet.has("title")) throw new Error("title must be represented by the portable page header");
  if (!html.includes('class="portable-page-header"')) throw new Error("missing portable page header for title block");
  const reportIds = ["title", ...renderedIds];
  const reportSet = new Set(reportIds);
  for (const id of mappedIds) if (!reportSet.has(id)) throw new Error(`missing configured block: ${id}`);
  for (const id of reportIds) if (!seen.has(id)) throw new Error(`unassigned report block: ${id}`);
  if (!html.includes('class="portable-block-stack"')) throw new Error("missing portable block stack");
  if (!html.includes('class="portable-sources"')) throw new Error("missing portable source list");
  if (!html.includes('id="data-analytics-portable-artifact-payload-source"')) throw new Error("missing artifact payload template");
  const slugs = new Set();
  for (const chapter of chapters) for (const entry of chapter.slides) {
    const slug = `${chapter.slug}/${entry.slug}`;
    if (slugs.has(slug)) throw new Error(`duplicate slide slug: ${slug}`);
    slugs.add(slug);
  }
  return { mappedIds, reportIds, slugs: [...slugs] };
}

export const DECK_STYLE = `
#data-analytics-portable-reader{display:none!important}
#data-analytics-portable-fallback{display:block!important;visibility:visible!important;position:relative!important}
`;

function runtimeMain(CONFIG) {
  window.__RETROSPECTIVE_DECK_CONFIG__ = CONFIG;
}

export const DECK_RUNTIME = `(${runtimeMain.toString()})(__CONFIG__);`;

export function enhanceHtml(input) {
  const html = stripDeckInjection(input);
  validateChapterMap(CHAPTERS, html);
  const config = JSON.stringify({ chapters: CHAPTERS, disclosures: DISCLOSURES }).replaceAll("<", "\\u003c");
  const style = `${STYLE_START}\n<style data-retrospective-deck-style>${DECK_STYLE}</style>\n${STYLE_END}`;
  const runtime = DECK_RUNTIME.replace("__CONFIG__", config);
  const script = `${SCRIPT_START}\n<script data-retrospective-deck-script>${runtime}</script>\n${SCRIPT_END}`;
  if (!html.includes("</head>") || !html.includes("</body>")) throw new Error("portable report is missing head/body terminators");
  return html.replace("</head>", `${style}\n</head>`).replace("</body>", `${script}\n</body>`);
}

function parseArgs(argv) {
  const args = { input: "", output: "", check: "" };
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key === "--input" || key === "--output" || key === "--check") args[key.slice(2)] = argv[++index] ?? "";
    else throw new Error(`unknown argument: ${key}`);
  }
  if (args.check) return args;
  if (!args.input || !args.output) throw new Error("usage: retrospective_deck.mjs --input PATH --output PATH | --check PATH");
  return args;
}

async function main(argv) {
  const args = parseArgs(argv);
  const inputPath = args.check || args.input;
  const source = await readFile(inputPath, "utf8");
  const enhanced = enhanceHtml(source);
  if (args.check) {
    process.stdout.write(`PASS: ${validateChapterMap(CHAPTERS, stripDeckInjection(source)).reportIds.length} blocks mapped into ${CHAPTERS.length} chapters\\n`);
    return;
  }
  const temp = `${args.output}.tmp-${process.pid}`;
  await writeFile(temp, enhanced, "utf8");
  await rename(temp, args.output);
  process.stdout.write(`wrote ${args.output}\\n`);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error.message}\\n`);
    process.exitCode = 1;
  });
}
```

- [ ] **Step 4: Run structural tests and CLI check**

Run:

```bash
node --test tests/report/retrospective_deck.test.mjs
node scripts/report/retrospective_deck.mjs --check retrospective.html
```

Expected:

```text
# pass 5
# fail 0
PASS: 74 blocks mapped into 7 chapters
```

- [ ] **Step 5: Commit the structural enhancer**

Run:

```bash
git add scripts/report/retrospective_deck.mjs tests/report/retrospective_deck.test.mjs
git commit -m "feat: add retrospective deck enhancer"
```

Expected: one commit containing exactly those two files.

---

### Task 2: Build the Two-Dimensional Layout and Progressive Disclosure

**Files:**
- Modify: `scripts/report/retrospective_deck.mjs`
- Create: `tests/report/test_retrospective_deck_browser.py`
- Test: `tests/report/retrospective_deck.test.mjs`

**Interfaces:**
- Consumes: `CHAPTERS`, `DISCLOSURES`, and `enhanceHtml()` from Task 1.
- Produces: runtime DOM with `.retrospective-deck`, seven `.deck-chapter` elements, 29 `.deck-slide` elements, `data-deck-ready="true"`, accessible disclosure wrappers, a `.deck-source-list`, and linear/print mode.

- [ ] **Step 1: Write failing browser structure tests**

Create `tests/report/test_retrospective_deck_browser.py`:

```python
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "retrospective.html"
ENHANCER = ROOT / "scripts/report/retrospective_deck.mjs"


@pytest.fixture(scope="session")
def enhanced_report(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("retrospective-deck") / "retrospective.html"
    subprocess.run(
        ["node", str(ENHANCER), "--input", str(REPORT), "--output", str(output)],
        cwd=ROOT,
        check=True,
        text=True,
    )
    return output


@pytest.fixture()
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path="/usr/bin/google-chrome",
            args=["--no-sandbox"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        yield page, errors
        context.close()
        browser.close()


def open_deck(page: Page, report: Path, suffix: str = "") -> None:
    page.goto(f"{report.as_uri()}{suffix}")
    page.wait_for_selector('html[data-deck-ready="true"]')


def test_groups_every_block_once(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report)
    assert browser_page.locator(".deck-chapter").count() == 7
    assert browser_page.locator(".deck-slide").count() == 29
    assert browser_page.locator(".deck-vertical-rail").count() == 7
    assert browser_page.locator(".deck-rail-button").count() == 29
    assigned = browser_page.locator(".deck-slide [data-artifact-block-id]")
    assert assigned.count() == 74
    ids = assigned.evaluate_all("nodes => nodes.map(node => node.dataset.artifactBlockId)")
    assert len(ids) == len(set(ids)) == 74
    assert errors == []


def test_progressive_disclosure_and_sources(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    exact_table = browser_page.locator('details[data-disclosure-for="leaderboard_table"]')
    assert exact_table.locator("summary").inner_text() == "Open the exact leaderboard table"
    assert not exact_table.get_attribute("open")
    assert browser_page.locator(".deck-source-list .portable-sources").count() == 1
    assert browser_page.locator(".deck-source-list .portable-sources > ol > li").count() == 10
    assert browser_page.locator(".retrospective-deck a[href^='https://']").count() >= 27


def test_linear_and_print_modes(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "?view=linear")
    assert browser_page.locator("html").get_attribute("data-deck-view") == "linear"
    assert browser_page.locator(".deck-chapter").first.is_visible()
    assert browser_page.locator("details.deck-disclosure:not([open])").count() == 0
    browser_page.goto(enhanced_report.as_uri())
    browser_page.wait_for_selector('html[data-deck-ready="true"]')
    assert browser_page.locator("details.deck-disclosure:not([open])").count() > 0
    browser_page.emulate_media(media="print")
    browser_page.evaluate("dispatchEvent(new Event('beforeprint'))")
    assert browser_page.locator("details.deck-disclosure:not([open])").count() == 0
    assert browser_page.locator(".deck-chrome").first.evaluate("node => getComputedStyle(node).display") == "none"
    assert browser_page.locator(".deck-slide").nth(28).is_visible()
    browser_page.evaluate("dispatchEvent(new Event('afterprint'))")
    assert browser_page.locator("details.deck-disclosure:not([open])").count() > 0


def test_mobile_has_bounded_content_and_touch_targets(enhanced_report: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        open_deck(page, enhanced_report)
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        sizes = page.locator(".deck-chrome button").evaluate_all(
            "nodes => nodes.map(node => ({width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height}))"
        )
        assert all(size["width"] >= 44 and size["height"] >= 44 for size in sizes)
        browser.close()


def test_enhancer_does_not_change_embedded_payload(enhanced_report: Path) -> None:
    source = REPORT.read_text()
    enhanced = enhanced_report.read_text()
    marker = 'id="data-analytics-portable-artifact-payload-source"'
    source_payload = source[source.index(marker):source.index("</template>", source.index(marker))]
    enhanced_payload = enhanced[enhanced.index(marker):enhanced.index("</template>", enhanced.index(marker))]
    assert hashlib.sha256(source_payload.encode()).digest() == hashlib.sha256(enhanced_payload.encode()).digest()
```

- [ ] **Step 2: Run the structure tests and verify they fail**

Run:

```bash
uv run pytest -q tests/report/test_retrospective_deck_browser.py
```

Expected: FAIL because `data-deck-ready`, `.deck-chapter`, and `.deck-slide` do not yet exist.

- [ ] **Step 3: Replace the minimal style with the scoped deck layout**

In `scripts/report/retrospective_deck.mjs`, replace `DECK_STYLE` with a complete scoped stylesheet implementing these exact contracts:

```js
export const DECK_STYLE = `
#data-analytics-portable-reader{display:none!important}
#data-analytics-portable-fallback{display:block!important;visibility:visible!important;position:relative!important;width:100%!important;max-width:none!important;padding:0!important}
html.retrospective-deck-ready,html.retrospective-deck-ready body{height:100%;overflow:hidden}
.retrospective-deck{height:100dvh;display:grid;grid-template-rows:auto minmax(0,1fr) auto;background:var(--portable-canvas);color:var(--portable-ink)}
.deck-chrome{position:relative;z-index:20;background:color-mix(in srgb,var(--portable-canvas) 92%,transparent);backdrop-filter:blur(12px)}
.deck-topbar,.deck-footer{display:flex;align-items:center;gap:12px;min-height:56px;padding:8px clamp(12px,2.5vw,32px);border-color:var(--portable-border)}
.deck-topbar{border-bottom:1px solid var(--portable-border)}
.deck-footer{justify-content:space-between;border-top:1px solid var(--portable-border)}
.deck-title{margin-right:auto;font-weight:750}.deck-breadcrumb{color:var(--portable-muted)}
.deck-button{min-width:44px;min-height:44px;border:1px solid var(--portable-border);border-radius:10px;background:var(--portable-surface);color:var(--portable-ink);cursor:pointer}
.deck-button:focus-visible,.deck-jump-item:focus-visible,.deck-slide:focus-visible,summary:focus-visible{outline:3px solid var(--portable-accent);outline-offset:3px}
.deck-track{display:flex;min-width:0;overflow-x:auto;overflow-y:hidden;scroll-snap-type:x mandatory;scroll-behavior:smooth;overscroll-behavior-x:contain;scrollbar-width:none}
.deck-chapter{flex:0 0 100%;min-width:0;height:100%;scroll-snap-align:start}
.deck-chapter{position:relative}
.deck-vertical{height:100%;overflow-y:auto;overflow-x:hidden;scroll-snap-type:y proximity;overscroll-behavior-y:contain}
.deck-vertical-rail{position:absolute;z-index:10;right:12px;top:50%;transform:translateY(-50%);display:grid;gap:7px;padding:9px;border:1px solid var(--portable-border);border-radius:999px;background:color-mix(in srgb,var(--portable-surface) 88%,transparent)}
.deck-rail-button{display:grid;place-items:center;width:28px;height:28px;padding:0;border:0;border-radius:999px;background:transparent;cursor:pointer}
.deck-rail-button::before{width:10px;height:10px;border:1px solid var(--portable-muted);border-radius:999px;background:transparent;content:""}
.deck-rail-button[aria-current="true"]::before{border-color:var(--portable-accent);background:var(--portable-accent)}
.deck-slide{min-height:100%;padding:clamp(18px,3vw,42px) clamp(16px,5vw,72px);scroll-snap-align:start;scroll-margin-top:12px}
.deck-slide-inner{width:min(1180px,100%);margin:0 auto;display:grid;gap:18px}
.deck-slide-heading{margin:0;font-size:clamp(22px,3vw,38px);line-height:1.12}.deck-question{margin:0;color:var(--portable-muted)}
.deck-slide .portable-page-header{position:static;width:auto;height:auto;min-height:0;margin:0;padding:0;border:0;background:transparent}
.deck-slide .portable-block-stack{display:contents}.deck-slide .portable-markdown{max-width:900px}
.deck-slide .portable-content-card,.deck-slide .portable-metric-card{box-shadow:none}
.deck-disclosure{border:1px solid var(--portable-border);border-radius:12px;background:var(--portable-surface);overflow:clip}
.deck-disclosure>summary{min-height:48px;padding:14px 18px;cursor:pointer;color:var(--portable-accent);font-weight:700}
.deck-disclosure>[data-artifact-block-id]{border:0;border-radius:0}
.deck-source-list{margin-top:18px}.deck-source-list>.deck-disclosure{width:100%}
.deck-jump{position:fixed;inset:0;z-index:50;display:none;place-items:center;padding:20px;background:rgba(15,23,42,.72)}
.deck-jump[data-open="true"]{display:grid}.deck-jump-panel{width:min(720px,100%);max-height:min(720px,88dvh);overflow:auto;padding:18px;border:1px solid var(--portable-border);border-radius:16px;background:var(--portable-surface)}
.deck-jump-input{width:100%;min-height:46px;padding:10px 12px;border:1px solid var(--portable-border);border-radius:9px;background:var(--portable-canvas);color:var(--portable-ink)}
.deck-jump-list{display:grid;gap:8px;margin-top:12px}.deck-jump-item{width:100%;min-height:48px;padding:10px 12px;border:0;border-radius:9px;background:var(--portable-surface-subtle);color:var(--portable-ink);text-align:left;cursor:pointer}
.deck-live,.deck-skip{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.deck-skip:focus{position:fixed;top:8px;left:8px;z-index:80;width:auto;height:auto;clip:auto;padding:10px;background:var(--portable-surface)}
html[data-deck-view="linear"],html[data-deck-view="linear"] body{height:auto;overflow:auto}
html[data-deck-view="linear"] .retrospective-deck{height:auto;display:block}html[data-deck-view="linear"] .deck-track{display:block;overflow:visible}html[data-deck-view="linear"] .deck-chapter,html[data-deck-view="linear"] .deck-slide{height:auto;min-height:0}html[data-deck-view="linear"] .deck-vertical{height:auto;overflow:visible}html[data-deck-view="linear"] .deck-disclosure>summary{display:none}html[data-deck-view="linear"] .deck-disclosure>[data-artifact-block-id]{display:block!important}
@media(max-width:700px){.deck-breadcrumb{display:none}.deck-topbar,.deck-footer{min-height:60px;padding:8px 10px}.deck-slide{padding:18px 12px}.deck-vertical-rail{display:none}.portable-table-scroll{max-width:calc(100vw - 24px)}.deck-button{min-width:48px;min-height:48px}}
@media(prefers-reduced-motion:reduce){.deck-track,.deck-vertical{scroll-behavior:auto!important}}
@media(forced-colors:active){.deck-button,.deck-disclosure,.deck-jump-panel{border:1px solid CanvasText}}
@media print{html,body{height:auto!important;overflow:visible!important}.deck-chrome,.deck-jump,.deck-skip,.deck-live{display:none!important}.retrospective-deck,.deck-track,.deck-chapter,.deck-vertical,.deck-slide{display:block!important;height:auto!important;min-height:0!important;overflow:visible!important;scroll-snap-type:none!important}.deck-disclosure>summary{display:none!important}.deck-disclosure>[data-artifact-block-id],.deck-disclosure:not([open])>*:not(summary){display:block!important}}
`;
```

- [ ] **Step 4: Implement DOM grouping, disclosures, sources, and linear mode**

Replace `DECK_RUNTIME` with an IIFE that uses the injected `__CONFIG__` value and these exact functions:

```js
function runtimeMain(CONFIG) {
  const html = document.documentElement;
  const fallback = document.getElementById("data-analytics-portable-fallback");
  const stack = fallback?.querySelector(".portable-block-stack");
  const sources = fallback?.querySelector(".portable-sources");
  const pageHeader = fallback?.querySelector(":scope > .portable-page-header");
  if (!fallback || !stack || !sources || !pageHeader) return;
  const blocks = new Map([...stack.querySelectorAll(":scope > [data-artifact-block-id]")].map(node => [node.dataset.artifactBlockId, node]));
  pageHeader.dataset.artifactBlockId = "title";
  blocks.set("title", pageHeader);
  const app = document.createElement("main");
  app.className = "retrospective-deck";
  app.setAttribute("aria-label", "Music-CRS retrospective deck");
  const skip = Object.assign(document.createElement("a"), { className: "deck-skip", href: "#outcome/summary", textContent: "Skip to current slide" });
  const live = Object.assign(document.createElement("div"), { className: "deck-live" });
  live.setAttribute("aria-live", "polite");
  live.setAttribute("aria-atomic", "true");
  const topbar = document.createElement("header");
  topbar.className = "deck-topbar deck-chrome";
  topbar.innerHTML = '<strong class="deck-title">Music-CRS retrospective</strong><span class="deck-breadcrumb"></span><span class="deck-progress"></span><button class="deck-button" type="button" data-action="linear">Linear view</button><button class="deck-button" type="button" data-action="jump">Jump</button>';
  const track = document.createElement("div");
  track.className = "deck-track";
  const footer = document.createElement("footer");
  footer.className = "deck-footer deck-chrome";
  footer.innerHTML = '<button class="deck-button" type="button" data-action="previous">← Previous</button><span class="deck-axis-help">←/→ chapters · ↑/↓ depth</span><button class="deck-button" type="button" data-action="next">Next →</button>';
  const disclosure = (node, label) => {
    if (!label) return node;
    const details = document.createElement("details");
    details.className = "deck-disclosure";
    details.dataset.disclosureFor = node.dataset.artifactBlockId;
    const summary = document.createElement("summary");
    summary.textContent = label;
    details.append(summary, node);
    return details;
  };
  for (const chapter of CONFIG.chapters) {
    const chapterNode = document.createElement("section");
    chapterNode.className = "deck-chapter";
    chapterNode.dataset.chapter = chapter.slug;
    chapterNode.setAttribute("aria-label", chapter.title);
    const vertical = document.createElement("div");
    vertical.className = "deck-vertical";
    const rail = document.createElement("nav");
    rail.className = "deck-vertical-rail";
    rail.setAttribute("aria-label", `${chapter.title} slides`);
    for (const entry of chapter.slides) {
      const slideNode = document.createElement("section");
      slideNode.className = "deck-slide";
      slideNode.id = `${chapter.slug}/${entry.slug}`;
      slideNode.dataset.slug = slideNode.id;
      slideNode.tabIndex = -1;
      slideNode.setAttribute("aria-labelledby", `${chapter.slug}-${entry.slug}-title`);
      const inner = document.createElement("div");
      inner.className = "deck-slide-inner";
      const heading = document.createElement("h2");
      heading.className = "deck-slide-heading";
      heading.id = `${chapter.slug}-${entry.slug}-title`;
      heading.textContent = entry.title;
      const question = document.createElement("p");
      question.className = "deck-question";
      question.textContent = chapter.question;
      inner.append(heading, question);
      for (const blockId of entry.blocks) inner.append(disclosure(blocks.get(blockId), CONFIG.disclosures[blockId]));
      slideNode.append(inner);
      vertical.append(slideNode);
      const railButton = document.createElement("button");
      railButton.className = "deck-rail-button";
      railButton.type = "button";
      railButton.dataset.go = slideNode.id;
      railButton.setAttribute("aria-label", `Go to ${entry.title}`);
      rail.append(railButton);
    }
    chapterNode.append(vertical, rail);
    track.append(chapterNode);
  }
  const finalSlide = track.querySelector('[id="synthesis/caveats-evidence"] .deck-slide-inner');
  const sourceDetails = document.createElement("details");
  sourceDetails.className = "deck-disclosure deck-source-list";
  sourceDetails.innerHTML = "<summary>Open the complete source list</summary>";
  sourceDetails.append(sources);
  finalSlide.append(sourceDetails);
  app.append(skip, topbar, track, footer, live);
  stack.replaceWith(app);
  html.dataset.deckView = new URL(location.href).searchParams.get("view") === "linear" ? "linear" : "deck";
  html.classList.add("retrospective-deck-ready");
  html.dataset.deckReady = "true";
  window.__retrospectiveDeck = { CONFIG, app, track, live };
}

export const DECK_RUNTIME = `(${runtimeMain.toString()})(__CONFIG__);`;
```

- [ ] **Step 5: Run unit and browser structure tests**

Run:

```bash
node --test tests/report/retrospective_deck.test.mjs
uv run pytest -q tests/report/test_retrospective_deck_browser.py
```

Expected: Node `5 passed`; pytest `5 passed`.

- [ ] **Step 6: Commit layout and disclosure behavior**

Run:

```bash
git add scripts/report/retrospective_deck.mjs tests/report/test_retrospective_deck_browser.py
git commit -m "feat: add retrospective deck layout"
```

Expected: one commit containing the enhancer update and browser structure tests.

---

### Task 3: Add Navigation, Hashes, Jump Search, and Accessibility Behavior

**Files:**
- Modify: `scripts/report/retrospective_deck.mjs`
- Modify: `tests/report/test_retrospective_deck_browser.py`

**Interfaces:**
- Consumes: `window.__retrospectiveDeck = { CONFIG, app, track, live }` from Task 2.
- Produces: `goTo(slug, options)`, `currentSlug()`, `setLinear(enabled)`, jump-dialog behavior, keyboard behavior, scroll-state synchronization, `aria-current`, history integration, and direct disclosure opening.

- [ ] **Step 1: Add failing navigation and accessibility tests**

Append to `tests/report/test_retrospective_deck_browser.py`:

```python
def test_buttons_keys_hash_and_history(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    open_deck(browser_page, enhanced_report)
    next_button = browser_page.locator('[data-action="next"]')
    assert next_button.inner_text() == "Official result →"
    next_button.click()
    browser_page.wait_for_url("**#outcome/official-result")
    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_url("**#query/lifecycle")
    browser_page.keyboard.press("ArrowRight")
    browser_page.wait_for_url("**#retrieval/retrievers")
    browser_page.keyboard.press("ArrowDown")
    browser_page.wait_for_url("**#retrieval/features")
    browser_page.go_back()
    browser_page.wait_for_url("**#retrieval/retrievers")
    assert errors == []


def test_jump_palette_filters_and_restores_focus(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report)
    opener = browser_page.get_by_role("button", name="Jump")
    opener.focus()
    browser_page.keyboard.press("Control+K")
    palette = browser_page.get_by_role("dialog", name="Jump anywhere")
    assert palette.is_visible()
    palette.get_by_role("searchbox").fill("volart")
    palette.get_by_role("button", name="Leading teams — volart").click()
    browser_page.wait_for_url("**#leaders/volart")
    opener.focus()
    browser_page.keyboard.press("Control+K")
    browser_page.keyboard.press("Escape")
    assert opener.evaluate("node => document.activeElement === node")


def test_direct_and_invalid_hashes(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#response/matrix")
    assert browser_page.locator('#response\\/matrix').get_attribute("aria-current") == "true"
    browser_page.goto(f"{enhanced_report.as_uri()}#not/a-slide")
    browser_page.wait_for_url("**#outcome/summary")


def test_direct_hash_opens_disclosure(page, enhanced_report: Path) -> None:
    browser_page, _ = page
    open_deck(browser_page, enhanced_report, "#retrieval/features?open=feature_matrix")
    details = browser_page.locator('details[data-disclosure-for="feature_matrix"]')
    assert details.get_attribute("open") is not None


def test_reduced_motion_and_passive_scroll_do_not_steal_focus(enhanced_report: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
        open_deck(page, enhanced_report)
        assert page.locator(".deck-track").evaluate("node => getComputedStyle(node).scrollBehavior") == "auto"
        page.get_by_role("button", name="Jump").focus()
        page.locator(".deck-track").evaluate("node => node.scrollLeft = node.clientWidth")
        page.wait_for_timeout(120)
        assert page.get_by_role("button", name="Jump").evaluate("node => document.activeElement === node")
        browser.close()


def test_no_external_requests_or_browser_errors(page, enhanced_report: Path) -> None:
    browser_page, errors = page
    requests: list[str] = []
    browser_page.on("request", lambda request: requests.append(request.url))
    open_deck(browser_page, enhanced_report)
    external = [url for url in requests if not url.startswith(("file:", "data:", "blob:"))]
    assert external == []
    assert errors == []
```

- [ ] **Step 2: Run the new tests and verify navigation fails**

Run:

```bash
uv run pytest -q tests/report/test_retrospective_deck_browser.py
```

Expected: the six new tests fail because button actions, dialog, hashes, and keyboard navigation are not implemented.

- [ ] **Step 3: Add current-location, history, disclosure, and linear-mode functions**

Append this code inside `DECK_RUNTIME`, immediately before assigning `window.__retrospectiveDeck`:

```js
  const slides = CONFIG.chapters.flatMap((chapter, chapterIndex) => chapter.slides.map((entry, slideIndex) => ({ chapter, entry, chapterIndex, slideIndex, slug: `${chapter.slug}/${entry.slug}` })));
  const bySlug = new Map(slides.map(item => [item.slug, item]));
  const breadcrumb = topbar.querySelector(".deck-breadcrumb");
  const progress = topbar.querySelector(".deck-progress");
  let active = slides[0];
  let scrollTimer = 0;
  const openRequestedDisclosure = () => {
    const params = new URLSearchParams(location.hash.split("?")[1] || "");
    const id = params.get("open");
    if (id) document.querySelector(`details[data-disclosure-for="${CSS.escape(id)}"]`)?.setAttribute("open", "");
  };
  const updateCurrent = (item, announce = false) => {
    active = item;
    document.querySelectorAll('.deck-slide[aria-current="true"]').forEach(node => node.removeAttribute("aria-current"));
    document.querySelectorAll('.deck-rail-button[aria-current="true"]').forEach(node => node.removeAttribute("aria-current"));
    const target = document.getElementById(item.slug);
    target.setAttribute("aria-current", "true");
    document.querySelector(`.deck-rail-button[data-go="${CSS.escape(item.slug)}"]`)?.setAttribute("aria-current", "true");
    breadcrumb.textContent = `${item.chapter.title} / ${item.entry.title}`;
    progress.textContent = `Chapter ${item.chapterIndex + 1}/${CONFIG.chapters.length} · slide ${item.slideIndex + 1}/${CONFIG.chapters[item.chapterIndex].slides.length}`;
    skip.href = `#${item.slug}`;
    const chapterSlides = slides.filter(candidate => candidate.chapterIndex === item.chapterIndex);
    const previousItem = item.slideIndex > 0 ? chapterSlides[item.slideIndex - 1] : slides.find(candidate => candidate.chapterIndex === item.chapterIndex - 1 && candidate.slideIndex === 0);
    const nextItem = item.slideIndex < chapterSlides.length - 1 ? chapterSlides[item.slideIndex + 1] : slides.find(candidate => candidate.chapterIndex === item.chapterIndex + 1 && candidate.slideIndex === 0);
    const previousButton = footer.querySelector('[data-action="previous"]');
    const nextButton = footer.querySelector('[data-action="next"]');
    previousButton.disabled = !previousItem;
    previousButton.textContent = previousItem ? `← ${previousItem.entry.title}` : "← Start";
    nextButton.disabled = !nextItem;
    nextButton.textContent = nextItem ? `${nextItem.entry.title} →` : "End";
    if (announce) live.textContent = `${item.chapter.title}, ${item.entry.title}`;
  };
  const goTo = (slug, { push = true, focus = true, announce = true } = {}) => {
    const cleanSlug = slug.split("?")[0];
    const item = bySlug.get(cleanSlug) || slides[0];
    const target = document.getElementById(item.slug);
    target.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start", inline: "start" });
    updateCurrent(item, announce);
    const nextHash = `#${item.slug}${slug.includes("?") ? `?${slug.split("?")[1]}` : ""}`;
    if (push) history.pushState({ slug: item.slug }, "", nextHash);
    else history.replaceState({ slug: item.slug }, "", nextHash);
    openRequestedDisclosure();
    if (focus) target.focus({ preventScroll: true });
    return item;
  };
  const setLinear = (enabled) => {
    const disclosures = document.querySelectorAll("details.deck-disclosure");
    disclosures.forEach(details => {
      if (enabled && !("deckLinearOpen" in details.dataset)) {
        details.dataset.deckLinearOpen = details.open ? "true" : "false";
        details.open = true;
      } else if (!enabled && "deckLinearOpen" in details.dataset) {
        details.open = details.dataset.deckLinearOpen === "true";
        delete details.dataset.deckLinearOpen;
      }
    });
    html.dataset.deckView = enabled ? "linear" : "deck";
    const url = new URL(location.href);
    if (enabled) url.searchParams.set("view", "linear"); else url.searchParams.delete("view");
    history.replaceState(history.state, "", url.href);
    topbar.querySelector('[data-action="linear"]').textContent = enabled ? "Deck view" : "Linear view";
  };
  const nearest = (nodes, axis) => [...nodes].reduce((best, node) => Math.abs(node.getBoundingClientRect()[axis]) < Math.abs(best.getBoundingClientRect()[axis]) ? node : best);
  const syncFromScroll = () => {
    if (html.dataset.deckView === "linear") return;
    const chapterNode = nearest(track.querySelectorAll(".deck-chapter"), "left");
    const slideNode = nearest(chapterNode.querySelectorAll(".deck-slide"), "top");
    const item = bySlug.get(slideNode.dataset.slug);
    if (item && item.slug !== active.slug) {
      updateCurrent(item, false);
      history.replaceState({ slug: item.slug }, "", `#${item.slug}`);
    }
  };
  track.addEventListener("scroll", () => { clearTimeout(scrollTimer); scrollTimer = setTimeout(syncFromScroll, 80); }, { passive: true });
  track.querySelectorAll(".deck-vertical").forEach(node => node.addEventListener("scroll", () => { clearTimeout(scrollTimer); scrollTimer = setTimeout(syncFromScroll, 80); }, { passive: true }));
```

- [ ] **Step 4: Implement buttons, keyboard isolation, jump search, and focus restoration**

Append this code after the functions from Step 3:

```js
  const jump = document.createElement("div");
  jump.className = "deck-jump";
  jump.dataset.open = "false";
  jump.setAttribute("role", "dialog");
  jump.setAttribute("aria-modal", "true");
  jump.setAttribute("aria-label", "Jump anywhere");
  jump.innerHTML = '<div class="deck-jump-panel"><label>Search chapters, teams, or topics<input class="deck-jump-input" type="search" role="searchbox"></label><div class="deck-jump-list"></div></div>';
  app.append(jump);
  const input = jump.querySelector(".deck-jump-input");
  const list = jump.querySelector(".deck-jump-list");
  let jumpOpener = null;
  const renderJump = (query = "") => {
    list.replaceChildren();
    const normalized = query.trim().toLowerCase();
    for (const item of slides.filter(candidate => `${candidate.chapter.title} ${candidate.entry.title} ${candidate.slug}`.toLowerCase().includes(normalized))) {
      const button = document.createElement("button");
      button.className = "deck-jump-item";
      button.type = "button";
      button.textContent = `${item.chapter.title} — ${item.entry.title}`;
      button.addEventListener("click", () => { closeJump(false); goTo(item.slug); });
      list.append(button);
    }
  };
  const openJump = (opener = document.activeElement) => {
    jumpOpener = opener instanceof HTMLElement ? opener : topbar.querySelector('[data-action="jump"]');
    jump.dataset.open = "true";
    renderJump();
    input.value = "";
    input.focus();
  };
  const closeJump = (restore = true) => {
    jump.dataset.open = "false";
    if (restore) jumpOpener?.focus();
  };
  input.addEventListener("input", () => renderJump(input.value));
  const interactive = (target) => target instanceof Element && target.closest("input,textarea,select,button,a,summary,details,[contenteditable=true],iframe,.portable-table-scroll");
  const horizontal = (delta) => {
    const chapterIndex = active.chapterIndex + delta;
    if (chapterIndex < 0 || chapterIndex >= CONFIG.chapters.length) return active;
    return slides.find(item => item.chapterIndex === chapterIndex && item.slideIndex === 0) || active;
  };
  const verticalItem = (delta) => {
    const chapterSlides = slides.filter(item => item.chapterIndex === active.chapterIndex);
    return chapterSlides[Math.max(0, Math.min(chapterSlides.length - 1, active.slideIndex + delta))];
  };
  app.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const destination = target?.closest("[data-go]")?.dataset.go;
    if (destination) { goTo(destination); return; }
    const action = target?.closest("[data-action]")?.dataset.action;
    if (action === "jump") openJump(event.target);
    if (action === "linear") setLinear(html.dataset.deckView !== "linear");
    if (action === "previous") goTo(active.slideIndex ? verticalItem(-1).slug : horizontal(-1).slug);
    if (action === "next") {
      const chapterSlides = slides.filter(item => item.chapterIndex === active.chapterIndex);
      goTo(active.slideIndex < chapterSlides.length - 1 ? verticalItem(1).slug : horizontal(1).slug);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && jump.dataset.open === "true") { event.preventDefault(); closeJump(); return; }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); jump.dataset.open === "true" ? closeJump() : openJump(); return; }
    if (!event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "j" && !interactive(event.target)) { event.preventDefault(); openJump(); return; }
    if (jump.dataset.open === "true" || interactive(event.target) || html.dataset.deckView === "linear") return;
    const destinations = { ArrowLeft: horizontal(-1), ArrowRight: horizontal(1), ArrowUp: verticalItem(-1), ArrowDown: verticalItem(1) };
    if (destinations[event.key]) { event.preventDefault(); goTo(destinations[event.key].slug); }
  });
  addEventListener("popstate", () => goTo(location.hash.slice(1) || slides[0].slug, { push: false, focus: false, announce: true }));
  addEventListener("beforeprint", () => document.querySelectorAll("details.deck-disclosure").forEach(details => {
    if (!("deckPrintOpen" in details.dataset)) details.dataset.deckPrintOpen = details.open ? "true" : "false";
    details.open = true;
  }));
  addEventListener("afterprint", () => document.querySelectorAll("details.deck-disclosure").forEach(details => {
    if ("deckPrintOpen" in details.dataset) {
      details.open = details.dataset.deckPrintOpen === "true";
      delete details.dataset.deckPrintOpen;
    }
  }));
  const initial = location.hash.slice(1);
  const initialSlug = initial.split("?")[0];
  if (!bySlug.has(initialSlug)) goTo(slides[0].slug, { push: false, focus: false, announce: false });
  else goTo(initial, { push: false, focus: false, announce: false });
  setLinear(new URL(location.href).searchParams.get("view") === "linear");
  window.__retrospectiveDeck = { CONFIG, app, track, live, goTo, setLinear, currentSlug: () => active.slug };
```

Remove the earlier Task 2 assignment of `window.__retrospectiveDeck` so it is assigned only once after behavior initialization.

- [ ] **Step 5: Run all focused tests**

Run:

```bash
node --test tests/report/retrospective_deck.test.mjs
uv run pytest -q tests/report/test_retrospective_deck_browser.py
```

Expected: Node `5 passed`; pytest `11 passed`.

- [ ] **Step 6: Commit navigation and accessibility behavior**

Run:

```bash
git add scripts/report/retrospective_deck.mjs tests/report/test_retrospective_deck_browser.py
git commit -m "feat: add retrospective deck navigation"
```

Expected: one commit containing exactly those two modified files.

---

### Task 4: Regenerate, Reconcile, and Deliver the Interactive Report

**Files:**
- Generate: `retrospective.html`
- Verify: `readme.md`
- Verify: `scripts/report/retrospective_deck.mjs`
- Verify: `tests/report/retrospective_deck.test.mjs`
- Verify: `tests/report/test_retrospective_deck_browser.py`

**Interfaces:**
- Consumes: canonical artifact commit `70bcd0b1fa95373cd270183eb9857c1619a98547`, the portable builder, and the completed enhancer.
- Produces: committed root `retrospective.html`, final SHA-256, private LAN/Tailscale preview, and a clean branch ready for integration choice.

- [ ] **Step 1: Revalidate canonical evidence and calculations before regeneration**

Run:

```bash
node - <<'NODE'
const fs = require('fs');
const root = '/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective';
const artifact = JSON.parse(fs.readFileSync(`${root}/artifact.json`));
const evidence = JSON.parse(fs.readFileSync(`${root}/evidence.json`));
if (artifact.manifest.blocks.length !== 74) throw Error('block count');
if (Object.keys(artifact.snapshot.datasets).length !== 8) throw Error('dataset count');
if (artifact.sources.length !== 10) throw Error('source count');
const mine = evidence.leaderboard.find(row => row.entry === 'npatta01');
for (const row of evidence.leaderboard) {
  const composite = .5*row.ndcg20 + .1*row.catalogDiversity + .1*row.lexicalDiversity + .3*(row.llmJudge-1)/4;
  if (Math.abs(composite-row.composite) > 2e-9) throw Error(`composite ${row.entry}`);
}
for (const gap of evidence.gapContributions) {
  const row = evidence.leaderboard.find(item => item.entry === gap.entry);
  const sum = gap.ndcg20 + gap.llmJudge + gap.lexicalDiversity + gap.catalogDiversity;
  if (Math.abs(sum-gap.totalGap) > 2e-9 || Math.abs((row.composite-mine.composite)-gap.totalGap) > 2e-9) throw Error(`gap ${gap.entry}`);
}
console.log('PASS: canonical 74/8/10 artifact and official score arithmetic');
NODE
```

Expected: `PASS: canonical 74/8/10 artifact and official score arithmetic`.

- [ ] **Step 2: Regenerate the verified linear report**

Run:

```bash
node /home/npatta01/.codex/plugins/cache/openai-curated-remote/data-analytics/0.2.8-13ceeea1f599/skills/build-report/scripts/deliver_portable_artifact.mjs \
  --input /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json \
  --output retrospective.html \
  --screenshot /tmp/music-crs-retrospective-deck-failure.png
```

Expected receipt:

```text
validation: passed
package: passed
verification: passed
viewports: 1440, 390
```

- [ ] **Step 3: Enhance the report and prove deterministic output**

Run:

```bash
node scripts/report/retrospective_deck.mjs --input retrospective.html --output retrospective.html
cp retrospective.html /tmp/retrospective-deck-first.html
node scripts/report/retrospective_deck.mjs --input retrospective.html --output retrospective.html
cmp /tmp/retrospective-deck-first.html retrospective.html
sha256sum retrospective.html
```

Expected: `cmp` exits `0`; record the new SHA-256 in the task report.

- [ ] **Step 4: Run focused, full-project, and repository acceptance checks**

Run:

```bash
set -e
node --test tests/report/retrospective_deck.test.mjs
uv run pytest -q tests/report/test_retrospective_deck_browser.py
uv run pytest -q
node scripts/report/retrospective_deck.mjs --check retrospective.html
git diff --check -- retrospective.html scripts/report/retrospective_deck.mjs tests/report/retrospective_deck.test.mjs tests/report/test_retrospective_deck_browser.py
test -s retrospective.html
test ! -d music-crs-2026
test "$(rg -c 'Competition retrospective.*retrospective\.html' readme.md)" -eq 1
for repo in artvolgin/music-crs-recsys2026 ryowk/recsys2026-niwatori yoobros/music-crs-challenge lopsandrea/music-crs-team2; do rg -q "$repo" retrospective.html; done
```

Expected:

- Node tests: 5 passed, 0 failed;
- focused browser tests: 11 passed;
- full project suite: 771 passed, 1 skipped, with only the two pre-existing Pydantic deprecation warnings;
- deck CLI: 74 blocks mapped into 7 chapters;
- all remaining commands exit `0`.

- [ ] **Step 5: Commit only the regenerated reader-facing report**

Run:

```bash
git add -- retrospective.html
git commit -m "docs: render interactive retrospective deck"
git show --stat --oneline --summary HEAD
```

Expected: the commit contains only `retrospective.html`.

- [ ] **Step 6: Verify final branch scope and workspace cleanliness**

Run:

```bash
IMPLEMENTATION_BASE=$(git log -1 --format=%H -- docs/superpowers/plans/2026-07-13-interactive-retrospective-deck.md)
git diff --check "$IMPLEMENTATION_BASE"..HEAD
git diff "$IMPLEMENTATION_BASE"..HEAD --name-only | sort
git status --short --branch
git -C /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective status --short
```

Expected implementation paths:

```text
retrospective.html
scripts/report/retrospective_deck.mjs
tests/report/retrospective_deck.test.mjs
tests/report/test_retrospective_deck_browser.py
```

The canonical artifact workspace must be clean. The project may still contain the untracked `.superpowers/` visual-companion workspace; it must not be staged or committed.

- [ ] **Step 7: Restart and verify the private preview server**

Inspect the existing listener and stop it only if its command line contains the retrospective-only server:

```bash
ss -ltnp '( sport = :8766 )'
PID=$(ss -ltnp '( sport = :8766 )' | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -1)
if test -n "$PID"; then
  tr '\0' ' ' < "/proc/$PID/cmdline" | rg 'node.*retrospective\.html'
  kill "$PID"
fi
```

Start this command through a persistent PTY/async execution session from the project worktree so it remains alive across turns:

```bash
node -e 'const http=require("http"); const fs=require("fs"); const server=http.createServer((req,res)=>{ const path=new URL(req.url,"http://localhost").pathname; if(req.method!=="GET"&&req.method!=="HEAD"){ res.writeHead(405,{"Allow":"GET, HEAD"}); return res.end(); } if(path!=="/"&&path!=="/retrospective.html"){ res.writeHead(404,{"Content-Type":"text/plain; charset=utf-8"}); return res.end("Not found\n"); } const data=fs.readFileSync("retrospective.html"); res.writeHead(200,{"Content-Type":"text/html; charset=utf-8","Content-Length":data.length,"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"}); if(req.method==="HEAD") return res.end(); res.end(data); }); server.listen(8766,"0.0.0.0",()=>process.stdout.write("Serving retrospective on 0.0.0.0:8766\n"));'
```

Verify the restarted server:

```bash
curl -sS -I --max-time 5 http://192.168.1.171:8766/
curl -sS --max-time 10 http://192.168.1.171:8766/ | sha256sum
curl -sS -o /dev/null -w '%{http_code}\n' --max-time 5 http://192.168.1.171:8766/readme.md
curl -sS -I --max-time 5 http://100.72.234.65:8766/
```

Expected:

- LAN and Tailscale report requests return `200`;
- served SHA-256 matches committed `retrospective.html`;
- `/readme.md` returns `404` because only the report is exposed.

- [ ] **Step 8: Record the final handoff**

Create an ignored task report at `.superpowers/sdd/interactive-deck-final-report.md` containing:

- four implementation commit SHAs and subjects;
- final `retrospective.html` SHA-256 and size;
- portable builder receipt;
- Node, focused browser, and full pytest results;
- advisor review verdict;
- LAN and Tailscale preview URLs;
- explicit statement that nothing was pushed, merged, or published.

Do not stage this ignored handoff file.
