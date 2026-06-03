# Session-Sharded Modal Inference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run parallel session-sharded Modal inference (devset and blindset) from `run_experiment.py` with run-id-scoped artifacts, then download → merge → (devset only) evaluate.

**Architecture:** `run_experiment.py` generates one run_id and calls a single generic `modal/app.py::run_inference_sharded(tid, eval_dataset, num_shards, run_id, ...)` that spawns N parallel workers (GPU/CPU chosen internally), each running the normal `run_inference_{devset,blindset}.py` on a contiguous session slice with `--output_suffix .run_{run_id}.shard_{k}`. Run-id naming makes stale shards harmless.

**Tech Stack:** Python 3.10, Modal, `datasets`, `omegaconf`, pytest. Spec: `docs/superpowers/specs/2026-06-03-session-sharded-modal-inference-design.md`.

**Invariant:** session partition → turn expansion → inference (never flatten turn rows then shard).

---

## File structure

- `run_inference_blindset.py` — add `--num_shards`/`--shard_id`/`--output_suffix` + session-slice logic (mirrors `run_inference_devset.py`).
- `scripts/merge_shard_results.py` — add `--run_id`; require full shard set; traces optional.
- `modal/download_results.py` — map run-scoped shard files to base tid; add `--run-id` filter.
- `modal/app.py` — generalize blindset workers for sharding; replace `run_inference_sharded` with generic split-oriented entrypoint.
- `run_experiment.py` — add `--num_shards`/`--run_id`, validation, `make_run_id`, `run_modal_sharded` orchestration.
- Tests: `tests/test_inference_scripts.py` (blindset shard slice), `tests/test_merge_shard_results.py` (new), `tests/test_modal_download_results.py` (run-scoped selection), `tests/test_run_experiment.py` (command construction, run_id, validation).

Run the suite with: `uv run pytest tests/test_run_experiment.py tests/test_merge_shard_results.py tests/test_modal_download_results.py tests/test_inference_scripts.py -v`

---

## Task 1: Blindset inference sharding

**Files:**
- Modify: `run_inference_blindset.py`
- Test: `tests/test_inference_scripts.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_inference_scripts.py`:

```python
def test_blindset_shard_slice_keeps_each_session_in_one_shard():
    """Contiguous index slicing partitions blindset sessions with no overlap."""
    total = 47
    seen = set()
    for num_shards in (1, 3, 5, 8):
        seen.clear()
        for shard_id in range(num_shards):
            start = (shard_id * total) // num_shards
            end = ((shard_id + 1) * total) // num_shards
            for i in range(start, end):
                assert i not in seen
                seen.add(i)
        assert seen == set(range(total))
```

Also add a behavior test that the script's `main` writes a suffixed file for one shard. Add at top of file if not present: `from types import SimpleNamespace`, `import json`, `from pathlib import Path`, `import importlib.util`, `import sys`. Then:

```python
def _load_blindset_module():
    module_path = Path(__file__).resolve().parents[1] / "run_inference_blindset.py"
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location("run_inference_blindset_mod", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_blindset_main_writes_suffixed_shard_output(tmp_path, monkeypatch):
    module = _load_blindset_module()

    rows = [
        {"user_id": f"u{i}", "session_id": f"s{i}",
         "conversations": [{"role": "user", "content": "hi", "turn_number": 1}]}
        for i in range(4)
    ]

    class _FakeDB(list):
        def select(self, idx):
            return _FakeDB(self[i] for i in idx)

    monkeypatch.setattr(module, "load_dataset", lambda *a, **k: _FakeDB(rows))

    class _FakeCRS:
        def batch_chat(self, batch):
            return [{"retrieval_items": ["t1"], "response": "r"} for _ in batch]

    monkeypatch.setattr(module, "load_crs_baseline", lambda **k: _FakeCRS())
    monkeypatch.setattr(module, "chat_history_parser", lambda conv, crs, tn: ([], "q"))

    cfg = {
        "lm_type": "dummy", "retrieval_type": "dummy", "item_db_name": "x",
        "user_db_name": "x", "track_split_types": [], "user_split_types": [],
        "corpus_types": [], "cache_dir": "./cache", "device": "cpu",
        "attn_implementation": "eager", "test_dataset_name": "x",
    }
    from omegaconf import OmegaConf
    monkeypatch.setattr(module.OmegaConf, "load", lambda p: OmegaConf.create(cfg))

    args = SimpleNamespace(
        tid="foo_blindset_A", eval_dataset="blindset_A", batch_size=2,
        exp_dir=str(tmp_path), clear_cache=False,
        num_shards=2, shard_id=0, output_suffix=".run_RID.shard_0",
    )
    module.main(args)

    out = tmp_path / "inference" / "blindset_A" / "foo_blindset_A.run_RID.shard_0.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert {r["session_id"] for r in data} == {"s0", "s1"}  # shard 0 of 2 over 4 sessions
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_inference_scripts.py::test_blindset_main_writes_suffixed_shard_output -v`
Expected: FAIL — `main` ignores `num_shards`/`output_suffix`, so the file is named `foo_blindset_A.json` (no suffix) and contains all 4 sessions.

- [ ] **Step 3: Add sharding to `run_inference_blindset.py`**

In `run_inference_blindset.py`, after `db = load_dataset(config.test_dataset_name, split="test")` (line 77), insert:

```python
    # Sharding kwargs were added later; programmatic callers (tests, Modal) may
    # not set them. Read defensively so the script stays backward-compatible.
    num_shards = getattr(args, "num_shards", 1)
    shard_id = getattr(args, "shard_id", 0)
    if num_shards > 1:
        if not (0 <= shard_id < num_shards):
            raise ValueError(
                f"shard_id={shard_id} out of range for num_shards={num_shards}"
            )
        # Each blindset row IS one session — contiguous index slicing partitions
        # the session list. Turn selection (last turn) happens below, after the
        # partition, so a session's turns never split across shards.
        total = len(db)
        start = (shard_id * total) // num_shards
        end = ((shard_id + 1) * total) // num_shards
        db = db.select(range(start, end))
        print(f"Shard {shard_id}/{num_shards}: {len(db)} sessions "
              f"(indices [{start}, {end}))")
```

Then change the output block (lines 108-110) to:

```python
    output_suffix = getattr(args, "output_suffix", "")
    os.makedirs(f"{args.exp_dir}/inference/{args.eval_dataset}", exist_ok=True)
    out_path = f"{args.exp_dir}/inference/{args.eval_dataset}/{args.tid}{output_suffix}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(inference_results, f, ensure_ascii=False)
```

Add these argparse arguments inside `if __name__ == "__main__":` (after the existing `--clear_cache` argument, before `args = parser.parse_args()`):

```python
    parser.add_argument(
        "--num_shards",
        type=int,
        default=1,
        help="Total number of shards. >1 enables sharded mode (must pair with --shard_id).",
    )
    parser.add_argument(
        "--shard_id",
        type=int,
        default=0,
        help="0-based shard index. Only this shard's slice of sessions is processed.",
    )
    parser.add_argument(
        "--output_suffix",
        type=str,
        default="",
        help="Optional suffix appended to the output filename "
             "(e.g. '.run_RID.shard_3' -> '{tid}.run_RID.shard_3.json').",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_inference_scripts.py -v -k "blindset"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add run_inference_blindset.py tests/test_inference_scripts.py
git commit -m "feat(blindset): session-sharded inference with output_suffix (#99)"
```

---

## Task 2: Run-id-scoped shard merge

**Files:**
- Modify: `scripts/merge_shard_results.py`
- Test: `tests/test_merge_shard_results.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_merge_shard_results.py`:

```python
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "merge_shard_results.py"
    spec = importlib.util.spec_from_file_location("merge_shard_results_mod", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(base: Path, name: str, rows: list[dict]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / name).write_text(json.dumps(rows), encoding="utf-8")


def _pred(session_id: str, turn: int) -> dict:
    return {"session_id": session_id, "turn_number": turn,
            "predicted_track_ids": ["t1"], "predicted_response": "r"}


def _trace(session_id: str, turn: int) -> dict:
    return {"session_id": session_id, "turn_number": turn, "trace": {"x": 1}}


def test_merge_run_scoped_devset_predictions_and_traces(tmp_path):
    module = _load_module()
    base = tmp_path / "inference" / "devset"
    rid = "20260603T074512Z-a3f91c"
    _write(base, f"foo_devset.run_{rid}.shard_0.json", [_pred("s0", 1)])
    _write(base, f"foo_devset.run_{rid}.shard_1.json", [_pred("s1", 1)])
    _write(base, f"foo_devset.run_{rid}.shard_0_trace.json", [_trace("s0", 1)])
    _write(base, f"foo_devset.run_{rid}.shard_1_trace.json", [_trace("s1", 1)])

    module.main([
        "--tid", "foo_devset", "--num_shards", "2", "--run_id", rid,
        "--split", "devset", "--exp-dir", str(tmp_path),
    ])

    preds = json.loads((base / "foo_devset.json").read_text())
    traces = json.loads((base / "foo_devset_trace.json").read_text())
    assert {r["session_id"] for r in preds} == {"s0", "s1"}
    assert {r["session_id"] for r in traces} == {"s0", "s1"}


def test_merge_requires_all_shards_for_run_id(tmp_path):
    module = _load_module()
    base = tmp_path / "inference" / "devset"
    rid = "20260603T074512Z-a3f91c"
    _write(base, f"foo_devset.run_{rid}.shard_0.json", [_pred("s0", 1)])
    # shard_1 deliberately missing

    with pytest.raises(FileNotFoundError, match="shard_1"):
        module.main([
            "--tid", "foo_devset", "--num_shards", "2", "--run_id", rid,
            "--split", "devset", "--exp-dir", str(tmp_path),
        ])


def test_merge_blindset_without_traces(tmp_path):
    module = _load_module()
    base = tmp_path / "inference" / "blindset_A"
    rid = "20260603T074512Z-a3f91c"
    _write(base, f"foo_blindset_A.run_{rid}.shard_0.json", [_pred("s0", 1)])
    _write(base, f"foo_blindset_A.run_{rid}.shard_1.json", [_pred("s1", 1)])
    # no trace shards

    module.main([
        "--tid", "foo_blindset_A", "--num_shards", "2", "--run_id", rid,
        "--split", "blindset_A", "--exp-dir", str(tmp_path),
    ])

    preds = json.loads((base / "foo_blindset_A.json").read_text())
    assert {r["session_id"] for r in preds} == {"s0", "s1"}
    assert not (base / "foo_blindset_A_trace.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_merge_shard_results.py -v`
Expected: FAIL — `main()` currently takes no argv and builds paths without `.run_{run_id}`; the run-scoped files are not found and `--run_id`/argv are unsupported.

- [ ] **Step 3: Update `scripts/merge_shard_results.py`**

Replace `_load_shards` and `main`, and add `_traces_present`, with:

```python
def _load_shards(
    base: Path, tid: str, run_scope: str, num_shards: int, kind: str
) -> list[tuple[int, Path, list[dict]]]:
    out = []
    for shard_id in range(num_shards):
        shard_path = base / f"{tid}{run_scope}.shard_{shard_id}{kind}.json"
        if not shard_path.exists():
            raise FileNotFoundError(f"Missing shard output: {shard_path}")
        with open(shard_path) as f:
            out.append((shard_id, shard_path, json.load(f)))
    return out


def _traces_present(base: Path, tid: str, run_scope: str, num_shards: int) -> bool:
    """True if every shard has a trace sidecar; False if none do.

    Devset writes a `_trace.json` per shard; blindset writes none. A partial
    set (some shards have traces, some don't) means a corrupt/incomplete run,
    so fail loudly rather than silently merging a subset.
    """
    paths = [base / f"{tid}{run_scope}.shard_{i}_trace.json" for i in range(num_shards)]
    present = [p for p in paths if p.exists()]
    if not present:
        return False
    if len(present) != num_shards:
        missing = [str(p) for p in paths if not p.exists()]
        raise FileNotFoundError(
            "Partial trace shards (some present, some missing): " + ", ".join(missing)
        )
    return True


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--tid", required=True, help="Experiment id (matches the shard prefix).")
    parser.add_argument("--num_shards", type=int, required=True)
    parser.add_argument(
        "--run_id",
        default=None,
        help="Run id scoping the shard files: {tid}.run_{run_id}.shard_N.json. "
             "Omit for legacy unscoped {tid}.shard_N.json files.",
    )
    parser.add_argument("--exp-dir", default="exp")
    parser.add_argument("--split", default="devset")
    args = parser.parse_args(argv)

    base = Path(args.exp_dir) / "inference" / args.split
    run_scope = f".run_{args.run_id}" if args.run_id else ""

    # Predictions are always required.
    pred_shards = _load_shards(base, args.tid, run_scope, args.num_shards, "")
    pred_rows = _merge(pred_shards, label="predictions", tid=args.tid)
    pred_out = base / f"{args.tid}.json"
    with open(pred_out, "w", encoding="utf-8") as f:
        json.dump(pred_rows, f, ensure_ascii=False)
    print(f"Wrote {pred_out}  ({len(pred_rows)} unique rows from {args.num_shards} shards)")

    # Traces are optional (devset has them; blindset does not).
    if _traces_present(base, args.tid, run_scope, args.num_shards):
        trace_shards = _load_shards(base, args.tid, run_scope, args.num_shards, "_trace")
        trace_rows = _merge(trace_shards, label="traces", tid=args.tid)
        trace_out = base / f"{args.tid}_trace.json"
        with open(trace_out, "w", encoding="utf-8") as f:
            json.dump(trace_rows, f, ensure_ascii=False)
        print(f"Wrote {trace_out}  ({len(trace_rows)} unique rows from {args.num_shards} shards)")
    else:
        print(f"No trace shards for {args.tid} — skipping trace merge.")
```

Note: keep the existing `_key` and `_merge` functions unchanged. Update the module docstring's usage line to include `--run_id`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_merge_shard_results.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add scripts/merge_shard_results.py tests/test_merge_shard_results.py
git commit -m "feat(merge): run-id-scoped shard merge, optional traces (#99)"
```

---

## Task 3: Run-scoped shard download selection

**Files:**
- Modify: `modal/download_results.py`
- Test: `tests/test_modal_download_results.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_modal_download_results.py`:

```python
def test_artifact_tid_strips_run_shard_suffix():
    module = _load_module()
    name = "inference/devset/foo_devset.run_20260603T074512Z-a3f91c.shard_0.json"
    assert module._artifact_kind(name) == "inference"
    assert module._artifact_tid(name, "inference") == "foo_devset"
    tname = "inference/devset/foo_devset.run_20260603T074512Z-a3f91c.shard_0_trace.json"
    assert module._artifact_kind(tname) == "trace"
    assert module._artifact_tid(tname, "trace") == "foo_devset"


def test_run_id_from_name_extracts_run_id():
    module = _load_module()
    name = "foo_devset.run_20260603T074512Z-a3f91c.shard_2.json"
    assert module._run_id_from_name(name) == "20260603T074512Z-a3f91c"
    assert module._run_id_from_name("foo_devset.json") is None


def test_select_artifacts_filters_by_run_id():
    module = _load_module()
    rid = "20260603T074512Z-a3f91c"
    arts = [
        module.RemoteArtifact(
            remote_path=f"inference/devset/foo_devset.run_{rid}.shard_0.json",
            size=1, kind="inference", split="devset", tid="foo_devset", run_id=rid,
        ),
        module.RemoteArtifact(
            remote_path="inference/devset/foo_devset.run_OLD.shard_0.json",
            size=1, kind="inference", split="devset", tid="foo_devset", run_id="OLD",
        ),
        module.RemoteArtifact(
            remote_path="inference/devset/foo_devset.json",
            size=1, kind="inference", split="devset", tid="foo_devset", run_id=None,
        ),
    ]
    selected = module.select_artifacts(
        arts, tids={"foo_devset"}, kinds={"inference"}, overwrite=True,
        out_dir=Path("/tmp/does-not-exist"), run_id=rid,
    )
    assert [a.remote_path for a in selected] == [
        f"inference/devset/foo_devset.run_{rid}.shard_0.json"
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_modal_download_results.py -v -k "run_id or run_shard"`
Expected: FAIL — `_artifact_tid` returns `foo_devset.run_....shard_0`; `_run_id_from_name` and the `run_id` field/param do not exist.

- [ ] **Step 3: Update `modal/download_results.py`**

Add `import re` near the top imports. After the `KIND_ALIASES` block, add:

```python
# Run-scoped shard suffix, e.g. ".run_20260603T074512Z-a3f91c.shard_0".
# run_id contains no dots (UTC stamp + hex, hyphen-joined); tids contain no dots.
_RUN_SHARD_RE = re.compile(r"\.run_(?P<run_id>[^.]+)\.shard_\d+$")


def _strip_run_shard(stem: str) -> str:
    return _RUN_SHARD_RE.sub("", stem)


def _run_id_from_name(name: str) -> str | None:
    stem = name
    for suffix in ("_trace.json", "_rewrite_audit.jsonl", "_rewrite_stats.json", ".json"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    match = _RUN_SHARD_RE.search(stem)
    return match.group("run_id") if match else None
```

Add a `run_id` field to `RemoteArtifact`:

```python
@dataclass(frozen=True)
class RemoteArtifact:
    remote_path: str
    size: int
    kind: str
    split: str | None
    tid: str | None
    run_id: str | None = None
```

Change `_artifact_tid` to strip the run-shard suffix from the recovered stem:

```python
def _artifact_tid(remote_path: str, kind: str) -> str | None:
    name = Path(remote_path).name
    if kind == "trace":
        for suffix in ("_trace.json", "_rewrite_audit.jsonl", "_rewrite_stats.json"):
            if name.endswith(suffix):
                return _strip_run_shard(name[: -len(suffix)])
    if kind in {"inference", "scores"} and name.endswith(".json"):
        return _strip_run_shard(name[:-5])
    return None
```

In `discover_remote_artifacts`, set `run_id=_run_id_from_name(Path(remote_path).name)` on the two `RemoteArtifact(...)` constructions under the inference loop and the score loop (ground-truth stays `run_id=None`, which is the default — leave it).

Update `select_artifacts` to accept and apply the filter:

```python
def select_artifacts(
    artifacts: list[RemoteArtifact],
    tids: set[str] | None,
    kinds: set[str],
    overwrite: bool,
    out_dir: Path,
    run_id: str | None = None,
) -> list[RemoteArtifact]:
    selected: list[RemoteArtifact] = []
    for artifact in artifacts:
        if artifact.kind not in kinds:
            continue
        if tids is not None and artifact.tid not in tids:
            continue
        if run_id is not None and artifact.run_id != run_id:
            continue
        local_path = out_dir / artifact.remote_path
        if not overwrite and local_path.exists():
            continue
        selected.append(artifact)
    return selected
```

Add the `--run-id` CLI arg in `build_parser` (after `--out-dir`):

```python
    parser.add_argument(
        "--run-id",
        default=None,
        help="Only download artifacts whose filename carries this run id "
             "(run-scoped shard files: {tid}.run_{run_id}.shard_N.json).",
    )
```

Thread it through `main`:

```python
    selected = select_artifacts(
        artifacts,
        tids=tids,
        kinds=kinds,
        overwrite=args.overwrite,
        out_dir=out_dir,
        run_id=args.run_id,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_modal_download_results.py -v`
Expected: PASS (new tests + all existing tests still green).

- [ ] **Step 5: Commit**

```bash
git add modal/download_results.py tests/test_modal_download_results.py
git commit -m "feat(download): run-scoped shard selection mapped to base tid (#99)"
```

---

## Task 4: Generic sharded Modal entrypoint

**Files:**
- Modify: `modal/app.py`

This task has no unit test (Modal entrypoints/workers run remotely and are not unit-testable in CI). Validation is the import smoke check in Step 3.

- [ ] **Step 1: Generalize the blindset workers for sharding**

In `modal/app.py`, replace `_inference_blindset` (lines ~308-320) with:

```python
def _inference_blindset(
    tid: str,
    batch_size: int,
    eval_dataset: str,
    num_shards: int = 1,
    shard_id: int = 0,
    output_suffix: str = "",
):
    import sys

    cmd = [
        sys.executable, "/app/run_inference_blindset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--eval_dataset", eval_dataset,
        "--exp_dir", EXP_DIR,
    ]
    if num_shards > 1:
        cmd += ["--num_shards", str(num_shards), "--shard_id", str(shard_id)]
    if output_suffix:
        cmd += ["--output_suffix", output_suffix]
    _run_inference_command(cmd)
    results_vol.commit()
    print(f"Results saved to volume: inference/{eval_dataset}/{tid}{output_suffix}.json")
```

Replace `_inference_blindset_cpu` (lines ~331-343) with the same body but the CPU command call:

```python
def _inference_blindset_cpu(
    tid: str,
    batch_size: int,
    eval_dataset: str,
    num_shards: int = 1,
    shard_id: int = 0,
    output_suffix: str = "",
):
    import sys

    cmd = [
        sys.executable, "/app/run_inference_blindset.py",
        "--tid", tid,
        "--batch_size", str(batch_size),
        "--eval_dataset", eval_dataset,
        "--exp_dir", EXP_DIR,
    ]
    if num_shards > 1:
        cmd += ["--num_shards", str(num_shards), "--shard_id", str(shard_id)]
    if output_suffix:
        cmd += ["--output_suffix", output_suffix]
    _run_inference_command(cmd, lancedb_uri=DEFAULT_REMOTE_LANCEDB_URI)
    results_vol.commit()
    print(f"CPU results saved to volume: inference/{eval_dataset}/{tid}{output_suffix}.json")
```

Keep the `@app.function(...)` decorators above each unchanged.

- [ ] **Step 2: Replace `run_inference_sharded` with the generic split-oriented entrypoint**

Replace the entire existing `run_inference_sharded` local entrypoint (lines ~751-826) with:

```python
@app.local_entrypoint()
def run_inference_sharded(
    tid: str = "v0plus_compiler_all_retrievers_devset",
    eval_dataset: str = "devset",
    num_shards: int = 4,
    run_id: str = "",
    batch_size: int = DEVSET_BATCH_SIZE,
    clear_cache: bool = False,
):
    """Run split-oriented, session-sharded inference across `num_shards` containers.

    Generic over split: `eval_dataset == "devset"` runs the devset worker,
    anything else runs the blindset worker. GPU vs CPU is chosen internally
    from the tid's config (`_tid_uses_cpu`) — callers never pick a resource
    flavor. Each shard writes run-scoped artifacts:
        inference/{split}/{tid}.run_{run_id}.shard_{i}.json
        inference/{split}/{tid}.run_{run_id}.shard_{i}_trace.json   (devset only)
    Merge them with scripts/merge_shard_results.py --run_id {run_id}.

    A non-empty `run_id` is required (the run_experiment.py wrapper always
    passes one) so stale shard files from prior runs can never be merged in.
    """
    if not run_id:
        raise ValueError(
            "run_inference_sharded requires a non-empty --run-id "
            "(run_experiment.py generates one automatically)."
        )

    is_devset = eval_dataset == "devset"
    uses_cpu = _tid_uses_cpu(tid)
    if is_devset:
        inference_fn = _inference_devset_cpu if uses_cpu else _inference_devset
    else:
        inference_fn = _inference_blindset_cpu if uses_cpu else _inference_blindset

    def _spawn(shard_id):
        output_suffix = f".run_{run_id}.shard_{shard_id}"
        if is_devset:
            return inference_fn.spawn(
                tid=tid,
                batch_size=batch_size,
                num_sessions=0,
                clear_cache=clear_cache,
                session_ids_json=None,
                num_shards=num_shards,
                shard_id=shard_id,
                output_suffix=output_suffix,
            )
        return inference_fn.spawn(
            tid=tid,
            batch_size=batch_size,
            eval_dataset=eval_dataset,
            num_shards=num_shards,
            shard_id=shard_id,
            output_suffix=output_suffix,
        )

    # Resilient join: a single shard failure must NOT raise out of this local
    # entrypoint mid-run, or Modal SIGINTs every other in-progress shard
    # container (a cascade that loses the whole run over one transient error).
    # Catch per shard, retry the failures once, then fail loudly if any remain.
    def _join(pairs):
        ok, bad = [], []
        for shard_id, call in pairs:
            try:
                call.get()
                ok.append(shard_id)
                print(f"Shard {shard_id} complete.")
            except Exception as e:  # noqa: BLE001 — report and continue, never abort the run
                bad.append(shard_id)
                print(f"Shard {shard_id} FAILED: {type(e).__name__}: {e}")
        return ok, bad

    calls = [(shard_id, _spawn(shard_id)) for shard_id in range(num_shards)]
    print(f"Spawned {num_shards} shards for {tid} (split={eval_dataset}, run_id={run_id}).")
    ok, failed = _join(calls)

    if failed:
        print(f"Retrying {len(failed)} failed shard(s): {failed}")
        ok2, failed = _join([(shard_id, _spawn(shard_id)) for shard_id in failed])
        ok += ok2

    if failed:
        # All spawns joined — no healthy shard is still in flight, so raising
        # here does not trigger the SIGINT cascade. Fail loudly: an incomplete
        # run must not exit 0, or a later merge silently picks up a partial set.
        raise RuntimeError(
            f"{len(failed)}/{num_shards} shard(s) failed after retry: {failed}. "
            f"Sharded run is INCOMPLETE — re-run with the same --num-shards and "
            f"--run-id {run_id} before merging."
        )
    print(
        f"All {num_shards} shards complete. Per-shard outputs: "
        f"inference/{eval_dataset}/{tid}.run_{run_id}.shard_{{0..{num_shards-1}}}.json"
    )
```

- [ ] **Step 3: Verify the module imports cleanly**

Run: `uv run python -c "import ast; ast.parse(open('modal/app.py').read()); print('parse-ok')"`
Expected: `parse-ok`.

Then, if Modal is configured locally, sanity-check the entrypoint signature is registered:
Run: `uv run python -c "import modal; print('modal-import-ok')"`
Expected: `modal-import-ok` (skip if Modal/credentials unavailable in CI — the ast parse is the required gate).

- [ ] **Step 4: Commit**

```bash
git add modal/app.py
git commit -m "feat(modal): generic split-oriented sharded entrypoint, blindset workers (#99)"
```

---

## Task 5: Wire sharding into `run_experiment.py` — args, validation, run_id

**Files:**
- Modify: `run_experiment.py`
- Test: `tests/test_run_experiment.py`

- [ ] **Step 1: Write the failing tests (args + run_id + validation)**

Add to `tests/test_run_experiment.py`:

```python
import re as _re


def test_make_run_id_format():
    module = _load_module("run_experiment_module_runid", "run_experiment.py")
    run_id = module.make_run_id()
    assert _re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{6}", run_id), run_id


def test_local_sharding_rejected(tmp_path):
    module = _load_module("run_experiment_module_local_shard_reject", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")
    module.PROJECT_ROOT = project_root
    with pytest.raises(ValueError, match="requires --backend modal"):
        module.main([
            "--backend", "local", "--tid", "foo_devset", "--num_shards", "5",
        ])


def test_num_sessions_with_sharding_rejected(tmp_path):
    module = _load_module("run_experiment_module_smoke_shard_reject", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")
    module.PROJECT_ROOT = project_root
    with pytest.raises(ValueError, match="cannot be combined with --num_shards"):
        module.main([
            "--backend", "modal", "--tid", "foo_devset",
            "--num_shards", "5", "--num_sessions", "3",
        ])


def test_run_id_requires_sharding(tmp_path):
    module = _load_module("run_experiment_module_runid_reject", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")
    module.PROJECT_ROOT = project_root
    with pytest.raises(ValueError, match="--run_id only applies"):
        module.main([
            "--backend", "modal", "--tid", "foo_devset", "--run_id", "abc",
        ])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_experiment.py -v -k "run_id or sharding or rejected"`
Expected: FAIL — `make_run_id` and the `--num_shards`/`--run_id` args/validation do not exist (argparse errors / AttributeError).

- [ ] **Step 3: Add args, `make_run_id`, and validation**

In `run_experiment.py`, add to the imports at the top (after `import sys`):

```python
import secrets
from datetime import datetime, timezone
```

In `build_parser`, add after the `--clear_cache` argument (before `return parser`):

```python
    parser.add_argument(
        "--num_shards",
        type=int,
        default=1,
        help="Number of parallel Modal shards. >1 runs session-sharded inference "
             "(Modal backend only). Default 1 = single run.",
    )
    parser.add_argument(
        "--run_id",
        default=None,
        help="Optional run id override for a sharded run (retry/resume). "
             "Generated automatically when omitted.",
    )
```

Add the `make_run_id` helper after `resolve_exp_dir` (or anywhere at module scope):

```python
def make_run_id() -> str:
    """One run id per sharded run: {UTC timestamp}-{short random hex}.

    Example: 20260603T074512Z-a3f91c. Scopes every shard's artifacts so a
    re-run never collides with — or silently merges — a prior run's files.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(3)}"
```

In `validate_args`, add at the end:

```python
    if args.num_shards < 1:
        raise ValueError("--num_shards must be >= 1.")
    if args.num_shards > 1 and args.backend != "modal":
        raise ValueError("--num_shards > 1 requires --backend modal.")
    if args.num_shards > 1 and args.num_sessions:
        raise ValueError(
            "--num_sessions cannot be combined with --num_shards > 1: "
            "run a smoke test (--num_sessions) OR a sharded full run, not both."
        )
    if args.run_id and args.num_shards == 1:
        raise ValueError(
            "--run_id only applies to sharded runs (--num_shards > 1)."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_experiment.py -v -k "run_id or sharding or rejected"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add run_experiment.py tests/test_run_experiment.py
git commit -m "feat(run_experiment): --num_shards, --run_id, validation, make_run_id (#99)"
```

---

## Task 6: Wire sharding into `run_experiment.py` — orchestration

**Files:**
- Modify: `run_experiment.py`
- Test: `tests/test_run_experiment.py`

- [ ] **Step 1: Write the failing tests (command construction)**

Add to `tests/test_run_experiment.py`:

```python
_FIXED_RUN_ID = "20260603T074512Z-a3f91c"


def test_modal_sharded_devset_builds_command_then_download_merge_eval(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_shard_devset", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")

    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(module, "make_run_id", lambda: _FIXED_RUN_ID)
    monkeypatch.setattr(
        module, "run_command",
        lambda cmd, cwd=None: commands.append(([str(p) for p in cmd], Path(cwd))),
    )

    exp = project_root / "artifacts"
    exit_code = module.main([
        "--backend", "modal", "--tid", "foo_devset",
        "--batch_size", "64", "--num_shards", "5", "--exp_dir", str(exp),
    ])

    assert exit_code == 0
    assert commands[0][0] == [
        "/usr/bin/python3", "-m", "modal", "run",
        "modal/app.py::run_inference_sharded",
        "--tid", "foo_devset",
        "--eval-dataset", "devset",
        "--num-shards", "5",
        "--run-id", _FIXED_RUN_ID,
        "--batch-size", "64",
    ]
    assert commands[1][0] == [
        "/usr/bin/python3", "modal/download_results.py",
        "--tid", "foo_devset",
        "--split", "devset",
        "--run-id", _FIXED_RUN_ID,
        "--out-dir", str(exp),
    ]
    assert commands[2][0] == [
        "/usr/bin/python3", "scripts/merge_shard_results.py",
        "--tid", "foo_devset",
        "--num_shards", "5",
        "--run_id", _FIXED_RUN_ID,
        "--split", "devset",
        "--exp-dir", str(exp),
    ]
    # devset → ground truth then evaluation
    assert commands[3][0][:2] == ["/usr/bin/python3", "evaluator/make_ground_truth.py"]
    assert commands[4][0][:2] == ["/usr/bin/python3", "evaluator/evaluate_devset.py"]


def test_modal_sharded_blindset_merges_without_eval(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_shard_blindset", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_blindset_A")

    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(module, "make_run_id", lambda: _FIXED_RUN_ID)
    monkeypatch.setattr(
        module, "run_command",
        lambda cmd, cwd=None: commands.append(([str(p) for p in cmd], Path(cwd))),
    )

    exp = project_root / "artifacts"
    exit_code = module.main([
        "--backend", "modal", "--tid", "foo_blindset_A",
        "--eval_dataset", "blindset_A", "--batch_size", "64",
        "--num_shards", "5", "--exp_dir", str(exp),
    ])

    assert exit_code == 0
    assert commands[0][0] == [
        "/usr/bin/python3", "-m", "modal", "run",
        "modal/app.py::run_inference_sharded",
        "--tid", "foo_blindset_A",
        "--eval-dataset", "blindset_A",
        "--num-shards", "5",
        "--run-id", _FIXED_RUN_ID,
        "--batch-size", "64",
    ]
    assert commands[1][0][:6] == [
        "/usr/bin/python3", "modal/download_results.py",
        "--tid", "foo_blindset_A", "--split", "blindset_A",
    ]
    assert commands[2][0][:2] == ["/usr/bin/python3", "scripts/merge_shard_results.py"]
    # No ground truth, no evaluation for blindset.
    assert len(commands) == 3


def test_modal_sharded_run_id_override_threaded(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_shard_override", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_blindset_A")

    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module, "run_command",
        lambda cmd, cwd=None: commands.append(([str(p) for p in cmd], Path(cwd))),
    )

    module.main([
        "--backend", "modal", "--tid", "foo_blindset_A",
        "--eval_dataset", "blindset_A", "--num_shards", "3",
        "--run_id", "CUSTOMID", "--exp_dir", str(project_root / "artifacts"),
    ])

    assert "--run-id" in commands[0][0]
    assert commands[0][0][commands[0][0].index("--run-id") + 1] == "CUSTOMID"
    assert commands[1][0][commands[1][0].index("--run-id") + 1] == "CUSTOMID"
    assert commands[2][0][commands[2][0].index("--run_id") + 1] == "CUSTOMID"


def test_modal_default_num_shards_uses_single_run_entrypoint(tmp_path, monkeypatch):
    module = _load_module("run_experiment_module_modal_single", "run_experiment.py")
    project_root = tmp_path / "repo"
    _write_config(project_root, "foo_devset")

    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(module, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(module.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(
        module, "run_command",
        lambda cmd, cwd=None: commands.append(([str(p) for p in cmd], Path(cwd))),
    )

    module.main([
        "--backend", "modal", "--tid", "foo_devset",
        "--exp_dir", str(project_root / "artifacts"),
    ])

    # Single-run path: the plain run_inference entrypoint, never the sharded one.
    assert commands[0][0][:5] == [
        "/usr/bin/python3", "-m", "modal", "run", "modal/app.py::run_inference",
    ]
    assert all("run_inference_sharded" not in part for part in commands[0][0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_experiment.py -v -k "sharded or single_run_entrypoint"`
Expected: FAIL — sharded path is not wired; `main` falls into the existing `run_modal` and builds `run_inference`/blindset commands, not `run_inference_sharded`.

- [ ] **Step 3: Add `run_modal_sharded` and route to it from `main`**

In `run_experiment.py`, add this function after `run_modal`:

```python
def run_modal_sharded(args: argparse.Namespace, split: str, exp_dir: Path) -> None:
    run_id = args.run_id or make_run_id()
    print(f"Sharded run_id: {run_id} (re-run with --run_id {run_id} to retry)")

    sharded_cmd = [
        sys.executable,
        "-m",
        "modal",
        "run",
        "modal/app.py::run_inference_sharded",
        "--tid",
        args.tid,
        "--eval-dataset",
        split,
        "--num-shards",
        str(args.num_shards),
        "--run-id",
        run_id,
        "--batch-size",
        str(args.batch_size),
    ]
    if args.clear_cache:
        sharded_cmd.append("--clear-cache")
    run_command(sharded_cmd, cwd=PROJECT_ROOT)

    run_command(
        [
            sys.executable,
            "modal/download_results.py",
            "--tid",
            args.tid,
            "--split",
            split,
            "--run-id",
            run_id,
            "--out-dir",
            str(exp_dir),
        ],
        cwd=PROJECT_ROOT,
    )
    run_command(
        [
            sys.executable,
            "scripts/merge_shard_results.py",
            "--tid",
            args.tid,
            "--num_shards",
            str(args.num_shards),
            "--run_id",
            run_id,
            "--split",
            split,
            "--exp-dir",
            str(exp_dir),
        ],
        cwd=PROJECT_ROOT,
    )

    if split == "devset":
        ensure_ground_truth(exp_dir)
        run_evaluation(args.tid, exp_dir, split)
```

Then change the dispatch in `main` from:

```python
    if args.backend == "local":
        run_local(args, split, exp_dir)
    else:
        run_modal(args, split, exp_dir)
```

to:

```python
    if args.backend == "local":
        run_local(args, split, exp_dir)
    elif args.num_shards > 1:
        run_modal_sharded(args, split, exp_dir)
    else:
        run_modal(args, split, exp_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_experiment.py -v`
Expected: PASS (new sharded tests + all existing run_experiment tests still green).

- [ ] **Step 5: Commit**

```bash
git add run_experiment.py tests/test_run_experiment.py
git commit -m "feat(run_experiment): orchestrate sharded modal runs (download/merge/eval) (#99)"
```

---

## Task 7: Docs + final verification

**Files:**
- Modify: `CLAUDE.md` (Run section), `docs/codebase/modules/infra.md`, `docs/codebase/modules/entrypoints.md`

- [ ] **Step 1: Update `CLAUDE.md` Run section**

In `CLAUDE.md`, under the `## Run` Modal example, add a sharded example after the existing Modal line:

```bash
# Sharded Modal run (parallel session shards; devset or blindset)
python run_experiment.py --backend modal --tid v0plus_compiler_all_retrievers_devset --batch_size 64 --num_shards 5
```

- [ ] **Step 2: Update infra/entrypoints docs**

In `docs/codebase/modules/infra.md`, update the `run_inference_sharded` row to the new signature `(tid, eval_dataset, num_shards, run_id, batch_size, clear_cache)`, note it is split-generic and run-id-scoped, and update the merge note to mention `--run_id` and that `run_experiment.py` now auto-merges. In `docs/codebase/modules/entrypoints.md`, note that `run_inference_blindset.py` now accepts `--num_shards`/`--shard_id`/`--output_suffix` (read with `getattr` defaults), mirroring the devset script. Keep edits factual and concise; match surrounding table/style.

- [ ] **Step 3: Run the full affected suite**

Run: `uv run pytest tests/test_run_experiment.py tests/test_merge_shard_results.py tests/test_modal_download_results.py tests/test_inference_scripts.py tests/test_v0plus_compiler_qu.py -v`
Expected: all PASS.

- [ ] **Step 4: Parse-check the Modal app once more**

Run: `uv run python -c "import ast; ast.parse(open('modal/app.py').read()); ast.parse(open('run_experiment.py').read()); print('parse-ok')"`
Expected: `parse-ok`.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/codebase/modules/infra.md docs/codebase/modules/entrypoints.md
git commit -m "docs: session-sharded modal inference UX + entrypoint signatures (#99)"
```

---

## Self-review notes

- **Spec coverage:** `--num_shards`/`--run_id` (T5), Modal+shards parallel (T4/T6), shard-by-session invariant (T1 blindset; devset already), single-run preserved (T6 dispatch + test), num_sessions+sharding rejected (T5), run_id form/override (T5/T6), run-scoped shard naming (T1/T4), merge requires full set + fails loud + canonical output (T2), download run-scoped selection (T3), devset evaluates / blindset stops (T6), no destructive cleanup (run-id naming only; no deletes added). All covered.
- **No placeholders:** every code step shows full code.
- **Type/name consistency:** `make_run_id`, `run_modal_sharded`, `_traces_present`, `_run_id_from_name`, `_strip_run_shard`, `RemoteArtifact.run_id`, `select_artifacts(..., run_id=...)`, entrypoint `run_inference_sharded(tid, eval_dataset, num_shards, run_id, batch_size, clear_cache)` are referenced consistently across tasks. Modal CLI flags use hyphens (`--eval-dataset`, `--num-shards`, `--run-id`, `--batch-size`); local script flags use underscores (`--num_shards`, `--run_id`) — matches existing conventions in `run_experiment.py` and the scripts.
