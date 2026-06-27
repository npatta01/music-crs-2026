# Anchoring-fix training labels — train split (v1.1)

**File:** `train_labels_full.jsonl` — 106,393 turns / 15,199 sessions (the entire
`talkpl-ai/TalkPlayData-Challenge-Dataset` **train** split).

> **Revision history.** **v1.1** (current) fixes two composition issues found in
> review: (1) the conflict gate now routes a turn to the Opus arbiter when the two
> cheap judges split on *either axis* (anchor or content), not only on the final
> label — previously, judges that agreed on a NEGATIVE label but disagreed on
> *why* (one `artist_anchoring`, one `content_violation`) were silently resolved
> to judge-1's reason; (2) the arbiter now judges **blind to the synthetic
> reaction** (`gt_label` is stripped from its input). Net effect vs v1: **3,486**
> additional turns (the axis-splits) were re-arbitrated by Opus, moving **1,591**
> turns out of the `artist_anchoring` bucket (19,813 → 18,222). All numbers below
> are v1.1.

Built to retrain the two-tower retriever so that, on a turn where the listener
explicitly asks for a **different artist**, it stops returning the just-played
artist (the *anchoring* bug). Every recommendation is independently re-judged by
LLMs rather than trusting the synthetic per-turn reaction label.

## How each turn was labeled

Per `(session, turn)` the just-played candidate track is judged on **two axes**,
each by two independent cheap judges (Gemma-4-26B + DeepSeek-V4-Flash, via
DeepInfra/LiteLLM), seeing the **last 3 conversation turns** up to the current ask
(assistant replies stripped, `[system played: …]` markers kept):

1. **ANCHOR** — `asked_for_different_artist` (bool): did the listener explicitly
   demand a different/other/new artist? `anchoring := asked_for_different_artist
   AND same_artist`, where `same_artist` is a **deterministic** catalog check
   (candidate artist == most-recent prior music-turn artist), never an LLM guess.
2. **CONTENT** — `content_fit ∈ {valid, invalid, unsure}`: does the track satisfy
   the current turn's named facets (genre/era/mood/tempo/named song/exclusions),
   ignoring artist novelty.

When the two cheap judges **disagree on the label _or_ on either axis** (19.9% of
turns), the turn is re-judged by an **Opus** arbiter (`anchor-arbiter` subagent),
axis-by-axis and **blind to the synthetic reaction**. Agreement →
`confidence_weight` 1.0 (HOLD → 0.3); arbiter → 0.6.

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
| POSITIVE | 35,191 | 33.1% |
| NEGATIVE | 61,063 | 57.4% |
| DROP | 4,007 | 3.8% |
| HOLD | 6,132 | 5.8% |

- **artist_anchoring negatives: 18,222** (17.1% of all turns).
- **5,880** of those anchoring negatives had synthetic reaction **MOVES** — i.e.
  the dataset said the listener *liked* the anchored-artist track right after
  asking for someone else. These are the poisoned positives this dataset rescues:
  on the raw label the retriever learns to anchor. (16,165 NEGATIVEs total had a
  raw `MOVES`, counting content violations.)
- `decided_by`: both_agree 85,208 / opus_arbitrated 21,185 (19.9%).
- `confidence_weight`: 1.0 → 83,482 · 0.6 → 21,185 (arbitrated) · 0.3 → 1,726
  (both-judge-agreed HOLDs; arbitrated HOLDs keep 0.6).

## Schema (per line)
`sid, tn, current_ask, just_played, candidate_track, listener_reaction
(MOVES|DOES_NOT), same_artist, asked_for_different_artist, anchoring,
content_fit, label, label_reason, confidence_weight, decided_by`

## Provenance / reproduce
- Sheet build: `scripts/rerank/anchor_labels/build_anchor_universe.py` (last 3 turns via
  `scripts/rerank/anchor_labels/convo_context.py`), batched by `scripts/rerank/anchor_labels/batch_sheet.py`.
- Judges: `scripts/rerank/anchor_labels/judge_anchor_content.py`. Arbiter subagent:
  `.claude/agents/anchor-arbiter.md` (+ `scripts/rerank/anchor_labels/run_arbiter.py` chunk/merge).
- Compose: `scripts/rerank/anchor_labels/compose_labels.py --split train`.
- Per-batch artifacts under `labels_train/bNN/` (judge records, conflicts, arbiter
  verdicts, final_labels). Coverage was verified per batch (0 dropped, 0 unresolved).
