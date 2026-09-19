# GitHub Pages Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one dependency-free repository-root landing page that routes GitHub Pages visitors to the Music-CRS reports, paper, submissions, audits, code, and data.

**Architecture:** A hand-authored `index.html` contains the complete semantic markup and embedded CSS. A focused static test validates the exact information architecture and local targets; a Playwright test validates responsive layout, focus treatment, color-scheme behavior, print readability, and overflow.

**Tech Stack:** HTML5, embedded CSS, Python 3.12, pytest, Playwright with installed Google Chrome

## Global Constraints

- Deliver one repository-root `index.html`; do not add routes, frameworks, JavaScript, analytics, web fonts, CDN assets, or a Pages deployment workflow.
- Use the architecture deck's dark navy, cyan, violet, green, amber, and coral visual language with system fonts.
- The Paper card links only to `paper/main.pdf`.
- The Code card links only to `https://github.com/npatta01/music-crs-2026`.
- Use relative repository paths for local artifacts and the exact external URLs from the approved specification.
- Support one-, two-, and three-column responsive layouts, operating-system light mode, reduced motion, visible keyboard focus, and readable print output.
- Publishing or changing GitHub Pages repository settings is out of scope.

---

### Task 1: Build the static link hub

**Files:**
- Create: `index.html`
- Create: `tests/report/test_github_pages_landing.py`

**Interfaces:**
- Consumes: the checked-in artifacts named in `docs/superpowers/specs/2026-07-20-github-pages-landing-page-design.md`
- Produces: a dependency-free root `index.html` with `.link-grid`, six `.link-card` elements, and the exact approved anchor targets

- [ ] **Step 1: Write the failing structural tests**

Create `tests/report/test_github_pages_landing.py`:

```python
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "index.html"

EXPECTED_LINKS = {
    "docs/submission-architecture.html",
    "docs/retrospective.html",
    "paper/main.pdf",
    "submission/v10_lgbm_A.zip",
    "submission/v10_lgbm_B_v1.zip",
    "reports/blindset-a-submission-audit/report.html",
    "reports/blindset-b-submission-audit/report.html",
    "https://github.com/npatta01/music-crs-2026",
    "https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge",
    "https://huggingface.co/datasets/Npatta01/music-crs-repro-2026",
    "data/anchor_labels_v1/README.md",
    "https://nlp4musa.github.io/music-crs-challenge/",
    "LICENSE",
}


def page_text() -> str:
    assert PAGE.exists(), "Create the repository-root GitHub Pages entrypoint"
    return PAGE.read_text()


def test_landing_page_has_exact_six_link_groups() -> None:
    html = page_text()
    assert len(re.findall(r'<article class="link-card ', html)) == 6
    for title in ("Reports", "Paper", "Submissions", "Audits", "Code", "Data"):
        assert f">{title}</h2>" in html


def test_landing_page_contains_only_the_approved_destinations() -> None:
    html = page_text()
    hrefs = set(re.findall(r'href="([^"]+)"', html))
    assert hrefs == EXPECTED_LINKS
    assert "paper/draft.md" not in html
    assert "docs/codebase/README.md" not in html
    assert "docs/reproduce_offline_bundle.md" not in html


def test_every_relative_link_exists() -> None:
    for href in EXPECTED_LINKS:
        if urlparse(href).scheme:
            continue
        assert (ROOT / href).exists(), href


def test_page_has_no_remote_resource_dependencies_or_scripts() -> None:
    html = page_text()
    assert "<script" not in html.lower()
    assert not re.search(r'<(?:img|iframe|audio|video|source)[^>]+src="https?://', html, re.I)
    assert not re.search(r'<link[^>]+href="https?://', html, re.I)
    assert "@import" not in html
```

- [ ] **Step 2: Run the structural tests and verify they fail**

Run:

```bash
pytest -q tests/report/test_github_pages_landing.py
```

Expected: FAIL at `PAGE.exists()` because `index.html` does not exist.

- [ ] **Step 3: Create the desktop link hub**

Create `index.html` with this exact semantic structure and copy:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Music-CRS RecSys Challenge 2026 submission artifacts, reports, code, and data.">
  <title>Music-CRS Submission</title>
  <style>
    :root {
      color-scheme: dark light;
      --bg: #07111f;
      --panel: #0e2036;
      --text: #edf5ff;
      --muted: #a9bdd3;
      --border: #29435f;
      --blue: #6ab8ff;
      --cyan: #52d6ca;
      --violet: #b596ff;
      --green: #6ed58a;
      --amber: #f4bd62;
      --coral: #ff7f8a;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body { background: var(--bg); color: var(--text); margin: 0; min-height: 100vh; }
    main { margin: 0 auto; max-width: 1180px; padding: clamp(48px, 8vw, 100px) 28px 56px; }
    .eyebrow { color: var(--blue); font-size: .78rem; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
    h1 { font-size: clamp(2.5rem, 6vw, 5.5rem); letter-spacing: -.055em; line-height: .95; margin: 18px 0 24px; max-width: 900px; }
    .intro { color: var(--muted); font-size: clamp(1rem, 1.8vw, 1.3rem); line-height: 1.6; margin: 0 0 44px; max-width: 760px; }
    .link-grid { display: grid; gap: 22px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .link-card { --accent: var(--blue); border-top: 5px solid var(--accent); min-height: 230px; padding: 26px 22px 22px; position: relative; }
    .link-card::before { color: var(--accent); content: attr(data-icon); font-size: 1.5rem; position: absolute; right: 22px; top: 22px; }
    .link-card h2 { font-size: 1.35rem; margin: 0 0 10px; }
    .link-card p { color: var(--muted); line-height: 1.5; margin: 0 0 22px; }
    .link-card ul { list-style: none; margin: 0; padding: 0; }
    .link-card li + li { border-top: 1px solid var(--border); margin-top: 10px; padding-top: 10px; }
    .link-card a { color: var(--text); font-weight: 750; text-decoration-color: color-mix(in srgb, var(--accent) 70%, transparent); text-decoration-thickness: 2px; text-underline-offset: .25em; }
    .link-card a:hover { color: var(--accent); }
    .link-card a:focus-visible, footer a:focus-visible { border-radius: 3px; outline: 3px solid var(--amber); outline-offset: 5px; }
    .reports { --accent: var(--blue); }
    .paper { --accent: var(--violet); }
    .submissions { --accent: var(--green); }
    .audits { --accent: var(--coral); }
    .code { --accent: var(--cyan); }
    .data { --accent: var(--amber); }
    footer { align-items: center; border-top: 1px solid var(--border); color: var(--muted); display: flex; font-size: .9rem; gap: 22px; justify-content: space-between; margin-top: 46px; padding-top: 22px; }
    footer nav { display: flex; gap: 18px; }
    footer a { color: var(--muted); }
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">RecSys Challenge 2026 · Music-CRS</div>
      <h1>Music-CRS submission</h1>
      <p class="intro">Architecture, paper, submitted artifacts, audits, code, and data from our conversational music recommendation system.</p>
    </header>
    <section class="link-grid" aria-label="Project artifacts">
      <article class="link-card reports" data-icon="↗"><h2>Reports</h2><p>Understand the system and what we learned.</p><ul><li><a href="docs/submission-architecture.html">Architecture Deck</a></li><li><a href="docs/retrospective.html">Competition Retrospective</a></li></ul></article>
      <article class="link-card paper" data-icon="¶"><h2>Paper</h2><p>Read the participant paper.</p><ul><li><a href="paper/main.pdf">Paper PDF</a></li></ul></article>
      <article class="link-card submissions" data-icon="↓"><h2>Submissions</h2><p>Download the submitted prediction bundles.</p><ul><li><a href="submission/v10_lgbm_A.zip">Blind-A submission</a></li><li><a href="submission/v10_lgbm_B_v1.zip">Blind-B submission</a></li></ul></article>
      <article class="link-card audits" data-icon="✓"><h2>Audits</h2><p>Inspect the retained submission evidence.</p><ul><li><a href="reports/blindset-a-submission-audit/report.html">Blind-A audit</a></li><li><a href="reports/blindset-b-submission-audit/report.html">Blind-B audit</a></li></ul></article>
      <article class="link-card code" data-icon="&lt;/&gt;"><h2>Code</h2><p>Explore the implementation.</p><ul><li><a href="https://github.com/npatta01/music-crs-2026">GitHub repository</a></li></ul></article>
      <article class="link-card data" data-icon="◫"><h2>Data</h2><p>Access challenge and released reproduction artifacts.</p><ul><li><a href="https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge">Challenge datasets</a></li><li><a href="https://huggingface.co/datasets/Npatta01/music-crs-repro-2026">Offline reproduction bundle</a></li><li><a href="data/anchor_labels_v1/README.md">Anchor-label data</a></li></ul></article>
    </section>
    <footer><span>Team npatta01</span><nav aria-label="Project information"><a href="https://nlp4musa.github.io/music-crs-challenge/">Challenge</a><a href="LICENSE">License</a></nav></footer>
  </main>
</body>
</html>
```

- [ ] **Step 4: Run the structural tests and verify they pass**

Run:

```bash
pytest -q tests/report/test_github_pages_landing.py
```

Expected: `4 passed`.

- [ ] **Step 5: Commit the static page**

```bash
git add index.html tests/report/test_github_pages_landing.py
git commit -m "feat: add GitHub Pages artifact hub"
```

---

### Task 2: Add responsive and accessibility verification

**Files:**
- Modify: `index.html`
- Modify: `tests/report/test_github_pages_landing.py`

**Interfaces:**
- Consumes: `.link-grid`, `.link-card`, and embedded CSS from Task 1
- Produces: one-, two-, and three-column layouts plus browser assertions for overflow, focus, color schemes, reduced motion, and print

- [ ] **Step 1: Add failing browser tests**

Append to `tests/report/test_github_pages_landing.py`:

```python
import pytest
from playwright.sync_api import sync_playwright

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def launch_browser(playwright):
    if CHROME.exists():
        return playwright.chromium.launch(headless=True, executable_path=str(CHROME))
    return playwright.chromium.launch(headless=True)


@pytest.mark.parametrize(
    ("viewport", "columns"),
    [((1440, 900), 3), ((900, 900), 2), ((390, 844), 1)],
)
def test_responsive_grid_and_no_horizontal_overflow(viewport, columns) -> None:
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
        page.goto(PAGE.as_uri())
        template = page.locator(".link-grid").evaluate("node => getComputedStyle(node).gridTemplateColumns")
        assert len(template.split()) == columns
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2")
        browser.close()


def test_focus_light_reduced_motion_and_print_are_readable() -> None:
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        page.goto(PAGE.as_uri())
        dark_bg = page.locator("body").evaluate("node => getComputedStyle(node).backgroundColor")
        page.keyboard.press("Tab")
        outline = page.locator(":focus").evaluate("node => getComputedStyle(node).outlineStyle")
        assert outline != "none"

        page.emulate_media(color_scheme="light", reduced_motion="reduce")
        light_bg = page.locator("body").evaluate("node => getComputedStyle(node).backgroundColor")
        assert light_bg != dark_bg
        assert page.locator(".link-card").first.evaluate("node => getComputedStyle(node).transitionDuration") in {"0s", "0.000001s", "1e-06s"}

        page.emulate_media(media="print")
        assert page.locator("body").evaluate("node => getComputedStyle(node).backgroundColor") in {"rgb(255, 255, 255)", "rgba(0, 0, 0, 0)"}
        browser.close()
```

- [ ] **Step 2: Run the browser tests and verify responsive/color checks fail**

Run:

```bash
pytest -q tests/report/test_github_pages_landing.py
```

Expected: static tests pass; responsive tests fail because the page has no two-/one-column, light-mode, reduced-motion, or print rules yet.

- [ ] **Step 3: Add the responsive, light, reduced-motion, and print CSS**

Append inside the existing `<style>` element in `index.html`:

```css
@media (max-width: 980px) {
  .link-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 620px) {
  main { padding: 42px 20px 34px; }
  .link-grid { grid-template-columns: 1fr; }
  .link-card { min-height: 0; }
  footer { align-items: flex-start; flex-direction: column; }
}
@media (prefers-color-scheme: light) {
  :root { --bg: #f7f9fc; --panel: #ffffff; --text: #10243a; --muted: #50667c; --border: #cad6e2; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .000001ms !important; }
}
@media print {
  :root { --bg: #ffffff; --text: #111827; --muted: #374151; --border: #cbd5e1; }
  body { background: #ffffff; }
  main { max-width: none; padding: 24px; }
  .link-card { break-inside: avoid; }
}
```

- [ ] **Step 4: Run all landing-page tests**

Run:

```bash
pytest -q tests/report/test_github_pages_landing.py
```

Expected: `8 passed`.

- [ ] **Step 5: Run the existing report tests to guard shared browser tooling**

Run:

```bash
pytest -q tests/report/test_submission_architecture.py tests/report/test_submission_architecture_browser.py tests/report/test_github_pages_landing.py
```

Expected: all tests pass with no page errors or overflow failures.

- [ ] **Step 6: Inspect the page at desktop, tablet, and phone widths**

Serve the repository root locally and inspect `index.html` at `1440×900`, `900×900`, and `390×844`. Confirm that all six cards are legible, the link order is unchanged, focus rings are visible, and no card or footer clips.

- [ ] **Step 7: Commit responsive verification**

```bash
git add index.html tests/report/test_github_pages_landing.py
git commit -m "test: verify landing page responsiveness"
```
