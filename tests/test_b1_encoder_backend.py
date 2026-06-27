"""b1 query-encoder backend selection (the `b1_cos` Modal fallback).

`_build_b1_encoder` must pick the in-process 4B locally only when the weights are
on disk, and otherwise fall back to the Modal `B1Encoder` client — so a local /
blindset run without the ~16GB weights serves b1_cos via Modal instead of
crashing on the in-process load. `MCRS_B1_ENCODER_BACKEND` forces either path.

Both encoders construct lazily (no model load / no Modal call at build time), so
this exercises the real selection branch without GPUs or a deployed Modal app.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "rerank"))

import b1_live  # noqa: E402
import mcrs.embeddings.modal_qwen3_client as modal_client_mod  # noqa: E402
from mcrs.embeddings.qwen3_embedding import Qwen3EmbeddingClient  # noqa: E402


class _FakeModalClient:
    """Stand-in for ModalQwen3EmbeddingClient (avoids importing modal)."""

    def __init__(self, *, app_name: str, cls_name: str) -> None:
        self.app_name = app_name
        self.cls_name = cls_name


def _patch_modal(monkeypatch):
    monkeypatch.setattr(
        modal_client_mod, "ModalQwen3EmbeddingClient", _FakeModalClient
    )


def test_auto_uses_local_when_weights_present(monkeypatch, tmp_path):
    monkeypatch.delenv("MCRS_B1_ENCODER_BACKEND", raising=False)
    enc = b1_live._build_b1_encoder(str(tmp_path), "cpu")  # tmp_path exists
    assert isinstance(enc, Qwen3EmbeddingClient)
    assert enc.model_name == str(tmp_path)
    assert enc.max_length == 2048  # b1 serving length (truncation-bug fix)


def test_auto_falls_back_to_modal_when_weights_absent(monkeypatch):
    monkeypatch.delenv("MCRS_B1_ENCODER_BACKEND", raising=False)
    monkeypatch.delenv("MCRS_B1_MODAL_CLS", raising=False)
    _patch_modal(monkeypatch)
    enc = b1_live._build_b1_encoder("/does/not/exist/b1-weights", "cpu")
    assert isinstance(enc, _FakeModalClient)
    assert enc.app_name == "music-crs"
    assert enc.cls_name == "B1Encoder"


def test_explicit_modal_overrides_present_weights(monkeypatch, tmp_path):
    monkeypatch.setenv("MCRS_B1_ENCODER_BACKEND", "modal")
    _patch_modal(monkeypatch)
    enc = b1_live._build_b1_encoder(str(tmp_path), "cpu")  # weights present, but forced
    assert isinstance(enc, _FakeModalClient)


def test_explicit_local_overrides_absent_weights(monkeypatch):
    monkeypatch.setenv("MCRS_B1_ENCODER_BACKEND", "local")
    enc = b1_live._build_b1_encoder("/does/not/exist/b1-weights", "cpu")
    assert isinstance(enc, Qwen3EmbeddingClient)


def test_modal_cls_env_override(monkeypatch):
    monkeypatch.setenv("MCRS_B1_ENCODER_BACKEND", "modal")
    monkeypatch.setenv("MCRS_B1_MODAL_CLS", "B1EncoderStaging")
    monkeypatch.setenv("MCRS_B1_MODAL_APP", "music-crs-dev")
    _patch_modal(monkeypatch)
    enc = b1_live._build_b1_encoder("/whatever", "cpu")
    assert enc.cls_name == "B1EncoderStaging"
    assert enc.app_name == "music-crs-dev"
