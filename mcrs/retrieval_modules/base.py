RETRIEVER_REGISTRY: dict[str, type] = {}


def register_retriever(name: str):
    """Class decorator that registers a retriever under the given name.

    Usage::

        @register_retriever("my_retriever")
        class MyRetriever:
            def __init__(self, dataset_name, split_types, corpus_types,
                         cache_dir, formatter, **retrieval_config): ...
    """
    def decorator(cls):
        RETRIEVER_REGISTRY[name] = cls
        return cls
    return decorator
