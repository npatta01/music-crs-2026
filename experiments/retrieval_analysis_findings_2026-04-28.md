# Retrieval Analysis Findings

Compared:

- `bm25_devset_retrieval_only_with_tag_list`
- `dense_qwen3_embedding_8b_devset`

Data source:

- `evaluator/exp/inference/devset/*.json`
- `evaluator/exp/ground_truth/devset.json`

## Aggregate Metrics

| Run | NDCG@20 | Hit@20 | Hit@1000 |
|---|---:|---:|---:|
| BM25 + tag list | 0.0970 | 0.2640 | 0.6311 |
| Dense Qwen 8B | 0.1025 | 0.2653 | 0.6934 |
| RRF hybrid (`k=60`) | 0.1072 | 0.2828 | 0.7210 |

## Complementarity at Top-1000

Total evaluated turns: `8000`

- Both hit: `4401` (`55.0%`)
- Both miss: `1805` (`22.6%`)
- Dense-only hit: `1146` (`14.3%`)
- BM25-only hit: `648` (`8.1%`)

Union hit count: `6195` (`77.4%`)

## Interpretation

The retrievers are meaningfully complementary.

- Dense is the stronger single retriever overall.
- BM25 still recovers `648` gold tracks in the top-1000 that dense misses entirely.
- Dense recovers `1146` that BM25 misses.
- The offline RRF fusion improves over both standalone runs:
  - `+0.0046` NDCG@20 over dense
  - `+0.0102` NDCG@20 over BM25
  - `+0.0276` Hit@1000 over dense
  - `+0.0899` Hit@1000 over BM25

This is strong evidence that a hybrid retriever or fusion stage is worth pursuing.

## Example Complementary Turns

BM25-only examples:

- `a510a742-18e9-4098-83a2-7e7f9a25aca7` turn `4` — BM25 rank `124`, dense miss
- `e17c1529-d45b-4eaf-a4dd-4e795d83c679` turn `5` — BM25 rank `422`, dense miss
- `1f1947c0-1c27-4520-9577-66af51c463f3` turn `3` — BM25 rank `13`, dense miss

Dense-only examples:

- `0979c6fc-c382-4c14-be3e-2a4711fcc532` turn `2` — dense rank `513`, BM25 miss
- `8741b1b4-cd87-42fc-a56d-483e7f66494c` turn `1` — dense rank `83`, BM25 miss
- `1f1947c0-1c27-4520-9577-66af51c463f3` turn `1` — dense rank `195`, BM25 miss
