from types import SimpleNamespace


def test_modal_client_uses_private_function_lookup(monkeypatch):
    from mcrs.lancedb.modal_client import LanceDbModalClient

    calls = {}

    class FakeFunction:
        def remote(self, **kwargs):
            calls["remote"] = kwargs
            return ["track-1", "track-2"]

    def fake_from_name(app_name, function_name):
        calls["lookup"] = (app_name, function_name)
        return FakeFunction()

    fake_modal = SimpleNamespace(
        Function=SimpleNamespace(from_name=fake_from_name)
    )
    monkeypatch.setattr("mcrs.lancedb.modal_client.modal", fake_modal)

    client = LanceDbModalClient(app_name="music-crs", function_name="query_lancedb")

    assert client.query("dark synthwave", topk=20, retrieval_config={"x": "y"}) == [
        "track-1",
        "track-2",
    ]
    assert calls["lookup"] == ("music-crs", "query_lancedb")
    assert calls["remote"] == {
        "query": "dark synthwave",
        "topk": 20,
        "retrieval_config": {"x": "y"},
    }
