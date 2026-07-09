# bfx-mcp

A local MCP server for bioinformatics: Slurm-aware job placement, discoverable
registries for reusable conda/venv/container environments and reference
databases, and output-validation guidance — all as a stdio server any MCP
client can register, with no standing daemon.

## Install

```bash
pip install -e .
claude mcp add --scope user bfx-mcp -- bfx-mcp
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

See `CLAUDE.md` for architecture and how to add a new tool.
