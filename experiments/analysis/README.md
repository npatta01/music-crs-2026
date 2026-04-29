# Analysis Index

Use this directory for self-contained analysis packages that combine a narrative README with local artifacts.

## Packages

| Analysis | Status | Purpose | Main finding | Next step |
|---|---|---|---|---|
| [query_intent_v1](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/query_intent_v1/README.md) | `analyzed` | Label conversation-level intent structure over the `test` split. | Most sessions depend on long-range conversational carryover and likely need hybrid retrieval plus structured state. | Build a conversation-aware query representation layer. |

## Artifact Conventions

- Each analysis package should live at `experiments/analysis/<analysis_name>/README.md`.
- Raw outputs, label files, or supporting tables should live in a sibling artifact directory inside that package.
- Prefer topic-based names like `query_intent_v1` over issue-only names so the package is legible without external context.
