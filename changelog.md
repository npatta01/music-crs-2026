# Changelog

Hybrid log for code and experiment outcomes. This file now keeps only the
current experiment-facing entries plus a pointer to Git history for older waves.

Repo: https://github.com/npatta01/music-conversational-music-recomender-2026

## 2026-06

- `Docs` **Pruned experiment workspace**. Removed archived configs, stale
  per-run reports, and checked-in raw analysis artifacts so agents use the
  current configs and concise status files instead of old experiment notes.
- `Experiment` **v0+ prompt-v4 all-retrievers full devset** -
  [#80](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/80).
  `v0plus_compiler_all_retrievers_devset` exercises BM25/year boosts, Qwen3
  dense text, CLAP text, centroid branches, resolved-artist discography, and
  era/popularity. Full 5-shard Modal run: NDCG@20 0.1219, Hit@20 0.2660,
  Hit@1000 0.6967. Best tracked candidate coverage, but not the top-20 score
  anchor. [report](experiments/v0plus_compiler_all_retrievers_devset.md)

## 2026-05

- `Fixed` **Issue #70 code-audit bugs** -
  [#71](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/71).
  Canonical `image` config re-run post-fix: NDCG@20 0.1452. This remains the
  current score anchor. [report](experiments/v0plus_compiler_image_devset.md)
- `Added` v0+ compiler `blindset_A` config -
  [#63](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/63).
- `Changed` LanceDB is the v0+ catalog source of truth -
  [#62](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/62).

## Older History

Older experiment waves and raw reports were pruned from this working tree.
Use Git history or the PR list for prior BM25, dense-only, rewrite, Milvus,
LanceDB, text-side, and offline reranker details.
