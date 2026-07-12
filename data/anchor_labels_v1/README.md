# Anchoring-fix training labels — v1.1

Clean, LLM-judged labels over the **train** and **dev** splits of
`talkpl-ai/TalkPlayData-Challenge-Dataset`, built to retrain the two-tower
retriever against the **anchoring bug** (returns the just-played artist when the
listener asked for a *different* one).

- **train** — 106,393 turns / 15,199 sessions
- **dev** (this project's `test` split) — 7,000 turns / 1,000 sessions

> **v1.1** supersedes v1: the conflict gate now arbitrates judge splits on
> *either axis* (not only the final label), and the Opus arbiter judges **blind
> to the synthetic reaction**. Net: 3,486 axis-split turns re-arbitrated, 1,591
> moved out of `artist_anchoring`. See **`DATASET_CARD.md` → Revision history**.

The data files are too large for the repo and live in the
[`Npatta01/music-crs-repro-2026`](https://huggingface.co/datasets/Npatta01/music-crs-repro-2026)
Hugging Face dataset, under `anchor_labels_v1.1/`:

| Asset | Size | Contents |
|---|---|---|
| `train_labels_full.jsonl.gz` | ~10 MB | Train deliverable — 106,393 labeled turns (one JSON object per line). |
| `dev_labels_full.jsonl.gz` | ~0.7 MB | Dev deliverable — 7,000 labeled turns. |
| `anchor_labels_v1_audit.tar.gz` | ~26 MB | Train provenance: per-batch `final_labels`, **Opus arbiter verdicts** (`arbiter.json` + `arb_*.json`), conflict sheets, judge records — recoverable without re-running Opus. |
| `dev_labels_audit.tar.gz` | ~1.2 MB | Dev provenance, same shape. |
| `*.sha256` | — | Checksum sidecar per asset. |

sha256 (uncompressed): train `64c82bc14208c76f…`, dev `cda599a7ec9df36f…`.

## Download

```bash
# from repo root — the full data payload (datasets + full audit/provenance
# bundles + checksums; anchor_labels_v1.1/'s docs and html reports are
# skipped since they're already tracked in this repo, under data/anchor_labels_v1/)
hf download Npatta01/music-crs-repro-2026 --repo-type dataset --local-dir . \
  --include "anchor_labels_v1.1/*.gz" --include "anchor_labels_v1.1/*.sha256"

# the HF dataset ships this folder as anchor_labels_v1.1/ — move it into
# this project's data/anchor_labels_v1/, alongside DATASET_CARD.md and
# REPRODUCE.md, which expect the data files next to them:
mv anchor_labels_v1.1/* data/anchor_labels_v1/ && rmdir anchor_labels_v1.1

# verify (before decompressing — the checksums are over the .gz files)
sha256sum -c data/anchor_labels_v1/train_labels_full.jsonl.gz.sha256 \
              data/anchor_labels_v1/dev_labels_full.jsonl.gz.sha256

# decompress
gunzip data/anchor_labels_v1/dev_labels_full.jsonl.gz data/anchor_labels_v1/train_labels_full.jsonl.gz
```

`anchor_labels_v1_audit.tar.gz` / `dev_labels_audit.tar.gz` (already downloaded
above) are the only optional piece — per-batch judge records and Opus arbiter
verdicts, useful for auditing individual labels but not needed to use the
datasets themselves.

## What's in this folder

| File | What |
|---|---|
| **`DATASET_CARD.md`** | Schema, labeling method, composition rules, full distribution. |
| **`REPRODUCE.md`** | Step-by-step to rebuild the labels from scratch on a fresh machine (prereqs, exact commands, the arbiter with/without Claude Code). |
| **`reports/train.html`** | Visual walkthrough of the full train result (open in a browser). |
| **`reports/dev.html`** | Visual walkthrough of the dev result. |
| **`reports/flow.html`** | Plain-English explainer of how the labeling works (for someone with no context). |

Pipeline scripts (committed): `scripts/rerank/anchor_labels/build_anchor_universe.py`,
`convo_context.py`, `batch_sheet.py`, `judge_anchor_content.py`,
`compose_labels.py`, `run_arbiter.py`; arbiter subagent at
`.claude/agents/anchor-arbiter.md`. See **`REPRODUCE.md`** to run them.

## Headline

POSITIVE 35,191 (33.1%) · NEGATIVE 61,063 (57.4%) · DROP 4,007 · HOLD 6,132.
**artist_anchoring negatives = 18,222**, of which **5,880 carried the
synthetic reaction `MOVES`** — the poisoned positives this dataset rescues
(the raw label said the listener "liked" the anchored artist right after asking
for a different one).
