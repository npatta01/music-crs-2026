# Semantic-ID Retrieval Handoff

Date: 2026-06-16

PR: https://github.com/npatta01/music-conversational-music-recomender-2026/pull/135

## Short Version

We tested whether semantic IDs can help the Music-CRS retriever find better
candidate tracks from a conversation. The answer is: useful research signal, but
not ready to replace v10 retrieval.

The strongest new candidate branch was not the semantic-ID decoder. It was the
continuous conversation-to-item retriever: embed or hash the conversation plus
prior accepted tracks, train a query projector, and directly rank catalog item
vectors.

The semantic-ID branch is still worth keeping because the Qwen 8B run improved
non-playable candidate recall, but it needs better libraries and better learned
item/code representations before it is likely to beat the continuous retriever.

## What We Tried

### 1. Semantic IDs From Existing Item Vectors

Built hierarchical item codes over the 47k-track catalog:

- level 1: 64 coarse clusters
- level 2: up to 16 leaf clusters per coarse cluster
- item inputs tested:
  - `cf_bpr`
  - `cf_bpr` + metadata/attribute embeddings
  - metadata/attribute embeddings only
  - Qwen 8B metadata/attribute embeddings
  - a hard-negative CF projection trained from v10 candidate pools

Result: semantic-ID overlays gave only tiny ranking deltas. This is not enough
to ship as a v10 replacement.

### 2. Conversation-To-Item Retriever

Trained a model that maps conversation context to catalog item-vector space and
ranks all tracks directly.

Inputs tested:

- last user turn
- last user turn + prior accepted tracks
- full conversation + prior accepted tracks

Best result:

| Input | All R@100 | All R@1000 | Non-playable R@1000 |
|---|---:|---:|---:|
| last turn + prior tracks | 0.2255 | 0.4165 | 0.1461 |
| full conversation + prior tracks | 0.2295 | 0.4230 | 0.1440 |

Interpretation: this is the best new candidate branch. Full conversation helps a
little overall, but last turn + prior tracks is slightly better on the
non-playable slice that matters most.

### 3. Hashed Constrained Semantic-ID Decoder

Trained a first constrained decoder that predicts valid `(sid_l1, sid_l2)`
codes, expands those leaves into tracks, and ranks inside the predicted leaves.

Best result:

| Input | All R@100 | All R@1000 |
|---|---:|---:|
| last turn + prior tracks | 0.0616 | 0.1681 |

Interpretation: it works mechanically, but it is weaker than direct
conversation-to-item retrieval.

### 4. Qwen Semantic-ID Generator

Moved closer to the generative-retrieval literature:

- text/query embeddings from local CUDA Qwen
- prior accepted tracks converted into semantic-ID code tokens
- Transformer predicts `sid_l1`, then predicts `sid_l2` conditioned on `sid_l1`
- valid leaf expansion only
- optional within-leaf ranking using metadata Qwen vectors

Main results:

| Model | Train turns | All R@100 | All R@1000 | Non-playable R@1000 |
|---|---:|---:|---:|---:|
| Qwen 0.6B | 20k | 0.0666 | 0.2118 | 0.0742 |
| Qwen 8B | 5k | 0.0736 | 0.2403 | 0.1102 |

Interpretation: Qwen 8B helped, especially on non-playable turns, even with less
training data. The semantic-ID approach has a real signal, but it is still
behind the continuous retriever.

## What This Is And Is Not

This is TIGER-inspired, not full TIGER.

It has:

- item semantic codes
- prior accepted-track code tokens
- conditional code generation
- constrained expansion through valid code paths

It does not yet have:

- a learned residual semantic tokenizer / RQ-VAE codebook
- a full autoregressive sequence model over item-code histories
- joint training of item representation and retrieval objective
- mature library-backed generation/constrained decoding

The likely stronger version should lean on mature libraries:

- Hugging Face `transformers` for seq2seq training, beam search, and constrained
  generation
- FAISS for scalable k-means or quantizer experiments
- `vector-quantize-pytorch` or similar for residual vector quantization if we
  pursue learned TIGER-style IDs

## Comparison To Current v10

Current v10 is still much stronger as the main retrieval/ranking system.

| Approach | All R/Hit@20 | All R/Hit@100 | All R/Hit@1000 |
|---|---:|---:|---:|
| v10 branch union | 0.4299 | 0.6255 | 0.8919 |
| v10 candidate fusion | 0.3182 | 0.4915 | 0.7206 |
| v10 LambdaMART stage | 0.6138 | 0.7212 | 0.8204 |
| conversation-to-item retriever | 0.1041 | 0.2255 | 0.4165 |
| Qwen semantic-ID 8B | 0.0193 | 0.0736 | 0.2403 |

The point is not to replace v10 right now. The point is to add a branch that
recovers examples the current v10 candidate pool misses, then retrain LambdaMART
on the expanded candidate union.

## Where We Are Leaving Off

PR #135 contains reusable experiment infrastructure:

- `mcrs/analysis/semantic_ids.py`
- `mcrs/analysis/semantic_hard_negatives.py`
- `mcrs/analysis/conversation_semantic.py`
- `mcrs/analysis/qwen_semantic_generator.py`
- `scripts/semantic_ids/`
- focused tests under `tests/test_*semantic*`

Generated results and caches are intentionally not committed:

- `exp/analysis/semantic_ids/`
- Qwen embedding caches
- semantic-ID parquet outputs
- JSON metric outputs

The isolated worktree used for the experiments was:

```text
/home/nidhin/.config/superpowers/worktrees/music-conversational-music-recomender-2026/semantic-id-experiment
```

The branch is:

```text
codex/semantic-id-experiment
```

## Recommended Next Step

Do not spend the next round trying to perfect the semantic-ID decoder first.

The highest expected-value next step is:

1. integrate the continuous conversation-to-item retriever as an additive v10
   candidate branch;
2. rebuild v10 feature rows over the expanded candidate union;
3. retrain LambdaMART;
4. measure whether non-playable recall turns into final NDCG@20 or Hit@20 lift.

After that, revisit semantic IDs with a more faithful library-backed approach:

1. use `transformers` for seq2seq generation and constrained decoding;
2. use FAISS or residual VQ for stronger item codebooks;
3. train task-aware item/code representations instead of relying only on fixed
   CF k-means IDs;
4. compare against the continuous retriever as an additive branch, not as a
   standalone replacement.

## Validation Before PR

Focused tests:

```text
22 passed, 2 warnings
```

Also ran `py_compile` over all new semantic-ID modules and scripts.
