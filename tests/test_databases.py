import pytest

from bfx_mcp.databases import tools as databases


def test_register_database_invalid_version_check_type_raises():
    with pytest.raises(ValueError):
        databases.register_database(
            "hg38",
            "host_genome",
            "/db/hg38",
            "GRCh38",
            version_check={"type": "carrier-pigeon", "spec": "x"},
        )


def test_register_database_missing_spec_raises():
    with pytest.raises(ValueError):
        databases.register_database(
            "hg38", "host_genome", "/db/hg38", "GRCh38", version_check={"type": "command"}
        )


def test_register_find_list_round_trip():
    databases.register_database(
        "hg38-host", "host_genome", "/db/hg38", "GRCh38", tags=["human"]
    )
    databases.register_database(
        "kraken2-std", "kraken2_db", "/db/kraken2-std", "2024-06-05", tags=["taxonomy"]
    )

    assert {e["name"] for e in databases.list_databases()} == {"hg38-host", "kraken2-std"}

    by_kind = databases.find_databases(kind="kraken2_db")
    assert [e["name"] for e in by_kind] == ["kraken2-std"]

    by_tag = databases.find_databases(tag="human")
    assert [e["name"] for e in by_tag] == ["hg38-host"]

    by_query = databases.find_databases(query="GRCh38")
    assert [e["name"] for e in by_query] == ["hg38-host"]


def test_check_for_updates_unknown_database_raises():
    with pytest.raises(ValueError):
        databases.check_for_updates("does-not-exist")


def test_check_for_updates_no_version_check_registered():
    databases.register_database("custom-db", "custom", "/db/custom", "v1")
    result = databases.check_for_updates("custom-db")
    assert result["checked"] is False
    assert result["recorded_version"] == "v1"


def test_check_for_updates_command_type_detects_no_difference():
    databases.register_database(
        "custom-db",
        "custom",
        "/db/custom",
        "v1",
        version_check={"type": "command", "spec": "echo v1"},
    )
    result = databases.check_for_updates("custom-db")
    assert result["checked"] is True
    assert result["fetched_value"] == "v1"
    assert result["differs"] is False


def test_check_for_updates_command_type_detects_difference():
    databases.register_database(
        "custom-db",
        "custom",
        "/db/custom",
        "v1",
        version_check={"type": "command", "spec": "echo v2"},
    )
    result = databases.check_for_updates("custom-db")
    assert result["differs"] is True
    assert result["fetched_value"] == "v2"


def test_check_for_updates_command_failure_is_reported_not_raised():
    databases.register_database(
        "custom-db",
        "custom",
        "/db/custom",
        "v1",
        version_check={"type": "command", "spec": "exit 1"},
    )
    result = databases.check_for_updates("custom-db")
    assert result["checked"] is False
    assert result["fetched_value"] is None
    assert result["error"]


def test_get_database_conventions_mentions_shared_location():
    text = databases.get_database_conventions()
    assert "databases.root" in text
