# Phase 2 Response Template Findings

## Recommendation

Do not spend scarce Phase 2 submissions on response-only / explanation-only
variants while the Phase 2 scoreboard does not expose a response-quality score.
Use the best response template only as packaging for retrieval/ranking
candidates that are already worth one of the three daily submissions.

If a Phase 2 retrieval/ranking artifact needs responses, use
`phase2_best_qwen` / `top1_constraint_latest_state_qwen`.

Do not spend one of the three Phase 2 slots on the alt-model, close-fit,
concise-only, exact-language, or sanitized no-alt response-only variants unless
a visible response score appears or there is otherwise unused submission budget.

## Best Template

`phase2_best_qwen` is a stable alias for `top1_constraint_latest_state_qwen`.

```json
{
  "listener_goal": true,
  "preferred_language": true,
  "latest_user": true,
  "trace_state": true,
  "style": "Write 1-2 concise sentences about only the selected track. Prioritize the latest user request and extracted state over older conversation history. If the track is reasonably aligned, explain the fit with one specific supported reason. If it clearly conflicts with an explicit avoid/new-artist constraint, do not oversell it or blame the system; briefly frame the limitation and the closest supported reason.",
  "item_format": "xml",
  "max_tags": 10,
  "temperature": 0.0,
  "max_tokens": 512
}
```

The response should explain `predicted_track_ids[0]`, not the top-20 list and
not a safer unsubmitted candidate.

## Observed CodaBench Results

These are user-reported Blind-A CodaBench results from frozen-retrieval response
sweeps over `v10_lgbm_A.zip`. Retrieval metrics stay fixed for response-only
variants: `nDCG@20 = 0.4380`, `catalog_diversity = 0.0313`.

| Variant | LLM judge | Composite | Lexical diversity | Decision |
|---|---:|---:|---:|---|
| `top1_constraint_latest_state_qwen` | `4.7000` | `0.5799` | `0.8028` | Best response template. Use for packaging retrieval/ranking candidates. |
| `top1_constraint_honest_qwen` | `4.6500` | `0.5753` | `0.7937` | Historical hedge with fuller context. Do not submit response-only in Phase 2. |
| `top1_constraint_no_system_qwen` | `4.6000` | `0.5715` | `0.7935` | Historical hedge. Do not submit response-only in Phase 2. |
| `top1_constraint_no_system_no_overclaim_qwen` | `4.5500` | `0.5670` | `0.7859` | Hold. Too much overclaim suppression slightly hurt. |
| `top1_context_qwen` | `4.3000` | `0.5497` | `0.8008` | Hold. More context did not help. |
| `top1_constraint_close_fit_qwen` | `4.2500` | `0.5474` | `0.8152` | Avoid. "Closest fit" framing underperformed. |
| `top1_concise_qwen` | `4.2000` | `0.5440` | `0.8186` | Avoid. Same LLM score as original anchor. |
| `top1_concise_alt_model` | `3.9500` | `0.5245` | `0.8109` | Avoid. Offline proxy overvalued this. |
| `v10_lgbm_A.zip` anchor | `4.2000` | not captured here | not captured here | Baseline response style to beat. |

## Findings

- The hidden judge rewarded constraint-aware top-1 explanation more than pure
  concision.
- Qwen `openrouter/qwen/qwen3-30b-a3b-instruct-2507` was safer than the tested
  alternate generator model.
- Dropping older history and keeping latest request plus extracted state was the
  largest positive prompt change.
- The offline judge is useful for risk flags and case inspection, but its raw
  score is not calibrated to CodaBench. It over-ranked the alt-model variant.
- Follow-up questions are not needed. The response can end after explaining the
  recommended track.
- Avoid queue/list framing. The response is explaining the selected top track,
  not opening a top-20 playlist.

## Generation Command

Use this shape only after a Phase 2 retrieval/ranking candidate is already worth
submitting. It packages that candidate with the best observed response template:

```bash
python -m scripts.respgen.sweep \
  --base <phase2_base_prediction.zip> \
  --trace <phase2_trace_sidecar.jsonl> \
  --out-dir exp/respgen/sweeps/phase2_$(date +%Y%m%d_%H%M%S) \
  --variants phase2_best_qwen \
  --batch-size 16
```

Validate each output zip before submission:

```bash
python - <<'PY'
import json, zipfile
from pathlib import Path

out_dir = Path("<sweep_dir>")
for zip_path in sorted(out_dir.glob("*.zip")):
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.namelist() == ["prediction.json"], (zip_path, zf.namelist())
        rows = json.loads(zf.read("prediction.json"))
    assert rows
    for row in rows:
        assert {"session_id", "turn_number", "predicted_track_ids", "predicted_response"} <= set(row)
        assert len(row["predicted_track_ids"]) == 20
        assert isinstance(row["predicted_response"], str) and row["predicted_response"].strip()
print("zip validation ok")
PY
```

## Lower-Confidence Probes

Generated but not CodaBench-scored variants from the follow-up sweep:

- `top1_constraint_latest_state_no_goal_qwen`
- `top1_constraint_latest_state_soft_confident_qwen`
- `top1_constraint_latest_state_no_alt_qwen`
- `top1_constraint_latest_state_no_alt_no_overclaim_qwen`

Manual inspection found the no-alt family useful for reducing fake "I will find
another artist" promises, but these are not recommended Phase 2 submissions
while response quality is not visible on the scoreboard.
