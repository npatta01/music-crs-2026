# v0+ text-side retrieval — Rounds 1–4 + failure-mode taxonomy — 2026-05-28

**Status:** `analyzed`
**Question:** Can anchor-free text-side retrieval (SigLIP-2 text-side → image_siglip2 column, LAION-CLAP music text-side → audio_laion_clap column) lift the novel-artist cohort that the proven image_centroid baseline can't reach?

**Headline:** No textside config beats the canonical `v0plus_compiler_image_devset` on NDCG@20. The architecture works (verified, novel-artist pool coverage measurably grew) but the new candidates rank too deep to translate into top-K wins without a reranker downstream. The investigation also produced a per-branch-rank trace diagnostic, a 4-bucket novel-artist failure taxonomy (A1–A4), and an aggregate failure analysis on 3100 failed turns that reframes where the ceiling actually sits.

Canonical config remains `v0plus_compiler_image_devset` (NDCG@20 = 0.1461). Textside configs are kept on disk as experimental artifacts.

---

## What we built

Six new YAML configs under `configs/v0plus_compiler_textside_*_devset.yaml`, all backed by a refactored compiler that supports:

- **Per-branch encoder dispatch.** `DenseBranch.encoder_id` selects from an `encoders: dict[str, EmbeddingClient]` map on `V0PlusCompiler`. YAML schema: top-level `encoders:` block. Back-compat with the legacy single-`encoder:` block preserved (all 38 existing tests pass).
- **Per-branch query template.** `DenseBranch.query_id` selects a query builder from a registry — `intent`, `sonic`, `sonic_nl`, `sonic_nl_enriched`, `visual`, `lyric`. Adding a new template is a single method + registry entry.
- **Per-branch GT-rank diagnostic.** `CompilerConfig.branch_trace_topk` (default 0 = off). When > 0, each turn's trace gets a `branch_rankings` map with each branch's top-K candidate IDs, enabling offline analysis of "where did the GT rank inside each retriever?" Decoupled from inference-time cost when off.
- **Modal `MultimodalTextEncoder` service** — single GPU container hosting both `SigLIP2TextEmbeddingClient` (768d, `google/siglip2-base-patch16-224`) and `ClapTextEmbeddingClient` (512d, `laion_clap` HTSAT-base + RoBERTa, music checkpoint `music_audioset_epoch_15_esc_90.14.pt`). Local `ModalMultimodalTextEmbeddingClient` exposes both as `EmbeddingClient` Protocols. Deployed.

### Catalog-convention verification (pre-flight)

Both text-side encoders were validated to live in the same embedding space as the catalog vectors before any retrieval run. Method: 200 random catalog tracks, encode `"artist - tags[:6]"` via the text encoder, cosine vs the catalog column for the same track, lift over random pairings.

| modality | cos_same_mean | cos_random_mean | lift over random |
|---|---:|---:|---:|
| SigLIP-2 text → image-siglip2 | 0.102 | 0.074 | **+0.028** |
| **CLAP music text → audio-laion_clap** | **0.261** | 0.096 | **+0.165** (6× SigLIP) |

CLAP music text-side has substantially stronger text↔modality alignment than SigLIP-2, because the LAION-CLAP music checkpoint was trained on (audio, caption) pairs of music while SigLIP was trained on general web image-caption pairs (cover art is a noisy proxy for music style).

---

## Round results — all on 50-session slice (400 turns: 236 novel, 164 continuation) unless noted

### R1 — `v0plus_compiler_textside_devset` (shared `intent` query, equal weights)
BM25 + image_centroid + SigLIP-text(intent) + CLAP-text(intent), all four branches at equal RRF weight.

- Slice novel Hit@1000 = **0.335** vs baseline 0.288 (**+16.2%**) — coverage win confirmed.
- Slice NDCG@20 = 0.128 vs baseline 0.145 (**−11.6%**) — ranking loss, novel −42.7%.

**Diagnosis:** The shared `turn_intent` query is mixed-vocabulary (sonic + visual + artist names + lyrical themes). Each text-side encoder gets noise it can't use; uniform RRF lets two noise-heavy branches outvote image_centroid on continuation.

### R2 — `v0plus_compiler_textside_v2_devset` (per-encoder queries `sonic` + `visual`)
Same fusion as R1 but SigLIP uses `query_id=visual` ("album cover, {tags}"), CLAP uses `query_id=sonic` ("music: {tags}; {turn_intent}").

| metric | baseline | R2 slice | R2 full devset |
|---|---:|---:|---:|
| NDCG@20 | 0.145 / **0.146** | 0.133 | 0.132 (−10%) |
| Novel Hit@20 | 0.051 / **0.073** | 0.055 | 0.066 (−9%) |
| Novel Hit@1000 | 0.288 / **0.371** | 0.335 | 0.389 (+5%) |

Full-devset confirmed the slice pattern: novel-artist pool coverage modestly lifts, top-K ranking gets worse. The two new branches contribute mostly redundant pool depth + ranking noise.

### R3 — `v0plus_compiler_textside_v3_devset` (sonic_nl + lyric + asymmetric weights, drop SigLIP)
Three changes, motivated by Phase B (below):
1. CLAP-text uses `query_id=sonic_nl` ("A song with {tags} sound, similar to {artists}"). Phase B showed +120% top-20 lift on novel-only.
2. New conditional `lyric` branch on `lyrics_qwen3_embedding_0_6b` (only fires when state has lyric-hint vocabulary).
3. SigLIP-text branch dropped (Phase A per-branch trace showed it contributed only 189 unique novel turns out of 4777 ≈ 4%).
4. Asymmetric weights: CLAP w=0.5, lyric w=0.4, BM25 and image_centroid w=1.0.

Slice: NDCG@20 = 0.137 (−5.4% vs baseline), continuation recovered (0.299 vs baseline 0.304), novel Hit@1000 = 0.331.

### R3a / R3b ablations
- **R3a** (sonic_nl only, drop lyric): slice novel Hit@1000 = **0.339** — best of all variants. Confirms CLAP contributes; lyric was neutral.
- **R3b** (lyric only, no CLAP): slice metrics indistinguishable from baseline on every cohort. Lyric branch is "do no harm" but adds essentially nothing.

### R4 — `v0plus_compiler_textside_v4_devset` (multi-CLAP-recall)
Three CLAP queries against the same audio column, fused via RRF. Each captures different turn types (per Phase B). Plus the R3b conditional lyric branch.

| metric | baseline | R4 (slice) | Δ |
|---|---:|---:|---:|
| Overall Hit@1000 | 0.570 | **0.600** | +5.3% |
| Overall Hit@200 | 0.460 | **0.488** | +6.0% |
| Novel Hit@1000 | 0.288 | **0.343** | **+19.1%** |
| **Novel Hit@200** | 0.131 | **0.178** | **+35.5%** |
| Novel Hit@20 | 0.051 | 0.047 | −8% |
| NDCG@20 | 0.145 | 0.139 | −3.8% |
| Hit@20 | 0.280 | **0.295** | +5.4% |
| MRR | 0.110 | 0.098 | −11% |

R4 is the strongest recall-pipeline config we built. On the slice it lifts novel-artist Hit@200 by +35% while continuation is preserved. Not run on full devset (slice variance flagged before committing the compute).

---

## Phase A — per-branch GT-rank diagnostic on R2 full devset

After the R2 full-devset NDCG@20 loss, the new `branch_rankings` trace was used to ask: where does the GT rank inside each retriever? Computed across all 4777 novel-artist turns:

### Novel cohort

| branch | in_top20 | in_top1000 | median rank when found |
|---|---:|---:|---:|
| **bm25** | **0.071** | **0.365** | 204 |
| centroid (image) | 0.008 | 0.115 | 306 |
| clap_text (sonic) | 0.014 | **0.242** | 319 |
| siglip2_text (visual) | 0.011 | 0.138 | 340 |

### Continuation cohort

| branch | in_top20 | in_top1000 | median rank when found |
|---|---:|---:|---:|
| bm25 | 0.509 | 0.978 | 19 |
| **centroid (image)** | **0.544** | 0.793 | **10** |
| clap_text | 0.012 | 0.289 | 334 |
| siglip2_text | 0.011 | 0.156 | 308 |

Key facts:
- **Image centroid is the engine of baseline NDCG@20 on continuation** — 54.4% of GTs in top-20, median rank 10.
- **CLAP-text is the only material new-candidate contributor on novel** (24.2% Hit@1000) but its candidates rank deep (median 319) — coverage, not ranking.
- **SigLIP-text is essentially redundant** (13.8% novel Hit@1000, mostly overlapping with BM25).
- Equal-weight RRF lets noisy mid-rank picks (CLAP rank 3) outvote image_centroid's rank-10 GT on continuation, which is why R2 lost continuation NDCG@20.

---

## Phase A — novel-artist bucket taxonomy (4777 turns)

Bucketed every novel-artist turn by whether the production R2 found the GT in BM25 / text-side / nowhere:

| bucket | n | % | what's happening |
|---|---:|---:|---|
| **A1 BM25 top-20** | 337 | 7.1% | 68% are turn-1 explicit-name queries ("Play Ice Cube's *It Was A Good Day*"). BM25 nails it on artist/track text match. |
| **A2 BM25 pool only (deep)** | 1405 | 29.4% | Median BM25 rank **318**. Tag overlap ≥ 1. Refinement / playlist_build modes. This is the reranker-shaped bucket. |
| **A3 Text-side only** | 979 | 20.5% | Tag overlap = 0 (BM25 has no text path). CLAP contributes 435/979 uniquely (44% of this bucket). Late-turn, refinement-mode. The bucket where CLAP earns its keep. |
| **A4 Total miss** | 2056 | **43.0%** | No branch finds GT in top-1000. Median state.tag ∩ GT.tag = 0. Mixed intent modes. |

A4 is the dominant fact. 43% of novel-artist turns are unreachable by any branch in this set. (Phase B partially walked this back — see below.)

---

## Phase B — query A/B on 499 novel-artist turns (CLAP only, isolated)

Tested 3 CLAP query templates against the audio_laion_clap column, with local LanceDB ANN, no fusion:

| variant | template | Hit@20 | Hit@1000 |
|---|---|---:|---:|
| v1 (Round 2 production) | `"music: {tags}; {turn_intent}"` | 0.010 | 0.216 |
| **v2 (natural language)** | `"A song with {tags} sound, similar to {artists}"` | **0.022** (**+120%**) | **0.246** (**+14%**) |
| v3 (pure tags) | `"{tags}"` | 0.012 | 0.208 |

**Critically, v2 recovered 14% of the A4 "unreachable" bucket** (30 of 219 sampled A4 turns went from rank > 1000 to rank ≤ 1000). The 43% A4 ceiling I claimed earlier is partially queryshape, not structural.

Per-bucket pattern:
- v1 wins on **A3** (current production behavior, tag-rich short queries)
- v2 wins on **A2 + A4** (variety-seeking, vocabulary-mismatch turns)
- No single template wins everywhere — motivates the R4 multi-CLAP architecture.

### Phase B+v4 — enrich query with anchor-track catalog-canonical tags
Tested a fourth variant — append top-N tags from anchor tracks to bridge user vocabulary → catalog vocabulary:

| variant | overall Hit@1000 | A3 | A2 | A1 | A4 |
|---|---:|---:|---:|---:|---:|
| v2 (NL) | 0.246 | 0.402 | 0.320 | 0.211 | 0.137 |
| v4 (enriched) | 0.251 | **0.446** | 0.333 | 0.184 | 0.123 |

Net +2 turns out of 499 (essentially a wash). The lift on continuation-shaped novel turns (A3) is real (+0.044) but anchor-tag enrichment hurts direction-changing turns (A4, A1) where the user wants variety different from the anchors. Still useful as one of three queries in the R4 multi-recall config.

---

## A4 deep-dive — failure modes in the "unreachable" bucket

Pulled 8 random samples from the 2056 A4 turns. Six recurring failure modes, ranked by share:

1. **Catalog tag quality** (~25–30%). GT tags include user-generated junk: `'bagel'`, `'somafm'`, `'macedead'`, `'kev'`, `'jones'`. No genre signal. Sample: Protomartyr "The Chuckler" has 3 GT tags, 0 useful.
2. **Vocabulary mismatch with good catalog tags** (~25–30%). State extracts user-language tags (`'thoughtful'`, `'storytelling'`); GT has good catalog-language tags (`'post-hardcore'`, `'melodic hardcore'`). Same intent, different vocabulary.
3. **Dataset noise — GT contradicts stated intent** (~15–20%). User explicitly demands 80s post-punk → GT is a 2017 pop track. User repeats "play No More Parties in LA" → GT is a 2004 Caribbean dance track. User rejects Fugazi → GT is Fugazi. **Unfixable from retrieval angle**.
4. **Lyric/theme queries with no audio signal** (~15%). User asks for "songs with meaningful lyrics about personal struggles." CLAP encodes audio (not lyrics); SigLIP encodes image; BM25 has no lyric column. We need a dedicated lyric text mode (which is missing — only the qwen3 lyric embedding exists, not raw text).
5. **Popularity ceiling under broad tags** (~10%). User asks `'Latin', 'pop', 'dance'`. GT matches all three but doesn't rise above thousands of similar tracks.
6. **Era constraint not honored** (~5–10%). User says "80s," our `release_date` `hard_filter` helps when extracted but ANN ranking ignores era.

---

## Multi-dimensional Hit@1000 split — the gap reframed

Bucketing R4 slice failures by multiple dimensions, not just novel-vs-continuation:

| dimension | bucket | n | Hit@1000 |
|---|---|---:|---:|
| **state↔GT artist overlap** | match | 178 | **0.966** |
| | no match | 222 | **0.306** |
| **GT artist catalog size** | head (20+) | 188 | 0.691 |
| | mid (5–19) | 114 | 0.649 |
| | long-tail (<5) | 98 | **0.367** |
| **goal_category** | K | 88 | 0.693 |
| | F / H | 96 | 0.667 |
| | **B (vague-recall)** | 56 | **0.375** |
| **n_positive_tags** | 0 | 136 | 0.551 |
| | 1–2 (sweet spot) | 59 | **0.746** |
| | 3–5 | 164 | 0.585 |
| | 6+ | 41 | 0.610 |
| **state↔GT tag overlap** | 0 | 251 | 0.538 |
| | 1+ | 149 | 0.705 |

The artist-overlap dimension is overwhelming — 97% vs 31% — and the novel-vs-continuation split is largely a proxy for it. The richer cuts are:
- Long-tail GT (37%) → popularity-balanced retrieval needed
- Goal cat B vague-recall (37%) → lyric snippet / wider candidate generation
- 0 tags extracted (55%) → extractor improvement

---

## Aggregate failure-mode analysis — R2 full devset (3100 failed turns)

The single most actionable finding from the whole investigation:

| failure mode | n / 3100 | share | who can fix it |
|---|---:|---:|---|
| **Extractor missed a GT-tag word the user literally said** | **1432** | **46.2%** | **Better extractor prompt** |
| F1 No state↔GT artist overlap | 2838 | 91.5% | (largely a consequence of the above) |
| F2 Long-tail GT artist (<5 catalog) | 1090 | 35.2% | New retriever (cf-bpr / popularity-balanced) |
| F3 Goal category B (vague-recall) | 441 | 14.2% | Lyric / wider candidate generation |
| F4 Zero positive tags extracted | 1211 | 39.1% | Better extractor prompt |
| F5 Zero state↔GT tag overlap | 2039 | 65.8% | Better extractor + vocabulary bridging |
| F1a Extractor missed a named artist | 295 | 9.5% | Better extractor + fuzzy artist match |

### Walking through one concrete failure per mode

**F1a / F4 — Beatles "Sun King" (session ba3da7b0, turn 8)**
After 7 turns of alternative-rock recommendations the assistant picks The Beatles. State has 6 positive artists, 7 positive tracks, **zero positive tags**, no Beatles mention.

```yaml
turn_intent: "Another highly popular alternative rock track with a reflective or atmospheric quality,
              similar to Red Hot Chili Peppers - On Mercury, from the late 90s or early 2000s."
positive_tags: []                     # extractor packed everything into turn_intent
hard_filters: []                      # "late 90s or early 2000s" never became release_date filter
```

Extractor failures: (a) descriptive words "popular alternative rock atmospheric reflective" should be discrete tag mentions, not just turn_intent prose. (b) "late 90s or early 2000s" should be a release_date hard_filter. Dataset issue: GT is from 1969 — outside the user's stated era.

**F2 — Cro-Mags "Hard Times" (long-tail)**
```
USER: "I'm looking for 80s American hardcore punk bands known for their raw energy and short, intense songs."
STATE: positive_tags = ['80s', 'American', 'hardcore punk', 'raw energy', 'intense']  ✓ all correct
GT artist Cro-Mags has 2 catalog tracks. State↔GT tag overlap: 4 tokens.
```
State is perfect. This is pure long-tail retrieval bias. No extractor change helps; needs a new retriever shape.

**F3 — Green Day "Basket Case" via lyric snippet**
```
USER: "Play the song with the exact lyrics 'Do you have the time to listen to me whine'"
STATE: turn_intent has the lyric; positive_tags = [], positive_artists = []  ✓ correct
```
State correctly captures intent. We have no lyric-text retriever (only the qwen3 semantic embedding, which doesn't do exact-snippet match). Needs a new retrieval modality, and we lack the raw lyrics in the catalog.

**F5 — Fugazi "Bad Mouth" (explicit rejection)**
```
USER: "Fugazi is legendary... but I was looking for something more sonically chaotic"
STATE: positive_tags = ['80s','American hardcore','punk','chaotic','noisy','abrasive','dissonant']
       explicit_rejections = [{kind: artist, value: 'Fugazi'}]  ✓ correctly extracted
GT: Fugazi "Bad Mouth"
```
State is excellent. The GT is the explicitly-rejected artist. **Pure dataset noise** — no retrieval system can be expected to recommend a rejected artist. This is the ~15–20% floor.

---

## What's promising vs not

| direction | merge as canonical? | reason |
|---|---|---|
| Compiler refactor (per-branch encoder/query, branch_traces) | YES (infrastructure) | Back-compat preserved; tests pass; enables all future experiments. |
| Modal MultimodalTextEncoder service | YES (deployed) | Verified working; reusable. |
| CLAP music text-side encoder + verify script | YES (verified) | Cosine lift +0.165 is real. |
| R4 textside_v4 config | NO | Best slice recall but NDCG@20 loses. Available as experimental artifact. |
| All other R1–R3 configs | NO | Superseded by R4 or by the conclusion that this direction doesn't beat baseline on NDCG@20. |
| Canonical config change | NO | `v0plus_compiler_image_devset` stays canonical. |

---

## Recommended next iterations (prioritized by leverage)

1. **Revised extractor prompt** (attacks 46% of failures). Force complete tag extraction (every descriptive word also becomes a tag mention), force era → release_date hard_filter, flag lyric snippets, parse "different from X" as explicit_rejection more aggressively. Single prompt change + LiteLLM cache flush. Highest expected lift / lowest cost.
2. **Long-tail / popularity-balanced retrieval** (attacks 35%). Either resurrect the cf-bpr branch with a warm cache, add a per-track popularity prior to post-fusion ranking, or add a tag-rarity boost. Smallest cost: post-fusion boost.
3. **Anchor-track audio centroid in CLAP space** (untried, mentioned but not built). Use the AUDIO embedding of accepted anchor tracks as the CLAP query — not text. Same shape as image_centroid but in audio space. Should attack a portion of A4 by sidestepping the text-to-audio alignment problem.
4. **Reranker on top-K pool** (deferred). The A2 bucket (29% of novel turns, median BM25 rank 318) is literally a ranking problem. The data is loudly pointing here.
5. **Lyric raw text** (attacks 14% — goal B). Requires sourcing raw lyric text outside the talkpl-ai catalog. Not available today.

The extractor prompt change is the unambiguous top priority — single prompt + one cache flush, attacks the largest fixable bucket.

## Artifacts

| tid | config | notes |
|---|---|---|
| v0plus_compiler_textside_v2_devset | sonic + visual, equal w | only one with full-devset trace (1.24GB) |
| v0plus_compiler_textside_v3b_devset | lyric branch only | "do no harm" reference |
| v0plus_compiler_textside_v4_devset | 3× CLAP + lyric | best slice recall |

Trace files in `evaluator/exp/inference/devset/` and on the Modal results volume.

## Commits

Code changes landing with this report:
- `compiler_v0plus.py`: `DenseBranch.encoder_id` + `query_id`; encoder map; 5 new query templates; `branch_trace_topk` diagnostic.
- `compiler_v0plus_qu.py`: parse `encoders:` block; validate branch encoder_id references; per-turn `branch_rankings` injection into trace.
- `modal/app.py`: `MultimodalTextEncoder` service (SigLIP-2 + CLAP music); `verify_textside` local entrypoint.
- `modal/download_results.py`: recognize `_trace.json` sidecars.
- New encoder clients: `siglip2_text_embedding.py`, `clap_text_embedding.py`, `modal_multimodal_client.py`.
- Verification script: `scripts/verify_textside_catalog_convention.py`.
- Experimental configs: `v0plus_compiler_textside_{v2, v3b, v4}_devset.yaml`.
