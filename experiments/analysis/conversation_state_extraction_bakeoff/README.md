# v0+ ConversationState Extraction Bake-off

Status: `analyzed` — three iteration rounds run; winner picked.

Goal: find the cheapest open-source model that **matches `gpt-5.4-nano`** on v0+ ConversationState extraction ([`iteration_1_minimal_schema.md`](../conversation_state_design_v2/iteration_1_minimal_schema.md)).

Budget: bake-off total under **$3**; eventual full-devset extraction run under **$10**.

> See [`analysis.md`](analysis.md) for the long-form analysis (methodology, iterations, caveats). This README is the verdict + protocol surface.

---

## Verdict

**Winner: `google/gemma-3-12b-it` via OpenRouter.**

| Metric | Value |
|---|---|
| Weighted F1 vs audit-gold (Claude Opus 4.7 hand labels) | **0.812** — best of 7 candidates |
| Weighted F1 vs nano-silver (user-designated oracle) | 0.731 — 4th of 7; within 5 pts of leader |
| Schema validity (strict json_schema) | **100%** (40/40 audit rows) |
| Mean latency per call | 4.9 s |
| **Full-devset extraction (8k turns × 2 stages, both-stage)** | **~$1.86** — 81% headroom under $10 budget |

Strictly dominant on cost × quality × latency among the OS candidates.

### Honest qualifications

1. **Nano isn't a perfect oracle.** It scores 0.680 vs audit — lower than 4 OS candidates. It under-extracts `track_feedback` by ~3× compared to my hand labels (36 entries vs 123). If "matches nano's behavior" is the test, Qwen3.6-35B-A3B (0.782 vs-nano) is the literal answer. If "matches a careful human reading" is the test, Gemma 3 12B is. They have different opinions about how dense to be.
2. **My hand labels are one interpretation.** I labeled 40 rows myself (Claude Opus 4.7) following the strict reading of the schema. A different labeler would produce different gold; the absolute F1 numbers are calibrated to my interpretation, not an objective ground truth.
3. **40-turn sample.** Statistical noise is non-trivial — at this sample size we can detect ~15-point F1 gaps confidently but not ~3-point ones. The top 4 OS candidates are within 8 points of each other; the ranking *between them* is uncertain. The fact that Gemma 3 12B is **half the cost** of the runner-up is what makes the verdict robust, not the F1 margin.

---

## Candidates (7 total)

| # | Model | Tier | OR slug | Final vs-audit | Final vs-nano | Schema | Latency | Full-devset $ |
|---|---|---|---|---:|---:|---:|---:|---:|
| 0 | `gpt-5.4-nano` | hosted (gold) | `openai/gpt-5.4-nano` | 0.680 | — | 100% | 2.1s | $6.20 |
| 1 | **`gemma-3-12b-it`** ⭐ | OS dense | `google/gemma-3-12b-it` | **0.812** | 0.731 | 100% | 4.9s | **$1.86** |
| 2 | `qwen3.6-35b-a3b` | OS MoE | `qwen/qwen3.6-35b-a3b` | 0.777 | **0.782** | 100% | 3.8s | ~$5–8 |
| 3 | `qwen3.6-27b` | OS dense | `qwen/qwen3.6-27b` | 0.768 | 0.773 | 100% | 4.3s | ~$7–12 |
| 4 | `gemma-4-26b-a4b-it` | OS MoE (4B active) | `google/gemma-4-26b-a4b-it` | 0.753 | 0.769 | 100% | 2.9s | $3.22 |
| 5 | `qwen3.5-9b` | OS dense | `qwen/qwen3.5-9b` | 0.721 | 0.697 | 97.5% | 16.6s | n/a — latency too high |
| 6 | `gemma-3-4b-it` | OS small | `google/gemma-3-4b-it` | 0.666 | 0.656 | 100% | 4.5s | $1.70 |

(Dropped from original user-supplied list during scoping: `Mistral Small 4` — not in proxy, over budget; `Qwen3.5-4B` — not on OR.)

Full per-field tables: [`artifacts/comparison_report.md`](artifacts/comparison_report.md).

---

## Protocol — what actually ran

| Step | Sample | What | Status |
|---|---|---|---|
| 0a | — | Build schema, prompt, sampler, runner, scorer | ✅ |
| 0b | 40 turns (30 multi-turn + 10 cold-start) | Audit gold labeled by Claude Opus 4.7 directly | ✅ |
| 0c | 40 turns | Score `gpt-5.4-nano` vs audit — 0.680 F1, 100% schema | ✅ |
| 1a | 40 turns × 7 models | First smoke screen — `Qwen3.5-9B` failed (reasoning tokens ate `max_tokens`); fixed with `reasoning: {enabled: False}` | ✅ |
| 1b | 40 turns × 7 models | Schema validity round — added `neutral` role to enum + strict json_schema for all models | ✅ |
| 1c | 40 turns × 7 models | Doc-tightening round — clarified `seed` and `referenced_track_ids` to fix over-fire | ✅ |
| 2 | 200 turns | Selection round | **skipped** — Step 1c picked a decisive cost winner; expanding the sample wouldn't change it |
| 3 | 500 turns | Confirm tiebreaker | skipped |

Total bake-off API spend: **~$2.50** (3 full sweeps × 7 models × 40 turns).

---

## Field-weighted scoring

```python
weights = {
    "intent_mode":          2.0,   # gates fusion weights — high impact
    "explicit_rejections":  2.0,   # hard filters — high impact
    "referenced_track_ids": 1.5,   # anchor selection
    "track_feedback":       1.5,   # anchor + post-filter
    "mentioned_entities":   1.0,   # query expansion (recoverable)
    "hard_filters":         1.0,   # release_date only in v0+
    "turn_intent":          0.5,   # entity-recall, not exact match
}
```

Per-field metric:
- Enum fields (`intent_mode`): exact-match accuracy
- List-of-objects (`mentioned_entities`, `track_feedback`, `explicit_rejections`): set-overlap F1 with normalized string match on `.value` (sentiment ignored for `mentioned_entities`)
- ID lists (`referenced_track_ids`, `track_feedback.track_id`): exact-set agreement
- Free text (`turn_intent`): named-entity recall — fraction of positive artist/album/track entities from gold that survive in the predicted text

See [`score.py`](score.py) for the exact implementation.

---

## Files

```
conversation_state_extraction_bakeoff/
├── README.md                  this file — verdict + protocol surface
├── analysis.md                long-form analysis: methodology, iterations, caveats
├── schema.py                  Pydantic v0+ schema — single source of truth
├── prompts.py                 SYSTEM + few-shot + json_schema spec
├── sample_for_labeling.py     emit labeling rows from the test split
├── make_audit_gold.py         build audit_gold.jsonl from Opus's hand-crafted labels (embedded)
├── make_silver_gold.py        convert nano's outputs into a gold file for scoring
├── run_extraction.py          run any model on any labeling/gold file via litellm
├── score.py                   per-field F1 with weighted overall
├── compare_models.py          build comparison_report.md from per-model score files
├── score_all.sh               one-shot: score every candidate, build report
├── dump_for_review.py         pretty-print labeling rows for inspection
└── artifacts/
    ├── labeling_set.jsonl              30 multi-turn rows (seed=0)
    ├── labeling_set_cold_start.jsonl   10 turn-1 rows (seed=1)
    ├── audit_gold.jsonl                40 rows with Opus 4.7 hand labels
    ├── silver_gold_nano.jsonl          40 rows with nano's outputs as gold
    ├── candidate_outputs/              one .jsonl per candidate
    ├── scores/                         per-model and per-model__vs_nano JSON
    └── comparison_report.md            auto-generated leaderboard
```

---

## How to reproduce

### 0. Prerequisites

- Python 3.10+ venv at `.venv` (`uv venv .venv --python=3.10 && source .venv/bin/activate && uv pip install -e .`)
- `OPENROUTER_API_KEY=sk-or-...` in `.env`
- HF auth (`uvx hf auth login`) for dataset loading

### 1. Generate the labeling set

```bash
.venv/bin/python -m experiments.analysis.conversation_state_extraction_bakeoff.sample_for_labeling \
    --n 30 --seed 0 \
    --out experiments/analysis/conversation_state_extraction_bakeoff/artifacts/labeling_set.jsonl

.venv/bin/python -m experiments.analysis.conversation_state_extraction_bakeoff.sample_for_labeling \
    --n 10 --seed 1 --min_turn 1 --max_turn 1 \
    --out experiments/analysis/conversation_state_extraction_bakeoff/artifacts/labeling_set_cold_start.jsonl
```

### 2. Build audit gold

```bash
.venv/bin/python -m experiments.analysis.conversation_state_extraction_bakeoff.make_audit_gold \
    --inputs experiments/analysis/conversation_state_extraction_bakeoff/artifacts/labeling_set.jsonl \
             experiments/analysis/conversation_state_extraction_bakeoff/artifacts/labeling_set_cold_start.jsonl \
    --out    experiments/analysis/conversation_state_extraction_bakeoff/artifacts/audit_gold.jsonl
```

(Labels are embedded in `make_audit_gold.py` as short-form tuples — they're reproducible without re-labeling.)

### 3. Run each candidate

```bash
export $(grep ^OPENROUTER_API_KEY .env)
for model in \
    openai/gpt-5.4-nano \
    openrouter/google/gemma-3-12b-it \
    openrouter/google/gemma-4-26b-a4b-it \
    openrouter/qwen/qwen3.6-27b \
    openrouter/qwen/qwen3.6-35b-a3b \
    openrouter/google/gemma-3-4b-it \
    openrouter/qwen/qwen3.5-9b; do
    slug=$(echo "$model" | tr '/' '-' | sed 's/^openrouter-//')
    .venv/bin/python -m experiments.analysis.conversation_state_extraction_bakeoff.run_extraction \
        --model "$model" \
        --input  experiments/analysis/conversation_state_extraction_bakeoff/artifacts/audit_gold.jsonl \
        --out    "experiments/analysis/conversation_state_extraction_bakeoff/artifacts/candidate_outputs/${slug##google-}.jsonl"
done
```

### 4. Score + report

```bash
./experiments/analysis/conversation_state_extraction_bakeoff/score_all.sh
```

Outputs the leaderboard to [`artifacts/comparison_report.md`](artifacts/comparison_report.md).

---

## Cost accounting

| Step | Calls | Approx $ |
|---|---|---|
| Sweep 1 (initial schema) | 7 × 40 | $0.20 |
| Sweep 2 (neutral role + strict schema) | 7 × 40 | $0.80 |
| Sweep 3 (tightened seed / referenced_track_ids docs) | 7 × 40 | $1.00 |
| Diagnostics (single-call probes for reasoning bug) | ~10 | <$0.01 |
| **Bake-off total** | | **~$2** |
| Full devset run with winner (8k turns × 2 stages) | 16k | **$1.86** |

Budget headroom for the full-devset run: $10 - $1.86 = **$8.14** for retries, ablations, or stage-B explanation generation.
