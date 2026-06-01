# LanceDB Architecture

LanceDB is a CPU-only retrieval experiment for comparing native LanceDB FTS against the existing tag-list BM25 baselines:

- direct BM25: `configs/bm25_devset_retrieval_only_with_tag_list.yaml`
- Milvus BM25: `configs/milvus_bm25_with_tag_list_devset.yaml`
- LanceDB FTS: `configs/lancedb_fts_with_tag_list_devset.yaml`

The first LanceDB config is intentionally sparse/FTS-only at query time.
LanceDB also supports dense vector lookup over stored embedding columns. The
local index build stores precomputed track embeddings by default so the same DB
can support dense or later hybrid LanceDB experiments, but
`lancedb_fts_with_tag_list_devset` does not load a dense query encoder.

This path should stay a pure LanceDB FTS comparison. Do not add a local
candidate reranker to make it match direct `bm25s`; if top-1000 scores diverge,
compare candidate overlap first. A low `Hit@1000` means LanceDB and the baseline
are returning different candidate sets, not just differently ordered candidates.

The default config uses `fts_bm25s_compat`, which keeps the search inside
LanceDB but makes the text representation closer to the direct `bm25s` baseline:
item text is pre-tokenized with `bm25s.tokenize`, stored as whitespace-separated
tokens, and queried with structured LanceDB `MatchQuery` clauses whose boosts
preserve repeated query terms. This avoids LanceDB's native tokenizer/parser
differences without introducing a second-stage scorer.

The structured query path is intentional. A native LanceDB string query against
the tokenized field is simpler, but it does not preserve repeated query term
frequency the way direct `bm25s` does. On a fixed 80-query smoke slice, native
string/`MatchQuery` search against the tokenized field only reached about
`0.695 overlap@20` and `0.615 overlap@1000` versus the boosted structured query
path.

LanceDB FTS returns only matching rows, while direct `bm25s` returns `k` rows
even when the tail has zero score. To keep the same retrieval-depth contract,
short LanceDB result sets are padded from catalog order after all scored FTS
matches.

## Benchmark Summary

Full devset runs on 2026-05-15 used `lm_type=dummy`, `qu_type=passthrough`, and
`retrieval_topk=1000`.

| Run | NDCG@20 | Hit@20 | Hit@100 | Hit@1000 | MRR |
|---|---:|---:|---:|---:|---:|
| Direct BM25 tag-list | 0.0971 | 0.2642 | 0.4305 | 0.6310 | 0.0558 |
| LanceDB `fts_bm25s_compat` | 0.0962 | 0.2602 | 0.4249 | 0.6235 | 0.0557 |
| Milvus native BM25 | 0.0933 | 0.2514 | 0.4104 | 0.6048 | 0.0542 |

The LanceDB run preserved full retrieval depth:

| Metric | Value |
|---|---:|
| min_pool_depth | 1000 |
| max_pool_depth | 1000 |
| n_shallow_rows | 0 |

Candidate overlap between LanceDB and direct BM25:

| Cutoff | Mean overlap |
|---|---:|
| @20 | 0.9463 |
| @100 | 0.9511 |
| @1000 | 0.9582 |

See `experiments/lancedb_fts_with_tag_list_devset.md` for the full report.

## Build And Storage

Build the local DB from the track metadata dataset:

```bash
uv run python scripts/build_lancedb_index.py --out-dir cache/lancedb --drop-existing
```

For a notebook-driven operator flow, use
`notebooks/05_lancedb_indexing.ipynb`. The notebook delegates the actual build,
upload, and smoke-test steps to the checked-in Python entrypoints instead of
duplicating indexing logic in notebook cells.

This creates a LanceDB table named `music_track_catalog`, stores all precomputed
track embedding vector columns plus their `has_*` indicators, and creates FTS
indexes for:

- `bm25_compat_text`
- `bm25_compat_bm25s_tokens_text`
- `bm25_with_tag_list_text`
- `bm25_with_tag_list_bm25s_tokens_text`
- `track_name_text`
- `artist_name_text`
- `album_name_text`
- `release_date_text`
- `tag_list_text`

For a smaller sparse-only local artifact, opt out of embedding columns:

```bash
uv run python scripts/build_lancedb_index.py --out-dir cache/lancedb --drop-existing --metadata-only
```

For Modal, upload the local DB directory to the models volume:

```bash
uv run modal run modal/app.py::upload_lancedb_index --local-db-dir cache/lancedb --remote-dir lancedb --overwrite
uv run modal run modal/app.py::smoke_lancedb_query --query "dark atmospheric synthwave" --topk 3
```

The volume name is `music-crs-models`, mounted at `/root/models`; the remote DB path is `/root/models/lancedb`. Use `--overwrite` for rebuilds because Modal volume uploads do not replace existing LanceDB manifest files in place. The upload entrypoint removes only the target directory and rejects `remote_dir=/`.

## Query Paths

Local inference opens `./cache/lancedb` by default.

Modal inference sets `MCRS_LANCEDB_URI=/root/models/lancedb` and runs the CPU function path when the config has `device: cpu`.

Private Modal smoke queries use the Modal SDK, not a public HTTP endpoint:

```bash
uv run modal deploy modal/app.py
uv run python scripts/smoke_lancedb_modal_query.py --query "dark atmospheric synthwave" --topk 20
```

The Python client uses `modal.Cls.from_name(...)`, so access is controlled by
the normal Modal client credentials.

Dense vector retrieval uses the same table and a `dense_vector` search entry.
The query embedding must come from the same model family as the stored vector
field. Supported LanceDB `distance_type` values are `cosine`, `dot`, and `l2`;
retriever results are converted so higher scores always mean more similar.

```yaml
retrieval_config:
  searches:
    - name: "metadata_dense"
      kind: "dense_vector"
      vector_field: "metadata_qwen3_embedding_0_6b"
      distance_type: "cosine"
      topk: 1000
  fusion:
    method: "weighted_rrf"
```

For Modal, set `MCRS_EMBEDDING_MODEL` plus its provider credentials so
`ModalRetrievalService` can embed the query before calling LanceDB.

### Private Modal Retrieval Service

`ModalRetrievalService` is the efficient service-style path for repeated LanceDB
queries. It is a private Modal class, not a public HTTP endpoint. The class
mounts the `music-crs-models` volume, opens `/root/models/lancedb` once per warm
container, and exposes:

- `retrieve(query, topk)`
- `retrieve_batch(queries, topk)`
- `embed_batch(texts)` when an embedding client is configured

Both retrieval methods also accept an optional `retrieval_config`. When supplied,
the service merges it with the default LanceDB path/table settings and builds a
request-scoped retriever, which lets callers choose FTS or dense vector search
without redeploying Modal.

The service is configured with `min_containers=0`, so it scales to zero when
idle. `query_scaledown_window` controls how long a warm container can stay idle
before shutdown, and `query_max_containers` caps cost during bursts.

Use this path when local or external Python inference should call Modal-hosted
retrieval:

```bash
uv run modal deploy modal/app.py
uv run python scripts/smoke_lancedb_modal_query.py --query "dark atmospheric synthwave" --topk 20
```
