# Cross-encoder exploration — committed result artifacts

Small result files backing [`../cross_encoder_exploration.md`](../cross_encoder_exploration.md).
Enough to **verify and extend the findings without a GPU**. (Large/intermediate artifacts — the
4.7 GB devset trace, the v1 superseded run — stay under the gitignored `exp/`; the report documents
how to regenerate them.)

| file | size | from | what it is |
|---|---|---|---|
| `xenc_phase3_4b_v2_rawscores.jsonl` | 612K | E3 `probe_xenc_zeroshot.py` | **The reproducer.** One row/turn: `{group (miss/ctrl), key:[sid,tn], before (lgbm rank), gt_idx (GT index in the lgbm top-100, −1 if absent), lane, reachable, novel, sc:[~100 P(yes)]}`. Re-derives every reranking mode/threshold offline. |
| `xenc_mining_results.json` | 516K | E1 `probe_xenc_mining.py` | Per-turn GT / mined-neg / DOES_NOT / random `P(yes)` (labeler kill-switch) + summary AUCs. |
| `xenc_softpos_judged.json` | 44K | E1 `judge_softpos.py` | Independent DeepSeek judge ratings of CE-flagged candidates (validity gate + soft-pos precision). |
| `xenc_ablation_results.json` | 4K | E2 `probe_xenc_ablation.py` | Model/prompt/context ablation summary (0.6B vs 4B, base/richquery/all/placebo). |
| `xenc_ablation_8b.json` | 4K | E2 | 8B/base arm (the row is tagged "4B/base" — see report note; it is 8B). |

## Reproduce the headline (E3) net table — no GPU, seconds

```bash
python scripts/rerank/sweep_phase3_offline.py \
    docs/research/cross_encoder_artifacts/xenc_phase3_4b_v2_rawscores.jsonl
```
Prints the population-weighted (1709 miss : 4865 ctrl) net ΔnDCG@20 for every mode/threshold —
the table in §5 of the report. Edit the `taus`/`ptaus` in the script to sweep any new threshold,
still GPU-free.

## Regenerate from scratch (needs GPU + data)
See the report's "How to reproduce" section — the `probe_xenc_*.py` commands plus the inputs
(LanceDB catalog, devset trace, lanes, ground truth) under the gitignored `exp/`.
