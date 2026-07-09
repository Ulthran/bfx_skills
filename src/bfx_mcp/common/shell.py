"""Shell execution helper shared by cluster job submission and elsewhere.

Commands are written to a temp bash script and executed as `bash <script>`
rather than passed through `subprocess.run(..., shell=True)`. This still
supports full shell syntax (pipes, redirects, `&&`) that bioinformatics
one-liners need, without string-interpolating untrusted values into a shell
invocation.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from pathlib import Path

_SCRIPT_HEADER = "#!/usr/bin/env bash\nset -euo pipefail\n"


def write_script(command: str, *, sbatch_directives: list[str] | None = None) -> Path:
    """Write `command` to a standalone, executable bash script and return its path.

    `sbatch_directives` are `#SBATCH ...` lines inserted after the shebang,
    turning the same script into a valid sbatch submission script.
    """
    fd, path_str = tempfile.mkstemp(prefix="bfx-mcp-", suffix=".sh")
    path = Path(path_str)
    with os.fdopen(fd, "w") as f:
        f.write(_SCRIPT_HEADER)
        if sbatch_directives:
            for directive in sbatch_directives:
                f.write(f"#SBATCH {directive}\n")
        f.write(command.rstrip() + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def run_foreground(argv: list[str], *, timeout: float | None = None) -> dict:
    """Run argv to completion and capture output. No shell involved."""
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\n[bfx-mcp] timed out",
            "timed_out": True,
        }
    except OSError as exc:
        return {"returncode": None, "stdout": "", "stderr": str(exc), "timed_out": False}
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": False,
    }


def spawn_background(argv: list[str], *, log_path: Path) -> int:
    """Launch argv detached from this process, redirecting output to log_path.

    Returns the child PID. Used for local (non-Slurm) job submission so a
    long-running command doesn't block the MCP tool call that started it.
    """
    with open(log_path, "wb") as log_file:
        process = subprocess.Popen(
            argv,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    return process.pid
