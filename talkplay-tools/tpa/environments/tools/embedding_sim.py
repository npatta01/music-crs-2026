"""Embedding-based retrieval utilities for text, audio, image, and CF modalities."""
import os
import json
import torch
import numpy as np
from tpa.environments.tools.models.qwen3_embedding import Qwen3Embedding
from tpa.environments.tools.models.clap import CLAP
from tpa.environments.tools.models.siglip2 import SigLIP2
from tpa.environments.tools.models.cf import CollaborativeFiltering
from tpa.environments.tools.utils import entity_str

class EmbeddingTool:
    """Load embedding models and vector DB, and perform similarity search."""
    def __init__(
        self,
        cache_dir="./cache",
        device="cuda",
        dtype=torch.bfloat16,
        enabled_retrievers=None,
        enabled_corpora=None,
    ):
        self.cache_dir = cache_dir
        self.device = device
        self.dtype = dtype
        self.enabled_retrievers = tuple(enabled_retrievers or ("text", "audio", "image", "cf"))
        self.enabled_corpora = tuple(enabled_corpora or ("metadata", "lyrics", "attributes", "audio", "image", "cf"))
        self.retriever = {}
        if "text" in self.enabled_retrievers:
            self.retriever["text"] = Qwen3Embedding(device=device, dtype=dtype)
        if "audio" in self.enabled_retrievers:
            self.retriever["audio"] = CLAP(device=device, dtype=dtype)
        if "image" in self.enabled_retrievers:
            self.retriever["image"] = SigLIP2(device=device, dtype=dtype)
        if "cf" in self.enabled_retrievers:
            self.retriever["cf"] = CollaborativeFiltering(device=device, dtype=dtype)
        self.vector_db = self.load_model()
        self.vector_db = {
            modality: values
            for modality, values in self.vector_db.items()
            if modality in self.enabled_corpora and values
        }
        self.modality_list = list(self.vector_db.keys())
        (
            self.original_matrices,
            self.original_id_lists,
            self.original_index_maps,
        ) = self._build_matrices_from_vector_db()
        self._init_track_pool() # init

    def _init_track_pool(self):
        """Reset in-memory matrices and id lists to the full corpus."""
        self.current_matrices = self.original_matrices.copy()
        self.current_id_lists = self.original_id_lists.copy()

    def _update_track_pool(self, track_pool: list[str]):
        """Restrict search to a provided candidate set of track ids.

        Args:
            track_pool (list[str]): Allowed track ids.
        """
        current_index = {}
        for modality in self.modality_list:
            index_map = self.original_index_maps[modality]
            indices = [index_map[track_id] for track_id in track_pool if track_id in index_map]
            current_index[modality] = indices
        self.current_matrices = self.original_matrices.copy()
        self.current_id_lists = self.original_id_lists.copy()
        for modality in self.modality_list:
            self.current_matrices[modality] = self.original_matrices[modality][current_index[modality]]
            self.current_id_lists[modality] = [self.original_id_lists[modality][i] for i in current_index[modality]]

    def load_model(self):
        """Load vector database from disk.

        Returns:
            dict | None: Modality to id→embedding mapping, or None if missing.
        """
        path = os.path.join(self.cache_dir, "encoder", "vector_db.pt")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing embedding cache: {path}")
        vector_db = torch.load(path, map_location="cpu")
        return vector_db

    def _build_matrices_from_vector_db(self):
        """Construct stacked matrices and id lists from the vector DB.

        Returns:
            tuple[dict, dict, dict]: modality→matrix, modality→id_list, and
            modality→track_id_to_index mappings.
        """
        matrices = {}
        id_lists = {}
        index_maps = {}
        for modality, id_to_vec in self.vector_db.items():
            if not id_to_vec:
                continue
            ids, vecs = [], []
            for track_id, emb in id_to_vec.items():
                emb = emb.detach().cpu().squeeze()
                if emb.ndim != 1:
                    emb = emb.view(-1)
                ids.append(track_id)
                vecs.append(emb)
            id_lists[modality] = ids
            index_maps[modality] = {track_id: idx for idx, track_id in enumerate(ids)}
            matrices[modality] = torch.stack(vecs, dim=0)
        return matrices, id_lists, index_maps

    @torch.no_grad()
    def build_index(self):
        """Build vector DB from cached metadata and encoders, then persist to disk."""
        test_metadata = json.load(open(os.path.join(self.cache_dir, "metadata", "test_metadata.json"), "r"))
        metadata_db, lyrics_db, attributes_db, audio_db, image_db, cf_db = {}, {}, {}, {}, {}, {}
        for track_id, meta_info in test_metadata.items():
            audio_path = f"/workspace/dataset/spotify/audio/{track_id[0]}/{track_id[1]}/{track_id}.mp3"
            image_path = f"/workspace/dataset/spotify/images/{track_id[0]}/{track_id[1]}/{track_id}.jpg"
            if "text" in self.retriever:
                if "metadata" in self.enabled_corpora:
                    metadata_db[track_id] = self.retriever["text"].get_text_embedding(entity_str(meta_info)).detach().cpu()
                if "lyrics" in self.enabled_corpora:
                    lyrics_db[track_id] = self.retriever["text"].get_text_embedding(meta_info['lyrics']).detach().cpu()
                if "attributes" in self.enabled_corpora:
                    attributes_db[track_id] = self.retriever["text"].get_text_embedding(",".join(meta_info['tag_list'])).detach().cpu()
            if "audio" in self.retriever and "audio" in self.enabled_corpora:
                audio_db[track_id] = self.retriever["audio"].get_audio_embedding(audio_path).detach().cpu()
            if "image" in self.retriever and "image" in self.enabled_corpora:
                image_db[track_id] = self.retriever["image"].get_image_embedding(image_path).detach().cpu()
            if "cf" in self.retriever and "cf" in self.enabled_corpora:
                cf_embedding = self.retriever["cf"].get_item_embedding(track_id)
                if cf_embedding is not None:
                    cf_db[track_id] = cf_embedding.detach().cpu()
        os.makedirs(os.path.join(self.cache_dir, "encoder"), exist_ok=True)
        vector_db = {}
        if "metadata" in self.enabled_corpora:
            vector_db["metadata"] = metadata_db
        if "lyrics" in self.enabled_corpora:
            vector_db["lyrics"] = lyrics_db
        if "attributes" in self.enabled_corpora:
            vector_db["attributes"] = attributes_db
        if "audio" in self.enabled_corpora:
            vector_db["audio"] = audio_db
        if "image" in self.enabled_corpora:
            vector_db["image"] = image_db
        if "cf" in self.enabled_corpora:
            vector_db["cf"] = cf_db
        torch.save(vector_db, os.path.join(self.cache_dir, "encoder", "vector_db.pt"))
        # Refresh in-memory structures
        self.vector_db = {modality: values for modality, values in vector_db.items() if values}
        self.modality_list = list(self.vector_db.keys())
        (
            self.original_matrices,
            self.original_id_lists,
            self.original_index_maps,
        ) = self._build_matrices_from_vector_db()

    def text_to_item_similarity(self, modality_type: str, corpus_type: str, query: str, topk: int):
        """Compute text-to-item similarity for the specified corpus.

        Args:
            modality_type (str): One of {"text", "audio", "image"}.
            corpus_type (str): One of {"metadata", "lyrics", "attributes", "audio", "image"}.
            query (str): Input text query.
            topk (int): Number of results.

        Returns:
            list[str]: Ranked track ids.
        """
        if corpus_type not in set(self.modality_list):
            raise ValueError(f"Invalid corpus_type: {corpus_type}")
        if modality_type not in self.retriever:
            raise ValueError(f"Invalid modality_type: {modality_type}")
        # enforce compatible pairs
        if corpus_type in {"metadata", "lyrics", "attributes"} and modality_type != "text":
            modality_type = "text"
        if modality_type == "audio" and corpus_type != "audio":
            corpus_type = "audio"
        if modality_type == "image" and corpus_type != "image":
            corpus_type = "image"
        mat = self.current_matrices.get(corpus_type)
        ids = self.current_id_lists.get(corpus_type, [])
        try:
            encoder = self.retriever[modality_type]
            q = encoder.get_text_embedding(query).detach().cpu().squeeze()
            k = min(topk, mat.size(0))
            scores = torch.matmul(mat, q.to(mat.dtype))
            top_indices = torch.topk(scores, k=k).indices.tolist()
            return [ids[i] for i in top_indices]
        except Exception as e:
            raise ValueError(f"Error in text_to_item_similarity: {e}")

    def item_to_item_similarity(self, modality_type: str, corpus_type:str, item_id: str, topk: int):
        """Compute item-to-item similarity within a corpus.

        Args:
            modality_type (str): One of {"audio", "image", "cf"}.
            corpus_type (str): One of {"audio", "image", "cf"}.
            item_id (str): Anchor track id.
            topk (int): Number of results.

        Returns:
            list[str]: Ranked track ids.
        """
        if modality_type not in self.retriever:
            raise ValueError(f"Invalid modality type: {modality_type}")
        if corpus_type not in set(self.modality_list):
            raise ValueError(f"Invalid corpus_type for item similarity: {corpus_type}")
        mat = self.current_matrices.get(corpus_type)
        ids = self.current_id_lists.get(corpus_type, [])
        try:
            if item_id not in self.vector_db.get(modality_type, {}):
                raise ValueError(f"Item {item_id} not found in the database")
            item_emb = self.vector_db[modality_type][item_id].detach().cpu().squeeze()
            k = min(topk, mat.size(0))
            scores = torch.matmul(mat, item_emb.to(mat.dtype))
            top_indices = torch.topk(scores, k=k).indices.tolist()
            return [ids[i] for i in top_indices]
        except Exception as e:
            raise ValueError(f"Error in item_to_item_similarity: {e}")

    def user_to_item_similarity(self, user_id: str, topk: int):
        """Compute user-to-item similarity using the CF model.

        Args:
            user_id (str): User identifier.
            topk (int): Number of results.

        Returns:
            list[str]: Ranked track ids personalized for the user.
        """
        # Use CF model to get user embedding; DB contains item embeddings
        mat = self.current_matrices.get("cf")
        ids = self.current_id_lists.get("cf", [])
        if "cf" not in self.retriever or mat is None:
            raise ValueError("CF retriever is not enabled")
        try:
            user_emb = self.retriever["cf"].get_user_embedding(user_id)
            if user_emb is None:
                raise ValueError(f"User {user_id} not found in the database, cold start user")
            q = user_emb.detach().cpu().squeeze()
            k = min(topk, mat.size(0))
            scores = torch.matmul(mat, q.to(mat.dtype))
            top_indices = torch.topk(scores, k=k).indices.tolist()
            return [ids[i] for i in top_indices]
        except Exception as e:
            raise ValueError(f"Error in user_to_item_similarity: {e}")

# emb_tool = EmbeddingTool()
# print(emb_tool.text_to_item_similarity("text", "metadata", "cold as ice", 5))
