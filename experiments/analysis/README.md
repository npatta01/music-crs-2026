# Analysis Directory

This directory is kept only as a placeholder for one-off analysis notes that are
important enough to check in. It is not a runtime module location.

## Checked-In Analysis Snapshots

| Snapshot | Scope | How to use |
|---|---|---|
| [devset_recall_gap_v0plus_all_retrievers_2026_06_06](devset_recall_gap_v0plus_all_retrievers_2026_06_06/index.html) | Baseline recall-gap, state-audit, and ranker-decision report for `v0plus_compiler_all_retrievers_devset`. | Use as a standalone experiment analysis and small replay-pack contract. Rerun/regenerate after changing state extraction, retrieval routing, ranker/fusion logic, catalog/index contents, or the evaluation split. |

ConversationState runtime code lives in:

- `mcrs/conversation_state/schema.py`
- `mcrs/conversation_state/prompts/current.py`
- `mcrs/conversation_state/prompts/previous.py`

Historical analysis packages, prompt bakeoffs, raw JSONL outputs, slide decks,
and scripts were intentionally pruned. Use Git history if an older artifact is
needed.
