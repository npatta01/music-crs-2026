# V1 Retrieval Regression — Independent Audit

Auditor: Claude (independent judge pass; **no** prompt/schema changes made).
Repo head: `2b24623` · Branch: `codex/issue-111-clean-v1-bridge` · Date: 2026-06-09.

Main question asked: *Did richer V1 state hurt because compiler/retriever consumption
made query pools noisier (BM25 `tag_list`, duplicate dense/CLAP branches)?*

## TL;DR verdict

1. **The mechanism is real and visible.** Verified in code *and* in the live 800-turn
   trace: the compiler dumps raw free-text into lexical BM25 channels on **100% of turns**.
   The "state is good but usage is bad" hypothesis is well-supported.
2. **But the experiment that would prove it was never run.** The two diagnostic configs
   (`pruned`, `pruned_dense_attrs`) are authored and correctly wired, but **no inference/scores
   exist** for either. The hypothesis is therefore **plausible-but-untested by artifact**.
3. **The premise is overstated.** The cited "regression" is a uniform ~2–4 pt drop in served
   `hit@k`, but **nDCG@20 — the scored/leaderboard metric — is essentially flat (−0.0005)**.
   This is a mild recall wobble, not a quality collapse.
4. **The proposed fix has a hole.** `dense_attrs` cleans `tag_list` but leaves the
   *highest-boost* pollutant — the full turn-intent sentence in `track_name` at boost **3.0** —
   untouched.

## 1–2. Config intent vs. reality — PASS (matches stated intent)

| Intent | Reality | Verdict |
|---|---|---|
| Qwen 0.6B lyrics-only in pruned | `pruned` keeps only `query_id: lyric` for qwen_0_6b (drops metadata/intent/attributes/attributes_enriched) | ✅ |
| Qwen 8B owns metadata + attributes | `pruned` keeps qwen_8b `metadata` + `attributes`; drops `intent` + `attributes_enriched` | ✅ |
| CLAP one text branch | `pruned` keeps only `clap_text … sonic_nl`; drops `sonic` + `sonic_nl_enriched` | ✅ |
| Style-reference anchors retained | `enable_similar_artist_anchors: true` still present (only a *comment* block was removed) | ✅ (earlier "pruned also drops style-ref" worry is **false**) |
| dense_attrs keeps V1 facts out of BM25 `tag_list` | `bm25_include_v1_attribute_facets: false` | ✅ |
| dense_attrs still feeds Qwen8 attributes | `attribute_query_source: "v1_attribute_facts"` + 8-facet allowlist | ✅ |
| (extra, beyond brief) dense_attrs also drops turn_intent tag clause | `bm25_include_turn_intent_tag_clause: false` | ⚠️ legitimate, but note it bundles a 2nd change |

## 3. Code wiring — PASS (flags are consumed, not inert)

All four new flags are read by the compiler (defaults reproduce current behavior):

- `bm25_include_v1_attribute_facets` (default `True`) → `compiler_v0plus.py:329`, gate at **:902-907**
  (`type=="tag"` + value ∈ V1 attribute facet keys → skip the `tag_list` clause).
- `bm25_include_turn_intent_tag_clause` (default `True`) → `:330`, gate at **:952-953**.
- `attribute_query_source` (default `"legacy_tags"`) → `:331`, used at **:1107**, validated **:1123**.
- `attribute_query_allowed_facets` (default empty) → `:332`, used at **:1085**.
- All four registered in the YAML allowlist (`compiler_v0plus_qu.py:1031-1034`).

The defaults mean `all_retrievers` == current polluting behavior; only `dense_attrs` flips them.
Clean design.

## 4. Targeted tests — PASS (20/20)

`pytest tests/test_v0plus_compiler*.py -k "bm25 or attribute_query or v1_attribute or routing_flags
or routing_boost or supported_dense_query_ids or call_counts or encoder_id or query_id or sonic_query"`
→ **20 passed, 111 deselected**. Includes the relevant coverage:

- `test_bm25_can_exclude_v1_attribute_facets_from_tag_list`
- `test_bm25_v1_attribute_filter_preserves_legacy_tags`
- `test_attributes_query_can_read_v1_attribute_facts_directly` / `..._can_filter_v1_attribute_facets`
- `test_v1_attribute_routing_flags_survive_yaml_allowlist`
- `test_v1_regression_variant_configs_reference_supported_dense_query_ids`

So the `dense_attrs` mechanism is correctly built and unit-tested. The only thing missing is **running it**.

## 5. Artifact comparison — BLOCKED (runs do not exist)

| Run dir | State | Usable? |
|---|---|---|
| `exp/smoke_satisfied_anchor_100sessions_20260608` (`all_retrievers`, current V1 vs old) | full inference + scores + trace | ✅ only complete run |
| `exp/v1_regression_pruned_100sessions_20260608` | **`subsets/` only** — no inference, no scores | ❌ |
| `exp/v1_regression_pruned_dense_attrs_100sessions_20260608` | **does not exist** | ❌ |

→ **Cannot compare pruned/dense_attrs vs current.** The headline experiment is unrun.

### The one real result (current V1 vs prior baseline, same 800 turns)

| Metric | OLD (prior baseline) | CURRENT (V1 bridge) | Δ |
|---|---:|---:|---:|
| **nDCG@20 (scored metric)** | 0.11209 | 0.11160 | **−0.0005 (flat)** |
| hit@20 | 0.26125 | 0.24000 | −0.0213 |
| hit@50 | 0.37250 | 0.33625 | −0.0363 |
| hit@100 | 0.43875 | 0.40625 | −0.0325 |
| hit@200 | 0.50375 | 0.47750 | −0.0263 |

Reading: a small, **uniform** decline in served `hit@k` at every depth; nDCG@20 unmoved.
Note the handoff's "deeper union improved (union@200 0.715→0.739)" refers to **branch-pool union**,
not the **served** list — on the served metric, recall fell at *every* depth. The widened pool
does not reach the final 20. (Identity of "OLD" per `smoke_comparison.json`: prior full-devset
predictions; treat as the pre-bridge baseline.)

## Query diff — the "bad usage" is visible turn-by-turn (current V1 trace, 800 turns)

Extracted from `branch_queries.bm25.clauses`:

- **100%** of turns inject the **entire `turn_intent` sentence** into `tag_list` (boost **1.5**).
- **100%** of turns inject that **same sentence** into `track_name` (boost **3.0**).
- mean **7.51** `tag_list` clauses/turn (max 17); **6,005** total.
- **19%** of all `tag_list` clauses are raw multi-word phrases (≥4 words / sentence punctuation /
  >40 chars) — i.e. not catalog tags.

Representative (turn 1, intent = *"80s American hardcore punk bands known for raw energy and short, intense songs."*):

```
tag_list <- "hardcore punk"            (plausible tag)
tag_list <- "American"                 (weak)
tag_list <- "raw energy"               (raw phrase, not a catalog tag)
tag_list <- "short, intense songs"     (raw phrase + punctuation)
tag_list <- "1980s"
tag_list <- "80s American hardcore punk bands known for raw energy and short, intense songs."  (FULL sentence @1.5)
track_name <- "80s American hardcore punk bands known for raw energy and short, intense songs." (FULL sentence @3.0)
```

This is direct confirmation that compiler **consumption** — not the dense encoders — is where raw
semantics leak into lexical BM25. The dense branches correctly receive the sentence as `query_text`.

## Gap in the proposed fix

`dense_attrs` removes (a) the turn_intent `tag_list` clause and (b) V1 attribute facts from
`tag_list`. It does **not** touch the unconditional full-sentence `track_name` clause at
`compiler_v0plus.py:951` — the **highest-boost (3.0)** pollutant, firing on 100% of turns.
Recommend a third gate (e.g. `bm25_include_turn_intent_trackname_clause`) so the dense_attrs
arm actually removes the worst offender.

Residual check (not done — needs a compile run): confirm on a sample that
`_v1_attribute_query_facet_keys` actually strips the *observed* raw phrases
(e.g. `"short, intense songs"`), not just the synthetic strings in unit tests.

## Bottom line for the main question

- **Did richer V1 hurt?** Marginally on recall, **not** on the scored metric (nDCG@20 flat).
- **Is consumption noisier?** Yes — verified mechanically and at 100%-of-turns scale.
- **Is noisier consumption the *cause* of the dip?** **Unproven.** The isolating runs don't exist.
  The change conflates state richness, BM25 pollution, and branch duplication; none is isolated yet.

## Recommended next steps (ranked)

1. **Actually run the two configs** (`pruned`, `pruned_dense_attrs`) on the same 800 turns and
   report nDCG@20 + hit@20 + per-branch recall. The harness is ready; this is the missing step.
2. **Add the `track_name` intent gate** before/with the dense_attrs run, or it leaves the
   boost-3.0 pollutant in place and under-measures the fix.
3. **Run `pruned` and `dense_attrs` as separate arms** (don't bundle) so branch-pruning vs
   tag-depollution are independently attributable.
4. Keep nDCG@20 as the headline; treat hit@20/union as diagnostics. The current "regression"
   framing overweights a flat-nDCG, small-hit dip.
5. Prior context worth heeding: lexical tag grounding was already tried and shelved on
   `claude/hopeful-nash-77dabf` (Issue #112, `tag_list` vocab found weak). Prefer "stop polluting
   lexical + lean on dense" over rebuilding a grounder to feed the weak channel.
