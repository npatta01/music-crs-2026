# Embedding Bake-Off — artifacts

Raw result JSONs for the Qwen3-Embedding bake-off (encoder size × tags template × query mode, subset pool).

**Read the writeup:** [`../../embedding_bakeoff_qwen3_subset.md`](../../embedding_bakeoff_qwen3_subset.md) — setup, seed-averaged tables, and the verdict.

## Artifacts

- [`artifacts/fuller_seed0.json`](artifacts/fuller_seed0.json) — fuller run, 150 sessions / pool 8000 / seed 0 (headline).
- [`artifacts/fuller_seed1.json`](artifacts/fuller_seed1.json) — same, seed 1 (replication).
- [`artifacts/smoke_seed0.json`](artifacts/smoke_seed0.json) — 10-session / pool-2000 smoke (path check).

Regenerate with `modal run modal/embedding_bakeoff.py ...` (see [`modal/EMBEDDING_BAKEOFF_HANDOFF.md`](../../../modal/EMBEDDING_BAKEOFF_HANDOFF.md)). Note: `modal/embedding_bakeoff.py` writes to the gitignored `exp/analysis/embedding_bakeoff/`; these copies are the committed record.
