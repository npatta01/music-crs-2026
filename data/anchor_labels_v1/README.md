# Anchoring-fix training labels — v1

Clean, LLM-judged labels over the **train** and **dev** splits of
`talkpl-ai/TalkPlayData-Challenge-Dataset`, built to retrain the two-tower
retriever against the **anchoring bug** (returns the just-played artist when the
listener asked for a *different* one).

- **train** — 106,393 turns / 15,199 sessions
- **dev** (this project's `test` split) — 7,000 turns / 1,000 sessions

The data files are too large for the repo and live as **GitHub Release assets**
on the [`anchor-labels-v1`](../../releases/tag/anchor-labels-v1) release:

| Asset | Size | Contents |
|---|---|---|
| `train_labels_full.jsonl.gz` | ~10 MB | Train deliverable — 106,393 labeled turns (one JSON object per line). |
| `dev_labels_full.jsonl.gz` | ~0.7 MB | Dev deliverable — 7,000 labeled turns. |
| `anchor_labels_v1_audit.tar.gz` | ~26 MB | Train provenance: per-batch `final_labels`, **Opus arbiter verdicts** (`arbiter.json` + `arb_*.json`), conflict sheets, judge records — recoverable without re-running Opus. |
| `dev_labels_audit.tar.gz` | ~1.2 MB | Dev provenance, same shape. |
| `*.sha256` | — | Checksum sidecar per asset. |

sha256 (uncompressed): train `aefb058d8f99cf55…`, dev `227986a813f82b50…`.

## Download

```bash
# the datasets
gh release download anchor-labels-v1 -p 'dev_labels_full.jsonl.gz'   && gunzip dev_labels_full.jsonl.gz
gh release download anchor-labels-v1 -p 'train_labels_full.jsonl.gz' && gunzip train_labels_full.jsonl.gz

# verify
gh release download anchor-labels-v1 -p '*.sha256'
sha256sum -c train_labels_full.jsonl.gz.sha256 dev_labels_full.jsonl.gz.sha256

# (optional) full audit/provenance bundles
gh release download anchor-labels-v1 -p '*_audit.tar.gz'
```

## What's here

- **`DATASET_CARD.md`** — schema, labeling method (two cheap judges →
  Opus arbiter on disagreements), label composition rules, full distribution,
  and the two-tower training recipe.

See the card for everything else. The pipeline scripts are under
`scripts/rerank/` (`build_anchor_universe.py`, `convo_context.py`,
`judge_anchor_content.py`, `compose_labels.py`, `run_arbiter.py`) and the
arbiter subagent at `.claude/agents/anchor-arbiter.md`.

## Headline

POSITIVE 34,938 (32.8%) · NEGATIVE 61,784 (58.1%) · DROP 3,922 · HOLD 5,749.
**artist_anchoring negatives = 19,813**, of which **6,234 carried the
synthetic reaction `MOVES`** — the poisoned positives this dataset rescues
(the raw label said the listener "liked" the anchored artist right after asking
for a different one).
