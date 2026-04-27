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
