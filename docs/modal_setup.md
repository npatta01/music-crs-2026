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

**1. Create persistent volumes**

```bash
modal volume create music-crs-hf-cache   # HF model weights (Llama, BERT)
modal volume create music-crs-results    # Inference outputs + scores
```

**2. Add HF token to `.env`**

Create a `.env` file in the project root (already in `.gitignore`):

```
HF_TOKEN=hf_...
```

Modal reads this automatically via `modal.Secret.from_dotenv()` — no manual `hf auth login` inside the container.

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

The second run will skip re-downloading model weights — HF cache is persisted in the `music-crs-hf-cache` volume.

---

### Run evaluation

After inference completes, score the predictions on CPU:

```bash
modal run modal/app.py::run_evaluate --tid llama1b_bm25_devset
```

Prints NDCG@1/10/20 and catalog diversity. Scores are also written to the `music-crs-results` volume at `scores/devset/{tid}.json`.

---

### Download results locally

Pull a predictions file or scores file from the volume to your local `exp/` directory:

```bash
# Download inference predictions
python modal/download_results.py --tid llama1b_bm25_devset

# Download evaluation scores
python modal/download_results.py --tid llama1b_bm25_devset --type scores
```
