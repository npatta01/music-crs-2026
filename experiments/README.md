# Experiment Index

This directory is intentionally pruned. Old experiment reports, archived configs,
and raw analysis artifacts were removed from the working tree because they were
misleading agents about the current system. Use Git history for older waves.

## Current Configs

| Config | Role | Notes |
|---|---|---|
| `configs/v0plus_compiler_all_retrievers_devset.yaml` | Latest devset experiment | Current-prompt all-retrievers candidate-pool config. Best tracked Hit@1000, but weaker top-20 ranking than the image anchor. |
| `configs/v0plus_compiler_image_devset.yaml` | Score anchor | Current v0+ top-20 retrieval baseline after bugfixes. |
| `configs/v0plus_compiler_blindset_A.yaml` | Submission path | Blind A config; keep split-specific behavior separate from devset experiments. |

## Current Reports

| Report | Why it remains |
|---|---|
| [v0plus_compiler_all_retrievers_devset.md](v0plus_compiler_all_retrievers_devset.md) | Latest full devset run: NDCG@20 0.1219, Hit@1000 0.6967. Treat as coverage/reranker evidence, not as the score anchor. |
| [v0plus_compiler_image_devset.md](v0plus_compiler_image_devset.md) | Current score anchor: NDCG@20 0.1452 after retrieval bugfixes. |
| [analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/index.html](analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/index.html) | Durable baseline recall-gap snapshot for the all-retrievers devset run. Treat as an experiment analysis and replay contract; rerun after extractor, retriever, ranker, catalog, or split changes. |
| [analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_additive_retriever_matrix_all110_summary.md](analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_additive_retriever_matrix_all110_summary.md) | Focused 110-pack additive candidate-recall matrix for frozen V1 state/projection. Treat as candidate-source evidence only, not as a full-devset or ranking result. |
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
