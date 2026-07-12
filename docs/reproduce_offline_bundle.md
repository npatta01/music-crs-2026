# Reproducing devset / Blind-A / Blind-B from the offline bundle

The offline reproduction bundle ships the ignored artifacts needed to
reproduce the saved devset, Blind-A, and Blind-B results with **no paid
LLM, embedding, Modal, or Hugging Face calls**. It's hosted on Hugging Face:

**https://huggingface.co/datasets/Npatta01/music-crs-repro-2026**

There are two reproduction paths. Pick the one you need — most people only
need the first.

| Path | What it proves |
|---|---|
| **Frozen replay** | The submitted `prediction.json` bytes are exactly what shipped |
| **Live offline rerun** | The pipeline itself, run fresh, reproduces the same tracks/quality without any credentials |

Both paths run on `main`.

## Quickest path — run inference yourself

Two scripts do everything Path 2 below does by hand: check prerequisites,
install the environment, download and verify the bundle, then run
inference with zero credentials.

```bash
git clone --branch main https://github.com/npatta01/music-conversational-music-recomender-2026.git
cd music-conversational-music-recomender-2026

scripts/repro_setup.sh   # checks uv/hf are installed, sets up .venv, downloads
                          # + extracts + verifies the bundle from Hugging Face
scripts/repro_run.sh     # runs Blind-B end to end — no credentials, no Modal
```

`repro_run.sh` defaults to Blind-B. Other splits or configs:

```bash
scripts/repro_run.sh --eval_dataset blindset_A
scripts/repro_run.sh --eval_dataset devset
scripts/repro_run.sh --eval_dataset blindset_B --tid some_other_config
scripts/repro_run.sh --help
```

Output lands at `exp/inference/<split>/<tid>.json`, same as the manual
commands in Path 2 below. If you only need the frozen predictions (Path 1)
without re-running anything, or want to understand what each step is
actually doing, read on.

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
| `anchor_labels_v1.1/` | 67 MB | LLM-judged anchoring-bug relabeling data (train+dev) — unrelated to devset/Blind-A/B reproduction, kept here as a single source of truth |

`cache/embedding` and `cache/state_extraction` ship as single `zstd -19`
archives rather than as their 163,018 individual files — extraction
reproduces the originals byte-for-byte (`diff -rq`, zero differences).
**Do not re-split these into individual files on HF**: downloading them as
individual files triggers severe server-side rate limiting on HF's
per-file metadata-check endpoint, turning a seconds-long download into
hours.

## Path 1 — Frozen replay (byte-exact, works on `main`)

```bash
git clone --branch main https://github.com/npatta01/music-conversational-music-recomender-2026.git
cd music-conversational-music-recomender-2026

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

**Avoid `--include` glob patterns across the whole repo** (e.g. `--include
"cache/*"`) — they resolve the full remaining tree before filtering, which
is slow. Downloading named paths (folders or the two tarballs) directly, as
above, avoids that entirely.

### Why frozen replay, not live rerun, is canonical

Live ANN retrieval can reorder near-tied candidates across machines or
library builds. Confirmed empirically (network-fenced live reruns of the
*exact* pruned bundle): ~5-10% of sessions match exactly, ~45% keep the same
20-track set with reordering among near-ties, ~40% differ by 1-4 tracks right
at the retrieval-pool boundary. Response text can differ too when the #1
track itself changes — and occasionally, on Blind-A/B, that turn's
explanation comes back blank rather than just different: `cache/litellm-repro`
only has a cached explanation for whichever track was actually #1 in the
canonical run, so if reordering promotes a different track to #1, generating
its explanation needs a live (credential-requiring) call that a zero-credential
rerun can't make. `scripts/repro_run.sh` flags this after a run if it
happens — the recommended track IDs are unaffected either way. None of this
is a bug — it's inherent ANN nondeterminism — but it means only
`.repro/traces/` + `.repro/reference/` reproduce the exact submitted bytes.

## Path 2 — Live offline rerun

The frozen-prediction path above needs no code changes. Actually re-running
inference with zero credentials relies on two things in `mcrs/`:

- A portable embedding cache key (`mcrs/embeddings/litellm_client.py`) that
  doesn't bake in a resolved `api_base` URL, so a cache lookup never needs a
  live endpoint resolved at all.
- Lazy endpoint resolution, on by default: a vLLM endpoint is only resolved
  into a live Modal URL on a genuine cache miss, never just to check the
  cache. Set `MCRS_LAZY_VLLM_ENDPOINT=0` to force eager resolution instead.

```bash
# activate_repro_env.sh sets MCRS_CACHE_DIR / MCRS_EMBEDDING_CACHE_DIR /
# MCRS_LITELLM_CACHE_DIR / MCRS_REQUIRE_LITELLM_CACHE=1 / HF_HOME and blanks
# all 6 credential vars — source it first even if you skipped Path 1:
source .repro/scripts/activate_repro_env.sh

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

## Verifying the reported result

Getting a `prediction.json` is not the same as confirming it scores what was
reported. How to check that depends on the split:

- **Blind-A / Blind-B**: these are the actual blind evaluation sets — ground
  truth isn't shipped to participants, so there's no local scorer to run.
  The only verifiable claim is Path 1's: `verify_bundle.sh` checksums
  `prediction.json` against `.repro/CRITICAL_SHA256SUMS`, which is the exact
  file that was uploaded to CodaBench and scored there. A Path 2 live rerun
  reproduces comparable quality but not the same bytes or score (see
  ANN-nondeterminism above), so it can't independently confirm the reported
  number — only the frozen file can.
- **Devset**: ground truth *is* public (it's the challenge dataset's `test`
  split), so a devset `prediction.json` — frozen or freshly reproduced — can
  be scored locally with the evaluator (`evaluator/` git submodule; see
  [`docs/evaluation.md`](evaluation.md) for setup and
  `evaluate_devset.py`). Compare the result against
  [`leaderboard.md`](../leaderboard.md) for the currently reported numbers
  (not reproduced here since the leaderboard is a living document — check it
  directly rather than trusting a copy that could go stale).
