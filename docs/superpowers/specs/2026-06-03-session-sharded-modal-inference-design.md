# Autorun Modal experiments with session-sharded inference

**Issue:** [#99](https://github.com/npatta01/music-conversational-music-recomender-2026/issues/99)
**Date:** 2026-06-03

## Goal

Support parallel session-sharded Modal inference from the normal experiment
wrapper (`run_experiment.py`), for both devset and blindset, without limiting it
to devset. The heavy work is already outsourced to retrieval / embedding / model
services, so the sharded API is **split-oriented and session-oriented**, not
resource-flavor-oriented. Resource profile (GPU vs CPU) stays an internal detail
of the orchestrator.

## Desired UX

Devset:

```bash
uv run python run_experiment.py \
  --backend modal \
  --tid v0plus_compiler_all_retrievers_devset \
  --batch_size 64 \
  --num_shards 5
```

Blindset:

```bash
uv run python run_experiment.py \
  --backend modal \
  --tid v0plus_compiler_blindset_A \
  --eval_dataset blindset_A \
  --batch_size 64 \
  --num_shards 5
```

Retry/resume with an explicit run id:

```bash
uv run python run_experiment.py \
  --backend modal \
  --tid v0plus_compiler_blindset_A \
  --eval_dataset blindset_A \
  --batch_size 64 \
  --num_shards 5 \
  --run_id 20260603T074512Z-a3f91c
```

## Decisions (confirmed)

1. **`--num_sessions` + `--num_shards > 1` → reject** with a clear error.
2. **Local backend + `--num_shards > 1` → reject** (sharding is Modal-only;
   local sharding gives no parallelism).
3. **Replace** the existing devset-only `modal/app.py::run_inference_sharded`
   with the generic signature.

## Architecture

A sharded run is orchestrated entirely from `run_experiment.py`:

```
run_experiment.py (--backend modal --num_shards N [--run_id ...])
  ├─ generate run_id = {UTC}-{hex6}  (or use --run_id override)
  ├─ modal run modal/app.py::run_inference_sharded
  │       (tid, eval_dataset, num_shards, run_id, batch_size, clear_cache)
  │     └─ spawn N internal workers in parallel
  │          (gpu OR cpu chosen internally via _tid_uses_cpu)
  │            └─ run_inference_{devset,blindset}.py
  │                   --num_shards N --shard_id k
  │                   --output_suffix .run_{run_id}.shard_k
  │                   (session-partition slice, then turn expansion)
  ├─ modal/download_results.py   (run-scoped shard selection for base tid)
  ├─ scripts/merge_shard_results.py --run_id ...  → canonical {tid}.json (+ _trace.json)
  └─ devset:  ensure ground truth → evaluate {tid}.json
     blindset: stop after merge (no blindset evaluator)
```

### Invariant

Correct: `session partition -> turn expansion -> inference`.
Incorrect: `flattened session-turn rows -> shard partition`.

Sharding slices the **session list** (the dataset rows, each row = one session)
by contiguous index: shard `k` gets sessions `[k*T/N, (k+1)*T/N)`. Turn
expansion (devset turns 1..8) happens **inside** each shard, after the partition,
so all turns of a session always land in the same shard. This already holds for
`run_inference_devset.py` and will be mirrored in `run_inference_blindset.py`.

## Run ID / Artifact Naming

One run id generated at the start of a sharded run, passed to all shards.

```
run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
# e.g. 20260603T074512Z-a3f91c
```

Shard outputs are run-scoped (via `--output_suffix .run_{run_id}.shard_{k}`):

```
inference/{split}/{tid}.run_{run_id}.shard_0.json
inference/{split}/{tid}.run_{run_id}.shard_1.json
inference/{split}/{tid}.run_{run_id}.shard_0_trace.json   (devset only)
...
```

After successful merge, write the canonical output (this is what the evaluator
and leaderboard consume):

```
inference/{split}/{tid}.json
inference/{split}/{tid}_trace.json   (devset only)
```

Run-id naming makes stale shard files from previous runs harmless — the merge
only ever reads the current run's shard set.

## Component changes

### `run_experiment.py`

- Add `--num_shards` (int, default `1`) and `--run_id` (str, optional).
- `make_run_id()` helper producing `{UTC}-{hex6}`.
- `validate_args` additions:
  - `num_shards < 1` → `ValueError`.
  - `num_shards > 1` and `backend != modal` → `ValueError` (Modal-only).
  - `num_shards > 1` and `num_sessions` → `ValueError` (reject the combination).
  - `--run_id` provided while `num_shards == 1` → `ValueError` (only meaningful
    for sharded runs).
- `num_shards == 1` preserves **exactly** today's behavior (existing `run_local`
  / `run_modal` code paths unchanged).
- New `run_modal_sharded(args, split, exp_dir)`:
  1. `run_id = args.run_id or make_run_id()`.
  2. `modal run modal/app.py::run_inference_sharded --tid ... --eval-dataset {split}
     --num-shards N --run-id ... --batch-size ... [--clear-cache]`.
  3. `modal/download_results.py --tid {tid} --split {split} --run-id {run_id}
     --out-dir {exp_dir}`.
  4. `scripts/merge_shard_results.py --tid {tid} --num_shards N --run_id {run_id}
     --split {split} --exp-dir {exp_dir}`.
  5. devset: `ensure_ground_truth` → `run_evaluation`. blindset: stop.
  - The run_id is printed so a failed run can be retried with `--run_id`.

### `modal/app.py`

- **Replace** `run_inference_sharded` with:
  `run_inference_sharded(tid, eval_dataset="devset", num_shards=4, run_id="",
  batch_size=..., clear_cache=False)`.
  - Requires a non-empty `run_id` (the wrapper always passes one).
  - Picks gpu vs cpu worker internally via `_tid_uses_cpu(tid)`.
  - Dispatches to the devset or blindset worker based on `eval_dataset`
    (`devset` → devset worker; anything else → blindset worker).
  - Keeps the existing resilient spawn → join → retry-once → fail-loud logic.
  - `output_suffix = f".run_{run_id}.shard_{shard_id}"`.
- Internal workers: extend the blindset workers (`_inference_blindset`,
  `_inference_blindset_cpu`) to accept `num_shards`, `shard_id`, `output_suffix`
  and forward them, mirroring the devset workers. No new split-flavored *sharded*
  entrypoints are exposed — only the one generic `run_inference_sharded`.

### `run_inference_blindset.py`

- Add `--num_shards`, `--shard_id`, `--output_suffix` (mirroring
  `run_inference_devset.py`), read defensively with `getattr` for programmatic
  callers.
- Shard by session via contiguous index slice of the dataset rows (each row is
  one session; blindset uses only the last turn). Output filename becomes
  `{tid}{output_suffix}.json`.

### `scripts/merge_shard_results.py`

- Add `--run_id`. Shard paths become
  `{tid}.run_{run_id}.shard_{k}{kind}.json`.
- Require **exactly** shards `{0..num_shards-1}` for that run_id; fail loudly
  (`FileNotFoundError`) if any expected shard file is missing.
- Predictions are always merged. Traces are merged only when present (blindset
  has no `_trace.json`); skip the trace kind gracefully if no shard has one.
- Canonical outputs: `{tid}.json` (+ `{tid}_trace.json` for devset).

### `modal/download_results.py`

- Recognize run-scoped shard files and map them to the base `{tid}` so a
  `--tid {tid}` selection pulls the run's shard set:
  - `{tid}.run_{run_id}.shard_{k}.json` → kind `inference`, tid `{tid}`.
  - `{tid}.run_{run_id}.shard_{k}_trace.json` → kind `trace`, tid `{tid}`.
- Add an optional `--run-id` filter so only the current run's shards download
  (avoids pulling stale shards from prior runs of the same tid).

## Error handling

- Any shard failing after one retry → `run_inference_sharded` raises, so the
  wrapper aborts before download/merge (no partial canonical output).
- Merge requires the full shard set for the run_id and fails loudly otherwise.
- The generated run_id is surfaced to the user so an incomplete run can be
  re-run with `--run_id` (re-running overwrites that run's shard files; merge
  then sees a complete set).
- No destructive cleanup of old Modal volume files — run_id naming makes old
  files inert.

## Testing (TDD)

Unit tests, mocking `run_command` / subprocess (no real Modal):

- **`run_experiment.py` command construction:**
  - Modal + `--num_shards 5` → builds `run_inference_sharded` command with
    `--num-shards 5`, `--eval-dataset`, and a generated `--run-id`.
  - Modal + default `num_shards == 1` → current single-run commands unchanged.
  - Sharded devset → download (run-scoped) → merge → ground truth → evaluate.
  - Sharded blindset → download → merge, **no** evaluate.
- **run_id:** generated form matches `^\d{8}T\d{6}Z-[0-9a-f]{6}$`; `--run_id`
  override is threaded verbatim to entrypoint, download, and merge.
- **Validation:** local + `num_shards > 1` rejected; `num_sessions` + sharding
  rejected; `--run_id` with `num_shards == 1` rejected.
- **merge:** requires matching run_id; fails loudly when a shard file is missing;
  blindset path merges predictions without requiring traces.
- **download:** run-scoped shard files map to base tid; `--run-id` filters to the
  current run.
- **shard partition:** all 8 turns of a devset session stay in one shard
  (extends the existing partition coverage test).

## Out of scope

- A blindset evaluator (none exists; blindset stops after merge).
- Local parallel sharding.
- Changing resource profiles / GPU policy beyond keeping them internal.
