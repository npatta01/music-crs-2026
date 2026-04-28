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
