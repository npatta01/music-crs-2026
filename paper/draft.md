# Team npatta01's Conversational Music Recommender for the RecSys Challenge 2026

**Nidhin Pattaniyil, Semih Yagli, Tanwir Zaman** — Independent Researchers

*Draft v3 for co-author review — mirrors paper/main.tex after an external (Antigravity) review pass. Body fills exactly 4 pages, references on page 5 — precisely the ACM 4+1 limit. Figures 1–4 are real in the PDF. Every number is verified against the repo or the official leaderboard CSV.*

---

## Abstract

We describe team npatta01's submission to the RecSys Challenge 2026 conversational music recommendation task: given a multi-turn dialog, retrieve 20 tracks from a 47,071-track catalog and generate a natural-language response. The pipeline extracts a typed conversation state with an LLM, gathers candidates from eleven retrieval branches over a single LanceDB collection, re-ranks the pooled candidates with a LightGBM LambdaMART model whose dominant feature is a fine-tuned conversational bi-encoder cosine, and generates a state-conditioned response. On the final Blind-B leaderboard the submission scored 0.3811 composite (nDCG@20 0.2537, LLM-judge 3.30), ranking 29th of 39 teams. We report the system in full, and then examine our own result: an in-sample development estimate (nDCG@20 0.38–0.46) created misplaced confidence while leakage-safe out-of-fold evidence (0.197–0.203) had already predicted the blind outcome; the benchmark's single-ground-truth labels carry a quantified *anchoring bias* that teaches rankers to copy the just-played artist; and concrete failure cases from the submitted run show extracted constraints the pipeline could not enforce. Code, models, and a zero-credential reproduction bundle: https://github.com/npatta01/music-conversational-music-recomender-2026.

## 1 Introduction

The Music-CRS challenge [1, 2] asks systems to act as a conversational music recommender. Each session is a multi-turn dialog between a listener and an assistant; at every assistant turn the system must (i) retrieve a ranked list of 20 tracks from a shared 47,071-track catalog and (ii) write a short natural-language response presenting its top recommendation. Training data comprises 15,199 sessions built on the TalkPlayData 2 collection [3], with per-track metadata (title, artist, album, up to 37 genre/mood tags, popularity, release date) and precomputed embeddings (text, audio, cover art, collaborative filtering). Evaluation is on two 80-session blind splits of final turns; Blind-B additionally removes the conversation-goal annotations present in training data. Submissions are scored with a composite metric:

Composite = 0.50 · nDCG@20 + 0.10 · catalog diversity + 0.10 · lexical diversity + 0.30 · (judge − 1)/4,

where "judge" is a 1–5 LLM-as-a-judge rating of the generated response. A 1,000-session development split with public per-turn ground truth (one target track per turn) supports offline iteration.

Our system is a retrieve-then-rerank pipeline conditioned on an explicitly compiled conversation state. Per the challenge's participant-paper mandate we document the full pipeline (Section 2) and results (Section 3); because we finished mid-pack, Section 4 is an unusually frank retrospective. Contributions:

1. A complete, reproducible pipeline: LLM state extraction → eleven-branch retrieval over one LanceDB collection → LambdaMART re-ranking → state-conditioned response generation.
2. An evaluation-lineage lesson: our in-sample development replay (nDCG@20 0.38–0.46) drove selection confidence, while leakage-safe out-of-fold estimates (0.197–0.203) already anticipated the blind result (0.2537).
3. A fine-tuned conversational bi-encoder whose single cosine feature carries 59% of the reranker's decision weight and replaces a label-noise-induced "artist-copy" shortcut.
4. A quantified analysis of ground-truth anchoring bias, with concrete failure cases from our submitted run and a cleaned, LLM-re-judged label set released alongside our code.

Related work in brief: the design follows the retrieve-then-rerank pattern standard in large-catalog recommendation, with reciprocal-rank fusion [4] for multi-source pooling, LambdaMART [5, 6] for learned ranking, and LLM-based dialog state tracking; the organizers' framework provided the evaluation harness.

## 2 Approach

[Figure 1 — full-width pipeline diagram, real in the PDF.] Conversation + user profile → state extraction (deepseek-v4-flash → typed JSON) → resolver (names → catalog IDs) → eleven branches over one LanceDB collection (BM25 + tiered tag resolver; dense text ×3; CLAP text→audio; anchor centroids SigLIP-2/CLAP/CF; user-CF centroid; discography + era lookups) → pool union (≤500/branch) → LightGBM LambdaMART (146 features) → top-20 → response LLM. Dashed side path: weighted RRF + post-fusion as baseline & fallback.

### 2.1 Understanding the conversation: state extraction

At each turn we prompt deepseek-v4-flash (via OpenRouter, JSON-schema constrained) to emit a typed conversation state, projected onto an 11-field contract: current request, intent mode (open-explore / refinement / pivot / playlist-build), per-track feedback with roles, mentioned entities, hard filters (release-date), explicit rejections (artist / track / tag), routing flags, lyrical theme, and a soft release-year range. A fuzzy resolver grounds surface names to catalog IDs so downstream stages operate on identifiers. Cheaper extraction models under-filled optional fields (rejections, attribute facets) in our checks, so all final runs use deepseek-v4-flash. Extraction runs once per turn and is cached.

[Figure 2 — worked example box, real in the PDF.] Real Blind-B turn (session 024a2738…): user hunts a specific song ("subdued, female singer, a sense of place in the lyrics, stark almost a cappella delivery… not it either"). Extracted state (abridged): request_type hidden_target; anchor artist Neko Case (must_use); rejected tracks "Calling Cards", "Man"; facets mood=subdued, lyrical_theme=sense of place, sonic=stark almost a cappella. Top-1: Neko Case — "Bracing For Sunday", with the submitted response quote.

### 2.2 Gathering candidates: one collection, eleven branches

All per-track information lives in a **single LanceDB collection**: metadata fields, a Tantivy full-text index, and every embedding column — three Qwen3-Embedding text views (metadata, attributes, lyrics; 1024-d), LAION-CLAP audio (512-d) [8], SigLIP-2 cover art (768-d) [9], BPR collaborative-filtering vectors (128-d) [10], and our bi-encoder document vectors (2560-d, Section 2.4). Every retrieval branch is a differently-shaped query against the same table — in principle the whole retrieval step could be one composed query clause (Section 4.4).

Eleven branches produce candidate pools per turn (Figure 1): (1) BM25 [11] over title / artist / album / tags with field boosts, where free-text mood and genre phrases pass through a **tiered tag resolver** — exact, alias, and substring matching against the catalog tag vocabulary with an embedding nearest-neighbor fallback (cosine ≥ 0.6, top-3); (2–4) dense ANN over the three Qwen3 text views; (5) CLAP text-to-audio; (6–8) centroids over liked anchor tracks in SigLIP-2, CLAP, and CF-BPR space, gated by intent mode (a pivot suppresses anchoring); (9) the user's own CF vector; (10–11) lookups from resolved-artist discographies and era popularity. Weighted reciprocal-rank fusion [4] (k=60, top-1000) plus post-fusion multiplicative adjustments (rejected artists/tracks dropped, played tracks dropped, exact-membership tag promotes/demotes, year-range decay) yields an explicit ranking that serves as **baseline and fallback**.

### 2.3 Ranking with a learned model

The submitted system replaces the fused order entirely: a LightGBM LambdaMART [5, 6] model scores the **union of the branch pools** (each truncated to its top 500) and emits the final top-20. It sees 146 features per (turn, track) pair: per-branch rank/score/margin/hit features, pool-normalized z-scores and percentiles, content and behavioral cosines, session/artist-affinity counters, tag and lexical overlap, popularity, extracted-state categoricals, and a constraint sidecar. Table 1 groups them by family with each family's share of total split gain in the deployed model; one feature — the bi-encoder cosine b1_cos — carries 59.0% of all gain. The RRF rank itself is *excluded*: the ranker sees raw branch evidence, not the fused opinion. After scoring, config-gated guards run (exact-track pins; a final-artist guard in the Blind-B configuration).

Table 1 — reranker feature families (share of total gain, deployed model).

| Family | Features | Gain share | Examples |
|---|---|---|---|
| Bi-encoder cosine | 1 | 59.0% | b1_cos |
| Per-branch rank/score | 66 | 11.5% | BM25 rank, dense margins |
| Session / artist affinity | 18 | 10.7% | same-artist, played count |
| Other similarity cosines | 17 | 8.9% | CLAP/SigLIP centroids |
| Popularity | 7 | 5.0% | popularity percentile |
| State / intent | 14 | 2.2% | request type, intent mode |
| Tag / lexical overlap | 10 | 2.0% | IDF tag overlap |
| Constraints / rejections | 13 | 0.7% | rejected-artist flag |

Training uses the per-turn ground-truth track as a binary label (LambdaRank objective optimizing nDCG@20; learning rate 0.025; 127 leaves; truncation 200; 5-fold user-grouped cross-validation; ~20.6M rows). Because the ground truth is noisy (Section 4.2), labels are down-weighted when the *next* turn contradicts them: ×0.3 if goal progress says the recommendation did not move toward the goal, ×0.3 if the user rejects the ground-truth track, ×0.6 if they reject its artist. The deployed bundle is *goal-free*: trained without the conversation-goal fields Blind-B removes. Cost shaped the training set: state extraction and per-turn retrieval tracing run through a paid LLM API, so the model trains on a 30,000-turn subset (~25% of the ~121.6k-turn split); the data-scaling curve had not flattened at that size.

### 2.4 The conversational bi-encoder behind b1_cos

[Figure 3 — two-tower diagram, real in the PDF.] Conversation rendering ([prev] user turn t−1 / [now] user turn t / [prev_track] artist — title) and track card (artist — title (year) | tags ≤5 | known for: LLM line) → shared fine-tuned Qwen3-Embedding-4B encoder (last-token pool, L2-norm) → 2560-d unit vectors → cosine → b1_cos reranker feature.

The reranker's dominant feature comes from a two-tower bi-encoder fine-tuned from Qwen3-Embedding-4B [7] (Figure 3). The query tower renders the conversation compactly behind a retrieval instruction prefix — `[prev] <user turn t−1> [now] <user turn t> [prev_track] <artist — title>` — and the document tower renders a track card — `Music track: artist — title (year) | tags: ≤5 | known for: <LLM line>` — whose one-line LLM-written "known for" artist description imports static world knowledge from larger models into the embedding space. One shared encoder E_θ serves both towers; with v_x = E_θ(x)/‖E_θ(x)‖₂ (last-token pooling, 2560-d), the feature is the cosine b1_cos(q,d) = v_qᵀv_d. Training minimizes the in-batch contrastive (MNRL) loss with temperature τ = 1/20 over batches of positive pairs, each with four mined hard negatives (the softmax denominator ranges over in-batch documents plus the hard negatives). Positives are conservative: the 53,885 (turn, track) pairs whose next-turn goal-progress annotation says the recommendation *moved the session forward*. Document vectors for all 47,071 tracks are precomputed into the collection; the conversation vector is encoded live with caching.

We deploy the bi-encoder *scout-only*: as a retrieval branch it added little coverage, but as a feature its cosine became the top signal (Table 1) — and a *generalizing replacement* for a shortcut learned from biased labels (Section 4.2): in leakage-safe out-of-fold ablations, removing the artist-consensus shortcut features reduces nDCG@20 by 0.0070, while adding b1_cos more than recovers the loss (+0.0091) with the shortcut absent.

### 2.5 Writing the response

The response generator is Qwen3-30B-A3B-Instruct-2507 [12] at temperature 0: a single pass over the top-1 track rendered as a delimited XML block (≤10 tags; the delimiting stops the model from echoing raw metadata) plus the *latest* extracted state. The deployed template's full style instruction is:

> *"Write 1–2 concise sentences about only the selected track. Prioritize the latest user request and extracted state over older conversation history. If the track is reasonably aligned, explain the fit with one specific supported reason. If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it or blame the system; briefly frame the limitation and the closest supported reason."*

Template choice matters: over a frozen Blind-A retrieval output, a sweep of eight templates moved the judge score from 3.95 to 4.70 without touching the recommendations. There is no multi-draft sampling, selection, fact-checking, or repair pass. On the development split we score retrieval only; both blind submissions use live generation.

Code, configs, trained models, cached extraction states, and a frozen-LLM-cache reproduction bundle that replays our submissions without API credentials are public: https://github.com/npatta01/music-conversational-music-recomender-2026 (models and data: https://huggingface.co/datasets/Npatta01/music-crs-repro-2026).

## 3 Results

The development split (1,000 sessions × 8 turns) has one ground-truth track per turn, so Recall@k equals Hit@k. Table 2 reports development-split numbers *with their evaluation lineage made explicit*; Table 3 reports the official leaderboard results.

Table 2 — development split, with evaluation lineage. The in-sample row replays turns the deployed (full-data) model saw during training; the out-of-fold rows are leakage-safe cross-validation estimates.

| System (lineage) | nDCG@20 | Hit@20 |
|---|---|---|
| Weighted RRF fusion (no training) | 0.1492 | 0.3183 |
| LambdaMART, out-of-fold CV | 0.1970 | — |
| + b1_cos (deployed feature set) | 0.2032 | — |
| LambdaMART, *in-sample replay* | 0.3844 | 0.5610 |

Footnote: an earlier in-sample capture of the predecessor reranker model read 0.4562. Official Blind-B nDCG@20: 0.2537 — between the out-of-fold estimates and far below the in-sample replay.

Table 3 — official CodaBench results (composite = 0.50·nDCG@20 + 0.10·catalog div. + 0.10·lexical div. + 0.30·(judge−1)/4).

| Split | nDCG@20 | Catalog div. | Lexical div. | Judge | Composite | Rank |
|---|---|---|---|---|---|---|
| Blind-A (dev phase) | 0.4380 | 0.0313 | 0.7670 | 4.20 | 0.5389 | — |
| Blind-B (final) | 0.2537 | 0.0315 | 0.7862 | 3.30 | 0.3811 | 29/39 |

Read honestly, Table 2 says two things. Learned re-ranking over the pooled candidates does beat static fusion — but by the leakage-safe estimate (0.149 → 0.197–0.203), not by the in-sample replay (→ 0.384) that we watched during development. And the blind result (0.2537) is consistent with the out-of-fold evidence that was available before submission. Feature attribution is strikingly concentrated (Table 1): one learned similarity carries 59% of gain, and classic signals (artist affinity, popularity) outweigh most hand-engineered lexical features.

## 4 Retrospective: Where It Went Wrong

### 4.1 Our development estimate was in-sample

The deployed reranker was fit on all of its feature data (the CV folds informed early stopping, then a full-data model shipped), and our headline development numbers came from *replaying splits the model had seen*. The resulting 0.38–0.46 development estimates drove selection confidence; the leakage-safe out-of-fold numbers (0.197–0.203), which we had, predicted the blind outcome (0.2537) far better. We flag this as a measurement-and-confidence failure rather than a proven cause of the final ranking — but it shaped every decision late in the competition, including which ideas looked "already good enough" to skip. The lesson is old but evidently worth restating: *report and act on the out-of-fold number, even when the in-sample number is the one on the dashboard*.

### 4.2 The ground truth contradicts itself

The benchmark's per-turn ground truth is a *sibling pick* from the listener's real session — the track actually played next — not an editorial judgment of the request. In a manual sample only 62% of ground-truth tracks were a clear fit to the request, 26% a loose fit, and 11% no fit. The dominant failure shape is **anchoring** (Figure 4).

[Figure 4 — conversation box, real in the PDF.] User: "…something with a similar chill, electronic vibe, but **from a different artist**?" (just played: Bonobo) → ground truth: Bonobo — "Jets" [annotation: MOVES toward goal]. Next turn: "'Jets' is cool, but I was actually hoping for something **from a different artist this time**…" → ground truth: Bonobo — "Pieces" [annotation: MOVES toward goal].

To measure it we re-judged all 106,393 training turns (and 7,000 development turns) with an LLM pipeline: two inexpensive judges score each (request, ground-truth) pair on two axes — did the user ask for a different artist, and does the track fit the request — and a stronger arbiter re-judges conflicts *blind to the synthetic reaction annotation*. Results: 57.4% of turns judged negative; 18,222 are anchoring negatives; 5,880 of those carry a synthetic "listener liked it" annotation — poisoned positives for any goal-progress-based training scheme, including our bi-encoder's. A second pattern — the user rejects the ground-truth track on the next turn — motivated our ×0.3 label down-weighting. Anchored labels teach a specific wrong lesson: *copy the last artist*. Our ablations show the ranker exploiting exactly this, and the bi-encoder cosine replacing the shortcut (Section 2.4). Since every team is scored against the same labels, the bias depresses and partially reshuffles all measured scores. We release the cleaned relabeling with our code; the submitted models were *not* trained on it.

### 4.3 Failure cases from the submitted run

A label-free LLM-judge audit of our 80 submitted Blind-B turns rated 68% weak-or-bad fits; for 31 of 79 judged turns a better candidate was *already in the retrieved pool* but ordered below the top-20 (versus 8 turns lost to over-aggressive filtering, 3 to state extraction, 1 to resolution) — with the caveat that hidden-label frequencies are unknown. Concrete cases from the submitted predictions:

- **Anchoring at serving time.** "Another alt-country song… but **from a different artist than Ryan Adams**" → our top-1 was *Ryan Adams & The Cardinals*, plus five more of their tracks in the top-20. The rejection resolved to the solo "Ryan Adams" catalog ID; the band-variant ID passed the hard-drop. The system reproduced exactly the bias of Section 4.2.
- **Rejected artist in the list.** "Symphonic black metal with strong **female operatic vocals**, **not Cradle of Filth**" → four Cradle Of Filth tracks in the top-20 (a duplicate artist-ID variant escaped the drop), and the top-1 was a male-fronted power-metal track — there is no vocal-attribute field to enforce.
- **Impossible exact request.** "Play 'Watercolors' by Pat Metheny" — the track does not exist in the 47k catalog. We returned Pat Metheny's "Alfie" without acknowledging the gap; an honest "that track is unavailable" response would likely have scored better with the judge.
- **Unactionable constraint.** "Any aggressive metal track that **exactly matches 126.70 bpm and G minor**, with tempo and key stated" — the catalog has no BPM or key fields; the constraint could neither filter nor be verified, and the response could not state what the ask demanded.

### 4.4 Where the pipeline lost information

**Rich extraction, uneven execution.** The state captured most of what users said, but each branch consumed only a slice of it and late fusion discarded the cross-field structure — despite one collection making a single composed query (filters + text + vectors) possible. Tag handling illustrates it: the BM25 clause resolves free-text moods to canonical tags via the tiered resolver, yet post-fusion tag promotes/demotes and the reranker's overlap features use exact string membership, and only one soft feature (tag_emb_cos) sees semantic tag similarity.

**Entity identity is fragmented.** Rejections were enforced by exact catalog ID, but artist identity in the catalog is not one ID per act (band variants, duplicates). Both leak cases above stem from this: a name-level or fuzzy-identity veto would have caught what the ID-exact drop missed.

**No co-occurrence or transition evidence.** Behavioral signal entered only through CF-BPR centroids and lookups; the pipeline had no direct track-to-track co-occurrence or sequential-transition lane, and no LightGBM column can recreate a signal that never entered the pipeline.

**Static knowledge, single-pass response.** LLM world knowledge entered only offline (the "known for" lines); nothing in the serving path reasons over candidates, which hidden-target requests (Figure 2) demand. The response was one temperature-0 draft with no selection, checking, or repair — and at 30% of the composite, our 3.30 judge score left the largest single block of points on the table.

## 5 Conclusion

We documented a state-compiled retrieve-then-rerank conversational music recommender in full, and audited our own mid-pack result honestly: an in-sample development estimate inflated confidence that leakage-safe evidence had already contradicted; the benchmark's single-label ground truth carries a quantified anchoring bias that our own submission reproduced at serving time; and several extracted constraints had no catalog fields or identity resolution to act on. We release the pipeline, models, a zero-credential replay bundle, and a cleaned relabeling of the training turns for future iterations.

---

## References

1. Music-CRS Challenge 2026 (RecSys Challenge). NLP4MusA organizers. https://nlp4musa.github.io/music-crs-challenge/
2. RecSys Challenge 2026. https://www.recsyschallenge.com/2026/
3. TalkPlay / TalkPlayData 2: multimodal conversational music recommendation dataset. https://huggingface.co/collections/talkpl-ai/talkplay-data-challenge
4. Cormack, G. V., Clarke, C. L. A., Büttcher, S. Reciprocal rank fusion outperforms Condorcet and individual rank learning methods. SIGIR 2009.
5. Ke, G., et al. LightGBM: a highly efficient gradient boosting decision tree. NeurIPS 2017.
6. Burges, C. J. C. From RankNet to LambdaRank to LambdaMART: an overview. MSR-TR-2010-82.
7. Qwen team. Qwen3 Embedding: advancing text embedding and reranking. arXiv:2506.05176, 2025.
8. Wu, Y., et al. Large-scale contrastive language-audio pretraining (LAION-CLAP). ICASSP 2023.
9. Tschannen, M., et al. SigLIP 2: multilingual vision-language encoders. arXiv:2502.14786, 2025.
10. Rendle, S., et al. BPR: Bayesian personalized ranking from implicit feedback. UAI 2009.
11. Robertson, S., Zaragoza, H. The probabilistic relevance framework: BM25 and beyond. Foundations and Trends in IR, 2009.
12. Qwen team. Qwen3 technical report (Qwen3-30B-A3B). arXiv:2505.09388, 2025.
13. DeepSeek. DeepSeek-V4-Flash model card (OpenRouter). 2026.
14. LanceDB: serverless vector database. https://lancedb.com (software).

---

Reviewer checklist for co-authors:

- The retrospective now leads with the in-sample-evaluation admission (4.1). Comfortable with that framing? It is labeled a measurement/confidence failure, not the proven cause.
- Failure cases in 4.3 are real sessions from the submitted Blind-B run (verified against the trace). Flag any you'd rather not print.
- No team comparisons anywhere, per our decision; the retrospective webpage stays separate from the paper.
- Numbers: Blind-B 0.2537 / 3.30 / 0.3811 rank 29/39; Blind-A 0.4380 / 4.20 / 0.5389; RRF 0.1492; OOF 0.1970 → 0.2032; in-sample 0.3844 (0.4562 older); b1_cos 59.0%; 53,885 pairs; 30k of ~121.6k turns; 62/26/11; 18,222 / 5,880; audit 68% weak-or-bad, 31/79 better-candidate-in-pool.
