# bfx-mcp — a local MCP server for bioinformatics

This repo is the source for `bfx-mcp`: a pip-installable, stdio-transport
MCP server that gives any Claude client (Code, Desktop, or a custom Agent
SDK app) a small set of bioinformatics-relevant tools. It is not a skill
library or a Snakemake pipeline — it's a Python package. No standing daemon:
the client spawns the server process on demand and kills it on session end.

## Design philosophy — read this before adding a tool

**Do not wrap a raw CLI command 1:1.** Claude already has direct shell
access to `sbatch`/`squeue`/`conda`/`docker`/`samtools`/etc. on the same
machine this server runs on. A tool that just shells out and returns stdout
adds a schema and a hop for zero benefit — Claude running the command
itself is strictly better. Every tool here earns its place by doing one of
three things raw CLI access can't:

1. **Judgment/orchestration** — e.g. `submit_job` deciding local vs. Slurm
   placement; `submit_and_wait` polling with exponential backoff so a
   multi-day job doesn't block a single tool call.
2. **State a stateless CLI call can't see** — e.g. tracking a local
   background PID (`squeue` has no idea it exists), or a discoverable index
   of reusable environments/databases with metadata (`find_environments`,
   `find_databases` — check before recreating something that already
   exists).
3. **Reference knowledge Claude wouldn't otherwise have** — e.g.
   `get_output_validation_guide`'s threshold tables, or
   `get_environment_guidelines`'s manager tradeoffs. These ship as plain
   tools returning markdown text, *not* MCP Resources — Claude Code
   currently only surfaces resources when a human explicitly `@`-mentions
   them, so a Resource would be invisible to the model during normal
   reasoning. A Tool call is what Claude actually consults unprompted.

If you're about to add a tool that's mostly "run this binary and format the
output," stop — that almost certainly belongs in Claude's own Bash use, not
in this server.

## Architecture

```
src/bfx_mcp/
├── server.py           # FastMCP instance; every tool is registered here
├── common/
│   ├── shell.py         # run_foreground / spawn_background / write_script — no shell=True string interpolation; commands run via a temp bash script for pipe/redirect support
│   ├── detect.py         # detect_capabilities(): actually runs each binary (exit code), not just shutil.which — PATH presence can lie (e.g. WSL Docker interop shims)
│   ├── config.py          # ~/.bfx_mcp/config.yaml loader; zero-config by default, every setting has a built-in default
│   └── registry.py        # generic durable-asset index (JSON per kind), shared by environments/ and databases/
├── cluster/            # submit_job, submit_and_wait, job_status, cancel_job
│   ├── slurm.py
│   └── job_state.py     # local job tracking, distinct from common/registry.py because jobs are ephemeral, not durable reusable assets
├── environments/       # register_environment, find_environments, list_environments, get_environment_guidelines
│   ├── tools.py
│   └── guidelines.md    # reference content returned by get_environment_guidelines — edit this file, not tools.py, to change the guidance text
├── databases/           # register_database, find_databases, list_databases, check_for_updates, get_database_conventions
│   ├── tools.py
│   └── conventions.md
└── validation/          # get_output_validation_guide — instructional only, no operational wrappers
    ├── tools.py
    └── output_validation.md
```

Config and state all live under `~/.bfx_mcp/` (override with `BFX_MCP_HOME`):
`config.yaml` (optional overrides), `jobs/` (local job tracking),
`registry/` (environments.json, databases.json).

## Adding a new tool

1. Write the plain function in the relevant module — no `mcp` import needed
   there; keep business logic testable without the SDK in the loop.
2. Register it in `server.py` with `mcp.tool()(your_function)` (or
   `@mcp.tool()` directly if defining it inline in server.py, as
   `detect_capabilities` does). The function's docstring becomes the tool
   description the model sees — write it for that audience, including when
   to call it and what it returns.
3. Add tests in `tests/`. Prefer exercising the real underlying command
   where the machine actually has it (this dev machine has sbatch, conda,
   docker interop, and samtools — see existing tests for the pattern); mock
   `common.shell.run_foreground` for Slurm-cluster-required paths that can't
   run for real in CI.
4. Run `pytest`. If it's a new tool, also sanity-check it registers via:
   ```bash
   python -c "from bfx_mcp.server import mcp; import asyncio; [print(t.name) for t in asyncio.run(mcp.list_tools())]"
   ```

## Development setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

**Always install into a dedicated venv, never the system/base Python or a
shared conda base env.** `mcp`'s dependency tree (starlette, pydantic,
httpx, anyio) will upgrade whatever's already installed in a shared
environment and can break unrelated projects there (this happened once
during initial setup — `mcp`'s starlette pin broke a co-installed FastAPI
app in the base conda env).

To register the local build with Claude Code for manual testing:

```bash
claude mcp add --scope user bfx-mcp -- /absolute/path/to/.venv/bin/bfx-mcp
claude mcp get bfx-mcp   # confirm "Connected"
```

Changes to the package take effect on the *next* server spawn (new client
session) — the running session that registered it won't see them.
