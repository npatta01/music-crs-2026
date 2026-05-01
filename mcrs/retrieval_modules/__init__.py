from mcrs.retrieval_modules.base import RETRIEVER_REGISTRY

# Import each module so its @register_retriever decorators execute.
import mcrs.retrieval_modules.bert  # noqa: F401
import mcrs.retrieval_modules.bm25  # noqa: F401
import mcrs.retrieval_modules.litellm_embedding  # noqa: F401
import mcrs.retrieval_modules.precomputed_embedding  # noqa: F401

# Re-export concrete classes for callers that import them directly.
from .bm25 import BM25_MODEL
from .bert import BERT_MODEL, DENSE_TRANSFORMER_MODEL


def load_retrieval_module(
    retrieval_type: str,
    dataset_name: str,
    track_split_types: list[str],
    corpus_types: list[str] = ["track_name", "artist_name", "album_name"],
    cache_dir: str = "./cache",
    formatter=None,
    retrieval_config: dict | None = None,
):
    retrieval_config = retrieval_config or {}
    if retrieval_type not in RETRIEVER_REGISTRY:
        raise ValueError(
            f"Unknown retrieval type '{retrieval_type}'. "
            f"Available: {sorted(RETRIEVER_REGISTRY)}"
        )
    cls = RETRIEVER_REGISTRY[retrieval_type]
    return cls(
        dataset_name=dataset_name,
        split_types=track_split_types,
        corpus_types=corpus_types,
        cache_dir=cache_dir,
        formatter=formatter,
        **retrieval_config,
    )
