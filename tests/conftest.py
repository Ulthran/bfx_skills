import pytest


@pytest.fixture(autouse=True)
def isolated_bfx_mcp_home(tmp_path, monkeypatch):
    """Point BFX_MCP_HOME at a throwaway dir per test and clear the config cache."""
    monkeypatch.setenv("BFX_MCP_HOME", str(tmp_path / ".bfx_mcp"))
    from bfx_mcp.common import config

    config.load_config.cache_clear()
    yield
    config.load_config.cache_clear()
