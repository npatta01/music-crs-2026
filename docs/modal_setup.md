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

### Run experiments

**Smoke test (5 random sessions, fast)**

```bash
python run_experiment.py --backend modal --tid llama1b_bm25_devset --num_sessions 5
```

**Full devset**

```bash
python run_experiment.py --backend modal --tid llama1b_bm25_devset --batch_size 16
```

**Blindset (submission)**

```bash
python run_experiment.py --backend modal --tid llama1b_bm25_blindset_A --eval_dataset blindset_A --batch_size 16
```

The wrapper runs Modal inference, downloads artifacts back into your local `exp/` tree, and evaluates devset runs locally. The second Modal run skips re-downloading model weights because the HF cache is persisted in the `music-crs-hf-cache` volume.

---

### LanceDB CPU retrieval

LanceDB FTS runs do not need a GPU. Build the DB locally, upload it to the `music-crs-models` volume, then run the CPU Modal path:

```bash
uv run python scripts/build_lancedb_index.py --out-dir cache/lancedb --drop-existing
uv run modal run modal/app.py::upload_lancedb_index --local-db-dir cache/lancedb --remote-dir lancedb
python run_experiment.py --backend modal --tid lancedb_fts_with_tag_list_devset --num_sessions 5
```

The same local build/upload/smoke flow is available as
`notebooks/05_lancedb_indexing.ipynb`; the notebook calls the checked-in scripts
and Modal entrypoints rather than embedding indexing logic in notebook cells.

The default LanceDB build stores precomputed track embedding columns too. The
current FTS config still queries only sparse text fields; use `--metadata-only`
on `scripts/build_lancedb_index.py` only when you explicitly want a smaller
sparse-only DB artifact.

The wrapper materializes a deterministic session-id subset for `--num_sessions`, so inference and local evaluation use the same smoke rows.

The LanceDB CPU resource sizes live in `modal/config.yaml`. Current defaults request 8 CPU / 32 GiB for full inference and 4 CPU / 16 GiB for the private query endpoint.

For a private Modal SDK query smoke after deployment:

```bash
uv run modal deploy modal/app.py
uv run python scripts/smoke_lancedb_modal_query.py --query "dark atmospheric synthwave" --topk 20
```

---

### Advanced manual commands

If you want to bypass the unified wrapper, the underlying Modal entrypoints are still available:

```bash
modal run modal/app.py::run_inference --tid llama1b_bm25_devset --batch-size 16
modal run modal/app.py::run_inference_blindset --tid llama1b_bm25_blindset_A --batch-size 16 --eval-dataset blindset_A
```

---

### Download results locally

Use the repo downloader to mirror artifacts from the Modal volume into a chosen local output directory. The unified wrapper uses `exp/`.

```bash
# Download one run into exp/
python modal/download_results.py --tid llama1b_bm25_devset --out-dir exp

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
