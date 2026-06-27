# Anchoring-fix training labels — v1

Clean, LLM-judged labels over the **train** split of
`talkpl-ai/TalkPlayData-Challenge-Dataset` (106,393 turns / 15,199 sessions),
built to retrain the two-tower retriever against the **anchoring bug** (returns
the just-played artist when the listener asked for a *different* one).

The data files are too large for the repo and live as **GitHub Release assets**
on the [`anchor-labels-v1`](../../releases/tag/anchor-labels-v1) release:

| Asset | Size | Contents |
|---|---|---|
| `train_labels_full.jsonl.gz` | ~10 MB | The deliverable — all 106,393 labeled turns (one JSON object per line). |
| `anchor_labels_v1_audit.tar.gz` | ~26 MB | Per-batch `final_labels`, the **Opus arbiter verdicts** (`arbiter.json` + `arb_*.json`), conflict sheets, and both cheap-judge records — the full provenance, recoverable without re-running Opus. |

`train_labels_full.jsonl` sha256 prefix: `aefb058d8f99cf55`.

## Download

```bash
# the dataset
gh release download anchor-labels-v1 -p 'train_labels_full.jsonl.gz'
gunzip train_labels_full.jsonl.gz

# (optional) the full audit/provenance bundle
gh release download anchor-labels-v1 -p 'anchor_labels_v1_audit.tar.gz'
tar xzf anchor_labels_v1_audit.tar.gz
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
