#!/usr/bin/env python3
"""
assess_data.py — FASTQ data assessment for bfx-skills init.

Scans a directory for FASTQ files, detects naming conventions, pairs R1/R2,
and produces a samples.tsv and a human-readable assessment report.

Usage:
    python assess_data.py --data-dir /path/to/fastqs [--output-tsv samples.tsv]

Exit codes:
    0  all samples paired cleanly
    1  warnings (unpaired files, ambiguous names) — review report
    2  error (no FASTQ files found, fatal issue)
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Known FASTQ extensions (in priority order for stripping)
# ---------------------------------------------------------------------------
FASTQ_EXTENSIONS = [
    ".fastq.gz", ".fq.gz", ".fastq.bz2", ".fq.bz2", ".fastq", ".fq"
]

# Patterns that identify R1 / R2 in filenames, in priority order.
# Each entry: (regex to find read tag, group name for sample stem, r1_tag, r2_tag)
PAIR_PATTERNS = [
    # Illumina standard: _R1_001 / _R2_001
    (r"(.+?)_R([12])_001$",        "illumina_001"),
    # Simple _R1 / _R2
    (r"(.+?)_R([12])$",            "simple_R"),
    # _1 / _2
    (r"(.+?)_([12])$",             "simple_numeric"),
    # .R1 / .R2 (dot separator)
    (r"(.+?)\.R([12])$",           "dot_R"),
    # _read1 / _read2
    (r"(.+?)_read([12])$",         "read_word"),
]


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_fastqs(data_dir: Path) -> list[Path]:
    files = []
    for ext in FASTQ_EXTENSIONS:
        files.extend(data_dir.glob(f"*{ext}"))
    return sorted(set(files))


def strip_extension(name: str) -> str:
    for ext in FASTQ_EXTENSIONS:
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

def detect_pair_pattern(stems: list[str]) -> tuple[str | None, str | None]:
    """
    Given a list of filename stems (extension stripped), return the
    (pattern_name, regex) that matches the most files.
    """
    scores = {}
    for pattern, name in PAIR_PATTERNS:
        count = sum(1 for s in stems if re.match(pattern, s))
        scores[name] = (count, pattern)

    best_name = max(scores, key=lambda k: scores[k][0])
    best_count, best_pattern = scores[best_name]
    if best_count == 0:
        return None, None
    return best_name, best_pattern


# ---------------------------------------------------------------------------
# Pairing
# ---------------------------------------------------------------------------

def pair_samples(files: list[Path], pattern: str) -> dict:
    """
    Returns dict: {sample_id: {"R1": Path, "R2": Path}}
    Also returns lists of unpaired and ambiguous files.
    """
    pairs: dict[str, dict] = defaultdict(dict)
    unmatched = []

    for f in files:
        stem = strip_extension(f.name)
        m = re.match(pattern, stem)
        if not m:
            unmatched.append(f)
            continue
        sample = m.group(1)
        read_num = m.group(2)
        key = "R1" if read_num == "1" else "R2"
        if key in pairs[sample]:
            # Collision — two files claim to be the same sample+read
            pairs[sample][f"COLLISION_{key}"] = f
        else:
            pairs[sample][key] = f

    complete = {s: d for s, d in pairs.items() if "R1" in d and "R2" in d}
    r1_only  = {s: d for s, d in pairs.items() if "R1" in d and "R2" not in d}
    r2_only  = {s: d for s, d in pairs.items() if "R2" in d and "R1" not in d}
    collision = {s: d for s, d in pairs.items() if any("COLLISION" in k for k in d)}

    return {
        "complete": complete,
        "r1_only":  r1_only,
        "r2_only":  r2_only,
        "collision": collision,
        "unmatched": unmatched,
    }


# ---------------------------------------------------------------------------
# Size checks
# ---------------------------------------------------------------------------

def check_sizes(pairs: dict[str, dict]) -> list[str]:
    """Flag suspiciously small files (<1 MB)."""
    warnings = []
    for sample, files in pairs.items():
        for key in ("R1", "R2"):
            f = files.get(key)
            if f and f.stat().st_size < 1_000_000:
                size_kb = f.stat().st_size // 1024
                warnings.append(f"{sample} {key}: only {size_kb} KB — verify file integrity")
    return warnings


# ---------------------------------------------------------------------------
# TSV output
# ---------------------------------------------------------------------------

def write_tsv(complete_pairs: dict, output_path: Path) -> None:
    with open(output_path, "w") as f:
        f.write("sample\tR1\tR2\n")
        for sample in sorted(complete_pairs):
            r1 = complete_pairs[sample]["R1"]
            r2 = complete_pairs[sample]["R2"]
            f.write(f"{sample}\t{r1.resolve()}\t{r2.resolve()}\n")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(
    data_dir: Path,
    pattern_name: str | None,
    result: dict,
    size_warnings: list[str],
) -> tuple[str, int]:
    lines = []
    lines.append(f"Data Assessment: {data_dir}")
    lines.append("=" * 60)

    total_files = (
        len(result["complete"]) * 2
        + len(result["r1_only"])
        + len(result["r2_only"])
        + len(result["unmatched"])
    )
    lines.append(f"FASTQ files found : {total_files}")
    lines.append(f"Naming convention : {pattern_name or 'UNKNOWN'}")
    lines.append(f"Complete pairs    : {len(result['complete'])}")

    exit_code = 0

    if result["r1_only"] or result["r2_only"]:
        lines.append("")
        lines.append("WARNINGS — unpaired files:")
        for s in result["r1_only"]:
            lines.append(f"  R1 only (no R2): {s}")
        for s in result["r2_only"]:
            lines.append(f"  R2 only (no R1): {s}")
        exit_code = 1

    if result["collision"]:
        lines.append("")
        lines.append("WARNINGS — multiple files match same sample+read:")
        for s in result["collision"]:
            lines.append(f"  {s}: {result['collision'][s]}")
        exit_code = 1

    if result["unmatched"]:
        lines.append("")
        lines.append("WARNINGS — files not matched by detected pattern:")
        for f in result["unmatched"]:
            lines.append(f"  {f.name}")
        exit_code = 1

    if size_warnings:
        lines.append("")
        lines.append("WARNINGS — suspiciously small files:")
        for w in size_warnings:
            lines.append(f"  {w}")
        exit_code = 1

    if not result["complete"] and not result["r1_only"]:
        lines.append("")
        lines.append("ERROR: No FASTQ files found in directory.")
        exit_code = 2

    lines.append("")
    if exit_code == 0:
        lines.append("✓ All samples paired cleanly.")
    elif exit_code == 1:
        lines.append("⚠ Warnings detected — review before proceeding.")
    else:
        lines.append("✗ Fatal errors — fix before running init-bfx.")

    return "\n".join(lines), exit_code


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Assess FASTQ data for bfx-skills")
    parser.add_argument("--data-dir", required=True, help="Directory containing FASTQ files")
    parser.add_argument("--output-tsv", default="samples.tsv", help="Output samples TSV path")
    parser.add_argument("--json", action="store_true", help="Also write machine-readable JSON summary")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    if not data_dir.exists():
        print(f"ERROR: {data_dir} does not exist.", file=sys.stderr)
        sys.exit(2)

    files = find_fastqs(data_dir)
    if not files:
        print(f"ERROR: No FASTQ files found in {data_dir}", file=sys.stderr)
        sys.exit(2)

    stems = [strip_extension(f.name) for f in files]
    pattern_name, pattern = detect_pair_pattern(stems)

    if pattern is None:
        print("ERROR: Could not detect a known R1/R2 naming pattern.", file=sys.stderr)
        print("Expected one of: _R1/_R2, _1/_2, _R1_001/_R2_001, .R1/.R2", file=sys.stderr)
        sys.exit(2)

    result = pair_samples(files, pattern)
    size_warnings = check_sizes(result["complete"])

    report, exit_code = build_report(data_dir, pattern_name, result, size_warnings)
    print(report)

    if result["complete"]:
        write_tsv(result["complete"], Path(args.output_tsv))
        print(f"\nSamples TSV written: {args.output_tsv}")
        print(f"  {len(result['complete'])} samples × 2 reads")

    if args.json:
        import json
        summary = {
            "data_dir": str(data_dir),
            "pattern": pattern_name,
            "n_complete_pairs": len(result["complete"]),
            "n_r1_only": len(result["r1_only"]),
            "n_r2_only": len(result["r2_only"]),
            "n_unmatched": len(result["unmatched"]),
            "size_warnings": size_warnings,
            "samples": {
                s: {"R1": str(d["R1"]), "R2": str(d["R2"])}
                for s, d in result["complete"].items()
            },
        }
        json_path = Path(args.output_tsv).with_suffix(".json")
        json_path.write_text(json.dumps(summary, indent=2))
        print(f"JSON summary written: {json_path}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
