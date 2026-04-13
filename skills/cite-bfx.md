# cite-bfx — Citation Generator

## Purpose
Produce a citation sheet for a completed (or in-progress) project, listing all
tools used with their versions, DOIs, and formatted references. Supports BibTeX,
APA, and plain-text output. Helps researchers cite their methods properly.

## Trigger
Use when:
- User is writing up a manuscript or report
- User asks "what do I need to cite", "generate citations", "cite-bfx"
- End of a project before publication

---

## Protocol (SKELETON — expand as tools are added)

### Step 1: Determine tools used

Read `{project_dir}/project.yaml`:
- `stages_completed` → maps to tool names via `tool_selections`
- Also check `workflow/state.yaml` for actual tool versions used

Collect:
```python
tools_used = [
    project.tool_selections[stage]
    for stage in project.stages_completed
]
# Always add: snakemake (workflow engine)
tools_used.append("snakemake")
```

### Step 2: Load citation database

```python
citations_db = yaml.safe_load(
    (bfx_skills_root / "config/citations.yaml").read_text()
)
```

For each tool in `tools_used`, look up the entry in the database.
If a tool is missing from the database, note it as `[CITATION NEEDED: {tool}]`
and remind the user to add it to `config/citations.yaml`.

### Step 3: Retrieve tool versions

For each tool, attempt to get the version used:
- From `workflow/state.yaml` if recorded
- From the conda env: `conda run -n bfx_{tool} {tool} --version 2>&1`
- From docker: `docker run --rm {image} {tool} --version 2>&1`
- Fallback: use version from tool profile YAML

### Step 4: Generate citation sheet

**TODO: implement full formatting logic**

For now, output three sections:

#### 4a. Methods snippet (plain text)

A paragraph suitable for copying into a Methods section:
```
Raw reads were quality-controlled using fastp v{version} (Chen et al., 2018)
with adapter auto-detection, minimum length 50 bp, and complexity filtering
(threshold 30%). Host and PhiX contamination were removed by mapping to hg38
and phiX174 using BWA-MEM2 v{version} (Vasimuddin et al., 2019) and retaining
unmapped read pairs via SAMtools v{version} (Danecek et al., 2021).
[Taxonomic profiling was performed with Kraken2 v{version} (Wood et al., 2019)
and abundance estimation with Bracken v{version} (Lu et al., 2017).]
All analyses were executed using Snakemake v{version} (Mölder et al., 2021).
```

#### 4b. Reference list (APA)

Formatted reference for each tool, one per line. Example:
```
Chen, S., Zhou, Y., Chen, Y., & Gu, J. (2018). fastp: an ultra-fast all-in-one 
FASTQ preprocessor. Bioinformatics, 34(17), i884–i890. https://doi.org/10.1093/bioinformatics/bty560
```

#### 4c. BibTeX file

Write `{project_dir}/results/citations.bib` containing all BibTeX entries.

### Step 5: Write output files

```
{project_dir}/results/
├── citations.bib           ← BibTeX
├── citations_apa.txt       ← APA reference list
└── methods_snippet.txt     ← paste-ready methods paragraph
```

Report to user:
```
Citation sheet generated for {project_name}
────────────────────────────────────────
Tools cited: fastp, bwa-mem2, samtools, snakemake (4 tools)
Missing citations: [none | list any missing]

Files written:
  {project_dir}/results/citations.bib
  {project_dir}/results/citations_apa.txt
  {project_dir}/results/methods_snippet.txt
```

---

## Adding citations to the database

To add a new tool:
1. Open `config/citations.yaml`
2. Add an entry following the existing format (key, apa, doi, bibtex, note)
3. The `key` should match the tool name used in `tool_selections`

To report a missing citation while writing:
```
[CITATION NEEDED: {tool_name}]
Please add an entry to config/citations.yaml and re-run cite-bfx.
```

---

## Known gaps (TODO)

- [ ] Auto-fetch citations from CrossRef API using DOI
- [ ] Support for Nature Methods citation style
- [ ] Database citations (Kraken2 DB version, UniRef90 date, etc.)
- [ ] Version capture from conda envs at runtime (hook into do-bfx)
- [ ] Deduplication when same tool appears in multiple stages
