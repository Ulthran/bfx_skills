# bfx-config — Configuration Manager

## Purpose
Read, validate, and update the BFX skills global configuration. Also resolves
project-level config overrides. Every other skill calls this first.

## Trigger
Use when:
- Starting any new bfx workflow (always load config first)
- User asks to change a tool preference, path, or cluster setting
- A path needs to be resolved (genome index, scratch dir, etc.)

---

## Protocol

### 1. Load configuration

```python
# Pseudo-code — read and merge configs
import yaml, os
from pathlib import Path

bfx_root = Path("~/Penn/bfx_skills").expanduser()
global_cfg = yaml.safe_load((bfx_root / "config/global.yaml").read_text())

# If inside a project context, overlay project-level overrides
project_cfg = {}
if project_dir:
    proj_override = Path(project_dir) / "workflow/config.yaml"
    if proj_override.exists():
        project_cfg = yaml.safe_load(proj_override.read_text())

# Merge: project overrides global
cfg = {**global_cfg, **project_cfg}
```

### 2. Resolve paths

Always expand `~` and make paths absolute before passing to other skills:
- `projects_root` → base for all new project dirs
- `genome_db` → prepend to genome entries under `genomes:`
- `bfx_skills_root` → location of templates, envs, tool profiles

### 3. Validate before returning

Check that critical paths exist; warn (do NOT fail) if they don't:
- `genome_db` directory
- `projects_root` directory (create it if missing)
- bwa/bowtie2 index files for any genome that will be used

If `genome_db` is missing or a requested genome index doesn't exist, report
clearly to the user and ask for the correct path before proceeding.

### 4. Load tool profile

When a specific tool is needed (e.g., for QC):
```
tool_profile = yaml.safe_load(
    (bfx_root / f"config/tools/{tool_name}.yaml").read_text()
)
```
Merge tool `default_params` with any overrides from the project config.

---

## Updating configuration

When the user wants to change a setting (e.g., "set projects_root to /data/projects"):
1. Read the current `config/global.yaml`
2. Update the relevant field
3. Write back with a comment noting the change
4. Confirm to user

Do NOT update `global.yaml` for project-specific overrides — those go in
`{project_dir}/workflow/config.yaml`.

---

## Returns

A resolved config dict that includes:
- All global settings with paths expanded
- Tool profile(s) loaded and params merged
- Validated status of required paths
