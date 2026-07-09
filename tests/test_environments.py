import pytest

from bfx_mcp.environments import tools as environments


def test_register_environment_invalid_manager_raises():
    with pytest.raises(ValueError):
        environments.register_environment("x", "not-a-real-manager", "/tmp/x", "spec")


def test_register_find_list_round_trip():
    environments.register_environment(
        "bfx-qc",
        "conda",
        "/envs/bfx-qc",
        "fastp=0.23.4, samtools=1.13",
        tags=["qc", "fastp"],
    )
    environments.register_environment(
        "bfx-assembly",
        "docker",
        "myorg/assembly:latest",
        "megahit=1.2.9",
        tags=["assembly"],
    )

    assert {e["name"] for e in environments.list_environments()} == {"bfx-qc", "bfx-assembly"}

    by_manager = environments.find_environments(manager="conda")
    assert [e["name"] for e in by_manager] == ["bfx-qc"]

    by_tag = environments.find_environments(tag="assembly")
    assert [e["name"] for e in by_tag] == ["bfx-assembly"]

    by_query = environments.find_environments(query="fastp")
    assert [e["name"] for e in by_query] == ["bfx-qc"]


def test_get_environment_guidelines_full_document_mentions_every_manager():
    text = environments.get_environment_guidelines()
    for manager in ("conda", "mamba", "venv", "docker", "apptainer"):
        assert manager in text.lower()


def test_get_environment_guidelines_single_manager_section():
    text = environments.get_environment_guidelines("docker")
    assert text.lower().startswith("## docker")
    assert "conda" not in text.split("\n", 1)[0].lower()


def test_get_environment_guidelines_unknown_manager_falls_back_gracefully():
    text = environments.get_environment_guidelines("not-a-manager")
    assert "No guidelines section found" in text


# --- real conda round trip, since conda is actually installed here ------


def test_registering_a_real_local_conda_env_is_discoverable(tmp_path):
    import subprocess

    env_path = tmp_path / "bfx-mcp-test-env"
    result = subprocess.run(
        ["conda", "create", "-y", "-p", str(env_path), "python=3.11"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

    environments.register_environment(
        "bfx-mcp-test-env", "conda", str(env_path), "python=3.11"
    )
    found = environments.find_environments(query="bfx-mcp-test-env")
    assert len(found) == 1
    assert found[0]["location"] == str(env_path)

    subprocess.run(["conda", "env", "remove", "-y", "-p", str(env_path)], capture_output=True)
