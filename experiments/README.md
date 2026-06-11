# Experiment Index

This directory is intentionally pruned. Old experiment reports, archived configs,
and raw analysis artifacts were removed from the working tree because they were
misleading agents about the current system. Use Git history for older waves.

## Current Configs

| Config | Role | Notes |
|---|---|---|
| `configs/v0plus_compiler_pruned_resolved_tags_devset.yaml` | **Current baseline** | Pruned dense branches (0.6B dedup) + tiered tag resolver. NDCG@20 0.1374 full devset (2026-06-11). |
| `configs/v0plus_compiler_pruned_devset.yaml` | Ablation arm | Pruning without the resolver; statistically identical head ranking. |
| `configs/v0plus_compiler_all_retrievers_devset.yaml` | Candidate-pool generator | Best union/deep coverage (union@1000 0.905); feeds the union-pool reranker (#95). |
| `configs/v0plus_compiler_blindset_A.yaml` | Submission path | Blind A config; keep split-specific behavior separate from devset experiments. |

## Current Reports

| Report | Why it remains |
|---|---|
| [v0plus_compiler_pruned_resolved_tags_devset.md](v0plus_compiler_pruned_resolved_tags_devset.md) | **Current baseline**: NDCG@20 0.1374 full devset; branch-dedup win (paired t=3.1) + retrieval-neutral tag resolver shipping ranker-feature metadata. |
| [seed50_paired_smoke_matrix.md](seed50_paired_smoke_matrix.md) | Paired seeded-slice methodology + the 5-arm ablation that attributed the win to branch dedup and retired catalog_exact. |
| [v0plus_compiler_all_retrievers_devset.md](v0plus_compiler_all_retrievers_devset.md) | Candidate-pool generator: best union/deep coverage; reranker evidence. |
| [v0plus_compiler_image_devset.md](v0plus_compiler_image_devset.md) | Retired image-only anchor: NDCG@20 0.1452 but hit@1000 0.626 and no multi-retriever union. |
| [analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/index.html](analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/index.html) | Durable baseline recall-gap snapshot for the all-retrievers devset run. Treat as an experiment analysis and replay contract; rerun after extractor, retriever, ranker, catalog, or split changes. |
| [analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_additive_retriever_matrix_all110_summary.md](analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_additive_retriever_matrix_all110_summary.md) | Focused 110-pack additive candidate-recall matrix for frozen V1 state/projection. Treat as candidate-source evidence only, not as a full-devset or ranking result. |
| [analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_all_on_candidate_recall_report.md](analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_all_on_candidate_recall_report.md) | Focused 110-pack all-on branch-pool attribution. Shows expanded existing branches do not improve the current 75/87/91 focused baseline; use it to separate source gaps from top-20 ordering tail work. |
| [analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_candidate_quality_nonprompt_report.md](analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_candidate_quality_nonprompt_report.md) | Focused 110-pack non-prompt candidate-quality diagnostic. Freezes V1 state/prompt, separates GT noise, shows catalog/anchor features lift branch-local union@20 from 77/110 to 84/110, and shows simple branch-family weighting plus capped candidate scoring do not yet produce valid final-like top-20 rescues. |
| [analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_gapfix_hard_drop_report.md](analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_gapfix_hard_drop_report.md) | Focused 110-pack gap-fix pass. Adds satisfied-feedback anchors and a hard-drop-only targeted branch matrix; improves promoted-feature-family OR coverage to 87/110 all and 76/97 valid at union@20. |
| [experiment_log.md](experiment_log.md) | Short current-state note only. Historical wave logs were pruned. |
| [analysis/README.md](analysis/README.md) | Notes that runtime prompt/schema modules have moved out of `experiments/analysis/`. |

## Do Not Resurrect By Default

- Do not recreate `configs/archive/` for superseded runs.
- Do not add raw JSONL, traces, slide decks, screenshots, or labeling artifacts
  under `experiments/` unless the user explicitly asks for a checked-in artifact.
- Store downloaded Modal artifacts under `exp/` or `evaluator/exp/`; those paths
  are local run outputs, not source-of-truth notes.
- For older scores or rationale, inspect Git history or the PR linked in
  [changelog.md](../changelog.md).

## Runtime Prompts

Runtime schema and extractor prompts have moved out of `experiments/`:

- `mcrs/conversation_state/schema.py`
- `mcrs/conversation_state/prompts/current.py`
- `mcrs/conversation_state/prompts/previous.py`

Keep `experiments/` for one-off reports and concise current-state notes.
