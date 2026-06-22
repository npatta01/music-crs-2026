from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "setup_worktree_cache.py"
    )
    spec = importlib.util.spec_from_file_location("setup_worktree_cache", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_source(root: Path) -> None:
    (root / "cache" / "lancedb").mkdir(parents=True)
    (root / "cache" / "tag_embedding_index").mkdir(parents=True)
    (root / "exp" / "analysis" / "rerank" / "raw_msg_store").mkdir(parents=True)
    (root / "exp" / "analysis" / "rerank" / "q06_memo.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (root / ".env").write_text("DEEPINFRA_API_KEY=x\n", encoding="utf-8")


def test_setup_links_cache_rerank_cache_and_env_from_cli_source(tmp_path):
    module = _load_module()
    source = tmp_path / "source"
    target = tmp_path / "target"
    _make_source(source)
    target.mkdir()

    result = module.setup_worktree_cache(target, source)

    assert result.changed == 3
    assert (target / "cache").resolve() == (source / "cache").resolve()
    assert (target / "exp" / "analysis" / "rerank").resolve() == (
        source / "exp" / "analysis" / "rerank"
    ).resolve()
    assert (target / ".env").resolve() == (source / ".env").resolve()


def test_setup_is_idempotent_for_existing_expected_symlinks(tmp_path):
    module = _load_module()
    source = tmp_path / "source"
    target = tmp_path / "target"
    _make_source(source)
    target.mkdir()

    first = module.setup_worktree_cache(target, source)
    second = module.setup_worktree_cache(target, source)

    assert first.changed == 3
    assert second.changed == 0
    assert second.ok == 3


def test_setup_refuses_to_overwrite_real_paths_without_force(tmp_path):
    module = _load_module()
    source = tmp_path / "source"
    target = tmp_path / "target"
    _make_source(source)
    (target / "cache").mkdir(parents=True)

    with pytest.raises(FileExistsError, match="cache"):
        module.setup_worktree_cache(target, source)


def test_setup_refuses_recursive_cache_link(tmp_path):
    module = _load_module()
    source = tmp_path / "source"
    _make_source(source)

    with pytest.raises(ValueError, match="recursive symlink"):
        module.setup_worktree_cache(source / "cache", source)


def test_resolve_source_prefers_env_then_git_config(tmp_path, monkeypatch):
    module = _load_module()
    env_source = tmp_path / "env-source"
    git_source = tmp_path / "git-source"
    _make_source(env_source)
    _make_source(git_source)
    monkeypatch.setenv("MCRS_SHARED_ROOT", str(env_source))
    monkeypatch.setattr(module, "git_config_shared_root", lambda: git_source)

    assert module.resolve_source(None) == env_source.resolve()


def test_main_returns_clear_error_when_shared_root_is_not_configured(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.delenv("MCRS_SHARED_ROOT", raising=False)
    monkeypatch.setattr(module, "git_config_shared_root", lambda: None)

    assert module.main([]) == 2

    captured = capsys.readouterr()
    assert "Shared cache root is not configured" in captured.err
    assert "git config --global mcrs.sharedRoot" in captured.err
