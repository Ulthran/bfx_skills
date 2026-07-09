"""Loads optional ~/.bfx_mcp/config.yaml. Zero-config by default: every
setting has a built-in default so the server works with no setup file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


def _home_dir() -> Path:
    return Path(os.environ.get("BFX_MCP_HOME", "~/.bfx_mcp")).expanduser()


@dataclass(frozen=True)
class ClusterConfig:
    local_cpu_ceiling: int = field(default_factory=lambda: os.cpu_count() or 4)
    local_mem_gb_ceiling: float = 16.0
    default_partition: str | None = None
    default_account: str | None = None


@dataclass(frozen=True)
class Config:
    home: Path
    environments_root: Path
    databases_root: Path
    jobs_dir: Path
    registry_dir: Path
    cluster: ClusterConfig


def _load_raw(home: Path) -> dict:
    config_path = home / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_config() -> Config:
    home = _home_dir()
    raw = _load_raw(home)

    environments_root = Path(
        raw.get("environments", {}).get("root", home / "environments")
    ).expanduser()
    databases_root = Path(
        raw.get("databases", {}).get("root", home / "databases")
    ).expanduser()

    cluster_raw = raw.get("cluster", {})
    cluster = ClusterConfig(
        local_cpu_ceiling=cluster_raw.get("local_cpu_ceiling", os.cpu_count() or 4),
        local_mem_gb_ceiling=cluster_raw.get("local_mem_gb_ceiling", 16.0),
        default_partition=cluster_raw.get("default_partition"),
        default_account=cluster_raw.get("default_account"),
    )

    config = Config(
        home=home,
        environments_root=environments_root,
        databases_root=databases_root,
        jobs_dir=home / "jobs",
        registry_dir=home / "registry",
        cluster=cluster,
    )

    for directory in (
        config.home,
        config.environments_root,
        config.databases_root,
        config.jobs_dir,
        config.registry_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    return config
