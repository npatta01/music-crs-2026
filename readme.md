# Music-CRS — Our RecSys 2026 Music Conversational Recommendation Submission

Our entry to the **[RecSys 2026 Music Conversational Recommendation Challenge](https://nlp4musa.github.io/music-crs-challenge/)**: given a multi-turn conversation, retrieve 20 tracks from a 47k-track catalog and generate a natural-language response explaining them.

Built on top of the organizers' official baseline/evaluation framework (task format, dataset loaders, inference contract). Everything past the original two-stage BM25/BERT + Llama-3.2-1B baseline — the state extraction, multi-branch retrieval, RRF fusion, learned reranker, and response generation — is our own pipeline, described below.

## Start here

**[Open the interactive architecture deck →](https://npatta01.github.io/music-crs-2026/docs/submission-architecture.html#/high-level-architecture)**

The progressive walkthrough explains how a conversation moves through state extraction, retrieval, ranking, and response generation, with examples and label-audit evidence.

[Project website](https://npatta01.github.io/music-crs-2026/index.html) · [Submission architecture deck](docs/submission-architecture.html) in this repository

- **Challenge site**: https://nlp4musa.github.io/music-crs-challenge/
- **ACM RecSys Challenge**: https://www.recsyschallenge.com/2026
- **Datasets**: [TalkPlayData-Challenge collection](https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge)
- **Scores**: see [below](#scores) — devset, Blind-A, and Blind-B across every reported facet
- **Competition retrospective**: [what we built, where we fell short, and what the leading public teams did differently](docs/retrospective.html)

---

## Scores

| Split | NDCG@20 | Catalog Diversity | Lexical Diversity | LLM-as-a-Judge | Composite | Source |
|---|---:|---:|---:|---:|---:|---|
| Devset | 0.4562 | — | — | — | — | Local evaluator ([leaderboard.md](leaderboard.md)) |
| Blind-A | 0.4380 | 0.0313 | 0.7670 | 4.2000 | **0.5389** | CodaBench submission `797598` (dev-phase rank 63/181 submissions) |
| Blind-B | 0.2537 | 0.0315 | 0.7862 | 3.3000 | **0.3811** | CodaBench submission `819863` (**final rank 29/39 teams**) |

Devset extras (no CodaBench equivalent): Hit@20 0.6138, MRR 0.4102 — see [leaderboard.md](leaderboard.md) for deep-cutoff diagnostics (@50–@1000) and per-stage recall breakdowns.

Devset and Blind-A/B aren't directly comparable: devset is scored locally against public ground truth with a different metric surface (no organizer-side Composite/Catalog Diversity/Lexical Diversity/LLM-as-a-Judge), while Blind-A/B are scored by CodaBench against held-out labels on the exact facets shown above.

⚠️ The devset NDCG@20 above is the last full 50-shard Modal capture (2026-06-15); a later local recapture after subsequent reranker fixes showed a lower number (0.3844), not yet reconfirmed with a fresh full Modal run — see `leaderboard.md`'s discrepancy note before treating 0.4562 as current.

---

## Running inference

Runs locally, no live credentials needed. One-time setup, then run any split:

```bash
scripts/repro_setup.sh   # one-time: creates .venv, installs deps, downloads the offline
                          # bundle (catalog, embeddings, extracted state, frozen LLM cache)
                          # from Hugging Face -- the catalog it downloads is also what
                          # training needs, so this is the right first step either way

scripts/repro_run.sh                          # Blind-B (default), 80 sessions
scripts/repro_run.sh --eval_dataset blindset_A   # 80 sessions
scripts/repro_run.sh --eval_dataset devset       # 1000 sessions, so proportionally longer
```

These commands never invoke Modal — this path is fully local, verified under a network fence (Modal genuinely unreachable) across all three splits. Within it, Modal is only ever a transparent, automatic fallback for specific embedding calls (e.g. the b1 bi-encoder and the CLAP/SigLIP-2 text encoders) when local GPU weights aren't available, and even that never fires here since the offline bundle pre-caches every query embedding these three splits touch. (Elsewhere in the repo — e.g. `docs/reproduce_reranker.md`'s FAST path, or CLAUDE.md's own command reference — Modal is also used to orchestrate live, credentialed runs at scale; that's a maintainer/retraining concern, not part of reproducing what we submitted.)

See [docs/reproduce_offline_bundle.md](docs/reproduce_offline_bundle.md) for the byte-exact frozen-replay path vs. this live rerun, and how to check the reported score rather than just the prediction file. Predictions land in `exp/inference/{split}/{tid}.json`. See [CLAUDE.md](CLAUDE.md) for the full command reference (including `run_pipeline.py` for faster staged local iteration) and shared-cache setup for local worktrees.

---

## Submission file

Our current active configs (all set `track_split_types: ["all_tracks"]`, so retrieval always searches the full 47k-track catalog — none subset it during inference):

| Config | Role |
|---|---|
| `configs/state_ranker_v10_lgbm_blindset_A.yaml` | Blind-A submission — `models/reranker_v12_goalfree` |
| `configs/state_ranker_v10_lgbm_blindset_B.yaml` | Blind-B submission — `models/reranker_v12_goalfree` |
| `configs/state_ranker_v10_lgbm_devset.yaml` | Devset scoring — `models/reranker_v12_goalfree` |
| `configs/state_ranker_v10_rrf_devset.yaml` | Explicit RRF/candidate-fusion baseline — no reranker |

`prediction.json` is packaged with a `<tid> [split]` pair (split defaults to `blindset_A`):

```bash
bash prepare_submission.sh state_ranker_v10_lgbm_blindset_A                # Blind-A (default split)
bash prepare_submission.sh state_ranker_v10_lgbm_blindset_B blindset_B     # Blind-B
```

which copies `exp/inference/{split}/{tid}.json` → `submission/prediction.json` and zips it. Previously submitted zips are kept in [`submission/`](submission/).

---

## Training the models from scratch

The one place real credentials are unavoidable — this is genuine GPU training work on Modal, not just running the shipped pipeline. Builds on the same venv `scripts/repro_setup.sh` above already creates; add credentials on top:

```bash
uvx hf auth login                # HF account with access to the TalkPlay Data Challenge collection
uv run python -m modal setup     # Modal auth
# and set OPENROUTER_API_KEY / DEEPINFRA_API_KEY / VLLM_API_KEY in .env

# LightGBM reranker: rebuild retrieval traces/features, retrain on Modal.
# See docs/reproduce_reranker.md for the full command sequence.

# b1 bi-encoder (the fine-tuned Qwen3-Embedding conv->track retriever
# behind the b1_cos reranker feature):
modal run scripts/rerank/modal_train_biencoder.py
modal volume get scout-models /biencoder_qwen06_eN ./models/   # N = 1,2,3 (one checkpoint/epoch)
# See docs/architectures/biencoder.md for the training recipe (MNRL, MOVES-only
# positives, known-for field dropout) and how the checkpoint gets promoted/served.
```

Offline bundle (catalog, caches, frozen traces, model weights): **https://huggingface.co/datasets/Npatta01/music-crs-repro-2026**

---

## Repo map

- [docs/codebase/README.md](docs/codebase/README.md) — start here for per-module internals and the verified-bugs audit
- [docs/data.md](docs/data.md) — dataset schemas, splits, inference output format
- [docs/evaluation.md](docs/evaluation.md) — metrics, devset leaderboard setup
- [experiments/README.md](experiments/README.md) — current config/report index (pruned intentionally; see git history for older waves)
- [changelog.md](changelog.md) — PR-linked outcomes (score table is in [Scores](#scores) above)
- [tips/](tips/) — extension ideas we didn't pursue (better item representations, generative retrieval, etc.)

---

## Paper

Our participant paper, **"Team npatta01's Conversational Music Recommender for the RecSys Challenge 2026"** (ACM sigconf, 4 pages + references), lives in [`paper/`](paper/): [`main.tex`](paper/main.tex) is the authoritative source, [`draft.md`](paper/draft.md) is a readable mirror. It documents the full pipeline and an honest retrospective: the in-sample-evaluation lesson, the ground-truth anchoring-bias analysis (cleaned relabeling released — see the [anchor labels](data/anchor_labels_v1/README.md)), and concrete failure cases from the submitted Blind-B run.

---

## License

Code is released under the [MIT License](LICENSE). Datasets referenced from Hugging Face keep their own licenses.

---

## Acknowledgments

Built on the RecSys 2026 Music-CRS organizers' baseline evaluation framework and the [TalkPlayData-Challenge](https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge) datasets. Thanks to the organizing committee for the challenge and infrastructure.

---

## Authors / Feedback

If you have feedback, please reach out to:

- [Nidhin Pattaniyil](mailto:npatta01@gmail.com) ([LinkedIn](https://www.linkedin.com/in/nidhinpattaniyil/))
- [Semih Yagli](mailto:semihyagli1@gmail.com) ([LinkedIn](https://www.linkedin.com/in/semihyagli/))
- [Tanwir Zaman](mailto:zaman.tanwir@gmail.com) ([LinkedIn](https://www.linkedin.com/in/tanwirzaman/))

---

## Competition retrospective

[Read the detailed post-competition retrospective](https://npatta01.github.io/music-crs-2026/docs/retrospective.html?path=audit#outcome/gap-interpretation).
