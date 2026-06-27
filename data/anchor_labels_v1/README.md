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

The data files are too large for the repo and live as **GitHub Release assets**
on the [`anchor-labels-v1.1`](../../releases/tag/anchor-labels-v1.1) release:

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
# the datasets
gh release download anchor-labels-v1.1 -p 'dev_labels_full.jsonl.gz'   && gunzip dev_labels_full.jsonl.gz
gh release download anchor-labels-v1.1 -p 'train_labels_full.jsonl.gz' && gunzip train_labels_full.jsonl.gz

# verify
gh release download anchor-labels-v1.1 -p '*.sha256'
sha256sum -c train_labels_full.jsonl.gz.sha256 dev_labels_full.jsonl.gz.sha256

# (optional) full audit/provenance bundles
gh release download anchor-labels-v1.1 -p '*_audit.tar.gz'
```

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
