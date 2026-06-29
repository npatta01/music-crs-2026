# Submission: Blind-B — state_ranker_v10_lgbm_blindset_B (v1)

| Field | Value |
|---|---|
| **Version** | v1 (first Blind-B submission) |
| **Date prepared** | 2026-06-29 |
| **Status** | ✅ Packaged locally — **NOT yet uploaded to CodaBench** |
| **Split** | blindset_B (`talkpl-ai/TalkPlayData-Challenge-Blind-B`, 80 sessions, final turn each) |
| **Artifact** | [`submission/v10_lgbm_B_v1.zip`](../submission/v10_lgbm_B_v1.zip) (packaged 2026-06-29) |
| **Zip SHA-256** | `d75e85d314ea0c262c81f8f0325f0e5ef89ad4a8186f2299688f1e911c16f6e2` |
| **Contents** | `prediction.json` (80 rows) |

➡️ **Upload to CodaBench Blind-B:** [`submission/v10_lgbm_B_v1.zip`](../submission/v10_lgbm_B_v1.zip)

## Git state

| | |
|---|---|
| **HEAD commit** | `92697b6` — "Prune configs to active set; merge fastlocal; rename v12 bundle (#178)" (2026-06-29 14:16 -0400) |
| **Working tree** | Dirty at package time — see uncommitted changes below |

Uncommitted changes when this submission was built:
- `configs/state_ranker_v10_lgbm_blindset_B.yaml` — **added the `explanation_lm_type` / `explanation_lm_kwargs` / `explanation_kwargs` block** (was missing → empty responses), set concurrency to 4/4, added DeepInfra embed `num_retries: 4` / `timeout: 60`, fixed stale header comment.
- `configs/state_ranker_v10_lgbm_devset.yaml` — DeepInfra embed retry guard (unrelated to this submission).
- `leaderboard.md`, `experiments/state_ranker_v10_lgbm_devset.md` — devset recapture (unrelated).

> ⚠️ These config edits are **not committed**. Commit them before treating this submission as reproducible from a clean checkout.

## Config used

`configs/state_ranker_v10_lgbm_blindset_B.yaml`

| Setting | Value |
|---|---|
| qu_type | state_ranker |
| ranking.mode | lgbm (`model_version: lgbm_v10`) |
| reranker bundle | **`models/reranker_v12_goalfree`** (goal-free — Blind-B-safe, drops goal features) |
| final_artist_guard | enabled, top_k 20 |
| state extraction | `prompt_version: v1`, file-per-turn cache (`cache/state_extraction/blindset_B`) |
| **explanation LM** | `litellm` → `openrouter/qwen/qwen3-30b-a3b-instruct-2507`, temp 0.0, max_tokens 2048 |
| explanation template | `phase2_best_qwen`, conditioning `latest_state`, item_format `xml`, max_tags 10 |
| query embed (0.6B) | DeepInfra `Qwen/Qwen3-Embedding-0.6B` (num_retries 4, timeout 60) |
| catalog | LanceDB, 47,071 tracks |
| concurrency | max_in_flight 4 / compile_max_in_flight 4 |

## Run

```bash
python run_experiment.py --backend local --tid state_ranker_v10_lgbm_blindset_B --eval_dataset blindset_B
bash prepare_submission.sh state_ranker_v10_lgbm_blindset_B blindset_B   # (then renamed with _v1_ version tag)
```

Local single-process run, ~4 min, 47 s/it (explanation generation `response_generation=42.4s` confirmed fired, vs 0 in the dummy run). No timeouts.

## Prediction stats

- 80 rows / 80 unique sessions (final turn each)
- `predicted_track_ids`: exactly 20 per row, 0 duplicates
- `predicted_response`: 80/80 non-empty (150–450 chars, median 277)

## Audit (label-free, deepseek-v4-flash judge)

Audit at `exp/analysis/prediction_audit/state_ranker_v10_lgbm_blindset_B/` (run on the
recommendation set — identical track IDs to this submission; only responses differ).

- Recommendation-fit judge (79 judged): good 25 / weak 12 / **bad 42** → weak-or-bad 54 (68%).
- Top-1 flagged 17/80, top-20 flagged rows 31/80; hard top-1 leaks 1.
- Dominant gap: **ranking_gap 31** (clean candidate available but ordered below), compiler_filter_gap 8, state_gap 3, resolver_gap 1.
- `with_better_pool` 31, `with_better_submitted` 30 → headroom from re-ordering existing candidates.
- State judge (79): good 39 / bad 39 / partial 1.

> Caveat: Blind-B has no hidden ground truth; the judge is a qualitative deepseek-v4-flash
> pass, not a retrieval metric. The high weak/bad rate flags ranking/ordering as the main
> improvement lever, not retrieval coverage.
