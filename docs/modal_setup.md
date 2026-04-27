# Modal Setup

[Modal](https://modal.com) is used to run inference on cloud GPUs.

## Authenticate

```bash
uv run python -m modal setup
```

This opens a browser for OAuth. After completing it, your token is saved to `~/.modal.toml`.

## Verify setup

Run the smoke test to confirm your token works and a remote worker spins up:

```bash
uv run modal run other/modal_get_started.py
```

Expected output:

```
This code is running on a remote worker!
the square is 1764
```

---

## Cloud Pipeline

### One-time setup

Add your HF token to a `.env` file in the project root (already in `.gitignore`):

```
HF_TOKEN=hf_...
```

Modal reads this automatically via `modal.Secret.from_dotenv()`. Volumes are created automatically on first run — no manual setup needed. Volume names and container paths are configured in `modal/config.yaml`.

---

### Run inference

**Smoke test (5 random sessions, fast)**

```bash
modal run modal/app.py::run_inference --num-sessions 5
```

**Full devset**

```bash
modal run modal/app.py::run_inference --tid llama1b_bm25_devset --batch-size 16
```

**Blindset (submission)**

```bash
modal run modal/app.py::run_inference_blindset --tid llama1b_bm25_blindset_A
```

The second run skips re-downloading model weights — HF model cache is persisted in the `music-crs-hf-cache` volume.

---

### Run evaluation

After inference completes, score the predictions on CPU:

```bash
modal run modal/app.py::run_evaluate --tid llama1b_bm25_devset
```

Prints NDCG@1/10/20 and catalog diversity. Scores are written to the `music-crs-results` volume at `scores/devset/{tid}.json`.

You can also run evaluation locally using the evaluator submodule directly:

```bash
# First initialise the submodule if you haven't already
git submodule update --init evaluator

# Generate ground truth once
python evaluator/make_ground_truth.py

# Score predictions
python evaluator/evaluate_devset.py --tid llama1b_bm25_devset
```

---

### Download results locally

Use the repo downloader to mirror artifacts from the Modal volume into local `evaluator/exp/` by default.

```bash
# Download one run (legacy usage still works)
python modal/download_results.py --tid llama1b_bm25_devset

# Download all missing remote artifacts
python modal/download_results.py

# Preview what would be downloaded first
python modal/download_results.py --dry-run --verbose

# Restrict to scores only
python modal/download_results.py --kind scores
```

The downloader mirrors the remote artifact tree under your chosen `--out-dir`:

- `inference/<split>/<tid>.json`
- `inference/<split>/<tid>_rewrite_audit.jsonl`
- `inference/<split>/<tid>_rewrite_stats.json`
- `scores/<split>/<tid>.json`
- `ground_truth/...`

If remote `scores/` or `ground_truth/` directories do not exist yet, the downloader skips them cleanly.
