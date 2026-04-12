# bfx-monitor — Workflow Monitor

## Purpose
Report on the current or historical state of a bfx workflow. Works across
Claude sessions by reading state.yaml and log files written by watch_job.py.

## Trigger
Use when:
- User asks "what's happening with project X", "is it done", "check on the run"
- Called automatically by bfx-orchestrate after launching a workflow
- User asks to see logs or errors from a running/completed job

---

## Protocol

### 1. Find the project

If project name is given, resolve path:
```
{projects_root}/{project_name}/workflow/state.yaml
```

If no project name given, list all projects:
```bash
ls -lt {projects_root}/*/workflow/state.yaml
```
Show a summary table of recent projects with status and last-checked time.
Ask user which one they mean.

### 2. Read state.yaml

Load `state.yaml`. Key fields to report:

| Field | Description |
|-------|-------------|
| `status` | pending / running / complete / failed / cancelled |
| `backend` | local / slurm |
| `started` / `ended` | timestamps |
| `progress.done` / `.total` | rules completed |
| `progress.failed` | rules that failed |
| `last_checked` | when watcher last polled |
| `log_errors` | recent error lines from log |
| `slurm_states` | per-job SLURM states (if slurm) |

### 3. Status report format

**Running:**
```
Project: hmp_pilot  [RUNNING]
Backend: slurm
Started: 2026-04-12 14:00 UTC (2h 15m ago)
Progress: 28/64 rules complete (44%)
Current stage: decontam (bwa_decontam_human)
Last checked: 3m ago

SLURM jobs: 8 RUNNING, 2 PENDING, 18 COMPLETED
```

**Complete:**
```
Project: hmp_pilot  [COMPLETE]
Finished: 2026-04-12 16:32 UTC (wall time: 2h 32m)
Rules: 64/64 complete, 0 failed

Outputs: {project_dir}/data/processed/
Run /bfx-analyze hmp_pilot to interpret results.
```

**Failed:**
```
Project: hmp_pilot  [FAILED]
Failed at: bwa_decontam_human (sample: SRR12345)
Time: 2026-04-12 15:10 UTC

Recent errors:
  [ERROR] bwa-mem2: cannot open file /ref/genomes/human/hg38/bwa/hg38.0123
  [ERROR] rule bwa_decontam_human failed after 3 attempts

Suggested fix: verify genome index path in config/global.yaml
Run /bfx-run hmp_pilot --rerun after fixing.
```

### 4. Live log tail (if requested)

If user asks "show me the logs":
```bash
tail -100 {project_dir}/logs/snakemake.log
```

Filter and highlight:
- `[ERROR]` / `Exception` lines → show in full
- Rule start/end lines → show (these have rule name and sample)
- Skip repetitive "Submitted job" lines unless user asks for them

### 5. Check if watcher is still alive

If `watcher_pid` is in state.yaml and status is "running":
```bash
kill -0 {watcher_pid} 2>/dev/null && echo alive || echo dead
```
If dead and job should still be running: restart the watcher (run bfx-run step 4 again).
Update state.yaml `watcher_status`.

### 6. SLURM efficiency check (if slurm backend, job complete)

```bash
seff {slurm_job_id}   # for each major job
```
Report CPU efficiency and memory usage. Flag jobs that used <50% of requested
resources (suggest tuning in tool profile) or >90% memory (suggest increasing).
