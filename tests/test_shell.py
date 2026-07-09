import time

from bfx_mcp.common import shell


def test_write_script_is_executable_and_has_strict_mode():
    path = shell.write_script("echo hello")
    text = path.read_text()
    assert text.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert "echo hello" in text
    assert path.stat().st_mode & 0o100  # owner-executable


def test_write_script_includes_sbatch_directives():
    path = shell.write_script("echo hi", sbatch_directives=["--job-name=test", "--mem=1G"])
    text = path.read_text()
    assert "#SBATCH --job-name=test" in text
    assert "#SBATCH --mem=1G" in text
    # directives must precede the command
    assert text.index("#SBATCH") < text.index("echo hi")


def test_run_foreground_captures_stdout_and_returncode():
    result = shell.run_foreground(["echo", "hello world"])
    assert result["returncode"] == 0
    assert result["stdout"].strip() == "hello world"
    assert result["timed_out"] is False


def test_run_foreground_nonzero_exit():
    result = shell.run_foreground(["bash", "-c", "exit 3"])
    assert result["returncode"] == 3


def test_run_foreground_missing_binary_does_not_raise():
    result = shell.run_foreground(["definitely-not-a-real-binary-xyz"])
    assert result["returncode"] is None
    assert result["stderr"]


def test_run_foreground_timeout():
    result = shell.run_foreground(["sleep", "5"], timeout=0.2)
    assert result["timed_out"] is True
    assert result["returncode"] is None


def test_spawn_background_runs_and_logs(tmp_path):
    log_path = tmp_path / "job.log"
    pid = shell.spawn_background(["bash", "-c", "echo running; sleep 0.2; echo done"], log_path=log_path)
    assert pid > 0
    time.sleep(0.5)
    assert log_path.read_text() == "running\ndone\n"
