# Blind-B Retrospective HTML Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private, self-contained HTML retrospective that explains the Music-CRS Blind-B result, compares the system with four leading public-code entries, and teaches reusable competition lessons without proposing a recovery roadmap.

**Architecture:** Freeze the leaderboard and repository evidence first, then build a claim ledger whose exact architectural statements point to commit-pinned sources. Compose a canonical Data Analytics `artifact.json` with native narrative, metric, table, and chart blocks plus five responsive custom diagram blocks; package it with the portable-report builder and require desktop/mobile verification before handoff.

**Tech Stack:** Git and GitHub source links, JSON, custom HTML/CSS/SVG inside portable report blocks, Data Analytics report artifact schema, Node.js portable-report builder and verifier.

## Global Constraints

- Follow `docs/superpowers/specs/2026-07-12-blind-b-retrospective-report-design.md` exactly.
- Keep the deliverable private and local; do not publish, deploy, or change sharing permissions.
- Store canonical report inputs and generated HTML under `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/`, outside tracked project source.
- Use first-person, accessible language and define uncommon terms on first use.
- Label material claims as **Verified**, **Inferred**, or **Not documented** in visible text; color and line style are secondary cues.
- Treat dev-set reuse as a measurement failure, not as a proven cause of Blind-B performance.
- Describe architecture differences as best-supported contributors, not hidden-set causal proof.
- Keep the close at the principle level; include no recovery plan, prioritized roadmap, proposed experiments, or next-step checklist.
- Pin all repository evidence to the exact commits listed in Task 1.
- Use `apply_patch` for hand-authored source files; use the packaged builder only for generated HTML.
- Do not stage or modify `.repro/`, `music-crs-repro-f519a83-20260711.tar.zst`, or its checksum.

## File Structure

- `/tmp/music-crs-retrospective-sources/` — disposable shallow checkouts used only to audit commit-pinned claims.
- `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json` — reviewed metrics, score-gap reconciliation, repository pins, and claim ledger.
- `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/diagram-probe.artifact.json` — minimal capability test for the two-rail architecture visual.
- `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/diagram-probe.html` — generated responsive-diagram probe.
- `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json` — canonical report artifact with embedded reviewed data and source metadata.
- `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/music-crs-blind-b-retrospective.html` — final self-contained deliverable.

---

### Task 1: Freeze Repositories and Reconcile the Leaderboard

**Files:**
- Create: `/tmp/music-crs-retrospective-sources/`
- Create: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json`
- Read: `configs/state_ranker_v10_lgbm_blindset_B.yaml`
- Read: `models/reranker_v12_goalfree/meta.json`

**Interfaces:**
- Consumes: Official final leaderboard CSV and five commit-pinned repositories.
- Produces: `evidence.json` with `leaderboard`, `gapContributions`, `repositories`, and an initially empty `claims` object.

- [ ] **Step 1: Create the private evidence workspace and exact checkouts**

Run:

```bash
mkdir -p /tmp/music-crs-retrospective-sources
mkdir -p /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective
git clone --filter=blob:none https://github.com/artvolgin/music-crs-recsys2026.git /tmp/music-crs-retrospective-sources/volart
git -C /tmp/music-crs-retrospective-sources/volart checkout 781ca9942b7c233255ac4a68da12fe42ec340b3a
git clone --filter=blob:none https://github.com/ryowk/recsys2026-niwatori.git /tmp/music-crs-retrospective-sources/niwatori
git -C /tmp/music-crs-retrospective-sources/niwatori checkout 5679a718c100aaf7779f122bb2eb65f702160f40
git clone --filter=blob:none https://github.com/yoobros/music-crs-challenge.git /tmp/music-crs-retrospective-sources/swyoo
git -C /tmp/music-crs-retrospective-sources/swyoo checkout 33dfe44dd36515e14e74116a8d23d059856d2d04
git clone --filter=blob:none https://github.com/lopsandrea/music-crs-team2.git /tmp/music-crs-retrospective-sources/team2
git -C /tmp/music-crs-retrospective-sources/team2 checkout e8ca96f67279a44aa38c614f51b4a015a65a2a90
```

Expected: each checkout ends in detached-HEAD state at the requested 40-character commit.

- [ ] **Step 2: Verify all five source revisions before reading claims**

Run:

```bash
git show -s --format=%H 2ecc45a7d5ea83535f0504b48352b009b3379139
git -C /tmp/music-crs-retrospective-sources/volart show -s --format=%H
git -C /tmp/music-crs-retrospective-sources/niwatori show -s --format=%H
git -C /tmp/music-crs-retrospective-sources/swyoo show -s --format=%H
git -C /tmp/music-crs-retrospective-sources/team2 show -s --format=%H
```

Expected, in order:

```text
2ecc45a7d5ea83535f0504b48352b009b3379139
781ca9942b7c233255ac4a68da12fe42ec340b3a
5679a718c100aaf7779f122bb2eb65f702160f40
33dfe44dd36515e14e74116a8d23d059856d2d04
e8ca96f67279a44aa38c614f51b4a015a65a2a90
```

- [ ] **Step 3: Create `evidence.json` with exact leaderboard rows**

Use `apply_patch` to encode these official rows and the composite formula:

```json
{
  "asOf": "2026-07-12",
  "officialResultsUrl": "https://nlp4musa.github.io/music-crs-challenge/static/results.csv",
  "compositeFormula": "0.50*nDCG@20 + 0.10*catalog_diversity + 0.10*lexical_diversity + 0.30*(LLM_judge-1)/4",
  "leaderboard": [
    {"entry":"volart","repository":"artvolgin/music-crs-recsys2026","composite":0.586611845,"ndcg20":0.396534887,"catalogDiversity":0.031611820,"lexicalDiversity":0.926832194,"llmJudge":4.9000},
    {"entry":"niwatori","repository":"ryowk/recsys2026-niwatori","composite":0.585920046,"ndcg20":0.493389952,"catalogDiversity":0.031186930,"lexicalDiversity":0.773563770,"llmJudge":4.4500},
    {"entry":"swyoo","repository":"yoobros/music-crs-challenge","composite":0.578429003,"ndcg20":0.382893624,"catalogDiversity":0.030273417,"lexicalDiversity":0.952048495,"llmJudge":4.8500},
    {"entry":"team2_s2","repository":"lopsandrea/music-crs-team2","composite":0.575916042,"ndcg20":0.445184942,"catalogDiversity":0.030252172,"lexicalDiversity":0.765483535,"llmJudge":4.6500},
    {"entry":"npatta01","repository":"npatta01/music-conversational-music-recomender-2026","composite":0.381109682,"ndcg20":0.253684925,"catalogDiversity":0.031484353,"lexicalDiversity":0.786187845,"llmJudge":3.3000}
  ],
  "gapContributions": [
    {"entry":"volart","totalGap":0.205502163,"ndcg20":0.071424981,"llmJudge":0.120000000,"lexicalDiversity":0.014064435,"catalogDiversity":0.000012747},
    {"entry":"niwatori","totalGap":0.204810364,"ndcg20":0.119852514,"llmJudge":0.086250000,"lexicalDiversity":-0.001262408,"catalogDiversity":-0.000029742},
    {"entry":"swyoo","totalGap":0.197319321,"ndcg20":0.064604349,"llmJudge":0.116250000,"lexicalDiversity":0.016586065,"catalogDiversity":-0.000121094},
    {"entry":"team2_s2","totalGap":0.194806360,"ndcg20":0.095750008,"llmJudge":0.101250000,"lexicalDiversity":-0.002070431,"catalogDiversity":-0.000123218}
  ],
  "repositories": {
    "npatta01":{"sha":"2ecc45a7d5ea83535f0504b48352b009b3379139","baseUrl":"https://github.com/npatta01/music-conversational-music-recomender-2026/blob/2ecc45a7d5ea83535f0504b48352b009b3379139/"},
    "volart":{"sha":"781ca9942b7c233255ac4a68da12fe42ec340b3a","baseUrl":"https://github.com/artvolgin/music-crs-recsys2026/blob/781ca9942b7c233255ac4a68da12fe42ec340b3a/"},
    "niwatori":{"sha":"5679a718c100aaf7779f122bb2eb65f702160f40","baseUrl":"https://github.com/ryowk/recsys2026-niwatori/blob/5679a718c100aaf7779f122bb2eb65f702160f40/"},
    "swyoo":{"sha":"33dfe44dd36515e14e74116a8d23d059856d2d04","baseUrl":"https://github.com/yoobros/music-crs-challenge/blob/33dfe44dd36515e14e74116a8d23d059856d2d04/"},
    "team2_s2":{"sha":"e8ca96f67279a44aa38c614f51b4a015a65a2a90","baseUrl":"https://github.com/lopsandrea/music-crs-team2/blob/e8ca96f67279a44aa38c614f51b4a015a65a2a90/"}
  },
  "claims": {"npatta01":[],"volart":[],"niwatori":[],"swyoo":[],"team2_s2":[]}
}
```

- [ ] **Step 4: Verify the formula and every signed gap**

Run:

```bash
node -e 'const fs=require("fs");const p="/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json";const e=JSON.parse(fs.readFileSync(p));const mine=e.leaderboard.find(x=>x.entry==="npatta01");for(const r of e.leaderboard){const c=.5*r.ndcg20+.1*r.catalogDiversity+.1*r.lexicalDiversity+.3*(r.llmJudge-1)/4;if(Math.abs(c-r.composite)>2e-9)throw Error(`composite ${r.entry}`)}for(const g of e.gapContributions){const s=g.ndcg20+g.llmJudge+g.lexicalDiversity+g.catalogDiversity;if(Math.abs(s-g.totalGap)>2e-9)throw Error(`gap terms ${g.entry}`);const r=e.leaderboard.find(x=>x.entry===g.entry);if(Math.abs((r.composite-mine.composite)-g.totalGap)>2e-9)throw Error(`gap total ${g.entry}`)}console.log("PASS: 5 composites and 4 signed gaps reconcile")'
```

Expected: `PASS: 5 composites and 4 signed gaps reconcile`.

---

### Task 2: Build the Commit-Pinned Claim Ledger

**Files:**
- Modify: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json`
- Read: `docs/architectures/v0plus_retrieval.md`
- Read: `docs/architectures/biencoder.md`
- Read: `docs/architectures/explanation_generation.md`
- Read: `configs/state_ranker_v10_lgbm_blindset_B.yaml`
- Read: `models/reranker_v12_goalfree/meta.json`
- Read: `mcrs/response_context.py`
- Read: `exp/inference/blindset_B/state_ranker_v10_lgbm_blindset_B.json`
- Read: `/tmp/music-crs-retrospective-sources/volart/`
- Read: `/tmp/music-crs-retrospective-sources/niwatori/`
- Read: `/tmp/music-crs-retrospective-sources/swyoo/`
- Read: `/tmp/music-crs-retrospective-sources/team2/`

**Interfaces:**
- Consumes: Pinned checkouts and the exact quantitative manifest from Task 1.
- Produces: Non-empty `claims[team]` arrays whose entries have `id`, `rail`, `label`, `status`, `summary`, `sourceUrl`, and `sourceNote`.

- [ ] **Step 1: Locate primary evidence for every planned exact claim**

Run focused searches rather than reading repositories indiscriminately:

```bash
rg -n "pool_k|b1_cos|LightGBM|RRF|out.of.fold|OOF|8000|8,000|Hit@1000|response" configs models docs mcrs scripts
rg -n 'response|response_text|Frank Ocean|Blonde' exp/inference/blindset_B/state_ranker_v10_lgbm_blindset_B.json
rg -n "five|5 |co.?occurrence|69|LambdaMART|best.of|critic|refine|validation" /tmp/music-crs-retrospective-sources/volart
rg -n "fourteen|14 |two.tower|176|history|transition|10 |candidate|divers" /tmp/music-crs-retrospective-sources/niwatori
rg -n "five.fold|5.fold|QLoRA|Qwen3|OOF|LightGBM|PAS|lexical" /tmp/music-crs-retrospective-sources/swyoo
rg -n "BGE|acoustic|collaborative|CatBoost|LightGBM|shift|Gemini|two.pass|ground" /tmp/music-crs-retrospective-sources/team2
```

Expected: every numeric or model-specific claim planned for a diagram has at least one primary-code or repository-documentation match. If a claim has no match, mark it `Not documented` or omit the exact count; do not infer a number.

- [ ] **Step 2: Add the author's system claims**

Use `apply_patch` to add entries covering both rails. This is the required shape:

```json
{
  "id": "own-reranker-boundary",
  "rail": "inference",
  "label": "RRF pool → top 500 → LightGBM",
  "status": "Verified",
  "summary": "The deployed Blind-B path fused retrieval candidates, truncated the pool to 500, and reranked that pool with the goal-free LightGBM bundle.",
  "sourceUrl": "https://github.com/npatta01/music-conversational-music-recomender-2026/blob/2ecc45a7d5ea83535f0504b48352b009b3379139/configs/state_ranker_v10_lgbm_blindset_B.yaml",
  "sourceNote": "Deployed Blind-B configuration"
}
```

Add separate entries for state extraction, retrieval lanes, `b1_cos`, in-sample dev evaluation, documented OOF nDCG of approximately 0.197–0.203, and single-pass response generation. Do not combine multiple source files into one claim entry; each marker must resolve unambiguously.

- [ ] **Step 3: Add volart claims**

Add separate offline and inference claims for the five retrieval lanes, track co-occurrence and priors, 69-feature LambdaMART, disjoint validation, best-of-three generation, critic/refine, hardening, and lexical-diversity handling. Every exact count must link under:

```text
https://github.com/artvolgin/music-crs-recsys2026/blob/781ca9942b7c233255ac4a68da12fe42ec340b3a/
```

- [ ] **Step 4: Add niwatori claims**

Add separate offline and inference claims for fourteen candidate sources, out-of-fold two-tower retrieval, history artist/album and transition signals, full-union candidate handling, the 176-feature LightGBM ranker, ten response candidates, and diversity-based selection. Every exact count must link under:

```text
https://github.com/ryowk/recsys2026-niwatori/blob/5679a718c100aaf7779f122bb2eb65f702160f40/
```

- [ ] **Step 5: Add swyoo claims**

Add separate offline and inference claims for the Qwen3 8B QLoRA two-tower, five folds, leakage-safe out-of-fold features, regularized LightGBM, PAS response structure, and lexical stabilization. Every exact count must link under:

```text
https://github.com/yoobros/music-crs-challenge/blob/33dfe44dd36515e14e74116a8d23d059856d2d04/
```

- [ ] **Step 6: Add team2_s2 claims**

Add separate offline and inference claims for multiple BGE retrievers, collaborative and acoustic evidence, routed LightGBM plus CatBoost, blind-like covariate-shift weighting, and two-pass fact-grounded Gemini generation. Every exact count must link under:

```text
https://github.com/lopsandrea/music-crs-team2/blob/e8ca96f67279a44aa38c614f51b4a015a65a2a90/
```

- [ ] **Step 7: Validate ledger completeness and evidence labels**

Run:

```bash
node -e 'const fs=require("fs");const p="/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json";const e=JSON.parse(fs.readFileSync(p));const teams=["npatta01","volart","niwatori","swyoo","team2_s2"];const states=new Set(["Verified","Inferred","Not documented"]);for(const t of teams){if(!Array.isArray(e.claims[t])||e.claims[t].length<4)throw Error(`too few claims: ${t}`);for(const c of e.claims[t]){for(const k of ["id","rail","label","status","summary","sourceNote"])if(!c[k])throw Error(`${t}/${c.id||"missing"}: ${k}`);if(!["offline","inference"].includes(c.rail))throw Error(`${t}/${c.id}: rail`);if(!states.has(c.status))throw Error(`${t}/${c.id}: status`);if(c.status!=="Not documented"&&!/^https:\/\/github\.com\/.+\/blob\/[0-9a-f]{40}\//.test(c.sourceUrl||""))throw Error(`${t}/${c.id}: unpinned source`)}}console.log("PASS: five claim ledgers are populated and commit-pinned")'
```

Expected: `PASS: five claim ledgers are populated and commit-pinned`.

---

### Task 3: Prove the Responsive Two-Rail Diagram Pattern

**Files:**
- Create: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/diagram-probe.artifact.json`
- Generate: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/diagram-probe.html`

**Interfaces:**
- Consumes: One author-system offline claim and one inference claim from `evidence.json`.
- Produces: A verified custom HTML block pattern reused for all five architecture diagrams.

- [ ] **Step 1: Create a minimal report artifact with one two-rail diagram**

Use `apply_patch` to create a valid report artifact with a `markdown` title block and one `html` block. The custom block must contain actual self-contained HTML/CSS with:

- a visibly named Offline rail and Inference rail;
- one ordered sequence of nodes per rail;
- visible **Verified** labels and `[S1]` source markers;
- a semantic ordered-list fallback containing the same steps;
- a media query at `max-width: 560px` that stacks the rails vertically;
- no external fonts, images, scripts, or stylesheets.

Use this source record exactly:

```json
{
  "id": "own-config",
  "label": "Pinned Blind-B configuration",
  "url": "https://github.com/npatta01/music-conversational-music-recomender-2026/blob/2ecc45a7d5ea83535f0504b48352b009b3379139/configs/state_ranker_v10_lgbm_blindset_B.yaml",
  "query": {
    "engine": "commit-pinned source review",
    "description": "Deployed Blind-B configuration",
    "executed_at": "2026-07-12",
    "tables_used": [],
    "filters": ["commit 2ecc45a7d5ea83535f0504b48352b009b3379139"],
    "metric_definitions": []
  }
}
```

- [ ] **Step 2: Package and verify the probe**

Run:

```bash
node /home/npatta01/.codex/plugins/cache/openai-curated-remote/data-analytics/0.2.8-13ceeea1f599/skills/build-report/scripts/deliver_portable_artifact.mjs --input /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/diagram-probe.artifact.json --output /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/diagram-probe.html --screenshot /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/diagram-probe-failure.png
```

Expected: `verification: passed`, with desktop and mobile viewport widths listed and zero external requests.

- [ ] **Step 3: Inspect the probe after packaged verification passes**

Open the generated local HTML in the available browser surface. Confirm both rails, labels, markers, and fallback are readable without horizontal scrolling. If the custom block clips or overflows, adjust only the probe HTML/CSS and rerun Step 2. Do not compose the other diagrams before this pattern is stable.

---

### Task 4: Compose the Canonical Report Artifact

**Files:**
- Create: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json`
- Read: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/evidence.json`

**Interfaces:**
- Consumes: Validated evidence manifest and proven architecture-diagram pattern.
- Produces: One canonical report artifact with the complete 13-section reading path, five diagrams, a signed contribution visual, exact leaderboard and cross-team tables, and canonical source metadata.

- [ ] **Step 1: Define report-native datasets and source records**

Create snapshot datasets named exactly:

```text
leaderboard
gap_contributions
cross_team_matrix
retrospective_choices
```

Use the reviewed rows from `evidence.json`. For `gap_contributions`, use one row per `entry × component`, with a signed `contribution` field and repeated `totalGap`. For `cross_team_matrix`, use only `Yes`, `Partial`, or `Not documented`; do not use `No` unless a primary source explicitly states that a technique was absent.

Create canonical sources for the official CSV, the pinned author repository, and each pinned competitor repository. The leaderboard source must include this executable SQL in `query.sql`:

```sql
SELECT *
FROM read_csv_auto('https://nlp4musa.github.io/music-crs-challenge/static/results.csv')
WHERE "Team ID" IN ('volart', 'niwatori', 'swyoo', 'team2_s2', 'npatta01')
ORDER BY "Composite Score" DESC;
```

- [ ] **Step 2: Build the headline and scoring blocks**

Use these stable block IDs in order:

```text
title
executive_summary
headline_metrics
how_scoring_works
leaderboard_table
gap_contribution_chart
gap_interpretation
```

The executive summary must state that the strongest evidence points to two broad issues: an unreliable in-sample development estimate, and weaker hidden-set ranking/response outcomes than the released leaders. It must immediately add that the first issue explains misplaced confidence, not the Blind-B score itself.

The metric strip must show the author's composite score `0.3811`, nDCG@20 `0.2537`, LLM judge `3.30/5`, and best public-code composite `0.5866`.

- [ ] **Step 3: Build the signed contribution visual and semantic fallback**

Use a native chart block when it can render signed values around zero without stacking negative values onto positive ones. Otherwise route the reviewed rows through the quantitative-visualization workflow and embed its static output in a custom block. The visual contract is:

- four panels: volart, niwatori, swyoo, team2_s2;
- horizontal zero line in every panel;
- one signed bar each for nDCG, LLM judge, lexical diversity, and catalog diversity;
- exact value label on every bar;
- explicit total-gap label;
- adjacent table with the same signed values.

The interpretation must say ranking and judge contributions dominate; catalog diversity is essentially neutral, while lexical diversity helps against volart/swyoo and slightly favors the author against niwatori/team2_s2.

- [ ] **Step 4: Build the author's system and methodological diagnosis**

Use stable block IDs:

```text
own_system_heading
own_system_diagram
own_system_walkthrough
what_worked
evaluation_mistake
ranking_contributors
response_contributors
```

The diagram must use the proven two-rail pattern and source each exact component from the author claim ledger. The evaluation section must show the documented in-sample range `0.384–0.456` separately from OOF nDCG `≈0.197–0.203`, then explain why Blind-B `0.2537` is more consistent with honest held-out evidence. Label the final comparison as an inference, not proof.

The response section must compare the Blind-A judge `4.70` with Blind-B `3.30`, discuss grounding limits and single-pass generation, and include the verified response-length comparison only if submitted response files can be traced to exact artifacts. Do not claim that length itself caused judge quality.

- [ ] **Step 5: Build the four competitor case studies**

Use these exact block IDs so all four case studies share the same six-part
template:

```text
volart_heading, volart_outcome, volart_diagram, volart_walkthrough, volart_comparison, volart_limits
niwatori_heading, niwatori_outcome, niwatori_diagram, niwatori_walkthrough, niwatori_comparison, niwatori_limits
swyoo_heading, swyoo_outcome, swyoo_diagram, swyoo_walkthrough, swyoo_comparison, swyoo_limits
team2_s2_heading, team2_s2_outcome, team2_s2_diagram, team2_s2_walkthrough, team2_s2_comparison, team2_s2_limits
```

Each diagram must contain an offline rail and an inference rail but may use a
topology appropriate to that system. Every exact count must carry a claim-ledger
marker. Each limits block must state what is not documented and that architecture
differences cannot prove session-level Blind-B causality.

- [ ] **Step 6: Build the cross-team synthesis and retrospective close**

Use stable block IDs:

```text
cross_team_heading
cross_team_matrix
preserve_reconsider_avoid
future_competition_lessons
caveats
evidence_notes
```

The matrix dimensions must include behavioral/co-occurrence retrieval, learned retrieval, leakage-safe validation, rich reranker features, full candidate union or late fusion, generation sampling, factual grounding, and response selection/critique.

The closing sections must remain retrospective. Phrase conclusions as principles such as “separate model-selection data from model-fitting data” and “optimize every scored component.” Do not introduce task owners, priorities, implementation stages, experiments, or schedules.

- [ ] **Step 7: Validate artifact structure before packaging**

Run:

```bash
node -e 'const fs=require("fs");const p="/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json";const a=JSON.parse(fs.readFileSync(p));const ids=new Set(a.manifest.blocks.map(b=>b.id));const required=["executive_summary","headline_metrics","leaderboard_table","gap_contribution_chart","own_system_diagram","volart_diagram","niwatori_diagram","swyoo_diagram","team2_s2_diagram","cross_team_matrix","preserve_reconsider_avoid","future_competition_lessons","caveats","evidence_notes"];for(const id of required)if(!ids.has(id))throw Error(`missing block ${id}`);const body=a.manifest.blocks.map(b=>b.body||"").join("\n");for(const bad of [/recovery plan/i,/next steps/i,/implementation roadmap/i])if(bad.test(body))throw Error(`forbidden roadmap language: ${bad}`);for(const label of ["Verified","Inferred","Not documented"])if(!body.includes(label))throw Error(`missing visible label ${label}`);console.log("PASS: required report structure and retrospective scope")'
```

Expected: `PASS: required report structure and retrospective scope`.

---

### Task 5: Package, Verify, and Hand Off the HTML

**Files:**
- Read: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json`
- Generate: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/music-crs-blind-b-retrospective.html`
- Generate on failure only: `/home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/report-verification-failure.png`

**Interfaces:**
- Consumes: Canonical `artifact.json` from Task 4.
- Produces: Final local HTML plus a passing packaged-verification receipt.

- [ ] **Step 1: Build and verify the portable HTML in one command**

Run:

```bash
node /home/npatta01/.codex/plugins/cache/openai-curated-remote/data-analytics/0.2.8-13ceeea1f599/skills/build-report/scripts/deliver_portable_artifact.mjs --input /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json --output /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/music-crs-blind-b-retrospective.html --screenshot /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/report-verification-failure.png
```

Expected: `verification: passed`, desktop and mobile viewports both succeed, the embedded artifact matches the source artifact, and external request count is zero.

- [ ] **Step 2: Run the standalone verifier as an independent second check**

Run:

```bash
node /home/npatta01/.codex/plugins/cache/openai-curated-remote/data-analytics/0.2.8-13ceeea1f599/skills/build-report/scripts/verify_portable_artifact.mjs --html /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/music-crs-blind-b-retrospective.html --artifact /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/artifact.json --screenshot /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/report-verification-failure.png
```

Expected: a passing result with no horizontal overflow, zero-size blocks, browser errors, or network requests.

- [ ] **Step 3: Perform the final content audit against the approved spec**

Confirm all of the following in the rendered HTML and source artifact:

- the opening directly answers what went wrong;
- the composite calculation and all four signed gaps reconcile;
- all five team diagrams have offline and inference rails;
- exact architectural counts have commit-pinned markers;
- each competitor uses the same outcome/walkthrough/comparison/limits template;
- the comparison matrix is tri-state;
- dev reuse is described as an estimate failure rather than hidden-score causality;
- strengths of the author's system are preserved;
- no recovery roadmap, prioritized actions, or proposed experiments appear;
- the caveats mention the 80-session hidden set and missing per-session labels.

- [ ] **Step 4: Confirm privacy and hand off the local artifact**

Run:

```bash
test -f /home/npatta01/.codex/visualizations/2026/07/13/019f58d4-5477-7621-b9cb-e88d6e78a846/blind-b-retrospective/music-crs-blind-b-retrospective.html
git status --short
```

Expected: the HTML exists; project status shows only the user's pre-existing untracked artifacts and any separately committed planning documentation. Do not stage the visualization workspace or publish the HTML.

Handoff with one clickable local link to the HTML, a one-sentence summary of the verified contents, and the packaged verifier result. Do not mention deployment or sharing unless the user asks.
