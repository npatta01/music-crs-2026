# Overnight Candidate Recall Gap Iteration - 2026-06-09

Scope: focused-110 state-gap pack only. V1 state extraction and schema stayed frozen. This run tested compiler/projection and retriever/source levers for candidate recall, not final ranking.

## Baseline Checkpoint

Use these as the comparison frame:

| Variant | all union@20 | all union@50 | all union@100 | valid-only union@20 | valid-only union@50 | valid-only union@100 |
|---|---:|---:|---:|---:|---:|---:|
| current OR | 75/110 | 87/110 | 91/110 | 67/97 | 77/97 | 81/97 |
| current + targeted | 77/110 | 90/110 | 93/110 | 69/97 | 80/97 | 83/97 |
| promoted feature family | 84/110 | 95/110 | 100/110 | 74/97 | 84/97 | 89/97 |
| all feature family | 84/110 | 95/110 | 104/110 | 74/97 | 84/97 | 92/97 |

Interpretation: the best measured focused-110 lift is still the branch-local candidate-quality family, not a prompt/schema change.

## What Changed In This Iteration

Added analysis-only variants in `scripts/state_v1_retriever_matrix.py`:

- `artist_neighbor_scene_fact_v4`: exact-resolves compiler-exposed V1 artist references before artist-neighbor tag scoring.
- `scene_era_fact_terms_v3`: tag/scene branch using only structured attribute facts plus lyric theme, avoiding prior artist-name leakage from generated summaries.
- `query_text_tag_popularity_soft_novelty` and `scene_era_tag_popularity_v2_soft_novelty`: same branch queries, but do not hard-exclude anchor artists just because `target_artist_mode=new_artist`.
- `reference_artist_discography`: small additive fanout over exact-resolved reference/satisfied artist IDs.

Also added a cached catalog-feature view for the fact-only branch so future local scans can be less painful.

## Results

| Test | Result | Decision |
|---|---:|---|
| `artist_neighbor_scene_fact_v4` | protected additive union@20 stayed 60/110; no new @20 rescues | Reject as recall lever; cleaner input, no lift |
| `scene_era_fact_terms_v3` | additive @20 = 65/110 vs v2 = 66/110 against protected baseline | Reject as replacement; fact-only loses useful context |
| soft novelty no-hard-drop variants | branch-only improves slightly, additive @20 unchanged | Keep as policy note, not measured recall lift |
| `qwen06_lyrics` on 5 lyric residuals | 0/5 @20, 0/5 @50, 0/5 @100; lyric branch GT absent top1000 where checked | Existing pseudo-lyrics branch is not solving lyric/theme misses |
| `siglip_visual` on 6 visual residuals | 0/6 @20, 0/6 @50, 0/6 @100; only one GT appeared in SigLIP top1000, at rank 148 | Existing visual branch is weak for these misses |
| `reference_artist_discography` | +1 all-110 @20 beyond promoted family, but rescued GT is audit-invalid | Defer; useful diagnostic, not valid-GT lift |

## What The Gap Is

The main gap is not that V1 state cannot extract useful information. In inspected failures the state often has the right facts: lyric themes, style/reference artists, scene terms, era cues, and satisfied prior tracks.

The gap is downstream:

1. Branch-local ordering is weak. After the promoted feature family, 26/110 still miss @20; many are near misses at ranks 22-50 or 51-100. This is candidate ordering inside branch pools, not state extraction.
2. Existing lyric and visual sources are weak. The focused residual tests show the current lyric and SigLIP branches do not surface GTs in top100 for the targeted misses, and often not in top1000.
3. Tag/scene search is noisy. Fact-only structured tags avoid entity leakage but lose context and do not improve recall. The tag-concept analysis also shows concept/tag search is not the answer; concept-cleaned text is only a small dense-query normalization helper.
4. Some remaining wins are noisy or contradictory GT. Reference-artist discography rescued `Dear Yvette`, but the audit labels it invalid because the user asked to branch out from Masta Ace and the GT is still Masta Ace.

## Current Recommendation

Promote to a full-devset smoke only after packaging the measured `promoted_feature_family` candidate-quality logic, not the rejected fact-only/tag variants.

Next high-value work:

- Implement a production-shaped branch-local candidate scorer over existing pools: catalog feature score, anchor/CF affinity, tag/scene compatibility, soft temporal compatibility, and hard drops only for explicit resolved exclusions.
- Add or improve source-specific retrievers only where the residual tests prove source weakness:
  - lyric/theme: current pseudo-lyrics Qwen branch is inadequate; test a better lyric/theme document source or stronger semantic document.
  - visual/cover: current SigLIP text-to-cover branch is inadequate; test better visual query construction or image-caption/cover-description source.
- Keep Qwen 0.6B mostly for lyrics in production-style configs; use Qwen 8B for metadata/attributes where available.
- Do not spend more time on tag/concept search as a recall branch. Use concept mapping only as optional dense-query cleanup.

## Evidence Artifacts

- `overnight_candidate_quality_repro.json`
- `overnight_artist_fact_v4_matrix.json`
- `overnight_scene_fact_v3_matrix.json`
- `overnight_soft_novelty_matrix.json`
- `overnight_qwen06_lyrics_residual5_with_pools.json`
- `overnight_qwen06_lyrics_residual5_branch_pools.json`
- `overnight_siglip_visual_residual6.json`
- `overnight_siglip_visual_residual6_branch_pools.json`
- `overnight_reference_artist_discography_matrix.json`
