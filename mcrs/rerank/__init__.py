"""LambdaMART reranker over v0+ branch-pool unions (GH #93).

Recall-only retrieval feeds the deduped union of all branch pools into a LightGBM
LambdaMART model that owns the final ordering, replacing weighted RRF. See
``docs/superpowers/specs/2026-06-02-lambdamart-reranker-design.md`` (mirrored on issue #93).
"""
