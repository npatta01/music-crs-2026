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
    if retrieval_type == "bm25":
        return BM25_MODEL(dataset_name, track_split_types, corpus_types, cache_dir, formatter=formatter)
    elif retrieval_type == "bert":
        return BERT_MODEL(
            dataset_name=dataset_name,
            split_types=track_split_types,
            corpus_types=corpus_types,
            cache_dir=cache_dir,
            model_name="bert-base-uncased",
            device=retrieval_config.get("device"),
            batch_size=32,
            max_length=128,
            pooling="mean",
            query_template="{query}",
            document_template="{text}",
            padding_side="right",
            torch_dtype="float32",
            formatter=formatter,
        )
    elif retrieval_type == "dense_transformer":
        return DENSE_TRANSFORMER_MODEL(
            dataset_name=dataset_name,
            split_types=track_split_types,
            corpus_types=corpus_types,
            cache_dir=cache_dir,
            formatter=formatter,
            **retrieval_config,
        )
    elif retrieval_type == "litellm_embedding":
        from .litellm_embedding import LITELLM_EMBEDDING_MODEL
        config = dict(retrieval_config)
        config.pop("device", None)
        return LITELLM_EMBEDDING_MODEL(
            dataset_name=dataset_name,
            split_types=track_split_types,
            corpus_types=corpus_types,
            cache_dir=cache_dir,
            formatter=formatter,
            **config,
        )
    elif retrieval_type == "milvus":
        from .milvus import MILVUS_MODEL

        return MILVUS_MODEL(
            dataset_name=dataset_name,
            split_types=track_split_types,
            corpus_types=corpus_types,
            cache_dir=cache_dir,
            formatter=formatter,
            retrieval_config=retrieval_config,
        )
    elif retrieval_type == "lancedb":
        from .lancedb import LANCEDB_MODEL

        return LANCEDB_MODEL(
            dataset_name=dataset_name,
            split_types=track_split_types,
            corpus_types=corpus_types,
            cache_dir=cache_dir,
            formatter=formatter,
            retrieval_config=retrieval_config,
        )
    else:
        raise ValueError(f"Unsupported retrieval type: {retrieval_type}")
