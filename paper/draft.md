# State-Driven Retrieval and Learned Re-Ranking for Conversational Music Recommendation

**Nidhin Pattaniyil, Semih Yagli, Tanwir Zaman** — Independent Researchers

*Draft v7 — verbosity pass + second PDF round applied. Mirrors paper/main.tex: whole paper now fits in 4 pages. All numbers verified.*

---

## Abstract

We describe team npatta01's submission to the RecSys Challenge 2026 conversational music recommendation task: given a multi-turn dialog, retrieve 20 tracks from a 47,071-track catalog and generate a natural-language response. The pipeline extracts a typed conversation state with an LLM, gathers candidates from eleven retrieval branches over a unified track index, re-ranks the pooled candidates with a LambdaMART model whose dominant feature is a fine-tuned conversational bi-encoder cosine, and generates a state-conditioned response. On the final Blind-B leaderboard the submission scored 0.3811 composite (nDCG@20 0.2537, LLM-judge 3.30), ranking 29th of 39 teams. We describe the system, then examine the result: the in-sample development estimates that guided our choices overstated performance, while leakage-safe out-of-fold estimates (nDCG@20 0.197–0.203) anticipated the blind outcome; the benchmark's single-ground-truth labels carry a quantified *anchoring bias* that rewards copying the just-played artist; and failure cases from the submitted run show extracted constraints the pipeline could not enforce. Code, models, and a full reproduction bundle are publicly released.

## 1 Introduction

The Music-CRS challenge [1, 2] asks systems to act as a conversational music recommender. Each session is a multi-turn dialog between a listener and an assistant; at every assistant turn the system must (i) retrieve a ranked list of 20 tracks from a shared 47,071-track catalog and (ii) write a short natural-language response presenting its top recommendation. Training data comprises 15,199 sessions built on the TalkPlayData 2 collection [3], with per-track metadata (title, artist, album, up to 37 genre/mood tags, popularity, release date) and precomputed embeddings (text, audio, cover art, collaborative filtering). Evaluation is on two 80-session blind splits of final turns; Blind-B additionally removes the conversation-goal annotations present in training data. Submissions are scored with the organizers' composite metric:

Composite = 0.50 · nDCG@20 + 0.10 · catalog diversity + 0.10 · lexical diversity + 0.30 · (judge − 1)/4,

where "judge" is a 1–5 rating of the generated response from the organizers' LLM-based evaluator. In addition to the training sessions, a 1,000-session development split with public per-turn ground truth (one target track per turn) supports offline iteration.

Our system is a retrieve-then-rerank pipeline conditioned on an explicitly compiled conversation state. This paper documents the pipeline (Section 2) and its results (Section 3), then analyzes the errors behind the final score (Section 4): an evaluation mistake in which in-sample development replays overstated performance while leakage-safe out-of-fold estimates anticipated the Blind-B result; a fine-tuned conversational bi-encoder whose single cosine feature carries 59% of the reranker's decision weight and displaces a label-noise-induced artist-copy shortcut; and a quantified anchoring bias in the ground-truth labels, illustrated with failure cases from the submitted run. Code, models, and a cleaned, LLM-re-judged label set are released at https://github.com/npatta01/music-crs-2026.

Related work in brief: the design follows the retrieve-then-rerank pattern standard in large-catalog recommendation, with reciprocal-rank fusion [4] for multi-source pooling, LambdaMART [5, 6] for learned ranking, and LLM-based dialog state tracking.

## 2 Approach

[Figure 1 — full-width pipeline diagram, real in the PDF.] Conversation + user profile → state extraction (deepseek-v4-flash → typed JSON) → resolver (names → catalog IDs) → eleven branches over one LanceDB collection (BM25 + tiered tag resolver; dense text ×3; CLAP text→audio; anchor centroids SigLIP-2/CLAP/CF; user-CF centroid; discography + era lookups) → pool union (≤500/branch) → LightGBM LambdaMART (146 features) → top-20 → response LLM. Dashed side path: weighted RRF + post-fusion as baseline & fallback.

### 2.1 State extraction

At each turn we prompt deepseek-v4-flash with the full conversation so far (all prior turns plus the user profile) to emit a schema-constrained conversation state. Its eleven fields cover the current request and intent mode, track feedback and pinned references, mentioned entities, hard filters and explicit rejections, process constraints, routing flags, lyrical theme, and a release-year window; Figure 2 shows the schema populated on a real turn. A fuzzy resolver grounds surface names to catalog IDs so downstream stages operate on identifiers. Cheaper extractors under-filled optional fields (rejections, facets), so all final runs use deepseek-v4-flash; extraction is cached per turn.

[Figure 2 — worked example box, real in the PDF.] Real Blind-B turn (session 024a2738…): user hunts a specific song ("subdued, female singer, a sense of place in the lyrics, stark almost a cappella delivery… not it either"). Extracted state (abridged): request_type hidden_target; anchor artist Neko Case (must_use); rejected tracks "Calling Cards", "Man"; facets mood=subdued, lyrical_theme=sense of place, sonic=stark almost a cappella. Top-1: Neko Case — "Bracing For Sunday", with the submitted response quote.

### 2.2 Candidate retrieval

All per-track information lives in a **single LanceDB collection**: metadata fields, a full-text index, and every embedding column — three Qwen3-Embedding text views (metadata, attributes, lyrics; 1024-d), LAION-CLAP audio (512-d) [8], SigLIP-2 cover art (768-d) [9], BPR collaborative-filtering vectors (128-d) [10], and our bi-encoder document vectors (2560-d, Section 2.4). Every retrieval branch is a differently-shaped query against the same table — in principle the whole retrieval step could be one composed query clause (Section 4.3).

Table 1 lists the eleven branches that produce candidate pools each turn. In the BM25 branch [11], free-text mood and genre phrases first pass through a **tiered tag resolver**: exact, alias, and substring matching against the catalog tag vocabulary, with an embedding nearest-neighbor fallback (cosine >= 0.6, top-3). Weighted reciprocal-rank fusion [4] (k=60, top-1000) plus post-fusion multiplicative adjustments (rejected artists/tracks dropped, played tracks dropped, exact-membership tag promotes/demotes, year-range decay) yields an explicit ranking that serves as **baseline and fallback**.

Table 1 — the eleven retrieval branches (all queries against the one collection).

| Branch | Space | Query |
|---|---|---|
| BM25 (fielded) | lexical | state text + resolved tags |
| Dense text x3 | Qwen3 views | state-built strings |
| CLAP text-to-audio | audio | sonic description |
| Anchor centroids x3 (pivot-gated) | SigLIP-2/CLAP/CF | liked-track centroids |
| User-CF centroid | CF-BPR | the user's own vector |
| Lookups x2 | catalog | discography; era popularity |

### 2.3 Learned re-ranking

The submitted system replaces the fused order: a LightGBM LambdaMART [5, 6] model scores the **union of the branch pools** (each truncated to its top 500) and emits the final top-20. It sees 146 features per (turn, track) pair: per-branch rank/score/margin/hit features, pool-normalized z-scores and percentiles, content and behavioral cosines, session/artist-affinity counters, tag and lexical overlap, popularity, extracted-state categoricals, and a constraint sidecar. Table 2 groups them by family with each family's share of total split gain in the deployed model; one feature — the bi-encoder cosine b1_cos — carries 59.0% of all gain. The RRF rank itself is *excluded*: the ranker sees raw branch evidence, not the fused opinion. After scoring, two rule-based guards apply: an exact-track pin when the user names a specific track, and a final-artist constraint check (enabled for the Blind-B run).

Table 2 — reranker feature families (share of total gain, deployed model).

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

### 2.4 The bi-encoder feature b1_cos

[Figure 3 — two-tower diagram, real in the PDF.] Conversation rendering ([prev] user turn t−1 / [now] user turn t / [prev_track] artist — title) and track card (artist — title (year) | tags ≤5 | known for: LLM line) → shared fine-tuned Qwen3-Embedding-4B encoder (last-token pool, L2-norm) → 2560-d unit vectors → cosine → b1_cos reranker feature.

The reranker's dominant feature comes from a two-tower bi-encoder fine-tuned from Qwen3-Embedding-4B [7] (Figure 3). The query tower renders the conversation compactly behind a retrieval instruction prefix and the document tower renders a track card (both formats in Figure 3), whose one-line LLM-written "known for" artist description imports static world knowledge from larger models into the embedding space. One shared encoder E_θ serves both towers; with v_x = E_θ(x)/‖E_θ(x)‖₂ (last-token pooling, 2560-d), the feature is the cosine b1_cos(q,d) = v_qᵀv_d. Training minimizes the in-batch contrastive (MNRL [15]) loss with temperature τ = 1/20 over batches of positive pairs, each with four mined hard negatives (the softmax denominator ranges over in-batch documents plus the hard negatives). Positives are conservative: the 53,885 (turn, track) pairs whose next-turn goal-progress annotation says the recommendation *moved the session forward*. Document vectors for all 47,071 tracks are precomputed into the collection; the conversation vector is encoded live with caching.

We deploy the bi-encoder as a reranker feature only: as a retrieval branch it added little coverage, but its cosine became the top signal (Table 2) — and a *generalizing replacement* for a shortcut learned from biased labels (Section 4.2): in leakage-safe out-of-fold ablations, removing the artist-consensus shortcut features reduces nDCG@20 by 0.0070, while adding b1_cos more than recovers the loss (+0.0091) with the shortcut absent.

### 2.5 Response generation

The response generator is Qwen3-30B-A3B-Instruct-2507 [12] at temperature 0: a single pass over the top-1 track rendered as a delimited XML block (≤10 tags; the delimiting stops the model from echoing raw metadata) plus the *latest* extracted state. The deployed template's full style instruction is:

> *"Write 1–2 concise sentences about only the selected track. Prioritize the latest user request and extracted state over older conversation history. If the track is reasonably aligned, explain the fit with one specific supported reason. If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it or blame the system; briefly frame the limitation and the closest supported reason."*

Over a frozen Blind-A retrieval output, a sweep of eight templates (varying state conditioning, history depth, item rendering, and concision) moved the judge score from 3.95 to 4.70 without changing the recommendations. There is no multi-draft sampling, selection, checking, or repair pass.

Code, configs, trained models, cached extraction states, and a frozen-LLM-cache reproduction bundle that replays our submissions without API credentials are public: https://github.com/npatta01/music-crs-2026 (models and data: https://huggingface.co/datasets/Npatta01/music-crs-repro-2026).

## 3 Results

The development split (1,000 sessions × 8 turns) has one ground-truth track per turn, so Recall@k equals Hit@k. Table 3 reports development-split numbers *with their evaluation lineage made explicit*; Table 4 reports the official leaderboard results.

Table 3 — development split, with evaluation lineage. The in-sample row replays turns the deployed (full-data) model saw during training; the out-of-fold rows are leakage-safe cross-validation estimates.

| System (evaluation lineage) | nDCG@20 |
|---|---|
| Weighted RRF fusion (no training) | 0.1492 |
| LambdaMART, out-of-fold CV | 0.1970 |
| + b1_cos (deployed feature set) | 0.2032 |
| LambdaMART, evaluated in-sample (train replay) | 0.3844 |

Footnote: official Blind-B nDCG@20: 0.2537 — between the out-of-fold estimates and far below the in-sample replay.

Table 4 — official CodaBench results (composite = 0.50·nDCG@20 + 0.10·catalog div. + 0.10·lexical div. + 0.30·(judge−1)/4). The Blind-A rank counts all development-phase submissions.

| Split | nDCG@20 | Catalog div. | Lexical div. | Judge | Composite | Rank |
|---|---|---|---|---|---|---|
| Blind-A (dev phase) | 0.4380 | 0.0313 | 0.7670 | 4.20 | 0.5389 | 63/181 |
| Blind-B (final) | 0.2537 | 0.0315 | 0.7862 | 3.30 | 0.3811 | 29/39 |

Learned re-ranking beats static fusion by the leakage-safe estimate (0.149 -> 0.197-0.203); the in-sample replay (0.384) overstated it, and the blind result (0.2537) tracked the out-of-fold evidence available before submission.

## 4 Error Analysis

### 4.1 In-sample development evaluation

Per-turn state extraction and retrieval tracing made held-out evaluation sets expensive, so the development split served both training and evaluation. The deployed reranker was fit on all of its feature data (cross-validation informed early stopping; a full-data model shipped), making the headline 0.38–0.46 development estimates in-sample — and those numbers drove selection. The leakage-safe out-of-fold estimates (0.197–0.203) predicted the blind outcome (0.2537) far better; the in-sample replay (0.384) had overstated it. We regard this as a measurement error rather than a demonstrated cause of the final ranking. The lesson: base model selection on out-of-fold estimates.

### 4.2 Ground-truth label noise

We found this while building higher-quality training data: for many turns, the labeled target contradicts the user's request. The benchmark's per-turn ground truth is a *sibling pick* from the listener's real session — the track actually played next — not an editorial judgment of the request. In a manual sample only 62% of ground-truth tracks were a clear fit to the request, 26% a loose fit, and 11% no fit. The dominant pattern is what we call **anchoring**: the ground truth stays with the just-played artist even against an explicit request for someone else (Figure 4).

[Figure 4 — conversation box, real in the PDF.] User: "…something with a similar chill, electronic vibe, but **from a different artist**?" (just played: Bonobo) → ground truth: Bonobo — "Jets" [annotation: MOVES toward goal]. Next turn: "'Jets' is cool, but I was actually hoping for something **from a different artist this time**…" → ground truth: Bonobo — "Pieces" [annotation: MOVES toward goal].

To quantify the bias, two inexpensive LLM judges scored every training and development turn (113,393 in total) on two axes — whether the user asked for a different artist, and whether the track fits the request — and a stronger arbiter re-judged every conflict without access to the synthetic reaction annotation.

Overall, 57.4% of turns were judged negative. 18,222 are anchoring negatives, and 5,880 of those additionally claim the listener liked the track — poisoned positives for any goal-progress-based training scheme, including our bi-encoder's. A second contradiction pattern, in which the user rejects the ground-truth track on the next turn, motivated the ×0.3 label down-weighting of Section 2.3. These labels systematically reward copying the last artist, and our ablations show the ranker exploiting exactly that shortcut before the bi-encoder cosine displaced it (Section 2.4). Because every team is scored against the same labels, the bias affects all measured scores; it is also possible that our judges, rather than the labels, are misaligned, so we release the full relabeling for independent audit. The submitted models were *not* trained on it.

### 4.3 Failure cases

A separate label-free audit — a single LLM judge over the 80 submitted Blind-B turns, unlike the two-judge pipeline of Section 4.2 — rated 68% of them weak-or-bad fits; the table below breaks the flagged turns down by pipeline stage (hidden-label frequencies remain unknown). Concrete cases from the submitted predictions, each with the systemic gap it exposes:

| Diagnosis | Turns |
|---|---|
| Better candidate in pool, ordered below top-20 | 31 |
| Over-aggressive filtering | 8 |
| State-extraction miss | 3 |
| Entity-resolution miss | 1 |

- **Anchoring at serving time.** "Another alt-country song… but **from a different artist than Ryan Adams**" → our top-1 was *Ryan Adams & The Cardinals*, plus five more of their tracks in the top-20: the rejection resolved to the solo "Ryan Adams" ID, and the band-variant ID passed the hard-drop. A second session leaked the same way — four Cradle Of Filth tracks despite "not Cradle of Filth" (a duplicate artist ID), under an unenforceable "female operatic vocals" ask. **Gap:** rejections are enforced by exact catalog ID, but artist identity is fragmented across band variants and duplicates; a name-level veto would have caught both. This is the serving-time face of the Section 4.2 bias.
- **Impossible exact request.** "Play 'Watercolors' by Pat Metheny" — the track does not exist in the 47k catalog; we returned Pat Metheny's "Alfie" without saying so. **Gap:** no world knowledge or external data to recognize an out-of-catalog request, and the single-pass response cannot flag unavailability — costly, since the response term carries 30% of the composite (our judge score: 3.30).
- **Unactionable constraint.** "Any aggressive metal track that **exactly matches 126.70 bpm and G minor**, with tempo and key stated" — the catalog has no BPM or key fields. **Gap:** the constraint was captured in state, but the catalog has no field to map it onto.

The unifying gap: **we did not model enough of the user's ask as executable constraints**. The state records what the user wants, but few fields became filters or ranked evidence — each branch consumed a slice of the state, and tag matching fell back to exact strings beyond the BM25 clause — while no co-occurrence, transition, or live-reasoning lane existed to compensate. Noisy candidate pools therefore reached the reranker, and a ranker trained on a quarter of the available turns could not reliably pull the right track back up.

## 5 Conclusion

We documented a state-compiled retrieve-then-rerank conversational music recommender in full and audited our mid-pack result: an in-sample development estimate inflated confidence that leakage-safe evidence had already contradicted; the ground truth carries a quantified anchoring bias our own submission reproduced at serving time; and several extracted constraints had nothing in the catalog to act on. We release the pipeline, models, a zero-credential replay bundle, and a cleaned relabeling for future iterations.

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
15. Reimers, N., Gurevych, I. Sentence-BERT: sentence embeddings using Siamese BERT-networks. EMNLP 2019.

---

Reviewer checklist for co-authors:

- The retrospective now leads with the in-sample-evaluation admission (4.1). Comfortable with that framing? It is labeled a measurement/confidence failure, not the proven cause.
- Failure cases in 4.3 are real sessions from the submitted Blind-B run (verified against the trace). Flag any you'd rather not print.
- No team comparisons anywhere, per our decision; the retrospective webpage stays separate from the paper.
- Numbers: Blind-B 0.2537 / 3.30 / 0.3811 rank 29/39; Blind-A 0.4380 / 4.20 / 0.5389; RRF 0.1492; OOF 0.1970 → 0.2032; in-sample 0.3844 (0.4562 older); b1_cos 59.0%; 53,885 pairs; 30k of ~121.6k turns; 62/26/11; 18,222 / 5,880; audit 68% weak-or-bad, 31/79 better-candidate-in-pool.
