---
name: download-artifacts
description: Use when you need to pull experiment predictions, rewrite traces, scores, or ground-truth artifacts from the Modal results volume into the local repo.
---

# Music CRS: Download Modal Artifacts

Use this skill when the user wants local copies of artifacts that were produced on Modal.

**Announce at start:** "I'm using the download-artifacts skill to sync Modal artifacts locally."

## Default behavior

Download into `evaluator/exp` so the evaluator can use the files immediately.

```bash
python modal/download_results.py --out-dir evaluator/exp
```

This syncs all missing remote artifacts by default, including:

- `inference/<split>/<tid>.json`
- `inference/<split>/<tid>_rewrite_audit.jsonl`
- `inference/<split>/<tid>_rewrite_stats.json`
- `scores/<split>/<tid>.json`
- `ground_truth/...`

## Common cases

### One specific run

```bash
python modal/download_results.py --tid {tid} --out-dir evaluator/exp
```

### Preview before downloading

```bash
python modal/download_results.py --dry-run --verbose --out-dir evaluator/exp
```

### Only one split

```bash
python modal/download_results.py --split devset --out-dir evaluator/exp
```

### Only scores

```bash
python modal/download_results.py --kind scores --out-dir evaluator/exp
```

### Batch of tids from a file

```bash
python modal/download_results.py --tid-file {path_to_tid_file} --out-dir evaluator/exp
```

## Notes

- The downloader skips files that already exist locally unless `--overwrite` is passed.
- Remote `scores/` or `ground_truth/` directories may not exist yet; that is not an error.
- If the user asks where the files landed, report the concrete paths under `evaluator/exp`.
