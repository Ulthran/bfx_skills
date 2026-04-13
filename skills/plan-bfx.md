# plan-bfx — Analysis Planner

## Purpose
Understand the current state of a project and determine what needs to happen next.
This skill is used both at the start (initial planning) and iteratively after each
stage completes (analyze results, assess next steps). It is the connective tissue
of the plan → prep → do → plan loop.

## Trigger
Use when:
- User wants to plan a new analysis for an initialized project
- A workflow stage has completed and the user wants to know what to do next
- User asks "what's the plan", "what should we do next", "analyze results"
- Returning to a project after time away

---

## Protocol

### Step 0: Enter planning mode

Use EnterPlanMode before doing any analysis or making any recommendations.
All planning happens in plan mode. Exit plan mode before calling prep-bfx or do-bfx.

### Step 1: Load project state

Read the following files from `{project_dir}`:
1. `project.yaml` — metadata, planned/completed stages
2. `config.yaml` — project settings
3. `workflow/state.yaml` — if it exists (indicates a workflow has run or is running)
4. `results/` directory listing — what outputs exist

Determine current situation:
- **Fresh project** (no state.yaml, no results): need to plan from scratch
- **Workflow running**: check state.yaml status — redirect to do-bfx / bfx-monitor
- **Stage just completed**: analyze outputs, plan next stage
- **Project paused**: summarize where things stand, ask what user wants to do

### Step 2: For a fresh project — gather analysis goals

Ask (or infer from context):
1. **Sample type**: stool? mucosal biopsy? other? (affects QC thresholds and interpretation)
2. **Study goal**: What question is being asked?
   - Taxonomic composition only?
   - Functional potential?
   - Genome-resolved (assembly + binning)?
   - All of the above?
3. **Host removal**: human? mouse? both? (check which indices exist in global config)
4. **Execution preference**: local or SLURM? (default: local dry-run → SLURM execute)
5. **Tool preferences**: any overrides from defaults? (usually no)

### Step 3: Build the analysis plan

Based on the goals, propose an ordered stage list from the available stages:

| Goal | Stages |
|------|--------|
| QC only | qc |
| Taxonomy | qc → decontam → taxonomy_profiling |
| Functional | qc → decontam → taxonomy_profiling → functional_profiling |
| Assembly | qc → decontam → assembly → binning |
| Full metagenomics | qc → decontam → taxonomy_profiling → functional_profiling → assembly → binning |

For each stage, state:
- Tool to be used (from global default_tools or user override)
- Key parameters (threads, memory, special options)
- Expected runtime estimate (from tool profile resources × N samples)
- Expected outputs

Present the plan clearly and ask for confirmation before writing anything.

**Plan format:**
```
Analysis Plan — {project_name}
────────────────────────────────────────────────────
Samples  : N × paired-end Illumina
Goal     : {stated goal}
Backend  : {local | slurm}

Stage 1: QC (fastp)
  Input  : N × raw paired FASTQ
  Output : N × trimmed FASTQ + QC reports
  Time   : ~2h local / ~30m SLURM

Stage 2: Decontamination (bwa-mem2)
  Refs   : human (hg38), phiX
  Input  : QC-filtered FASTQs
  Output : N × decontaminated FASTQ + flagstat
  Time   : ~4h local / ~45m SLURM

[... etc ...]

Total estimated time: ~6h local / ~1.5h SLURM (32 cores)

Confirm this plan? [yes / modify / cancel]
```

### Step 4: After user confirms — update project.yaml

Write the confirmed plan into `project.yaml`:
```yaml
stages_planned: [qc, decontam, taxonomy_profiling]
analysis_goal: "taxonomic profiling of gut microbiome"
sample_type: stool
decontam_refs: [human, phix]
backend: slurm
tool_selections:
  qc: fastp
  decontam: bwa
  taxonomy_profiling: kraken2
```

### Step 5: For post-stage planning — analyze results first

If `stages_completed` is non-empty, call the relevant analysis logic from
`skills/bfx-analyze.md` before making next-step recommendations.

Summarize:
- What stage just ran
- Key QC metrics (pass rates, host fraction, etc.)
- Any samples flagged or excluded
- Whether it's safe to proceed

Then propose the next stage using the same plan format as Step 3.

Common post-stage decisions:
- QC looks bad → do not proceed; investigate before decontam
- High host fraction (unexpected) → confirm sample type before proceeding
- Low yield after decontam → warn; assembly may fail for affected samples
- Taxonomy stage complete → present composition overview; ask if functional needed

### Step 6: Exit plan mode

After the user confirms the plan (or decides not to proceed), exit plan mode.

If proceeding: tell user to run `/prep-bfx {project_name}` next.
If not proceeding: summarize what needs to be resolved first.
