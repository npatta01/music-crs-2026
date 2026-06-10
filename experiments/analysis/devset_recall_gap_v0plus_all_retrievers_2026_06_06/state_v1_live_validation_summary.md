# State v1 Live Extraction Validation

Date: 2026-06-06

Command:

```bash
set -a
source /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.env
set +a
uv run --extra dev python scripts/evaluate_state_replay_pack.py \
  --state-source live \
  --packs all \
  --output experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_live_all110_scores.json \
  --observed-output experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_live_all110_observed.jsonl \
  --markdown-report experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_live_all110_report.md \
  > /tmp/state_v1_live_all110_stdout.json
```

Model: `openrouter/deepseek/deepseek-v4-flash`

Comparison artifacts were generated from the saved live JSONL without another
LLM call:

```bash
uv run --extra dev python scripts/evaluate_state_replay_pack.py \
  --state-source jsonl \
  --packs all \
  --states experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_live_all110_observed.jsonl \
  --output experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_live_all110_comparison_scores.json \
  --observed-output experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_live_all110_comparison_audit.jsonl \
  --markdown-report experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/state_v1_live_all110_comparison_report.md \
  > /tmp/state_v1_live_all110_comparison_stdout.json
```

## Result

The live extractor validates structurally but is not semantically solved.

| Metric | Value |
|---|---:|
| samples | 110 |
| schema_valid_rate | 100.0% |
| all_pass_rate | 45.5% |
| role_correct_rate range by pack | 70.0% to 100.0% |
| target_artist_mode_correct_rate range by pack | 20.0% to 100.0% |
| retrieval_profile_correct_rate range by pack | 20.0% to 100.0% |
| temporal_semantics_correct_rate on temporal pack | 60.0% |
| rejection_normalization_correct_rate on rejection pack | 50.0% |
| exact-entity positive control all-pass | 90.0% |
| new state captures expected information | 50 / 110 |
| rows improved vs previous trace state | 34 / 110 |
| rows regressed vs previous trace state | 27 / 110 |

## What Changed During Validation

- Added live replay support for `--packs all`, per-pack sampling, raw observed-state JSONL, and markdown reports.
- Added baseline/new/desired comparison output. Each audit row now includes
  `previous_state`, `previous_observed`, `new_state`, `new_observed`,
  `desired_state`, and an `evaluation` object with improved, regressed, and
  still-missing checks.
- Corrected evaluator semantics for exact named-entity controls: `retrieval_profile=exact_probe` is the meaningful check; same/new artist mode is not meaningful for direct "play X by Y" requests.
- Corrected evaluator semantics for broad novelty requests where `any_artist` or `unknown` plus `retrieval_profile=novelty` is acceptable.
- Added prompt guardrails for:
  - current named artist plus refined mood: keep the artist as `current_target`, `target_artist_mode=same_artist`, `retrieval_profile=continuation`;
  - sequential "journey / next stop" requests: prior artists are history, target is novelty;
  - broad "other songs / popular hits" asks after artist praise: the praised artist is satisfied, not the current seed.

## Remaining Extractor Gaps

1. **Mode/profile labels remain unstable.** The model often chooses `continuation`, `feature_search`, or `hidden_target_search` where the replay contract expects novelty. Some of this is real ambiguity, but some affects downstream route selection.
2. **Named artist role is better but not fully robust.** The targeted Frank Ocean sample passed after the guardrail, but the full pack still has named-artist role/mode misses.
3. **Temporal hard-vs-soft is still inconsistent.** On the temporal pack, temporal semantics pass only 60%. The common failure is treating era wording like "from the late 90s or early 2000s" as a hard `release_date` filter or missing the soft era entirely.
4. **Rejection extraction is under-specified.** On the rejection pack, only 50% pass. The extractor often emits soft style rejections or no rejection when the test expects a hard normalized rejection. Some replay labels are noisy, but the state contract still needs clearer named-entity vs style-rejection behavior.
5. **Replay labels are partly contaminated by GT/ranker assumptions.** Several failures are not extractor mistakes, for example user asks for a new artist but `ideal_state` says same artist because the GT happens to share an artist. The evaluator now handles the clearest cases, but the pack needs a human-labeled `expected_state_checks` layer before it can be treated as a strict gate.

## Recommendation

Do not treat this branch as extractor-complete. The schema and replay harness are useful, and structural validation is good, but the live extraction result says the next iteration should focus on:

- adding an explicit human-reviewed expected-check layer for the 110 replay samples;
- tightening prompt rules for novelty vs continuation, especially "what else", "similar to this", "other artists", and named-artist praise;
- tightening temporal language: only `only`, `strictly`, `released between`, `nothing newer/older`, or equivalent should set `apply_as_filter=true`;
- tightening rejection language: named "not X / no more X / but not them" should become hard entity rejection when resolvable, while descriptive "less heavy / not so metal" remains soft style rejection.

Source artifacts:

- Scores: `state_v1_live_all110_scores.json`
- Raw observed states: `state_v1_live_all110_observed.jsonl`
- Comparison scores: `state_v1_live_all110_comparison_scores.json`
- Comparison audit JSONL with previous/new/desired states: `state_v1_live_all110_comparison_audit.jsonl`
- Comparison markdown report: `state_v1_live_all110_comparison_report.md`
- Original observed-only markdown report: `state_v1_live_all110_report.md`
