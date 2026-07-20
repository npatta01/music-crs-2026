# Music-CRS System Approach Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a detailed, approachable, self-contained `docs/approach.html` that explains the final submitted Music-CRS system through a vertical end-to-end trace, several strong examples, failure cases, and an evidence-backed gap map.

**Architecture:** Keep the reader-facing artifact self-contained while keeping its source maintainable. A structured evidence snapshot supplies claims and example traces; an HTML source file contains the semantic report; two generated editorial images are project assets; and a small packaging script embeds the images into the final HTML. A validator and headless-Chrome screenshots provide structural and visual verification.

**Tech Stack:** Semantic HTML5, embedded CSS and vanilla JavaScript, JSON evidence snapshot, Python 3 standard library for deterministic packaging/validation, ImageGen bitmap assets, and headless Google Chrome for rendered QA.

## Global Constraints

- Deliver the reader-facing report at `docs/approach.html`.
- Keep the report private/local; do not publish, deploy, expose a service, or change sharing permissions.
- Use one vertical reading flow at every viewport size. Parallel retrieval branches may fan out temporarily but must visibly reconverge.
- The visible page must tell the complete story; full prompts, JSON, configs, candidate tables, and evidence details use native `details` disclosures.
- Prefer real devset conversations and saved traces. Mark reconstructed teaching examples `Illustrative` and never present them as observed runs.
- Label important claims `Verified`, `Inferred`, or `Illustrative` where the evidence boundary matters.
- Include several good examples, at least one full bad example, and an explicit gap map separating observed failures, architectural limitations, measurement gaps, and unknown impacts.
- Explain Modal accurately: label each workload local, hosted API, or Modal according to the submitted configuration and code. Do not imply every model call ran on Modal.
- Distinguish the challenge response LLM judge from development-time LLM judgments and generated labels.
- The final HTML must have no CDN, runtime network call, external stylesheet, external script, or sibling-asset dependency.
- Preserve unrelated worktree changes and the existing untracked `.repro/` and reproduction archives.
- Generated images must contain no embedded text; technical diagrams remain native HTML/CSS.
- Support keyboard navigation, reduced motion, print, mobile widths, semantic tables, and useful alt text.

## File Structure

`docs/approach/evidence.json`
: Curated, source-backed report snapshot containing claims, the primary walkthrough, strong examples, failures, gaps, and sources.

`docs/approach/source.html`
: Canonical semantic HTML/CSS/JS source with exactly two image placeholders: `{{HERO_DATA_URI}}` and `{{ALIGNMENT_DATA_URI}}`.

`docs/approach/assets/hero.png`
: Original editorial hero generated with ImageGen.

`docs/approach/assets/alignment-vs-distortion.png`
: Original editorial good-path/failing-path illustration generated with ImageGen.

`scripts/build_approach_report.py`
: Embeds both PNGs as data URIs and writes `docs/approach.html` deterministically.

`scripts/validate_approach_report.py`
: Validates required sections, anchors, disclosures, evidence markers, embedded images, and runtime independence.

`docs/approach.html`
: Generated self-contained report.

`/home/npatta01/.codex/visualizations/2026/07/14/019f5f2a-2ba4-7550-bc17-59e6656f5224/approach-report/{desktop,mobile}.png`
: Local rendered-QA screenshots; not committed.

---

### Task 1: Curate the Evidence and Example Snapshot

**Files:**
- Create: `docs/approach/evidence.json`
- Read: `configs/state_ranker_v10_lgbm_blindset_B.yaml`
- Read: `exp/inference/blindset_B/state_ranker_v10_lgbm_blindset_B_trace.jsonl`
- Read: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_experiment_pack.json`
- Read: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/ranker_decision/report_data.json`
- Read: `experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/recall_gap_data.json`
- Read: `docs/codebase/bugs.md`
- Read: `docs/research/2026-06-10-response-generation-bakeoff.md`

**Interfaces:**
- Consumes: Saved traces, active configuration, analysis snapshots, prompts, and source files.
- Produces: JSON keys `meta`, `claims`, `primaryTrace`, `goodExamples`, `failureExamples`, `gaps`, and `sources`.

- [ ] **Step 1: Inspect the source schemas**

Run:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
paths = [
    Path("exp/inference/blindset_B/state_ranker_v10_lgbm_blindset_B_trace.jsonl"),
    Path("experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_experiment_pack.json"),
    Path("experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/ranker_decision/report_data.json"),
]
for path in paths:
    value = json.loads(path.read_text().splitlines()[0]) if path.suffix == ".jsonl" else json.loads(path.read_text())
    print(path, sorted(value) if isinstance(value, dict) else type(value).__name__)
PY
```

Expected: all three files parse and print their top-level keys.

- [ ] **Step 2: Select examples with explicit evidence rules**

Choose one primary end-to-end trace; five distinct strong intents (exact entity, refinement, pivot/new artist, lyrical theme, hidden target); one full failure with a known first broken boundary; and up to three additional failures only when they cover different boundaries. Use labelled devset evidence to call outcomes strong or weak. Blind-B traces may illustrate submitted mechanics but not relevance because hidden labels are unavailable.

- [ ] **Step 3: Create the snapshot**

Use `apply_patch` to create this top-level shape:

```json
{
  "meta": {"title": "Inside Our Music-CRS Recommender", "generated": "2026-07-14", "submittedConfig": "configs/state_ranker_v10_lgbm_blindset_B.yaml"},
  "claims": [],
  "primaryTrace": {},
  "goodExamples": [],
  "failureExamples": [],
  "gaps": [],
  "sources": []
}
```

Every claim/example has `status`, `sourcePaths`, and `sourceNote`. Every gap has `expectedCapability`, `submittedBehavior`, `evidence`, `userConsequence`, `recoverability`, and one status from `Observed failure`, `Architectural limitation`, `Measurement gap`, or `Unknown impact`.

- [ ] **Step 4: Validate shape and source paths**

Run:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
d = json.loads(Path("docs/approach/evidence.json").read_text())
assert set(d) == {"meta", "claims", "primaryTrace", "goodExamples", "failureExamples", "gaps", "sources"}
assert len(d["goodExamples"]) >= 5 and len(d["failureExamples"]) >= 1
for item in d["claims"] + d["goodExamples"] + d["failureExamples"]:
    assert item["status"] in {"Verified", "Inferred", "Illustrative"}
    assert item["sourcePaths"]
    for source in item["sourcePaths"]: assert Path(source).exists(), source
for gap in d["gaps"]:
    assert gap["status"] in {"Observed failure", "Architectural limitation", "Measurement gap", "Unknown impact"}
    for key in ("expectedCapability", "submittedBehavior", "evidence", "userConsequence", "recoverability"): assert gap[key].strip()
print("evidence snapshot valid")
PY
```

Expected: `evidence snapshot valid`.

- [ ] **Step 5: Commit**

```bash
git add docs/approach/evidence.json
git commit -m "docs: curate approach report evidence"
```

### Task 2: Generate and Validate Two Editorial Images

**Files:**
- Create: `docs/approach/assets/hero.png`
- Create: `docs/approach/assets/alignment-vs-distortion.png`

**Interfaces:**
- Consumes: Approved visual direction.
- Produces: Two text-free PNG assets ready for data-URI packaging.

- [ ] **Step 1: Generate the hero with built-in ImageGen**

Prompt:

```text
Use case: illustration-story
Asset type: wide editorial hero for a technical competition report
Primary request: a multi-turn music conversation flows through a tactile modular music mixing console and emerges as one carefully selected record or track card
Style/medium: sophisticated editorial illustration, screenprint texture mixed with clean geometric forms, approachable rather than futuristic
Composition/framing: wide 3:2; clear top-to-bottom/diagonal flow; generous breathing room
Color palette: warm cream, charcoal, muted coral, teal, golden yellow
Constraints: no readable text, logos, brand marks, watermark, photorealistic people, or fake UI labels
```

Move the selected output to `docs/approach/assets/hero.png`.

- [ ] **Step 2: Generate alignment versus distortion**

Prompt:

```text
Use case: illustration-story
Asset type: wide editorial section illustration
Primary request: two vertical musical signal journeys in one composition; one keeps conversation signals aligned through transformations into a harmonious selected record, while the other progressively bends, loses cues, and ends in a mismatched selection
Style/medium: matching sophisticated editorial screenprint illustration with clean geometric forms
Composition/framing: wide 3:2 with clear top-to-bottom movement and distinct paths without literal split-screen
Color palette: warm cream, charcoal, muted coral, teal, golden yellow
Constraints: no readable text, good/bad words, checkmarks, crosses, logos, watermark, or fake UI labels
```

Move the selected output to `docs/approach/assets/alignment-vs-distortion.png`.

- [ ] **Step 3: Validate and inspect**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
from PIL import Image
for name in ("hero.png", "alignment-vs-distortion.png"):
    with Image.open(Path("docs/approach/assets") / name) as im:
        assert im.format == "PNG" and im.width >= 1200 and im.height >= 700
        assert im.mode in {"RGB", "RGBA"}
        print(name, im.size, im.mode)
PY
```

Expected: both images are PNG, at least 1200×700, and RGB/RGBA. Then inspect both with `view_image`; regenerate only an image containing text, watermark, misleading UI, or a style mismatch.

- [ ] **Step 4: Commit**

```bash
git add docs/approach/assets
git commit -m "docs: add approach report illustrations"
```

### Task 3: Build the Vertical Report Shell and Infrastructure Story

**Files:**
- Create: `docs/approach/source.html`

**Interfaces:**
- Consumes: Evidence copy and exact placeholders `{{HERO_DATA_URI}}`, `{{ALIGNMENT_DATA_URI}}`.
- Produces: Semantic shell, visual system, hero, navigation, overview, and infrastructure chapters.

- [ ] **Step 1: Create the semantic shell with `apply_patch`**

Use HTML5 with `lang="en"`, skip link, `header`, `nav`, `main`, and `footer`. Define warm cream/ink/coral/teal/gold/status CSS variables and one centered content column capped near 1120px. Add exactly these section IDs:

```text
overview infrastructure walkthrough state compile ranking response evaluation examples gaps lessons reproduce
```

The two `<img>` elements use the exact data-URI placeholders once each.

- [ ] **Step 2: Add the hero and directory**

Use title `Inside Our Music-CRS Recommender`, facts for 47k tracks / top 20 / structured state / top-1 explanation, and a compact anchor directory for all twelve sections. Sticky behavior is desktop-only; mobile remains in document flow.

- [ ] **Step 3: Add the 60-second vertical lifecycle**

Use a semantic `<ol>` with nine stages from conversation to evaluation. Each stage has a plain-language title, one-sentence contract, and evidence badge. CSS connectors show sequence without raster graphics.

- [ ] **Step 4: Add the infrastructure chapter**

Show local orchestration/caches → hosted API or Modal workload → persisted artifact → local replay/evaluation. Label every workload local, hosted API, or Modal from the active config/code. Include an expandable configuration and zero-cost offline reproduction disclosure.

- [ ] **Step 5: Smoke-check and commit**

Run:

```bash
test "$(rg -o 'HERO_DATA_URI' docs/approach/source.html | wc -l)" -eq 1
test "$(rg -o 'ALIGNMENT_DATA_URI' docs/approach/source.html | wc -l)" -eq 1
rg -n 'Inside Our Music-CRS Recommender|id="overview"|id="infrastructure"|<ol' docs/approach/source.html
git add docs/approach/source.html
git commit -m "docs: build approach report shell"
```

Expected: both counts are one and required markers print.

### Task 4: Implement the Full Conversation-to-Response Walkthrough

**Files:**
- Modify: `docs/approach/source.html`
- Read: `docs/approach/evidence.json`
- Read: `mcrs/conversation_state/prompts/current.py`
- Read: `mcrs/system_prompts/response_generation.txt`

**Interfaces:**
- Consumes: `primaryTrace` and supporting claims.
- Produces: Complete `walkthrough`, `state`, `compile`, `ranking`, and `response` sections.

- [ ] **Step 1: Add conversation and annotated state**

Render accessible speaker turns, visible current-request/facts/exclusions/feedback cards, a compact JSON excerpt, and a disclosure with the full snapshot state.

- [ ] **Step 2: Add meaningful prompt excerpts**

Include next-recommendation scope, request classes, fact roles, exclusions, and compatibility-field derivation. Show V1 → projection → resolved V0Plus as three vertical cards and link local sources.

- [ ] **Step 3: Add resolution, compilation, and reconvergence**

Show surface names → catalog IDs, then branch cards for BM25, metadata, attributes, lyrics, sonic, visual, anchor/user centroids, discography, and era/popularity. Every card states its input and output. All paths reconverge into one candidate union.

- [ ] **Step 4: Add ranking movement and top pick**

Explain candidate recall as the ranker's ceiling, feature families, `b1_cos`, and a before/after top-five ordered-list ladder. Include a top-20 disclosure and highlight the selected top track.

- [ ] **Step 5: Add response handoff**

Show response context categories, a meaningful response prompt excerpt, final prose, and the grounding boundary. State that the submitted path was top-1/single-pass without an independently documented fact checker or selector/critic.

- [ ] **Step 6: Validate populated sections and commit**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
s = Path("docs/approach/source.html").read_text()
for section in ("walkthrough", "state", "compile", "ranking", "response"):
    body = s.split(f'id="{section}"', 1)[1].split("</section>", 1)[0]
    assert "evidence-badge" in body and len(body) > 1200, (section, len(body))
print("walkthrough sections populated")
PY
git add docs/approach/source.html
git commit -m "docs: add recommendation walkthrough"
```

Expected: `walkthrough sections populated`.

### Task 5: Add Evaluation, Several Good Examples, Failures, and Gaps

**Files:**
- Modify: `docs/approach/source.html`
- Read: `docs/approach/evidence.json`
- Read: `docs/evaluation.md`

**Interfaces:**
- Consumes: Scoring claims, `goodExamples`, `failureExamples`, and `gaps`.
- Produces: Complete `evaluation`, `examples`, `gaps`, and `lessons` sections.

- [ ] **Step 1: Add challenge scoring and LLM-as-judge**

Show the exact composite formula and explain nDCG@20, catalog diversity, lexical diversity, and normalized response judge. Visibly distinguish the challenge response judge from development-time LLM labels/judgments.

- [ ] **Step 2: Add primary good and bad traces**

Use the same vertical rows: user signal → extracted belief → branches → candidate boundary → top pick/response → outcome/first broken boundary. Explain downstream recoverability.

- [ ] **Step 3: Add several strong examples**

Add at least five `example-card strong` elements covering exact entity, refinement, pivot/new artist, lyrical theme, and hidden target. Each has an evidence status and expandable state/query detail.

- [ ] **Step 4: Add distinct failure examples**

Add at least one `example-card failure`. Add more only for different verified boundaries; never manufacture examples to meet a visual count.

- [ ] **Step 5: Add the vertical gap map and synthesis**

For state, grounding, candidate coverage, ranking/features, response, evaluation/model selection, and infrastructure where supported, show expected capability, submitted behavior, evidence, consequence, recoverability, and status. Finish with Preserve / Fragile or failed / Unknown, not a roadmap.

- [ ] **Step 6: Validate and commit**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
s = Path("docs/approach/source.html").read_text()
assert s.count('class="example-card strong"') >= 5
assert s.count('class="example-card failure"') >= 1
for text in ("Observed failure", "Architectural limitation", "Measurement gap", "Unknown impact"): assert text in s
assert "challenge llm judge" in s.lower() and "development-time" in s.lower()
print("examples and gaps covered")
PY
git add docs/approach/source.html
git commit -m "docs: add approach examples and gap map"
```

Expected: `examples and gaps covered`.

### Task 6: Complete Sources, Glossary, Accessibility, and Disclosure

**Files:**
- Modify: `docs/approach/source.html`

**Interfaces:**
- Consumes: Evidence source list and all report sections.
- Produces: Final canonical source with progressive disclosure, reproduction links, and accessible responsive/print behavior.

- [ ] **Step 1: Add source map and reproduction chapter**

Link the active config, state schema/prompt, compiler/retrievers, bi-encoder, reranker, response prompt, cache docs, staged pipeline, and offline reproduction docs using repository-relative links.

- [ ] **Step 2: Add glossary and evidence boundary**

Define BM25, ANN, centroid, RRF, LambdaMART, bi-encoder, nDCG@20, LLM judge, grounding, candidate recall, plus Verified/Inferred/Illustrative.

- [ ] **Step 3: Complete progressive disclosure and accessibility**

Use native `details`; optional JavaScript may add expand-all/scroll spy but cannot carry core content. Add `:focus-visible`, mobile rules below 720px, `prefers-reduced-motion`, contained audit-table scrolling, alt text, table captions/headers, and print styles.

- [ ] **Step 4: Validate source markers and commit**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
s = Path("docs/approach/source.html").read_text()
for marker in ('<html lang="en">', 'class="skip-link"', '<main', '<nav', '<details', ':focus-visible', 'prefers-reduced-motion', '@media print', 'alt="', '<caption>', '<th scope="col"'):
    assert marker in s, marker
print("accessibility markers present")
PY
git add docs/approach/source.html
git commit -m "docs: finish approach report source"
```

Expected: `accessibility markers present`.

### Task 7: Package and Structurally Validate the Self-Contained HTML

**Files:**
- Create: `scripts/build_approach_report.py`
- Create: `scripts/validate_approach_report.py`
- Create: `docs/approach.html`

**Interfaces:**
- Consumes: Canonical source and two PNG assets.
- Produces: Deterministic self-contained HTML and a validator that exits zero only when invariants hold.

- [ ] **Step 1: Create the validator first**

Using only Python's standard library and `html.parser.HTMLParser`, require all twelve section IDs, valid internal anchors, at least eight disclosures, two embedded PNG data URIs, required evidence/gap statuses, and no network-loaded `src`, stylesheet, or script. Allow source citations in `<a href>`.

- [ ] **Step 2: Verify the missing-output failure**

Run:

```bash
uv run python scripts/validate_approach_report.py docs/approach.html
```

Expected: non-zero with `missing report: docs/approach.html`.

- [ ] **Step 3: Create the packager**

Using `argparse`, `base64`, and `pathlib`, require each placeholder exactly once, verify PNG signatures, replace both placeholders with `data:image/png;base64,...`, reject remaining `{{...}}`, write UTF-8 `docs/approach.html`, and print source/output/byte size.

- [ ] **Step 4: Build, validate, and check determinism**

Run:

```bash
uv run python scripts/build_approach_report.py
uv run python scripts/validate_approach_report.py docs/approach.html
sha256sum docs/approach.html > /tmp/approach.before.sha256
uv run python scripts/build_approach_report.py
sha256sum -c /tmp/approach.before.sha256
```

Expected: validator prints `approach report valid`; checksum prints `docs/approach.html: OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_approach_report.py scripts/validate_approach_report.py docs/approach.html
git commit -m "docs: package self-contained approach report"
```

### Task 8: Render, Inspect, and Complete Final Verification

**Files:**
- Modify if required: `docs/approach/source.html`
- Regenerate if required: `docs/approach.html`
- Create locally: `/home/npatta01/.codex/visualizations/2026/07/14/019f5f2a-2ba4-7550-bc17-59e6656f5224/approach-report/desktop.png`
- Create locally: `/home/npatta01/.codex/visualizations/2026/07/14/019f5f2a-2ba4-7550-bc17-59e6656f5224/approach-report/mobile.png`

**Interfaces:**
- Consumes: Packaged report.
- Produces: Visually reviewed desktop/mobile report and final verification evidence.

- [ ] **Step 1: Render both viewports**

Run:

```bash
mkdir -p /home/npatta01/.codex/visualizations/2026/07/14/019f5f2a-2ba4-7550-bc17-59e6656f5224/approach-report
google-chrome --headless --disable-gpu --no-sandbox --hide-scrollbars --window-size=1440,12000 --screenshot=/home/npatta01/.codex/visualizations/2026/07/14/019f5f2a-2ba4-7550-bc17-59e6656f5224/approach-report/desktop.png "file://$PWD/docs/approach.html"
google-chrome --headless --disable-gpu --no-sandbox --hide-scrollbars --window-size=390,16000 --force-device-scale-factor=1 --screenshot=/home/npatta01/.codex/visualizations/2026/07/14/019f5f2a-2ba4-7550-bc17-59e6656f5224/approach-report/mobile.png "file://$PWD/docs/approach.html"
```

Expected: both commands report non-empty PNG files.

- [ ] **Step 2: Inspect with `view_image`**

Check vertical order, clipping, page-level horizontal overflow, prompt/code legibility, image crops, fan-out/reconvergence, and good/bad/gap hierarchy.

- [ ] **Step 3: Fix only verified issues in canonical source**

Use `apply_patch` on `docs/approach/source.html`; never hand-edit generated HTML. Rebuild, revalidate, and rerender the affected viewport.

- [ ] **Step 4: Run final verification**

Run:

```bash
uv run python scripts/build_approach_report.py
uv run python scripts/validate_approach_report.py docs/approach.html
git diff --check
git status --short
```

Expected: build succeeds; validator prints `approach report valid`; `git diff --check` is silent; status includes only intended report work plus the pre-existing `.repro/` and reproduction archives.

- [ ] **Step 5: Commit final corrections and hand off**

```bash
git add docs/approach/source.html docs/approach.html
git commit -m "docs: polish rendered approach report"
```

Link the final HTML, source, evidence snapshot, and both local QA screenshots. Report the Verified/Inferred/Illustrative example mix and confirm the report remains private/local.
