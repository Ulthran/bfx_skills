from bfx_mcp.common.detect import detect_capabilities


def test_detect_capabilities_reports_every_probed_binary():
    report = detect_capabilities()
    for binary in ("sbatch", "conda", "mamba", "docker", "apptainer", "singularity", "samtools"):
        assert binary in report
        entry = report[binary]
        assert set(entry) == {"available", "path", "version"}
        if not entry["available"]:
            assert entry["version"] is None


def test_detect_capabilities_available_implies_path_present():
    report = detect_capabilities()
    for entry in report.values():
        if entry["available"]:
            assert entry["path"] is not None
