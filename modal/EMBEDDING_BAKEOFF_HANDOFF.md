# Handoff — Run the Qwen3 Embedding Bake-Off

**For:** a Claude Code session running in an environment **with Modal configured and
open network egress** (Mac/local dev, or a web env whose network policy allows
Modal + Hugging Face). The script already exists on this branch; your job is to
**run it, interpret the numbers, and write up the result.**

**Branch:** `claude/embedding-tags-metadata-nvrRM`
**Script:** `modal/embedding_bakeoff.py` (already committed)

---

## 1. The questions

**A — encoder size.** Does a **bigger metadata encoder** (Qwen3-Embedding 4B / 8B)
retrieve better than the **0.6B** baseline the catalog was built with? An earlier
comparison (`experiments/dense_qwen3_embedding_8b_devset.md`, leaderboard #9,
NDCG@20 0.1025) only tracked **NDCG@20** — which can't see whether a bigger model
improves **deep recall** (the real job of a first-stage retriever before reranking).
This bake-off reports **Recall@100 / Recall@1000** alongside NDCG@20.

**B — tags representation.** The attributes/tags branch *hurt* in the v0+ ablation.
The hypothesis is that the raw **tag-dump** document template
(`music attributes, tags :rock,melancholic,90s`) sits far from conversational
queries. The bake-off renders each catalog track three ways — `metadata`,
`attributes_raw` (the existing tag-dump), and `attributes_nl` (a natural-language
rewrite of the same tags, `This is a rock, melancholic and 90s track.`) — so the
clean test is **`attributes_raw` vs `attributes_nl`**: same tag info, different
formatting, everything else held constant.

### Context you should know (from prior investigation)
- **metadata_qwen3 (0.6B)** is a *positive* retrieval branch: +21% NDCG@20 vs BM25
  in the v0+ ablation (`experiments/v0plus_compiler_ablation_2026-05-26.md`).
- **attributes_qwen3 (tags) and lyrics_qwen3 hurt** in that ablation (−6.7% / −8.9%).
  That finding is about the *tags representation/template*, not encoder size.
- The catalog's metadata vectors are **organizer-provided at 0.6B**; swapping the
  model normally means re-embedding 47k tracks. This script **avoids** that by
  re-encoding only a **subset pool** with each model.
- The hypothesis going in: a bigger encoder moves recall **modestly**; the larger
  lever is the query/representation side. The point of this run is to *measure*,
  not to assume.

---

## 2. Prerequisites (one-time)

- `modal token set ...` configured (or `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` in env).
- `.env` in the **repo root** containing `HF_TOKEN=hf_...` (read by
  `modal.Secret.from_dotenv`; the GPU container uses it to download models + datasets).
- HF account has access to the `talkpl-ai/TalkPlayData-Challenge-*` datasets and the
  `Qwen/Qwen3-Embedding-{0.6B,4B,8B}` models.
- `git checkout claude/embedding-tags-metadata-nvrRM && git pull`.

> This is the same setup as `python run_experiment.py --backend modal ...`. If that
> works for you, this will too.

---

## 3. Run it

```bash
# 1) SMOKE FIRST — small + fast, confirms the whole path works end to end
modal run modal/embedding_bakeoff.py --num-sessions 10 --pool-size 2000

# 2) FULLER comparison once smoke looks sane
modal run modal/embedding_bakeoff.py --num-sessions 150 --pool-size 8000

# focus the tags question only (raw tag-dump vs natural-language rewrite)
modal run modal/embedding_bakeoff.py --doc-variants attributes_raw,attributes_nl --models 0.6B,8B
```

**CLI flags** (`--flag value`): `--models` (default `0.6B,4B,8B`),
`--doc-variants` (`metadata,attributes_raw,attributes_nl`),
`--query-modes` (`symmetric,instruct`), `--num-sessions` (100), `--pool-size`
(5000), `--max-turns` (8), `--batch-size` (32, auto-shrunk for 4B/8B),
`--max-length` (512), `--seed` (0).

**Output:** a printed table + a JSON file at
`exp/analysis/embedding_bakeoff/bakeoff_<timestamp>.json`.

---

## 4. What the script does (so you can sanity-check it)

1. Loads track metadata (`...-Track-Metadata`, `all_tracks`) and the devset
   (`...-Challenge-Dataset`, `test`) from HF.
2. Builds `(query_text, gold_track_id)` examples from devset turns. `query_text`
   is the raw conversation (prior turns, music turns rendered to artist–title
   labels, then the current user message) — mirrors
   `mcrs/inference_utils.chat_history_parser`. The gold track is never in the query.
3. Builds a **candidate pool** = all gold tracks + random negatives (`--pool-size`).
   Every (model × variant) ranks within this *same* pool.
4. Renders each pool track under every **document variant** (`metadata`,
   `attributes_raw`, `attributes_nl`) and reports per-variant **coverage**
   (fraction of tracks with a non-empty doc — attribute variants are empty for
   tracks with no tags).
5. For each model: encodes queries once per mode — `symmetric` (no instruct;
   matches how the catalog was built/queried today) and `instruct` (Qwen3's
   asymmetric prefix) — then encodes each document variant and scores every
   (variant × mode) combination with the repo's own
   `evaluator.metrics.metrics_recsys.compute_metrics`.

**Validity:** absolute recall is inflated because the pool is a subset, not the full
47k catalog. **Only the relative ordering across models/modes is meaningful** — pool,
template, queries, and scoring are identical across models, so it's apples-to-apples.

---

## 5. Caveats to keep in mind when reading results

- **Subset pool** → don't compare these absolute numbers to the leaderboard. Compare
  models *to each other within this run*.
- **`max_length=512` right-truncation** clips the end of long 8-turn conversations
  (where the latest user turn lives). It's consistent across all models so the
  comparison is fair; if it looks like it's hurting, re-run with `--max-length 1024`.
- **Re-encoded 0.6B ≠ organizer's stored 0.6B vectors** (dtype/normalization differ
  slightly). That's intended — all three models go through one identical code path.
- **Attribute variants are tags-only.** Tempo/key/chord aren't in the published
  metadata, so `attributes_raw`/`attributes_nl` are built from `tag_list` alone.
  Watch their **coverage** — tracks with no tags get an empty doc and can't be
  retrieved by that variant, which caps its recall. Compare `attributes_raw` vs
  `attributes_nl` against **each other** (same coverage), not against `metadata`.

---

## 6. How to read it / decision criteria

- **Headline:** does 4B/8B beat 0.6B on **Recall@100** and **Recall@1000**? Those
  predict how much a downstream reranker has to work with.
- A meaningful win is a **consistent, non-trivial** recall lift across both
  `--seed` variations and at the fuller `--num-sessions 150` size — not a fraction
  of a point that flips with the sample.
- Also note **symmetric vs instruct**: if `instruct` clearly beats `symmetric`,
  that's a cheaper, separate win (query-side prompt) independent of model size.
- **If 8B ≈ 0.6B on recall:** the prior holds — encoder size isn't the lever; pivot
  to the query/representation side (and the tags-template rewrite). **If 8B clearly
  wins on recall:** it justifies the cost of re-embedding the full catalog at the
  larger size; quantify the gap before committing to that.

### Tags question (B)
- Compare **`attributes_nl` vs `attributes_raw`** at the *same* model + query mode
  (same coverage). If `attributes_nl` consistently wins, the tags branch was being
  hurt by **formatting**, not by the tags themselves — a cheap, high-value fix
  (rewrite the template, re-embed only the attributes column). If they're equal,
  the problem is deeper than formatting (the tag *vocabulary* doesn't align with
  conversational intents) and the branch likely stays demoted.
- `metadata` is expected to beat both attribute variants — that's not the question;
  it's the reference. The point is the raw-vs-NL delta.

---

## 7. After the run — write it up (per `experiments/CLAUDE.md`)

1. Save the printed table + JSON path. Add a short report under `experiments/`
   (naming per `experiments/CLAUDE.md`), summarizing: setup (pool size, sessions,
   seed), the table, and a verdict against §6.
2. Update `experiments/experiment_log.md` with the takeaway and next step.
3. If it changes the recommendation, note it in `changelog.md`. (Leaderboard is
   devset NDCG@20 on the *full* catalog, so a **subset** bake-off does **not** get a
   leaderboard row — call that out so nobody mistakes subset recall for a headline.)
4. Commit + push to `claude/embedding-tags-metadata-nvrRM`. Do **not** open a PR
   unless the user asks.

---

## 8. If something breaks

- **Auth/secret errors** → `.env` missing `HF_TOKEN`, or Modal token not set.
- **OOM on 8B** → lower `--batch-size` (it already auto-shrinks; try `--batch-size 8`)
  or rely on the GPU fallback list (H100 → A100-80GB → A100-40GB → L40S).
- **`No scorable examples`** → `--num-sessions` too small or gold tracks not in
  catalog; raise `--num-sessions`.
- **Low attribute coverage** → expected if many sampled tracks lack tags; it caps
  attribute-variant recall but doesn't bias the raw-vs-NL comparison (same pool).
- **Want a richer NL template** → edit `_render_attributes_nl` in
  `modal/embedding_bakeoff.py` (e.g. separate genre vs mood phrasing) and re-run.
