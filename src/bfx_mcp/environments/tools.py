"""Discoverable registry of reusable conda/mamba/venv/docker/apptainer
environments. Claude creates the actual environment itself via the raw CLI —
this module's job is making it findable afterward instead of recreated."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bfx_mcp.common import registry

_KIND = "environment"
_VALID_MANAGERS = {"conda", "mamba", "venv", "docker", "apptainer"}
_GUIDELINES_PATH = Path(__file__).parent / "guidelines.md"


def register_environment(
    name: str,
    manager: str,
    location: str,
    spec_summary: str,
    tags: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Record metadata for an environment Claude just created, so it's
    discoverable later instead of silently recreated.

    `manager` is one of conda/mamba/venv/docker/apptainer. `location` is
    where it actually lives (a conda env path, a venv directory, an image
    tag, a .sif path) — ideally under the configured shared environments
    root so it's reusable across projects, not just this one. `spec_summary`
    is a short human-readable description of what's installed (key packages
    and versions, or a path to the spec file used to build it).
    """
    if manager not in _VALID_MANAGERS:
        raise ValueError(f"manager must be one of {sorted(_VALID_MANAGERS)}, got {manager!r}")
    return registry.register(
        _KIND,
        name,
        {
            "manager": manager,
            "location": location,
            "spec_summary": spec_summary,
            "tags": tags or [],
        },
        overwrite=overwrite,
    )


def find_environments(
    query: str | None = None, manager: str | None = None, tag: str | None = None
) -> list[dict[str, Any]]:
    """Search registered environments before creating a new one — avoids
    burning time/disk recreating something that already exists."""
    results = registry.find(_KIND, query=query, manager=manager)
    if tag:
        results = [e for e in results if tag in (e.get("tags") or [])]
    return results


def list_environments() -> list[dict[str, Any]]:
    return registry.list_all(_KIND)


def _extract_section(text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\b.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    match = pattern.search(text)
    return match.group(0).strip() if match else None


def get_environment_guidelines(manager: str | None = None) -> str:
    """Guidance on when to use conda/mamba vs. venv vs. docker vs. apptainer,
    plus known gotchas and the shared-location reuse convention. Pass a
    specific manager name (conda/mamba/venv/docker/apptainer) to get just
    that section instead of the full document."""
    text = _GUIDELINES_PATH.read_text()
    if manager is None:
        return text
    section = _extract_section(text, manager)
    if section is None:
        return (
            f"No guidelines section found for manager={manager!r}. "
            f"Known managers: {sorted(_VALID_MANAGERS)}.\n\nFull guidelines:\n\n{text}"
        )
    return section
