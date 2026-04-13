# init-bfx — Project Initializer

## Purpose
Create a new bfx project workspace and assess the raw data. Run once per project,
at the very start. Sets up the directory structure, generates a project config
from the global template, and produces a `samples.tsv` by scanning input FASTQs.

## Trigger
Use when:
- User starts a new analysis ("I want to analyze this dataset", "set up a project for...")
- User provides a data directory and wants to begin

---

## Protocol

### Step 1: Gather minimum required information

Before doing anything, confirm you have:
1. `project_name` — short identifier, no spaces (e.g., `hmp_pilot`, `ibd_cohort_2026`)
2. `data_dir` — path to directory containing raw FASTQ files
3. `project_dir` — where to create the project (default: `{projects_root}/{project_name}`)

If `data_dir` is not provided, ask for it. Do NOT proceed without it.

### Step 2: Load global config (bfx-config)

Follow `skills/bfx-config.md`:
- Resolve `projects_root` and `bfx_skills_root`
- If `config/global.yaml` does not exist, prompt the user:
  ```
  config/global.yaml not found.
  Please copy config/global.yaml.template → config/global.yaml
  and fill in your paths (genome_db, projects_root, bfx_skills_root).
  ```
  Stop until they do.

### Step 3: Create project directory structure

```
{project_dir}/
├── config.yaml          ← project-specific config (copy from global, allow overrides)
├── project.yaml         ← project metadata
├── samples.tsv          ← generated from data assessment
├── workflow/            ← Snakefile goes here (written by prep-bfx)
│   └── envs/            ← conda env symlinks (written by prep-bfx)
├── data/
│   └── raw/             ← symlinks to input FASTQs
├── logs/
│   ├── snakemake/
│   └── slurm/
└── results/
```

Create all directories. Symlink each FASTQ from `data_dir` into `data/raw/`
(never copy raw data).

### Step 4: Generate project config.yaml

Copy `config/global.yaml` to `{project_dir}/config.yaml`.
Add a header block at the top:
```yaml
# Project-specific config for: {project_name}
# Overrides global config. Edit here to change settings for this project only.
# Generated: {ISO timestamp}
project: {project_name}
data_dir: {data_dir}
```
All other fields inherit from global. User can edit `config.yaml` to override
specific settings (different SLURM account, more cores, etc.) without touching
the global config.

### Step 5: Assess raw data

Run the data assessment script:
```bash
python {bfx_skills_root}/scripts/assess_data.py \
  --data-dir {data_dir} \
  --output-tsv {project_dir}/samples.tsv \
  --json
```

Parse and report the output:
- Naming convention detected
- Number of complete pairs found
- Any warnings (unpaired, size issues, ambiguous names)
- Show the first 5 rows of samples.tsv

If the script exits with code 2 (fatal error), stop and ask the user to fix the
data directory before continuing.

If warnings (exit code 1):
- Show the warnings clearly
- Ask if the user wants to proceed anyway or fix first
- Note warnings in `project.yaml`

### Step 6: Write project.yaml

```yaml
project: {project_name}
description: ""              # user can fill in later
created: {ISO timestamp}
data_dir: {data_dir}
n_samples: {N}
naming_convention: {detected pattern}
data_warnings: []            # list any warnings from assess_data.py
stages_planned: []           # filled in by plan-bfx
stages_completed: []
bfx_skills_root: {resolved path}
```

### Step 7: Confirm to user

```
Project initialized: {project_name}
────────────────────────────────────────
Directory : {project_dir}
Samples   : N paired-end samples detected
Convention: {naming_convention}
Config    : {project_dir}/config.yaml (edit to override global settings)

[any warnings]

Next step: run /plan-bfx {project_name} to plan the analysis.
```
