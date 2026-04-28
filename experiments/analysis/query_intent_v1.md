# Query Intent Analysis v1

Issue 45 notebook-first analysis over the `test` split using full-conversation session labeling with `openai/gpt-5.5` through the local LiteLLM proxy.

## Coverage

- Target sessions: `1000`
- Successful labels: `999`
- Skipped failures: `1`
- Successful label file: `experiments/analysis/issue_45/full_labels_openai_gpt_5.5_1000.jsonl`
- Failure log: `experiments/analysis/issue_45/full_labels_openai_gpt_5.5_1000_failures.jsonl`

The single skipped session (`a66c093c-76f5-4e8d-bd78-fe01bd9821f4`) returned reasoning-only output without a final JSON object after retry.

## Goal Taxonomy Snapshot

Most common goal categories in the labeled `test` set:

- `K` Temporal & Era Discovery: `156` (`15.6%`)
- `B` Lyrical Discovery: `142` (`14.2%`)
- `H` Artist & Discography Discovery: `134` (`13.4%`)
- `F` Metadata-Rich Exploration: `95` (`9.5%`)
- `E` Interactive Refinement: `95` (`9.5%`)

Specificity is spread across the four cells, but high-target or high-dialogue specificity dominates:

- `LH`: `313` (`31.3%`)
- `HL`: `306` (`30.6%`)
- `LL`: `278` (`27.8%`)
- `HH`: `102` (`10.2%`)

## Conversation Dynamics

Session archetypes are overwhelmingly multi-turn recommendation tasks rather than one-shot lookups:

- `iterative_refinement`: `642` (`64.3%`)
- `transition_or_pivot`: `238` (`23.8%`)
- `recover_forgotten_item`: `50` (`5.0%`)
- `find_more_like_this`: `49` (`4.9%`)
- `exploratory_browsing`: `17` (`1.7%`)
- `direct_lookup`: `3` (`0.3%`)

Context dependency is almost always conversation-wide:

- `both` prior user turns and prior assistant/music turns: `995` (`99.6%`)
- `prior_user_turns`: `3` (`0.3%`)
- `none`: `1` (`0.1%`)

Recommendation mode also skews heavily toward open candidate sets:

- `multiple_valid_tracks`: `858` (`85.9%`)
- `artist_or_work_cluster`: `93` (`9.3%`)
- `single_specific_track`: `48` (`4.8%`)

## Constraint and Evidence Patterns

Most common extracted constraint facets:

- `mood_or_emotion`: `654` (`65.5%`)
- `artist_or_discography`: `632` (`63.3%`)
- `mixed`: `475` (`47.5%`)
- `era_or_time`: `428` (`42.8%`)
- `lyrics_or_story`: `260` (`26.0%`)

Most common retrieval evidence needs:

- `hybrid`: `860` (`86.1%`)
- `recommendation_history_carryover`: `627` (`62.8%`)
- `semantic_similarity`: `231` (`23.1%`)
- `metadata_filter`: `92` (`9.2%`)
- `exact_entity`: `62` (`6.2%`)

## Failure Risks

The main risk modes are conversational, not purely lexical:

- `long_range_callback`: `503` (`50.4%`)
- `hidden_target`: `287` (`28.7%`)
- `underspecified`: `113` (`11.3%`)
- `multimodal_dependence`: `57` (`5.7%`)

This suggests the system’s main difficulty is preserving and using long-range session state, plus resolving implicit targets that emerge only through interaction.

## Takeaways

1. The benchmark is mostly not a one-shot retrieval problem.
   `iterative_refinement` plus `transition_or_pivot` account for `880 / 999` sessions (`88.1%`).

2. Conversation state is not optional.
   Nearly every successful label required carryover from both prior user turns and prior assistant/music turns.

3. A single flat rewritten query is too weak as the primary representation.
   Most sessions combine positive anchors, negative anchors, refinement, pivots, and long-range constraints that are hard to preserve in one text string.

4. Retrieval should be treated as hybrid by default.
   The dominant label is `hybrid` retrieval evidence, often coupled with recommendation-history carryover.

5. The first structured dimensions worth extracting are:
   mood/emotion, artist/discography, era/time, lyrics/story, and prior accepted/rejected examples.

## Recommended Next Step

Prioritize a conversation-aware query representation layer rather than only improving free-text rewrite prompts.

The next experiment should extract structured state from the full conversation, such as:

- intent type: refinement / pivot / forgotten-item recovery
- positive anchors: accepted tracks, artists, attributes
- negative anchors: rejected tracks, artists, attributes
- active constraints: mood, era, genre, lyrics, popularity, geography, activity
- recommendation-history carryover: which prior suggestions still matter
- generated sparse query
- generated dense semantic query

Then retrieve with:

- BM25 or sparse lexical matching for explicit entities and metadata
- dense embedding retrieval for semantic and mood similarity
- fusion or reranking that accounts for accepted/rejected history

That direction fits the labeled dynamics better than relying on one flattened retrieval query per session.
