# State Fact Extraction Root-Cause Audit

This audits the current best paid validation path:
`state_fact_v1_paid_current_full_stateonly_fact_scores.json`.

## Headline

- Samples: 56
- Strict all-pass: 37 / 56 = 66.1%
- Compiler-core pass: 44 / 56 = 78.6%
- Strict failures: 19
- Request-type-only failures: 7
- Core state failures: 12

The strict score understates state quality because 7 failures are request-type label disagreements that do not affect the compiler-core checks. The remaining 12 failures are the real audit set.

## What The Gap Is

The gap is not mostly raw ambiguity. It is a mix of four issues:

1. **True extraction omissions**: the model sometimes drops useful literal facets such as `hit`, `artistically unique`, `Rusty Cage`, `deep longing`, or `emotional storytelling`.
2. **Paraphrase vs retrieval-term mismatch**: the model captures the meaning, but not the exact retrieval-friendly phrase. Example: `watching a movie` becomes `cinematic narrative`; `artistically unique` becomes `striking cover art` and `memorable visual identity`.
3. **Label/evaluator contract mismatch**: labels sometimes require a downstream policy decision instead of a fact. Example: style rejections are scored as hard exclusions even when compiler-safe behavior should treat them as soft demotions.
4. **Role ambiguity / policy leakage**: some labels encode whether a prior artist should be a seed, not just whether the user mentioned or liked it. Example: Brent Faiyaz and Mac Miller cases are not purely extraction questions.

## Core Failure Audit

| Sample | Failure class | Missing facts | Audit read | What should change |
|---|---:|---|---|---|
| `15b1caf3...::t6` | true extraction omission | `electronic`, `soulful` | The state captures `out there` and `unique`, but loses useful prior-derived sonic facets. | Add a deterministic or prompted rule to preserve salient liked-prior attributes as `reference` or `desired` facets when the current utterance says "what else" / continuation. |
| `f2d85aa5...::t8` | mixed: extraction + label scope | `ambient electronic`, `dark and harsh`, temporal kind | State captures warm/ethereal/subtly rhythmic/instrumental and soft-rejects dark/harsh, but misses explicit genre phrase and temporal object. | Keep style negatives soft; fix temporal scorer/schema to separate `release_date` filter vs style-era cue. Require literal genre preservation. |
| `1e14a07f...::t8` | evaluator/label mismatch | hard `metal` exclusion | State correctly extracts `metal` as rejected style, but marks it soft. That is safer than a hard catalog filter. | Label should accept soft style rejection; hard exclusions should be reserved for resolved artist/track/album. |
| `d265b5a9...::t6` | paraphrase / literal retrieval-term gap | `artistically unique` | State captures `striking cover art` and `memorable visual identity`, but drops the exact phrase. | Score semantic capture separately from literal retrieval terms. Add literal-preservation for rare visual/aesthetic phrases. |
| `963b3ee7...::t5` | mixed: role/policy + omission | Lupe role, `boost my energy`, hard style exclusion | State hard-rejects Lupe Fiasco and captures upbeat/energetic/feel-good/hip-hop, but misses `boost my energy`; label expects Lupe as history/satisfied rather than rejected. | Split "artist complained about" from "artist to never return". Preserve motivational phrase as energy facet. Do not score style negatives as hard entity filters. |
| `899f906b...::t8` | label/evaluator mismatch | Linkin Park role | State marks Linkin Park/Pantera as satisfied prior and also hard-rejects them because user says "besides". That is compiler-safe. | Evaluator should accept satisfied-prior plus hard exclusion for "besides X" cases; role list is too narrow. |
| `93199894...::t6` | true extraction omission | `Rusty Cage` | State captures Soundgarden, Spoonman, Stone Temple Pilots, Nirvana, but misses the explicit track `Rusty Cage`. | Improve exact quoted-title extraction; add deterministic quoted-entity carry-forward from current/prior user utterances. |
| `692611f0...::t8` | paraphrase / retrieval-term mismatch | `watching a movie` | State captures `vivid storytelling` and `cinematic narrative`, which is semantically right but may lose lexical retrieval coverage. | Preserve raw simile phrases as additional `surface_phrase` / query facets when they are short and distinctive. |
| `8071d14d...::t5` | role ambiguity / policy leakage | Brent Faiyaz role/seed | User says "I like Brent Faiyaz" and asks for something similar/more groove. State treats Brent as current target seed; label expects satisfied prior and no seed. Both are defensible depending on compiler policy. | Label should express both facts: liked artist and similarity anchor. Compiler decides whether to use same-artist branch or similar-artist branch. |
| `c863175a...::t6` | policy label mismatch | Mac Miller seed | User says "not just Mac Miller"; state treats Mac Miller as satisfied prior and not seed. Label expects seed=true. That is a compiler-policy choice, not pure extraction. | Do not bake `use_as_retrieval_seed=True` into hand labels for "not just X" unless exact same-artist retrieval is explicitly desired. |
| `c96d7bb9...::t7` | paraphrase / omission | `deep longing`, `emotional storytelling` | State captures `sertanejo`, `powerful emotional`, and `deep heartfelt lyrics`, but loses two useful affect/story facets. | Keep both normalized and literal facets for emotional/lyrical asks. |
| `2bbc0a7e...::t1` | literal facet omission | `hit` | State merges `early 2000s hit` into one era phrase; popularity is not separately available. | Split compound facets into `era=early 2000s` and `popularity=hit`. |

## Conclusion

The current extractor is not good enough as a direct production contract, but the failure mode is more specific than "LLM cannot solve it."

The right next step is not more broad prompt iteration. It is:

1. Make `facts` the canonical evaluation target.
2. Score semantic fact capture separately from compiler policy.
3. Accept soft style exclusions when the rejected item is not a resolved entity.
4. Preserve literal retrieval phrases alongside normalized facets.
5. Derive legacy `entities`, `rejections`, and seed flags deterministically from facts.

After that, rerun the 56-sample paid validation. The expected improvement should come from removing evaluator noise and making the model preserve retriever-usable literal facets, not from asking the LLM to directly decide retrieval policy.
