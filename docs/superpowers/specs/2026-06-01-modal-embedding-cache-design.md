# Modal GPU Embedding Cache — Design

**Date:** 2026-06-01
**Status:** Approved design, pending implementation plan
**Goal:** Speed up Modal eval throughput by persistently caching text→vector results for every GPU-native embedder, so repeated query/template text is encoded at most once per run and never re-encoded across runs.

## Problem

Catalog vectors are already precomputed in LanceDB. The remaining hot path is **query-time text encoding** on Modal GPUs:

- `Qwen3Encoder` (`modal/app.py`) — Qwen3-Embedding-0.6B, metadata/attributes/lyrics/query text.
- `MultimodalTextEncoder` (`modal/app.py`) — SigLIP-2 text (768d, image space) + LAION-CLAP music text (512d, audio space).

Today the only dedup is an **in-turn** cache in `compiler_v0plus.py` keyed by `(encoder_id, query_id)`, which dies at the end of each turn. The same text on the next turn — or the next run — re-encodes from scratch on the GPU. Across a devset pass, templates and common phrases recur constantly, and iterative re-runs re-pay the full encode cost every time.

## Goals / Non-goals

**Goals**
- Persistent, cross-run cache keyed by exact text + model identity.
- Covers **all** leaf GPU embedders on Modal (Qwen3, SigLIP-2, CLAP), via one reusable wrapper.
- No change to returned vectors — same bytes, just cached.
- Simple kill-switch and a clear invalidation lever.

**Non-goals**
- Within-run cross-container live sharing (Modal Volume limitation, accepted — see Consistency).
- Caching the local (Mac/CPU) encode path. (Wrapper is reusable there later, but out of scope.)
- Touching the existing LiteLLM API cache. It stays independent.

## Architecture

Three small, independently testable pieces in a new module `mcrs/embeddings/embedding_cache.py`. **No dependency on `mcrs/litellm_cache.py`.**

### 1. `KeyValueStore` protocol
```
get(key: str) -> list[float] | None
set(key: str, vec: list[float]) -> None
```
One interface so the backend is swappable (disk-on-Volume now; `modal.Dict` later) without touching cache logic.

### 2. `DiskVectorCache` (implements `KeyValueStore`)
Self-contained on-disk store. Purpose-built (not adapted from litellm):
- Sharded layout `dir/ab/cd/<key>.json` to avoid huge flat directories.
- Value = JSON list of floats.
- Writes are **atomic**: write to a temp file in the same directory, then `os.replace()` to the final path. A reader never sees a partial file.
- Read miss / decode error / missing file → returns `None` (treated as cache miss, never raises into the encode path).
- Key validation: non-empty string, no path separator, no null byte (keys are sha256 hex, so always valid).

### 3. `CachedTextEmbedder`
Generic wrapper. Constructor: `(inner, store, namespace, enabled=True)` where `inner` is anything with `embed_batch(texts) -> list[list[float]]`.

`embed_batch(texts)`:
1. If `enabled` is False or `texts` empty → delegate straight to `inner` (zero behavior change).
2. Dedup `texts` to unique values (same text twice in one call → one encode).
3. For each unique text, compute key and `store.get`; partition into hits / misses.
4. `inner.embed_batch(misses)` — GPU encodes **only** the misses, in one batch.
5. `store.set` each miss result.
6. Reassemble output aligned to the **original** input order, fanning deduped vectors back to every position (including duplicates).

This class is Modal-free and unit-testable with a fake encoder + temp dir.

## Cache key & invalidation

Key = `sha256(f"{namespace}\x00{text}".encode("utf-8")).hexdigest()`.

`namespace` pins model identity **and anything that changes the output vector**:
- Qwen3 → `qwen3:Qwen3-Embedding-0.6B:dtype=<bf16|fp16|fp32>` (dtype affects vectors).
- SigLIP-2 → `siglip2:google/siglip2-base-patch16-224`.
- CLAP → `clap:music_audioset_epoch_15_esc_90.14`.

Different vector spaces (512d vs 768d) can never collide because the namespace differs. **Invalidation lever:** bump the namespace string (old files go cold) or wipe the volume (`modal volume rm <name>`) to reclaim space.

## Modal wiring

**New dedicated Volume v2** (config-driven, mirroring existing volume constants which come from `modal/config.yaml` → `_cfg.volumes` / `_cfg.container`):
- `modal/config.yaml`: add `volumes.embedding_cache` (e.g. `music-crs-embedding-cache`) and `container.embedding_cache_dir` (e.g. `/cache/embeddings`).
- `modal/app.py`: `embedding_cache_vol = modal.Volume.from_name(EMBEDDING_CACHE_VOLUME, create_if_missing=True, version=2)`.

**One shared volume, mounted on both encoder classes.** Files are namespaced + sha256-hashed, so the two classes write disjoint file paths and never collide; a shared volume is safe.

- `Qwen3Encoder` `@app.cls(volumes=...)`: add `EMBEDDING_CACHE_DIR: embedding_cache_vol` to its mount dict.
- `MultimodalTextEncoder` `@app.cls(volumes=...)`: add the same mount.

In each class's `@modal.enter() setup()` (~3 lines):
```
store = DiskVectorCache(EMBEDDING_CACHE_DIR)
enabled = os.environ.get("EMBEDDING_CACHE_ENABLED", "1") != "0"
self.client = CachedTextEmbedder(self.client, store, "qwen3:...:dtype=...", enabled)
# multimodal: wrap self.siglip and self.clap with their namespaces
```
The `@modal.method()` bodies (`embed_batch`, `embed_siglip_text`, `embed_clap_text`) are unchanged — they call `.embed_batch(...)` on what is now a cached wrapper.

Caching is applied at the **leaf** GPU encoders only (where `model.forward` runs), not at delegating layers (e.g. the retrieval-service class whose `embed_batch` forwards to a configured encoder). This captures all callers and avoids double-caching.

### Consistency (the one accepted limitation)
- **Durability / cross-run:** rely on Volume v2 background autocommit; a fresh container sees prior runs' entries at mount time. Add a `@modal.exit()` `commit()` as a belt-and-suspenders flush so a run's final writes survive scaledown.
- **Within-run cross-container:** **not** shared live. With up to N concurrent containers, container B won't see container A's just-written file until A commits and B reloads. We do **not** add periodic `reload()`. Consequence: within a single run the cache is effectively per-container; full cross-container benefit shows on re-runs. This is the deliberate trade for using a Volume (browsable files, simple model) over `modal.Dict`. Swapping the store to `modal.Dict` later would recover live sharing without touching `CachedTextEmbedder`.

## Kill-switch

`EMBEDDING_CACHE_ENABLED=0` (env) disables caching for all wrapped encoders → plain pass-through encode. Default enabled.

## Testing

Unit tests (no Modal) for `CachedTextEmbedder` + `DiskVectorCache` against a temp dir and a fake encoder that counts calls and returns deterministic vectors:
- Miss then hit: second call for same text does not invoke the inner encoder.
- Partial batch: mixed hits/misses encode only the misses, output order preserved.
- Duplicate text within one call: encoded once, fanned to all positions.
- Disabled mode: pure pass-through, store untouched.
- Corrupt/missing cache file: treated as miss, no raise.
- Atomic write: final file is complete JSON (no partial-read path).

## Files

- **New:** `mcrs/embeddings/embedding_cache.py` (`KeyValueStore`, `DiskVectorCache`, `CachedTextEmbedder`).
- **New:** `tests/.../test_embedding_cache.py`.
- **Edit:** `modal/config.yaml` (volume + dir entries).
- **Edit:** `modal/app.py` (volume constant + object, mounts on both encoder classes, wrapping in both `setup()`s, `@modal.exit()` commit).

## Out of scope / future

- Client-side cache to also skip the `.remote()` round-trip.
- `modal.Dict` backend for live within-run cross-container sharing.
- Reusing the wrapper on the local CPU/MPS encode path.
