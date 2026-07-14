# npatta01 at the RecSys Challenge 2026: Multi-Branch Retrieval with a Learned Reranker for Conversational Music Recommendation

**Nidhin Pattaniyil, Semih Yagli, Tanwir Zaman** — Independent Researchers

*Draft for co-author review. Target: ACM sigconf, 4 pages + 1 page references. Figures are described in bracketed placeholders; they exist as sketches and will be typeset in LaTeX. Every number below is copied from a verified source (repo file or official leaderboard CSV) — please flag anything that reads wrong rather than editing numbers directly.*

---

## Abstract

We describe the npatta01 submission to the RecSys Challenge 2026 conversational music recommendation task: given a multi-turn dialog, retrieve 20 tracks from a 47,071-track catalog and generate a natural-language response. Our pipeline extracts a typed conversation state with an LLM, gathers candidates from eleven retrieval branches over a single LanceDB collection, re-ranks the pooled candidates with a LightGBM LambdaMART model, and generates a state-conditioned response. On the final Blind-B leaderboard our submission scored 0.3811 composite (nDCG@20 0.2537, LLM-judge 3.30), ranking 29th of 39 teams. We report two observations that we believe generalize beyond our submission: learned re-ranking over pooled candidates was by far the dominant lever (2.6× NDCG@20 over static rank fusion on identical candidates), and the benchmark's single-ground-truth labels carry a measurable *anchoring bias* — the ground truth frequently stays on the just-played artist even when the user explicitly asks for a different one — which teaches rankers a shortcut we had to ablate away. Code, models, and a zero-credential reproduction bundle: https://github.com/npatta01/music-conversational-music-recomender-2026.

## 1 Introduction

The Music-CRS challenge [1, 2] asks systems to act as a conversational music recommender. Each session is a multi-turn dialog between a listener and an assistant; at every assistant turn the system must (i) retrieve a ranked list of 20 tracks from a shared 47,071-track catalog and (ii) write a short natural-language response presenting its top recommendation. Training data comprises 15,199 sessions built on the TalkPlayData 2 collection [3], with per-track metadata (title, artist, album, up to 37 genre/mood tags, popularity, release date) and precomputed embeddings (text, audio, cover art, collaborative filtering). Evaluation is on two 80-session blind splits of final turns; Blind-B additionally removes the conversation-goal annotations present in training data. Submissions are scored with a composite metric:

> Composite = 0.50 · nDCG@20 + 0.10 · catalog diversity + 0.10 · lexical diversity + 0.30 · (judge − 1)/4,

where "judge" is a 1–5 LLM-as-a-judge rating of the generated response. A 1,000-session development split with public per-turn ground truth (one target track per turn) supports offline iteration.

Our system is a retrieve-then-rerank pipeline conditioned on an explicitly compiled conversation state. This paper documents the full pipeline (Section 2), the numbers behind it (Section 3), and — because we finished mid-pack — an unusually frank discussion of where the score was lost (Section 4). Our contributions:

1. A complete, reproducible conversational music recommendation pipeline: LLM state extraction → multi-branch retrieval over one LanceDB collection → LambdaMART re-ranking → state-conditioned response generation.
2. Evidence that learned re-ranking is the dominant lever on this task: on identical pooled candidates, our reranker lifts devset NDCG@20 from 0.149 (weighted reciprocal-rank fusion) to 0.384.
3. A fine-tuned conversational bi-encoder whose single cosine feature carries 59% of the reranker's decision weight and replaces a label-noise-induced "artist-copy" shortcut.
4. A quantified analysis of ground-truth anchoring bias in the benchmark labels, with a cleaned, LLM-re-judged label set released alongside our code.

Related work in brief: our design follows the retrieve-then-rerank pattern standard in large-catalog recommendation and web search, with reciprocal-rank fusion [4] for multi-source candidate pooling, LambdaMART [5, 6] for learned ranking, and LLM-based dialog state tracking in the spirit of conversational recommender systems surveys; the organizers' baseline framework provided the evaluation harness.

## 2 Approach

> **[Figure 1 — full-width pipeline diagram.]** Conversation → LLM state extraction (typed JSON) → resolver (names → catalog IDs) → eleven retrieval branches over one LanceDB collection, grouped as lexical / dense text / cross-modal / behavioral / lookup → branch-pool union → LightGBM LambdaMART → top-20 → response LLM. A side path shows weighted RRF fusion producing the baseline/fallback ranking.

### 2.1 Understanding the conversation: state extraction

At each turn we prompt `deepseek-v4-flash` (via OpenRouter, JSON-schema constrained) to emit a typed conversation state, which is projected onto an 11-field contract consumed by retrieval: current request text, intent mode (open-explore / refinement / pivot / playlist-build), per-track feedback with roles (accepted / rejected / seed), mentioned entities (artists, tracks, albums, tags), hard filters (release-date), explicit rejections (artist / track / tag), routing flags (e.g., lyrics-focused, visual), lyrical theme, and a soft release-year range. A fuzzy resolver then grounds surface names to catalog IDs, so downstream stages operate on identifiers rather than strings. We initially used smaller, cheaper extraction models, but in our checks they under-filled optional fields (rejections, attribute facets) that drive retrieval and filtering, so all final runs use `deepseek-v4-flash`. Extraction runs once per turn and is cached; the same cached states serve every downstream experiment.

> **[Figure 2 — single-column worked example (real Blind-B session).]** Turn 3 of session `024a2738…`: the user is hunting a specific song ("subdued, female singer, a sense of place in the lyrics, stark almost a cappella delivery… not it either"). Extracted state (abridged): request_type `hidden_target`; anchor artist Neko Case (must-use); two candidate tracks already rejected ("Calling Cards", "Man"); facets mood=subdued, lyrical_theme=sense of place, sonic=stark almost a cappella. System's top-1: Neko Case — "Bracing For Sunday". Submitted response: "You're looking for something subdued with a strong sense of place and a stark, almost a cappella delivery—and *Bracing For Sunday* fits that mood perfectly. Neko Case's haunting, intimate vocals carry the weight of a quiet, specific moment, like a solitary figure in a weathered room, making the song feel both deeply personal and grounded in a distinct place."

### 2.2 Gathering candidates: one collection, eleven branches

All per-track information lives in a **single LanceDB collection**: metadata fields, a Tantivy full-text index, and every embedding column — three Qwen3-Embedding text views (metadata, attributes, lyrics; 1024-d), LAION-CLAP audio (512-d) [8], SigLIP-2 cover art (768-d) [9], BPR collaborative-filtering vectors (128-d) [10], and our own bi-encoder document vectors (2560-d, Section 2.4). Because one collection holds text, filters, and vectors together, every retrieval branch is just a differently-shaped query against the same table — and in principle the whole retrieval step could be expressed as one composed query clause (a point we return to in Section 4.3).

Eleven branches produce candidate pools per turn: (1) BM25 [11] over title / artist / album / tags with field boosts, where free-text mood and genre phrases are first passed through a **tiered tag resolver** — exact, alias, and substring matching against the catalog tag vocabulary, with an embedding nearest-neighbor fallback (cosine ≥ 0.6, top-3) for phrases that match nothing lexically; (2–4) dense ANN over the three Qwen3 text views, with query text built from the extracted state; (5) CLAP text-to-audio; (6–8) centroid queries over anchor tracks the user liked, in SigLIP-2, CLAP, and CF-BPR space, gated by intent mode (a pivot suppresses anchoring); (9) the user's own CF vector; (10–11) lookup pools from resolved-artist discographies and era popularity. Weighted reciprocal-rank fusion [4] (k = 60, top-1000) over the branch pools, followed by post-fusion multiplicative adjustments (rejected artists/tracks dropped; played tracks dropped; exact-membership tag promotes/demotes; year-range decay), yields an explicit ranking that serves as our **fusion baseline and as the fallback** when the learned ranker is unavailable.

### 2.3 Ranking with a learned model

Static fusion plateaued early (NDCG@20 0.149 on devset), so the final system replaces the fused order entirely: a LightGBM LambdaMART [5, 6] model scores the **union of the branch pools** (each truncated to its top 500) and emits the final top-20. The model sees 146 features per (turn, track) pair: per-branch rank/score/margin/hit features for every retriever, pool-normalized z-scores and percentiles, content and behavioral cosines, session/artist-affinity counters, tag and lexical overlap, popularity, extracted-state categoricals, and a constraint sidecar (played, rejected-artist, rejected-track flags). Table 1 groups them by family with their share of total split gain in the deployed model; a single feature — the bi-encoder cosine `b1_cos` (Section 2.4) — carries 59.0% of all gain. Notably, the RRF rank itself is *excluded* from the feature set: the ranker sees raw branch evidence, not the fused opinion. After scoring, config-gated guards run (exact-track pins when the user names a track; a final-artist guard for the Blind-B configuration).

**Table 1 — reranker feature families (share of total gain, deployed model).**

| Family | # features | Gain share | Examples |
|---|---:|---:|---|
| Bi-encoder cosine | 1 | 59.0% | `b1_cos` |
| Per-branch rank/score | 66 | 11.5% | `rank__bm25`, `margin__dense.metadata` |
| Session / artist affinity | 18 | 10.7% | `same_artist_session`, `artist_played_count` |
| Other similarity cosines | 17 | 8.9% | `clap_centroid`, `siglip_centroid`, `user_cf` |
| Popularity | 7 | 5.0% | `pop_pct`, `within_artist_pop` |
| State / intent | 14 | 2.2% | `request_type`, `intent_mode` |
| Tag / lexical overlap | 10 | 2.0% | `tag_overlap_idf`, `title_in_msg` |
| Constraints / rejections | 13 | 0.7% | `rejected_artist_exact`, `is_played_track` |

Training uses the devset protocol's single ground-truth track as a binary label (lambdarank objective, NDCG@20 metric, learning rate 0.025, 127 leaves, truncation 200, 5-fold user-grouped cross-validation, ~20.6M candidate rows). Because the generator's ground truth is noisy (Section 4.2), labels are down-weighted when the *next* turn contradicts them: ×0.3 if the goal-progress annotation says the recommendation did not move toward the goal, ×0.3 if the user rejects the ground-truth track, ×0.6 if they reject its artist. The deployed bundle is *goal-free*: trained without the conversation-goal fields that Blind-B removes, so training-time inputs match test-time reality. One cost constraint shaped the training set: because state extraction and per-turn retrieval tracing run through a paid LLM API, building features for the full ~121.6k-turn training split was too expensive; the deployed model trains on a 30,000-turn subset (~25%), and the data-scaling curve had not flattened at that size.

### 2.4 The conversational bi-encoder behind `b1_cos`

> **[Figure 3 — single-column two-tower diagram.]** Conversation rendering and track card feed one shared fine-tuned Qwen3-Embedding-4B encoder; last-token pooling and L2 normalization give 2560-d unit vectors; their cosine becomes the reranker feature `b1_cos`.

The reranker's dominant feature comes from a two-tower bi-encoder fine-tuned from Qwen3-Embedding-4B [7]. The query tower renders the conversation compactly — previous user turn, current user turn, and the previously played track — behind an instruction prefix; the document tower renders a track card: artist, title, year, up to five cleaned tags, and a one-line LLM-written "known for" description per artist, which imports static world knowledge from larger models into the embedding space. One shared encoder serves both towers (last-token pooling, L2-normalized 2560-d outputs), trained with in-batch contrastive loss (MNRL, scale 20) plus four mined hard negatives per positive. Positives are deliberately conservative: only the 53,885 (turn, track) pairs whose next-turn goal-progress annotation says the recommendation *moved the session forward*. Document vectors for all 47,071 tracks are precomputed into the same LanceDB collection; the conversation vector is encoded live with caching.

We deploy the bi-encoder *scout-only*: as a retrieval branch it added little candidate coverage, but as a reranker feature its cosine became the single most important signal (Table 1) — and, importantly, a *generalizing replacement* for a shortcut the ranker would otherwise learn from biased labels (Section 4.2): in held-out ablations, deleting the artist-consensus shortcut features costs −0.0070 NDCG@20, and adding `b1_cos` more than recovers it (+0.0091) with the shortcut absent.

### 2.5 Writing the response

The response generator is `qwen3-30b-a3b-instruct-2507` at temperature 0. It receives the top-1 track rendered as XML (metadata plus at most 10 tags) together with the *latest* extracted state, under a constraint-aware template instructing one to two concise sentences that stay honest about unmet constraints. Template choice matters: over a frozen Blind-A retrieval output, a systematic sweep of eight templates moved the official LLM-judge score from 3.95 to 4.70 without touching the recommendations. On the development split we score retrieval only (responses disabled); both blind submissions use live generation.

Code, configs, trained models, cached extraction states, and a frozen-LLM-cache reproduction bundle that replays our submissions without any API credentials are public: https://github.com/npatta01/music-conversational-music-recomender-2026 (models and data at https://huggingface.co/datasets/Npatta01/music-crs-repro-2026).

## 3 Experiments

The development split (1,000 sessions × 8 turns) has one ground-truth track per turn, so Recall@k equals Hit@k; we report NDCG@20 as the headline. Table 2 isolates the pipeline's main lever on identical candidate pools; Table 3 reports the official leaderboard results.

**Table 2 — development split: static fusion vs. learned re-ranking (same candidate pools).**

| System | NDCG@20 | Hit@20 | MRR |
|---|---:|---:|---:|
| Weighted RRF fusion (baseline) | 0.1492 | 0.3183 | 0.1015 |
| + LambdaMART reranker (submitted bundle) | **0.3844** | **0.5610** | **0.3325** |

*Footnote: reranker row is a local recapture of the exact submitted (goal-free) bundle; an earlier full-cluster capture of the preceding v10-era bundle read 0.4562 before subsequent pipeline pruning.*

**Table 3 — official CodaBench results (composite = 0.50·nDCG@20 + 0.10·catalog div. + 0.10·lexical div. + 0.30·(judge−1)/4).**

| Split | nDCG@20 | Catalog div. | Lexical div. | Judge | Composite | Rank |
|---|---:|---:|---:|---:|---:|---:|
| Blind-A (dev phase) | 0.4380 | 0.0313 | 0.7670 | 4.20 | 0.5389 | — |
| **Blind-B (final)** | 0.2537 | 0.0315 | 0.7862 | 3.30 | **0.3811** | **29/39** |

The learned ranker more than doubles NDCG@20 over static fusion (0.149 → 0.384) and lifts Hit@20 from 0.32 to 0.56 — the largest single improvement in our development history; no retrieval-side change came close. Feature attribution is strikingly concentrated (Table 1): one learned similarity carries 59% of gain, and classic recommendation signals (artist affinity, popularity) still matter more than most hand-engineered lexical features.

## 4 Discussion: gaps and lessons

### 4.1 Ranking was the lever

Every large gain we realized came from re-ordering candidates we already had, not from retrieving new ones. A label-free audit of our final Blind-B submission (an LLM judge over all 80 final turns, with no access to ground truth) points the same way: 68% of judged turns were rated weak-or-bad fits, and for 31 of 79 turns a *better candidate was already present in the retrieved pool* but ordered below the top-20 — versus 8 turns lost to over-aggressive filtering, 3 to state extraction, and 1 to entity resolution. Only a single turn violated a hard constraint (a rejected artist resurfacing at top-1). We read this as a property of the task: with 47k tracks, a dozen heterogeneous signals, and conversational constraints, hand-set fusion weights cannot express the ranking function; investment should go to the learned ranker and its training signal.

### 4.2 The ground truth contradicts itself

The benchmark's per-turn ground truth is a *sibling pick* from the listener's real session — the track they actually played next — not an editorial judgment of the request. In a manual sample we rated only 62% of ground-truth tracks a clear fit to the request, 26% a loose fit, and 11% no fit. The failure has a dominant shape we call **anchoring**:

> **[Figure 4 — single-column conversation box (real training session).]** User: "…something with a similar chill, electronic vibe, but **from a different artist**?" (just played: Bonobo) → ground truth: **Bonobo — "Jets"**, with the synthetic reaction annotation "MOVES [toward goal]". Next turn: "'Jets' is cool, but I was actually hoping for something **from a different artist this time**…" → ground truth: **Bonobo — "Pieces"**, again annotated as moving toward the goal.

To measure the phenomenon we re-judged all 106,393 training turns (and 7,000 development turns) with an LLM pipeline: two inexpensive judges score each (request, ground-truth track) pair on two axes — did the user ask for a different artist, and does the track fit the request content — and a stronger arbiter re-judges every conflict *blind to the synthetic reaction annotation*. The result: 57.4% of turns judged negative overall; 18,222 turns are anchoring negatives (ground truth stays on the just-played artist against an explicit request otherwise), and 5,880 of those carry a synthetic "the listener liked it" annotation — poisoned positives under any goal-progress-based training scheme, including ours (Section 2.4's MOVES-only positives predate this analysis). A second contradiction pattern — the user explicitly rejects the ground-truth track on the next turn — motivated our ×0.3 label down-weighting.

Anchored labels do not merely add noise; they *teach a specific wrong lesson*: copy the last artist. Our reranker ablations show the model exploiting exactly this (artist-consensus features), and the fine-tuned bi-encoder cosine replacing that shortcut with a signal that survives the shortcut's removal (Section 2.4). Because every team is scored against the same labels, we expect this bias to depress — and partially reshuffle — all measured scores, not only ours. We release the cleaned two-axis relabeling (train + dev) with our code; the submitted models were *not* trained on it, and doing so is the obvious next step.

### 4.3 Where we fell short

**We under-used our own extracted state.** One collection makes a single composed query possible — filters, text, and vectors in one clause — but we never issued one: each branch consumed its own slice of the state and late fusion discarded the cross-field structure. Tag handling illustrates the inconsistency: the BM25 clause resolves free-text moods to canonical catalog tags through the tiered resolver, but post-fusion tag promotes/demotes and the reranker's overlap features match the user's raw words by exact string membership, and only one soft feature (`tag_emb_cos`) sees semantic tag similarity. The same extracted signal is treated three different ways depending on the stage that consumes it.

**Only static world knowledge in the loop.** We imported LLM world knowledge offline (the per-artist "known for" lines in the bi-encoder's track cards), but no serving-path component can *reason* about candidates. Hidden-target requests — "find the specific subdued Neko Case song with a sense of place" (Figure 2) — are knowledge-and-reasoning queries; embeddings alone under-serve them.

**Constraints extracted but not actionable.** Only release-date is enforceable as a hard filter, and entity-level rejections as drops. Musical-attribute constraints the extractor happily captures — BPM/tempo, key, instrumentation, "female singer", "stark almost a cappella" — have no corresponding catalog fields, so they ride only through soft embedding similarity and cannot filter or be verified.

**Not all of our experiments were valid.** We ran many offline experiments whose conclusions did not survive: pipeline drift between capture dates and the label noise of Section 4.2 silently invalidated several internal comparisons. This paper therefore reports only externally validated leaderboard numbers plus the single internally consistent devset pair of Table 2.

## 5 Conclusion

We presented a state-compiled retrieve-then-rerank pipeline for conversational music recommendation, in which a learned LambdaMART ranker over pooled multi-branch candidates delivered essentially all of the headline gain, powered dominantly by one fine-tuned conversational bi-encoder feature. Our main transferable finding is about the benchmark itself: single-ground-truth conversational labels inherit an anchoring bias from real listening sessions that both depresses measured scores and teaches rankers the wrong invariance, and we release a cleaned relabeling to support future iterations. Team npatta01's code, models, and reproduction bundle are public at the links above.

---

## References (to be BibTeX'd in Phase B)

1. Music-CRS Challenge 2026 (RecSys Challenge). NLP4MusA organizers. https://nlp4musa.github.io/music-crs-challenge/
2. RecSys Challenge 2026. https://www.recsyschallenge.com/2026/
3. Doh, K., et al. TalkPlay / TalkPlayData 2: multimodal conversational music recommendation dataset. (dataset collection: talkpl-ai/talkplay-data-challenge on Hugging Face; cite the TalkPlay paper + dataset report)
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

*Reviewer checklist for co-authors:*
- *Is any claim too strong / not something you'd defend? (especially §4.2's bias numbers and §4.1's audit reading)*
- *Anything missing that you remember trying and want credited or warned about?*
- *Numbers: Blind-B 0.2537/3.30/0.3811 rank 29/39; Blind-A 0.4380/4.20/0.5389; devset 0.1492→0.3844; b1_cos 59.0%; 53,885 pairs; 30k/121.6k turns; 62/26/11; 18,222/5,880; audit 31/79 ranking-gap. All verified against repo + official CSV.*
