# bfx-dag — Snakemake DAG Builder

## Purpose
Given a project description and list of pipeline stages, generate a complete
Snakemake workflow in the project directory. Assembles from rule templates +
tool profiles; no ad-hoc shell commands.

## Trigger
Use when:
- User requests a new analysis pipeline
- User adds or removes a stage from an existing project
- A tool needs to be swapped in an existing workflow

---

## Protocol

### 1. Gather requirements

Collect from the user request or bfx-orchestrate:
- `project_name` — short identifier (used as directory name)
- `project_description` — human-readable description
- `stages` — ordered list, e.g., `["qc", "decontam"]`
- `samples` — dict of {sample_id: {R1: path, R2: path}} or path to sample sheet
- `tool_overrides` — optional, e.g., `{qc: trimmomatic}` to override defaults
- `decontam_refs` — list of reference keys from global.yaml, e.g., `["human", "phix"]`

### 2. Create project directory structure

```
{projects_root}/{project_name}/
├── project.yaml             ← write metadata here
├── workflow/
│   ├── Snakefile            ← generate this
│   ├── config.yaml          ← generate this
│   └── envs/                ← symlink or copy conda env specs here
├── data/
│   └── raw/                 ← symlink inputs here
├── logs/
│   ├── snakemake/
│   └── slurm/
└── results/
```

Create directories. Symlink input files into `data/raw/` — never copy raw data.

### 3. Write project.yaml

```yaml
project: {project_name}
description: {project_description}
created: {ISO timestamp}
stages: {stages}
samples: {sample list}
tool_selections: {resolved tools}
decontam_refs: {refs}
bfx_skills_version: {git hash or "dev"}
```

### 4. Write workflow/config.yaml

This is the Snakemake config file injected at runtime. Include:
```yaml
project: {project_name}
outdir: {project_dir}/data/processed
logdir: {project_dir}/logs
samples_file: {project_dir}/workflow/samples.tsv
# Tool parameters (merged from tool profile defaults + any overrides)
fastp:
  threads: 8
  min_length: 50
  complexity_threshold: 30
  extra: ""
bwa_decontam:
  threads: 16
  decontam_refs: [human, phix]
# Resolved genome index paths
genome_indices:
  human: {resolved bwa index path}
  phix:  {resolved bwa index path}
```

### 5. Write samples.tsv

```
sample  R1  R2
sample1 /path/R1.fastq.gz  /path/R2.fastq.gz
```

### 6. Assemble the Snakefile

**Header** (always included):
```python
import os
import pandas as pd

configfile: "config.yaml"

samples = pd.read_csv(config["samples_file"], sep="\t", index_col="sample")

# Final targets — tell Snakemake what the "all" rule needs
rule all:
    input: [... final outputs for each sample and stage ...]
```

**Rules** — for each stage, for each tool:
1. Read the rule template from `templates/rules/{stage}/{tool}.smk`
2. Replace `<<placeholder>>` tokens with values from config + tool profile:
   - `<<threads>>` → tool profile `resources.cpus`
   - `<<mem_mb>>` → tool profile `resources.mem_mb`
   - `<<runtime_min>>` → tool profile `resources.runtime_min`
   - `<<conda_env>>` → resolved path to `envs/{tool}.yaml`
   - `<<min_length>>`, `<<complexity_threshold>>`, etc. → default_params
   - `<<ref_name>>`, `<<input_r1>>`, `<<bwa_index_path>>` → from config
3. For decontam with multiple refs, generate one rule per ref with chained inputs

**Append** all resolved rules to Snakefile.

### 7. Symlink conda envs

For each tool used, symlink `{bfx_skills_root}/envs/{tool}.yaml` into
`{project_dir}/workflow/envs/` so the Snakefile can reference a relative path.

### 8. Report to user

Summarize the generated workflow:
- Project path
- Stages and tools selected
- Number of samples
- Input/output paths
- Estimated resource usage (sum of per-sample estimates × samples)

Ask user to confirm before calling bfx-run.

---

## Adding a stage to an existing project

1. Load existing `project.yaml` and `workflow/config.yaml`
2. Append the new rule(s) to the existing Snakefile
3. Update the `rule all` inputs
4. Add new tool params to `workflow/config.yaml`
5. Update `project.yaml` stages list
