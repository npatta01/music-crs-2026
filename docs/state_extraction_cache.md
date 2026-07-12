# State Extraction Cache

State extraction is cache-first when a config enables:

```yaml
qu_kwargs:
  extractor:
    state_cache:
      enabled: true
      mode: file_per_turn
      dir: cache/state_extraction/<split>
```

Lookup precedence is:

1. `turn_<n>_override.json`
2. `turn_<n>.json`
3. LiteLLM cache/network extraction

Override files are for manual corrections only. Create one when important
conversation information is missing or the extracted state would steer retrieval
the wrong way. Put it beside the raw file:

```text
cache/state_extraction/<split>/<session_id>/turn_<turn_number>.json
cache/state_extraction/<split>/<session_id>/turn_<turn_number>_override.json
```

## Standard Distribution

Generated state files are distributed artifacts, not repo files. The
canonical copy — trainset, devset, blindset_A, blindset_B — ships as
`cache/state_extraction.tar.zst` in the
[`Npatta01/music-crs-repro-2026`](https://huggingface.co/datasets/Npatta01/music-crs-repro-2026)
Hugging Face dataset (see [`docs/reproduce_offline_bundle.md`](reproduce_offline_bundle.md)
for the full offline reproduction bundle this is part of). It unpacks into
repo root as:

```text
cache/state_extraction/blindset_A/...
cache/state_extraction/blindset_B/...
cache/state_extraction/devset/...
cache/state_extraction/trainset/...
cache/state_extraction/MANIFEST.json
cache/state_extraction/SHA256SUMS
cache/state_extraction/RELEASE_NOTES.md
```

Build a fresh archive from the shared cache-owner checkout:

```bash
uv run python scripts/package_state_cache.py \
  --version state_extraction_cache_v1_2026-06-28
```

The archive is written to:

```text
cache/releases/state_extraction_cache_v1_2026-06-28.tar.zst
```

Publish it to the HF dataset, for example:

```bash
hf upload Npatta01/music-crs-repro-2026 \
  cache/releases/state_extraction_cache_v1_2026-06-28.tar.zst \
  cache/state_extraction.tar.zst --repo-type dataset
```

## Install / Verify

From repo root:

```bash
hf download Npatta01/music-crs-repro-2026 --repo-type dataset --local-dir . \
  --include "cache/state_extraction.tar.zst"

tar --use-compress-program=unzstd -xf cache/state_extraction.tar.zst
sha256sum -c cache/state_extraction/SHA256SUMS
```

Then link shared caches in any worktree:

```bash
git config --global mcrs.sharedRoot /path/to/music-crs-cache-owner
uv run python scripts/setup_worktree_cache.py
```

## Materialization Rules

Blind sets only need the final turn per session:

```bash
uv run python scripts/extract_state.py --tid state_ranker_v10_lgbm_blindset_A --turn-scope final --output-dir cache/state_extraction/blindset_A --skip-existing
uv run python scripts/extract_state.py --tid state_ranker_v10_lgbm_blindset_B --turn-scope final --output-dir cache/state_extraction/blindset_B --skip-existing
```

Devset uses all turns:

```bash
uv run python scripts/extract_state.py --tid state_ranker_v10_lgbm_devset --turn-scope all --output-dir cache/state_extraction/devset --skip-existing
```

Trainset is materialized from the existing extracted-state artifact:

```text
exp/state_extraction/deepseek_train_all.jsonl
```

Do not store these generated raw files under `exp/`, and do not commit them to
Git. Keep the source cache in the shared `cache/` tree and distribute it through
the release asset.
