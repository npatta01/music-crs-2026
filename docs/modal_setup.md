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

You can also run evaluation locally against a downloaded predictions file:

```bash
python run_evaluate.py --tid llama1b_bm25_devset
```

---

### Download results locally

Pull a predictions file or scores file from the volume to your local `exp/` directory:

```bash
# Download inference predictions
music-download --tid llama1b_bm25_devset

# Download evaluation scores
music-download --tid llama1b_bm25_devset --type scores
```
