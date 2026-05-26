"""User-side embeddings catalog.

Loads the TalkPlayData User-Embeddings dataset into memory and provides
`vector(user_id, vector_field)` lookups. Used by the v0+ compiler for
centroid-only branches with `centroid_source="user"` (currently just
user_cf_bpr — the only user-side modality in the dataset).

Memory footprint:
- 9091 users across 3 splits (train 8591 + test_warm 371 + test_cold 129)
- cf_bpr: 128 float32 per user → ~4.4 MB resident

Loaded once at startup. Cache key is user_id → field → vector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


# Default dataset / splits / field-name mapping. Splits cover all user
# partitions: training users (history-rich) and the two challenge splits
# (test_warm = active users, test_cold = new users). Both warm and cold
# users have a precomputed cf_bpr vector — the user branch should fire
# uniformly across them.
DEFAULT_DATASET = "talkpl-ai/TalkPlayData-Challenge-User-Embeddings"
DEFAULT_SPLITS = ("train", "test_warm", "test_cold")

# HF column → LanceDB-safe column name (so the same `vector_field` string
# the compiler uses for track-side cf_bpr also indexes into the user store).
_HF_TO_FIELD = {
    "cf-bpr": "cf_bpr",
}


@dataclass
class UserEmbeddings:
    """In-memory user_id → field → vector store.

    Built from one or more dataset splits at init. Subsequent lookups are
    plain dict accesses — no HF / network calls on the hot path."""

    dataset_name: str = DEFAULT_DATASET
    splits: tuple[str, ...] = DEFAULT_SPLITS

    _vectors: dict[str, dict[str, list[float]]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        from datasets import load_dataset

        for split in self.splits:
            ds = load_dataset(self.dataset_name, split=split)
            for row in ds:
                uid = row.get("user_id")
                if not uid:
                    continue
                for hf_col, val in row.items():
                    if hf_col == "user_id":
                        continue
                    field_name = _HF_TO_FIELD.get(hf_col)
                    if field_name is None:
                        # Unknown column — preserve sanitized name for forward-compat
                        field_name = hf_col.replace("-", "_").replace(".", "_")
                    if val is None:
                        continue
                    vec = [float(x) for x in val]
                    if not vec:
                        continue
                    self._vectors.setdefault(field_name, {})[str(uid)] = vec

    # ----- Protocol -----

    def vector(self, user_id: str, vector_field: str) -> list[float] | None:
        store = self._vectors.get(vector_field)
        if store is None:
            return None
        return store.get(user_id)

    @property
    def available_fields(self) -> Iterable[str]:
        return tuple(self._vectors.keys())

    def user_count(self, vector_field: str) -> int:
        store = self._vectors.get(vector_field)
        return len(store) if store else 0

    # ----- Test/synthetic-data constructor -----

    @classmethod
    def from_dict(cls, vectors: dict[str, dict[str, list[float]]]) -> "UserEmbeddings":
        """Build a UserEmbeddings from an in-memory dict (no HF call). Used
        by tests to inject fake data. Shape: {vector_field: {user_id: vec}}."""
        inst = cls.__new__(cls)
        inst.dataset_name = "<from_dict>"
        inst.splits = ()
        inst._vectors = {field: dict(by_uid) for field, by_uid in vectors.items()}
        return inst
