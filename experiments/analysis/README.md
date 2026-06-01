# Analysis Index

Use this directory for self-contained analysis packages that combine a narrative README with local artifacts.

## Packages

| Analysis | Status | Purpose | Main finding | Next step |
|---|---|---|---|---|
| [query_intent_v1](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/query_intent_v1/README.md) | `analyzed` | Label conversation-level intent structure over the `test` split. | Most sessions depend on long-range conversational carryover and likely need hybrid retrieval plus structured state. | Build a conversation-aware query representation layer. |
| [embedding_bakeoff](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/analysis/embedding_bakeoff/README.md) | `analyzed` | Qwen3-Embedding subset bake-off: encoder size (0.6B/4B/8B) × tags template (raw/NL) × query mode (sym/instruct), two seeds. | Encoder size moves deep recall (0.6B→4B large, 4B→8B Recall@1000-only); NL tags template beats raw tag-dump at 0.6B/4B; instruct prefix is a free win. Writeup: [`embedding_bakeoff_qwen3_subset.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/embedding_bakeoff_qwen3_subset.md). | Instruct prefix on dense-text branch; re-embed attributes column with NL template; quantify full-catalog re-embed at 4B. |

## Artifact Conventions

- Each analysis package should live at `experiments/analysis/<analysis_name>/README.md`.
- Raw outputs, label files, or supporting tables should live in a sibling artifact directory inside that package.
- Prefer topic-based names like `query_intent_v1` over issue-only names so the package is legible without external context.
