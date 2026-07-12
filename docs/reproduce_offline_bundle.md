# Reproducing devset / Blind-A / Blind-B from the offline bundle

The `f519a83` offline reproduction bundle ships the ignored artifacts needed
to reproduce the saved devset, Blind-A, and Blind-B results with **no paid
LLM, embedding, Modal, or Hugging Face calls**. It's hosted on Hugging Face:

**https://huggingface.co/datasets/Npatta01/music-crs-repro-2026**

There are two reproduction paths. Pick the one you need — most people only
need the first.

| Path | What it proves |
|---|---|
| **Frozen replay** | The submitted `prediction.json` bytes are exactly what shipped |
| **Live offline rerun** | The pipeline itself, run fresh, reproduces the same tracks/quality without any credentials |

Both paths run on `main`.

## What's in the bundle

Folder layout mirrors the repo's own relative paths, so downloading into the
repo root drops everything in the right place directly — **except the two
components with tens of thousands of tiny files, which ship as a single
`.tar.zst` each and need one extract step** (see below). Every other folder
downloads directly into place with no extraction needed.

| Path | Size | What |
|---|---:|---|
| `cache/lancedb/` | 4.3 GB | Track catalog (47,071 tracks), compacted, pruned to columns real code reads |
| `cache/embedding.tar.zst` | 384 MB | Query embedding cache, tarred — exact verified minimal set for devset+Blind-A+Blind-B (33,257 files, 2.1 GB extracted) |
| `cache/state_extraction.tar.zst` | 33 MB | File-per-turn extracted state, tarred — trainset (15,199 sessions), devset (1,000), Blind-A/B (80 each) (129,761 files, 996 MB extracted) |
| `exp/analysis/rerank/` | 1.7 GB | q06/msg reranker feature memos (frozen; checksummed) |
| `.repro/traces/` | 4.8 GB | Frozen retrieval traces — the canonical byte-exact reproduction boundary |
| `.repro/hf_home/` | 426 MB | Cached HF dataset snapshots (offline `datasets.load_dataset`) |
| `cache/tag_embedding_index/` | 69 MB | Tag vocabulary vectors |
| `cache/litellm-repro/` | 18 MB | Frozen LLM response cache (Blind-B explanation generation) |
| `.repro/reference/`, `.repro/submissions/`, `.repro/scripts/` | 8 MB | Frozen predictions, original submitted ZIPs, install/verify/rebuild scripts |
| `anchor_labels_v1.1/` | 67 MB | LLM-judged anchoring-bug relabeling data (train+dev), migrated from the now-retired `anchor-labels-v1.1` GitHub release — unrelated to devset/Blind-A/B reproduction, kept here for single-source-of-truth |

**Why two components are tarred and the rest aren't:** `cache/embedding` and
`cache/state_extraction` are file-per-cache-key/file-per-turn caches — great
for the *runtime* (read one key at a time), terrible for *distribution*
(163,018 files combined). Shipping them as individual files on HF triggers
server-side rate limiting on the per-file metadata-check endpoint badly
enough that a full download can take hours instead of seconds. Packed as
single `zstd -19` archives, the same content downloads in under 15 seconds
combined and verifies byte-for-byte identical to the unpacked originals
(`diff -rq`, zero differences across all 163,018 files). **Do not re-split
these into individual files on HF** — that's what caused the problem.
`state-extraction-cache-v1` and `deepseek-train-state-v1` (the GitHub
releases that used to separately ship trainset's raw and materialized state)
are retired — this bundle's `cache/state_extraction.tar.zst` is the single
source of truth now, verified as a complete, faithful materialization
(121,592/121,592 rows matched, 0 missing, 0 mismatched).

## Path 1 — Frozen replay (byte-exact, works on `main`)

```bash
git clone --branch main https://github.com/npatta01/music-conversational-music-recomender-2026.git
cd music-conversational-music-recomender-2026
git switch main && git pull --ff-only
git merge-base --is-ancestor f519a83b0cb29ae60622116acc69b111aa20bc78 HEAD

hf download Npatta01/music-crs-repro-2026 --repo-type dataset --local-dir .

# cache/embedding and cache/state_extraction ship as tarballs (see above) —
# extract them into place, then the downloaded .tar.zst can be deleted:
tar --use-compress-program=unzstd -xf cache/embedding.tar.zst
tar --use-compress-program=unzstd -xf cache/state_extraction.tar.zst

# hf download doesn't preserve the executable bit — restore it once:
chmod +x .repro/scripts/*.sh

source .repro/scripts/activate_repro_env.sh
.repro/scripts/verify_bundle.sh
.repro/scripts/rebuild_submissions.sh
```

`verify_bundle.sh` checks 11 checksummed artifacts against
`.repro/CRITICAL_SHA256SUMS`. `rebuild_submissions.sh` validates and installs
the frozen prediction JSONs, then creates:

- `submission/reproduced_v10_lgbm_A.zip`
- `submission/reproduced_v10_lgbm_B_v1.zip`

The regenerated ZIP container bytes can vary with local `zip` version/
timestamp; the `prediction.json` bytes inside are byte-identical to what was
submitted (verified against `.repro/CRITICAL_SHA256SUMS`).

Only need one piece? Download just that folder (or tarball):

```bash
hf download Npatta01/music-crs-repro-2026 --repo-type dataset --local-dir . \
  --include "cache/embedding.tar.zst" --include "cache/lancedb/*" --include ".repro/*"
tar --use-compress-program=unzstd -xf cache/embedding.tar.zst
```

**Avoid `--include` glob patterns across the whole repo** (e.g. don't try to
list-and-filter everything in one call) — with the old many-small-file
layout this triggered severe HF-side rate limiting; even after tarring the
two big offenders, a wildcard `--include "cache/*"` still has to resolve the
full remaining tree first. Downloading named paths (folders or the two
tarballs) directly, as above, avoids that entirely.

### Why frozen replay, not live rerun, is canonical

Live ANN retrieval can reorder near-tied candidates across machines or
library builds. Confirmed empirically (network-fenced live reruns of the
*exact* pruned bundle): ~5-10% of sessions match exactly, ~45% keep the same
20-track set with reordering among near-ties, ~40% differ by 1-4 tracks right
at the retrieval-pool boundary. Response text can differ too when the #1
track itself changes. None of this is a bug — it's inherent ANN
nondeterminism — but it means only `.repro/traces/` + `.repro/reference/`
reproduce the exact submitted bytes.

## Path 2 — Live offline rerun

The frozen-prediction path above needs no code changes. Actually re-running
inference with zero credentials relies on two things in `mcrs/`:

- A portable embedding cache key (`mcrs/embeddings/litellm_client.py`) that
  doesn't bake in a resolved `api_base` URL, so a cache lookup never needs a
  live endpoint resolved at all.
- Lazy endpoint resolution, opt-in via `MCRS_LAZY_VLLM_ENDPOINT=1` (off by
  default — a run without this flag set eagerly resolves a live Modal URL
  before ever checking cache, so it needs Modal auth even on a pure cache
  hit).

```bash
# activate_repro_env.sh sets MCRS_CACHE_DIR / MCRS_EMBEDDING_CACHE_DIR /
# MCRS_LITELLM_CACHE_DIR / MCRS_REQUIRE_LITELLM_CACHE=1 / HF_HOME and blanks
# all 6 credential vars — source it first even if you skipped Path 1:
source .repro/scripts/activate_repro_env.sh

MCRS_LAZY_VLLM_ENDPOINT=1 \
python run_inference_blindset.py --tid state_ranker_v10_lgbm_blindset_A \
  --eval_dataset blindset_A --batch_size 8 --require_litellm_cache

# same pattern for blindset_B, and for devset via run_inference_devset.py
```

**Verified end-to-end**: Blind-A, Blind-B (all 80/80 sessions each), and
devset (all 1,000 sessions) run to completion with zero errors under a hard
network fence (`systemd-run -p 'RestrictAddressFamilies=AF_UNIX AF_NETLINK'`
— Modal isn't just unauthenticated, it's *unreachable*) and every credential
blanked. `cache/embedding`'s keys cover the exact set each real,
network-fenced run actually touches (33,257 keys, zero slack, zero gaps),
which is what makes this possible without Modal having ever needed to see
these three splits' traffic again.

If you point this at an *older* copy of `cache/embedding` (e.g. one warmed
before the portable cache key landed), its entries are keyed the old way —
including the resolved `api_base` URL — and won't be found by the new
namespace. That's a one-time re-key, not a re-embed: for every text the old
key already has an entry, copy it to the new key (no live call), re-deriving
the mapping from `mcrs/embeddings/litellm_client.py::cache_namespace_for_client`'s
old vs. new payload shape. The bundle above already ships fully re-keyed, so
this only matters if you're merging in your own older cache.
