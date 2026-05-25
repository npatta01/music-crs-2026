# LanceDB as v0+ Catalog Source of Truth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LanceDB the canonical source of v0+ catalog metadata, replace the duplicate in-memory `HFTalkPlayCatalog` for production reads, and fix the silent `release_date between` filter bug by typing dates end-to-end.

**Architecture:** Add a `LanceDbCatalog` implementing the existing `CompilerCatalog` Protocol; it opens the LanceDB table once at init and builds the same derived caches (`_artist_names`, `popularity_sorted`, vector dicts) `HFTalkPlayCatalog` does today, but sourced from LanceDB instead of the HF datasets. The Pydantic `HardFilter` schema gains explicit `start: date | None, end: date | None` fields with validators that expand year-only / year-month inputs. LanceDB stores `release_date` as `pyarrow.date32()` going forward.

**Tech Stack:** Python 3.10+, Pydantic v2, pyarrow, LanceDB, pytest. HuggingFace `datasets` only at index-build time (no longer at inference time).

---

## File Structure

| Path | Role | Status |
|---|---|---|
| `experiments/analysis/conversation_state_extraction_bakeoff/schema.py` | Pydantic schemas — `HardFilter` gets typed dates | modify |
| `mcrs/qu_modules/v0plus_catalog.py` | `CompilerCatalog` Protocol — `release_date_filter_mask` signature changes | modify |
| `mcrs/qu_modules/v0plus_catalog_hf.py` | HF-backed impl — update to match new Protocol; keep for tests | modify |
| `mcrs/qu_modules/v0plus_catalog_lance.py` | **NEW** — LanceDB-backed impl | create |
| `mcrs/qu_modules/compiler_v0plus.py` | Compiler — pass `HardFilter` through (not `op,value`) | modify |
| `mcrs/qu_modules/compiler_v0plus_qu.py` | QU wrapper — wire `LanceDbCatalog` in production | modify |
| `mcrs/lancedb/indexing.py` | Indexer — write `release_date` as `date32`, null on empty | modify |
| `tests/test_v0plus_schema.py` | **NEW** — HardFilter validators | create |
| `tests/test_v0plus_catalog_lance.py` | **NEW** — LanceDbCatalog against fixture table | create |
| `tests/test_v0plus_catalog_hf.py` | Update one filter-signature test | modify |
| `tests/test_v0plus_compiler.py` | Update tests that build HardFilter manually | modify |
| `tests/v0plus_fakes.py` | DictCatalog — update filter signature | modify |
| `scripts/build_lancedb_index.py` | CLI invokes indexing — verify date32 makes it through | verify |
| `modal/app.py` | Likely zero changes (catalog is loaded inside container; we just point at the LanceDB volume) | verify |
| `CLAUDE.md` | Note source-of-truth migration | modify |

---

### Task 1: Type the HardFilter schema

**Files:**
- Modify: `experiments/analysis/conversation_state_extraction_bakeoff/schema.py:65-75`
- Test: `tests/test_v0plus_schema.py` (create)

- [ ] **Step 1: Create the failing test file**

Create `tests/test_v0plus_schema.py`:

```python
"""HardFilter date typing and op-required-field validation."""
from datetime import date

import pytest
from pydantic import ValidationError

from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    HardFilter,
)


class TestHardFilterDateTypes:
    def test_between_accepts_full_iso_dates(self):
        f = HardFilter(field="release_date", op="between", start="2010-01-01", end="2013-12-31")
        assert f.start == date(2010, 1, 1)
        assert f.end == date(2013, 12, 31)

    def test_between_accepts_year_only_start(self):
        f = HardFilter(field="release_date", op="between", start="2010", end="2013")
        assert f.start == date(2010, 1, 1)
        assert f.end == date(2013, 12, 31)

    def test_between_accepts_year_month(self):
        f = HardFilter(field="release_date", op="between", start="2010-06", end="2013-08")
        assert f.start == date(2010, 6, 1)
        assert f.end == date(2013, 8, 31)

    def test_lt_accepts_year_only_end(self):
        f = HardFilter(field="release_date", op="<", end="2000")
        assert f.end == date(2000, 12, 31)

    def test_gt_accepts_year_only_start(self):
        f = HardFilter(field="release_date", op=">", start="2020")
        assert f.start == date(2020, 1, 1)


class TestHardFilterRequiredFields:
    def test_lt_requires_end(self):
        with pytest.raises(ValidationError, match="end"):
            HardFilter(field="release_date", op="<", start="2010-01-01")

    def test_gt_requires_start(self):
        with pytest.raises(ValidationError, match="start"):
            HardFilter(field="release_date", op=">", end="2010-01-01")

    def test_between_requires_both(self):
        with pytest.raises(ValidationError, match="start"):
            HardFilter(field="release_date", op="between", end="2010-12-31")
        with pytest.raises(ValidationError, match="end"):
            HardFilter(field="release_date", op="between", start="2010-01-01")

    def test_between_rejects_inverted_range(self):
        with pytest.raises(ValidationError, match="start.*end"):
            HardFilter(
                field="release_date", op="between",
                start="2015-01-01", end="2010-01-01",
            )

    def test_invalid_op_rejected(self):
        with pytest.raises(ValidationError):
            HardFilter(field="release_date", op="<=", end="2010-01-01")

    def test_malformed_date_rejected(self):
        with pytest.raises(ValidationError):
            HardFilter(field="release_date", op="<", end="January 2010")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_v0plus_schema.py -v`

Expected: errors / failures — `HardFilter` doesn't have `start`/`end` yet.

- [ ] **Step 3: Update `HardFilter` schema**

Replace `HardFilter` (currently at `schema.py:65-75`) with:

```python
from datetime import date as _date
from pydantic import field_validator, model_validator


class HardFilter(BaseModel):
    field: Literal["release_date"] = Field(
        ..., description="v0+ supports release_date only; other fields are deferred to v1."
    )
    op: Literal["<", ">", "between"]
    start: _date | None = Field(
        default=None,
        description=(
            "Start of the range (inclusive). Required for op='>' and op='between'. "
            "Emit as YYYY-MM-DD; 'YYYY' is expanded to YYYY-01-01, 'YYYY-MM' to YYYY-MM-01."
        ),
    )
    end: _date | None = Field(
        default=None,
        description=(
            "End of the range (inclusive). Required for op='<' and op='between'. "
            "Emit as YYYY-MM-DD; 'YYYY' is expanded to YYYY-12-31, 'YYYY-MM' to last day of month."
        ),
    )

    @field_validator("start", "end", mode="before")
    @classmethod
    def _coerce_partial(cls, v, info):
        if v is None or isinstance(v, _date):
            return v
        s = str(v).strip()
        if not s:
            return None
        is_end = info.field_name == "end"
        # Year-only: "2016" → 2016-01-01 (start) or 2016-12-31 (end)
        if len(s) == 4 and s.isdigit():
            return _date(int(s), 12, 31) if is_end else _date(int(s), 1, 1)
        # Year-month: "2016-06" → 2016-06-01 (start) or last-of-month (end)
        if len(s) == 7 and s[4] == "-" and s[:4].isdigit() and s[5:].isdigit():
            y, m = int(s[:4]), int(s[5:7])
            if is_end:
                # Last day: jump to next month, subtract a day
                from calendar import monthrange
                return _date(y, m, monthrange(y, m)[1])
            return _date(y, m, 1)
        # Otherwise let Pydantic try ISO parse (YYYY-MM-DD)
        return v

    @model_validator(mode="after")
    def _check_required_per_op(self):
        if self.op == "<":
            if self.end is None:
                raise ValueError("op='<' requires end")
        elif self.op == ">":
            if self.start is None:
                raise ValueError("op='>' requires start")
        elif self.op == "between":
            if self.start is None:
                raise ValueError("op='between' requires start")
            if self.end is None:
                raise ValueError("op='between' requires end")
            if self.start > self.end:
                raise ValueError(f"between: start ({self.start}) must be <= end ({self.end})")
        return self
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_v0plus_schema.py -v`

Expected: 12/12 PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.claude/worktrees/quirky-shaw-f102af
git add experiments/analysis/conversation_state_extraction_bakeoff/schema.py tests/test_v0plus_schema.py
git commit -m "feat(v0+): type HardFilter with start/end date fields and op-required-field validation"
```

---

### Task 2: Update CompilerCatalog Protocol + HF filter

**Files:**
- Modify: `mcrs/qu_modules/v0plus_catalog.py:72-84`
- Modify: `mcrs/qu_modules/v0plus_catalog_hf.py:281-304`
- Modify: `mcrs/qu_modules/compiler_v0plus.py:298-309`
- Modify: `tests/v0plus_fakes.py` (DictCatalog filter signature)
- Modify: `tests/test_v0plus_catalog_hf.py` (update one test)

- [ ] **Step 1: Update Protocol signature**

In `mcrs/qu_modules/v0plus_catalog.py`, replace the `release_date_filter_mask` declaration (lines 72-84) with:

```python
    def release_date_filter_mask(self, hf: "HardFilter") -> set[str]:
        """Return the set of track_ids passing the structured release_date filter.

        For op='<' includes tracks with release_date < hf.end.
        For op='>' includes tracks with release_date > hf.start.
        For op='between' includes tracks with hf.start <= release_date <= hf.end.
        Tracks with missing or unparseable release_date are excluded.
        """
        ...
```

Add at the top of the file, after the `from typing import` line:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
        HardFilter,
    )
```

- [ ] **Step 2: Write failing test for HF filter with new API**

In `tests/test_v0plus_catalog_hf.py`, find any existing test calling `release_date_filter_mask(op=..., value=...)` and update to use a `HardFilter`. If none exists, add at the end of the file:

```python
def test_release_date_filter_mask_between_yields_dated_tracks():
    from datetime import date
    from experiments.analysis.conversation_state_extraction_bakeoff.schema import HardFilter

    rows = [
        {"track_id": "t-old",  "release_date": "1985-06-12", "popularity": 0.0,
         "track_name": ["Old"], "artist_name": ["A"], "artist_id": ["a1"], "album_name": ["X"], "album_id": ["x1"], "tag_list": []},
        {"track_id": "t-in",   "release_date": "2010-03-08", "popularity": 0.0,
         "track_name": ["In"],  "artist_name": ["A"], "artist_id": ["a1"], "album_name": ["X"], "album_id": ["x1"], "tag_list": []},
        {"track_id": "t-new",  "release_date": "2020-01-01", "popularity": 0.0,
         "track_name": ["New"], "artist_name": ["A"], "artist_id": ["a1"], "album_name": ["X"], "album_id": ["x1"], "tag_list": []},
        {"track_id": "t-bad",  "release_date": "",           "popularity": 0.0,
         "track_name": ["Bad"], "artist_name": ["A"], "artist_id": ["a1"], "album_name": ["X"], "album_id": ["x1"], "tag_list": []},
    ]
    catalog = HFTalkPlayCatalog.from_rows(metadata_rows=rows, embedding_rows=[], vector_columns=[])
    hf = HardFilter(field="release_date", op="between", start="2000", end="2015")
    assert catalog.release_date_filter_mask(hf) == {"t-in"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_v0plus_catalog_hf.py::test_release_date_filter_mask_between_yields_dated_tracks -v`

Expected: FAIL — current impl takes `(op, value)`, not `hf`.

- [ ] **Step 4: Update HF catalog implementation**

In `mcrs/qu_modules/v0plus_catalog_hf.py`, replace the body of `release_date_filter_mask` (lines 281-304) with:

```python
    def release_date_filter_mask(self, hf) -> set[str]:
        from datetime import date as _date
        out: set[str] = set()
        for tid, meta in self.metadata.items():
            rd_str = meta.get("release_date")
            if not isinstance(rd_str, str) or not rd_str:
                continue
            try:
                rd = _date.fromisoformat(rd_str)
            except ValueError:
                continue
            if hf.op == "<" and rd < hf.end:
                out.add(tid)
            elif hf.op == ">" and rd > hf.start:
                out.add(tid)
            elif hf.op == "between" and hf.start <= rd <= hf.end:
                out.add(tid)
        return out
```

- [ ] **Step 5: Update DictCatalog (test fake)**

In `tests/v0plus_fakes.py`, find `release_date_filter_mask` and replace with:

```python
    def release_date_filter_mask(self, hf) -> set[str]:
        from datetime import date as _date
        out = set()
        for tid, meta in self._meta.items():
            rd_str = meta.get("release_date") or ""
            try:
                rd = _date.fromisoformat(rd_str)
            except ValueError:
                continue
            if hf.op == "<" and rd < hf.end:
                out.add(tid)
            elif hf.op == ">" and rd > hf.start:
                out.add(tid)
            elif hf.op == "between" and hf.start <= rd <= hf.end:
                out.add(tid)
        return out
```

(If `DictCatalog`'s internal dict name differs from `_meta`, adapt accordingly — read the file first.)

- [ ] **Step 6: Update compiler to pass HardFilter through**

In `mcrs/qu_modules/compiler_v0plus.py`, find the `_release_date_mask` method (around lines 298-309) and replace the body so it forwards the whole `HardFilter` instead of unpacking `op`/`value`:

```python
    def _release_date_mask(self, state) -> set[str]:
        masks: list[set[str]] = []
        for hf in state.hard_filters:
            if hf.field != "release_date":
                continue
            masks.append(self.catalog.release_date_filter_mask(hf))
        if not masks:
            return set(self.catalog.all_track_ids())
        result = masks[0]
        for m in masks[1:]:
            result &= m
        return result
```

- [ ] **Step 7: Run all v0+ tests to verify**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_v0plus_catalog_hf.py tests/test_v0plus_compiler.py tests/test_v0plus_compiler_qu.py tests/test_v0plus_resolver.py -v`

Expected: all pass. If `test_v0plus_compiler.py` constructs `HardFilter(... value=...)` directly anywhere, update those call sites to use `start`/`end`.

- [ ] **Step 8: Commit**

```bash
git add mcrs/qu_modules/v0plus_catalog.py mcrs/qu_modules/v0plus_catalog_hf.py mcrs/qu_modules/compiler_v0plus.py tests/v0plus_fakes.py tests/test_v0plus_catalog_hf.py tests/test_v0plus_compiler.py
git commit -m "refactor(v0+): pass HardFilter through release_date_filter_mask and parse dates with date.fromisoformat"
```

---

### Task 3: LanceDB indexing stores release_date as date32

**Files:**
- Modify: `mcrs/lancedb/indexing.py:118` (and the schema-derivation path nearby)
- Test: extend an existing indexing test (or add `tests/test_lancedb_indexing_release_date.py` if no suitable host)

- [ ] **Step 1: Write the failing test**

Create `tests/test_lancedb_indexing_release_date.py`:

```python
"""LanceDB indexing must store release_date as pyarrow date32, with empty -> null."""
import pyarrow as pa
import pytest
import lancedb

from mcrs.lancedb.indexing import build_track_record


def test_release_date_full_iso_becomes_date32():
    rec = build_track_record(
        metadata_row={"track_id": "t1", "release_date": "2016-03-08",
                      "track_name": ["X"], "artist_name": ["A"], "artist_id": ["a"],
                      "album_name": ["X"], "album_id": ["x"], "tag_list": [],
                      "popularity": 0.5, "duration": 200},
        embedding_row=None, vector_columns=[], embedding_field_names=[],
    )
    from datetime import date
    assert rec["release_date"] == date(2016, 3, 8)


def test_release_date_empty_becomes_none():
    rec = build_track_record(
        metadata_row={"track_id": "t2", "release_date": "",
                      "track_name": ["Y"], "artist_name": ["B"], "artist_id": ["b"],
                      "album_name": ["Y"], "album_id": ["y"], "tag_list": [],
                      "popularity": 0.5, "duration": 200},
        embedding_row=None, vector_columns=[], embedding_field_names=[],
    )
    assert rec["release_date"] is None


def test_lancedb_table_schema_has_date32_release_date(tmp_path):
    """End-to-end: write a tiny table via the indexing path and check the schema."""
    from mcrs.lancedb.indexing import write_track_records_to_lancedb

    rows = [
        {"track_id": "t1", "release_date": "2016-03-08", "track_name": ["X"],
         "artist_name": ["A"], "artist_id": ["a"], "album_name": ["X"],
         "album_id": ["x"], "tag_list": [], "popularity": 0.5, "duration": 200},
    ]
    write_track_records_to_lancedb(
        db_uri=str(tmp_path), table_name="t", rows=rows, embedding_rows=None,
        vector_columns=[], embedding_field_names=[],
    )
    db = lancedb.connect(str(tmp_path))
    tbl = db.open_table("t")
    schema = tbl.schema
    rd_field = schema.field("release_date")
    assert pa.types.is_date32(rd_field.type), f"expected date32, got {rd_field.type}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_lancedb_indexing_release_date.py -v`

Expected: FAIL — `build_track_record` may not be exported, may not produce dates, etc. If the function names differ, read `mcrs/lancedb/indexing.py` first and update the test imports to match the actual public API.

- [ ] **Step 3: Update indexing**

In `mcrs/lancedb/indexing.py`, find the line `record["release_date"] = str(metadata_row.get("release_date") or "")` (around line 118) and replace with:

```python
    raw_rd = metadata_row.get("release_date")
    record["release_date"] = _parse_iso_date(raw_rd) if raw_rd else None
```

Add at module top (after imports):

```python
def _parse_iso_date(value):
    """Parse YYYY-MM-DD into datetime.date; return None for empty / malformed."""
    from datetime import date as _date
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return _date.fromisoformat(s)
    except ValueError:
        return None
```

If the schema is built from `record.keys()` and pyarrow infers types from dicts, the date32 type will be inferred automatically from `datetime.date` values. If the indexer uses an explicit pyarrow schema, find that schema and change the `release_date` field from `pa.string()` to `pa.date32()`.

- [ ] **Step 4: Run tests to verify pass**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_lancedb_indexing_release_date.py -v`

Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add mcrs/lancedb/indexing.py tests/test_lancedb_indexing_release_date.py
git commit -m "feat(lancedb): store release_date as pyarrow date32; null on missing/malformed"
```

---

### Task 4: LanceDbCatalog implementation

**Files:**
- Create: `mcrs/qu_modules/v0plus_catalog_lance.py`
- Create: `tests/test_v0plus_catalog_lance.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_v0plus_catalog_lance.py`:

```python
"""LanceDbCatalog implements CompilerCatalog backed by a LanceDB table."""
from datetime import date

import pytest
import pyarrow as pa
import lancedb

from experiments.analysis.conversation_state_extraction_bakeoff.schema import HardFilter
from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog


def _build_fixture_table(path):
    db = lancedb.connect(str(path))
    rows = [
        {"track_id": "t-old",  "release_date": date(1985, 6, 12), "popularity": 0.1,
         "track_name": ["Old"],  "artist_name": ["Alice"], "artist_id": ["a1"],
         "album_name": ["A1"], "album_id": ["x1"], "tag_list": ["rock"]},
        {"track_id": "t-in",   "release_date": date(2010, 3, 8),  "popularity": 0.9,
         "track_name": ["In"],   "artist_name": ["Alice"], "artist_id": ["a1"],
         "album_name": ["A2"], "album_id": ["x2"], "tag_list": ["pop"]},
        {"track_id": "t-new",  "release_date": date(2020, 1, 1),  "popularity": 0.5,
         "track_name": ["New"],  "artist_name": ["Bob"],   "artist_id": ["b1"],
         "album_name": ["B1"], "album_id": ["y1"], "tag_list": ["jazz", "pop"]},
        {"track_id": "t-null", "release_date": None,             "popularity": 0.0,
         "track_name": ["Null"], "artist_name": ["Carol"], "artist_id": ["c1"],
         "album_name": ["C1"], "album_id": ["z1"], "tag_list": []},
    ]
    db.create_table("music_track_catalog", data=rows)
    return path


def test_loads_artist_and_track_names(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert set(cat.artist_names) == {"Alice", "Bob", "Carol"}
    assert set(cat.track_names) == {"Old", "In", "New", "Null"}


def test_artist_id_of_name(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.artist_id_of_name("Alice") == "a1"
    assert cat.artist_id_of_name("Missing") is None


def test_track_id_of_name(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.track_id_of_name("In") == "t-in"


def test_artist_id_of_track(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.artist_id_of("t-in") == "a1"
    assert cat.artist_id_of("missing") is None


def test_tracks_by_artist_id(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert set(cat.tracks_by_artist_id("a1")) == {"t-old", "t-in"}


def test_tag_list(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.tag_list("t-new") == ["jazz", "pop"]


def test_release_date_filter_between(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    hf = HardFilter(field="release_date", op="between", start="2000", end="2015")
    assert cat.release_date_filter_mask(hf) == {"t-in"}


def test_release_date_filter_lt(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    hf = HardFilter(field="release_date", op="<", end="2000-01-01")
    assert cat.release_date_filter_mask(hf) == {"t-old"}


def test_release_date_filter_gt(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    hf = HardFilter(field="release_date", op=">", start="2015-01-01")
    assert cat.release_date_filter_mask(hf) == {"t-new"}


def test_release_date_filter_excludes_null(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    hf = HardFilter(field="release_date", op="between", start="1900", end="2100")
    assert "t-null" not in cat.release_date_filter_mask(hf)


def test_all_track_ids(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert set(cat.all_track_ids()) == {"t-old", "t-in", "t-new", "t-null"}


def test_popularity_sorted(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.popularity_sorted_track_ids() == ["t-in", "t-new", "t-old", "t-null"]


def test_vector_returns_none_when_column_missing(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.vector("t-in", "nonexistent_field") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_v0plus_catalog_lance.py -v`

Expected: ImportError — `LanceDbCatalog` doesn't exist yet.

- [ ] **Step 3: Implement `LanceDbCatalog`**

Create `mcrs/qu_modules/v0plus_catalog_lance.py`:

```python
"""LanceDB-backed implementation of CompilerCatalog.

The HF-backed `HFTalkPlayCatalog` is retained for unit tests via its
`from_rows` constructor; production v0+ inference reads from this class so
LanceDB is the canonical metadata source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any

from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
    HardFilter,
)


def _first(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    s = str(value).strip()
    return s or None


def _list_of_str(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


@dataclass
class LanceDbCatalog:
    """CompilerCatalog backed by a LanceDB table opened at init time.

    Scans the table once at init and materializes the same derived caches
    `HFTalkPlayCatalog` builds (artist_names, popularity-sorted ids, etc.)
    so per-call lookups stay O(1).
    """

    db_uri: str
    table_name: str = "music_track_catalog"

    # Populated from the LanceDB scan in __post_init__
    _per_track: dict[str, dict[str, Any]] = field(default_factory=dict, init=False, repr=False)
    _artist_names: list[str] = field(default_factory=list, init=False, repr=False)
    _track_names: list[str] = field(default_factory=list, init=False, repr=False)
    _artist_name_to_id: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _track_name_to_id: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _tracks_by_artist_id: dict[str, list[str]] = field(default_factory=dict, init=False, repr=False)
    _popularity_sorted: list[str] = field(default_factory=list, init=False, repr=False)
    _release_date_by_tid: dict[str, _date] = field(default_factory=dict, init=False, repr=False)
    _vector_columns_available: set[str] = field(default_factory=set, init=False, repr=False)
    _table: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        import lancedb

        db = lancedb.connect(self.db_uri)
        self._table = db.open_table(self.table_name)
        # Identify which fixed_size_list columns look like vector columns
        for f in self._table.schema:
            if "embedding" in f.name and not f.name.startswith("has_"):
                self._vector_columns_available.add(f.name)

        # Pull just the columns we need for the derived caches; vectors are
        # fetched on demand to keep init cheap.
        wanted = [
            "track_id", "release_date", "popularity",
            "track_name", "artist_name", "artist_id", "album_name", "album_id",
            "tag_list",
        ]
        # Some columns may not exist in test fixtures; only request those that do.
        existing = {f.name for f in self._table.schema}
        wanted = [c for c in wanted if c in existing]

        df = self._table.to_pandas(columns=wanted)
        artist_seen: set[str] = set()
        track_seen: set[str] = set()
        for row in df.to_dict(orient="records"):
            tid = str(row["track_id"])
            self._per_track[tid] = row
            artist_name = _first(row.get("artist_name"))
            track_name = _first(row.get("track_name"))
            artist_id = _first(row.get("artist_id"))
            if artist_name and artist_name not in artist_seen:
                artist_seen.add(artist_name)
                self._artist_names.append(artist_name)
                if artist_id:
                    self._artist_name_to_id[artist_name] = artist_id
            if track_name and track_name not in track_seen:
                track_seen.add(track_name)
                self._track_names.append(track_name)
                self._track_name_to_id[track_name] = tid
            if artist_id:
                self._tracks_by_artist_id.setdefault(artist_id, []).append(tid)
            rd = row.get("release_date")
            if isinstance(rd, _date):
                self._release_date_by_tid[tid] = rd

        # Popularity-sorted (desc), stable on ties
        self._popularity_sorted = sorted(
            self._per_track.keys(),
            key=lambda t: (-(float(self._per_track[t].get("popularity") or 0.0)), t),
        )

    # ----- Protocol methods -----

    @property
    def artist_names(self) -> list[str]:
        return list(self._artist_names)

    @property
    def track_names(self) -> list[str]:
        return list(self._track_names)

    def artist_id_of_name(self, name: str) -> str | None:
        return self._artist_name_to_id.get(name)

    def track_id_of_name(self, name: str) -> str | None:
        return self._track_name_to_id.get(name)

    def artist_id_of(self, track_id: str) -> str | None:
        row = self._per_track.get(track_id)
        if row is None:
            return None
        return _first(row.get("artist_id"))

    def tracks_by_artist_id(self, artist_id: str) -> list[str]:
        return list(self._tracks_by_artist_id.get(artist_id, []))

    def tag_list(self, track_id: str) -> list[str]:
        row = self._per_track.get(track_id)
        if row is None:
            return []
        return _list_of_str(row.get("tag_list"))

    def vector(self, track_id: str, vector_field: str) -> list[float] | None:
        if vector_field not in self._vector_columns_available:
            return None
        df = self._table.to_pandas(columns=["track_id", vector_field],
                                   filter=f"track_id = '{track_id}'")
        if df.empty:
            return None
        v = df.iloc[0][vector_field]
        if v is None:
            return None
        return [float(x) for x in v]

    def metadata_vector(self, track_id: str) -> list[float] | None:
        return self.vector(track_id, "metadata_qwen3_embedding_0_6b")

    def release_date_filter_mask(self, hf: HardFilter) -> set[str]:
        out: set[str] = set()
        for tid, rd in self._release_date_by_tid.items():
            if hf.op == "<" and rd < hf.end:
                out.add(tid)
            elif hf.op == ">" and rd > hf.start:
                out.add(tid)
            elif hf.op == "between" and hf.start <= rd <= hf.end:
                out.add(tid)
        return out

    def all_track_ids(self) -> list[str]:
        return list(self._per_track.keys())

    def popularity_sorted_track_ids(self) -> list[str]:
        return list(self._popularity_sorted)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_v0plus_catalog_lance.py -v`

Expected: 12/12 PASS. If any fail because the LanceDB API differs (`.to_pandas(columns=...)` argument shape varies by version), adapt: e.g. use `.search().limit(0).to_pandas()` or `.to_arrow().to_pandas()`.

- [ ] **Step 5: Commit**

```bash
git add mcrs/qu_modules/v0plus_catalog_lance.py tests/test_v0plus_catalog_lance.py
git commit -m "feat(v0+): add LanceDbCatalog implementing CompilerCatalog from LanceDB table"
```

---

### Task 5: Vector access optimization

**Background:** the compiler calls `catalog.vector(tid, field)` many times per compile (centroid mixing across multiple played + anchor tracks). One round-trip to LanceDB per call would be slow. Either cache the whole vector column in memory at init (matches the HF catalog's behavior), or batch-fetch.

**Files:**
- Modify: `mcrs/qu_modules/v0plus_catalog_lance.py`
- Modify: `tests/test_v0plus_catalog_lance.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_v0plus_catalog_lance.py`:

```python
def test_vector_returns_loaded_embedding(tmp_path):
    # Build a fixture with a real vector column
    import lancedb, pyarrow as pa
    db = lancedb.connect(str(tmp_path))
    rows = [
        {"track_id": "t1",
         "metadata_qwen3_embedding_0_6b": [0.1] * 4,
         "has_metadata_qwen3_embedding_0_6b": True,
         "release_date": None, "popularity": 0.0,
         "track_name": ["X"], "artist_name": ["A"], "artist_id": ["a"],
         "album_name": ["Y"], "album_id": ["y"], "tag_list": []},
    ]
    schema = pa.schema([
        pa.field("track_id", pa.string()),
        pa.field("metadata_qwen3_embedding_0_6b", pa.list_(pa.float32(), 4)),
        pa.field("has_metadata_qwen3_embedding_0_6b", pa.bool_()),
        pa.field("release_date", pa.date32()),
        pa.field("popularity", pa.float64()),
        pa.field("track_name", pa.list_(pa.string())),
        pa.field("artist_name", pa.list_(pa.string())),
        pa.field("artist_id", pa.list_(pa.string())),
        pa.field("album_name", pa.list_(pa.string())),
        pa.field("album_id", pa.list_(pa.string())),
        pa.field("tag_list", pa.list_(pa.string())),
    ])
    db.create_table("music_track_catalog", data=rows, schema=schema)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog",
                        eager_vector_fields=["metadata_qwen3_embedding_0_6b"])
    v = cat.metadata_vector("t1")
    assert v == [pytest.approx(0.1)] * 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_v0plus_catalog_lance.py::test_vector_returns_loaded_embedding -v`

Expected: FAIL — `eager_vector_fields` param doesn't exist.

- [ ] **Step 3: Add eager-vector-loading to LanceDbCatalog**

In `mcrs/qu_modules/v0plus_catalog_lance.py`:

a. Add `eager_vector_fields: tuple[str, ...] = ()` to the dataclass fields (after `table_name`).

b. Add an instance cache:
```python
    _vectors: dict[str, dict[str, list[float]]] = field(default_factory=dict, init=False, repr=False)
```

c. In `__post_init__`, after the metadata scan, add:
```python
        for vf in self.eager_vector_fields:
            if vf not in self._vector_columns_available:
                continue
            vdf = self._table.to_pandas(columns=["track_id", f"has_{vf}", vf])
            store: dict[str, list[float]] = {}
            for row in vdf.to_dict(orient="records"):
                if not row.get(f"has_{vf}"):
                    continue
                v = row.get(vf)
                if v is None:
                    continue
                store[str(row["track_id"])] = [float(x) for x in v]
            self._vectors[vf] = store
```

d. Replace `vector(...)`:
```python
    def vector(self, track_id: str, vector_field: str) -> list[float] | None:
        cached = self._vectors.get(vector_field)
        if cached is not None:
            return cached.get(track_id)
        # Cold path: one-off query
        if vector_field not in self._vector_columns_available:
            return None
        df = self._table.to_pandas(columns=["track_id", vector_field],
                                   filter=f"track_id = '{track_id}'")
        if df.empty:
            return None
        v = df.iloc[0][vector_field]
        return None if v is None else [float(x) for x in v]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_v0plus_catalog_lance.py -v`

Expected: 13/13 PASS.

- [ ] **Step 5: Commit**

```bash
git add mcrs/qu_modules/v0plus_catalog_lance.py tests/test_v0plus_catalog_lance.py
git commit -m "feat(v0+): LanceDbCatalog can eager-load vector columns into memory at init"
```

---

### Task 6: Wire LanceDbCatalog into the v0+ QU

**Files:**
- Modify: `mcrs/qu_modules/compiler_v0plus_qu.py:367`

- [ ] **Step 1: Read the current catalog-construction site**

Run: `sed -n '360,400p' /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.claude/worktrees/quirky-shaw-f102af/mcrs/qu_modules/compiler_v0plus_qu.py`

Confirm the location of the `HFTalkPlayCatalog.from_hf(...)` call and the surrounding `qu_kwargs["catalog"]` shape.

- [ ] **Step 2: Update production catalog wiring**

In `compiler_v0plus_qu.py`, find the block that builds the catalog (around line 367). Replace it with a routing that prefers LanceDB when a `lancedb` block exists in `qu_kwargs`:

```python
    # ----- Catalog -----
    if "catalog" in _overrides:
        catalog = _overrides["catalog"]
    else:
        # Production: LanceDB-backed. Tests / synthetic data: pass an override.
        lance_cfg = dict(qu_kwargs.get("lancedb") or {})
        db_uri = os.environ.get("MCRS_LANCEDB_URI") or lance_cfg.get("db_uri")
        if not db_uri:
            raise ValueError(
                "v0+ catalog requires a LanceDB URI. Set qu_kwargs.lancedb.db_uri or "
                "MCRS_LANCEDB_URI."
            )
        from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog
        catalog = LanceDbCatalog(
            db_uri=db_uri,
            table_name=lance_cfg.get("table_name", "music_track_catalog"),
            eager_vector_fields=tuple(
                lance_cfg.get("eager_vector_fields") or (
                    "metadata_qwen3_embedding_0_6b",
                    "attributes_qwen3_embedding_0_6b",
                    "lyrics_qwen3_embedding_0_6b",
                )
            ),
        )
```

- [ ] **Step 3: Update YAML config (no schema change, just remove HF-catalog-specific keys)**

In `configs/v0plus_compiler_devset.yaml`, the existing `catalog:` block points at HF datasets:
```
metadata_dataset: ...
embeddings_dataset: ...
```
Leave those keys in (they're ignored by the new wiring) — but the canonical configuration is now under `lancedb:` which already exists. No edit required. Verify by reading the config and confirming `lancedb.db_uri` is set.

- [ ] **Step 4: Run all v0+ tests**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/test_v0plus_compiler_qu.py -v`

Expected: all pass. The tests use catalog overrides (`_overrides["catalog"]`), so they bypass the LanceDB path.

- [ ] **Step 5: Commit**

```bash
git add mcrs/qu_modules/compiler_v0plus_qu.py
git commit -m "feat(v0+): wire LanceDbCatalog as default for production compile; HFTalkPlayCatalog now test-only"
```

---

### Task 7: Reindex LanceDB locally and verify schema

**Files:**
- Run: `scripts/build_lancedb_index.py`

- [ ] **Step 1: Clear existing local LanceDB cache**

```bash
rm -rf /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.claude/worktrees/quirky-shaw-f102af/cache/lancedb
```

- [ ] **Step 2: Rebuild local LanceDB index**

Run from the worktree:
```bash
cd /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.claude/worktrees/quirky-shaw-f102af
/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python scripts/build_lancedb_index.py
```

Expected: ~5–10 minutes. No errors.

- [ ] **Step 3: Verify schema**

Run:
```bash
/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -c "
import lancedb
db = lancedb.connect('cache/lancedb')
tbl = db.open_table('music_track_catalog')
rd = tbl.schema.field('release_date')
print('release_date type:', rd.type)
assert str(rd.type) == 'date32[day]', f'expected date32, got {rd.type}'
print('row count:', tbl.count_rows())
"
```

Expected: `release_date type: date32[day]` and row count ~47000.

- [ ] **Step 4: Smoke test LanceDbCatalog against the real index**

Run:
```bash
/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -c "
from datetime import date
from experiments.analysis.conversation_state_extraction_bakeoff.schema import HardFilter
from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog
cat = LanceDbCatalog(db_uri='cache/lancedb', eager_vector_fields=())
hf = HardFilter(field='release_date', op='between', start='2016', end='2016')
m = cat.release_date_filter_mask(hf)
print(f'2016 mask size: {len(m)}')
assert 100 < len(m) < 5000, f'unexpected mask size: {len(m)}'
"
```

Expected: a non-zero mask size, in a reasonable range (a few hundred to a few thousand 2016-released tracks).

- [ ] **Step 5: Commit (no code changes — index lives outside git, but commit any pending fixes from the rebuild)**

If the rebuild surfaced any bug not covered by Task 3 tests, fix and commit with a clear message. Otherwise skip.

---

### Task 8: Reindex LanceDB on Modal and redeploy

**Files:**
- Run: `modal/app.py::upload_lancedb_index` (and the deploy step)

- [ ] **Step 1: Upload the rebuilt LanceDB index to Modal**

```bash
cd /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.claude/worktrees/quirky-shaw-f102af
/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/modal run modal/app.py::upload_lancedb_index --local-db-dir cache/lancedb --remote-dir lancedb
```

Expected: upload completes, Modal volume now has the date32 schema.

- [ ] **Step 2: Verify on Modal**

```bash
/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/modal volume ls music-crs-models lancedb 2>&1 | head
```

Expected: index files present.

- [ ] **Step 3: Redeploy the Modal app**

```bash
/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/modal deploy modal/app.py
```

Expected: `App deployed in <30s`.

- [ ] **Step 4: Re-run the 20-session test**

```bash
/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python run_experiment.py --backend modal --tid v0plus_compiler_devset --num_sessions 20 --batch_size 64
```

Run in background and monitor for `v0+ empty result` warnings.

Expected: zero `v0+ empty result: compiler returned 0 candidates` warnings. Throughput should match the prior cached run (~5 turns/sec).

- [ ] **Step 5: Verify the previously-failing sessions now return candidates**

```bash
/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python <<'PY'
import json
with open("exp/inference/devset/v0plus_compiler_devset.json") as f:
    data = json.load(f)
empties = [r for r in data if not r.get("predicted_track_ids")]
print(f"Empties: {len(empties)}/{len(data)}")
PY
```

Expected: 0 empties (or a much smaller number than 9; if any remain, they're from a different code path and need separate diagnosis).

- [ ] **Step 6: Commit any final adjustments**

```bash
git status
# If untracked or modified files remain after the run, commit them.
git commit -m "chore(v0+): rerun 20-session test post-migration; zero empties"
```

---

### Task 9: Cleanup — remove the HF production path

**Files:**
- Modify: `mcrs/qu_modules/v0plus_catalog_hf.py` (drop `from_hf`)
- Modify: `CLAUDE.md` (note the source-of-truth migration)

- [ ] **Step 1: Verify nothing in production calls `HFTalkPlayCatalog.from_hf`**

Run:
```bash
grep -rn "HFTalkPlayCatalog.from_hf\|HFTalkPlayCatalog(.*from_hf" \
    --include="*.py" \
    /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.claude/worktrees/quirky-shaw-f102af \
    | grep -v __pycache__ | grep -v ".venv"
```

Expected: no production hits. If only tests use it, proceed.

- [ ] **Step 2: Drop `from_hf` and rename the class to clarify test-only role**

In `mcrs/qu_modules/v0plus_catalog_hf.py`:
- Remove the `from_hf` classmethod
- Remove the `DEFAULT_METADATA_DATASET`, `DEFAULT_EMBEDDINGS_DATASET`, related module-level constants used only by `from_hf`
- Add a docstring note: "Test-only fake — production uses `LanceDbCatalog`."

- [ ] **Step 3: Run all tests**

Run: `cd .claude/worktrees/quirky-shaw-f102af && /Users/npatta01/data/projects/music-conversational-music-recomender-2026/.venv/bin/python -m pytest tests/ -q`

Expected: all pass.

- [ ] **Step 4: Update CLAUDE.md**

Add a single line to the v0+ section of `CLAUDE.md`:

> Catalog source of truth: LanceDB (`mcrs/qu_modules/v0plus_catalog_lance.py`). The HF-backed `HFTalkPlayCatalog` is retained only for unit tests.

- [ ] **Step 5: Commit**

```bash
git add mcrs/qu_modules/v0plus_catalog_hf.py CLAUDE.md
git commit -m "chore(v0+): drop HF-backed catalog from production path; LanceDB is the source of truth"
```

---

## Self-Review

**Spec coverage:**
- Pydantic schema with typed dates ✓ Task 1
- Update CompilerCatalog Protocol ✓ Task 2
- HF catalog filter adapts to new API ✓ Task 2
- LanceDB stores release_date as date32 ✓ Task 3
- LanceDbCatalog implementing the Protocol ✓ Tasks 4-5
- Wire LanceDbCatalog into v0+ QU ✓ Task 6
- Reindex local + Modal ✓ Tasks 7-8
- Verify the 9 empties are gone ✓ Task 8 Step 5
- Drop HFTalkPlayCatalog from production ✓ Task 9

**Placeholder scan:** None — all steps contain concrete code, file paths, and commands.

**Type consistency:**
- `HardFilter.start: date | None`, `HardFilter.end: date | None` — used consistently in Tasks 1, 2, 4
- `release_date_filter_mask(self, hf: HardFilter) -> set[str]` — same signature in Protocol (Task 2), HF impl (Task 2), DictCatalog (Task 2), LanceDbCatalog (Task 4)
- LanceDB column `release_date: pa.date32()` — Task 3 writes, Task 4 reads
- `eager_vector_fields: tuple[str, ...]` — defined Task 5, used Task 6

**Open risks called out in plan:**
- LanceDB Python API surface (`.to_pandas(columns=, filter=)`) may differ across versions. Task 4 Step 4 notes the adaptation path.
- If the indexing path uses an explicit pyarrow schema, Task 3 Step 3 calls out the override location.
- The eager-loading of three full embedding columns (3 × 1024 × 47k × 4 bytes ≈ 540 MB) matches the current HF catalog memory profile — no regression, but worth noting.
