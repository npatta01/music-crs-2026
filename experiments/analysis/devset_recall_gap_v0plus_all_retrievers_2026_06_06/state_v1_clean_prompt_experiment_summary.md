# State v1 Clean Prompt Experiment

Date: 2026-06-06

## Purpose

The original 110-sample replay score mixed extractor-state mistakes with
GT/ranker-derived labels. This experiment creates a smaller human-reviewed
20-sample overlay and tests prompt variants only against state facts that are
clear from the user conversation.

## Clean Subset

Reviewed overlay:
`state_v1_clean_expected_overrides.json`

The overlay covers:

- direct exact track / artist requests;
- hidden-target recall requests;
- same-artist and same-album continuation;
- satisfied-prior novelty requests;
- hard rejection requests such as "good on Drake for now" and "but not them";
- soft temporal era requests.

The evaluator uses the overlay through:

```bash
--expected-overrides state_v1_clean_expected_overrides.json --only-overrides
```

## Variants Tested

| Variant | Prompt version | What changed |
|---|---|---|
| Current baseline | `current` | Existing state-v1 prompt, scored from saved live JSONL. |
| Broad rubric | `rubric` | Adds a decision ladder for exact vs hidden target, entity roles, artist policy, retrieval profile, and temporal semantics. |
| Rejection few-shot | `rejection` | Adds synthetic hard-rejection few-shots for "good on X for now" and "similar to X but not them"; kept as an experiment artifact. |
| Generic guarded production current | `current` | Adds synthetic hard-rejection examples plus a guardrail to preserve explicit current-turn album/track names. |

## Results

| Variant | All-pass | Role | Artist mode | Retrieval profile | Temporal | Rejection |
|---|---:|---:|---:|---:|---:|---:|
| current | 17/20 | 20/20 | 20/20 | 19/20 | 20/20 | 18/20 |
| rubric | 17/20 | 19/20 | 20/20 | 19/20 | 20/20 | 19/20 |
| rejection | 18/20 | 19/20 | 20/20 | 19/20 | 20/20 | 20/20 |
| guarded current | 19/20 | 20/20 | 20/20 | 19/20 | 20/20 | 20/20 |

## Findings

1. **Cleaning labels changes the read.** The same current-prompt live output
   scores 17/20 on reviewed checks, versus 50/110 on the noisy full pack. The
   state extractor is not solved, but the raw 110 score understated it because
   several expected labels were GT/ranker-contaminated.
2. **Broad rubric did not improve net quality.** It fixed the System Of A Down
   hard rejection, but regressed one Gorillaz continuation case by omitting the
   explicit album entity `Cracker Island`.
3. **Targeted rejection few-shots helped.** The rejection-focused variant fixed
   both hard-rejection misses in the clean subset: `Drake` and
   `System Of A Down`.
4. **Few-shots can still perturb extraction.** The rejection-focused variant
   also missed the `Cracker Island` album entity that the current prompt
   captured. Do not promote it to production without a broader regression run.
5. **Remaining non-rejection issue:** the Natalia Lafourcade first-album request
   is labeled continuation, but both tested variants emit `exact_probe`. This
   is arguably acceptable for candidate generation because the user gives a
   named artist and album. The clean overlay may be too strict on this point.
6. **The generic production-safe version is the one to keep.** Adding
   synthetic rejection examples to `current.py` and a generic guardrail to keep
   explicit album/track names raised the reviewed subset to 19/20. A
   devset-near prompt variant scored higher on noisy labels, but it is not the
   production prompt because it used a sampled failure pattern too directly.

## Recommendation

Do not adopt the broad rubric as-is. Keep it as an experiment artifact.

The production prompt now uses the narrower change:

- one generic hard-rejection few-shot for the pattern "good on X for now" plus
  "other artists/bands";
- one explicit guardrail that rejection examples must not cause the model to
  drop current-turn album/track entities;
- rerun at least the 20 reviewed samples and then the full 110 replay pack.

Artifacts:

- Current baseline scores: `state_v1_clean_current_scores.json`
- Current baseline audit: `state_v1_clean_current_audit.jsonl`
- Rubric scores: `state_v1_clean_rubric_scores.json`
- Rubric audit: `state_v1_clean_rubric_audit.jsonl`
- Rejection few-shot scores: `state_v1_clean_rejection_scores.json`
- Rejection few-shot audit: `state_v1_clean_rejection_audit.jsonl`
- Generic guarded full-run clean-overlay scores: `state_v1_clean_from_full110_generic_guarded_scores.json`
- Generic guarded full-run clean-overlay audit: `state_v1_clean_from_full110_generic_guarded_audit.jsonl`
- Generic guarded full 110 scores: `state_v1_live_all110_generic_guarded_scores.json`
- Generic guarded full 110 audit: `state_v1_live_all110_generic_guarded_audit.jsonl`

## Full 110 Replay Follow-Up

After promoting the generic guarded change into `current.py`, the full 110
replay was rerun live. The production prompt does not contain the reviewed
failure names `Drake`, `System Of A Down`, `Blade Runner 2049`, or
`Cracker Island`.

```bash
uv run --extra dev python scripts/evaluate_state_replay_pack.py \
  --state-source live \
  --packs all \
  --prompt-version current \
  --output state_v1_live_all110_generic_guarded_scores.json \
  --observed-output state_v1_live_all110_generic_guarded_audit.jsonl \
  --markdown-report state_v1_live_all110_generic_guarded_report.md
```

Full noisy-label replay:

| Run | All-pass |
|---|---:|
| previous current | 50/110 |
| generic guarded current | 52/110 |

Clean reviewed overlay rescored from that same full live run:

| Run | All-pass | Rejection checks |
|---|---:|---:|
| previous current | 17/20 | 18/20 |
| generic guarded current | 19/20 | 20/20 |

Full replay all-pass changes versus the previous current run: 14 samples changed
status, with 8 improvements and 6 regressions under the noisy labels. The clean
reviewed subset changed 2 samples, both improvements and zero regressions. The
targeted hard-rejection checks improved from 18/20 to 20/20, and explicit
current-turn album/track preservation remained correct on the clean overlay.

Remaining known clean-subset miss: the Natalia Lafourcade first-album request
still emits `exact_probe` instead of `continuation`; this is probably acceptable
for retrieval because the user names both artist and album.
