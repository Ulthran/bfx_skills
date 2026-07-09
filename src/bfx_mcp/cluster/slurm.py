"""Smart job placement and a bounded, backoff-polling wait.

Deliberately not a wrapper around every sbatch/squeue/scancel flag — Claude
can already run those directly. What's here is the judgment raw CLI can't
provide: deciding local vs. cluster placement, and waiting on a job that may
take anywhere from seconds to days without blocking a single tool call for
that whole span.
"""

from __future__ import annotations

import re
import time
from typing import Any, Literal

from bfx_mcp.cluster import job_state
from bfx_mcp.common import shell
from bfx_mcp.common.config import load_config
from bfx_mcp.common.detect import detect_capabilities

Target = Literal["auto", "local", "cluster"]

_SUBMITTED_JOB_RE = re.compile(r"Submitted batch job (\d+)")

_INITIAL_POLL_INTERVAL = 5.0
_MAX_POLL_INTERVAL = 300.0
_RUNNING_STATES = {"PENDING", "RUNNING", "CONFIGURING", "COMPLETING", "SUSPENDED"}
_CANCELLED_STATES_PREFIX = "CANCELLED"
_FAILED_STATES = {"FAILED", "NODE_FAIL", "OUT_OF_MEMORY", "DEADLINE", "BOOT_FAIL", "TIMEOUT"}


def _decide_backend(target: Target, cpus: int, mem_gb: float | None, slurm_available: bool) -> str:
    if target == "cluster":
        if not slurm_available:
            raise RuntimeError(
                "target='cluster' was requested but no Slurm tooling (sbatch) was found on "
                "PATH. Not falling back to local — call detect_capabilities() to confirm, or "
                "use target='local'/'auto' if cluster execution isn't actually required."
            )
        return "slurm"
    if target == "local":
        return "local"
    if target == "auto":
        if not slurm_available:
            return "local"
        ceilings = load_config().cluster
        exceeds_cpu = cpus > ceilings.local_cpu_ceiling
        exceeds_mem = mem_gb is not None and mem_gb > ceilings.local_mem_gb_ceiling
        return "slurm" if (exceeds_cpu or exceeds_mem) else "local"
    raise ValueError(f"target must be 'auto', 'local', or 'cluster', got {target!r}")


def submit_job(
    command: str,
    target: Target = "auto",
    cpus: int = 1,
    mem_gb: float | None = None,
    time_limit: str | None = None,
    job_name: str | None = None,
    partition: str | None = None,
    account: str | None = None,
) -> dict[str, Any]:
    """Run `command` locally or on the Slurm cluster, non-blockingly.

    `target="auto"` (default) places the job on Slurm only if it's available
    *and* the requested cpus/mem_gb exceed configured local ceilings;
    otherwise it runs locally in the background. `target="cluster"` demands
    Slurm and raises clearly (no silent local fallback) if it isn't present.
    `target="local"` always runs locally regardless of requested resources.

    Returns immediately with a job id — use submit_and_wait or job_status to
    check on it, since real jobs can run for hours to days.
    """
    capabilities = detect_capabilities()
    slurm_available = capabilities["sbatch"]["available"]
    backend = _decide_backend(target, cpus, mem_gb, slurm_available)

    metadata = {
        "job_name": job_name,
        "cpus": cpus,
        "mem_gb": mem_gb,
        "time_limit": time_limit,
        "requested_target": target,
    }

    if backend == "local":
        entry = job_state.create_local_job(command, metadata=metadata)
        return entry

    config = load_config()
    directives = [f"--cpus-per-task={cpus}"]
    if job_name:
        directives.append(f"--job-name={job_name}")
    if mem_gb is not None:
        directives.append(f"--mem={mem_gb}G")
    if time_limit:
        directives.append(f"--time={time_limit}")
    chosen_partition = partition or config.cluster.default_partition
    if chosen_partition:
        directives.append(f"--partition={chosen_partition}")
    chosen_account = account or config.cluster.default_account
    if chosen_account:
        directives.append(f"--account={chosen_account}")

    script_path = shell.write_script(command, sbatch_directives=directives)
    result = shell.run_foreground(["sbatch", str(script_path)])
    if result["returncode"] != 0:
        raise RuntimeError(f"sbatch failed: {result['stderr'].strip() or result['stdout'].strip()}")

    match = _SUBMITTED_JOB_RE.search(result["stdout"])
    if not match:
        raise RuntimeError(f"Could not parse a job id from sbatch output: {result['stdout']!r}")

    slurm_job_id = match.group(1)
    metadata["script_path"] = str(script_path)
    entry = job_state.create_slurm_job_entry(slurm_job_id, command, metadata=metadata)
    return entry


def _normalize_slurm_state(state: str) -> str:
    state = state.strip().upper().split()[0] if state.strip() else ""
    if state in _RUNNING_STATES:
        return "running"
    if state == "COMPLETED":
        return "completed"
    if state.startswith(_CANCELLED_STATES_PREFIX):
        return "cancelled"
    if state in _FAILED_STATES:
        return "failed"
    return "unknown"


def _refresh_slurm(entry: dict[str, Any]) -> dict[str, Any]:
    if entry["status"] in job_state.TERMINAL_STATUSES:
        return entry

    slurm_job_id = entry["slurm_job_id"]
    result = shell.run_foreground(["squeue", "-j", slurm_job_id, "--noheader", "--format=%T"])
    if result["returncode"] == 0 and result["stdout"].strip():
        state = result["stdout"].strip().splitlines()[0]
        entry["status"] = _normalize_slurm_state(state)
        entry["updated_at"] = time.time()
        return entry

    # No longer in the queue — check sacct for the terminal state.
    result = shell.run_foreground(
        ["sacct", "-j", slurm_job_id, "--format=State", "--noheader", "--parsable2"]
    )
    if result["returncode"] == 0 and result["stdout"].strip():
        state = result["stdout"].strip().splitlines()[0]
        entry["status"] = _normalize_slurm_state(state)
    else:
        entry["status"] = "unknown"
    entry["updated_at"] = time.time()
    return entry


def _refresh(entry: dict[str, Any]) -> dict[str, Any]:
    if entry["backend"] == "local":
        return job_state.refresh_local_status(entry)
    return _refresh_slurm(entry)


def _require_entry(job_id: str) -> dict[str, Any]:
    entry = job_state.get_job(job_id)
    if entry is None:
        raise ValueError(f"No known job with id {job_id!r} (check list_jobs() for known ids)")
    return entry


def job_status(job_id: str) -> dict[str, Any]:
    """One immediate status check, no waiting. For a local job id this is the
    only way to check on it at all — a plain background PID isn't visible to
    squeue. For a Slurm job id it also refreshes the cached state that
    submit_and_wait relies on."""
    entry = _require_entry(job_id)
    entry = _refresh(entry)
    job_state.save(entry)
    return entry


def submit_and_wait(job_id: str, max_wait_seconds: float = 600.0) -> dict[str, Any]:
    """Poll a job with exponential backoff (fast at first to catch immediate
    failures, backing off toward a 5-minute cap for genuinely long jobs),
    bounded to `max_wait_seconds` for this call.

    If the job reaches a terminal state within the budget, returns that final
    state. Otherwise returns status "still_running" — call this again with
    the same job_id to keep waiting; the backoff cursor persists between
    calls so a second call doesn't restart at the fast polling interval.
    """
    entry = _require_entry(job_id)
    budget_remaining = max_wait_seconds

    while True:
        entry = _refresh(entry)
        job_state.save(entry)
        if entry["status"] in job_state.TERMINAL_STATUSES or entry["status"] == "unknown":
            return entry

        poll_state = entry["poll_state"]
        sleep_for = min(poll_state["interval_seconds"], budget_remaining)
        if sleep_for <= 0:
            result = dict(entry)
            result["status"] = "still_running"
            return result

        time.sleep(sleep_for)
        budget_remaining -= sleep_for
        poll_state["elapsed_seconds"] += sleep_for
        poll_state["interval_seconds"] = min(poll_state["interval_seconds"] * 2, _MAX_POLL_INTERVAL)
        job_state.save(entry)


def cancel_job(job_id: str) -> dict[str, Any]:
    """Cancel a job regardless of backend. For a local job this is the only
    option — Claude has no PID to send scancel a job id for. For a Slurm job
    it also updates our cached record so submit_and_wait/job_status agree."""
    entry = _require_entry(job_id)
    if entry["status"] in job_state.TERMINAL_STATUSES:
        return entry

    if entry["backend"] == "local":
        entry = job_state.cancel_local(entry)
    else:
        result = shell.run_foreground(["scancel", entry["slurm_job_id"]])
        if result["returncode"] != 0:
            raise RuntimeError(f"scancel failed: {result['stderr'].strip()}")
        entry["status"] = "cancelled"
        entry["updated_at"] = time.time()

    job_state.save(entry)
    return entry


def list_jobs() -> list[dict[str, Any]]:
    return job_state.list_jobs()
