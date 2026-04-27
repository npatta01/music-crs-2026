from .bm25 import BM25_MODEL
from .bert import BERT_MODEL

def load_retrieval_module(
        retrieval_type: str,
        dataset_name: str,
        track_split_types: list[str],
        corpus_types: list[str] = ["track_name", "artist_name", "album_name"],
        cache_dir: str = "./cache",
        formatter=None,
    ):
    if retrieval_type == "bm25":
        return BM25_MODEL(dataset_name, track_split_types, corpus_types, cache_dir, formatter=formatter)
    elif retrieval_type == "bert":
        return BERT_MODEL(dataset_name, track_split_types, corpus_types, cache_dir, formatter=formatter)
    else:
        raise ValueError(f"Unsupported retrieval type: {retrieval_type}")
