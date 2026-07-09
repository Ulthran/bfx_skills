# Environment manager guidelines (draft)

Rough guidance on which environment manager fits a given bioinformatics task.
This is a first draft — expect it to be refined.

## conda

Default choice for most bioinformatics tools, especially anything published
via Bioconda. Reach for `mamba` instead of `conda` itself when available —
same environments, much faster solver, particularly on envs with many pinned
scientific packages.

Use when: the tool ships a Bioconda recipe (most aligners, variant callers,
QC tools do); you need a quick, disposable environment for one pipeline
stage; reproducibility just needs a pinned package list, not full OS-level
isolation.

Gotchas: solver time balloons on large/loosely-pinned environments — pin
versions in the spec rather than letting the resolver improvise; conda
environments are not portable across architectures (x86_64 vs. arm64) or
sometimes even across OS versions, so don't assume a conda env built on one
cluster node works unchanged on another.

## mamba

Not a separate ecosystem — a drop-in, faster solver for conda environments.
Prefer it over plain `conda` for anything beyond a two-package environment.
If `detect_capabilities()` shows mamba isn't installed, conda still works,
just slower.

## venv (Python virtual environments)

Use when: the task is pure-Python tooling with no compiled/bioconda
dependency (a custom analysis script, a Python-only API client), or when a
tool's Python dependencies conflict with what's in a conda env you don't
want to touch.

Gotchas: doesn't manage non-Python binaries at all — if a tool needs
`samtools` or `bwa` on PATH, venv alone won't provide it; combine with a
system install or a conda env for the binary dependency.

## docker

Use when: you need strict reproducibility (exact OS + library versions,
not just package versions), the tool ships an official image, or you're
distributing a pipeline stage to run identically on a laptop and a cluster
node. Also the right call for tools with painful native dependency chains
that fight conda's solver.

Gotchas: many HPC/Slurm clusters don't allow Docker (no rootless daemon
access for regular users) — check `detect_capabilities()` for whether Docker
is actually usable in the current execution context before relying on it,
especially if `target="cluster"` is in play. Bind-mount data directories
explicitly; don't assume the container sees the host filesystem.

## apptainer (formerly Singularity)

Use when: you're on a shared HPC cluster and need container-level
reproducibility — this is what most clusters actually allow, unlike Docker.
Can typically run Docker Hub images directly (`apptainer pull docker://...`)
without needing Docker itself.

Gotchas: image files (`.sif`) are large, single files — put them in the
configured shared databases/environments root (see below) so they're reused
across projects instead of re-pulled per project.

## Reuse and the shared location

Before creating any new environment, call `find_environments()` — someone
(including a past run of yourself) may have already built one that fits.
When creating a new one, prefer placing it under the configured shared root
(`environments.root` in `~/.bfx_mcp/config.yaml`, defaulting to
`~/.bfx_mcp/environments/`) rather than inside a single project's directory,
then call `register_environment()` so it shows up for next time. An
environment that only exists inside one project's throwaway directory can't
be found or reused later.
