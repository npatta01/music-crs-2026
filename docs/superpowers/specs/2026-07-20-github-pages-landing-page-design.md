# GitHub Pages Landing Page Design

**Date:** 2026-07-20  
**Target:** repository-root `index.html`

## Goal

Create one static GitHub Pages landing page that routes visitors to the Music-CRS submission artifacts. The page is a link hub, not a narrative report, dashboard, or documentation site.

## Audience

Competition organizers, participants, reviewers, and repository visitors who want to understand, inspect, or reproduce the submission.

## Page structure

The page contains:

1. A compact header with the project name and one sentence explaining that this repository contains the RecSys Challenge 2026 Music-CRS submission and its retained evidence.
2. A responsive six-card link grid.
3. A small footer linking to the challenge website and repository license.

The six cards are:

| Card | Links |
| --- | --- |
| Reports | Architecture Deck; Competition Retrospective |
| Paper | Paper PDF only |
| Submissions | Blind-A submitted ZIP; Blind-B submitted ZIP |
| Audits | Blind-A submission audit; Blind-B submission audit |
| Code | GitHub repository only |
| Data | TalkPlay challenge datasets; offline reproduction bundle; released anchor-label data |

The Paper card must not link to the readable Markdown draft. The Code card must not include the codebase map, reproduction guide, or other secondary documentation.

## Link targets

- Architecture Deck: `docs/submission-architecture.html`
- Competition Retrospective: `docs/retrospective.html`
- Paper PDF: `paper/main.pdf`
- Blind-A submission: `submission/v10_lgbm_A.zip`
- Blind-B submission: `submission/v10_lgbm_B_v1.zip`
- Blind-A audit: `reports/blindset-a-submission-audit/report.html`
- Blind-B audit: `reports/blindset-b-submission-audit/report.html`
- Code: `https://github.com/npatta01/music-crs-2026`
- Challenge datasets: `https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge`
- Offline reproduction bundle: `https://huggingface.co/datasets/Npatta01/music-crs-repro-2026`
- Anchor-label data: `data/anchor_labels_v1/README.md`
- Challenge website: `https://nlp4musa.github.io/music-crs-challenge/`
- License: `LICENSE`

## Visual design

The page reuses the architecture deck's visual language without copying its slide navigation:

- dark navy default background;
- system sans-serif typography;
- pale text with cyan, violet, green, amber, and coral accents;
- colored top rules and compact icons to distinguish cards;
- restrained gradients and borders;
- no decorative raster images or model-authored SVGs;
- a light color scheme when the operating system requests light mode;
- reduced-motion support.

Cards should feel like clear destinations rather than dense boxes. Each card has a short label, one-line description, and one or more obvious links. The first viewport should show the complete purpose and most or all of the link grid on a typical laptop.

## Technical design

- Deliver one hand-authored, dependency-free `index.html` at the repository root.
- Keep CSS embedded in the file so GitHub Pages needs no build step.
- Use semantic landmarks, headings, lists, and anchors.
- Use only relative repository paths and the approved external URLs above.
- Open links in the same tab unless the browser/user chooses otherwise.
- Add visible focus states and sufficient dark/light contrast.
- Collapse the grid from three columns to two and then one at smaller widths.
- Do not add JavaScript, analytics, web fonts, CDN assets, a framework, or a Pages deployment workflow.

GitHub Pages can serve the page when the repository's Pages source is configured to the selected branch root. Publishing and repository settings changes are outside this implementation unless separately authorized.

## Verification

Automated checks should verify:

- every required card and exact link is present;
- the removed Paper and Code secondary links are absent;
- all relative targets exist in the repository;
- the page contains no remote scripts, stylesheets, images, fonts, or iframes;
- desktop, tablet, and phone layouts have no horizontal overflow;
- keyboard focus is visible;
- dark, light, reduced-motion, and print modes remain readable.

The implementation should be inspected locally in a browser before handoff. No public deployment is part of verification.
