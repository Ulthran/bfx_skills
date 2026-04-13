# prep-bfx — Workflow Preparer

## Purpose
Take the confirmed plan from plan-bfx and prepare everything needed to execute:
build the Snakefile, validate tool availability, check all paths, and run a
dry-run to verify the DAG. The workflow is ready to execute when this skill
exits successfully.

## Trigger
Use after plan-bfx has produced a confirmed plan and updated project.yaml.

---

## Protocol

### Step 1: Load project plan

Read `{project_dir}/project.yaml` and `{project_dir}/config.yaml`.
Confirm that `stages_planned` is non-empty. If it is, tell the user to run
plan-bfx first.

Load tool profiles for each planned stage:
```
tool_profiles = {
  stage: yaml.safe_load((bfx_skills_root / f"config/tools/{tool}.yaml").read_text())
  for stage, tool in project.tool_selections.items()
  if stage in project.stages_planned
}
```

### Step 2: Validate genome indices

For each genome in `decontam_refs`:
1. Resolve the bwa index path: `{genome_db}/{genome.bwa_index}`
2. Check that at least one index file exists (e.g., `{prefix}.0123`)
3. If missing, STOP and report:
   ```
   Missing genome index: human (hg38)
   Expected at: /ref/genomes/human/hg38/bwa/hg38
   
   To build:
     bwa-mem2 index -p {prefix} {fasta}
   
   Or update config.yaml with the correct path.
   ```

### Step 3: Check tool availability

For each tool profile:

**If activation = conda/mamba:**
```bash
# Check if env already exists
conda env list | grep bfx_{toolname}
# If not, dry-create to validate spec:
mamba env create --dry-run -f {bfx_skills_root}/envs/{tool}.yaml
```
Report: `[✓] fastp env: bfx_fastp (exists)` or `[○] fastp env: will be created on first run`

**If activation = docker:**
```bash
docker image inspect {docker_image} > /dev/null 2>&1 && echo present || echo missing
```
If missing: `docker pull {docker_image}` (ask user before pulling large images)

**If activation = system:**
```bash
which {tool_binary}
```

### Step 4: Assemble the Snakefile

Follow the DAG assembly protocol from `skills/bfx-dag.md`:
1. Write `{project_dir}/workflow/config.yaml` (injecting resolved paths and params)
2. Write `{project_dir}/workflow/samples.tsv` (from project samples.tsv)
3. Assemble `{project_dir}/workflow/Snakefile` from rule templates
4. Symlink conda envs into `{project_dir}/workflow/envs/`

Show the user the assembled Snakefile path and a brief summary of rules included.

### Step 5: Dry-run

```bash
cd {project_dir}/workflow
snakemake \
  --profile {bfx_skills_root}/templates/profiles/local \
  --dryrun \
  2>&1 | tee {project_dir}/logs/dryrun.log
```

Parse the dry-run output:
- Extract total job count and breakdown by rule
- Verify first sample's input file paths resolve correctly
- Check for any errors: MissingInputException, AmbiguousRuleException, etc.

**If dry-run fails:**
- Show the error from the log
- Diagnose common causes:
  - `MissingInputException`: input path doesn't exist → check samples.tsv, data/raw/ symlinks
  - `AmbiguousRuleException`: rule conflict → check Snakefile for duplicate rule names
  - `WorkflowError`: Python syntax in Snakefile → inspect the offending section
- Do NOT proceed to do-bfx until dry-run is clean.

**If dry-run succeeds, report:**
```
Dry-run successful ✓
────────────────────────────────────────
Total jobs     : 64
Rules          : fastp_qc (16) + bwa_decontam_human (16) + bwa_decontam_phix (16) + ...
First sample   : SRR001 → data/raw/SRR001_R1.fastq.gz ✓
Output root    : data/processed/
Est. wall time : ~6h local / ~1.5h SLURM

Snakefile : {project_dir}/workflow/Snakefile
Log       : {project_dir}/logs/dryrun.log

Ready to execute. Run /do-bfx {project_name} [--backend local|slurm]
```

### Step 6: Update project.yaml

```yaml
prep_status: ready
snakefile: {project_dir}/workflow/Snakefile
dryrun_log: {project_dir}/logs/dryrun.log
dryrun_job_count: 64
prepped_at: {ISO timestamp}
```

---

## Re-prepping after plan changes

If plan-bfx adds or removes stages, run prep-bfx again to regenerate the
Snakefile. It is safe to overwrite the existing Snakefile — the project
config and samples.tsv are preserved.

If a workflow is currently running (state.yaml status = running), do NOT
regenerate the Snakefile. Warn the user and exit.
