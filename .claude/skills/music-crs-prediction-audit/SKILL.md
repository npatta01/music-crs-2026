---
name: music-crs-prediction-audit
description: Build an interactive Music CRS prediction audit from a tid, config, prediction JSON, or submission ZIP. Use when diagnosing devset, blindset, test, or pre-submission recommendations; mapping conversations/state/traces to predicted tracks; checking rejection leaks, state/compiler/resolver/ranking/retriever gaps; selecting better candidates from the submitted list or candidate pool; optionally adding a label-free LLM judge; or generating an HTML report with aggregate validity metrics.
---

# Music CRS Prediction Audit

Use this skill to inspect a Music-CRS recommendation run as a user-facing audit,
not only as aggregate scores.

Announce at start:

```text
I'm using the music-crs-prediction-audit skill to build an interactive prediction audit.
```

## Inputs

Accept any of these entry points:

- `--tid <tid>`: infer `configs/<tid>.yaml`, prediction path under `exp/inference/<split>/`, optional trace, optional devset ground truth, and output directory.
- `--config <path>`: read YAML and infer `tid` and split when possible.
- `--prediction <path>`: read a prediction JSON or a submission ZIP containing `prediction.json`.

Useful optional inputs:

- `--trace <path>`: JSONL state/ranking trace. Enables state, resolver, branch, and candidate-pool diagnosis.
- `--ground-truth <path>`: devset labels. Enables nDCG/hit/MRR and per-row gold rank.
- `--dataset <hf_dataset>`: override Hugging Face conversation dataset.
- `--split <split>`: `devset`, `blindset_A`, `blindset_B`, or another local split name.
- `--catalog-lancedb <path>`: LanceDB catalog directory, defaults to `cache/lancedb`.
- `--catalog-source {auto,lancedb,hf}`: catalog metadata source, default `auto`. `auto` tries LanceDB first, then falls back to Hugging Face track metadata.
- `--catalog-hf-dataset <name>` / `--catalog-hf-split <split>`: HF catalog source, defaults to `talkpl-ai/TalkPlayData-Challenge-Track-Metadata` split `all_tracks`.
- `--leaderboard-metadata <path>`: optional JSON with external leaderboard scores. Never require this for pre-submission audits.
- `--llm-judge`: optional qualitative judge for label-free/blind audits only. The script skips model calls automatically when `--ground-truth` is supplied.
- `--llm-explanation-judge`: optional qualitative judge for the generated natural-language response/explanation in label-free/blind audits. It is separate from the recommendation judge and also skips when `--ground-truth` is supplied.
- `--llm-state-judge`: optional diagnostic judge for extracted/compiled state accuracy. It compares raw conversation against trace state and is separate from recommendation/explanation judging.
- `--judge-model <model>`: LiteLLM model for label-free judging. Defaults to `MCRS_AUDIT_JUDGE_MODEL` or `openrouter/deepseek/deepseek-v4-flash`; `openrouter/google/gemma-3-12b-it` is also a known option.
- `--judge-limit <n>`: maximum rows to judge, default 80; use `0` for all audited rows.
- `--judge-top-k <n>`: number of submitted recommendations shown to the LLM judge, default 20.
- `--judge-workers <n>` / `--judge-max-tokens <n>`: control concurrent model calls and response budget when completing a larger blind audit.
- `--explanation-judge-cache <path>`: optional JSONL cache for response/explanation judgments, default `<out>/llm_explanation_judgments.jsonl`.
- `--state-judge-cache <path>`: optional JSONL cache for state judgments, default `<out>/llm_state_judgments.jsonl`.
- `--judge-litellm-cache {disk,local,off}`: LiteLLM completion cache for uncached judge calls, default `disk`. This is separate from the report JSONL audit cache.
- `--judge-litellm-cache-dir <path>`: directory for LiteLLM disk cache, default `<out parent>/.litellm_cache`.
- `--judge-include-state`: diagnosis mode only; include compiled/extracted state and audit flags in the LLM judge prompt. By default the judge sees the raw conversation and candidate metadata, not pipeline state.
- `--out <dir>`: output directory. Defaults under `exp/analysis/prediction_audit/`.

## Workflow

1. Resolve paths from `tid`, `config`, or `prediction`.
2. If local shared artifacts are missing, run `python scripts/setup_worktree_cache.py` from the repo root before recomputing or loading large cached resources.
3. Run the bundled generator from the repo root:

```bash
python .claude/skills/music-crs-prediction-audit/scripts/audit_submission_predictions.py \
  --tid state_ranker_v10_lgbm_blindset_A \
  --trace exp/inference/blindset_A/state_ranker_v10_lgbm_blindset_A_trace.jsonl
```

or for a submission ZIP:

```bash
python .claude/skills/music-crs-prediction-audit/scripts/audit_submission_predictions.py \
  --prediction submission/v10_lgbm_A.zip \
  --trace exp_modal_blindA_check/inference/blindset_A/state_ranker_v10_lgbm_blindset_A_trace.jsonl \
  --split blindset_A
```

or for a label-free Blind-A audit with a recorded LLM judge:

```bash
python .claude/skills/music-crs-prediction-audit/scripts/audit_submission_predictions.py \
  --prediction submission/v10_lgbm_A.zip \
  --trace exp_modal_blindA_check/inference/blindset_A/state_ranker_v10_lgbm_blindset_A_trace.jsonl \
  --split blindset_A \
  --llm-judge \
  --llm-explanation-judge \
  --llm-state-judge \
  --judge-model openrouter/deepseek/deepseek-v4-flash
```

Blind-B is supported by `--split blindset_B` or any config whose dataset is
`talkpl-ai/TalkPlayData-Challenge-Blind-B`. Its rows may have null
`conversation_goal` and empty `goal_progress_assessments`; the judge prompt
therefore uses the raw conversation and candidate metadata by default.

or for a label-aware devset audit:

```bash
python .claude/skills/music-crs-prediction-audit/scripts/audit_submission_predictions.py \
  --tid state_ranker_v10_lgbm_devset \
  --ground-truth exp/ground_truth/devset.json
```

4. Open `index.html` from the output directory and inspect:
   - collapsible metric groups
   - gap breakdown
   - row table filters
   - conversation/current request
   - extracted/compiled state and resolver
   - final top-20 with colors
   - better submitted candidate
   - better candidate-pool candidate when trace is available
   - Recommendation Fit verdict/reason when labels are absent
   - Recommendation Fit dropdown/chips for label-free judge runs
   - Response Quality dropdown/chips for label-free `predicted_response` audits
   - State Accuracy dropdown/chips for trace-backed state accuracy audits
   - LLM judge pick from the shown submitted recommendations when `--llm-judge` is used

5. Report source caveats clearly:
   - Blind/test/pre-submit audits do not know hidden ground truth.
   - Blind-B may have no `conversation_goal`; render this as `not provided` and judge from the raw conversation and candidate metadata.
   - Leaderboard scores are external optional metadata.
   - “Heuristic better” candidates are deterministic validity/intent heuristics unless ground truth confirms them.
   - “Recommendation Fit” is the external judge's recorded choice from the submitted recommendations it was shown. It displays raw verdicts as `strong fit`, `plausible`, `weak fit`, or `bad fit`.
   - “Response Quality” is the external judge's recorded assessment of the generated `predicted_response`, focusing on whether the prose grounds and justifies the submitted top recommendation, stays conversationally relevant, and avoids unsupported claims. It may use raw dataset `user_profile` when present and renders it as `not provided` when null. It is not a hidden-ground-truth retrieval judge. It displays raw verdicts as `clear`, `acceptable`, `thin`, or `misleading`.
   - “State Accuracy” is a diagnostic compiler/state audit: it intentionally sees raw conversation plus extracted/compiled state, and reports missing constraints, stale state, and state-risk. It is not a recommendation-quality judge. It displays raw verdicts as `accurate`, `partial`, or `inaccurate`.
   - LLM judge is qualitative and should only be used when labels are missing; it is never a substitute for devset labels.
   - LLM judge responses are still recorded in the report JSONL cache for auditability; LiteLLM disk/local cache only avoids repeated provider calls for identical uncached completions.
   - The LLM judge prompt must not include compiled/extracted state by default, because state/compiler bugs can contaminate the judge. Keep state visible in the HTML debugging panel; use `--judge-include-state` only for diagnosis runs.

## Diagnosis Rules

Treat these as high-confidence bad recommendations:

- final top1 or top20 item matches a rejected artist, album, or track by id
- final item matches normalized rejected names, even when ids differ
- request asks for new/different/other artists and final item repeats a satisfied prior artist
- response says the chosen track should be avoided

Classify likely root cause:

- `state_gap`: conversation asks to avoid/switch, but structured state has no exclusion/rejection.
- `resolver_gap`: structured rejection exists, but rejected ids/names are incomplete or duplicated.
- `compiler_filter_gap`: resolver has rejected ids or names, but final ranking still contains them.
- `ranking_gap`: candidate fusion or the submitted list had clean candidates, but final ordering placed an invalid or weak candidate above them.
- `retrieval_gap`: no clean matching candidate is available in submitted top20 or candidate-fusion pool.
- `label_miss`: ground truth is absent from top20/devset metric miss.

Prefer a better candidate in this order:

1. first strong valid candidate from submitted top20
2. strongest valid candidate from candidate-fusion pool
3. if no trace exists, say candidate-pool diagnosis is unavailable

## Outputs

The script writes:

- `index.html`: portable interactive audit
- `audit.json`: source-backed row diagnostics and aggregate metrics

Do not check raw traces or large generated reports into source control unless the user explicitly asks. Keep generated reports under `exp/analysis/prediction_audit/` by default.
