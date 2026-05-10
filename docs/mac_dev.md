# Mac / Local Dev

Mac configs use MPS + float32 + eager attention (no CUDA). Separate from Linux configs.

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
  --tid llama1b_bm25_devset_mac \
  --batch_size 2 \
  --exp_dir exp \
  --session_ids_file data/local_eval_split.json
```

The wrapper will run inference, generate ground truth in `exp/ground_truth/` if needed, and write scores to `exp/scores/devset/{tid}.json`.
