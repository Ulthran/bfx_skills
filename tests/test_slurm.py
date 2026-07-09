import time
from unittest.mock import patch

import pytest

from bfx_mcp.cluster import job_state, slurm


def _fake_run(returncode=0, stdout="", stderr=""):
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr, "timed_out": False}


# --- local placement & lifecycle (real, no mocking needed) ------------------


def test_submit_job_local_target_runs_and_completes():
    entry = slurm.submit_job("echo hello", target="local")
    assert entry["backend"] == "local"
    assert entry["status"] == "running"

    for _ in range(20):
        status = slurm.job_status(entry["job_id"])
        if status["status"] != "running":
            break
        time.sleep(0.1)

    assert status["status"] == "completed"
    assert status["returncode"] == 0


def test_submit_job_local_failure_is_reported():
    entry = slurm.submit_job("exit 7", target="local")
    for _ in range(20):
        status = slurm.job_status(entry["job_id"])
        if status["status"] != "running":
            break
        time.sleep(0.1)
    assert status["status"] == "failed"
    assert status["returncode"] == 7


def test_cancel_job_local():
    entry = slurm.submit_job("sleep 5", target="local")
    cancelled = slurm.cancel_job(entry["job_id"])
    assert cancelled["status"] == "cancelled"
    # cancelling again is a no-op, not an error
    assert slurm.cancel_job(entry["job_id"])["status"] == "cancelled"


def test_job_status_unknown_job_id_raises():
    with pytest.raises(ValueError):
        slurm.job_status("local:does-not-exist")


def test_submit_and_wait_returns_still_running_within_small_budget():
    entry = slurm.submit_job("sleep 2", target="local")
    result = slurm.submit_and_wait(entry["job_id"], max_wait_seconds=0.3)
    assert result["status"] == "still_running"
    slurm.cancel_job(entry["job_id"])


def test_submit_and_wait_returns_completed_when_job_finishes_in_budget():
    entry = slurm.submit_job("echo hi", target="local")
    result = slurm.submit_and_wait(entry["job_id"], max_wait_seconds=5)
    assert result["status"] == "completed"


def test_submit_and_wait_backoff_persists_between_calls():
    entry = slurm.submit_job("sleep 5", target="local")
    first = slurm.submit_and_wait(entry["job_id"], max_wait_seconds=0.2)
    second = slurm.submit_and_wait(entry["job_id"], max_wait_seconds=0.2)
    assert second["poll_state"]["elapsed_seconds"] > first["poll_state"]["elapsed_seconds"]
    slurm.cancel_job(entry["job_id"])


# --- placement heuristic ------------------------------------------------


def test_auto_places_locally_when_slurm_unavailable():
    with patch("bfx_mcp.cluster.slurm.detect_capabilities") as mock_detect:
        mock_detect.return_value = {"sbatch": {"available": False}}
        entry = slurm.submit_job("echo hi", target="auto", cpus=64, mem_gb=200)
    assert entry["backend"] == "local"


def test_auto_places_on_cluster_when_resources_exceed_local_ceiling():
    with patch("bfx_mcp.cluster.slurm.detect_capabilities") as mock_detect, patch(
        "bfx_mcp.cluster.slurm.shell.run_foreground"
    ) as mock_run:
        mock_detect.return_value = {"sbatch": {"available": True}}
        mock_run.return_value = _fake_run(stdout="Submitted batch job 4242\n")
        entry = slurm.submit_job("echo hi", target="auto", cpus=999, mem_gb=None)
    assert entry["backend"] == "slurm"
    assert entry["slurm_job_id"] == "4242"


def test_auto_stays_local_for_modest_resources_even_if_slurm_available():
    with patch("bfx_mcp.cluster.slurm.detect_capabilities") as mock_detect:
        mock_detect.return_value = {"sbatch": {"available": True}}
        entry = slurm.submit_job("echo hi", target="auto", cpus=1)
    assert entry["backend"] == "local"


def test_cluster_target_without_slurm_raises_clear_error_not_silent_fallback():
    with patch("bfx_mcp.cluster.slurm.detect_capabilities") as mock_detect:
        mock_detect.return_value = {"sbatch": {"available": False}}
        with pytest.raises(RuntimeError, match="no Slurm tooling"):
            slurm.submit_job("echo hi", target="cluster")


def test_invalid_target_raises():
    with pytest.raises(ValueError):
        slurm._decide_backend("bogus", cpus=1, mem_gb=None, slurm_available=True)


# --- slurm backend, fully mocked -----------------------------------------


def test_submit_job_cluster_parses_job_id_and_builds_directives():
    with patch("bfx_mcp.cluster.slurm.shell.run_foreground") as mock_run:
        mock_run.return_value = _fake_run(stdout="Submitted batch job 555\n")
        entry = slurm.submit_job(
            "echo hi",
            target="cluster",
            cpus=8,
            mem_gb=32,
            time_limit="24:00:00",
            job_name="qc-run",
            partition="general",
        )
    assert entry["backend"] == "slurm"
    assert entry["slurm_job_id"] == "555"

    script_path = entry["script_path"]
    script_text = open(script_path).read()
    assert "#SBATCH --cpus-per-task=8" in script_text
    assert "#SBATCH --job-name=qc-run" in script_text
    assert "#SBATCH --mem=32G" in script_text
    assert "#SBATCH --time=24:00:00" in script_text
    assert "#SBATCH --partition=general" in script_text


def test_submit_job_cluster_sbatch_failure_raises():
    with patch("bfx_mcp.cluster.slurm.shell.run_foreground") as mock_run:
        mock_run.return_value = _fake_run(returncode=1, stderr="sbatch: error: bad partition")
        with pytest.raises(RuntimeError, match="sbatch failed"):
            slurm.submit_job("echo hi", target="cluster")


def test_job_status_slurm_running_via_squeue():
    entry = job_state.create_slurm_job_entry("999", "echo hi", metadata={})
    with patch("bfx_mcp.cluster.slurm.shell.run_foreground") as mock_run:
        mock_run.return_value = _fake_run(stdout="RUNNING\n")
        status = slurm.job_status("slurm:999")
    assert status["status"] == "running"


def test_job_status_slurm_completed_falls_back_to_sacct_when_not_in_queue():
    entry = job_state.create_slurm_job_entry("888", "echo hi", metadata={})
    with patch("bfx_mcp.cluster.slurm.shell.run_foreground") as mock_run:
        mock_run.side_effect = [
            _fake_run(returncode=0, stdout=""),  # squeue: not found, empty
            _fake_run(returncode=0, stdout="COMPLETED\n"),  # sacct
        ]
        status = slurm.job_status("slurm:888")
    assert status["status"] == "completed"


def test_cancel_job_slurm_calls_scancel():
    job_state.create_slurm_job_entry("777", "echo hi", metadata={})
    with patch("bfx_mcp.cluster.slurm.shell.run_foreground") as mock_run:
        mock_run.return_value = _fake_run(returncode=0)
        result = slurm.cancel_job("slurm:777")
    assert result["status"] == "cancelled"
    mock_run.assert_called_once_with(["scancel", "777"])
