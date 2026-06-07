# State V1 Retriever Matrix Modal Summary

Focused replay over the 56-turn state gap pack with saved V1 extraction output.
The goal was candidate-generation recall, especially branch union@20 and
union@50, before spending on a full devset run.

The reproducible input is the tracked `state_experiment_pack.json` plus the
focused sample list in `state_role_v2_pack56_sample_ids.txt`.

## Runs

| Run | Artifact | Notes |
|---|---|---|
| CLAP + centroid | `state_v1_matrix_modal_clap_centroid56.json` | Tests natural-language audio/style anchors plus centroid branches. |
| Qwen-8B query templates | `state_v1_matrix_modal_qwen8_56.json` | Tests metadata, intent, attributes, and attributes-enriched templates against 8B embedding fields. |
| Combined candidate recall | `state_v1_matrix_modal_all_candidate56.json` | Tests lookup, Qwen 0.6B/8B, CLAP, similar-artist anchors, and centroid branches together. |

## Summary

| Variant | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 |
|---|---:|---:|---:|---:|---:|---:|
| official trace baseline | 0.196 | n/a | 0.554 | 0.554 inferred | 0.554 | 1.000 |
| `clap_centroid` | 0.304 | 0.357 | 0.446 | 0.500 | 0.571 | 0.696 |
| `qwen8_metadata` | 0.268 | 0.286 | 0.375 | 0.446 | 0.571 | 0.679 |
| `qwen8_metadata_intent` | 0.286 | 0.339 | 0.393 | 0.482 | 0.571 | 0.643 |
| `qwen8_attributes` | 0.268 | 0.286 | 0.321 | 0.393 | 0.518 | 0.571 |
| `qwen8_attributes_enriched` | 0.268 | 0.286 | 0.321 | 0.393 | 0.518 | 0.571 |
| `qwen8_intent_attr_enriched` | 0.304 | 0.357 | 0.411 | 0.500 | 0.625 | 0.679 |
| `all_candidate_recall` | 0.321 | 0.429 | 0.554 | 0.625 | 0.732 | 0.839 |

## Read

Single dense branches improved final placement on this focused pack, but did
not beat the official trace at union@20. The combined candidate set was the
first measured candidate-generation win: it tied official union@20, improved
inferred union@50 from 0.554 to 0.625, and improved union@100 from 0.554 to
0.732.

The prior Qwen-8B Modal failure was a matrix harness bug. The harness was
reading YAML directly, which left the OmegaConf env placeholder and logical
`vllm_endpoint` unresolved. The matrix now resolves config through OmegaConf and
uses the same vLLM endpoint resolver as `run_inference_devset.py`.

## Decision

Keep the alternate state-consuming query templates in the canonical devset and
blindset configs:

- Qwen metadata `intent`
- Qwen `attributes_enriched`
- CLAP `sonic_nl`
- CLAP `sonic_nl_enriched`

This is still a focused-pack result. A full devset Modal run should be the next
gate before claiming leaderboard improvement.
