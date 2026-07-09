"""Instructional guidance for validating pipeline outputs — not operational
wrappers. Claude already has direct access to samtools/fastp/seff; this
module only supplies the judgment (which thresholds matter, and why)."""

from __future__ import annotations

import re
from pathlib import Path

_GUIDE_PATH = Path(__file__).parent / "output_validation.md"
_VALID_FILE_TYPES = {"fastq", "bam", "slurm_job"}


def _extract_section(text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\b.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    match = pattern.search(text)
    return match.group(0).strip() if match else None


def get_output_validation_guide(file_type: str | None = None) -> str:
    """Guidance on what to check and which thresholds apply for a given
    output type, before trusting it and moving on to the next pipeline
    stage.

    `file_type` is one of "fastq" (post-QC reads), "bam" (post-alignment/
    decontam), or "slurm_job" (completed job resource efficiency). Omit it
    to get the full guide across all three. This only tells you what to run
    and how to interpret it — run the actual command (samtools, fastp's
    JSON report, seff) yourself.
    """
    text = _GUIDE_PATH.read_text()
    if file_type is None:
        return text
    section = _extract_section(text, file_type)
    if section is None:
        return (
            f"No validation guidance found for file_type={file_type!r}. "
            f"Known types: {sorted(_VALID_FILE_TYPES)}.\n\nFull guide:\n\n{text}"
        )
    return section
