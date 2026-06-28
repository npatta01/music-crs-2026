"""Runtime construction helpers for debug commands."""

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
from typing import Any

from .artifacts import RunArtifacts, load_run_aliases, resolve_run_alias, resolve_session_prefix, trace_session_ids


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", help="Path to an explicit YAML config.")
    group.add_argument("--tid", help="Task id matching configs/{tid}.yaml.")
    parser.add_argument("--config-dir", default="configs")

def _load_config_for_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.config:
        path = Path(args.config)
    else:
        path = Path(args.config_dir) / f"{args.tid}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    try:
        from omegaconf import OmegaConf

        raw = OmegaConf.to_container(OmegaConf.load(path), resolve=True) or {}
    except ModuleNotFoundError:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"config must be a YAML object: {path}")
    return raw

def _debug_config_for_cache_policy(config: dict[str, Any], *, allow_cache_write: bool) -> dict[str, Any]:
    if allow_cache_write:
        return config
    out = copy.deepcopy(config)
    qu_kwargs = out.get("qu_kwargs")
    if not isinstance(qu_kwargs, dict):
        return out

    def disable_encoder_cache(encoder_cfg: Any) -> None:
        if isinstance(encoder_cfg, dict):
            encoder_cfg["cache"] = False
            encoder_cfg["disk_cache"] = False

    disable_encoder_cache(qu_kwargs.get("encoder"))
    encoders = qu_kwargs.get("encoders")
    if isinstance(encoders, dict):
        for encoder_cfg in encoders.values():
            disable_encoder_cache(encoder_cfg)
    return out

def _build_debug_encoder_from_config(
    config: dict[str, Any],
    encoder_id: str,
    *,
    allow_cache_write: bool = False,
) -> Any:
    qu_kwargs = config.get("qu_kwargs") or {}
    if not isinstance(qu_kwargs, dict):
        raise ValueError("config.qu_kwargs must be a mapping")
    encoder_id = str(encoder_id or "default")
    encoders_cfg = qu_kwargs.get("encoders") or {}
    if not isinstance(encoders_cfg, dict):
        raise ValueError("config.qu_kwargs.encoders must be a mapping")
    encoder_cfg = None
    if encoder_id in encoders_cfg:
        encoder_cfg = encoders_cfg[encoder_id]
    elif encoder_id == "default" and qu_kwargs.get("encoder") is not None:
        encoder_cfg = qu_kwargs.get("encoder")
    if encoder_cfg is None:
        default_names = ["default"] if qu_kwargs.get("encoder") is not None else []
        available = sorted({*encoders_cfg.keys(), *default_names})
        raise ValueError(f"encoder_id {encoder_id!r} not found in config; available={available}")
    if not isinstance(encoder_cfg, dict):
        raise ValueError(f"encoder config for {encoder_id!r} must be a mapping")
    from mcrs.qu_modules.compiler_v0plus_qu import _build_encoder

    debug_cfg = dict(encoder_cfg)
    if not allow_cache_write:
        debug_cfg["cache"] = False
        debug_cfg["disk_cache"] = False
    return _build_encoder(debug_cfg)

def _debug_lancedb_params(
    config: dict[str, Any],
    run: RunArtifacts | None,
    args: argparse.Namespace,
) -> tuple[str, str]:
    if run is not None:
        return str(run.catalog_db_uri), str(run.catalog_table)
    qu_kwargs = config.get("qu_kwargs") or {}
    if not isinstance(qu_kwargs, dict):
        raise ValueError("config.qu_kwargs must be a mapping")
    lance_cfg = qu_kwargs.get("lancedb") or {}
    if not isinstance(lance_cfg, dict):
        raise ValueError("config.qu_kwargs.lancedb must be a mapping")
    db_uri = os.environ.get("MCRS_LANCEDB_URI") or lance_cfg.get("db_uri") or args.catalog_db_uri
    table_name = lance_cfg.get("table_name") or args.catalog_table
    return str(db_uri), str(table_name)

def _build_debug_lancedb_retriever(config: dict[str, Any], run: RunArtifacts | None, args: argparse.Namespace) -> Any:
    db_uri, table_name = _debug_lancedb_params(config, run, args)
    from mcrs.lancedb.retriever import LanceDbRetriever

    return LanceDbRetriever.from_retrieval_config(
        {
            "db_uri": db_uri,
            "table_name": table_name,
            "fusion": {"method": "weighted_rrf"},
            "device": "cpu",
        }
    )

def _load_debug_lancedb_catalog(config: dict[str, Any], run: RunArtifacts | None, args: argparse.Namespace) -> Any:
    db_uri, table_name = _debug_lancedb_params(config, run, args)
    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog

    return LanceDbCatalog(db_uri=db_uri, table_name=table_name)

def _build_extractor_from_config(config: dict[str, Any]) -> Any:
    from scripts.extract_state import build_extractor, extractor_config_from_config

    return build_extractor(extractor_config_from_config(config))

def _build_state_ranker_from_config(config: dict[str, Any]) -> Any:
    from mcrs.qu_modules.state_ranker_qu import build_state_ranker_qu

    qu_kwargs = config.get("qu_kwargs") or {}
    if not isinstance(qu_kwargs, dict):
        raise ValueError("config.qu_kwargs must be a mapping")
    return build_state_ranker_qu(qu_kwargs=qu_kwargs)

def _require_trace_run(args: argparse.Namespace) -> RunArtifacts:
    run = _require_run(args)
    if run.trace is None:
        raise ValueError(f"run alias {run.name!r} does not define a trace path")
    return run

def _require_run(args: argparse.Namespace) -> RunArtifacts:
    if not args.run:
        raise ValueError("--run is required for this command")
    return _resolve_run(args)

def _optional_run(args: argparse.Namespace) -> RunArtifacts | None:
    return _resolve_run(args) if args.run else None

def _resolve_run(args: argparse.Namespace) -> RunArtifacts:
    run_file = Path(args.run_file)
    aliases = load_run_aliases(run_file)
    return resolve_run_alias(aliases, args.run, base_dir=run_file.resolve().parent)

def _resolve_session(run: RunArtifacts, value: str) -> str:
    if run.trace is None:
        raise ValueError(f"run alias {run.name!r} does not define a trace path")
    return resolve_session_prefix(trace_session_ids(run.trace), value)

def _load_catalog(run: RunArtifacts | None, args: argparse.Namespace) -> Any:
    db_uri = str(run.catalog_db_uri if run else args.catalog_db_uri)
    table_name = str(run.catalog_table if run else args.catalog_table)
    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog

    return LanceDbCatalog(db_uri=db_uri, table_name=table_name)
