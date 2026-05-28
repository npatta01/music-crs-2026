from datasets import load_dataset, concatenate_datasets

from mcrs.corpus_formatters import DefaultFormatter


class MusicCatalogDB:
    def __init__(self,
            dataset_name: str,
            split_types: list[str],
            corpus_types: list[str],
        ):
        metadata_dataset = load_dataset(dataset_name)
        metadata_concat_dataset = concatenate_datasets([metadata_dataset[split_type] for split_type in split_types])
        self.corpus_types = corpus_types
        self.metadata_dict = {item["track_id"]: item for item in metadata_concat_dataset}

    def id_to_metadata(self, track_id: str, use_semantic_id: bool = False):
        metadata = self.metadata_dict[track_id]
        formatter = DefaultFormatter()
        corpus_types = [
            "track_id",
            *(field for field in self.corpus_types if field != "track_id"),
        ]
        return formatter.format(metadata, corpus_types)
