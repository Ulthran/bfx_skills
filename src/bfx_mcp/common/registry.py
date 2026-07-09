"""Generic index of reusable, durable assets (environments, databases).

Each `kind` (e.g. "environment", "database") gets its own JSON file of
entries under the configured registry directory. This is the actual value a
raw CLI can't provide: a discoverable, queryable record of "what reusable
things already exist and where," so callers can check before recreating
something that's already there.

Not used for ephemeral job state — see cluster/job_state.py for that.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from bfx_mcp.common.config import load_config


def _store_path(kind: str) -> Path:
    return load_config().registry_dir / f"{kind}.json"


def _read_all(kind: str) -> list[dict[str, Any]]:
    path = _store_path(kind)
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _write_all(kind: str, entries: list[dict[str, Any]]) -> None:
    path = _store_path(kind)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(entries, f, indent=2, sort_keys=True)
    tmp.replace(path)


def register(kind: str, name: str, metadata: dict[str, Any], *, overwrite: bool = False) -> dict[str, Any]:
    """Record a new asset, or update an existing one if overwrite=True."""
    entries = _read_all(kind)
    now = time.time()
    existing_index = next((i for i, e in enumerate(entries) if e["name"] == name), None)

    if existing_index is not None and not overwrite:
        raise ValueError(
            f"{kind} '{name}' is already registered "
            f"(pass overwrite=True to replace it, or pick a different name)"
        )

    entry = {"name": name, "kind": kind, **metadata}
    entry.setdefault("created_at", now)
    entry["updated_at"] = now

    if existing_index is not None:
        entry["created_at"] = entries[existing_index].get("created_at", now)
        entries[existing_index] = entry
    else:
        entries.append(entry)

    _write_all(kind, entries)
    return entry


def get(kind: str, name: str) -> dict[str, Any] | None:
    return next((e for e in _read_all(kind) if e["name"] == name), None)


def list_all(kind: str) -> list[dict[str, Any]]:
    return _read_all(kind)


def find(kind: str, query: str | None = None, **filters: Any) -> list[dict[str, Any]]:
    """Search entries. `filters` must match exactly; `query` substring-matches
    against name, tags, and any string-valued field."""
    results = _read_all(kind)

    for key, value in filters.items():
        if value is None:
            continue
        results = [e for e in results if e.get(key) == value]

    if query:
        needle = query.lower()

        def matches(entry: dict[str, Any]) -> bool:
            haystacks = [str(entry.get("name", ""))]
            tags = entry.get("tags") or []
            haystacks.extend(str(t) for t in tags)
            haystacks.extend(str(v) for v in entry.values() if isinstance(v, str))
            return any(needle in h.lower() for h in haystacks)

        results = [e for e in results if matches(e)]

    return results
