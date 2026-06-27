# Reproducing the anchoring-fix labels from scratch

This rebuilds `train_labels_full.jsonl` (106,393 turns) and the dev set
(7,000 turns) end-to-end. **You do not need to re-run this to *use* the data** —
download it from the release (see `README.md`). This is for regenerating or
extending it.

The pipeline, per `(session, turn)`:

```
build sheet ─▶ 2 cheap judges (Gemma + DeepSeek) ─▶ compose (find conflicts)
           ─▶ Opus arbiter on conflicts ─▶ merge ─▶ compose --arbiter ─▶ final_labels
```

---

## 1. Prerequisites

| Need | How |
|---|---|
| Repo + Python env | `uv venv .venv --python=3.10 && source .venv/bin/activate && uv pip install -e .` |
| HF access to the dataset | `uvx hf auth login` (the `talkpl-ai/TalkPlayData-Challenge-Dataset` is gated) |
| **DeepInfra API key** (the two cheap judges) | `export DEEPINFRA_API_KEY=...` or put it in `<repo>/.env` |
| **`doc_corpus.jsonl`** (catalog: `{track_id, artist, title, doc}`, ~23 MB) | Lands at `exp/analysis/retrieval_exploration/doc_corpus.jsonl`. It's in the shared cache (`scripts/setup_worktree_cache.py`); it's derived from `talkpl-ai/TalkPlayData-Challenge-Track-Metadata` and is what makes `same_artist` deterministic. |
| **The Opus arbiter** | Runs as the Claude Code `anchor-arbiter` subagent. No Claude Code? See [§5](#5-running-the-arbiter-without-claude-code). |

Set a couple of shell vars used below:

```bash
PY=.venv/bin/python
DATA=exp/analysis/retrieval_exploration          # all artifacts live under here
```

The scripts default their artifacts dir to `<repo>/exp/analysis/retrieval_exploration`.
To point them at a different location (e.g. a shared cache shared across worktrees),
export `ANCHOR_DATA_DIR` and it overrides the default everywhere:

```bash
export ANCHOR_DATA_DIR="$PWD/$DATA"     # or an absolute path to a shared cache
```

> **Cost & time (full train):** ~$33 of DeepInfra for the two cheap judges
> (heavily cached on re-run) + the Opus arbiter (~14M tokens ≈ the bulk of the
> spend; ran on a Claude plan + usage credits). Wall-clock a few hours, mostly
> the arbiter.

---

## 2. Build the judge-ready sheet

```bash
# TRAIN — writes $DATA/judge_bakeoff/sheet_full_train.jsonl
$PY scripts/rerank/anchor_labels/build_anchor_universe.py --split train --expand-all

# DEV (this project's "test" split) — override the train-named defaults
$PY scripts/rerank/anchor_labels/build_anchor_universe.py --split test --expand-all \
    --out-universe   $DATA/anchor_universe_test.jsonl \
    --out-sample     $DATA/judge_bakeoff/sheet_strat2k_test.jsonl \
    --out-full       $DATA/judge_bakeoff/sheet_full_test.jsonl
```

A turn is **labelable** iff a track was played at `tn` AND `assessment[tn+1]` is
non-null (off-by-one: `assessment[tn+1]` grades `track[tn]`; the last track per
session is unlabeled). Each sheet row carries: `sid, tn, gt_label, request`
(full conversation, assistant replies stripped, `[system played: …]` markers
kept), `track_meta` (the candidate doc), and `same_artist` (deterministic).

## 3. Slice into batches of whole sessions

```bash
$PY scripts/rerank/anchor_labels/batch_sheet.py \
    --sheet $DATA/judge_bakeoff/sheet_full_train.jsonl \
    --out-dir $DATA/labels_train/batches --sessions-per-batch 1000
# -> batch_00.jsonl ... batch_15.jsonl (sessions kept intact, deterministic)
```

(For dev it's a single batch; you can skip batching and point step 4 at
`sheet_full_test.jsonl` directly, writing into `$DATA/labels_test/`.)

## 4. Label one batch end-to-end

Do this for each `batch_NN`; `B=$DATA/labels_train/b00`, `SHEET=$DATA/labels_train/batches/batch_00.jsonl`:

```bash
mkdir -p $B

# 4a. two cheap judges (DeepInfra, via LiteLLM). Cached + resumable.
$PY scripts/rerank/anchor_labels/judge_anchor_content.py --base https://api.deepinfra.com/v1/openai \
    --key-env DEEPINFRA_API_KEY --model google/gemma-4-26B-A4B-it --concurrency 64 \
    --sheet $SHEET --out $B/records_gemma.jsonl
$PY scripts/rerank/anchor_labels/judge_anchor_content.py --base https://api.deepinfra.com/v1/openai \
    --key-env DEEPINFRA_API_KEY --model deepseek-ai/DeepSeek-V4-Flash --concurrency 64 \
    --sheet $SHEET --out $B/records_deepseek.jsonl

# 4b. compose -> finds the ~16% of turns where the two judges DISAGREE
$PY scripts/rerank/anchor_labels/compose_labels.py --split train \
    --judge1 $B/records_gemma.jsonl --j1-name gemma \
    --judge2 $B/records_deepseek.jsonl --j2-name deepseek_v4_flash \
    --sheet $SHEET --out-dir $B
# -> $B/conflicts_sheet.jsonl  (turns needing the arbiter)

# 4c. chunk the conflicts for the arbiter (~150 rows/chunk fits an Opus context)
$PY scripts/rerank/anchor_labels/run_arbiter.py chunk \
    --conflicts $B/conflicts_sheet.jsonl --work-dir $B/arbiter --size 150
# -> chunk_000.jsonl ...  AND prints the exact Agent calls to run next

# 4d. >>> run the Opus anchor-arbiter once per chunk <<<  (see §5)
#     each reads chunk_00N.jsonl, writes arb_00N.json keyed by "sid|tn"

# 4e. merge the chunk verdicts + VERIFY full coverage (must be MISSING: 0)
$PY scripts/rerank/anchor_labels/run_arbiter.py merge \
    --conflicts $B/conflicts_sheet.jsonl --work-dir $B/arbiter --out $B/arbiter.json

# 4f. final compose, now with the arbiter verdicts folded in
$PY scripts/rerank/anchor_labels/compose_labels.py --split train \
    --judge1 $B/records_gemma.jsonl --j1-name gemma \
    --judge2 $B/records_deepseek.jsonl --j2-name deepseek_v4_flash \
    --sheet $SHEET --arbiter $B/arbiter.json --out-dir $B
# -> $B/final_labels.jsonl   (expect: 7000 turns, 0 dropped, 0 unresolved)
```

**If step 4e reports `MISSING: N`** (an arbiter chunk dropped rows): write the
missing rows to `chunk_fix.jsonl`, run one more arbiter pass on it → `arb_fix.json`,
then re-run 4e + 4f. `0 dropped / 0 unresolved` is the bar for every batch.

## 5. Running the arbiter without Claude Code

The arbiter is just an **Opus** call with a fixed system prompt — the file
`.claude/agents/anchor-arbiter.md` *is* that prompt. It reads a chunk of
conflict turns and returns, per turn, the two axes:

```json
{ "<sid>|<tn>": { "asked_diff": true/false, "content": "valid|invalid|unsure" }, ... }
```

- **With Claude Code (how this was built):** spawn the `anchor-arbiter` subagent
  once per chunk — `run_arbiter.py chunk` prints the exact `Agent` calls
  (`subagent_type='anchor-arbiter'`, INPUT=chunk_00N.jsonl, OUTPUT=arb_00N.json).
  Cost lands on your Claude plan, not a paid API.
- **Without Claude Code:** loop the chunks yourself against the Messages API
  (`claude-opus-4-8`), using the body of `anchor-arbiter.md` as the system prompt
  and each chunk line as input; write the `{sid|tn: {asked_diff, content}}` JSON
  to `arb_00N.json`. `compose_labels.py --arbiter` accepts either that `.json`
  map or a `.jsonl` of records. (Sonnet works too at lower cost — it only sees
  the ~16% the cheap judges disagree on.)

## 6. Assemble the full set

After all 16 batches pass step 4:

```bash
$PY - <<'EOF'
import json, glob
rows, seen = [], set()
for f in sorted(glob.glob("exp/analysis/retrieval_exploration/labels_train/b[01][0-9]/final_labels.jsonl")):
    for line in open(f):
        r = json.loads(line); k = (r["sid"], r["tn"])
        if k not in seen: seen.add(k); rows.append(r)
rows.sort(key=lambda r: (r["sid"], r["tn"]))
open("train_labels_full.jsonl", "w").write("".join(json.dumps(r)+"\n" for r in rows))
print(len(rows), "turns")     # 106393
EOF
```

## 7. How the labels are composed (the rules)

| label | reason | rule |
|---|---|---|
| **NEGATIVE** | `artist_anchoring` | `asked_for_different_artist` AND `same_artist` — **even if reaction was MOVES** |
| **NEGATIVE** | `content_violation` | `content_fit == invalid` |
| **POSITIVE** | `fits_and_liked` | `content_fit == valid` AND reaction MOVES |
| **DROP** | `fit_but_disliked` | `content_fit == valid` AND reaction DOES_NOT |
| **HOLD** | `unverifiable` | `content_fit == unsure` |

`anchoring := asked_for_different_artist (LLM) AND same_artist (deterministic
catalog match)`. Judges agree → `confidence_weight` 1.0 (HOLD 0.3); arbiter → 0.6.

## 8. Gotchas worth knowing

- **Caching:** `judge_anchor_content.py` caches every judgment under
  `$DATA/anchor_content_cache/`. Re-runs are near-instant and only call uncached
  rows — cheap to resume after an interruption. The cache key folds in the prompts
  + schema, so editing a prompt correctly invalidates it.
- **Concurrency:** `--concurrency 64–128` was stable on DeepInfra (~46 calls/s, no
  rate-limiting).
- **0 dropped is the bar:** grammar-constrained JSON can occasionally stutter; the
  judge retries in plain-JSON mode so rows recover instead of dropping. Always
  confirm `0 dropped — a judge errored` and `MISSING: 0` per batch.
- **Arbiter robustness:** if the orchestrator restarts mid-run, in-flight subagent
  chunks are lost — just re-run the chunks whose `arb_*.json` is missing; `merge`'s
  coverage check tells you which.
- **Split flag must match:** `compose_labels.py --split` must be `train` for train
  sheets, `test` for the dev sheet (it asserts session ids are in that index).

See `DATASET_CARD.md` for the schema + two-tower training recipe, and
`reports/` for the visual walkthroughs.
