"""Discoverable registry of reference databases (host genomes, Kraken2/
HUMAnN/MetaPhlAn DBs, custom marker sets, ...), plus a generic pluggable
check for whether a newer version exists upstream."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from bfx_mcp.common import registry
from bfx_mcp.common.shell import run_foreground

_KIND = "database"
_VALID_VERSION_CHECK_TYPES = {"url", "command"}
_CONVENTIONS_PATH = Path(__file__).parent / "conventions.md"
_URL_FETCH_TIMEOUT = 15
_URL_FETCH_MAX_CHARS = 2000


def register_database(
    name: str,
    kind: str,
    location: str,
    version: str,
    source_url: str | None = None,
    version_check: dict[str, str] | None = None,
    tags: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Record metadata for a reference database, so it's discoverable and
    versioned instead of silently re-downloaded per project.

    `kind` is a free-text category (host_genome, kraken2_db, humann_db,
    custom, ...) — not restricted to a fixed list, since reference databases
    in this space are heterogeneous. `version_check`, if provided, is
    `{"type": "url"|"command", "spec": "..."}` describing how to later check
    for a newer version (see get_database_conventions() for the full
    convention).
    """
    if version_check is not None:
        vc_type = version_check.get("type")
        if vc_type not in _VALID_VERSION_CHECK_TYPES:
            raise ValueError(
                f"version_check['type'] must be one of {sorted(_VALID_VERSION_CHECK_TYPES)}, "
                f"got {vc_type!r}"
            )
        if not version_check.get("spec"):
            raise ValueError("version_check['spec'] is required when version_check is provided")

    return registry.register(
        _KIND,
        name,
        {
            "db_kind": kind,
            "location": location,
            "version": version,
            "source_url": source_url,
            "version_check": version_check,
            "tags": tags or [],
        },
        overwrite=overwrite,
    )


def find_databases(
    query: str | None = None, kind: str | None = None, tag: str | None = None
) -> list[dict[str, Any]]:
    """Search registered reference databases before downloading or building
    a new one — these are typically large and slow to (re)create."""
    results = registry.find(_KIND, query=query, db_kind=kind)
    if tag:
        results = [e for e in results if tag in (e.get("tags") or [])]
    return results


def list_databases() -> list[dict[str, Any]]:
    return registry.list_all(_KIND)


def _fetch_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=_URL_FETCH_TIMEOUT) as response:  # noqa: S310
        body = response.read(_URL_FETCH_MAX_CHARS + 1)
    text = body.decode("utf-8", errors="replace")
    return text[:_URL_FETCH_MAX_CHARS]


def check_for_updates(name: str) -> dict[str, Any]:
    """Check whether a registered database has a newer version available.

    Generic and pluggable: runs whatever `version_check` was registered
    (fetch a URL or run a command) and returns the recorded version next to
    the freshly fetched value. Does not parse or compare version formats —
    those vary too much across genome/taxonomy DB sources to do reliably;
    interpret the diff yourself.
    """
    entry = registry.get(_KIND, name)
    if entry is None:
        raise ValueError(f"No database registered with name {name!r} (check list_databases())")

    version_check = entry.get("version_check")
    if not version_check:
        return {
            "name": name,
            "recorded_version": entry["version"],
            "checked": False,
            "message": "No version_check was registered for this database — nothing to compare against.",
        }

    vc_type = version_check["type"]
    spec = version_check["spec"]

    if vc_type == "url":
        try:
            fetched_value = _fetch_url(spec)
            error = None
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            fetched_value = None
            error = str(exc)
    else:
        result = run_foreground(["bash", "-c", spec], timeout=_URL_FETCH_TIMEOUT)
        if result["returncode"] == 0:
            fetched_value = result["stdout"].strip()
            error = None
        else:
            fetched_value = None
            error = result["stderr"].strip() or f"command exited {result['returncode']}"

    return {
        "name": name,
        "recorded_version": entry["version"],
        "fetched_value": fetched_value,
        "checked": error is None,
        "error": error,
        "checked_at": time.time(),
        "differs": (
            fetched_value is not None and fetched_value.strip() != str(entry["version"]).strip()
        ),
    }


def get_database_conventions() -> str:
    """Guidance on the reference-database manifest schema, the shared
    storage location convention, and how the version_check mechanism works."""
    return _CONVENTIONS_PATH.read_text()
