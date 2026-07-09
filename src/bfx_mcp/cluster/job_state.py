"""Job registry: tracks both locally-backgrounded processes and Slurm
submissions under a single job id, since raw CLI has no way to see a plain
background PID and submit_and_wait needs a place to persist its backoff
cursor between calls."""

from __future__ import annotations

import json
import os
import signal
import time
import uuid
from pathlib import Path
from typing import Any

from bfx_mcp.common import shell
from bfx_mcp.common.config import load_config

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _job_path(job_id: str) -> Path:
    safe_name = job_id.replace(":", "_")
    return load_config().jobs_dir / f"{safe_name}.json"


def _read(job_id: str) -> dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _write(entry: dict[str, Any]) -> None:
    path = _job_path(entry["job_id"])
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(entry, f, indent=2, sort_keys=True)
    tmp.replace(path)


def list_jobs() -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in sorted(load_config().jobs_dir.glob("*.json"))]


def get_job(job_id: str) -> dict[str, Any] | None:
    return _read(job_id)


def create_local_job(command: str, *, metadata: dict[str, Any]) -> dict[str, Any]:
    job_id = f"local:{uuid.uuid4().hex[:12]}"
    config = load_config()
    script_path = shell.write_script(command)
    log_path = config.jobs_dir / f"{job_id.replace(':', '_')}.log"
    exit_code_path = config.jobs_dir / f"{job_id.replace(':', '_')}.exitcode"

    # Wrap so the exit code is written to disk by the child itself, not
    # inferred via os.waitpid — that only works if this same server process
    # is still the parent, which isn't guaranteed across client restarts.
    wrapper_argv = [
        "bash",
        "-c",
        f'"{script_path}"; echo $? > "{exit_code_path}"',
    ]
    pid = shell.spawn_background(wrapper_argv, log_path=log_path)

    now = time.time()
    entry = {
        "job_id": job_id,
        "backend": "local",
        "command": command,
        "script_path": str(script_path),
        "log_path": str(log_path),
        "exit_code_path": str(exit_code_path),
        "pid": pid,
        "status": "running",
        "submitted_at": now,
        "updated_at": now,
        "poll_state": {"interval_seconds": 5.0, "elapsed_seconds": 0.0},
        **metadata,
    }
    _write(entry)
    return entry


def create_slurm_job_entry(slurm_job_id: str, command: str, *, metadata: dict[str, Any]) -> dict[str, Any]:
    job_id = f"slurm:{slurm_job_id}"
    now = time.time()
    entry = {
        "job_id": job_id,
        "backend": "slurm",
        "slurm_job_id": slurm_job_id,
        "command": command,
        "status": "running",
        "submitted_at": now,
        "updated_at": now,
        "poll_state": {"interval_seconds": 5.0, "elapsed_seconds": 0.0},
        **metadata,
    }
    _write(entry)
    return entry


def refresh_local_status(entry: dict[str, Any]) -> dict[str, Any]:
    """Update a local job entry's status in place (does not persist)."""
    if entry["status"] in TERMINAL_STATUSES:
        return entry

    exit_code_path = Path(entry["exit_code_path"])
    if exit_code_path.exists():
        try:
            returncode = int(exit_code_path.read_text().strip())
        except ValueError:
            returncode = None
        entry["returncode"] = returncode
        entry["status"] = "completed" if returncode == 0 else "failed"
        entry["updated_at"] = time.time()
        return entry

    if not _pid_alive(entry["pid"]):
        # Process is gone but never wrote an exit code (e.g. SIGKILL) —
        # genuinely unknown, don't claim success or failure.
        entry["status"] = "unknown"
        entry["updated_at"] = time.time()
        return entry

    entry["status"] = "running"
    return entry


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def cancel_local(entry: dict[str, Any]) -> dict[str, Any]:
    if entry["status"] in TERMINAL_STATUSES:
        return entry
    try:
        os.kill(entry["pid"], signal.SIGTERM)
    except ProcessLookupError:
        pass
    entry["status"] = "cancelled"
    entry["updated_at"] = time.time()
    return entry


def save(entry: dict[str, Any]) -> None:
    _write(entry)
