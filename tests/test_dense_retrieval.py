import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover
    torch = None

sys.modules.setdefault("bm25s", MagicMock())

import mcrs


class ListLikeConfig:
    def __init__(self, *values):
        self._values = list(values)

    def __iter__(self):
        return iter(self._values)

    def __getitem__(self, index):
        return self._values[index]

    def __len__(self):
        return len(self._values)


class RetrievalFactoryTests(unittest.TestCase):
    def test_bert_alias_preserves_legacy_defaults(self):
        try:
            from mcrs.retrieval_modules import load_retrieval_module
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional dependency missing: {exc}")

        with patch("mcrs.retrieval_modules.BERT_MODEL") as mock_bert_model:
            load_retrieval_module(
                retrieval_type="bert",
                dataset_name="tracks",
                track_split_types=["all_tracks"],
                corpus_types=["track_name"],
                cache_dir="./cache",
            )

            _, kwargs = mock_bert_model.call_args
            self.assertEqual(kwargs["model_name"], "bert-base-uncased")
            self.assertEqual(kwargs["pooling"], "mean")
            self.assertEqual(kwargs["max_length"], 128)
            self.assertEqual(kwargs["batch_size"], 32)
            self.assertEqual(kwargs["query_template"], "{query}")
            self.assertEqual(kwargs["document_template"], "{text}")

    def test_dense_transformer_selector_forwards_retrieval_config(self):
        try:
            from mcrs.retrieval_modules import load_retrieval_module
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional dependency missing: {exc}")

        with patch("mcrs.retrieval_modules.DENSE_TRANSFORMER_MODEL") as mock_dense_model:
            retrieval_config = {
                "model_name": "intfloat/e5-base-v2",
                "pooling": "mean",
                "query_template": "query: {query}",
                "document_template": "passage: {text}",
                "batch_size": 64,
                "max_length": 512,
                "padding_side": "right",
                "torch_dtype": "float32",
            }

            load_retrieval_module(
                retrieval_type="dense_transformer",
                dataset_name="tracks",
                track_split_types=["all_tracks"],
                corpus_types=["track_name", "artist_name"],
                cache_dir="./cache",
                retrieval_config=retrieval_config,
            )

            _, kwargs = mock_dense_model.call_args
            for key, value in retrieval_config.items():
                self.assertEqual(kwargs[key], value)


class CRSPlumbingTests(unittest.TestCase):
    def test_load_crs_baseline_forwards_retrieval_config(self):
        if torch is None:
            self.skipTest("torch is not installed")

        with patch("mcrs.crs_baseline.CRS_BASELINE") as mock_baseline:
            retrieval_config = {"model_name": "BAAI/bge-base-en-v1.5"}

            mcrs.load_crs_baseline(
                lm_type="dummy",
                retrieval_type="dense_transformer",
                retrieval_config=retrieval_config,
            )

            args, _ = mock_baseline.call_args
            self.assertEqual(args[-1], retrieval_config)


class DenseTransformerModelTests(unittest.TestCase):
    def test_pooling_modes_cover_mean_cls_and_last_token(self):
        if torch is None:
            self.skipTest("torch is not installed")
        from mcrs.retrieval_modules.bert import DENSE_TRANSFORMER_MODEL

        model = DENSE_TRANSFORMER_MODEL.__new__(DENSE_TRANSFORMER_MODEL)

        hidden_states = torch.tensor(
            [
                [[10.0, 0.0], [1.0, 1.0], [2.0, 2.0]],
                [[20.0, 0.0], [3.0, 3.0], [4.0, 4.0]],
            ]
        )
        attention_mask = torch.tensor([[1, 1, 0], [1, 1, 1]])

        mean_embeddings = model._pool_hidden_states(hidden_states, attention_mask, "mean")
        cls_embeddings = model._pool_hidden_states(hidden_states, attention_mask, "cls")
        last_embeddings = model._pool_hidden_states(hidden_states, attention_mask, "last_token")

        self.assertTrue(torch.equal(mean_embeddings, torch.tensor([[5.5, 0.5], [9.0, 7.0 / 3.0]])))
        self.assertTrue(torch.equal(cls_embeddings, torch.tensor([[10.0, 0.0], [20.0, 0.0]])))
        self.assertTrue(torch.equal(last_embeddings, torch.tensor([[1.0, 1.0], [4.0, 4.0]])))

    def test_build_index_serializes_list_like_configs(self):
        if torch is None:
            self.skipTest("torch is not installed")

        try:
            from mcrs.retrieval_modules.bert import DENSE_TRANSFORMER_MODEL
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional dependency missing: {exc}")

        with (
            patch("mcrs.retrieval_modules.bert.AutoModel.from_pretrained") as mock_model,
            patch("mcrs.retrieval_modules.bert.AutoTokenizer.from_pretrained") as mock_tokenizer,
            patch("mcrs.retrieval_modules.bert.concatenate_datasets") as mock_concatenate_datasets,
            patch("mcrs.retrieval_modules.bert.load_dataset") as mock_load_dataset,
            patch("mcrs.retrieval_modules.bert.DENSE_TRANSFORMER_MODEL._encode_texts") as mock_encode_texts,
        ):
            metadata_row = {
                "track_id": "track-1",
                "track_name": ["x"],
                "artist_name": ["y"],
            }
            mock_load_dataset.return_value = {"all_tracks": [metadata_row]}
            mock_concatenate_datasets.return_value = [metadata_row]
            mock_encode_texts.return_value = torch.zeros(1, 2)
            mock_tokenizer.return_value = MagicMock()
            mock_model.return_value = MagicMock()

            with tempfile.TemporaryDirectory() as temp_dir:
                model = DENSE_TRANSFORMER_MODEL(
                    dataset_name="tracks",
                    split_types=ListLikeConfig("all_tracks"),
                    corpus_types=ListLikeConfig("track_name", "artist_name"),
                    cache_dir=temp_dir,
                    model_name="intfloat/e5-base-v2",
                )

                config_path = Path(model.index_dir) / "config.json"
                self.assertTrue(config_path.exists())

    def test_index_dir_changes_when_model_or_templates_change(self):
        if torch is None:
            self.skipTest("torch is not installed")

        try:
            from mcrs.retrieval_modules.bert import DENSE_TRANSFORMER_MODEL
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional dependency missing: {exc}")

        with (
            patch("mcrs.retrieval_modules.bert.AutoModel.from_pretrained") as mock_model,
            patch("mcrs.retrieval_modules.bert.AutoTokenizer.from_pretrained") as mock_tokenizer,
            patch("mcrs.retrieval_modules.bert.concatenate_datasets") as mock_concatenate_datasets,
            patch("mcrs.retrieval_modules.bert.load_dataset") as mock_load_dataset,
            patch("mcrs.retrieval_modules.bert.DENSE_TRANSFORMER_MODEL._load_index") as mock_load_index,
            patch("mcrs.retrieval_modules.bert.DENSE_TRANSFORMER_MODEL.build_index") as mock_build_index,
        ):
            mock_load_dataset.return_value = {"all_tracks": [{"track_id": "track-1", "track_name": ["x"]}]}
            mock_concatenate_datasets.return_value = [{"track_id": "track-1", "track_name": ["x"]}]
            mock_load_index.return_value = (torch.zeros(1, 2), ["track-1"])
            mock_tokenizer.return_value = MagicMock()
            mock_model.return_value = MagicMock(to=MagicMock(return_value=MagicMock(eval=MagicMock())))

            with tempfile.TemporaryDirectory() as temp_dir:
                base = DENSE_TRANSFORMER_MODEL(
                    dataset_name="tracks",
                    split_types=["all_tracks"],
                    corpus_types=["track_name"],
                    cache_dir=temp_dir,
                    model_name="intfloat/e5-base-v2",
                    query_template="query: {query}",
                    document_template="passage: {text}",
                )
                variant = DENSE_TRANSFORMER_MODEL(
                    dataset_name="tracks",
                    split_types=["all_tracks"],
                    corpus_types=["track_name"],
                    cache_dir=temp_dir,
                    model_name="BAAI/bge-base-en-v1.5",
                    query_template="Represent this sentence for searching relevant passages: {query}",
                    document_template="{text}",
                )

            self.assertIn("intfloat__e5-base-v2", str(Path(base.index_dir)))
            self.assertIn("BAAI__bge-base-en-v1.5", str(Path(variant.index_dir)))
            self.assertNotEqual(base.index_dir, variant.index_dir)


class LiteLLMEmbeddingModelTests(unittest.TestCase):
    def test_build_index_resumes_from_cached_chunks(self):
        if torch is None:
            self.skipTest("torch is not installed")

        from mcrs.retrieval_modules.litellm_embedding import LITELLM_EMBEDDING_MODEL

        with tempfile.TemporaryDirectory() as temp_dir:
            model = LITELLM_EMBEDDING_MODEL.__new__(LITELLM_EMBEDDING_MODEL)
            model.index_dir = temp_dir
            model.batch_size = 2
            model.concurrency = 2
            model.model_name = "openrouter/qwen/qwen3-embedding-4b"
            model.corpus_types = ["track_name"]
            model.embedding_query_prefix = ""
            model.embedding_passage_prefix = ""
            model.dimensions = None
            model.max_retries = 0
            model.retry_base_seconds = 0
            model.metadata_dict = {
                "track-1": {"track_id": "track-1", "track_name": "one"},
                "track-2": {"track_id": "track-2", "track_name": "two"},
                "track-3": {"track_id": "track-3", "track_name": "three"},
            }
            model._render_document_text = lambda metadata: metadata["track_name"]

            chunk_dir = Path(temp_dir) / "chunks"
            chunk_dir.mkdir(parents=True)
            torch.save(torch.tensor([[1.0, 0.0], [0.0, 1.0]]), chunk_dir / "00000000.pt")
            (chunk_dir / "00000000.track_ids.json").write_text(
                json.dumps(["track-1", "track-2"]),
                encoding="utf-8",
            )

            calls = []

            def fake_embed_specs(specs, desc):
                calls.extend(spec["start"] for spec in specs)
                for spec in specs:
                    torch.save(torch.tensor([[0.5, 0.5]]), spec["embedding_path"])
                    Path(spec["track_ids_path"]).write_text(
                        json.dumps(spec["track_ids"]),
                        encoding="utf-8",
                    )

            model._embed_index_specs = fake_embed_specs

            model.build_index()

            self.assertEqual(calls, [2])
            embeddings = torch.load(Path(temp_dir) / "embeddings.pt")
            self.assertTrue(torch.equal(embeddings, torch.tensor([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])))
            track_ids = json.loads((Path(temp_dir) / "track_ids.json").read_text(encoding="utf-8"))
            self.assertEqual(track_ids, ["track-1", "track-2", "track-3"])


if __name__ == "__main__":
    unittest.main()
