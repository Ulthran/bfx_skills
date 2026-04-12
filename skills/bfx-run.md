# bfx-run — Workflow Executor

## Purpose
Execute a generated Snakemake workflow (dry-run or real), initialize job state,
and launch the background watcher.

## Trigger
Use after bfx-dag has generated a project workflow, when the user wants to:
- Dry-run to validate the DAG
- Execute locally
- Submit to SLURM

---

## Protocol

### Step 1: Always dry-run first

Before any real execution, run a dry-run unless the user explicitly says to skip it.

```bash
cd {project_dir}/workflow
snakemake \
  --profile {bfx_skills_root}/templates/profiles/local \
  --dryrun \
  --dag \
  2>&1 | tee {project_dir}/logs/dryrun.log
```

Parse the dry-run output:
- Count jobs by rule name
- List input/output files for first 3 samples (to verify paths)
- Check for any "MissingInputException" or "AmbiguousRuleException" errors

**Report to user:**
```
Dry-run complete:
  Jobs planned: 32 (16 fastp_qc + 16 bwa_decontam_human + ...)
  Samples: 16
  Estimated wall time: ~4h (local), ~45m (SLURM, 16 parallel)
  First sample inputs: ✓ /path/to/sample1_R1.fastq.gz (exists)
  Output root: {project_dir}/data/processed/

Ready to execute. Backend? [local / slurm / cancel]
```

If there are ANY path errors or missing files, DO NOT proceed — show the errors
and ask the user to fix them.

### Step 2: Initialize state.yaml

Write `{project_dir}/workflow/state.yaml` before launching:
```yaml
project: {project_name}
status: pending
backend: {local|slurm}
started: null
ended: null
snakemake_pid: null
slurm_job_ids: []
stages: {stages}
samples_count: N
progress:
  total: 0
  done: 0
  failed: 0
  pending: 0
last_checked: null
log: {project_dir}/logs/snakemake.log
log_tail: []
log_errors: []
watcher_status: null
```

### Step 3a: Local execution

```bash
cd {project_dir}/workflow
nohup snakemake \
  --profile {bfx_skills_root}/templates/profiles/local \
  --cores {local_cores} \
  > {project_dir}/logs/snakemake.log 2>&1 &
echo $!
```

Capture the PID. Update state.yaml:
```yaml
status: running
started: {ISO timestamp}
snakemake_pid: {pid}
backend: local
```

### Step 3b: SLURM execution

```bash
cd {project_dir}/workflow
# Patch the SLURM profile with project-specific account/partition if set
# Then launch:
nohup snakemake \
  --profile {bfx_skills_root}/templates/profiles/slurm \
  > {project_dir}/logs/snakemake.log 2>&1 &
echo $!
```

Update state.yaml:
```yaml
status: running
started: {ISO timestamp}
snakemake_pid: {pid}
backend: slurm
```

SLURM job IDs will be scraped from the log by watch_job.py as jobs are submitted.

### Step 4: Launch background watcher

```bash
nohup python {bfx_skills_root}/scripts/watch_job.py \
  --project {project_dir} \
  --interval {monitor.poll_interval from global config} \
  > {project_dir}/logs/watcher.log 2>&1 &
echo "Watcher PID: $!"
```

Update state.yaml:
```yaml
watcher_status: running
watcher_pid: {pid}
```

### Step 5: Confirm to user

```
Workflow launched.
  Project: {project_name}
  Backend: {local|slurm}
  Snakemake PID: {pid}
  Log: {project_dir}/logs/snakemake.log
  State: {project_dir}/workflow/state.yaml

Run /bfx-monitor {project_name} to check progress.
```

---

## Re-running after failure

If state.yaml shows `status: failed`:
1. Show the `log_errors` from state.yaml
2. Ask user to fix the issue (missing file, wrong path, etc.)
3. Re-run with `snakemake --rerun-incomplete` flag added to the command

## Cancelling a running job

- Local: `kill {snakemake_pid}` (SIGTERM allows Snakemake to clean up)
- SLURM: `scancel {slurm_job_ids}` then kill the Snakemake process

Update state.yaml: `status: cancelled`, `ended: {timestamp}`
