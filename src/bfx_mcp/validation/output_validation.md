# Output validation guide

Quick checks to run whenever a pipeline stage produces output, before
trusting it and moving on. Run the actual command yourself (samtools,
fastp's own JSON report, `seff`, ...); this is judgment about what the
numbers mean, not a wrapper around running them.

## fastq (post-QC, e.g. fastp output)

Read `fastp`'s own JSON report (`--json`) rather than re-deriving these by
hand. Key fields and flags:

| Metric | Field | WARN | FAIL |
|---|---|---|---|
| Pass rate | `after_filtering.total_reads / before_filtering.total_reads` | <0.70 | <0.50 |
| Duplication rate | `duplication.rate` | >0.50 | >0.80 |
| Q30 rate | `after_filtering.q30_rate` | <0.75 | — |
| Insert size peak | `insert_size.peak` | <100bp | — |
| GC content | `after_filtering.gc_content` | outside 35–75% | — |
| Low-complexity fraction | `filtering_result.low_complexity_reads / before_filtering.total_reads` | >0.20 | — |

A single WARN in isolation usually isn't a big deal; multiple WARNs on the
same sample, or any FAIL, is worth flagging before proceeding to the next
stage.

## bam (post-alignment / host-decontamination)

Run `samtools flagstat` on the output. What "normal" looks like depends
heavily on sample type — don't apply a single threshold blindly:

| Sample type | Expected host fraction | WARN | FAIL |
|---|---|---|---|
| Stool metagenome | 0.1–10% | >50% | >90% |
| Mucosal biopsy | 40–90% (high is *expected*, not a problem) | — | — |
| Lavage / aspirate | variable, no fixed prior | use judgment | — |

Also check, regardless of sample type:

| Metric | WARN | FAIL |
|---|---|---|
| PhiX fraction | >1% | — |
| Reads surviving decontam | <100,000 | <10,000 |

A high host fraction on a *stool* sample is a real signal (mucosal
contamination, collection issue) worth surfacing — the same number on a
biopsy sample is expected and shouldn't be flagged.

## slurm_job (completed job resource efficiency)

Run `seff <job_id>` on a completed Slurm job before assuming the resource
request was well-tuned for next time:

| Metric | Signal |
|---|---|
| CPU efficiency <50% of requested | Over-requested — lower cpus next run |
| Memory efficiency >90% of requested | Under-requested — raise mem_gb next run, risk of OOM kill |

This is about tuning future `submit_job` calls, not about whether the job's
scientific output is trustworthy — that's the fastq/bam checks above.
