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
