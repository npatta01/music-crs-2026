# Mac / Local Dev

Mac local runs can use the CPU-compatible retrieval-only configs in `configs/`.

## One-time setup

```bash
# Create difficulty-stratified local eval split (3 easy / 3 medium / 3 hard = 9 sessions)
uv run python scripts/create_local_split.py --n_per_tier 3 --seed 42
# saves data/local_eval_split.json (gitignored)
```

## Run the local split

```bash
uv run python run_experiment.py \
  --backend local \
  --tid v0plus_compiler_all_retrievers_devset \
  --batch_size 2 \
  --exp_dir exp \
  --session_ids_file data/local_eval_split.json
```

The wrapper will run inference, generate ground truth in `exp/ground_truth/` if needed, and write scores to `exp/scores/devset/{tid}.json`.
