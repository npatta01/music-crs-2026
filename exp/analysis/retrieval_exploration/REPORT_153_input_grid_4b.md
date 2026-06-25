# Report — b1 retriever: goal-free input grid + 4B lift (Issue #153)

*All numbers are on the off-by-one-**corrected** labels (see §6). Devset, n=6,184 MOVES turns,
full-catalog rank over 47,071 docs, max_len=2048, paired McNemar. All runs on Modal.*

## TL;DR
- **Question:** does a *better goal-free query input* beat the baseline input for the b1
  conversation→track retriever (Qwen3-Embedding), and how much does scaling 0.6B→4B add — framed for
  **Blind Dataset B** (no `conversation_goal`, half cold-start → inputs must be goal-free /
  profile-free).
- **Winner input: `v_struct_pt`** = `[prev] <prev user turn> [now] <current user turn> [prev_track]
  <just-played artist—title>`. **+5.05pp r@100 over baseline @0.6B (p≈1e-28).**
- **The right input beats a 7× bigger encoder** (+5.05pp input vs +2.86pp model), and they **stack
  to +7.37pp** (p≈6e-48). They're **complementary by lane**: prev_track fixes *continuation*, 4B
  fixes *hard_pivot*.
- **Special tokens (`<|prev|>`/`<|now|>`) rejected** — no benefit over plain markers.

## 1. Setup
- b1 = fine-tuned Qwen3-Embedding bi-encoder, single cosine, 47k-track text-doc index. Recipe:
  variant-b MOVES-only, kf-dropout 0.3, n_hardneg 4, bs64, 1 epoch, MNRL, last-token pool.
- **Goal-free / profile-free** inputs (Blind-B-deployable). Variants: `baseline` `[msg] p / n`;
  `v_struct` `[prev] p [now] n`; `v_tok` `<|prev|> p <|now|> n` (learned special tokens);
  `v_struct_pt` = v_struct + `[prev_track]`.
- Train on the `train` split (15,199 sessions); eval on `dev` (6,184 MOVES turns) — disjoint.

## 2. Results — model × input (corrected labels)
| model · input | r@20 | r@100 | r@1000 | medrank |
|---|---|---|---|---|
| 0.6B · baseline | 26.5 | 46.6 | 77.7 | 131 |
| 0.6B · v_struct_pt | 30.3 | 51.7 | 80.8 | 89 |
| 4B · baseline | 28.5 | 49.5 | 80.4 | 104 |
| **4B · v_struct_pt** | **32.7** | **54.0** | **82.9** | **72** |

(Input grid @0.6B also ran v_struct = 47.4 r@100 — a tiny +0.8pp, seed-fragile — and v_tok ≈ baseline.)

## 3. Lifts (paired McNemar, r@100, corrected)
| lever | Δ r@100 | net turns | p |
|---|---|---|---|
| **Input** (baseline→v_struct_pt) @0.6B | **+5.05pp** | +312 | 1e-28 |
| **Input** @4B | +4.51pp | +279 | 7e-21 |
| **Model** (0.6B→4B) on baseline | +2.86pp | +177 | 5e-11 |
| **Model** on v_struct_pt | +2.33pp | +144 | 1e-08 |
| **Stack** (0.6B·baseline → 4B·v_struct_pt) | **+7.37pp** | +456 | 6e-48 |

## 4. Per-lane r@100 — the complementarity
| lane (n) | 0.6B base | 0.6B v_struct_pt | 4B base | 4B v_struct_pt |
|---|---|---|---|---|
| continuation (2434) | 70.3 | **81.8** | 72.6 | **83.4** |
| hard_pivot (2850) | 25.7 | 26.3 | **29.1** | **28.9** |
| turn_1 / cold-start (900) | 48.9 | 50.6 | **51.8** | **54.2** |

**prev_track → continuation** (+11.5pp; it adds the just-played track so "more like this" resolves).
**4B → hard_pivot** (+3.4pp on baseline) and cold-start — the lanes prev_track can't help. Different
levers, different lanes → keep both.

## 5. Key findings
1. **Information beats layout, and beats model size.** Adding the *just-played track* (prev_track)
   is the single biggest lever (+5pp), larger than the 7× encoder (+2.9pp); they're additive.
2. **prev_track's win is a narrow, same-artist-continuation signal** — ~100% of the gain is in the
   ~32% of turns where the GT shares the just-played artist (+17.7pp there); roughly neutral/slightly
   negative on the diff-artist majority; ~0 on hard_pivot. It is **leak-free** (prev_track never
   equals the GT; GT never in a prior turn). On cold-start it renders identically to v_struct →
   **neutral, never harmful**.
3. **Special tokens are a dead end** — `v_tok` ≈ baseline, significantly below the equivalent plain
   markers `v_struct`. Learned delimiter tokens add nothing over pretrained text markers at 1-epoch FT
   (verified not a code bug).
4. **Formatting alone (v_struct) is within single-seed noise** — not bankable without a seed replicate.

## 6. hard_pivot diagnosis (the open problem)
hard_pivot r@100 ≈ 26% (true, corrected). Root cause, measured: **named-artist fixation** — the
encoder returns the *just-played artist* as its #1 result on **80%** of pivots; the correct pivot
artist is in the top-10 only **7.5%** (0.3% on deep misses). Two walls:
- **Fixable (training):** the model was trained with random negatives → never penalized for "more of
  the same"; `prev_track` in the request amplifies the anchor.
- **Irreducible (text):** r@1000 only ~64–68% → ~31% of pivot GTs are unreachable by the text channel
  at any depth (format/size-invariant); the pivot target is a *co-listen* fact, not in the words.
The lane label is an **oracle** (defined by the GT artist) → no inference-time pivot detector → any
fix must be **automatic / detector-free**.

## 7. The off-by-one label bug (found mid-stream, fixed, re-confirmed)
`TalkPlayData assessment[turn N]` grades `track[N-1]`, **not** `track[N]` (memory
`goal-progress-label-offbyone`). The original pairing (`pos_id=track[tn]` with `gpa=assessment[tn]`)
mislabeled ~31% of MOVES positives + mis-selected the eval turns. **Fixed** in `modal_build_data.py`
(gate `track[tn]` on `assessment[tn+1]`, drop last-track), rebuilt (**32,912 label flips**), and
**re-ran baseline + v_struct_pt at both 0.6B and 4B**. **Every conclusion held** — the bug was a
*shared confound* (same labels for all variants/models), so it added noise but didn't flip any
ordering. Magnitudes shifted slightly (corrected MOVES are cleaner → a touch higher/easier; stack
+8.36→+7.37pp). The corrected eval also surfaced ~900 cold-start (`turn_1`) turns the bug had excluded.

## 8. Verification
- Code reviewed by 2 Opus advisors + an 11-agent ultracode workflow → **no bugs; every number
  reproduced exactly from the raw rank files.** Training/pooling parity, MNRL shape, leak checks, and
  the on-Modal eval all confirmed.

## 9. Forward plan + handoffs (NOT done here — deliberately forked)
The hard_pivot *fix* is scoped, not implemented:
- **Issue #156** — judge bake-off (request-grounded relevance judge: Qwen3-Reranker CE vs instruct
  LLM; decisive test = true-negative vs valid-alternative).
- **Issue #148** — multi-tower (3-tower request/song/history + learned gate; go beyond 3 with a CF
  `cf_bpr` tower for the text-unreachable residual). Carries the best prompt/model learnings.
- Both flagged with the off-by-one blocker; both must build on corrected labels.

## 10. Loose ends / caveats
- **`v_struct_pt` is a *retrieval* win, not yet an *end-to-end* win** — the downstream nDCG@20 /
  rerank-feature A/B (the issue's step 2/3) was **not** run. Single-GT r@k is necessary-not-sufficient
  (~78% of misses are "plausibly valid"). Validate before shipping.
- All runs are **single-seed** (the 4B/v_struct_pt effects are large/robust; the small v_struct
  formatting effect is not).

## 11. Files & artifacts
- Scripts (committed, this branch): `scripts/rerank/{modal_build_data,modal_train_variants,
  modal_spotcheck,modal_fixation,modal_ckpt_info,modal_promote_hf}.py` — self-contained (the
  doc-corpus build logic is inlined in `modal_build_data.py`). The reference originals
  (`build_*`, `eval_scout_*`, `modal_embed_docs`) belong to the GATE-0 work and are not duplicated here.
- Modal volumes: `biencoder-data` (corrected `input_variants/`, `doc_corpus`, `retriever_pairs`);
  `scout-models` (checkpoints + `ranks_<v>_l2048[_qwen3-embedding-4b].json`); catalog on
  `music-crs-models/lancedb` (has `cf_bpr`/`audio_laion_clap`/`image_siglip2`). Secret `huggingface`.
- Memory: `input-grid-prevtrack-4b-lift` (+ off-by-one re-confirmation). Plan/handoff:
  `~/.claude/plans/sequential-toasting-lollipop.md`.
