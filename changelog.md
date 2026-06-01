# Changelog

Hybrid log — **code/infra changes and experiment outcomes** in one place. Each entry links its PR so a result traces back to the exact code state. Metrics are devset **NDCG@20** unless noted. Newest first.

Tags: `Added` `Changed` `Fixed` `Docs` `Experiment`. See [experiments/README.md](experiments/README.md) for current bests and [leaderboard.md](leaderboard.md) for the ranked table.

Repo: https://github.com/npatta01/music-conversational-music-recomender-2026

## 2026-06

- `Experiment` **v0+ prompt-v4 all-retrievers full devset** — [#80](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/80). `v0plus_compiler_all_retrievers_devset` exercises BM25/year boosts, Qwen3 dense text, CLAP text, centroid branches, resolved-artist discography, and era/popularity. Full 5-shard Modal run: **NDCG@20 0.1219**, Hit@20 0.2660, Hit@1000 0.6967. Best tracked candidate coverage, but not a canonical top-20 ranking config. [report](experiments/v0plus_compiler_all_retrievers_devset.md)

## 2026-05

- `Fixed` **Issue #70 code-audit bugs** — [#71](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/71). Validate LanceDB distance types + convert `dot` distance back to higher-is-better similarity; skip anchor centroid-only branches on pivot turns; clear error on missing prediction keys in devset eval; dashboard points at `blindset_A` (`mcrs/dashboard_paths.py`); download `_trace.json` sidecars as trace artifacts. (`id_to_metadata` char-by-char bug was already fixed via the `DefaultFormatter` refactor.) Closes [#70](https://github.com/npatta01/music-conversational-music-recomender-2026/issues/70).
- `Experiment` **v0+ text-side retrieval Rounds 1–4** — [#69](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/69). Anchor-free SigLIP-2 / multi-CLAP text-side branches (per-branch encoder/query, GT-rank diagnostic). Architecture works and grows novel-artist pool coverage, but candidates rank too deep to win top-K without a reranker — no config beats image on NDCG@20. [report](experiments/v0plus_textside_2026-05-28.md)
- `Fixed` **4 retrieval pipeline bugs from the #65 audit** — [#66](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/66). Canonical `image` config re-run post-fix: **NDCG@20 0.1452** (vs 0.1461 pre-fix; deep-pool Hit@1000 0.598→0.626). [report](experiments/v0plus_compiler_image_devset.md)
- `Experiment` **v0+ compiler multimodal embedding ablation** — [#64](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/64). `image_siglip2` is the single biggest lever: **NDCG@20 0.146 (+48% vs BM25-only)**, +107% Hit@1. `all-embeddings` gives best coverage (Hit@1000 0.673). qwen3 attributes/lyrics branches *hurt* at macro. → current overall best. [report](experiments/v0plus_compiler_ablation_2026-05-26.md)
- `Added` v0+ compiler `blindset_A` config — [#63](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/63).
- `Experiment` `Changed` **v0+ ConversationState compiler + LanceDB-as-source migration** — [#62](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/62). Full devset run: **NDCG@20 0.1005 (+36% vs BM25 retrieval-only)**. LanceDB is now the catalog source of truth (`v0plus_catalog_lance.py`). [report](experiments/v0plus_compiler_devset.md)
- `Docs` ConversationState schema design — v3 candidate + v0+ iteration plan — [#61](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/61). [design](experiments/analysis/conversation_state_design_v2/README.md)
- `Docs` Gen-CRS literature review artifact — [#60](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/60).
- `Added` Modal LiteLLM cache + LanceDB retrieval services — [#59](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/59).
- `Changed` Archived old experiment configs into `configs/archive/` — [#58](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/58).
- `Experiment` LanceDB Modal sparse retrieval — [#57](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/57). [report](experiments/lancedb_fts_with_tag_list_devset.md)
- `Added` Native Milvus BM25 retrieval support — [#56](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/56). [report](experiments/milvus_bm25_with_tag_list_devset.md)
- `Added` **Unified experiment runner** (`run_experiment.py`, local + Modal) — [#55](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/55).

## 2026-04

- `Experiment` **Wave 4 — dense text retrieval** — [#38](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/38). Best: `dense_qwen3_embedding_8b` **NDCG@20 0.1025**. [index](experiments/README.md#wave-4-dense-text-retrieval)
- `Experiment` **Wave 3 — LLM-rewrite query understanding** — [#39](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/39). Best: `gemma4_e2b` carryover-guard v3 **NDCG@20 0.1092**.
- `Experiment` **Wave 2 — deterministic query understanding** (5 conversation→query transforms) — [#37](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/37), [#33](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/33), documented in [#36](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/36).
- `Experiment` **Wave 1 — BM25 metadata signal** — [#28](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/28). Best: `bm25_with_tag_list` **NDCG@20 0.0970** (retrieval-only reference).
- `Added` Issue-45 query-intent analysis report — [#48](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/48). [package](experiments/analysis/query_intent_v1/README.md)
- `Added` Newer OpenRouter frontier models — [#47](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/47).
- `Added` Retrieval analysis notebook + experiment index — [#46](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/46). Best offline hybrid `RRF(bm25+tags, dense_qwen3_8b)` **NDCG@20 0.1072**. [findings](experiments/retrieval_analysis_findings_2026-04-28.md)
- `Added` LiteLLM proxy support for embeddings + rewrite + generation — [#42](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/42).
- `Added` Bulk Modal artifact download workflow — [#41](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/41).
- `Added` Deep retrieval diagnostics @200/@500/@1000 — [#23](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/23).
- `Added` Pluggable QU module, `CorpusFormatter`, dummy LM, cache improvements — [#24](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/24).
- `Added` `run-experiment` skill (inference + eval + markdown report) — [#18](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/18).
- `Changed` Richer dev-set eval metrics (closes #5) — [#14](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/14).
- `Added` Modal cloud pipeline — persistent HF cache + results volumes, A10G inference, CPU eval — [#6](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/6).
- `Docs` Modal auth + smoke-test instructions — [#4](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/4).
- `Added` Interactive notebooks + Streamlit prediction explorer — [#3](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/3).
- `Added` Mac local-dev support + difficulty-stratified eval split — [#2](https://github.com/npatta01/music-conversational-music-recomender-2026/pull/2).
- `Docs` CLAUDE.md / AGENTS.md symlink + data/evaluation/architecture guides — `736ad06`.

## 2026-04 (pre-PR / initial)

- `Fixed` Attention implementation — `attn_implementation: "sdpa"`, flash-attention working — `25aad8f`, `b8ed954`, `283842c`.
- `Added` Initial submission packaging — `bb70133`.
- `Added` music-crs-evaluator as a submodule — `f1e8f35`.
- `Added` Repo init + baseline README — `f267f0f`.
