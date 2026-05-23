# Music Conversational Recommendation Challenge — Baselines

Official evaluation framework for the **The RecSys Challenge 2026 Conversational Music Recommendation System Challenge**. Music-CRS focuses on the evolving landscape of music discovery, where static recommendation lists are being replaced by dynamic, conversational interactions. As users increasingly interact with AI through natural language, there is a critical need for systems that can seamlessly integrate Natural Language Understanding (NLU) with high-precision Recommender Systems (RecSys). This challenge aims to push the boundaries of how AI understands nuanced user preferences, explores musical tastes through dialogue, and provides contextually relevant track recommendations.

This repository provides standardized tools to evaluate music recommendation systems on the **TalkPlay Data Challenge** datasets. Participants must follow the strict inference JSON format specified below to ensure their submissions can be properly evaluated.

- **ACM RecSys Website**: [https://www.recsyschallenge.com/](https://www.recsyschallenge.com/)
- **Challenge Website**: [https://nlp4musa.github.io/music-crs-challenge/](https://nlp4musa.github.io/music-crs-challenge/)
- **Challenge datasets**: [talkpl-ai/talkplay-data-challenge](https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge)

## Timeline

| Date | Milestone |
|------|-----------|
| 31 March 2026 | Website online |
| 10 April 2026 | Start RecSys Challenge — Release dataset (Train, Development, Blind A) |
| 15 April 2026 | Submission System Open — Leaderboard live (with Blind A dataset) |
| 15 June 2026 | Blind Dataset B released, Activate submission system for Blind B dataset |
| 30 June 2026 | End RecSys Challenge |
| 6 July 2026 | Final Leaderboard & Winners — EasyChair open for submissions |
| 9 July 2026 | Upload code of the final predictions |
| 20 July 2026 | Paper Submission Due |
| 3 August 2026 | Paper Acceptance Notifications |
| 10 August 2026 | Camera-Ready Papers |
| September 2026 | RecSys Challenge Workshop at ACM RecSys 2026 |

---

## Baseline System

The system operates on a **two-stage pipeline**:
1. **RecSys** — Retrieve candidate tracks matching user preferences
2. **LLM** — Generate a natural language response explaining the recommendations

### Core Components

| Component | Description | Module |
|---|---|---|
| LLM | Generates natural language responses (Llama-3.2-1B-Instruct) | `mcrs/lm_modules/` |
| RecSys | Retrieves relevant tracks via BM25 (sparse) or BERT (dense) | `mcrs/retrieval_modules/` |
| User DB | Stores user profiles (user_id, age, gender, country) | `mcrs/db_user/user_profile.py` |
| Item DB | Contains track metadata (name, artist, album, tags, release date) | `mcrs/db_item/music_catalog.py` |

---

## Challenge Resources

- **Dataset collection**: [TalkPlayData-Challenge](https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge)
- **Conversation Dataset**: [TalkPlayData-Challenge-Dataset](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Dataset)
- **Track Metadata**: [TalkPlayData-Challenge-Track-Metadata](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Track-Metadata)
- **User Profiles**: [TalkPlayData-Challenge-User-Metadata](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-User-Metadata)
- **Blind A Dataset**: [TalkPlayData-Challenge-Blind-A](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Blind-A)
- **Blind B Dataset**: Will be uploaded @ 15 Jun

---

## Quick Start

### Installation

```bash
# Required
uv venv .venv --python=3.10
source .venv/bin/activate
uv pip install -e .
uv pip install -e ".[dev]"   # optional, for pytest-based local verification

# Optional — faster LLM inference (requires CUDA toolkit + compatible gcc)
uv pip install flash-attn --no-build-isolation
```

### Hugging Face Authentication

The datasets and models are hosted on Hugging Face. Log in before running inference:

```bash
uvx hf auth login
```

> **Note:** You will need a Hugging Face account with access to the [TalkPlay Data Challenge](https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge) collection.

> **Note:** The default configs use `attn_implementation: "sdpa"` (PyTorch built-in, no extra install needed). If you successfully install `flash-attn`, you can switch to `attn_implementation: "sdpa"` in your config for a small speed boost.

### Modal Authentication (for cloud GPU runs)

```bash
# Authenticate (opens browser)
uv run python -m modal setup

# Verify setup
uv run modal run other/modal_get_started.py
# Expected: "This code is running on a remote worker! the square is 1764"
```

### Run Experiments

The preferred operator command is the unified experiment wrapper:

```bash
# Local devset run + local evaluation
python run_experiment.py --backend local --tid bm25_devset_retrieval_only_with_tag_list --batch_size 16

# Modal devset run + download into local exp/ + local evaluation
python run_experiment.py --backend modal --tid lancedb_fts_with_tag_list_devset --batch_size 64

# Local dense retriever run
python run_experiment.py --backend local --tid dense_qwen3_embedding_8b_devset --batch_size 16
```

Devset runs write predictions to `exp/inference/devset/{tid}.json` and scores to `exp/scores/devset/{tid}.json`.

The low-level inference scripts remain available when you want to run only one stage:

```bash
# Dev set inference only
python run_inference_devset.py --tid bm25_devset_retrieval_only_with_tag_list --batch_size 16

# Blind set inference requires adding a split-specific config under configs/.
python run_inference_blindset.py --tid my_blindset_A_config --eval_dataset blindset_A --batch_size 16
```

### Run Inference on the Development Set

**⚠️ Note: During inference, the recommender system must always retrieve candidates from the entire track catalog. Do not filter, subset, or restrict tracks using `track_split_types` or any other mechanism!**

For BM25/dense baselines, your config must include:

```yaml
track_split_types:
  - "all_tracks"
```

If you do not use `all_tracks`, your evaluation may be considered invalid.

- Always use `all_tracks` for every experiment and submission.
- Do **not** preprocess, filter, or use only a subset of tracks during inference.


```bash
# BM25 baseline
python run_experiment.py --backend local --tid bm25_devset_retrieval_only_with_tag_list --batch_size 16

# Dense retriever
python run_experiment.py --backend local --tid dense_qwen3_embedding_8b_devset --batch_size 16
```

Results are saved under `exp/`.

Rewrite-based QU experiments may also emit sidecars alongside the prediction file:

- `exp/inference/devset/{tid}_rewrite_audit.jsonl`
- `exp/inference/devset/{tid}_rewrite_stats.json`

To pull Modal-run artifacts back to your machine, use the bulk downloader:

```bash
# Download one run (predictions, traces, and scores if present)
python modal/download_results.py --tid bm25_devset_retrieval_only_with_tag_list

# Sync all missing artifacts from the Modal volume into evaluator/exp/
python modal/download_results.py

# Preview planned downloads and byte counts
python modal/download_results.py --dry-run --verbose
```

If you are using Codex with this repo, the `download-artifacts` skill wraps the same workflow and defaults to syncing into `evaluator/exp`.

The downloader defaults to `evaluator/exp/` and mirrors any available remote:

- `inference/<split>/<tid>.json`
- `inference/<split>/<tid>_rewrite_audit.jsonl`
- `inference/<split>/<tid>_rewrite_stats.json`
- `scores/<split>/<tid>.json`
- `ground_truth/...`

### Run Inference on Blind Sets (for submission)

```bash
# Add a split-specific config in configs/ first, then pass the blindset explicitly.
python run_experiment.py --backend local --tid my_blindset_A_config --eval_dataset blindset_A --batch_size 16
```

---

## Custom Configuration

Create a config file in `configs/`:

```yaml
# configs/my_model.yaml
lm_type: "Qwen/Qwen3-4B" # change llama to qwen3
retrieval_type: "bm25"
qu_type: "passthrough"
test_dataset_name: "talkpl-ai/TalkPlayData-Challenge-Dataset"
item_db_name: "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
user_db_name: "talkpl-ai/TalkPlayData-Challenge-User-Metadata"
track_split_types:
  - "all_tracks"
user_split_types:
  - "all_users"
corpus_types:
  - "track_name"
  - "artist_name"
  - "album_name"
  - "release_date"
cache_dir: "./cache"
device: "cuda"
attn_implementation: "sdpa"
```

Then run with your config:

```bash
python run_experiment.py --backend local --tid my_model --eval_dataset devset
```

For retrieval-only Wave 3 rewrite experiments, use `lm_type: "dummy"` and move the rewrite model into `qu_kwargs`:

```yaml
lm_type: "dummy"
retrieval_type: "bm25"
qu_type: "llm_rewrite"
qu_kwargs:
  model_name: "HuggingFaceTB/SmolLM2-1.7B-Instruct"
  prompt_name: "preserve_entities_v1"
  max_new_tokens: 96
  audit_path: "./exp/inference/devset/<tid>_rewrite_audit.jsonl"
  stats_path: "./exp/inference/devset/<tid>_rewrite_stats.json"
corpus_types:
  - "track_name"
  - "artist_name"
  - "album_name"
  - "tag_list"
```

---

## Evaluation

For evaluation, please refer to: https://github.com/nlp4musa/music-crs-evaluator

---

## Tips & Extensions

See `./tips/` for advanced techniques. Some directions to explore:

- **Improve Item Representation** — Add audio features or use stronger embedding models
- **Add a Reranker Module** — Implement two-stage ranking with LLM or embedding-based rerankers
- **Generative Retrieval** — Use semantic IDs for end-to-end track generation

---

Good luck with the challenge!
