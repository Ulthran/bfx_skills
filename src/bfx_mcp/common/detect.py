"""Probes for what bioinformatics-relevant tooling is actually on PATH."""

from __future__ import annotations

import shutil
import subprocess

# Binary -> args to get a version string. sbatch alone stands in for "Slurm is
# usable" — real Slurm installs ship srun/squeue/scancel/sinfo alongside it.
_PROBES: dict[str, list[str]] = {
    "sbatch": ["--version"],
    "conda": ["--version"],
    "mamba": ["--version"],
    "docker": ["--version"],
    "apptainer": ["--version"],
    "singularity": ["--version"],
    "samtools": ["--version"],
}


def _run_version_check(binary: str, args: list[str]) -> tuple[bool, str | None]:
    """Actually run the binary rather than trusting PATH presence.

    On WSL, Windows executables (e.g. Docker Desktop's docker.exe shim) can
    show up on PATH via interop yet fail at runtime ("could not be found in
    this WSL distro"), so a successful exit code is the real signal.
    """
    try:
        result = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, None
    if result.returncode != 0:
        return False, None
    output = (result.stdout or result.stderr or "").strip().splitlines()
    version = output[0] if output else None
    return True, version


def detect_capabilities() -> dict[str, dict]:
    """Report which relevant CLI tools are installed and actually runnable.

    Returns a mapping of binary name to {"available": bool, "path": str|None,
    "version": str|None}. Intended as the first call before attempting Slurm
    job submission, environment/container management, or samtools-based
    validation, rather than guessing at what's present.
    """
    report: dict[str, dict] = {}
    for binary, version_args in _PROBES.items():
        path = shutil.which(binary)
        if path is None:
            report[binary] = {"available": False, "path": None, "version": None}
            continue
        available, version = _run_version_check(binary, version_args)
        report[binary] = {"available": available, "path": path, "version": version}
    return report
