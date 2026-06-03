# Qwen Embedding Field And Size Smoke

**Date:** 2026-06-03
**Scope:** 100-session devset smoke, 800 turns, pool depth 1000
**Branch:** `codex/vllm-qwen-catalog-rebuild`

## Question

Measure whether Qwen3 embedding size improves v0+ retrieval when metadata and
attributes are kept as separate item fields.

The comparison varied:

- embedding size: 0.6B, 4B, 8B
- Qwen field: metadata only, attributes only, metadata plus attributes

All rows kept the rest of the v0+ stack fixed: BM25, CLAP-text, centroid
branches, resolved-artist discography, and era/popularity.

## Embedding Inputs

Item side used raw catalog documents, with no item-side instruction:

- metadata item document: `music track, title:{track_name}, artist:{artists}, album:{albums}`
- attributes item document: `music attributes, tags :{tag_list}` plus tempo, key, and chord fields when present

Query side used a query instruction for Qwen text embeddings:

```text
Instruct: Given a music recommendation conversation, retrieve relevant track metadata passages that match the listener request and prior music preferences.
Query: {branch_query_text}
```

The branch query text stayed field-specific:

- metadata query: turn intent plus resolved positive artists, albums, and tracks; no explicit tag list
- attributes query: `music attributes, tags :{positive_tags}`

## Index Rebuild

The LanceDB catalog was rebuilt with per-item, single-text LiteLLM embedding
requests for generated 4B and 8B vectors. The successful rebuild replay used the
cache only:

| Metric | Value |
|---|---:|
| catalog rows | 47,071 |
| generated fields | 4 |
| cache hits | 188,284 |
| endpoint requests | 0 |

Generated fields:

- `metadata-qwen3_embedding_4b`
- `attributes-qwen3_embedding_4b`
- `metadata-qwen3_embedding_8b`
- `attributes-qwen3_embedding_8b`

The item document renderer uses raw metadata/attribute templates with minimal
fallback text, so every selected catalog item/model/document-kind pair receives
an embedding even when source fields are sparse.

The 0.6B item vectors used the shipped catalog embeddings.

## What Combined Means

The combined rows did not concatenate metadata and attributes into one document.
They included both as separate dense branches and fused them through the v0+
compiler:

```yaml
- vector_field: "metadata_qwen3_embedding_8b"
  query_id: "metadata"
- vector_field: "attributes_qwen3_embedding_8b"
  query_id: "attributes"
```

Runtime traces confirmed separate branches, for example:

```text
dense.default.metadata.metadata_qwen3_embedding_8b
dense.default.attributes.attributes_qwen3_embedding_8b
```

## Smoke Results

| Model | Qwen field(s) | NDCG@20 | Hit@20 | Hit@100 | Hit@1000 | MRR |
|---|---|---:|---:|---:|---:|---:|
| 0.6B | metadata | 0.1155 | 0.2663 | 0.4375 | 0.6800 | 0.0787 |
| 0.6B | attributes | 0.1002 | 0.2288 | 0.4137 | 0.6850 | 0.0699 |
| 0.6B | metadata + attributes | 0.1088 | 0.2500 | 0.4363 | 0.6887 | 0.0749 |
| 4B | metadata | 0.1153 | 0.2675 | 0.4325 | 0.7012 | 0.0778 |
| 4B | attributes | 0.0957 | 0.2225 | 0.3975 | 0.6937 | 0.0661 |
| 4B | metadata + attributes | 0.1062 | 0.2450 | 0.4325 | 0.7087 | 0.0732 |
| 8B | metadata | 0.1104 | 0.2587 | 0.4363 | 0.7137 | 0.0745 |
| 8B | attributes | 0.1022 | 0.2400 | 0.4213 | 0.6963 | 0.0693 |
| 8B | metadata + attributes | 0.1045 | 0.2462 | 0.4500 | 0.7200 | 0.0709 |

## Per-Turn Winners

Best NDCG@20 by turn:

| Turn | Winning row | NDCG@20 | Hit@20 | Hit@100 |
|---:|---|---:|---:|---:|
| 1 | 8B metadata | 0.1156 | 0.2300 | 0.3800 |
| 2 | 4B metadata + attributes | 0.1828 | 0.4000 | 0.5900 |
| 3 | 0.6B metadata | 0.1437 | 0.3200 | 0.5100 |
| 4 | 0.6B metadata | 0.1051 | 0.2600 | 0.4600 |
| 5 | 0.6B metadata | 0.1058 | 0.2300 | 0.3900 |
| 6 | 4B metadata | 0.1274 | 0.2600 | 0.4400 |
| 7 | 4B metadata | 0.0997 | 0.2500 | 0.4200 |
| 8 | 0.6B metadata | 0.0804 | 0.2300 | 0.3300 |

## Learnings

- Larger Qwen embeddings did not improve top-20 ranking in this smoke.
  The strongest top-rank row remained 0.6B metadata with NDCG@20 0.1155 and
  MRR 0.0787.
- 4B metadata was effectively tied with 0.6B metadata on NDCG@20, but did not
  produce a clear lift.
- 8B improved deep recall: metadata Hit@1000 rose from 0.6800 to 0.7137, and
  metadata plus attributes reached 0.7200. This did not translate into better
  NDCG@20 or MRR.
- Attributes alone were consistently weaker than metadata for top-20 ranking.
- Adding metadata and attributes as separate branches improved deep recall but
  hurt top-rank quality versus metadata-only.

## Decision

Do not promote 4B or 8B Qwen as the default based on this smoke. The larger
embeddings are useful recall candidates, but they need downstream fusion or
reranking work before they help the final top-20 recommendation quality.

Full devset was not run because the gated smoke did not show a top-20 or MRR
lift over the 0.6B metadata baseline.

The temporary bakeoff configs used to run this matrix were intentionally not
kept in the repository; the durable outcome is this report plus the reusable
indexing/cache support.
