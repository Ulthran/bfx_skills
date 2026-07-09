import pytest

from bfx_mcp.common import registry


def test_register_and_get_round_trip():
    registry.register("environment", "qc-env", {"manager": "conda", "location": "/envs/qc-env"})
    entry = registry.get("environment", "qc-env")
    assert entry["name"] == "qc-env"
    assert entry["manager"] == "conda"
    assert "created_at" in entry
    assert "updated_at" in entry


def test_get_missing_returns_none():
    assert registry.get("environment", "does-not-exist") is None


def test_register_duplicate_without_overwrite_raises():
    registry.register("database", "kraken2-std", {"kind": "kraken2_db"})
    with pytest.raises(ValueError):
        registry.register("database", "kraken2-std", {"kind": "kraken2_db"})


def test_register_duplicate_with_overwrite_updates_and_preserves_created_at():
    first = registry.register("database", "kraken2-std", {"version": "1"})
    second = registry.register("database", "kraken2-std", {"version": "2"}, overwrite=True)
    assert second["version"] == "2"
    assert second["created_at"] == first["created_at"]
    assert second["updated_at"] >= first["updated_at"]


def test_list_all_returns_every_entry():
    registry.register("environment", "a", {"manager": "conda"})
    registry.register("environment", "b", {"manager": "venv"})
    names = {e["name"] for e in registry.list_all("environment")}
    assert names == {"a", "b"}


def test_kinds_are_isolated_from_each_other():
    registry.register("environment", "shared-name", {"manager": "conda"})
    registry.register("database", "shared-name", {"kind": "host_genome"})
    assert registry.get("environment", "shared-name")["manager"] == "conda"
    assert registry.get("database", "shared-name")["kind"] == "host_genome"


def test_find_by_exact_filter():
    registry.register("environment", "conda-a", {"manager": "conda", "tags": ["qc"]})
    registry.register("environment", "venv-a", {"manager": "venv", "tags": ["qc"]})
    results = registry.find("environment", manager="conda")
    assert [e["name"] for e in results] == ["conda-a"]


def test_find_by_query_substring_matches_name_and_tags():
    registry.register(
        "database", "hg38-host", {"kind": "host_genome", "tags": ["human", "grch38"]}
    )
    registry.register("database", "kraken2-std", {"kind": "kraken2_db", "tags": ["taxonomy"]})

    assert [e["name"] for e in registry.find("database", query="grch38")] == ["hg38-host"]
    assert [e["name"] for e in registry.find("database", query="taxonomy")] == ["kraken2-std"]
    assert registry.find("database", query="nonexistent") == []
