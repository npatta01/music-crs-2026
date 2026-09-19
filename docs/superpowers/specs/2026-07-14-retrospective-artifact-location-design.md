# Retrospective Artifact Location Design

Date: 2026-07-14

## Decision

Move the reader-facing retrospective from repository-root `retrospective.html` to:

```text
docs/retrospective.html
```

This location supersedes only the artifact-location requirements in the earlier retrospective specifications and plans. Their historical implementation details remain unchanged.

## Rationale

The entire repository is already scoped to the Music-CRS competition, so a second competition-named directory would be redundant. The retrospective is durable project documentation and belongs beside the existing architecture, evaluation, reproduction, and codebase documentation.

A nested `docs/retrospective/index.html` directory is unnecessary because the report is deliberately self-contained and has no companion asset directory.

## Required Changes

- Move the generated HTML artifact to `docs/retrospective.html`.
- Update the repository README link to `docs/retrospective.html`.
- Update active generator and browser-test input paths to the new location.
- Preserve the self-contained artifact, all canonical blocks, links, sources, payloads, and interactive behavior byte-for-byte apart from path-dependent regeneration effects.
- Keep `scripts/report/retrospective_deck.mjs` and `tests/report/` in their existing locations.
- Do not add a root redirect or duplicate HTML copy; the root should no longer contain `retrospective.html`.
- Do not rewrite historical plans/specifications that record the former root path. This design is the explicit superseding record.

## Verification

- A test must fail while active report constants still reference the root path.
- `docs/retrospective.html` must exist and root `retrospective.html` must not.
- The README link must resolve to the new tracked file.
- Node manifest tests, browser tests, full repository tests, deterministic regeneration, deck validation, and link/payload preservation must pass.
- The local viewer must serve the new artifact with the same checksum as the tracked file.
