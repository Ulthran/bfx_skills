#!/usr/bin/env python3
"""
watch_job.py — Background job watcher for bfx-skills workflows.

Polls a running Snakemake workflow (local PID or SLURM job IDs) and writes
status updates to the project's workflow/state.yaml.

Usage:
    python watch_job.py --project /path/to/project [--interval 60]

The watcher exits automatically when the workflow reaches a terminal state
(complete, failed, cancelled).
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state(state_path: Path) -> dict:
    with open(state_path) as f:
        return yaml.safe_load(f) or {}


def save_state(state_path: Path, state: dict) -> None:
    tmp = state_path.with_suffix(".yaml.tmp")
    with open(tmp, "w") as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=False)
    tmp.replace(state_path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Snakemake log parsing
# ---------------------------------------------------------------------------

def tail_log(log_path: Path, n: int = 40) -> list[str]:
    if not log_path.exists():
        return []
    with open(log_path) as f:
        lines = f.readlines()
    return [l.rstrip() for l in lines[-n:]]


def snakemake_summary(workflow_dir: Path) -> dict:
    """Run `snakemake --summary` to get job counts."""
    result = {"total": 0, "done": 0, "failed": 0, "pending": 0}
    try:
        out = subprocess.check_output(
            ["snakemake", "--summary", "--quiet"],
            cwd=workflow_dir,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
        for line in out.splitlines()[1:]:   # skip header
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            result["total"] += 1
            status = parts[2].strip().lower()
            if status == "ok":
                result["done"] += 1
            elif "missing" in status or "updated" in status:
                result["pending"] += 1
            elif "failed" in status:
                result["failed"] += 1
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return result


# ---------------------------------------------------------------------------
# Local PID monitoring
# ---------------------------------------------------------------------------

def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def check_local(state: dict, workflow_dir: Path) -> dict:
    pid = state.get("snakemake_pid")
    if pid and not pid_alive(int(pid)):
        # Process ended — check if outputs exist to distinguish complete vs failed
        summary = snakemake_summary(workflow_dir)
        if summary["failed"] > 0:
            state["status"] = "failed"
            state["fail_reason"] = f"{summary['failed']} rule(s) failed"
        elif summary["pending"] == 0 and summary["total"] > 0:
            state["status"] = "complete"
        else:
            state["status"] = "failed"
            state["fail_reason"] = "snakemake process exited with pending jobs"
        state["ended"] = now_iso()
    else:
        summary = snakemake_summary(workflow_dir)
        state["progress"] = summary
        state["last_checked"] = now_iso()
    return state


# ---------------------------------------------------------------------------
# SLURM monitoring
# ---------------------------------------------------------------------------

def check_slurm(state: dict, workflow_dir: Path) -> dict:
    job_ids = state.get("slurm_job_ids", [])
    if not job_ids:
        return state

    try:
        out = subprocess.check_output(
            ["squeue", "--jobs", ",".join(str(j) for j in job_ids),
             "--format=%i %T", "--noheader"],
            text=True,
            timeout=15,
            stderr=subprocess.DEVNULL,
        )
        slurm_states = {}
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) == 2:
                slurm_states[parts[0]] = parts[1]
        state["slurm_states"] = slurm_states
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Also get overall Snakemake progress
    summary = snakemake_summary(workflow_dir)
    state["progress"] = summary
    state["last_checked"] = now_iso()

    if summary["failed"] > 0:
        state["status"] = "failed"
        state["fail_reason"] = f"{summary['failed']} rule(s) failed"
        state["ended"] = now_iso()
    elif summary["pending"] == 0 and summary["total"] > 0:
        state["status"] = "complete"
        state["ended"] = now_iso()

    return state


# ---------------------------------------------------------------------------
# Log summary written to state for quick inspection
# ---------------------------------------------------------------------------

def update_log_summary(state: dict, log_path: Path) -> dict:
    lines = tail_log(log_path)
    if lines:
        state["log_tail"] = lines
    # Look for error markers
    errors = [l for l in lines if any(k in l.lower() for k in ("error", "exception", "failed", "killed"))]
    if errors:
        state["log_errors"] = errors[-5:]
    return state


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="BFX workflow watcher")
    parser.add_argument("--project", required=True, help="Path to project directory")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    args = parser.parse_args()

    project_dir = Path(args.project).expanduser().resolve()
    state_path = project_dir / "workflow" / "state.yaml"
    workflow_dir = project_dir / "workflow"
    log_path = project_dir / "logs" / "snakemake.log"

    if not state_path.exists():
        print(f"ERROR: state.yaml not found at {state_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[watch_job] Watching project: {project_dir}")
    print(f"[watch_job] State file: {state_path}")
    print(f"[watch_job] Poll interval: {args.interval}s")

    terminal_states = {"complete", "failed", "cancelled"}

    def handle_sigterm(signum, frame):
        state = load_state(state_path)
        state["watcher_status"] = "stopped"
        save_state(state_path, state)
        print("[watch_job] Received SIGTERM, exiting.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)

    while True:
        try:
            state = load_state(state_path)

            if state.get("status") in terminal_states:
                print(f"[watch_job] Workflow reached terminal state: {state['status']}. Exiting.")
                break

            backend = state.get("backend", "local")
            if backend == "slurm":
                state = check_slurm(state, workflow_dir)
            else:
                state = check_local(state, workflow_dir)

            state = update_log_summary(state, log_path)
            save_state(state_path, state)

            progress = state.get("progress", {})
            print(
                f"[watch_job] {now_iso()} | status={state['status']} | "
                f"done={progress.get('done', '?')}/{progress.get('total', '?')} | "
                f"failed={progress.get('failed', 0)}"
            )

            if state.get("status") in terminal_states:
                print(f"[watch_job] Terminal state reached: {state['status']}. Exiting.")
                break

        except Exception as exc:
            print(f"[watch_job] WARNING: poll error: {exc}", file=sys.stderr)

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
