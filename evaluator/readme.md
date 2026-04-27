# Music CRS Evaluator

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

## Overview

The evaluation framework computes two categories of metrics:

- **Retrieval Metrics** — nDCG@{1, 5, 10, 20, 50, 100, 200, 500, 1000} and
  Hit@{1, 5, 10, 20, 50, 100, 200, 500, 1000}, plus MRR, MRR@{100,200,500,1000},
  mean/median rank-of-GT, and % GT not in top-{20,100,200,500,1000}.
  nDCG@{1, 10, 20} remain the **headline** numbers used for leaderboard comparison;
  the rest are dev-set diagnostics.
- **Diversity Metrics** — catalog coverage (@20 and @100) and Distinct-2 lexical diversity.
- **Per-turn breakdown** — NDCG@20 / Hit@20 / Hit@100 split by turn 1–8 so you can
  spot turn-specific degradation.

For the deep-cutoff diagnostics to be meaningful, the prediction file must contain
>= 1000 ranked ids per turn. The evaluator now fails explicitly when a dev-set
prediction row is too shallow for these metrics instead of silently truncating the
metric definition. Submission files stay at top-20; dev-set inference can retrieve deeper.

## Setup

### Requirements

- Python 3.10+
- Dependencies: `datasets`, `pandas`, `numpy`, `scipy`, `tqdm`

### Installation

```bash
uv venv .venv --python=3.10
source .venv/bin/activate
uv pip install -r requirments.txt
```

## Quick Start

> **Note — Blind Set Evaluation:**

> Blind set (Blind A / Blind B) evaluation is **not supported** in this repository.

> Submit your predictions to the official leaderboard on **[CodaBench](https://www.codabench.org/)** for blind set scoring.

> Full evaluation on blind sets includes additional metrics that are kept server-side to prevent leakage.

> This repository currently only supports evaluation on the development dataset. For blind set evaluation, please refer to the official baseline code or submit your predictions to the leaderboard as described above.

### 1. Prepare Ground Truth

Before running evaluation, generate the ground truth file for the development set:

```bash
python make_ground_truth.py
```

This saves ground truth to `exp/ground_truth/talkpl_ai_talkplaydata_challenge_dataset/test.json`.

### 2. Place Your Predictions

Save your inference file to:
```
exp/inference/devset/<tid>.json
```

### 3. Run Evaluation

```bash
python evaluate_devset.py --eval_dataset devset --tid <tid>
```

This will:
- Load predictions from `exp/inference/devset/<tid>.json`
- Load ground truth for the development set
- Compute headline and deep-cutoff retrieval diagnostics through `@1000`
- Compute catalog and lexical diversity
- Save macro-averaged results to `exp/scores/devset/<tid>.json`

For more baselines, see: [nlp4musa/music-crs-baselines](https://github.com/nlp4musa/music-crs-baselines)


## Inference JSON Format

**IMPORTANT:** Participants must strictly follow this JSON format for their predictions.

Your inference results must be saved as a JSON file under `exp/inference/<eval_dataset>/<tid>.json` (e.g. `exp/inference/devset/my_model_devset.json`) with the following structure:

```json
[
  {
    "session_id": "69137__2020-02-08",
    "user_id": "69137",
    "turn_number": 1,
    "predicted_track_ids": [
      "715f8aff-7c99-46b8-8f9d-6d1aa1ae0372",
      "73562c63-02e3-4278-baf3-aeb3252f8b33",
      "4302b6cf-afe4-45d9-ab72-bd477086d838",
      "f20c5819-a312-4a6d-9ad1-46deccb4ff2f"
    ],
    "predicted_response": "Here are some songs you might enjoy."
  }
]
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `string` | Unique session identifier (format: `{user_id}__{date}`) |
| `user_id` | `string` | Unique user identifier |
| `turn_number` | `int` | Conversation turn number (1–8) |
| `predicted_track_ids` | `list[string]` | **Ordered** list of predicted track IDs (submission files use 20; dev-set diagnostics can use deeper pools such as 1000) |
| `predicted_response` | `string` | Text response generated by the system (can be empty string) |

### Important Notes

- **One prediction per turn:** Provide predictions for every session × turn in the evaluation set
- **No duplicates:** Each `predicted_track_ids` list must contain unique track IDs
- **Order matters:** Rank track IDs by relevance (most relevant first)
- **Valid track IDs:** IDs must match those in [TalkPlayData-Challenge-Track-Metadata](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Track-Metadata)

## Evaluation Metrics

### Retrieval Metrics

The framework computes **Normalized Discounted Cumulative Gain (nDCG)** at
k = {1, 5, 10, 20, 50, 100, 200, 500, 1000}, alongside matching Hit/Recall and
MRR cutoffs for dev-set diagnostics.

$$
\text{nDCG@k} = \frac{\text{DCG@k}}{\text{IDCG@k}}, \quad \text{DCG@k} = \sum_{i=1}^{k} \frac{2^{rel_i} - 1}{\log_2(i + 1)}
$$

- `rel_i` = 1 if the track at position *i* matches the ground truth, 0 otherwise
- IDCG@k is the ideal (maximum possible) DCG@k
- Results are macro-averaged first over turns, then over sessions
- `nDCG@{1,10,20}` remain the main comparable headline metrics
- Deep-cutoff metrics require at least 1000 ranked IDs per turn; otherwise evaluation fails clearly

### Diversity Metrics

| Metric | Description |
|--------|-------------|
| `catalog_diversity` | Unique recommended tracks ÷ total catalog size (0–1). Higher = broader coverage. |
| `lexical_diversity` | **Distinct-2**: unique bigrams ÷ total bigrams across all predicted responses. Higher = richer vocabulary. |

## Repository Structure

```
music-crs-evaluator/
├── readme.md                    # This file
├── requirments.txt              # Python dependencies
├── make_ground_truth.py         # Script to generate ground truth files
├── evaluate_devset.py           # Evaluation script for the development set
├── metrics/
│   ├── __init__.py
│   ├── metrics_recsys.py        # nDCG and retrieval metrics
│   └── metrics_diversity.py     # Catalog and lexical diversity metrics
└── exp/
    ├── ground_truth/            # Ground truth files (generated by make_ground_truth.py)
    ├── inference/               # Place your prediction JSON files here
    │   └── <eval_dataset>/
    │       └── <tid>.json
    └── scores/                  # Evaluation results (auto-generated)
        └── <eval_dataset>/
            └── <tid>.json
```

## Baseline Results (Devset)

| Method | nDCG@1 | nDCG@10 | nDCG@20 | Catalog Diversity | Lexical Diversity |
|--------|-------:|--------:|--------:|------------------:|------------------:|
| Random | 0.0000 | 0.0001 | 0.0001 | 0.9652 | 0.0000 |
| Popularity | 0.0005 | 0.0018 | 0.0024 | 0.0004 | 0.0000 |
| LLaMA-1B + BM25 | 0.0098 | 0.0627 | 0.0815 | 0.3795 | 0.2558 |

For baseline implementations, see: [nlp4musa/music-crs-baselines](https://github.com/nlp4musa/music-crs-baselines)

## Dataset

All datasets are part of the [TalkPlay Data Challenge](https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge) collection on Hugging Face.

| Dataset | Size | Description |
|---------|------|-------------|
| [TalkPlayData-Challenge-Dataset](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Dataset) | 1k sessions | Multi-turn music conversations with user profiles, conversation goals, and goal-progress assessments |
| [TalkPlayData-Challenge-Track-Metadata](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Track-Metadata) | 50.4k tracks | Track metadata: name, artist, album, tags, popularity, release date |
| [TalkPlayData-Challenge-User-Metadata](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-User-Metadata) | 9.09k users | User demographics: age, gender, country |
| [TalkPlayData-Challenge-Track-Embeddings](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Track-Embeddings) | 50.4k tracks | Pre-computed embeddings for all tracks |
| [TalkPlayData-Challenge-User-Embeddings](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-User-Embeddings) | 9.09k users | Pre-computed embeddings for all users |

The dataset contains multi-turn conversations (~8 turns each) where the system must recommend music based on conversational context, user listening history, and demographic profile.

## Validation Checklist

Before submitting your predictions, verify:

- [ ] JSON file is saved at the correct path (`exp/inference/devset/<tid>.json`)
- [ ] All required fields are present in every entry
- [ ] Predictions cover all sessions × turns (1–8) in the evaluation set
- [ ] Track IDs are valid identifiers from [TalkPlayData-Challenge-Track-Metadata](https://huggingface.co/datasets/talkpl-ai/TalkPlayData-Challenge-Track-Metadata)
- [ ] No duplicate track IDs within each `predicted_track_ids` list
- [ ] Track IDs are ordered by relevance (most relevant first)
- [ ] JSON is properly formatted (`json.dump(..., ensure_ascii=False)`)

## Troubleshooting

**"Predictions should be unique. Duplicates detected."**
Ensure no duplicate track IDs appear in `predicted_track_ids`.

**Missing predictions error**
Verify predictions exist for all sessions and turn numbers (1–8). Check that `session_id` and `turn_number` match exactly with the ground truth file.

**KeyError on session_id / turn_number**
Confirm your JSON uses the exact field names listed in the Required Fields table above.

## Contact

For questions or issues with the evaluation framework, please open an issue in this repository.
