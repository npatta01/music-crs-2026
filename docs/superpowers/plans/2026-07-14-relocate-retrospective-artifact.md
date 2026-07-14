# Relocate Retrospective Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the self-contained retrospective from the repository root to `docs/retrospective.html` and update every active path reference without changing report content or behavior.

**Architecture:** Treat the HTML as one generated artifact whose canonical location changes. Update the two test entrypoints and README link, use Git-aware rename detection for the large file, then validate deterministic generation, browser behavior, and source/payload integrity from the new path.

**Tech Stack:** Git, Node.js ES modules and tests, Python pytest/Playwright, Markdown.

## Global Constraints

- Canonical artifact path is exactly `docs/retrospective.html`.
- Root `retrospective.html` must not remain as a redirect or duplicate.
- Historical specs and plans retain their recorded old paths; the superseding location design explains the change.
- Generator and report tests remain in their current directories.
- Report content, 74 canonical blocks, links, sources, payloads, interactions, and visual behavior remain unchanged.

---

### Task 1: Move the Artifact and Active References

**Files:**
- Move: `retrospective.html` → `docs/retrospective.html`
- Modify: `readme.md`
- Modify: `tests/report/retrospective_deck.test.mjs`
- Modify: `tests/report/test_retrospective_deck_browser.py`

**Interfaces:**
- Consumes: the current self-contained generated HTML and existing generator CLI.
- Produces: one canonical `docs/retrospective.html` referenced by README and both test entrypoints.

- [ ] **Step 1: Write the failing path contract**

In `tests/report/retrospective_deck.test.mjs`, change:

```javascript
const REPORT = new URL("../../docs/retrospective.html", import.meta.url);
const ROOT_REPORT = new URL("../../retrospective.html", import.meta.url);
```

Import `access` from `node:fs/promises` and add:

```javascript
test("retrospective artifact lives under docs only", async () => {
  await access(REPORT);
  await assert.rejects(access(ROOT_REPORT), { code: "ENOENT" });
});
```

In `tests/report/test_retrospective_deck_browser.py`, change:

```python
REPORT = ROOT / "docs" / "retrospective.html"
```

- [ ] **Step 2: Run the focused test and verify RED**

```bash
node --test --test-name-pattern="retrospective artifact lives under docs only" tests/report/retrospective_deck.test.mjs
```

Expected: FAIL with `ENOENT` for `docs/retrospective.html`.

- [ ] **Step 3: Move the artifact and update README**

```bash
git mv retrospective.html docs/retrospective.html
```

Change the README link target from `retrospective.html` to `docs/retrospective.html`.

- [ ] **Step 4: Run focused path and browser checks**

```bash
node --test --test-name-pattern="retrospective artifact lives under docs only|chapter map assigns" tests/report/retrospective_deck.test.mjs
TMPDIR=/var/tmp/mcrs-playwright-tmp uv run pytest -q tests/report/test_retrospective_deck_browser.py -k "groups_every_block_once or synthesis_decoder"
```

Expected: all selected tests PASS.

- [ ] **Step 5: Verify deterministic generation at the new path**

```bash
node scripts/report/retrospective_deck.mjs --check docs/retrospective.html
node scripts/report/retrospective_deck.mjs --input docs/retrospective.html --output /var/tmp/retrospective-relocation-check.html
sha256sum docs/retrospective.html /var/tmp/retrospective-relocation-check.html
```

Expected: 74 blocks map into 8 chapters and both hashes match.

- [ ] **Step 6: Run full verification**

```bash
node --test tests/report/retrospective_deck.test.mjs
TMPDIR=/var/tmp/mcrs-playwright-tmp uv run pytest -q
git diff --check
git status --short
```

Expected: all tests PASS; no root `retrospective.html`; only the intended rename and reference changes are present.

- [ ] **Step 7: Commit and update PR #198**

```bash
git add readme.md docs/retrospective.html tests/report/retrospective_deck.test.mjs tests/report/test_retrospective_deck_browser.py
git commit -m "docs: move retrospective under docs"
git push
```

Expected: PR #198 points to the new canonical artifact path.
