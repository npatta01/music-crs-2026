# State Projector v1 Iteration Summary

Date: 2026-06-07

## What changed

This iteration tested the split contract:

1. LLM extracts fact-first state: `current_request`, `facts`, `exclusions`, temporal, lyrics.
2. Deterministic projection derives compiler-facing views:
   - `mentioned_entities`
   - `explicit_rejections`
   - audit-only `compiler_mentioned_entities`
   - audit-only `compiler_explicit_rejections`
3. Compiler/retriever policy should consume the projected view, not raw LLM seed flags.

Code changes:

- `mcrs/conversation_state/schema.py`
  - Added fact/exclusion projection helpers.
  - `mentioned_entities` is now fact-first when `facts` or `exclusions` are present.
  - `explicit_rejections` is now fact-first when `facts` or `exclusions` are present.
  - Raw compatibility fields still work for legacy states without fact-first fields.
- `mcrs/conversation_state/replay_eval.py`
  - Audit output now includes `compiler_mentioned_entities` and `compiler_explicit_rejections`.
- `mcrs/conversation_state/prompts/current.py`
  - Added generic retriever-critical cue instructions for popularity, functional goals, similes, negative style phrases, exact alternatives, and replacement-after-failed-exact-item.
- `mcrs/conversation_state/repair.py`
  - Added deterministic post-extraction repair for literal current-turn cue phrases, negative correction phrases, stale similarity anchors, named style anchors, and praised current-turn named-artist context.
- `mcrs/qu_modules/compiler_v0plus_qu.py`
  - Applies the deterministic repair after LLM schema validation for sync and async extraction.
- `scripts/evaluate_state_projection_labels.py`
  - Scores the compiler-facing projected state (`compiler_mentioned_entities`, `compiler_explicit_rejections`) separately from request-type/policy labels.

## Local validation

Command:

```bash
uv run python -m pytest -q tests/test_state_v1_schema.py tests/test_state_repair.py tests/test_state_fact_evaluator.py tests/test_state_replay_evaluator.py tests/test_v0plus_compiler.py tests/test_v0plus_compiler_qu.py tests/test_lancedb_retriever_standalone.py
git diff --check
```

Result:

- `205 passed`
- 1 Pydantic deprecation warning from class-based config.
- `git diff --check` passed.

## Paid validation setup

Scoped pack:

- `state_projector_v1_scoped20_pack.json`
- 20 samples total:
  - 12 prior compiler-core failures from the previous paid state-fact run.
  - 8 passing controls.

Labels:

- `state_projector_v1_scoped20_fact_labels.json`

Model:

- `openrouter/deepseek/deepseek-v4-flash`
- prompt version: `current`
- history source: `window`

## Paid validation results

### Before cue prompt

Artifacts:

- `state_projector_v1_scoped20_deepseek_audit.jsonl`
- `state_projector_v1_scoped20_deepseek_fact_scores.json`
- `state_projector_v1_scoped20_deepseek_projection_scores.json`

Fact-label score:

- Strict all-pass: `8/20`
- Compiler-core pass: `9/20`

Projection score:

- Strict projection pass: `12/20`

### After cue prompt

Artifacts:

- `state_projector_v1_scoped20_deepseek_promptcue_audit.jsonl`
- `state_projector_v1_scoped20_deepseek_promptcue_fact_scores.json`
- `state_projector_v1_scoped20_deepseek_promptcue_projection_scores.json`
- `state_projector_v1_scoped20_deepseek_promptcue_projection_scores_relaxed.json`

Fact-label score:

- Strict all-pass: `10/20`
- Compiler-core pass: `10/20`

Projection score:

- Strict projection pass: `14/20`
- Token-aware projection pass: `16/20`

The cue prompt was net positive on this scoped set.

### Full JSON few-shot baseline

Artifacts:

- `state_projector_v1_scoped20_deepseek_fewshot_audit.jsonl`
- `state_projector_v1_scoped20_deepseek_fewshot_fact_scores.json`
- `state_projector_v1_scoped20_deepseek_fewshot_projection_scores.json`

Fact-label score:

- Strict all-pass: `15/20`
- Compiler-core pass: `15/20`

Projection score:

- Token-aware projection pass: `18/20`
- Remaining projected gaps:
  - `heavy and intense` was not emitted as a negative style/rejection.
  - `lyrical storytelling` was compressed to a weaker storytelling phrase.

### Failed prompt-only iteration

Adding more prompt prose and two extra few-shots did not hold up:

- `state_projector_v1_scoped20_deepseek_finalcue_audit.jsonl`
- Strict fact all-pass: `12/20`
- Compiler-core fact pass: `16/20`
- Projection pass: `16/20`

Decision: do not keep the prompt-only extension. It overfit the two target cases and regressed other projection cases.

### Deterministic repair on previous paid run

Artifacts:

- `state_projector_v1_scoped20_deepseek_fewshot_repaired_audit.jsonl`
- `state_projector_v1_scoped20_deepseek_fewshot_repaired_fact_scores.json`
- `state_projector_v1_scoped20_deepseek_fewshot_repaired_projection_scores.json`

Fact-label score:

- Strict all-pass: `15/20`
- Compiler-core pass: `17/20`

Projection score:

- Strict projected compiler-state pass: `20/20`
- The stricter scorer also checks stale forbidden positives, not only missing positives/rejections.

### Fresh paid run with repair

Artifacts:

- `state_projector_v1_scoped20_deepseek_repairlive_audit.jsonl`
- `state_projector_v1_scoped20_deepseek_repairlive_rerepaired_audit.jsonl`
- `state_projector_v1_scoped20_deepseek_repairlive_rerepaired_fact_scores.json`
- `state_projector_v1_scoped20_deepseek_repairlive_rerepaired_projection_scores.json`

Fact-label score after repair:

- Strict all-pass: `13/20`
- Compiler-core pass: `14/20`

Projection score after repair:

- Strict projected compiler-state pass: `20/20`

Interpretation: live DeepSeek extraction is still variable at the full fact-label level. The deterministic projector/repair layer is what closes the scoped compiler-facing gaps.

### Relation/reuse current prompt plus repair

Artifacts:

- `state_projector_v1_relation_reuse_scoped20_current_live_audit.jsonl`
- `state_projector_v1_relation_reuse_scoped20_current_live_repaired_audit.jsonl`
- `state_projector_v1_relation_reuse_scoped20_current_live_repaired_fact_scores.json`
- `state_projector_v1_relation_reuse_scoped20_current_live_repaired_projection_scores.json`

Fact-label score after repair:

- Strict all-pass: `18/20`
- Compiler-core pass: `19/20`
- Required entity coverage: `20/20`
- Required exclusions: `20/20`
- Forbidden stale seeds: `20/20`

Projection score after repair:

- Strict projected compiler-state pass: `20/20`

Remaining strict failures:

- `f2d85aa5...::t8`: `hidden_target`/`attribute_search` plus `release_date`/`style_era` disagreement. The state preserves genre, mood, negative style, and temporal text; this is a temporal/request-type label-policy edge.
- `c863175a...::t6`: `attribute_search` vs `similar_to_prior`. The prompt explicitly says attribute-rich asks should be `attribute_search`; compiler projection still passes.

Decision: keep the repair/projector changes. Do not add another broad prompt or repair iteration for these two strict failures without retrieval-facing evidence.

### Paid 56-sample fact-label validation plus repair

Artifacts:

- `state_fact_v1_paid_current_full_audit.jsonl`
- `state_fact_v1_paid_current_full_current_repaired_audit.jsonl`
- `state_fact_v1_paid_current_full_current_repaired_fact_scores.json`
- `state_fact_v1_paid_current_full_current_repaired_projection_scores.json`

Fact-label score after repair:

- Strict all-pass: `43/56` (`0.768`)
- Compiler-core pass: `51/56` (`0.911`)
- Required entity coverage: `52/56` (`0.929`)
- Required exclusions: `56/56`
- Forbidden stale seeds: `56/56`

Projection score after repair:

- Projected retriever-input pass: `56/56`
- Scorer definition: exact positive compiler mentions plus `style_reference_entities` count as positive retriever inputs; forbidden exact positives still check only exact compiler mentions.

Additional fixes validated on this broader pack:

- Album rejections now survive projection into `explicit_rejections` (`Blade Runner 2049`).
- Already-extracted exact current albums/tracks/artists are promoted from soft/query-facet shape to retriever seeds when the current turn names them (`Cracker Island`).
- Fallback quoted track probes are recovered when the user asks “not even `<track>`?” (`Rusty Cage`).
- Literal current-turn facets are preserved for retriever query terms (`electronic`, `soulful`, `ambient electronic`, `artistically unique`, `watching a movie`, `deep longing`, `emotional storytelling`).
- Soft artist anchors are represented as style references, not exact fanout seeds, for “not just X” and “someone like X or Y” (`Mac Miller`, `John Fogerty`, `Bruce Springsteen`).

Remaining strict fact-label failures are mostly request-type disagreements plus one temporal-kind disagreement. They do not currently block projected compiler input on the paid 56 pack.

## What worked

- Deterministic projection fixed the compatibility-field leak class:
  - Fact/exclusion fields now override noisy `entities` and `rejections` for compiler-facing views.
  - Example: a raw LLM `entities` seed can no longer make a fact-level exclusion become a positive compiler seed.
- Deterministic repair closed the remaining scoped projection gaps:
  - Lost literal cues: `out there`, `positive vibe`, `boost my energy`, `lyrical storytelling`.
  - Negative corrections: `it is actually heavy and intense` becomes a rejected style fact plus projection rejection.
  - Stale similarity anchors: liked prior artist/track are demoted when the turn is `similar_to_prior` plus concrete attributes.
  - Named style anchors: `similar to Mac Miller's style` promotes Mac Miller as a usable style anchor unless the user asks for different/new/other artists or explicitly says not that artist.
  - Praised current-turn artists such as `Flying Lotus` and `Kendrick` are retained as satisfied non-seed context when the current request pivots to attributes.
- Negative style phrases are better represented after the cue prompt:
  - `dark harsh` now projects as negative style.
  - `heavy and intense` / `metal` now project as soft tag/style rejections.
- Replacement exact-track pattern improved:
  - `Tom Sawyer` is now rejected and `The Spirit of Radio` is the target.
- Popularity cue improved:
  - `hit back then` is now emitted as a popularity fact.

## What did not work yet

Projection on the scoped20 pack has no remaining failures after repair.

Full fact labels still have failures, but they are not all compiler-facing extraction gaps:

1. Request-type/policy disagreements remain noisy (`hidden_target` vs `attribute_search`, `similar_to_prior` vs `attribute_search`, `release_date` vs `style_era`).
2. Some hand labels intentionally ask for roles that are arguable, such as whether Mac Miller should be a hard artist seed or a style anchor.
3. Style exclusion normalization still varies (`metal` vs `heavy intense metal`, `dark and harsh` vs `dark harsh`), though the projected compiler view now has usable negative/rejection signals.

## Interpretation

The split is valid:

- The projector is useful and should stay.
- The raw LLM fact extractor is still incomplete, but the current scoped compiler-facing failures are closed by deterministic projection/repair.
- The replay-level `target_artist_mode` / `retrieval_profile` score should not be treated as the primary extractor score because those are compiler-policy outputs under the new contract.

The most important remaining extractor behavior is literal phrase preservation for retriever-critical cues:

- popularity: `hit`
- visual/aesthetic: `artistically unique`
- simile: `watching a movie`
- emotional/lyrical carryover: `deep longing`, `emotional storytelling`
- combined phrase preservation: `ethereal vocals`

## Recommendation

Keep the fact-first projection and deterministic repair. Do not rely on prompt-only extraction to close these gaps.

Next focused iteration should expand validation, not add more prompt prose:

1. Run the projection scorer on the full 70 or 110 hand-labeled pack.
2. Add deterministic repairs only for repeated, literal current-turn cue failures that are non-policy and safe to project.
3. Keep request-type and retrieval-policy derivation in the compiler/projector, not as an LLM quality gate.
4. Only after projection holds on a larger pack, run retrieval to measure whether union@20 improves.
