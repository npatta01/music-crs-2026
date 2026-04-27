# Music-CRS

RecSys Challenge 2026 baseline — conversational music recommendation system. Given a multi-turn conversation, retrieve 20 tracks from a 47k-track catalog and generate a natural language response.

Challenge: https://nlp4musa.github.io/music-crs-challenge/

## Docs

- [Data](docs/data.md) — dataset schemas, splits, sample rows, inference output format
- [Baseline Architecture](docs/architectures/baseline.md) — pipeline, retrieval modules, LLM module, config
- [Evaluation](docs/evaluation.md) — metrics, devset leaderboard
- [Mac / Local Dev](docs/mac_dev.md) — local testing on Apple Silicon
- [Modal Setup](docs/modal_setup.md) — cloud GPU authentication and smoke test

## Setup

```bash
uv venv .venv --python=3.10
source .venv/bin/activate
uv pip install -e .
uvx hf auth login   # HF access required for datasets + Llama
```

## Run

```bash
# Dev set
python run_inference_devset.py --tid llama1b_bm25_devset --batch_size 16

# Blind set A (submission)
python run_inference_blindset.py --tid llama1b_bm25_blindset_A --eval_dataset blindset_A --batch_size 16

# Package submission
bash prepare_submission.sh
```

Results saved to `exp/inference/{split}/{tid}.json`.

## Extend

See `tips/` for directions: better item representations, reranker modules, generative retrieval.

## Skills

- `download-artifacts` — sync Modal prediction artifacts, rewrite traces, scores, and ground-truth files into `evaluator/exp` using `python modal/download_results.py`
- `run-experiment` — run a Modal experiment end-to-end, download results locally, and evaluate devset runs
