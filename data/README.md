# data/

Small, **committed** reference data that is expensive to regenerate — kept in git
(not the gitignored `exp/` cache tree) so clones are reproducible.

| file | size | what | regenerate |
|---|---|---|---|
| `artist_knownfor.json` | ~1.5M | LLM-generated "known for" line per artist (8983 artists), keyed by artist name | `python scripts/rerank/build_doc_corpus.py --workers 24` (re-uses this cache; only fills missing artists) |

Derived artifacts (`exp/analysis/retrieval_exploration/doc_corpus.jsonl`, the b1
`b1_vstructpt_4b` LanceDB vectors) are built from this + the catalog with **no LLM
calls** and stay gitignored. See [docs/architectures/biencoder.md](../docs/architectures/biencoder.md).
