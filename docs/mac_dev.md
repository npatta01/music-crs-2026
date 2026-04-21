# Mac / Local Dev

Mac configs use MPS + float32 + eager attention (no CUDA). Separate from Linux configs.

## One-time setup

```bash
# Create difficulty-stratified local eval split (3 easy / 3 medium / 3 hard = 9 sessions)
uv run python scripts/create_local_split.py --n_per_tier 3 --seed 42
# saves data/local_eval_split.json (gitignored)

# Generate evaluator ground truth
cd evaluator && python make_ground_truth.py && cd ..
```

## Run inference on the local split

```bash
uv run python run_inference_devset.py \
  --tid llama1b_bm25_devset_mac \
  --batch_size 2 \
  --session_ids_file data/local_eval_split.json
```

## Evaluate

```bash
cp exp/inference/devset/llama1b_bm25_devset_mac.json evaluator/exp/inference/devset/

cd evaluator && python evaluate_devset.py \
  --tid llama1b_bm25_devset_mac \
  --session_ids_file ../data/local_eval_split.json
```

Results saved to `evaluator/exp/scores/devset/{tid}.json`.
