from types import SimpleNamespace


def test_modal_client_uses_private_class_lookup(monkeypatch):
    from mcrs.lancedb.modal_client import LanceDbModalClient

    calls = {}

    class FakeService:
        def __init__(self):
            calls["instantiated"] = True
            self.retrieve = SimpleNamespace(remote=self.retrieve_remote)
            self.retrieve_batch = SimpleNamespace(remote=self.retrieve_batch_remote)
            self.embed_batch = SimpleNamespace(remote=self.embed_batch_remote)

        def retrieve_remote(self, **kwargs):
            calls["retrieve"] = kwargs
            return ["track-1", "track-2"]

        def retrieve_batch_remote(self, **kwargs):
            calls["retrieve_batch"] = kwargs
            return [["track-1"], ["track-2"]]

        def embed_batch_remote(self, **kwargs):
            calls["embed_batch"] = kwargs
            return [[1.0], [2.0]]

    def fake_cls_from_name(app_name, class_name):
        calls["lookup"] = (app_name, class_name)
        return FakeService

    fake_modal = SimpleNamespace(
        Cls=SimpleNamespace(from_name=fake_cls_from_name)
    )
    monkeypatch.setattr("mcrs.lancedb.modal_client.modal", fake_modal)

    client = LanceDbModalClient(app_name="music-crs", class_name="ModalRetrievalService")

    assert client.query("dark synthwave", topk=20, retrieval_config={"ignored": True}) == [
        "track-1",
        "track-2",
    ]
    assert client.query_batch(["dark", "ambient"], topk=10) == [["track-1"], ["track-2"]]
    assert client.embed_batch(["a", "b"]) == [[1.0], [2.0]]
    assert calls["lookup"] == ("music-crs", "ModalRetrievalService")
    assert calls["instantiated"] is True
    assert calls["retrieve"] == {
        "query": "dark synthwave",
        "topk": 20,
        "retrieval_config": {"ignored": True},
    }
    assert calls["retrieve_batch"] == {
        "queries": ["dark", "ambient"],
        "topk": 10,
        "retrieval_config": None,
    }
    assert calls["embed_batch"] == {"texts": ["a", "b"]}
