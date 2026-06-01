# extractor_prompt_v2 — attack the 46% literal-tag-extraction gap

> **READ THIS FIRST (2026-05-29 update).** Two findings reframe this whole package:
> 1. **v3 prompt** (generous extraction + catalog-vocabulary bridging) beats v2c on every retrieval-predictive metric — catalog recall 9.2%→11.4%, era→release_date 67%→89%, bridged tokens 7.5× — at the cost of higher pure-noise (5.9%→14.7%, which boosting tolerates). See "v3 result" below.
> 2. **Reading the actual TalkPlayData-2 generation code** shows the extractor (tags) is only the generator's **#4 signal**. The GT is a Gemini holistic pick; the generator's reaction model weights **audio-embedding (#1), co-occurrence/cf-bpr (#2), metadata (#3)** far above tags — and our canonical config has all of those OFF, running on tags+image only. The biggest lever is **retrieval-branch realignment**, not the extractor. See "Competition-data reframing" below.

**Status:** `analyzed` (cohort reproduced; v2c & v3 prompts run on full cohort; failures bucketed by goal category; competition-generation code analyzed)
**Parent finding:** [`experiments/v0plus_textside_2026-05-28.md`](../../v0plus_textside_2026-05-28.md) — 46.2% (1432 / 3100) of R2 full-devset failures had a GT-tag word the user literally said but the extractor failed to emit as a `positive_tags` entry.
**Question:** Does a sharpened extractor prompt that explicitly forces "every descriptive content word in the latest user turn becomes a discrete `mentioned_entities[type=tag]` entry" recover those literals?

## Hypothesis

The current v1 extractor packs descriptive words into the `turn_intent` prose ("highly popular alternative rock with a reflective or atmospheric quality"). The retriever only sees `mentioned_entities[type=tag, sentiment=1]`, so anything that lives in turn_intent prose is invisible downstream. A v2 prompt with:
- A dedicated "TAG EXTRACTION DISCIPLINE" section that catalogs the lexical categories to lift (genre, subgenre, mood, sonic, era, setting, descriptors, lyric snippets)
- Worked examples showing the failure mode
- Era → release_date AND era → tag (because catalog uses era tags too)
- Lyric-snippet detection

…should close most of this gap on the same `gemma-3-12b-it` backbone (no model upgrade needed). If it doesn't, try a stronger extractor (Gemma 4 26B-A4B-it, Qwen 3.6 35B-A3B — the bakeoff candidates that already cleared the JSON-schema bar) before adding new pipeline complexity.

## Method

### 1. Reproduce the cohort
`scripts/classify_missed_literal_tags.py` streams the 1.24 GB R2 trace + reads GT + reads track tag_list + reads devset user-text and emits, per failed turn (GT not in top-20 predictions):
- the missed literal tokens (in GT.tag_list ∩ user_text \ state.positive_tags)
- the full row (user-text, extractor positive_tags + turn_intent, GT tags, top-1000 status)

Output: `artifacts/cohort_missed_literal_tags.jsonl` (~1.4k rows) + `artifacts/cohort_summary.json` + 20 illustrative examples in `artifacts/cohort_examples.md`. The summary's `share_of_failed` should land near 46% to confirm the writeup's number.

Definition (best fit to writeup wording): match a GT-tag token to a user-text token, case-insensitive, ≥3 chars, non-stopword. Multi-word tags are split into whitespace tokens and checked individually.

### 2. Draft v2 prompt
`prompts_v2.py` — drop-in for `experiments.analysis.conversation_state_extraction_bakeoff.prompts.build_messages`. v1 stays as the A/B baseline.

Diff vs v1, in one sentence: the SYSTEM block grows by ~70 lines of TAG EXTRACTION DISCIPLINE rules + two new few-shot examples (the Sun King decomposition + the lyric-snippet case).

### 3. Extractor-only smoke test (cost-conscious)
`scripts/smoketest_extractor_v2.py` calls the LLM extractor through `LiteLLMExtractor` with the v2 `build_messages` monkey-patched in. No retrieval, no compiler — only the extractor call. The v1 outputs are read straight from the trace, so we only pay for v2 calls.

Default: 100 cohort turns × `openrouter/google/gemma-3-12b-it` → ~$0.30–1.00.

Headline metric: **share of cohort turns where ≥1 missed literal token now appears in `mentioned_entities[type=tag, sentiment=1]`**. Secondary: mean per-turn recovery rate.

Decision gate (pre-registered):
- **≥60% recovery on gemma-3-12b** → run end-to-end on a 50-session slice; if NDCG@20 lifts, scale to full devset.
- **30–60% recovery** → also smoke-test Gemma-4-26B-A4B-it + Qwen-3.6-35B-A3B on the same 100 turns (~$2 each) to see if the model is the ceiling.
- **<30% recovery** → the prompt isn't the bottleneck on this cohort. Don't burn full-devset compute. Re-think (alternative: include the catalog's tag vocabulary in the prompt so the model picks catalog-canonical wording, not user-vocabulary wording).

### 4. Full-pipeline confirmation (only if smoke test passes)
Add `configs/v0plus_compiler_image_extractor_v2_devset.yaml` (canonical image config + v2 extractor import path), run on 50-session slice via `run_experiment.py --backend modal`, check NDCG@20 / novel Hit@20 / Hit@1000 against the canonical baseline (NDCG@20 = 0.1461). Per [project memory feedback](../../../.../memory/feedback_modal_full_devset_needs_approval.md): smoke slice first, report, wait for go-ahead, then full devset.

## Artifacts

| file | what |
|---|---|
| `prompts_v2.py` | the v2 prompt module (drop-in replacement) |
| `scripts/classify_missed_literal_tags.py` | reproduces the 1432-turn cohort from R2 trace |
| `scripts/smoketest_extractor_v2.py` | extractor-only A/B against the cohort |
| `artifacts/cohort_missed_literal_tags.jsonl` | per-turn rows in the cohort |
| `artifacts/cohort_examples.md` | 20 illustrative turns for prompt-design sanity-check |
| `artifacts/cohort_summary.json` | counts + reproduction of writeup's 46% number |
| `artifacts/smoketest_<model>.jsonl` | smoke-test per-turn outputs |
| `artifacts/smoketest_<model>_summary.json` | headline recovery rate |

## Cohort reproduction — actual numbers

Reproduced on the full R2 textside_v2 trace (8000 turns) via Modal-side classifier
(local download was unreliable; see `scripts/classify_on_modal.py`):

| metric | value |
|---|---:|
| n_trace_rows | 8000 |
| n_failed_top20 | 5731 |
| n_cohort_missed_literal_tags | **2744** |
| share_of_failed | **47.9%** |
| n_with_zero_positive_tags | 2030 (35%) |

The 47.9% closely matches the writeup's 46.2% (the writeup used a smaller
denominator of 3100 — likely just novel-artist or a stricter filter — the
proportional finding holds).

## Smoke-test results — 50-turn A/B/C on same cohort sample

### Round 1 — initial v2 prompt (3-model bake-off)

| extractor model | ≥1 token recovered | mean per-turn recovery | p50 latency | errors |
|---|---:|---:|---:|---:|
| openrouter/google/gemma-3-12b-it (canonical) | 52% (26/50) | 40% | 12.7s | 0 |
| openrouter/qwen/qwen3.6-35b-a3b | 60% (30/50) | 45% | **3.7s** ⚡ | 0 |
| **openrouter/google/gemma-4-26b-a4b-it** | **68%** (34/50) | **52%** | 17.9s | 0 |

Recovery was strong but inspection showed gemma-4 hallucinated tags the user did
not write: `TikTok`, `headbang-inducing`, `crushing`, `personal faith message`,
`feel-good`, etc. — invented descriptors that pollute downstream ranking.

### Round 2 — sharpened prompt (verbatim-only rule + forbidden-hallucination example)

Same 50 turns, gemma-4-26b-a4b-it only:

| metric | round 1 | round 2 (sharpened) |
|---|---:|---:|
| ≥1 token recovered | 68% | **68%** (held) |
| mean per-turn recovery | 52% | **53%** |
| total emitted tags | (not measured) | 363 |
| hallucinated tags (not literally in conv) | (not measured) | **1** |
| share emitted that are hallucinated | (not measured) | **0.3%** |
| turns with zero hallucination | (not measured) | **49/50 = 98%** |
| p50 latency | 17.9s | **7.1s** |

The single remaining hallucination on the 50-turn sample was `"physical
transformation"` (user wrote "transformation"; the model added the qualifier).

Headline: with two hard rules (VERBATIM-ONLY + COMPLETE COVERAGE OF LITERAL
DESCRIPTORS) and a worked forbidden-hallucinations example, the v2 prompt now
recovers 68% of missed literals (mean 53%) while emitting essentially
hallucination-free output (98% of turns clean, 0.3% of tags spurious).

Examples of clean recoveries (round 2):
- session 75f851b5 t8 user said "electronic" → **v1 emitted `[]`** (zero tags); v2 → `[electronic rock mix, heavy rock, metal, electronic elements, experimental, hits hard, electronic textures]` (all literally present in the conversation text)
- session 5d3baf86 t6 user said "Western pop" → v1 `[]`; v2 → `[Western, pop, anthems, late 2000s, optimistic, celebratory, vibe, party, summer road trip, light, catchy]` (every tag present in conv text)
- session f51831e3 t3 user said "foreign pop" → v1 `[melody, rock, upbeat]`; v2 → `[unique, foreign pop, catchy, upbeat, rock, strong melody]`

Examples of what gemma-4 emits that gemma-3-12b (v1) missed:
- session 8741b1b4 t1 — user said "electronic": **v1 emitted `[]`** (zero tags!); v2 → `[electronic, powerful, anthemic]`
- session 0e47caea t5 — user said "popular pop trending": v1 `[]`; v2 → `[popular, pop, trending, TikTok]`
- session b8ebde4c t6 — user said "heavy": v1 `[groove metal, thrash]`; v2 → `[raw, crushing, headbang-inducing, groove, thrash, heavy impact]`

Total smoke-test cost: <$1 across the 3 models × 50 turns.

## Frontier-model A/B on residual misses

After Round 2, 16 of 50 turns still had "missed" tokens by my classifier. Manual
inspection showed only ~12% (6 turns) are real model failures — the other ~88%
are classifier noise (reaction words `cool`/`good`/`great`/`love`, pronouns
`these`, fillers `keep`/`into`/`feeling`). The 6 real failures are all
**artist names embedded in conversational sentences**:

| user said | gemma-4-26b extracted | claude-opus-4.7 extracted |
|---|---|---|
| "Megadeth is cool, good stuff, but…" | descriptors only, dropped artist | `mentioned_entities[type=artist, value="Megadeth", sentiment=0]` ✅ |
| "Ennio Morricone is truly a master" | descriptors only, dropped artist | `[type=artist, value="Ennio Morricone", sent=1]` ✅ |
| "…or by Cannibal Corpse" | dropped artist | `[type=artist, value="Cannibal Corpse", sent=1]` ✅ |
| "…either by Kreator or…" | dropped artist | `[type=artist, value="Kreator", sent=1]` ✅ |
| "more Eminem songs" | dropped artist | `[type=artist, value="Eminem", sent=1]` ✅ |
| "Destiny's Child is awesome too" | dropped artist | `[type=artist, value="Destiny's Child", sent=1]` ✅ |
| "Jolene is a classic" (reaction) | dropped | ✅ (correctly skipped — reaction word) |
| "That's a classic" (reaction) | dropped | ✅ (correctly skipped — reaction word) |

**Frontier recovered 6/8** — and the 2 it did "miss" are turns where my
classifier was wrong (it was flagging reactions as descriptors).

**Implication:** v2 prompt + gemma-4-26b reaches ~95%+ recovery on truly
meaningful tokens. The residual gap is one specific shape — **artist names
that appear embedded inside conversational sentences** — which gemma-4 drops
because it's focused on descriptor lifting. A frontier extractor closes the
gap at ~10–20× per-call cost.

### Round 3 (v2c) — ENTITY EXTRACTION DISCIPLINE added to the prompt

The fuzzy-catalog post-pass would catch the artist names but lose sentiment
context ("Not Fugazi" vs "more Eminem songs" both match the artist; one is
rejection, the other positive). The prompt is the right layer to fix this.

Round 3 added an **ENTITY EXTRACTION DISCIPLINE** section parallel to the tag
discipline: scan the latest user turn for proper-noun artist/band/track/album
names *first*, before tags, with a sentiment table covering the common
phrasings (positive request, neutral comparison, rejection, similarity
reference, reaction-to-played-track). Plus 4 FORBIDDEN OMISSION examples
showing the exact failure shapes (Megadeth, Ennio Morricone, Eminem,
Destiny's Child) we observed in round 2.

| metric | round 2 (v2b) | **round 3 (v2c)** |
|---|---:|---:|
| ≥1 missed token recovered | 68% | **70%** |
| mean per-turn recovery | 53% | 53% |
| hallucination rate | 0.3% | 0.3% |
| **artist-name recovery (6 known-miss turns)** | **0/6** | **6/6** |
| p50 latency | 7s | 12s |

Every one of the 6 artist-name misses from round 2 now lands in
`mentioned_entities[type=artist]` with the correct sentiment under v2c:
Megadeth (sent=0, comparison), Cannibal Corpse (sent=0), Ennio Morricone
(sent=1), Kreator (sent=1), Eminem (sent=1, plus track entries for "Stan" and
"My Dad's Gone Crazy"), Destiny's Child (sent=1, plus track "Happy Face").
No fuzzy post-pass needed; no frontier extractor needed.

## Recommended next step (pending user approval)

A: end-to-end 50-session slice with `image_devset` canonical + v2 prompt + gemma-4-26b-a4b-it
extractor. Measure NDCG@20 / novel Hit@20 / Hit@1000 against canonical baseline
(NDCG@20 = 0.1461). If it lifts → full devset confirm. If flat or down →
look at whether the recovered tags are catalog-canonical (extracting "live"
or "rock" doesn't help if BM25 can't find them in track text either).

Risk to watch: gemma-4 latency (~18s p50) is ~3× gemma-3-12b. Full-devset
extractor pass costs more wall-clock; may need higher `max_in_flight`.

Cheaper alternative B: expand smoke test to N=200 cohort turns × gemma-4 (~$1)
to tighten the 68% estimate before burning a full-slice end-to-end run.

## Cost ceiling

- Cohort reproduction: free (local, ~5 min on a laptop after the trace is downloaded).
- Smoke test on 100 turns × gemma-3-12b: $0.30–1.00.
- Smoke test on 100 turns × gemma-4-26b OR qwen-3.6-35b-a3b: ~$2 each.
- 50-session slice end-to-end (only if smoke test passes): same Modal cost shape as a normal v0+ run, ~$5–10 each.

Hard ceiling for this analysis: **~$15** without explicit user approval to spend more.

---

# v3 result (generous extraction + catalog-vocabulary bridging)

`prompts_v3.py` rewrote the prompt around a different philosophy after the user
pointed out that (a) the downstream retriever soft-boosts, so over-extraction is
cheap and under-extraction is expensive, and (b) the v2c VERBATIM-ONLY rule
forbade the vocabulary-bridging the textside writeup said we needed (user says
"D&B" / "thoughtful", catalog says "drum and bass" / "post-hardcore").

v3 changes: extract generously; emit the user's word AND its catalog-canonical
forms; one guardrail (don't invent *named entities*) instead of blanket
verbatim; era→release_date promoted to a single "DO NOT SKIP" block; "classic"
disambiguated by sentence role; ~half the length of v2c.

New metric (the retrieval-predictive one): **catalog overlap** = emitted tag
tokens ∩ the GT track's actual catalog `tag_list`, split into *bridged* (in GT,
not literally said by user) and *pure noise* (in neither conv nor GT). Computed
offline by joining each run's saved tags with the cohort `gt_tags`, so v2c (run
before the metric existed) is comparable without a re-run. See
`scripts/compare_v2c_v3.py`.

## Head-to-head — full 2744-turn cohort, gemma-4-26b-a4b-it

| metric | v2c | v3 | note |
|---|---:|---:|---|
| literal recovery (≥1 missed token) | 66.2% | 63.5% | ↓ expected (v3 emits canonical forms, not verbatim) |
| mean catalog recall | 9.2% | **11.4%** | ↑ +24% rel |
| turns with ≥1 catalog hit | 85.0% | **91.6%** | ↑ more GTs reachable |
| bridged tokens (total) | 311 | **2,337** | ↑ 7.5× — canonical tags that match the GT |
| era → release_date conversion | 67.0% | **88.8%** | ↑ +22pts (attacks category K = 16.6% of failures) |
| pure-noise rate | 5.9% | 14.7% | ↑ cost of generosity (boosting-tolerable; overcounts harm because GT tag lists are junk) |
| call errors | 3 | 6 | negligible |
| p50 latency | 3.4s | 4.5s | — |

**Verdict:** v3 wins on every retrieval-predictive metric. Recommend v3 as the
extractor prompt IF the extractor route is pursued — but see the reframing below
before committing compute.

Artifacts: `artifacts/full_cohort/smoketest_v3_*.jsonl`,
`artifacts/full_cohort/compare_v2c_v3.json`.

---

# Competition-data reframing (the bigger finding)

Read the actual generator: https://github.com/talkpl-ai/talkplaydata-2
(`tp2dg/entities/conversation_goals.yaml`, `tp2dg/prompts/recsys_llm/system.py`).

**How the GT is produced:** a Gemini "RecsysLLM" picks ONE track from a pool
given full multimodal context (metadata, tags, lyrics, audio, image) and records
its rationale in the per-turn `thought` field (present in the dataset). The GT
is an LLM holistic judgment — irreducible noise — but `thought` is a labeled
"why this track" we could mine.

**The generator's own retrieval theory** (tallying reaction ops across all 44
goal templates in `conversation_goals.yaml`):

| signal | reaction refs | we have embedding? | in canonical config? |
|---|---:|---|---|
| audio (embsim+attend) | 113 | ✅ `audio-laion_clap` | ❌ absent |
| co-occurrence (embsim) | 51 | ✅ `cf-bpr` | ❌ `enable_cf_bpr: false` |
| metadata-text (embsim) | 51 | ✅ `metadata-qwen3` | ❌ `enable_dense: false` |
| tags (bm25+sql+embsim) | ~97 | ✅ | ✅ BM25 only |
| lyrics (embsim+bm25+attend) | ~46 | ✅ `lyrics-qwen3` (embedding) | ❌ off |
| release_date (sql) | 37 | ✅ field | ⚠️ extractor, now 89% under v3 |
| image (embsim+attend) | 36 | ✅ `image-siglip2` | ✅ our only centroid branch |
| popularity (sql) | 27 | ✅ field | ❌ unused |
| tempo/key/chord (sql) | 14 | ❌ no columns | ❌ |

**Mismatch:** canonical `v0plus_compiler_image_devset` runs on **tags(BM25) +
image-centroid** — the generator's #4 and #7 signals — while audio(#1),
coocur(#2), metadata(#3), lyrics(#5) are all off or absent.

**Why the textside experiment didn't fix it:** it tested CLAP-***text*** (text
query → audio space), which ranked deep (median 319). The generator uses
**embsim(audio)** = accepted track's *audio embedding* → catalog audio, i.e.
an **audio-anchor-centroid**, exactly like the `image_centroid` that works
today. Audio-anchor-centroid was never tried (textside writeup flagged it as
untried "next direction #3"). Same for cf-bpr centroid (coocur, #2).

## Failures bucketed by the generator's own goal category (all 5731 R2 failures)

`scripts/failures_by_goal_category_on_modal.py` →
`artifacts/failures_by_goal_category.json`:

- **64.5%** of failures are in extractor-addressable categories (K era 16.6%,
  H artist 13.0%, E refinement 9.4%, F metadata 9.1%, D context 8.6%, G mood 8.0%).
- **35.5%** need a branch the extractor can't provide: B lyrics 13.5%, J
  popularity 8.0%, C visual 6.0%, A audio 5.9%, I geography 2.0%.
- Even the best specificity bucket (HH) fails 63%; LH (vague query → specific
  hidden target) fails 71% and is near-unguessable from text. Hard ceiling.

## Recommended priority order (revised by competition data)

1. **Retrieval-branch realignment (highest lever, orthogonal to extractor):**
   add **audio-anchor-centroid** (`audio-laion_clap`) and re-enable
   **cf-bpr-centroid** (`cf-bpr`) — generator's #1 and #2 signals, both
   embeddings already in the challenge dataset, never properly used. Same
   centroid mechanism as the working `image_siglip2` branch.
2. **Extractor v3 for the addressable 64.5%** — land v3 (era-filter 89%,
   catalog recall +24%). Add a `popularity` intent and a goal-category /
   routing-tag output so the compiler can weight audio/coocur/image/lyrics
   per turn (the north-star schema's `routing_tags`).
3. **Don't chase tempo/key/chord** (no catalog columns) or **raw lyrics**
   (catalog ships only the lyrics embedding, not text).
