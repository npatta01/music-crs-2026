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
