# Anchoring-fix training labels — train split (v1)

**File:** `train_labels_full.jsonl` — 106,393 turns / 15,199 sessions (the entire
`talkpl-ai/TalkPlayData-Challenge-Dataset` **train** split).

Built to retrain the two-tower retriever so that, on a turn where the listener
explicitly asks for a **different artist**, it stops returning the just-played
artist (the *anchoring* bug). Every recommendation is independently re-judged by
LLMs rather than trusting the synthetic per-turn reaction label.

## How each turn was labeled

Per `(session, turn)` the just-played candidate track is judged on **two axes**,
each by two independent cheap judges (Gemma-4-26B + DeepSeek-V4-Flash, via
DeepInfra/LiteLLM), seeing the **full reconstructed conversation** (last turns,
assistant replies stripped, `[system played: …]` markers kept):

1. **ANCHOR** — `asked_for_different_artist` (bool): did the listener explicitly
   demand a different/other/new artist? `anchoring := asked_for_different_artist
   AND same_artist`, where `same_artist` is a **deterministic** catalog check
   (candidate artist == most-recent prior music-turn artist), never an LLM guess.
2. **CONTENT** — `content_fit ∈ {valid, invalid, unsure}`: does the track satisfy
   the current turn's named facets (genre/era/mood/tempo/named song/exclusions),
   ignoring artist novelty.

When the two cheap judges **disagree** on either axis (16.7% of turns), the turn
is re-judged **blind** by an **Opus** arbiter (`anchor-arbiter` subagent),
axis-by-axis. Agreement → `confidence_weight` 1.0 (HOLD 0.3); arbiter → 0.6.

### Label composition
| label | reason | rule |
|---|---|---|
| **NEGATIVE** | `artist_anchoring` | `anchoring` is true — **even if the synthetic reaction was MOVES** |
| **NEGATIVE** | `content_violation` | `content_fit == invalid` |
| **POSITIVE** | `fits_and_liked` | `content_fit == valid` AND reaction `MOVES` |
| **DROP** | `fit_but_disliked` | `content_fit == valid` AND reaction `DOES_NOT` |
| **HOLD** | `unverifiable` | `content_fit == unsure` (no checkable facet / unverifiable) |

Off-by-one honored upstream: a turn's reaction = `MOVES` iff
`goal_progress_assessments[tn+1] == MOVES_TOWARD_GOAL`; last track/session dropped.

## Distribution

| label | count | % |
|---|---|---|
| POSITIVE | 34,938 | 32.8% |
| NEGATIVE | 61,784 | 58.1% |
| DROP | 3,922 | 3.7% |
| HOLD | 5,749 | 5.4% |

- **artist_anchoring negatives: 19,813** (18.6% of all turns).
- **6,234** of those anchoring negatives had synthetic reaction **MOVES** — i.e.
  the dataset said the listener *liked* the anchored-artist track right after
  asking for someone else. These are the poisoned positives this dataset rescues:
  on the raw label the retriever learns to anchor. (16,509 NEGATIVEs total had a
  raw `MOVES`, counting content violations.)
- `decided_by`: both_agree 88,640 / opus_arbitrated 17,753.
- `confidence_weight`: 1.0 → 86,914 · 0.6 → 17,753 · 0.3 → 1,726.

## Schema (per line)
`sid, tn, current_ask, just_played, candidate_track, listener_reaction
(MOVES|DOES_NOT), same_artist, asked_for_different_artist, anchoring,
content_fit, label, label_reason, confidence_weight, decided_by`

## Training recipe (two-tower retriever)
- **Positives:** `label == POSITIVE` → (conversation query, candidate_track) pairs.
- **Hard negatives, query-local:** `label == NEGATIVE`. The
  `label_reason == artist_anchoring` subset is the targeted anchoring signal —
  mine them as **per-query** negatives (same conversation), not global randoms.
- **DROP:** fit-but-disliked — exclude from positives; optionally a weak negative.
- **HOLD:** exclude from training (unverifiable).
- Weight the loss by `confidence_weight` (down-weight arbiter 0.6 / HOLD 0.3).

## Provenance / reproduce
- Sheet build: `scripts/rerank/build_anchor_universe.py` (full conversation via
  `scripts/rerank/convo_context.py`), batched by `scripts/rerank/batch_sheet.py`.
- Judges: `scripts/rerank/judge_anchor_content.py`. Arbiter subagent:
  `.claude/agents/anchor-arbiter.md` (+ `scripts/rerank/run_arbiter.py` chunk/merge).
- Compose: `scripts/rerank/compose_labels.py --split train`.
- Per-batch artifacts under `labels_train/bNN/` (judge records, conflicts, arbiter
  verdicts, final_labels). Coverage was verified per batch (0 dropped, 0 unresolved).
