# bfx-analyze — Results Analyzer

## Purpose
Parse tool outputs from a completed workflow stage, apply domain-aware QC
thresholds, flag problems, and recommend next steps. Focused on gut microbiome
metagenomics but applicable to other study types.

## Trigger
Use when:
- A workflow stage completes (called from bfx-orchestrate)
- User asks "how did the QC look", "what were the decontam rates", etc.
- Debugging a failed downstream step (poor assembly, low coverage, etc.)

---

## QC Stage Analysis (fastp)

### Parse fastp JSON reports

For each sample, read `{project_dir}/data/processed/qc/{sample}_fastp.json`.

Key fields to extract:
```json
{
  "summary": {
    "before_filtering": { "total_reads", "total_bases", "q20_rate", "q30_rate", "gc_content" },
    "after_filtering":  { "total_reads", "total_bases", "q20_rate", "q30_rate" }
  },
  "filtering_result": { "passed_filter_reads", "low_quality_reads", "too_short_reads",
                        "low_complexity_reads", "too_many_N_reads" },
  "duplication": { "rate" },
  "insert_size": { "peak" }
}
```

### Compute per-sample metrics

| Metric | Formula |
|--------|---------|
| pass_rate | `after.total_reads / before.total_reads` |
| q30_rate | `after.q30_rate` |
| duplication_rate | `duplication.rate` |
| insert_size_peak | `insert_size.peak` |
| gc_content | `before.gc_content` |
| complexity_removed_frac | `low_complexity_reads / before.total_reads` |

### Flag thresholds (from tool profile; these are gut microbiome defaults)

| Check | Threshold | Action |
|-------|-----------|--------|
| pass_rate < 0.70 | WARN | Investigate read quality; check sequencer QC |
| pass_rate < 0.50 | FAIL | Do not proceed; likely sequencing failure |
| duplication_rate > 0.50 | WARN | May indicate PCR over-amplification or low input |
| duplication_rate > 0.80 | FAIL | Library likely unusable |
| q30_rate < 0.75 | WARN | Low base quality |
| insert_size_peak < 100 | WARN | Short inserts; may indicate degradation |
| gc_content outside [35%, 75%] | WARN | Unusual GC; check for contamination |
| complexity_removed_frac > 0.20 | WARN | High low-complexity; check extraction protocol |

### Cohort-level summary

After per-sample analysis, summarize across all samples:
- Distribution of pass rates (min, median, max)
- Any outlier samples (>2 SD from cohort mean)
- Total input reads → total passing reads (yield)

**Example output:**
```
QC Summary — hmp_pilot (16 samples)
─────────────────────────────────────────────────────
Pass rate:   median=91.2%  min=78.4%  max=96.1%
Duplication: median=18.3%  max=34.2%
Q30 rate:    median=94.1%  min=88.6%
Insert size: median=285bp

WARNINGS:
  ⚠ SRR12345: pass_rate=78.4% (threshold: 80%) — low_quality_reads unusually high
  ⚠ SRR12350: duplication=34.2% — above expected for gut metagenome

FAILS: None

Recommendation: Proceed to decontamination. Monitor SRR12345 at downstream steps.
```

---

## Decontamination Stage Analysis (bwa)

### Parse flagstat files

For each sample and each reference, read
`{project_dir}/data/processed/decontam/{sample}_{ref}.flagstat`.

Extract:
- `total` reads mapped
- `mapped` count and percentage
- `properly paired` percentage

### Compute host fraction

```
host_fraction = mapped_reads / total_input_reads
surviving_reads = total_input_reads - mapped_reads
```

### Flag thresholds (gut microbiome context)

| Check | Threshold | Notes |
|-------|-----------|-------|
| human host_fraction > 0.50 | WARN | High for gut; may indicate mucosal sample or contamination |
| human host_fraction > 0.90 | FAIL | Mostly host; microbial content too low for analysis |
| phix host_fraction > 0.01 | WARN | PhiX carry-over from sequencing |
| surviving_reads < 100,000 | WARN | Low yield; may affect downstream analysis power |
| surviving_reads < 10,000 | FAIL | Insufficient reads; exclude sample |

### Gut microbiome context

Typical human gut metagenome host fractions:
- Stool: 0.1–10% human (usually <5%)
- Mucosal biopsy: 40–90% human (expected high)
- Lavage/aspirate: variable

Always ask the user what sample type this is if host fraction is unexpectedly high,
before flagging it as a problem.

**Example output:**
```
Decontamination Summary — hmp_pilot
─────────────────────────────────────────────────────
Human removal: median=2.1%  max=8.4%  min=0.3%
PhiX removal:  median=0.04% max=0.12%
Surviving reads: median=12.3M  min=8.1M  max=19.2M

WARNINGS:
  ⚠ SRR12347: human_fraction=8.4% — higher than cohort median; confirm sample type

Recommendation: Proceed to taxonomic profiling. All samples meet minimum read thresholds.
```

---

## Cross-stage summary

When called after a multi-stage workflow, provide a combined view:
- Input reads → post-QC reads → post-decontam reads (with % retained at each step)
- Flag any samples that should be excluded before downstream analysis
- Estimate statistical power: expected coverage if proceeding to taxonomy/assembly

---

## Determining next steps

Based on analysis results, recommend:

| Situation | Recommendation |
|-----------|----------------|
| All samples pass | Proceed to next planned stage |
| 1–2 samples fail | Exclude failing samples, proceed with rest; note in project.yaml |
| >20% samples fail | Stop; investigate root cause before continuing |
| High host contamination | Check if mucosal sample type; consider re-extraction |
| High duplication | Consider PCR-free library prep for future samples |
| Low insert size | Check DNA quality; degraded samples may need different assembly params |
| Low complexity high | Check bead-beating protocol; may indicate over-homogenization |
