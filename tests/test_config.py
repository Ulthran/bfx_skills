import os

from bfx_mcp.common.config import load_config


def test_defaults_create_all_directories():
    config = load_config()
    for directory in (
        config.home,
        config.environments_root,
        config.databases_root,
        config.jobs_dir,
        config.registry_dir,
    ):
        assert directory.is_dir()


def test_cluster_defaults():
    config = load_config()
    assert config.cluster.local_cpu_ceiling == (os.cpu_count() or 4)
    assert config.cluster.local_mem_gb_ceiling == 16.0
    assert config.cluster.default_partition is None


def test_config_yaml_overrides(tmp_path, monkeypatch):
    home = tmp_path / ".bfx_mcp"
    home.mkdir()
    custom_envs_root = tmp_path / "custom-envs"
    (home / "config.yaml").write_text(
        f"""
environments:
  root: {custom_envs_root}
cluster:
  local_cpu_ceiling: 2
  local_mem_gb_ceiling: 4
  default_partition: general
"""
    )
    monkeypatch.setenv("BFX_MCP_HOME", str(home))
    from bfx_mcp.common import config as config_module

    config_module.load_config.cache_clear()
    config = config_module.load_config()

    assert config.environments_root == custom_envs_root
    assert config.cluster.local_cpu_ceiling == 2
    assert config.cluster.default_partition == "general"
