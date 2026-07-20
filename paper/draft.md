# State-Driven Retrieval and Learned Re-Ranking for Conversational Music Recommendation

**Nidhin Pattaniyil, Semih Yagli, Tanwir Zaman** — Independent Researchers

*Draft v11 — author-comment pass (19 comments on the v10 PDF): claims softened throughout given the 29/39 finish; abstract no longer claims out-of-fold "tracked the blind outcome"; §4.1 condensed to the overfit-our-own-selection account; §4.2 states what the 57.4% actually measures and drops "real session" (the conversations are LLM-generated); §4.3 trimmed to one exact-track example; conclusion gains a fourth gap (no track/artist knowledge beyond catalog metadata); inline bolding removed. Prior v10: §4.3 restructured by pipeline stage (Retrieval and ranking vs. Response generation), verified from the Blind-B submission trace: constraint-not-enforced (Kamelot Silverthorn→Haven, album in catalog; "explore beyond"→10/20 same artist), absent-data constraints (126.70 bpm/key, Breaking Bad soundtrack — no such catalog fields), and exact-track-not-in-catalog response-gen failure (Watercolors/Fallen/Czar Refaeli). Prior v9: goal-free vs. goal-progress distinction, §4.2 rates re-based to 106,393, LLM judges named, abstract split. Mirrors paper/main.tex. Numbers re-verified against repo artifacts in v11; the unsourced 62/26/11 manual-sample figures were removed, and the template-sweep, in-sample-range, and Blind-B audit-N claims were corrected.*

---

## Abstract

We describe team npatta01's submission to the RecSys Challenge 2026 conversational music recommendation task. The pipeline extracts a typed conversation state with an LLM, gathers candidates from eleven retrieval branches over a unified track index, re-ranks them with a LambdaMART model, and generates a state-conditioned response. On the final Blind-B leaderboard it scored 0.3811 composite (nDCG@20 0.2537, LLM-judge 3.30), ranking 29th of 39 teams. We then examine why. Our development estimates were computed in-sample and overstated performance. The training conversations are LLM-generated, and on many turns we were unsure that the single ground-truth track matched the request — often it repeats the just-played artist after an explicit request for someone else. We re-judged the turns with LLM judges and release that relabeling; a model trained on it scored lower, so the submission kept the original labels. Failure cases from the submitted run show extracted constraints the pipeline could not enforce. Code, models, and a full reproduction bundle are publicly released.

## 1 Introduction

The Music-CRS challenge [1, 2] asks systems to act as a conversational music recommender. Each session is a multi-turn dialog between a listener and an assistant; at every assistant turn the system must (i) retrieve a ranked list of 20 tracks from a shared 47,071-track catalog and (ii) write a short natural-language response presenting its top recommendation. Training data comprises 15,199 sessions built on the TalkPlayData 2 collection [3], with per-track metadata (title, artist, album, up to 37 genre/mood tags, popularity, release date) and precomputed embeddings (text, audio, cover art, collaborative filtering). Evaluation is on two 80-session blind splits of final turns; Blind-B additionally removes the conversation-goal annotations present in training data. Submissions are scored with the organizers' composite metric:

Composite = 0.50 · nDCG@20 + 0.10 · catalog diversity + 0.10 · lexical diversity + 0.30 · (judge − 1)/4,

where "judge" is a 1–5 rating of the generated response from the organizers' LLM-based evaluator. In addition to the training sessions, a 1,000-session development split with public per-turn ground truth (one target track per turn) supports offline iteration.

Our system is a retrieve-then-rerank pipeline conditioned on an explicitly compiled conversation state. The deployed reranker is *goal-free*: it uses none of the conversation-goal annotations that Blind-B withholds. Section 2 documents the pipeline, Section 3 the results, and Section 4 the errors behind the final score.

Related work. The design combines four established lines rather than proposing a new method. Conversational recommenders commonly track dialog state explicitly and condition retrieval on it; we follow that pattern but compile the state with a prompted LLM instead of a trained tracker. Large-catalog systems retrieve then rerank, pooling multiple sources with reciprocal-rank fusion [4] and ranking with LambdaMART [5, 6]. Music retrieval adds modality-specific encoders — contrastive language-audio pretraining [8] and vision-language models over cover art [9] — alongside collaborative-filtering embeddings [10] and general-purpose text embeddings [7]. What we report is how that combination behaved, not a new technique.

## 2 Approach

[Figure 1 — full-width pipeline diagram, real in the PDF.] Conversation + played tracks → state extraction (deepseek-v4-flash) → resolver (names → catalog IDs) → eleven branches over one LanceDB collection (BM25 + tiered tag resolver; dense text ×3; CLAP text→audio; anchor centroids SigLIP-2/CLAP/CF; user-CF centroid; discography + era lookups) → pool union (≤500/branch) → LightGBM LambdaMART (146 features) → top-20 → response LLM. Dashed side path: weighted RRF + post-fusion as baseline & fallback.

### 2.1 State extraction

At each turn we prompt an LLM (deepseek-v4-flash [14]) with the dialog so far — the turns themselves and the IDs of the tracks already played — to emit a schema-constrained conversation state. Nothing else is fed in: none of the dataset's supplied annotations reach the extractor, so the state is whatever an LLM can read off the conversation. Its fields cover the current request and intent mode, track feedback and pinned references, mentioned entities, hard filters and explicit rejections, process constraints, routing flags, lyrical theme, and a release-year window; Figure 2 shows the schema populated on a real turn. A fuzzy resolver grounds surface names to catalog IDs so downstream stages operate on identifiers. Cheaper extractors under-filled optional fields such as rejections and facets, so all final runs use it.

[Figure 2 — worked example box, real in the PDF.] Blind-B turn: user hunts a specific song ("subdued, female singer, a sense of place in the lyrics, stark almost a cappella delivery… not it either"). Extracted state (abridged): request_type hidden_target; anchor artist Neko Case (must_use); rejected tracks "Calling Cards", "Man"; facets mood=subdued, lyrical_theme=sense of place, sonic=stark almost a cappella. Top-1: Neko Case — "Bracing For Sunday", with the submitted response quote.

### 2.2 Candidate retrieval

All per-track information lives in a single LanceDB collection [15]: metadata fields, a full-text index, and every embedding column — three Qwen3-Embedding text views (lyrics from the 0.6B model at 1024-d; metadata and attributes re-indexed with the 8B model), LAION-CLAP audio (512-d) [8], SigLIP-2 cover art (768-d) [9], BPR collaborative-filtering vectors (128-d) [10], and our bi-encoder document vectors (2560-d, Section 2.4). The goal was to express every filter in one space: each branch is a differently-shaped query against the same table, so retrieval could in principle collapse into a single composed query. We never got there (Section 4.3).

Table 1 lists the eleven branches that produce candidate pools each turn. In the BM25 branch [11], free-text mood and genre phrases first pass through a tiered tag resolver: exact, alias, and substring matching against the catalog tag vocabulary, with an embedding nearest-neighbor fallback (cosine >= 0.6, top-3). Weighted reciprocal-rank fusion [4] (k=60, top-1000) plus post-fusion multiplicative adjustments (rejected artists/tracks dropped, played tracks dropped, exact-membership tag promotes/demotes, year-range decay) yields an explicit ranking that serves as baseline and fallback.

Table 1 — the eleven retrieval branches (all queries against the one collection).

| Branch | Space | Query |
|---|---|---|
| BM25 (fielded) | lexical | state text + resolved tags |
| Dense text x3 | Qwen3 views | state-built strings |
| CLAP text-to-audio | audio | sonic description |
| Anchor centroids x3 (pivot-gated) | SigLIP-2/CLAP/CF | liked-track centroids |
| User-CF centroid | CF-BPR | the user's own vector |
| Lookups x2 | catalog | discography; era popularity |

### 2.3 Candidate re-ranking

The submitted system replaces the fused order: a LightGBM LambdaMART [5, 6] model scores the union of the branch pools (each truncated to its top 500) and emits the final top-20. It sees 146 features per (turn, track) pair: per-branch rank/score/margin/hit features, pool-normalized z-scores and percentiles, content and behavioral cosines, session/artist-affinity counters, tag and lexical overlap, popularity, extracted-state categoricals, and a constraint sidecar of played/rejected/violation flags. Table 2 groups them by family with each family's share of total split gain in the deployed model; one feature — the bi-encoder cosine b1_cos — carries 59.0% of all gain. After scoring, two rule-based guards apply: an exact-track pin when the user names a specific track, and a final-artist constraint check.

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

The deployed model is *goal-free*: no conversation-goal annotation enters it as a feature, since Blind-B removes them. Its training data is the development split only — the same 8,000 turns used for offline evaluation (~20.6M candidate rows). Per-turn state extraction runs through a paid LLM API, so we never built features over the ~121.6k-turn training split; Section 4.1 discusses what that reuse cost us. Training treats the per-turn ground-truth track as a binary label under a LambdaRank objective (learning rate 0.025, 127 leaves, truncation 200, 5-fold user-grouped cross-validation). Because the labels are noisy (Section 4.2), we down-weight a turn when the *next* turn contradicts it: ×0.3 when the user rejects the labelled track or the goal-progress annotation says it did not help, ×0.6 when they reject only its artist. That annotation shapes training labels — these weights and the bi-encoder positives of Section 2.4 — but is never itself a feature.

### 2.4 The bi-encoder feature b1_cos

[Figure 3 — two-tower diagram, real in the PDF.] Conversation rendering ([prev] user turn t−1 / [now] user turn t / [prev_track] artist — title) and track card (artist — title (year) | tags ≤5 | known for: LLM line) → shared fine-tuned Qwen3-Embedding-4B encoder (last-token pool, L2-norm) → 2560-d unit vectors → cosine → b1_cos reranker feature.

The reranker's dominant feature comes from a two-tower bi-encoder fine-tuned from Qwen3-Embedding-4B [7] (Figure 3). The query tower renders the conversation compactly behind a retrieval instruction prefix and the document tower renders a track card (both formats in Figure 3), whose one-line LLM-written "known for" artist description imports static world knowledge from larger models into the embedding space. One shared encoder E_θ serves both towers; with v_x = E_θ(x)/‖E_θ(x)‖₂ (last-token pooling, 2560-d), the feature is the cosine b1_cos(q,d) = v_qᵀv_d. Training minimizes the in-batch contrastive (MNRL [13]) loss with temperature τ = 1/20 over batches of positive pairs, each with four mined hard negatives (the softmax denominator ranges over in-batch documents plus the hard negatives). Positives are conservative: the 53,885 (turn, track) pairs whose next-turn goal-progress annotation says the recommendation *moved the session forward*. Document vectors for all 47,071 tracks are precomputed into the collection; the conversation vector is encoded live with caching.

We deploy the bi-encoder as a reranker feature only. In an earlier experiment we tried it as a twelfth retrieval branch, where it added little to the union's coverage and was dropped. As a feature its cosine dominates the fitted model — 59.0% of split gain (Table 2) — but that is a diagnostic of the fit, not a measure of recommendation quality; its incremental effect is much smaller, moving leakage-safe out-of-fold nDCG@20 from 0.1970 to 0.2032 (Table 3). We did not isolate which parts of the rendering mattered, or test whether the effect carries to the blind splits.

### 2.5 Response generation

The response generator is Qwen3-30B-A3B-Instruct-2507 [12] at temperature 0: a single pass over the top-1 track rendered as a delimited XML block (≤10 tags) plus the *latest* extracted state. The deployed template's full style instruction is:

> *"Write 1–2 concise sentences about only the selected track. Prioritize the latest user request and extracted state over older conversation history. If the track is reasonably aligned, explain the fit with one specific supported reason. If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it or blame the system; briefly frame the limitation and the closest supported reason."*

Over a frozen Blind-A retrieval output, a sweep of eight response variants (varying state conditioning, history depth, item rendering, and concision) moved the Blind-A judge score from 4.20 to 4.70 without changing the recommendations; a further variant that also swapped the generator model scored 3.95. Our own offline judge did not rank these variants reliably, so we selected on the leaderboard score instead. There is no multi-draft sampling, selection, checking, or repair pass.

Code, configs, trained models, cached extraction states, and a frozen-LLM-cache reproduction bundle that replays our submissions without API credentials are public: https://github.com/npatta01/music-crs-2026 (models and data: https://huggingface.co/datasets/Npatta01/music-crs-repro-2026).

## 3 Results

The development split (1,000 sessions × 8 turns) has one ground-truth track per turn. Table 3 reports development-split numbers, separating leakage-safe estimates from in-sample ones; Table 4 reports the official leaderboard results.

Table 3 — development split. The in-sample row replays turns the deployed (full-data) model saw during training; the out-of-fold rows are leakage-safe cross-validation estimates.

| System (how measured) | nDCG@20 |
|---|---|
| Weighted RRF fusion (no training) | 0.1492 |
| LambdaMART, out-of-fold CV | 0.1970 |
| + b1_cos (deployed feature set) | 0.2032 |
| LambdaMART, evaluated in-sample (train replay) | 0.3844 |

Footnote: official Blind-B nDCG@20: 0.2537 — above the out-of-fold estimates and far below the in-sample replay.

Table 4 — official CodaBench results (composite = 0.50·nDCG@20 + 0.10·catalog div. + 0.10·lexical div. + 0.30·(judge−1)/4). The Blind-A rank counts all development-phase submissions.

| Split | nDCG@20 | Catalog div. | Lexical div. | Judge | Composite | Rank |
|---|---|---|---|---|---|---|
| Blind-A (dev phase) | 0.4380 | 0.0313 | 0.7670 | 4.20 | 0.5389 | 63/181 |
| Blind-B (final) | 0.2537 | 0.0315 | 0.7862 | 3.30 | 0.3811 | 29/39 |

Learned re-ranking improves over static fusion by the leakage-safe estimate (0.149 → 0.197–0.203); Section 4.1 discusses the in-sample row.

## 4 Error Analysis

### 4.1 In-sample development evaluation

We never built features over the training split, so the development split served as both training and evaluation data and we had no clean held-out set. The numbers we selected on (0.38–0.46) were replays of turns the model had trained on; our out-of-fold estimates were much lower (0.197–0.203). The blind score (0.2537) came out between the two — above the out-of-fold estimates, well below the in-sample replays. We overfit our own selection process.

### 4.2 Label disagreement and relabeling

Our own model shows anchoring behaviour, and we think it learns it from the labels. The per-turn ground truth is simply the track played next in the session, which is itself LLM-generated, and on many turns it does not fit the request: the label stays with the just-played artist even against an explicit request for someone else (Figure 4).

[Figure 4 — conversation box, real in the PDF.] User: "…something with a similar chill, electronic vibe, but **from a different artist**?" (just played: Bonobo) → ground truth: Bonobo — "Jets" [annotation: MOVES toward goal]. Next turn: "'Jets' is cool, but I was actually hoping for something **from a different artist this time**…" → ground truth: Bonobo — "Pieces" [annotation: MOVES toward goal].

We tried to train on cleaner labels instead. Two inexpensive LLM judges (Gemma-4-26B and DeepSeek-V4-Flash) re-judged every labelable training and development turn (113,393) on two axes — whether the user asked for a different artist, and whether the track fits the request. They disagreed on about 20% of the 106,393 training turns, which Claude Opus arbitrated. Across the same turns they did not settle on the played track being a good fit for 57%, and 17% (18,222) are anchoring cases. A model trained on the relabeled data scored lower in our own evaluation, so the final submission kept the original labels. Our judges may be wrong too; we release the relabeling so others can check it.

### 4.3 Failure cases

We wanted to understand where the system failed, so we had a single LLM judge (DeepSeek-V4-Flash) rate the submitted Blind-B run: 68% of turns came back weak-or-bad. The table below diagnoses a subset of them. These are examples and audit categories, not measures of what each cost us — Blind-B exposes no relevance labels, so only the validation failure of Section 4.1 is actually measured.

| Diagnosis | Turns |
|---|---|
| Better candidate in pool, ordered below top-20 | 31 |
| Over-aggressive filtering | 8 |
| State-extraction miss | 3 |
| Entity-resolution miss | 1 |

- **The constraint was under-applied.** Asked for "the Kamelot track from *Silverthorn*," the system matched the artist but not the album, returning *Fallen Star* from Kamelot's *Haven* (*Silverthorn* is in the catalog); asked to "explore beyond" the current artist, it stayed on them (10 of the top 20 in one Ryan Adams session).
- **Nothing in our data encodes the request.** An exact "126.70 bpm and G minor" (no tempo or key field), or "a song from the *Breaking Bad* soundtrack" (no film/TV metadata), which no branch can match on.
- **Response generation.** The single-pass generator did not properly consider the query — in particular an exact-track request for a title we do not have. On several turns a named track was read correctly as an exact-track request but is absent from the 47,071-track catalog; rather than flag it unavailable, the generator described a different song by the same artist as if it were the one asked for — for "'Watercolors' by Pat Metheny," it returned Metheny's "Alfie."

The limitation we keep returning to is that too little of the user's intent became executable constraints. The state records what the user wants, but few fields became filters or ranked evidence — each branch consumed a slice of the state, and tag matching fell back to exact strings outside the BM25 branch — while no co-occurrence, transition, or live-reasoning lane existed to compensate. Noisy candidate pools therefore reached the reranker; in the audit, 31 turns had a candidate the judge preferred sitting in the pool below our top-20 — the largest bucket in the audit table.

Our analysis has its own limits. The relabeling was never checked against human judgments, the Blind-B audit used a single LLM judge, the conversations are LLM-generated rather than observed listening sessions, and neither blind split exposes relevance labels — so every rate we report comes from our own judges rather than from ground truth.

## 5 Conclusion

We documented a state-compiled retrieve-then-rerank conversational music recommender and finished 29th of 39. Four gaps stand out among the failures we could diagnose:

1. model selection relied on in-sample development replays, and we had no clean held-out set to check them against;
2. the extracted conversation state was rich, but too little of it became executable filters or ranking evidence, so noisy candidate pools reached the reranker;
3. for retrieval and ranking we had little information about tracks and artists beyond the provided catalog metadata — no external source, and no LLM-generated knowledge beyond the one-line artist description — so requests naming anything the catalog does not encode had nothing to match against;
4. responses were generated in a single unchecked pass that could flag neither unavailable tracks nor unmet constraints.

Separately, we were unsure about many of the training labels, and re-judged the 113,393 labelable turns with LLM judges (Section 4.2). We release the pipeline, the models, a replay bundle, and the re-judged labels [16].

---

## References

1. Music-CRS Challenge 2026 (RecSys Challenge). NLP4MusA organizers. https://nlp4musa.github.io/music-crs-challenge/
2. RecSys Challenge organizers. 2026. RecSys Challenge 2026. https://www.recsyschallenge.com/2026/
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
13. Reimers, N., Gurevych, I. Sentence-BERT: sentence embeddings using Siamese BERT-networks. EMNLP 2019.
14. DeepSeek. DeepSeek-V4-Flash model card (OpenRouter). 2026.
15. LanceDB: serverless vector database. https://lancedb.com (software).
16. Team npatta01. 2026. music-crs-2026: code, models, and reproduction bundle. https://github.com/npatta01/music-crs-2026

---

Reviewer checklist for co-authors:

- The retrospective now leads with the in-sample-evaluation admission (4.1). Comfortable with that framing? It is labeled a measurement/confidence failure, not the proven cause.
- Failure cases in 4.3 are sessions from the submitted Blind-B run (verified against the trace). Flag any you'd rather not print.
- No team comparisons anywhere, per our decision; the retrospective webpage stays separate from the paper.
- Numbers: Blind-B 0.2537 / 3.30 / 0.3811 rank 29/39; Blind-A 0.4380 / 4.20 / 0.5389; RRF 0.1492; OOF 0.1970 → 0.2032; in-sample 0.3844 (0.4562 older, same config); b1_cos 59.0% (recomputed from model.txt: 59.03%); 146 features (meta.json `n_feature_cols: 142` is pre-sidecar-join; model.txt has 146 — aside cut from paper as confusing); 53,885 pairs; trained on the 8,000 dev turns only (~20.6M rows; the ~121.6k-turn train split was never featurized); judges: 106,393 train turns, ~20% arbitrated, 57% not-a-good-fit, 17% (18,222) anchoring; audit 68% weak-or-bad over 79 judged (N dropped from paper per author), 31 better-candidate-in-pool.
- Cut in v11: the 62/26/11 manual-sample figures (no artifact, no N anywhere in repo) and the 5,880 poisoned-positives clause (dangling once the "poisoned positives" framing was softened out). Both recoverable from git history if a source turns up.
