# Experiment Log

This file captures cross-run takeaways, decisions, and next steps.

Per-run artifacts stay in `experiments/{tid}.md`.
Use this log to summarize what we learned from a group of related runs.

## 2026-04-27 - BM25 metadata signal wave 1

Question:
Which metadata fields help BM25 retrieval most?

Runs:
- `bm25_devset_retrieval_only`
- `bm25_devset_retrieval_only_no_release_date`
- `bm25_devset_retrieval_only_with_tag_list`
- `bm25_devset_retrieval_only_tag_list_only`

Takeaways:
- Adding `tag_list` to the default BM25 corpus was the strongest result in the wave.
- `bm25_devset_retrieval_only_with_tag_list` improved over the control from `NDCG@10 0.0626 -> 0.0752`, `NDCG@20 0.0815 -> 0.0970`, `Hit@20 0.2200 -> 0.2640`, and `Hit@1000 0.4265 -> 0.6311`.
- Removing `release_date` alone was a small positive, which suggests `release_date` is weak signal and may add some noise.
- `tag_list` alone underperformed the control at the head, so tags look best as an additive field rather than a replacement for title, artist, and album.

Linked reports:
- `experiments/bm25_devset_retrieval_only_no_release_date.md`
- `experiments/bm25_devset_retrieval_only_with_tag_list.md`
- `experiments/bm25_devset_retrieval_only_tag_list_only.md`

Next step:
- Run the optional single-field ablations: `track_name` only, `artist_name` only, and `album_name` only.
- If those confirm `tag_list` is additive rather than substitutive, promote `track_name + artist_name + album_name + tag_list` as the new BM25 retrieval-only default and use it for the next reranking or QU wave.

Status:
- In progress

## 2026-05-10 - Milvus native BM25 tag-list comparison

Question:
How close is native Milvus BM25 to the checked-in non-Milvus sparse baseline when both use the same combined metadata plus tag-list corpus?

Runs:
- `bm25_devset_retrieval_only_with_tag_list`
- `milvus_bm25_with_tag_list_devset`

Key metrics:
- Non-Milvus baseline: `bm25_devset_retrieval_only_with_tag_list`
  - `NDCG@20 0.0970`
  - `Hit@20 0.2640`
  - `Hit@1000 0.6311`
  - `MRR 0.0558`
- Milvus native BM25: `milvus_bm25_with_tag_list_devset`
  - `NDCG@20 0.0933`
  - `Hit@20 0.2514`
  - `Hit@1000 0.6048`
  - `MRR 0.0542`

Takeaways:
- Native Milvus BM25 is close to the repo's checked-in sparse baseline, but it is still slightly behind across head and deep retrieval metrics.
- The current Milvus BM25 setup uses an explicit analyzer override on the text fields instead of the implicit/default Milvus field analysis: `standard` tokenizer plus `lowercase` and English stopword filtering.
- That analyzer change was important operationally because earlier raw Milvus BM25 runs sometimes returned fewer than `topk=1000` results. With the explicit analyzer, the devset run preserved full `topk=1000` output depth, so the comparison is now fully native and does not rely on synthetic tail padding.
- The remaining gap is modest at the head: `-0.0037 NDCG@20`, `-0.0126 Hit@20`, and `-0.0016 MRR`.
- The deeper retrieval gap is still visible at `Hit@1000`: `0.6311 -> 0.6048` (`-0.0263`).
- This is a reasonable foundation for future sparse+dense Milvus hybrid work, but the non-Milvus BM25 baseline remains the stronger pure sparse retrieval reference for now.

Linked reports:
- `experiments/bm25_devset_retrieval_only_with_tag_list.md`
- `experiments/milvus_bm25_with_tag_list_devset.md`

Next step:
- Use `milvus_bm25_with_tag_list_devset` as the Milvus sparse anchor when comparing future Milvus dense-only and hybrid retrieval configs.

Status:
- Done

## 2026-05-15 - LanceDB CPU FTS tag-list comparison

Question:
Can LanceDB provide a CPU-only sparse retrieval path on Modal that stays close to the direct `bm25s` tag-list baseline and is competitive with the native Milvus BM25 comparison?

Runs:
- `lancedb_fts_with_tag_list_devset`
- `bm25_devset_retrieval_only_with_tag_list`
- `milvus_bm25_with_tag_list_devset`

Key metrics:
- Direct BM25 tag-list baseline:
  - `NDCG@20 0.0971`
  - `Hit@20 0.2642`
  - `Hit@100 0.4305`
  - `Hit@1000 0.6310`
  - `MRR 0.0558`
- LanceDB CPU FTS:
  - `NDCG@20 0.0962`
  - `Hit@20 0.2602`
  - `Hit@100 0.4249`
  - `Hit@1000 0.6235`
  - `MRR 0.0557`
- Milvus native BM25:
  - `NDCG@20 0.0933`
  - `Hit@20 0.2514`
  - `Hit@100 0.4104`
  - `Hit@1000 0.6048`
  - `MRR 0.0542`

Takeaways:
- LanceDB FTS does not need GPU for this sparse retrieval experiment; the Modal path uses CPU resources and reads the index from the `music-crs-models` volume.
- The useful configuration is `fts_bm25s_compat`: pre-tokenize item text with `bm25s.tokenize`, index that field with LanceDB whitespace FTS, and query with structured `MatchQuery` boosts to preserve repeated query terms.
- Native LanceDB string querying against the tokenized field was not close enough by itself because it lost the repeated-query-term signal that direct `bm25s` uses.
- The final LanceDB run is very close to direct BM25: `-0.0009 NDCG@20`, `-0.0040 Hit@20`, `-0.0075 Hit@1000`, and `-0.0001 MRR`.
- Candidate overlap with direct BM25 is high: `overlap@20 0.9463`, `overlap@100 0.9511`, and `overlap@1000 0.9582`.
- LanceDB is ahead of the current Milvus sparse anchor across head and deep retrieval metrics: `+0.0029 NDCG@20`, `+0.0088 Hit@20`, and `+0.0187 Hit@1000`.
- LanceDB FTS can return fewer than `topk` rows for rare queries. The implementation pads the zero-score tail from catalog order after scored FTS matches so the devset diagnostic contract stays at `min_pool_depth = max_pool_depth = 1000`.

Linked reports:
- `experiments/lancedb_fts_with_tag_list_devset.md`
- `experiments/bm25_devset_retrieval_only_with_tag_list.md`
- `experiments/milvus_bm25_with_tag_list_devset.md`

Next step:
- Upload the rebuilt local `cache/lancedb` directory to the Modal models volume before Modal runs: `uv run modal run modal/app.py::upload_lancedb_index --local-db-dir cache/lancedb --remote-dir lancedb`.
- Use `lancedb_fts_with_tag_list_devset` as the LanceDB sparse anchor for future CPU sparse or sparse+dense comparisons.

Status:
- Done

## 2026-04-27 - Deterministic QU wave 2

Question:
Do cleaner conversation-to-query transforms improve BM25 retrieval?

Runs (all on devset, `lm_type=dummy`, BM25 over `track_name`/`artist_name`/`album_name`/`release_date`, `retrieval_topk=1000`; control = `bm25_devset_retrieval_only` passthrough):
- `bm25_qu_last_user_turn_devset`
- `bm25_qu_user_turns_only_devset`
- `bm25_qu_last_2_user_turns_devset`
- `bm25_qu_last_3_user_turns_devset`
- `bm25_qu_no_music_history_devset`

Results (NDCG@20 / Hit@20 / Hit@100):
- passthrough (control): `0.0815 / 0.2200 / 0.3340`
- no_music_history:      `0.0496 / 0.1204 / 0.2084`
- user_turns_only:       `0.0474 / 0.1090 / 0.1881`
- last_3_user_turns:     `0.0461 / 0.1033 / 0.1723`
- last_2_user_turns:     `0.0459 / 0.0999 / 0.1666`
- last_user_turn:        `0.0448 / 0.0964 / 0.1653`

Takeaways:
- Every deterministic transform underperforms the passthrough baseline. Hit@20 collapses by ~45-55% across all five variants.
- Prior music-recommendation metadata (artist, album, track names from earlier turns) is the dominant BM25 signal. Stripping it - whether by user-only filters or by `no_music_history` - is what hurts, not the conversational noise we hoped to remove.
- `no_music_history` is the strongest of the five (it keeps user + assistant text turns), confirming that assistant text adds some value but nowhere near enough to recover what's lost from dropping music turns.
- Per-turn breakdown shows turn 1 is identical across all variants (no history yet); the gap opens from turn 2 onward as music history accumulates.

Linked reports:
- `experiments/bm25_qu_last_user_turn_devset.md`
- `experiments/bm25_qu_user_turns_only_devset.md`
- `experiments/bm25_qu_last_2_user_turns_devset.md`
- `experiments/bm25_qu_last_3_user_turns_devset.md`
- `experiments/bm25_qu_no_music_history_devset.md`

Next step:
- For wave 3 (LLM rewrite), the rewriter must deliberately preserve or re-inject the artist+track signal that prior music turns provide - not just narrow the conversation to user intent.
- Skip further deterministic QU variants on BM25; the signal is clear that naive trimming loses more than it gains.

Status:
- Done

## 2026-04-28 - Sparse/dense complementarity and hybrid simulation

Question:
Are the best sparse and dense retrieval runs complementary enough to justify a hybrid stack?

Inputs:
- `bm25_devset_retrieval_only_with_tag_list` (best sparse retrieval-only run)
- `dense_qwen3_embedding_8b_devset` (best dense retrieval-only run)
- Offline analysis from `notebooks/retrieval_analysis.ipynb` over `evaluator/exp/inference/devset/*.json`

Key metrics:
- Sparse baseline: `bm25_devset_retrieval_only_with_tag_list`
  - `NDCG@20 0.0970`
  - `Hit@20 0.2640`
  - `Hit@1000 0.6311`
- Dense baseline: `dense_qwen3_embedding_8b_devset`
  - `NDCG@20 0.1025`
  - `Hit@20 0.2653`
  - `Hit@1000 0.6934`
- Offline RRF hybrid (`k=60`) over the two ranked lists
  - `NDCG@20 0.1072`
  - `Hit@20 0.2828`
  - `Hit@1000 0.7210`

Complementarity breakdown at top-1000 across 8,000 dev turns:
- Both hit: `4401` (`55.0%`)
- Both miss: `1805` (`22.6%`)
- Dense-only hits: `1146` (`14.3%`)
- Sparse-only hits: `648` (`8.1%`)
- Union hit count: `6195` (`77.4%`)

Takeaways:
- The dense Qwen 8B retriever is the stronger single system, but the sparse BM25 run still contributes substantial unique coverage.
- BM25 recovers `648` gold tracks in the top-1000 that dense misses entirely, which is too much complementary signal to ignore.
- The reverse gap is larger (`1146` dense-only hits), so any hybrid should treat dense as the stronger base and sparse as additive support rather than equal peers.
- Simple rank fusion already improves over both standalone runs: `+0.0046 NDCG@20` over dense, `+0.0102 NDCG@20` over sparse, and `+0.0276 Hit@1000` over dense.
- This is strong evidence that the next retrieval wave should include a hybrid sparse+dense candidate or a learned reranker over the union pool.

Linked reports:
- `experiments/bm25_devset_retrieval_only_with_tag_list.md`
- `experiments/dense_qwen3_embedding_8b_devset.md`
- `experiments/retrieval_analysis_findings_2026-04-28.md`
- `notebooks/retrieval_analysis.ipynb`

Next step:
- Build a first hybrid retrieval wave using the dense Qwen 8B run as the primary branch and BM25-with-tags as the complementary branch, starting with offline fusion baselines and then a reranker over the union candidate set.

Status:
- Done

## 2026-04-27 - LLM rewrite wave 3

Question:
Can an LLM-backed QU rewrite improve BM25 retrieval on the new sparse control `track_name + artist_name + album_name + tag_list` with `release_date` removed?

Control:
- `bm25_devset_retrieval_only_tag_list_no_release_date`
  - `NDCG@20 0.0972`
  - `Hit@20 0.2640`
  - `Hit@100 0.4320`
  - `Hit@200 0.4959`
  - `Hit@1000 0.6341`
  - `MRR 0.0561`

Phase 1 preserve prompt runs completed:
- `bm25_qu_llmrewrite_llama32_1b_preserve_entities_v1_devset`
  - `NDCG@20 0.0946`
  - `Hit@20 0.2577`
  - `Hit@100 0.4234`
  - `Hit@200 0.4865`
  - `Hit@1000 0.6181`
- `bm25_qu_llmrewrite_smollm2_1p7b_preserve_entities_v1_devset`
  - `NDCG@20 0.0970`
  - `Hit@20 0.2594`
  - `Hit@100 0.4256`
  - `Hit@200 0.4892`
  - `Hit@1000 0.6241`
- `bm25_qu_llmrewrite_gemma4_e2b_preserve_entities_v1_devset`
  - `NDCG@20 0.1048`
  - `Hit@20 0.2475`
  - `Hit@100 0.3841`
  - `Hit@200 0.4307`
  - `Hit@1000 0.5584`
- `bm25_qu_llmrewrite_qwen25_3b_preserve_entities_v1_devset`
  - `NDCG@20 0.1001`
  - `Hit@20 0.2319`
  - `Hit@100 0.3639`
  - `Hit@200 0.4089`
  - `Hit@1000 0.5383`
- `bm25_qu_llmrewrite_qwen3_4b_preserve_entities_v1_devset`
  - `NDCG@20 0.1061`
  - `Hit@20 0.2498`
  - `Hit@100 0.4144`
  - `Hit@200 0.4784`
  - `Hit@1000 0.6273`

Phase 2 prompt runs completed so far:
- `bm25_qu_llmrewrite_gemma4_e2b_catalog_terms_v2_devset`
  - `NDCG@20 0.1089`
  - `Hit@20 0.2500`
  - `Hit@100 0.3886`
  - `Hit@200 0.4355`
  - `Hit@1000 0.5713`
  - `MRR 0.0732`
- `bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset`
  - `NDCG@20 0.1092`
  - `Hit@20 0.2617`
  - `Hit@100 0.3834`
  - `Hit@200 0.4301`
  - `Hit@1000 0.5561`
  - `MRR 0.0695`
- `bm25_qu_llmrewrite_qwen25_3b_catalog_terms_v2_devset`
  - `NDCG@20 0.1008`
  - `Hit@20 0.2390`
  - `Hit@100 0.3725`
  - `Hit@200 0.4245`
  - `Hit@1000 0.5740`
  - `MRR 0.0660`
- `bm25_qu_llmrewrite_qwen25_3b_carryover_guard_v3_devset`
  - `NDCG@20 0.0936`
  - `Hit@20 0.2131`
  - `Hit@100 0.3505`
  - `Hit@200 0.3978`
  - `Hit@1000 0.5185`
  - `MRR 0.0640`
- `bm25_qu_llmrewrite_qwen3_4b_catalog_terms_v2_devset`
  - `NDCG@20 0.1055`
  - `Hit@20 0.2451`
  - `Hit@100 0.4096`
  - `Hit@200 0.4767`
  - `Hit@1000 0.6281`
  - `MRR 0.0713`
- `bm25_qu_llmrewrite_qwen3_4b_carryover_guard_v3_devset`
  - `NDCG@20 0.1049`
  - `Hit@20 0.2468`
  - `Hit@100 0.4087`
  - `Hit@200 0.4685`
  - `Hit@1000 0.6164`
  - `MRR 0.0700`

Takeaways:
- The sparse control is strong, but multiple rewrite models beat it on ranking quality. The best completed run so far is `Gemma-4-E2B + carryover_guard_v3`, which improves `NDCG@20` from `0.0972 -> 0.1092`.
- Head ranking and deeper pool coverage need to be read together. Some rewrites improve `NDCG@20` and `MRR` while giving back `Hit@100` and beyond; others, like `Qwen3-4B preserve_entities_v1`, stay much closer to the control on `Hit@1000` (`0.6273` vs `0.6341`) while still lifting `NDCG@20`.
- Among preserve-only Phase 1 runs, the current ranking is `Qwen3-4B` first, `Gemma-4-E2B` second, and `Qwen2.5-3B` third.
- The best prompt outcome so far is not the baseline preserve prompt. Both completed Gemma prompt variants outperform `Gemma preserve_entities_v1`, which is a strong sign that prompt choice matters materially for rewrite quality.
- `Qwen2.5-3B` did not reproduce that same prompt lift. `catalog_terms_v2` stayed narrowly above its preserve baseline on `NDCG@20` (`0.1008` vs `0.1001`) but remained below it on `MRR`, while `carryover_guard_v3` regressed on both ranking quality and coverage.
- `Qwen3-4B` also did not beat its preserve baseline. Both prompt variants stayed below `Qwen3 preserve_entities_v1` on `NDCG@20`, and `catalog_terms_v2` was the better of the two while remaining roughly tied on deeper coverage.
- Rewrites do not move as one family on coverage. `Gemma carryover_guard_v3` currently leads on `NDCG@20`, but `SmolLM2 catalog_terms_v2` is stronger on `Hit@20`, `Hit@100`, `Hit@200`, and `Hit@1000` than any completed rewrite run except the sparse control.
- `meta-llama/Llama-3.2-3B-Instruct` was operationally blocked in Modal by gated-model access, so the planned fallback replacement `Qwen/Qwen2.5-3B-Instruct` was used instead.

Linked reports:
- `experiments/bm25_devset_retrieval_only_tag_list_no_release_date.md`
- `experiments/bm25_qu_llmrewrite_llama32_1b_preserve_entities_v1_devset.md`
- `experiments/bm25_qu_llmrewrite_smollm2_1p7b_preserve_entities_v1_devset.md`
- `experiments/bm25_qu_llmrewrite_gemma4_e2b_preserve_entities_v1_devset.md`
- `experiments/bm25_qu_llmrewrite_qwen25_3b_preserve_entities_v1_devset.md`
- `experiments/bm25_qu_llmrewrite_qwen3_4b_preserve_entities_v1_devset.md`
- `experiments/bm25_qu_llmrewrite_gemma4_e2b_catalog_terms_v2_devset.md`
- `experiments/bm25_qu_llmrewrite_gemma4_e2b_carryover_guard_v3_devset.md`
- `experiments/bm25_qu_llmrewrite_qwen25_3b_catalog_terms_v2_devset.md`
- `experiments/bm25_qu_llmrewrite_qwen25_3b_carryover_guard_v3_devset.md`
- `experiments/bm25_qu_llmrewrite_qwen3_4b_catalog_terms_v2_devset.md`
- `experiments/bm25_qu_llmrewrite_qwen3_4b_carryover_guard_v3_devset.md`

Next step:
- Finalize the Wave 3 winner by the fixed rule: `NDCG@20`, then `Hit@20`, then rewrite latency, then fallback rate, while explicitly reporting `Hit@100`, `Hit@200`, and `Hit@1000` alongside the winner so deeper coverage tradeoffs stay visible.

Status:
- Done

## 2026-04-27 - Dense text retrieval wave 4

Question:
Can a generic Hugging Face dense text retriever beat the strongest sparse text baseline on passthrough conversational queries using only track metadata text?

Runs:
- `dense_e5_base_v2_devset`
- `dense_bge_base_en_v1_5_devset`
- `dense_e5_large_v2_devset`
- `dense_bge_large_en_v1_5_devset`
- `dense_qwen3_embedding_0_6b_devset`
- `dense_qwen3_embedding_4b_devset`
- `dense_qwen3_embedding_8b_devset`

Key metrics:
- Comparison baseline: `bm25_devset_retrieval_only_with_tag_list` = `NDCG@20 0.0970`, `Hit@20 0.2640`, `Hit@100 0.4305`, `Hit@200 0.4919`, `Hit@500 0.5714`, `Hit@1000 0.6311`, `NDCG@1000 0.1522`.
- Best non-Qwen dense run: `dense_e5_base_v2_devset` = `NDCG@20 0.0906`, `Hit@20 0.2310`, `Hit@100 0.3593`, `Hit@200 0.4113`, `Hit@500 0.4825`, `Hit@1000 0.5520`, `NDCG@1000 0.1375`.
- Dense runner-up: `dense_qwen3_embedding_4b_devset` = `NDCG@20 0.0994`, `Hit@20 0.2479`, `Hit@100 0.4250`, `Hit@200 0.4965`, `Hit@500 0.5996`, `Hit@1000 0.6803`, `NDCG@1000 0.1630`.
- Best dense run: `dense_qwen3_embedding_8b_devset` = `NDCG@20 0.1025`, `Hit@20 0.2652`, `Hit@100 0.4435`, `Hit@200 0.5120`, `Hit@500 0.6130`, `Hit@1000 0.6934`, `NDCG@1000 0.1658`.

Takeaways:
- Dense retrieval is promising, but only the Qwen family clearly changed the frontier in this wave.
- `dense_qwen3_embedding_8b_devset` is the first dense run to beat `bm25_devset_retrieval_only_with_tag_list` on all three primary comparison metrics, plus the `NDCG@1000` headroom diagnostic.
- `dense_qwen3_embedding_4b_devset` already surpassed the sparse comparison on `NDCG@20` and `Hit@1000`, but still trailed slightly on `Hit@20`; the 8B model closed that final gap.
- The deeper coverage story matters too: Qwen 8B beats the sparse baseline not just at `Hit@1000`, but also at `Hit@100`, `Hit@200`, and `Hit@500`, which makes the dense gain more robust than a single-cutoff win.
- Scaling helped substantially for Qwen (`0.6B -> 4B -> 8B`), helped modestly for BGE, and did not help for E5 where the base model slightly beat the large model.
- Even before reranking, the Qwen dense runs materially improved deep-pool coverage, which makes them strong candidates for a next-stage reranker or hybrid sparse+dense stack.

Linked reports:
- `experiments/dense_e5_base_v2_devset.md`
- `experiments/dense_bge_base_en_v1_5_devset.md`
- `experiments/dense_e5_large_v2_devset.md`
- `experiments/dense_bge_large_en_v1_5_devset.md`
- `experiments/dense_qwen3_embedding_0_6b_devset.md`
- `experiments/dense_qwen3_embedding_4b_devset.md`
- `experiments/dense_qwen3_embedding_8b_devset.md`

Next step:
- Promote `dense_qwen3_embedding_8b_devset` as the dense candidate for the next reranking or hybrid retrieval wave, and keep `dense_qwen3_embedding_4b_devset` as the lower-cost fallback.

Status:
- Done

## 2026-05-25 - v0+ ConversationState compiler: end-to-end devset run + tuning campaign

Question:
Does the v0+ compiler (full pipeline: LLM extractor → resolver → multi-branch retrieval + fusion + soft adjustments) beat the BM25 baseline on the competition metric (NDCG@20), and where is the remaining headroom?

Runs:
- `v0plus_compiler_devset` (the canonical config — see [`v0plus_compiler_devset.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_compiler_devset.md) for full ablation history)

Setup highlights (also documented in the per-run report):
- Migrated the v0+ catalog source-of-truth from a duplicated in-memory `HFTalkPlayCatalog` to `LanceDbCatalog` (single canonical source — the same LanceDB used for retrieval). 9-task implementation plan at [`docs/superpowers/plans/2026-05-25-lancedb-as-catalog-source-of-truth.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/docs/superpowers/plans/2026-05-25-lancedb-as-catalog-source-of-truth.md).
- Fixed a silent `release_date between` filter bug: schema was overloaded `value: str | list[str]`, catalog only handled the list form, LLM emitted the string form — filter mask silently returned `set()`, killing the candidate pool. Schema retyped to `start: date | None, end: date | None`; LanceDB `release_date` migrated from `string` to `pa.date32()`.
- Fixed a second silent bug: `_apply_soft_adjustments` ignored `rs.resolved_rejections` entirely. Resolver translated `explicit_rejections` into artist/track ids but the compiler never read the field. Now hard-excludes matching tracks; pivot subset Hit@20 went 0.126 → 0.201.
- Added per-turn state trace sidecar (`{tid}_trace.json`) capturing extracted state + resolver counts + compiler counts.
- Added cross-container sharding (`run_inference_sharded` in `modal/app.py` + `scripts/merge_shard_results.py`) — full devset wall time ~10 min at N=5 vs ~60 min single-shard.

Headline result:
- `NDCG@20 0.1005`, `Hit@20 0.2378`, `MRR 0.0676` on full 1000-session devset.
- vs BM25 baseline (`lancedb_fts_with_tag_list`): **+36% NDCG@20, +23% Hit@20, +52% MRR, +182% Hit@1**.
- vs v0+ design target (`NDCG@20 ≥ 0.1092`): 8% short.
- Per-turn pattern: v0+ advantage *grows* with conversation depth (turn 1 +7% vs BM25, turn 6 +44%) — the multi-turn state is doing real work.

Ablation campaign (NDCG@20, full devset):
- Baseline (dense on, original knobs): 0.0878
- α = 0.30, `same_artist_demote` = 1.0 (dense on): 0.0880 — no signal
- α = 0.30, dense **off**: **0.1009** (+15% vs baseline) ← picked
- + explicit-rejections hard-exclude: 0.1005 (macro flat; pivot subset Hit@20 +60%)

Takeaways:
- Sparse-only retrieval *beats* hybrid for this dataset. The 3 Qwen3 dense branches blurred exact-match precision more than they added coverage; disabling lifts NDCG@20 by 15%. Re-enabling dense only makes sense behind a reranker that can re-prioritize.
- The dominant remaining bottleneck is structural, not parametric: 62% of GT turns have a **novel artist** (not in prior plays), and on that cohort Hit@100 is only 0.16 — the candidate isn't even in our top-100. Diversification + a CF (`cf_bpr`) branch would attack this; tuning the same knobs further won't.
- NDCG ranking headroom on the *current* retrieval pool is +0.137 (Hit@20 = 0.238 means 24% of GT is already in top-20; if a perfect reranker pushed them all to rank 1 the NDCG@20 would be 0.238 vs current 0.101). A cross-encoder reranker is the highest-leverage move for NDCG.
- Pivot intent is rare (2% of turns) and the LLM still mis-extracts contrastive mentions ("different from X" → puts X in `mentioned_entities` instead of `explicit_rejections`). Prompt fix is small but cache-invalidating; not worth the cost until other bigger levers land.

Linked reports:
- [`v0plus_compiler_devset.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_compiler_devset.md)

Next step:
- Per-artist diversity cap in top-K (small change, attacks same-artist crowding directly).
- Add `cf_bpr` as a track→track dense branch (it's already indexed in LanceDB, never wired into v0+). Best single bet for closing the novel-artist coverage gap.
- Cross-encoder reranker on top-100 (largest expected NDCG@20 impact; biggest implementation lift).

Status:
- Analyzed

## 2026-05-28 - v0+ image config post-bugfix rescore

Question:
After PR #66 metadata / resolver bugfixes, is `v0plus_compiler_image_devset` performing better, and should shallow devset rows suppress all cutoff metrics?

Run:
- `v0plus_compiler_image_devset` on Modal, predictions generated at `05133129b7e9556eba52cc89cf6cb4f48116f444`
- Rescored with relaxed evaluator semantics: `require_full_diagnostic_depth=false`; shallow rows count missing unretrieved tails as misses instead of nulling all cutoffs.

Results:
- NDCG@20 `0.1452`, Hit@20 `0.2989`, MRR `0.1062`
- Hit@100 `0.4450`, Hit@1000 `0.6261`
- 81 / 8000 rows were shallower than 1000 candidates; min pool depth was 0.

Takeaways:
- Headline top-20 quality is flat to slightly lower than the prior image ablation (`0.1452` vs `0.1461` NDCG@20), so the bugfixes are correctness wins rather than a headline metric lift.
- Deep coverage improved versus the prior image row (`Hit@1000 0.6261` vs `0.598`), while the config remains far ahead of BM25-only (`0.1452` vs `0.0984` NDCG@20).

Linked report:
- [`v0plus_compiler_image_devset.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_compiler_image_devset.md)

Status:
- Analyzed

## 2026-05-26 - v0+ compiler multimodal embedding ablation

Question:
Now that v0+'s LanceDB has all 6 track-side embedding columns properly indexed (fixed_size_list<float32>[dim]) and a UserEmbeddings catalog is available, which embedding signals — fused into the compiler's RRF pool alongside BM25 — actually lift NDCG@20 over the BM25-only baseline?

Runs (all on 1000-session devset, 4-shard Modal inference, identical extractor / resolver / fusion, varying only retrieval branches):
- `v0plus_compiler_devset` (BM25-only baseline)
- `v0plus_compiler_user_devset` (BM25 + user_cf_bpr — user-source centroid)
- `v0plus_compiler_cfbpr_devset` (BM25 + cf_bpr anchor-track centroid)
- `v0plus_compiler_audio_devset` (BM25 + audio_laion_clap anchor centroid)
- `v0plus_compiler_image_devset` (BM25 + image_siglip2 anchor centroid)
- `v0plus_compiler_audio_image_devset` (BM25 + audio + image)
- `v0plus_compiler_attributes_devset` (BM25 + attributes_qwen3 dense)
- `v0plus_compiler_lyrics_devset` (BM25 + lyrics_qwen3 dense)
- `v0plus_compiler_metadata_devset` (BM25 + metadata_qwen3 dense)
- `v0plus_compiler_all_devset` (BM25 + everything)

Headline (NDCG@20, ranked):
- `+ image_siglip2`: **`0.1461`** (`+48.4%` vs BM25 baseline `0.0984`) ← new canonical
- `+ all embeddings`: `0.1428` (+45.1%) ← best on Hit@1000 and novel-artist Hit@20
- `+ audio + image`: `0.1421` (+44.4%)
- `+ metadata_qwen3`: `0.1191` (+21.0%) ← only qwen3 dense that helps
- `+ audio_laion_clap`: `0.1082` (+10.0%)
- `+ cf_bpr (anchor)`: `0.1036` (+5.3%) — handicapped by 12.7% cold-cache extractor-fail rate
- `+ user_cf_bpr`: `0.0996` (+1.2%)
- baseline (BM25): `0.0984`
- `+ attributes_qwen3`: `0.0919` (-6.7%)
- `+ lyrics_qwen3`: `0.0897` (-8.9%)

Takeaways:
- `image_siglip2` is the single biggest lever. Hit@1 doubles (`+107%`), NDCG@20 lifts `+48%`, MRR lifts `+61%`. Cover-art embeddings cluster tracks by genre/era/visual aesthetic — a remarkably strong same-artist / same-era signal.
- All embeddings combined gives the best **novel-artist** Hit@20 (`0.120` vs baseline `0.093`, `+29%`) and the best Hit@1000 (`0.673`, `+18%`). It's the only config that meaningfully moves the novel-artist needle.
- `cf_bpr (anchor)` and `user_cf_bpr` underperform expectations. cf_bpr's behavioral neighborhood for an anchor track is dominated by *more tracks by the same artist* (BPR factorization concentrates within-artist co-listening), so it strengthens continuation but actively hurts novel-artist Hit@20 (-8%). user_cf_bpr's all-time taste prior is too coarse to compete with even BM25 on turn 1 (-16% turn-1 NDCG@20).
- Two qwen3 dense branches (attributes, lyrics) drag macro NDCG@20 down. Only `metadata_qwen3` helps (`+21%`) — the metadata text contains the same surface forms as the LLM's `turn_intent`, so it acts as a fuzzy semantic-BM25.
- Per-turn: image is the only config that fully flattens the turn 6-8 NDCG@20 decay that's been the v0+ pipeline's biggest depth-related failure mode.
- Empty-pool from extractor failure is rare in steady state — ~0.16% of turns once the LiteLLM cache is warm. The 12.7% spike in the cf_bpr run was a one-off (first run with the rewritten extractor prompt, fully-cold cache, DeepInfra rate-limited).
- The dominant remaining gap is **novel-artist coverage**: 64% of turns are novel-artist, baseline Hit@20 = `0.093`, best config = `0.120`. Every retrieval branch we have starts from an anchor centroid and is structurally biased toward continuation. No centroid-based modality alone (or in combination) brings novel-artist Hit@20 above `0.13`. Next lever is a cross-encoder reranker over top-200 — anchor-free, scores (intent_text, candidate_text) pairs directly.

Linked reports:
- [`v0plus_compiler_ablation_2026-05-26.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_compiler_ablation_2026-05-26.md) — canonical writeup with cohort + per-turn + gap analysis
- [`v0plus_compiler_cfbpr_devset.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_compiler_cfbpr_devset.md) — per-run cf_bpr report (root-cause-analysis of the cold-cache extractor-fail spike)

Next step:
- Ship `v0plus_compiler_image_devset` as the new canonical retrieval config (`NDCG@20 0.1461`).
- Try weighted RRF (image w=2.0 + audio w=1.0) — leverages image's top-of-list precision and audio's pool-coverage asymmetrically.
- Build a cross-encoder reranker over the top-200 candidate pool — only structural lever that can attack the novel-artist gap.
- Drop `attributes_qwen3` and `lyrics_qwen3` from future hybrid configs (both regress).

Status:
- Analyzed

## 2026-05-28 - v0+ text-side retrieval (Rounds 1-4) + failure taxonomy

Question:
Can anchor-free text-side retrieval (SigLIP-2 text → image_siglip2, LAION-CLAP music text → audio_laion_clap) lift the novel-artist cohort that image_centroid can't reach?

Configs (all 50-session slice unless noted):
- `v0plus_compiler_textside_devset` (R1: shared intent query, equal weights)
- `v0plus_compiler_textside_v2_devset` (R2: per-encoder queries sonic + visual) - full devset
- `v0plus_compiler_textside_v3_devset` / v3a / v3b (R3: sonic_nl + lyric, asymmetric, ablations)
- `v0plus_compiler_textside_v4_devset` (R4: 3xCLAP + lyric)

Headline:
- No textside config beats the canonical `v0plus_compiler_image_devset` on NDCG@20.
- R2 full devset: NDCG@20 -10% vs baseline; novel Hit@1000 +5%. Coverage gain real but modest, ranking loss real.
- R4 50-session: novel Hit@200 +35.5% vs baseline, novel Hit@1000 +19.1%. Strongest recall variant but not run on full devset.
- Architecture verified working (CLAP text->audio alignment lift +0.165 vs random pairings); the candidates rank too deep to translate to top-K wins without a reranker downstream.

What was built (worth keeping as infrastructure):
- Compiler refactor: per-branch `encoder_id` + `query_id` + encoder map + `branch_traces` diagnostic. Five new query templates (intent, sonic, sonic_nl, visual, sonic_nl_enriched, lyric). Back-compat preserved (38 tests pass).
- Modal `MultimodalTextEncoder` service (SigLIP-2 + CLAP music) - deployed.
- Per-branch GT-rank trace diagnostic - controlled via `CompilerConfig.branch_trace_topk`. Decoupled diagnostic from inference cost.

Diagnostic findings (the durable value, beyond any single config):
- Per-branch trace on R2 full devset shows BM25 is the novel-artist workhorse (Hit@1000 = 0.365); CLAP-text uniquely contributes ~9% of novel turns; SigLIP-text is mostly redundant; image_centroid is the continuation engine (median rank 10 on cont).
- Phase A bucketing of 4777 novel turns: A1 BM25 top-20 (7%), A2 BM25 deep (29%), A3 text-side hero (20%), A4 total miss (43%).
- Phase B query A/B (499 novel turns, CLAP only): natural-language query (`"A song with {tags} sound, similar to {artists}"`) +120% Hit@20 vs the Round-2 sonic template, recovers 14% of A4.
- A4 deep-dive: ~30% catalog tag noise, ~30% vocabulary mismatch, ~15-20% dataset noise (GT contradicts user intent), ~15% lyric/theme queries with no audio signal.
- Multi-dimensional Hit@1000 split (R4 slice): state↔GT artist overlap is the dominant predictor (0.97 with match vs 0.31 without); long-tail GT artist (0.37 Hit@1000); goal category B vague-recall (0.38); 0 tags extracted (0.55).
- Aggregate analysis of 3100 R2 full-devset failures: **46% have a GT-tag word the user literally said but the extractor failed to capture as a tag**. 35% are long-tail GT artists. ~15-20% are dataset noise (GT contradicts stated intent like rejected artists).

Takeaways:
- The textside direction does not beat baseline NDCG@20 on this catalog without a reranker. The encoders work and the pool genuinely grows, but the new candidates rank too deep for RRF to promote to top-K.
- The architectural ceiling for fusion-only changes is roughly the R4 slice numbers. Further gains need either (a) a reranker downstream, or (b) better state extraction.
- State extraction is the highest-leverage next lever. 46% of failures are extractor tag-extraction gaps - the extractor packs descriptive vocabulary into `turn_intent` as prose and doesn't emit it as discrete `mentioned_entities[type=tag]`.

Linked reports:
- [`v0plus_textside_2026-05-28.md`](/Users/npatta01/data/projects/music-conversational-music-recomender-2026/experiments/v0plus_textside_2026-05-28.md) - full writeup with diagnostics, all rounds, failure taxonomy, recommendations.

Next step (prioritized by leverage):
- Revised extractor prompt: force complete tag extraction, era-to-filter conversion, lyric-snippet flagging, sharper anti-anchor parsing. Single prompt change + LiteLLM cache flush. Attacks 46% of failures.
- Long-tail / popularity-balanced retrieval: cf-bpr (warm cache) or popularity prior on post-fusion ranking. Attacks 35%.
- Anchor-track audio centroid in CLAP space (untried): use accepted-track audio embedding as CLAP query, not text. Attacks A4-shaped failures.
- Reranker on top-K pool (still deferred but data points loudly here for the A2 bucket: 29% of novel turns, median BM25 rank 318).

Status:
- Analyzed
