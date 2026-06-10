# Conversation State Prompt Contract

The active extractor prompt is `current.py`. `rubric.py` and `rejection.py` are
experiment-only variants for replay testing; they are not production defaults.
The main implementation artifact for state-v1 work is the prompt contract, not
the replay evaluator. The evaluator is only a later smoke harness for a small
batch of examples.

## Objective

Extract state that downstream retrieval can use for the next recommendation.
Do not summarize the conversation. Classify the role of each entity and mode of
the latest user request. The active prompt emits `ConversationStateV1`; compiler
compatibility fields are derived by the bridge.

The prompt must teach these behaviors:

- Separate `current_target` / `seed` from `satisfied`, `history`, `contrast`,
  and `rejected`.
- Mark prior liked artists and tracks as `satisfied` or `history` when the user
  asks for other artists, another item, or a new direction.
- Use `current_request.request_type`, `facts[].relation`, and `facts[].reuse`
  to make the request semantics clear. Do not emit `target_artist_mode` or
  `retrieval_profile`; the bridge/compiler derives those.
- Keep hard future exclusions separate from soft style dislikes.
- Treat era phrases as soft style cues unless the user gives literal release
  date eligibility language.
- Keep `evidence_text` short and verbatim enough to audit high-risk decisions.

## Prompt Review Checklist

Before changing schema or resolver code, check whether `current.py` already
teaches the desired extraction behavior:

1. Does the system prompt describe the decision rule?
2. Is there a few-shot example showing the positive case?
3. Is there a few-shot example showing the nearest confusing negative case?
4. Does the output use only fields supported by `ConversationStateV1`?
5. Does the bridge/projected V0Plus view consume the field, or is it analysis-only?

## Current Few-Shot Coverage

The active few-shot set covers:

- satisfied prior artist plus new-artist novelty
- same-artist exact/album continuation
- style-era temporal cue that must not hard-filter
- hard artist rejection
- hard release-date filter
- stale disco/funk artist satisfied as history
- novelty after an iconic hit (`Toxic`-style case)
- hidden target search with lyric phrase
- contrast artist plus soft style rejection
- hard soundtrack/style family exclusion
- rejection-focused experimental examples for "good on Drake for now" and
  "System Of A Down, but not them" live in `rejection.py`, not `current.py`.

These examples are intentionally devset-shaped. They should remain compact
because every example is sent with every extractor call.

## Clean Replay Experiment

The reviewed 20-sample prompt experiment is documented in:

`experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_clean_prompt_experiment_summary.md`

Result summary:

- original `current`: 17/20 all-pass on reviewed checks.
- `rubric`: 17/20; fixed one rejection but regressed one album entity.
- `rejection`: 18/20; fixed both hard-rejection misses but still regressed the
  `Cracker Island` album entity.
- updated guarded `current`: 19/20; fixed both hard-rejection misses while
  preserving explicit album/track entities.

Conclusion: keep the generic guarded `current` change. It teaches the pattern
"good on X for now" without hardcoding devset artist names, and keeps the
album/track preservation guardrail that prevented the `Cracker Island`
regression. Rerun the full 110 replay pack before treating the extractor as
complete.

## What Not To Optimize First

Do not add broad metadata fields just because they exist in organizer data.
Session-level constants can condition retrieval or ranking, but they do not
distinguish candidates by themselves. Add them only when there is a concrete
downstream consumer.

Do not make temporal extraction the main state project. The useful prompt work
is the hard-vs-soft distinction, not a large era ontology.

Do not treat replay-pack scores as proof that the prompt is good. A live replay
run is useful later, but the first deliverable is a clear prompt contract with
examples that express the intended extraction behavior.
