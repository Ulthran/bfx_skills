"""Entry point for the bfx-mcp stdio server."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from bfx_mcp.cluster import slurm
from bfx_mcp.common.detect import detect_capabilities as _detect_capabilities
from bfx_mcp.databases import tools as databases
from bfx_mcp.environments import tools as environments
from bfx_mcp.validation import tools as validation

mcp = FastMCP("bfx-mcp")


@mcp.tool()
def detect_capabilities() -> dict[str, dict]:
    """Detect which bioinformatics-relevant CLI tools are installed on this
    machine (Slurm, conda, mamba, docker, apptainer/singularity, samtools).

    Call this first, before attempting Slurm job submission, environment/
    container management, or samtools-based validation, to know what's
    actually available rather than guessing.
    """
    return _detect_capabilities()


mcp.tool()(slurm.submit_job)
mcp.tool()(slurm.submit_and_wait)
mcp.tool()(slurm.job_status)
mcp.tool()(slurm.cancel_job)

mcp.tool()(environments.get_environment_guidelines)
mcp.tool()(environments.register_environment)
mcp.tool()(environments.find_environments)
mcp.tool()(environments.list_environments)

mcp.tool()(databases.get_database_conventions)
mcp.tool()(databases.register_database)
mcp.tool()(databases.find_databases)
mcp.tool()(databases.list_databases)
mcp.tool()(databases.check_for_updates)

mcp.tool()(validation.get_output_validation_guide)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
