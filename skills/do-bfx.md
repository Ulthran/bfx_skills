# do-bfx — Workflow Executor & Monitor

## Purpose
Execute a prepared workflow (requires prep-bfx to have succeeded) and monitor
it until completion or the user ends the session. If the session ends while the
job is running, the watcher keeps updating state.yaml so monitoring can resume
in the next session via plan-bfx.

## Trigger
Use when:
- User confirms they want to execute after prep-bfx reports ready
- User says "run it", "go ahead", "submit to SLURM", etc.
- Resuming a session to check on a running job

---

## Protocol

### Step 1: Confirm readiness

Read `{project_dir}/project.yaml`. Check:
- `prep_status: ready` — if not, tell user to run prep-bfx first
- `workflow/state.yaml` does NOT have `status: running` — if it does, redirect to Step 4

### Step 2: Choose backend

If not specified by user, ask:
```
Execute on:
  [1] local  — run on this machine ({local_cores} cores, est. {time})
  [2] slurm  — submit to cluster (est. {time} with parallelism)
```

For SLURM, confirm account and partition from config.yaml (prompt if null).

### Step 3: Initialize state.yaml

Write `{project_dir}/workflow/state.yaml`:
```yaml
project: {project_name}
status: pending
backend: {local|slurm}
stages: {stages_planned}
samples_count: N
started: null
ended: null
snakemake_pid: null
slurm_job_ids: []
progress:
  total: {dryrun_job_count}
  done: 0
  failed: 0
  pending: {dryrun_job_count}
log: {project_dir}/logs/snakemake.log
watcher_pid: null
watcher_status: null
```

### Step 4a: Local execution

```bash
cd {project_dir}/workflow
nohup snakemake \
  --profile {bfx_skills_root}/templates/profiles/local \
  --cores {local_cores} \
  > {project_dir}/logs/snakemake.log 2>&1 &
```

Capture PID. Update state.yaml: `status: running`, `snakemake_pid: {pid}`, `started: {now}`.

### Step 4b: SLURM execution

Patch SLURM profile if account/partition are set in config.yaml:
```bash
# Write a project-local copy of the SLURM profile with account/partition filled in
cp -r {bfx_skills_root}/templates/profiles/slurm {project_dir}/workflow/slurm_profile
# Edit slurm_profile/config.yaml to inject account and partition
```

Then launch:
```bash
cd {project_dir}/workflow
nohup snakemake \
  --profile {project_dir}/workflow/slurm_profile \
  > {project_dir}/logs/snakemake.log 2>&1 &
```

Update state.yaml: `status: running`, `backend: slurm`, `snakemake_pid: {pid}`.

### Step 5: Launch background watcher

```bash
nohup python {bfx_skills_root}/scripts/watch_job.py \
  --project {project_dir} \
  --interval {monitor.poll_interval} \
  > {project_dir}/logs/watcher.log 2>&1 &
```

Update state.yaml: `watcher_pid: {pid}`, `watcher_status: running`.

### Step 6: Confirm launch to user

```
Workflow launched ✓
────────────────────────────────────────
Project       : {project_name}
Backend       : {local|slurm}
Snakemake PID : {pid}
Watcher PID   : {pid}
Log           : {project_dir}/logs/snakemake.log

Monitoring every {poll_interval}s. State: {project_dir}/workflow/state.yaml
```

### Step 7: In-session monitoring

While the job is running and the user is still in the session, provide periodic
updates when asked. Read state.yaml and show:
- Jobs done / total
- Current rule being executed
- Any errors in log_errors

If the user ends the session, the watcher continues running. When they return,
running plan-bfx will automatically detect the running/completed state and pick
up from there.

### Step 8: On completion

When state.yaml transitions to `status: complete`:
```
Workflow complete ✓
────────────────────────────────────────
Project   : {project_name}
Duration  : {started} → {ended} ({elapsed})
Jobs      : {done}/{total} complete

Outputs   : {project_dir}/data/processed/

Run /plan-bfx {project_name} to analyze results and plan next steps.
```

### Step 9: On failure

When state.yaml transitions to `status: failed`:
```
Workflow failed ✗
────────────────────────────────────────
Failed rule : {from log_errors}
Error       : {log_errors content}

Log: {project_dir}/logs/snakemake.log

Common fixes:
  - Missing input file → check samples.tsv paths
  - Out of memory → increase mem_mb in config.yaml or tool profile
  - Missing genome index → verify path in config.yaml
  - SLURM timeout → increase default_time in config.yaml

After fixing, re-run: /do-bfx {project_name} --rerun-incomplete
```

The `--rerun-incomplete` flag adds `--rerun-incomplete` to the Snakemake command,
which resumes from the last checkpoint without re-running completed rules.

---

## Resuming after session restart

If state.yaml exists and `status = running`:
1. Check if watcher is still alive: `kill -0 {watcher_pid}`
2. If dead, restart it (Step 5 above)
3. Report current progress from state.yaml
4. Continue to Step 7 (in-session monitoring)
