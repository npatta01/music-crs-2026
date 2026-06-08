# Focused 110 Gap-Fix Pass: Satisfied Anchors + Hard-Drop Branch Matrix

Date: 2026-06-08

Scope:

- Frozen V1 state extraction/prompt/schema.
- Focused 110 state-gap pack only.
- Candidate recall only; no global RRF/final-ranker work and no full-devset claim.
- Compared against the previous current+targeted baseline and the promoted non-prompt feature-family baseline from `state_v1_candidate_quality_nonprompt_matrix_all110.json`.

## What Changed

1. `track_feedback.role="satisfied"` now counts as a positive soft anchor in the compiler, alongside `accepted` and `seed`.
   - This fixes continuation turns where the user says a prior recommendation worked, but the compiler previously discarded that track as an anchor.
   - Existing pivot protections still apply: pivot turns do not add prior-anchor tags to the BM25 tag channel.

2. The focused retriever matrix now applies `branch_local_rules` to analysis branches as well as compiler branches.
   - Before this, diagnostic branches such as same-album fanout could ignore hard drops and overstate contradictory/noisy GT rescues.
   - Added `all_candidate_plus_targeted_v4_hard_drop`, a hard-drop-only targeted branch variant.

Rejected in this pass:

- The full soft rule set (`new_artist_demote`, `anchor_tag_boost`, `explicit_popularity_boost`, `negative_tag_demote`, `temporal_soft`) as a blanket branch reranker.
- On the source-gap residual slice, full rules reduced valid top-20 from 3/16 to 1/16 because temporal/popularity soft scoring pushed valid scene/era hits down. Keep those as future branch-local experiments, not global defaults.

## Metrics

All-110 focused pack:

| Candidate set | all union@20 | all union@50 | all union@100 | valid union@20 | valid union@50 | valid union@100 |
|---|---:|---:|---:|---:|---:|---:|
| current OR baseline | 75/110 | 87/110 | 91/110 | 67/97 | 77/97 | 81/97 |
| current + targeted baseline | 77/110 | 90/110 | 93/110 | 69/97 | 80/97 | 83/97 |
| promoted feature family | 84/110 | 95/110 | 100/110 | 74/97 | 84/97 | 89/97 |
| hard-drop targeted variant alone vs protected pools | 79/110 | 92/110 | 100/110 | 70/97 | 82/97 | 89/97 |
| current + targeted OR hard-drop variant | 80/110 | 94/110 | 101/110 | 71/97 | 83/97 | 90/97 |
| promoted feature family OR hard-drop variant | 87/110 | 98/110 | 104/110 | 76/97 | 87/97 | 93/97 |

Residual source-gap 19 slice:

| Candidate set | all union@20 | all union@50 | all union@100 | valid union@20 | valid union@50 | valid union@100 |
|---|---:|---:|---:|---:|---:|---:|
| prior v4 source-gap run | 1/19 | 2/19 | 2/19 | 1/16 | 2/16 | 2/16 |
| satisfied-anchor v4, no hard-drop rules | 4/19 | 7/19 | 10/19 | 2/16 | 5/16 | 8/16 |
| satisfied-anchor v4 hard-drop-only | 4/19 | 6/19 | 10/19 | 3/16 | 5/16 | 9/16 |

Interpretation:

- This is a real candidate-recall improvement, but not a replacement for the prior promoted feature family.
- Hard-drop targeted branches add 3 all / 2 valid top-20 hits on top of the promoted feature-family hit set.
- The biggest measured value is additive coverage: promoted feature family OR hard-drop variant reaches 87/110 all and 76/97 valid at union@20, and 104/110 all / 93/97 valid at union@100.

## Rescued Valid Examples

New valid top-20 gains over `current_plus_targeted`:

- `380a5ed5-3eb9-4201-8fa6-81381a583bf5::t3`: God Hates a Coward / Tomahawk via `dense.qwen_8b.attributes_enriched`, rank 1.
- `67b9ba8a-382f-4b70-af76-576848d8cf67::t8`: Gangsta Gangsta / N.W.A. via `analysis.artist_neighbor_scene_v2`, rank 20.

Additional valid gains inside the protected-pool all-110 matrix include:

- Two To Make It Right / Seduction via `analysis.scene_era_tag_popularity_v2`, rank 6.
- Armature / Emptyset via CLAP sonic, rank 12.
- Redneck Yacht Club / Craig Morgan via `analysis.scene_era_tag_popularity_v2`, rank 1.
- Love Train / The O'Jays via `analysis.artist_tag_neighbor_popularity`, rank 4.
- Vengeance / Perturbator via SigLIP visual, rank 1.

Noisy/contradictory example still surfaced:

- `88beb200-0334-4aba-be15-8e1303725766::t6`: Used To / Lil Wayne, Drake via same-album fanout, rank 14. This GT conflicts with the user constraint and is not counted as a valid win. The frozen state/projection did not supply a resolved Drake exclusion for this row, so hard-drop could not remove it.

## Remaining Gaps

Still not solved by this pass:

- Hidden-target / lyric rows: existing lyric and text branches still do not put several GTs into top-20.
- Visual cover/artwork rows: SigLIP visual helps a few controls and one positive-tag row, but does not solve visual-text misses such as the harder residual cover-art examples.
- Temporal scene/popularity: scene branches help, but full temporal soft scoring is too blunt. Keep hard filters only for explicit resolved date constraints; treat era as branch-specific scoring.
- Roleless stale entity: satisfied anchors help continuation, but old prior entities still need better branch selection and ranking; many valid misses are now @21-100 rather than absent.
- Same-album fanout is useful for continuation but dangerous when rejection state is missing. It should stay behind hard-drop and likely production gating.

## Decision

Keep:

- Compiler support for positive `satisfied` feedback as a soft anchor.
- Matrix harness fix that applies branch-local rules to analysis branches.
- `all_candidate_plus_targeted_v4_hard_drop` as the next diagnostic/prototype candidate-recall variant.

Do not promote yet:

- Full soft branch-local rule set as a global default.
- Same-album fanout without resolved hard-drop and state-quality checks.
- Any full-devset or leaderboard claim.

Next measured step:

- Combine the prior promoted feature family with the hard-drop targeted variant in one saved branch-pool run, then test a small production-gating config: keep hard drops global, gate same-album to positive satisfied/accepted continuation turns, gate scene/era/popularity to explicit scene/era/popularity state, and keep visual/lyric branches as source-specific experiments.

Artifacts:

- Matrix JSON: `state_v1_gapfix_hard_drop_all110.json`
- Matrix CSV: `state_v1_gapfix_hard_drop_all110.csv`
- Source-gap JSON: `state_v1_gapfix_hard_drop_source19.json`
- Source-gap CSV: `state_v1_gapfix_hard_drop_source19.csv`
