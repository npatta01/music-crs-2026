# Experiment Index

This directory is intentionally pruned. Old experiment reports, archived configs,
and raw analysis artifacts were removed from the working tree because they were
misleading agents about the current system. Use Git history for older waves.

## Current Configs

| Config | Role | Notes |
|---|---|---|
| `configs/state_ranker_v10_rrf_devset.yaml` | Devset candidate-fusion baseline | Explicit `ranking.mode: rrf`; useful for retrieval and candidate-pool recall. |
| `configs/state_ranker_v10_lgbm_devset.yaml` | Current devset score anchor | Fresh v10 LambdaMART run: NDCG@20 0.4520, Hit@20 0.6105. |
| `configs/state_ranker_v10_lgbm_blindset_A.yaml` | Blind A submission path | CodaBench submission `797598`: nDCG@20 0.4380, composite 0.5389. |

## Current Reports

| Report | Why it remains |
|---|---|
| [state_ranker_v10_lgbm_devset.md](state_ranker_v10_lgbm_devset.md) | Current devset score anchor and stage-by-stage recall handoff. |
| [state_ranker_v10_rrf_devset.md](state_ranker_v10_rrf_devset.md) | Explicit candidate-fusion baseline used to build fresh v10 reranker features. |
| [analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/index.html](analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/index.html) | Durable baseline recall-gap snapshot for the all-retrievers devset run. Treat as an experiment analysis and replay contract; rerun after extractor, retriever, ranker, catalog, or split changes. |
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
