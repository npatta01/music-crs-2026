# Experiment: v0plus_compiler_all_retrievers_devset

**Date:** 2026-06-03
**Config:** `configs/v0plus_compiler_all_retrievers_devset.yaml`
**Backend:** Modal, 10-shard full devset run (8 CPU cores/shard)
**Modal app:** `ap-M8QUeyndYED7iCGjQYUXL8` (run id `20260603T174341Z-78c558`)
**Status:** `analyzed`

> **Reproduced 2026-06-03 17:43** (run id `20260603T174341Z-78c558`, 10 shards × 8 cores)
> after three results-neutral infra changes: (1) **client-side DiskVectorCache** on the
> `modal_multimodal` CLAP/SigLIP encoder so repeated query texts skip the Modal RPC
> (mirrors the litellm Qwen cache); (2) `litellm.suppress_debug_info` to silence the
> OpenRouter "Provider List" log flood (BerriAI/litellm#23879); (3) inference container
> specs `inference_cpu 2→6`, `inference_memory 16→32 GiB` (measured: ~4 cores used —
> the per-turn fusion is GIL-bound, so cores beyond ~6 idle; RAM bursts to ~25 GiB).
> Metrics matched the prior 5-shard run within rounding noise (NDCG@20 0.1253, Hit@1000
> 0.7289), confirming the changes affect only speed/cost, not retrieval. With the litellm +
> embedding caches warm (PR #105 had covered these query texts), this run issued **no GPU
> encoder calls and no OpenRouter calls** — all embeds/extractions were cache hits — yet
> `dense.clap_text` and `dense.qwen_8b` still `fired=8000` with non-zero recall, proving the
> cache served the branches rather than silently skipping them.

## Summary

Full devset (1000 sessions, 8000 turns) on the **freshly rebuilt LanceDB catalog**
(metadata + FTS + 0.6B/4B/8B Qwen embedding columns). This is the first full-devset
validation of the catalog's 4B/8B Qwen dense columns end-to-end — all dense branches
(`qwen_0_6b`, `qwen_8b`, `clap_text`) plus the centroid/discography/era branches ran
with no missing-vector-field errors and zero shallow/extractor-none rows out of 8000.

It improves on the prior all-retrievers run across the board — most notably candidate
**coverage** (Hit@1000 0.6967 → **0.7289**) — but top-20 ranking still trails the
image-only canonical config. More branches recover more gold tracks somewhere in the
1000-deep pool; the fused order remains the bottleneck for headline top-K quality.

| Comparison | NDCG@20 | Hit@20 | Hit@1000 | MRR |
|---|---:|---:|---:|---:|
| `v0plus_compiler_image_devset` | 0.1452 | 0.2989 | 0.6261 | 0.1062 |
| `v0plus_compiler_all_devset` | 0.1432 | 0.3090 | 0.6730 | 0.1010 |
| `all_retrievers` (2026-06-01, 0.6B dense only) | 0.1219 | 0.2660 | 0.6967 | 0.0871 |
| **`all_retrievers` (2026-06-03, fresh DB + 8B dense)** | **0.1255** | **0.2742** | **0.7289** | **0.0897** |

Verdict: keep as the best coverage / candidate-pool reference, not the canonical ranking
config. The Branch Union Coverage below quantifies the headroom: the gold track is
*reachable* far more often than it *survives* fusion — so the next lever is fusion/
survivor-set tuning or a reranker over this pool, not more branch recall.

## Configuration

| Field | Value |
|---|---|
| lm_type | dummy |
| qu_type | v0plus_compiler |
| retrieval_type | bm25 *(vestigial — V0PlusCompilerQU owns retrieval; the baseline retriever is built but unused)* |
| retrieval_topk | 1000 |
| compiler.final_topk | 1000 |
| dense branches | `metadata`/`attributes` × `qwen_0_6b` **and** `qwen_8b`; `clap_text` (CLAP text→audio) |
| centroid-only branches | `image_siglip2`, `audio_laion_clap`, `cf_bpr`, `cf_bpr:user` |
| extra branches | resolved-artist discography, era/popularity |

## Diagnostic Depth

| Field | Value |
|---|---:|
| Turns evaluated | 8000 |
| require_full_diagnostic_depth | false |
| Target diagnostic depth | 1000 |
| Min / Max pool depth | 1000 / 1000 |
| Shallow rows | 0 |

All 8000 turns returned a full 1000-candidate pool — no shallow rows or extractor-none
this run.

## Ranking Quality

| Metric | Value |
|---|---:|
| NDCG@1 | 0.0394 |
| NDCG@5 | 0.0839 |
| NDCG@10 | 0.1047 |
| NDCG@20 | 0.1255 |
| NDCG@50 | 0.1479 |
| NDCG@100 | 0.1614 |
| NDCG@200 | 0.1724 |
| NDCG@500 | 0.1847 |
| NDCG@1000 | 0.1929 |
| MRR | 0.0897 |
| MRR@100 | 0.0887 |
| MRR@200 | 0.0892 |
| MRR@500 | 0.0896 |
| MRR@1000 | 0.0897 |

## Retrieval Coverage

| Metric | Value |
|---|---:|
| Hit@1 | 0.0394 |
| Hit@5 | 0.1274 |
| Hit@10 | 0.1919 |
| Hit@20 | 0.2742 |
| Hit@50 | 0.3871 |
| Hit@100 | 0.4705 |
| Hit@200 | 0.5490 |
| Hit@500 | 0.6518 |
| Hit@1000 | 0.7289 |
| % GT not in top-20 | 72.6% |
| % GT not in top-100 | 53.0% |
| % GT not in top-200 | 45.1% |
| % GT not in top-500 | 34.8% |
| % GT not in top-1000 | 27.1% |
| Mean rank when found | 154.9 |
| Median rank when found | 43.0 |

## Branch Union Coverage

Fraction of turns where **some** retriever branch surfaces the GT in its top-k
(pre-fusion), versus the final fused/ranked hit@k, with
`fusion_efficiency = hit@k / unionhit@k` (how much reachable GT the fusion+rank stage
keeps). Computed from the per-turn branch pools in the devset trace.

| k | union@k | final hit@k | fusion efficiency |
|---|---:|---:|---:|
| 20 | 0.4768 | 0.2742 | 0.575 |
| 100 | 0.6620 | 0.4705 | 0.711 |
| 200 | 0.7432 | 0.5490 | 0.739 |
| 1000 | 0.9051 | 0.7289 | 0.805 |

**Read:** at depth 1000, 90.5% of GTs are reachable by some branch but only 72.9% survive
to the final list — the fusion/rerank stage, not branch recall, is the binding constraint
on the deep tail. At depth 200, union 0.743 vs final 0.549 (efficiency 0.739) → ~26% of
reachable GT is dropped by fusion/ranking. This is the quantified case for a reranker /
survivor-set policy over this pool.

## Diversity

| Metric | Value |
|---|---:|
| Catalog diversity @20 | 0.5314 |
| Catalog diversity @100 | 0.8968 |
| Lexical diversity | 0.0000 *(response generation is the dummy path — no response text to diversify)* |

## Per-Turn Breakdown

| Turn | NDCG@20 | Hit@20 | Hit@100 | N |
|---:|---:|---:|---:|---:|
| 1 | 0.1671 | 0.3180 | 0.4800 | 1000 |
| 2 | 0.1981 | 0.4030 | 0.6050 | 1000 |
| 3 | 0.1553 | 0.3430 | 0.5600 | 1000 |
| 4 | 0.1278 | 0.2910 | 0.5000 | 1000 |
| 5 | 0.1001 | 0.2340 | 0.4420 | 1000 |
| 6 | 0.0922 | 0.2170 | 0.4140 | 1000 |
| 7 | 0.0935 | 0.2170 | 0.3920 | 1000 |
| 8 | 0.0699 | 0.1710 | 0.3710 | 1000 |

Ranking quality peaks at turns 1–2 (most explicit query signal) and decays monotonically
as conversations deepen and intent drifts — same shape as the prior run, slightly higher
at every turn.

## Findings

1. **Coverage improved again; ranking nudged up but is still the bottleneck.**
   Hit@1000 reaches 0.7289 (best tracked v0+ coverage), and adding the 8B dense branches on
   the fresh catalog lifts every metric vs the 0.6B-only 2026-06-01 run. But Hit@20 is still
   0.2742 — the extra branches mostly add recoverable candidates at mid/deep ranks.

2. **Fusion efficiency is the headline diagnostic.** union@1000 0.905 vs final 0.729 means
   ~18% of reachable gold is lost between branch pools and the final list; at @200 the loss is
   ~26%. The candidate reservoir is rich — the ranking/fusion stage is where the points are.

3. **Clean run.** Zero shallow rows / extractor-none out of 8000; the noisy LiteLLM
   provider-list log footers are benign (the 50-session smoke showed them too and scored fine).

4. **Best reranker input to date.** With the largest candidate reservoir of the tracked
   configs and quantified fusion headroom, this run is the natural source pool for a reranker
   or survivor-set experiment.

## Operational Notes

- Run: `python run_experiment.py --backend modal --tid v0plus_compiler_all_retrievers_devset --num_shards 5 --batch_size 64` (auto download → merge → evaluate).
- First full-devset run on the rebuilt catalog (cached Qwen 0.6B/4B/8B columns); the catalog rebuild used the process-pool embedding path (PR #104).
- Union@k comes from `scripts/branch_diagnostics.py`, which streams the trace (one pass, O(1) memory) so it scales to the full-devset trace. `run_experiment.py` runs it automatically after devset evaluation and folds `union@k` / `fusion_efficiency@k` into the scores JSON, so future devset runs capture these without a manual step.

## Files

- Inference predictions: `exp/inference/devset/v0plus_compiler_all_retrievers_devset.json`
- Trace: `exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl`
- Per-shard predictions/traces: `exp/inference/devset/v0plus_compiler_all_retrievers_devset.run_20260603T110031Z-f985d4.shard_{0..4}*.json`
- Aggregate scores: `exp/scores/devset/v0plus_compiler_all_retrievers_devset.json`
- Per-sample metrics: `exp/scores/devset/v0plus_compiler_all_retrievers_devset_samples.csv`
