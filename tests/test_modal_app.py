from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


class _FakeVolume:
    def __init__(self):
        self.commit_calls = 0

    def commit(self):
        self.commit_calls += 1


class _FakeImage:
    @classmethod
    def debian_slim(cls, python_version: str):
        return cls()

    def uv_sync(self, *_args, **_kwargs):
        return self

    def uv_pip_install(self, *_args, **_kwargs):
        return self

    def add_local_dir(self, *_args, **_kwargs):
        return self

    def env(self, *_args, **_kwargs):
        return self


class _FakeFunction:
    def __init__(self, fn):
        self.fn = fn
        self.remote_calls = []

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)

    def remote(self, **kwargs):
        self.remote_calls.append(kwargs)


class _FakeApp:
    def __init__(self, _name):
        pass

    def function(self, **_kwargs):
        def decorator(fn):
            return _FakeFunction(fn)

        return decorator

    def local_entrypoint(self):
        def decorator(fn):
            return fn

        return decorator


def _fake_modal_module():
    results_volume = _FakeVolume()
    hf_cache_volume = _FakeVolume()

    def from_name(name: str, create_if_missing: bool = False):
        return results_volume if "results" in name else hf_cache_volume

    fake_modal = SimpleNamespace(
        Secret=SimpleNamespace(from_dotenv=lambda _path: object()),
        Volume=SimpleNamespace(from_name=from_name),
        App=_FakeApp,
        Image=_FakeImage,
    )
    return fake_modal, results_volume


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "modal" / "app.py"
    fake_modal, results_volume = _fake_modal_module()
    spec = importlib.util.spec_from_file_location("modal_app_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    sys.modules["modal"] = fake_modal
    spec.loader.exec_module(module)
    return module, results_volume


def test_talkplay_modal_function_runs_talkplay_script_and_commits(monkeypatch):
    module, results_volume = _load_module()
    commands = []

    def fake_run(cmd, cwd):
        commands.append((cmd, cwd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    module._inference_talkplay_devset(
        tid="talkplay_qwen3_4b_devset_smoke",
        batch_size=1,
        num_sessions=10,
        clear_cache=True,
    )

    assert commands == [
        (
            [
                sys.executable,
                "/app/run_inference_talkplay_devset.py",
                "--tid",
                "talkplay_qwen3_4b_devset_smoke",
                "--batch_size",
                "1",
                "--exp_dir",
                module.EXP_DIR,
                "--device",
                "cuda",
                "--num_sessions",
                "10",
                "--clear_cache",
            ],
            "/app",
        )
    ]
    assert results_volume.commit_calls == 1


def test_talkplay_modal_function_writes_session_ids_file_and_suffix(monkeypatch):
    module, _results_volume = _load_module()
    commands = []

    def fake_run(cmd, cwd):
        commands.append((cmd, cwd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    module._inference_talkplay_devset(
        tid="talkplay_qwen3_4b_devset_smoke",
        batch_size=1,
        num_sessions=0,
        clear_cache=False,
        session_ids_json='["session-1","session-2"]',
        output_suffix="shard_000",
    )

    cmd, cwd = commands[0]
    assert cwd == "/app"
    assert "--session_ids_file" in cmd
    assert "--output_suffix" in cmd
    assert "shard_000" in cmd


def test_split_session_ids_balances_shards():
    module, _results_volume = _load_module()

    shards = module._split_session_ids(
        ["session-1", "session-2", "session-3", "session-4", "session-5"],
        num_shards=2,
    )

    assert shards == [
        ["session-1", "session-3", "session-5"],
        ["session-2", "session-4"],
    ]
