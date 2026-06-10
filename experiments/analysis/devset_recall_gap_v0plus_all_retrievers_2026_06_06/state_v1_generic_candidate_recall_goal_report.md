# State V1 Generic Candidate Recall Goal

Date: 2026-06-10

Scope: focused-110 only. State extraction and schema were frozen. Changes were limited to compiler/matrix consumption of existing projected state plus catalog-derived candidate features.

## Headline

The state can help candidate recall, but the remaining gap is not solved by state extraction alone.

## Stop Point: Survivor Selector Prototype

After the user-id-aware matrix, the next tested hypothesis was a branch-local
survivor selector: add one opt-in branch that only reconsiders candidates that
already appeared below the top-20 window in existing branches. This is meant to
test the 21-100 near-miss gap without changing the LLM prompt, schema, global
RRF, or final ranker.

Implemented, disabled by default:

- `enable_state_feature_survivor_branch`
- rank window knobs: `state_feature_survivor_min_rank=21`,
  `state_feature_survivor_max_rank=120`
- score knobs: state-feature score, mid-rank prior, and multi-branch support
- matrix variants:
  - `current_config_state_survivor`
  - `all_candidate_plus_targeted_v4_state_survivor`
  - `all_candidate_plus_targeted_v4_state_selector_family_survivor`

Evidence so far:

- Unit tests passed for compiler behavior and matrix config wiring:
  `5 passed`.
- A real one-sample smoke emitted the `state_feature_survivor` branch through
  the matrix harness and wrote:
  `state_v1_survivor_smoke1_branch_pools.json`.
- Offline saved-pool probe on `state_v1_all_on_branch_pools.json` showed the
  survivor idea can rescue up to +5 `union@20` on that older all-on pool:
  base `64/110` -> `69/110`, with rescues in novelty, temporal, same-album,
  positive-tag, and one clean control slice.

Important caveat:

- The live focused-110 Modal validation was intentionally stopped because it
  was too slow for the current session. It reached only 3/110 samples before
  cancellation. Therefore the survivor selector is implemented and smoke-tested,
  but not yet promoted. Treat it as a candidate for the next Modal validation,
  not a proven improvement over the corrected user-id-aware matrix.

Decision:

- Keep the code as an opt-in diagnostic branch.
- Do not claim the focused-110 headline has improved beyond the last completed
  corrected run: best completed `union@20` remains `76/110`, `union@50`
  `92/110`, `union@100` `96/110`.
- Next validation should run only:
  `all_candidate_plus_targeted_v4_state_survivor` and
  `all_candidate_plus_targeted_v4_state_selector_family_survivor`, preferably
  on Modal with cached embeddings warmed or sharded.

## Stop Point: User-ID-Aware Focused Matrix

After reviewer feedback, the focused matrix harness was corrected to pass `user_id`
from the focused-110 sidecar into the compiler. This matters because the
production compiler has an existing `centroid.user.cf_bpr` branch. The prior
matrix could forward `user_id` if present, but the main loop only passed the
audit row into `_compile_variant`, so the sidecar user id never reached the
compiler.

Corrected Modal artifact:

- `modal_downloads/state_v1_userid_matrix_all110.json`
- `modal_downloads/state_v1_userid_matrix_all110.md`
- `modal_downloads/state_v1_userid_matrix_all110.csv`

Corrected all-110 result:

| Variant | all u@20 | all u@50 | all u@100 | final@20 | NDCG@20 | read |
|---|---:|---:|---:|---:|---:|---|
| `current_config` | 60/110 | 69/110 | 78/110 | 32/110 | 0.1740 | production-like current config with user ids |
| `current_config_state_selector_family` | 65/110 | 80/110 | 87/110 | 34/110 | 0.1625 | state selector adds candidates, hurts NDCG |
| `all_candidate_plus_targeted_v4` | 72/110 | 86/110 | 93/110 | 34/110 | 0.2026 | stronger targeted candidate baseline |
| `all_candidate_plus_targeted_v4_state_selector_family` | 76/110 | 92/110 | 96/110 | 32/110 | 0.1822 | best candidate recall, worse final ranking |

Delta from targeted v4:

- Candidate recall improves: `union@20` +4, `union@50` +6, `union@100` +3.
- The four `union@20` rescues are 2 positive-tag failures, 1 novelty/prior-anchor failure, and 1 clean positive control.
- No `union@20` examples are lost relative to targeted v4.
- Final ranking regresses: `final@20` 34 -> 32 and NDCG@20 0.2026 -> 0.1822.

Read:

- The user-id fix is real harness correctness: smoke branch pools now include
  both `centroid.user.cf_bpr` and `state_feature_selector.centroid.user`.
- It does not change the headline conclusion. The best corrected candidate
  result is still 76/110, matching the earlier targeted-family count.
- The gap is no longer mostly "state not extracted" or "retrievers not firing."
  The corrected matrix has deep coverage: best targeted-family `union@100` is
  96/110 and `union@1000` is 108/110.
- The remaining hard problem is candidate ordering/fusion: many targets are in
  the branch pool but not top 20, and the candidate-recall feature packaging
  hurts final ranking.

### User-CF Attribution Audit (2026-06-10, Claude)

Per-sample comparison of the corrected `state_v1_userid_matrix_all110` run
against the pre-fix artifacts changes how the corrected numbers should be read:

- **The rerun is bit-identical for the three variants with pre-fix per-sample
  artifacts.** `current_config_state_selector_family`, `all_candidate_plus_targeted_v4`,
  and `all_candidate_plus_targeted_v4_state_selector_family` show zero
  `union@20` flips in either direction. The harness is deterministic.
- **The v4 variants never had a user-CF branch.** For non-`use_base_config`
  variants, `_variant_qu_kwargs` builds `centroid_only_branches` without a
  `centroid_source` key (`scripts/state_v1_retriever_matrix.py`, the
  `comp["centroid_only_branches"]` block), so they fall back to the compiler
  default `anchor_tracks`. Only `use_base_config` variants inherit the
  production `centroid_source: "user"` branch. "User-CF does not help on top
  of targeted v4" is therefore **not established by this run** — the branch was
  structurally absent there.
- **Adding it would still not move v4 union@20.** `current_config` (which does
  have the user branch) covers 0 of `all_candidate_plus_targeted_v4_state_selector_family`'s
  34 union@20 misses at @20, so a user branch added to v4 cannot rescue any of
  them at top-20.
- **The `current_config` 55→60 lift is mostly not user-CF.** Of the 5 upward
  flips versus the stale `state_v1_matrix_modal_all110_current_config.json`,
  only `c863175a` (GT at rank 1 in `centroid.user.cf_bpr`, same-album pack) is
  a user-CF rescue. The other 4 are pool-set drift: the old artifact ran with
  13–16 branch pools per turn versus 16–17 now (e.g. qwen-8B
  attributes_enriched and anchor image centroid were missing from the old
  current_config run). Do not credit user-CF with +5.
- **User-CF is a depth signal live.** It is the best branch in 7
  `current_config` turns, 6 of them with GT at rank 101–113 — below the @20
  and @100 cutoffs. This matches the prior expectation that user CF helps
  deeper recall, not top-20.

Decision: keep the user-id harness fix as a correctness fix; **reject user-CF
as a focused-110 `union@20` lever** (correctly tested, insufficient). Its depth
contribution (~rank 100) is only relevant to consumers of `union@200/1000`
pools, i.e. later ranking work.

Live compiler result:

| Variant | all u@20 | all u@50 | all u@100 | valid u@20 | valid u@50 | valid u@100 | final@20 | NDCG@20 | controls u@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `current_config` | 55/110 | 63/110 | 73/110 | 50/97 | 58/97 | 67/97 | 31/110 | 0.1687 | 18/20 |
| `current_config_state_features` | 65/110 | 82/110 | 89/110 | 59/97 | 75/97 | 82/97 | 33/110 | 0.1637 | 19/20 |
| `current_config_state_selector` | 62/110 | 71/110 | 80/110 | 57/97 | 66/97 | 74/97 | 32/110 | 0.1737 | 19/20 |
| `current_config_state_selector_family` | 65/110 | 80/110 | 86/110 | 59/97 | 73/97 | 79/97 | 33/110 | 0.1620 | 19/20 |
| `current_config_state_features_inplace` | 43/110 | 59/110 | 68/110 | 42/97 | 57/97 | 66/97 | 28/110 | 0.1429 | 19/20 |
| `all_candidate_plus_targeted_v4` | 72/110 | 86/110 | 93/110 | 65/97 | 78/97 | 84/97 | 34/110 | 0.2026 | 18/20 |
| `all_candidate_plus_targeted_v4_state_selector` | 73/110 | 87/110 | 94/110 | 66/97 | 79/97 | 85/97 | 33/110 | 0.2000 | 19/20 |
| `all_candidate_plus_targeted_v4_state_selector_family` | 76/110 | 92/110 | 96/110 | 68/97 | 83/97 | 87/97 | 32/110 | 0.1823 | 19/20 |
| `all_candidate_plus_targeted_v4_state_features` | 76/110 | 93/110 | 96/110 | 68/97 | 84/97 | 87/97 | 31/110 | 0.1799 | 19/20 |

Reference bars from prior saved-pool analysis:

| Variant | all u@20 | valid u@20 | read |
|---|---:|---:|---|
| `current_plus_targeted` | 77/110 | 69/97 | protected saved-pool targeted baseline |
| `promoted_feature_family` | 84/110 | 74/97 | saved-pool feature ceiling, not validated as live production fusion |

Interpretation:

- Additive `.state_features` is a real live candidate-recall lever on `current_config`: +10 all u@20 and +9 valid u@20.
- It mostly adds depth: +19 all u@50 and +16 all u@100 versus `current_config`.
- In-place reordering is rejected for now. It regresses union@20/50/100 and final@20.
- On the paired live targeted recipe, additive state features do improve candidate recall: `all_candidate_plus_targeted_v4` 72/110 -> 76/110 all u@20 and 65/97 -> 68/97 valid u@20.
- The same paired targeted run regresses final-list quality: final@20 34/110 -> 31/110 and NDCG@20 0.2026 -> 0.1799. This is candidate-recall evidence, not a production final-ranking patch.
- A single `state_feature_selector` branch is safer but weaker: targeted u@20 moves 72/110 -> 73/110 and NDCG@20 only slips 0.2026 -> 0.2000. It is not enough to close the focused recall gap.
- A family-grouped `state_feature_selector` is the cleanest tested packaging so far: it matches additive `.state_features` at u@20 (`76/110` all, `68/97` valid), loses only one all/valid u@50 versus additive duplicate branches, and is less noisy than cloning every branch. It still hurts final guardrails versus the targeted baseline, so it remains an experiment, not a production final-list patch.
- The remaining gap is branch-query quality and candidate selection, not just missing state fields.

## What Changed

Code changes:

- Added opt-in branch-local state-feature scoring in `mcrs/qu_modules/compiler_v0plus.py`.
- Added `branch_local_feature_rerank_mode` with `additive` and `in_place`.
- Added opt-in single `state_feature_selector` branch that scores the deduped union of fired branch candidates with the same state/catalog feature evidence.
- Added opt-in family-grouped `state_feature_selector` branches that score deduped candidates within source families, e.g. `state_feature_selector.lexical`, `state_feature_selector.lookup`, `state_feature_selector.dense.attributes`, `state_feature_selector.dense.intent`, and `state_feature_selector.centroid.anchor_tracks`.
- Added score breakdown traces for each `.state_features` branch: tag overlap, rarity-weighted tag overlap, phrase hits, temporal compatibility, popularity, negative tag demotion, anchor CF, and same-anchor novelty demotion.
- Normalized the V1 attribute fact to projected tag mention join for BM25 catalog-exact filtering.
- Added matrix variants:
  - `current_config_state_features`
  - `current_config_state_selector`
  - `current_config_state_selector_family`
  - `current_config_state_features_inplace`
  - `bm25_lookup_state_features`
  - `bm25_lookup_state_features_inplace`
  - `all_candidate_plus_targeted_v4`
  - `all_candidate_plus_targeted_v4_state_features`
  - `all_candidate_plus_targeted_v4_state_selector`
  - `all_candidate_plus_targeted_v4_state_selector_family`
- Added NDCG@20 to future matrix CSV/Markdown summaries as a final-quality guardrail.
- Added Modal matrix progress logging.

## Decisions

Keep:

- `current_config_state_features` as an experimental candidate-recall diagnostic. It is opt-in and measured.
- `state_feature_selector_grouping="family"` as the preferred experimental packaging for the next focused candidate-recall pass. It recovers the same u@20 candidates as additive duplicate `.state_features` on the paired targeted run, while avoiding a clone of every source branch. It is still not production-promoted because final@20/NDCG remain worse than targeted baseline.
- Single global `state_feature_selector` as a safer but underpowered diagnostic. It preserves most final-quality guardrail behavior, but its focused candidate-recall lift is small.
- Score-breakdown traces. They are needed to debug why a GT moved or did not move.
- Normalized V1 attribute/tag matching. It prevents punctuation mismatches from bypassing `catalog_exact`.
- Modal progress logging for long matrix runs.

Reject for promotion:

- `in_place` branch-local reranking. It is too destructive: it improves some controls but loses many failure-class candidates by replacing useful raw branch ordering.
- Treating state-feature scoring as a final-list solution. Candidate recall improved, but final quality did not: current_config NDCG@20 moved 0.1687 -> 0.1637 with additive features, and the paired targeted recipe moved 0.2026 -> 0.1799 with additive features or 0.1823 with family selector packaging.

Defer:

- Survivor slots and global RRF/ranker changes. They are final-ranking work and should be a separate goal.
- Prompt/schema iteration. The frozen state had enough signal to move live candidate recall.
- New retriever source. Prior saved-pool audit said only 2 valid GTs were absent from deep pools; most misses are ranking/query specificity.

## Where The Gap Still Lives

After the best live candidate-recall runs (`all_candidate_plus_targeted_v4_state_features` and `all_candidate_plus_targeted_v4_state_selector_family`):

- all union@20 is 76/110, still below the saved-pool feature ceiling 84/110.
- valid union@20 is 68/97, below the saved-pool feature ceiling 74/97.
- union@50 is much healthier: additive duplicate branches reach 93/110 all and 84/97 valid; family selector reaches 92/110 all and 83/97 valid.

That means many GTs are now reachable but still not branch-top-20. The likely next lever is not more state extraction; it is sharper branch queries or a candidate selector that can use the score features without drowning in duplicate RRF branches.

The paired targeted run confirms the tradeoff:

- `all_candidate_plus_targeted_v4_state_features` rescues +4 all u@20 and +3 valid u@20 over `all_candidate_plus_targeted_v4`.
- It also rescues +7 all u@50 and +6 valid u@50, so the state-feature signal is moving candidates toward the top.
- It hurts final@20 and NDCG@20, so the packaging is wrong for production. Additive duplicate branches are useful diagnostics, not a final-list strategy.
- `all_candidate_plus_targeted_v4_state_selector` is less noisy but underpowered: +1 all u@20, +1 valid u@20, +1 all u@50, +1 valid u@50 over targeted v4. It does not recover the candidates found by duplicate state-feature branches.
- `all_candidate_plus_targeted_v4_state_selector_family` recovers the same +4 all u@20 and +3 valid u@20 as additive `.state_features`. Its u@50 is one point lower than additive duplicate branches, but its packaging is cleaner and its final-list degradation is slightly smaller.

Per-class additive current_config gains:

| Pack | current u@20 | additive u@20 | additive u@50 |
|---|---:|---:|---:|
| P0_roleless_stale_entity_failure | 1/10 | 1/10 | 4/10 |
| P0_novelty_prior_anchor_failure | 3/10 | 5/10 | 7/10 |
| P0_new_artist_union20_gap_failure | 0/10 | 1/10 | 2/10 |
| P1_positive_tag_retrieval_gap_failure | 1/10 | 3/10 | 9/10 |
| P1_temporal_constraint_failure | 1/10 | 1/10 | 5/10 |
| P0_same_album_ranker_failure | 7/10 | 10/10 | 10/10 |
| P0_good_state_ranker_near_miss_failure | 9/10 | 10/10 | 10/10 |

Read:

- Same-album and clean near-miss cases are mostly fixable by branch-local state/catalog scoring.
- Positive-tag and temporal failures often improve at u@50 but not u@20, so top-20 candidate selection is still weak.
- Roleless/stale-entity and new-artist failures remain hard; they likely need better branch queries and stronger novelty/anchor handling, not just state fields.

## Guardrails

The live state-feature variants reported:

- `gt_release_date_masked`: 1/110.
- `gt_hard_dropped`: 10/110.

Most hard-dropped GTs are the known noisy/contradictory audit rows. One valid row is release-date masked, and one valid row is hard-dropped while still appearing in raw branch traces. This matters because branch union is a raw candidate-surfacing metric; final eligibility can still remove a candidate. Do not read raw branch union as “will survive final filters.”

Positive controls stayed stable or improved:

- `current_config`: 18/20 controls u@20.
- `current_config_state_features`: 19/20 controls u@20.
- `current_config_state_features_inplace`: 19/20 controls u@20.
- `current_config_state_selector`: 19/20 controls u@20.
- `current_config_state_selector_family`: 19/20 controls u@20.
- `all_candidate_plus_targeted_v4`: 18/20 controls u@20.
- `all_candidate_plus_targeted_v4_state_selector`: 19/20 controls u@20.
- `all_candidate_plus_targeted_v4_state_selector_family`: 19/20 controls u@20.
- `all_candidate_plus_targeted_v4_state_features`: 19/20 controls u@20.

Final-quality guardrail:

- `current_config_state_features`: final@20 31/110 -> 33/110, but NDCG@20 0.1687 -> 0.1637.
- `current_config_state_selector`: final@20 31/110 -> 32/110 and NDCG@20 0.1687 -> 0.1737.
- `current_config_state_selector_family`: final@20 31/110 -> 33/110, but NDCG@20 0.1687 -> 0.1620.
- `all_candidate_plus_targeted_v4_state_selector`: final@20 34/110 -> 33/110 and NDCG@20 0.2026 -> 0.2000.
- `all_candidate_plus_targeted_v4_state_selector_family`: final@20 34/110 -> 32/110 and NDCG@20 0.2026 -> 0.1823.
- `all_candidate_plus_targeted_v4_state_features`: final@20 34/110 -> 31/110 and NDCG@20 0.2026 -> 0.1799.
- Do not promote this packaging without a later fusion/ranking goal.

Temporal guardrail:

- `gt_release_date_masked` is 1/110 in state-feature runs.
- This is too small to make temporal the main effort right now; keep hard release filters conservative and treat era/style as soft scoring.

Tag/concept mapping guardrail:

- Do not ask the LLM to emit canonical catalog tags.
- LLM state should keep raw facts such as "early 2000s pop-punk" or "technical death metal".
- The compiler should map raw fact text to catalog concepts deterministically using cleaned catalog tag keys, aliases, optional embedding lookup over tag/concept strings, and BM25/FTS over track search text.
- Use mapped tags as score features, not hard filters.

## Artifacts

- `state_v1_generic_state_features_additive_all110.json/md/csv`
- `state_v1_generic_state_features_inplace_all110.json/md/csv`
- `state_v1_targeted_v4_all110.json/md/csv`
- `state_v1_targeted_v4_state_features_all110.json/md/csv`
- `state_v1_state_selector_all110.json/md/csv`
- `state_v1_state_selector_family_all110.json/md/csv`
- `state_v1_candidate_quality_nonprompt_matrix_all110.json`
- `state_v1_candidate_quality_nonprompt_report.md`

## Reviewer Feedback Reconciliation

Incorporated:

- Keep additive union@20 as the focused candidate-recall metric, but always report final@20, NDCG@20, controls, and hard-drop guardrails beside it.
- Test packaging instead of treating additive duplicate `.state_features` as production-safe. The live matrix now includes additive, in-place, single selector, and family selector variants.
- Keep score-breakdown traces for state-feature scoring so row-level wins and misses can be debugged without re-running a local replay.
- Keep tag/concept mapping compiler-side. The LLM emits raw facts; the compiler normalizes and maps them to safe catalog evidence.
- Treat temporal as a guardrail, not the main bet. The live focused run has only 1/110 GT release-date-masked row, so broad temporal work is not the next priority.
- Defer random devset slice until the focused-110 packaging is cleaner, but keep it as the next regression gate before full devset.

Rejected or deferred:

- Do not use survivor slots or final-list prepending in this goal. That is final-ranking behavior, not candidate-recall measurement.
- Do not optimize final@20 as the primary metric here. It is a guardrail until a later ranking/fusion goal.
- Do not retune global RRF, train a global ranker, or change the frozen state extractor in this goal.
- Do not promote standalone tag retrieval as the main bet. Use cleaned tag/concept evidence as a scoring feature inside existing branch-local candidate selection.

## Recommendation

Do not ship this as a production ranking change yet.

Promote the family-grouped state selector only as a focused candidate-recall experiment and keep it behind config. The paired live run confirms state-derived score features add candidate recall, but both duplicate additive branches and family selector packaging still hurt final ranking. Keep additive `.state_features` as a diagnostic ceiling check, reject in-place reranking, and treat the single global selector as underpowered. The next useful goal is a stronger branch-local candidate selector or query-specificity pass over the u@50-not-u@20 failures, followed by a paired random devset slice before any full-devset or production config change.
