# hypothesize-bfx — Hypothesis Generator

## Purpose
Survey the contemporary literature relevant to the current project's study
context and produce a ranked list of testable questions to explore in the
dataset. Bridges the gap between "here's what I have" and "here's what's
worth looking for." Designed to be run after at least one analysis stage
completes, or any time the user wants research-informed direction.

## Trigger
Use when:
- User asks "what should we look for", "what questions can we ask", "any ideas"
- A major stage completes and the user wants to go deeper than the QC summary
- User wants to know what's current in their field before deciding on next analyses
- User provides a specific direction to explore ("focus on butyrate producers",
  "what's known about inflammation markers here")

---

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Project state | `{project_dir}/project.yaml` + `workflow/state.yaml` | Yes |
| Completed analysis outputs | `{project_dir}/data/processed/` + `results/` | Preferred |
| Direction prompt | User message | No — if absent, use broad study context |

---

## Protocol

### Step 1: Build the study context

Read `{project_dir}/project.yaml` and any available results. Assemble a
structured context object that will drive the literature search:

```yaml
context:
  sample_type: stool | biopsy | lavage | other
  organism: human | mouse | other
  study_design: cross-sectional | longitudinal | case-control | intervention
  n_samples: N
  cohort_descriptor: ""        # inferred or asked: "IBD patients", "healthy adults", etc.
  stages_completed: [qc, decontam, taxonomy_profiling, ...]
  available_data:              # what can actually be analyzed
    - taxonomic_profiles: true/false
    - functional_profiles: true/false
    - MAGs: true/false
    - metadata_columns: []     # any sample metadata (disease, age, BMI, etc.)
  user_direction: ""           # optional prompt from user
```

If `cohort_descriptor` or `sample_type` is ambiguous, ask the user before searching.
The quality of the literature search depends heavily on knowing the study context.

### Step 2: Formulate search queries

Generate 3–5 targeted search queries from the context object. Queries should
be specific enough to find relevant recent work but broad enough to surface
emerging angles.

**Query construction logic:**

Base terms (always include at least one):
- `"gut microbiome" OR "gut microbiota"`
- `"human gut metagenomics"` (if whole-metagenome data)
- `"16S rRNA"` only if explicitly single-amplicon data

Context-specific modifiers (add based on what's known):
- Sample type: `"stool metagenome"`, `"mucosal biopsy"`, `"rectal swab"`
- Cohort: `"inflammatory bowel disease"`, `"colorectal cancer"`, `"healthy adults"`, etc.
- Direction prompt keywords (if provided)
- Analytical angle: `"taxonomic profiling"`, `"functional profiling"`, `"metagenome-assembled genomes"`

Recency: always filter or rank for papers from the past 3 years unless direction
asks for foundational/review work.

**Example queries for a stool metagenome IBD cohort:**
1. `gut microbiome inflammatory bowel disease metagenomics 2023 2024 2025`
2. `Crohn's disease ulcerative colitis gut microbiota composition dysbiosis`
3. `IBD microbiome butyrate producers Faecalibacterium short chain fatty acids`
4. `metagenome-assembled genomes IBD novel species 2024`
5. `gut microbiome disease activity clinical outcome prediction`

### Step 3: Search contemporary literature

Use WebSearch to execute each query. Target:
- PubMed / NCBI (pubmed.ncbi.nlm.nih.gov)
- bioRxiv preprints (biorxiv.org) for cutting-edge work
- Google Scholar as fallback for breadth

For each query, collect the top 5–8 results. For each result:
- Record: title, authors, year, journal/server, DOI or URL
- Read abstract (WebFetch the abstract page if needed)
- Extract: study question, cohort type, key finding, methods used

Aim to survey **15–25 papers total** across all queries, deduplicating overlaps.

**Prioritize:**
- Papers published 2022–present
- Studies with similar sample types and cohort sizes
- High-impact journals (Nature, Cell, Gut, Microbiome, Cell Host & Microbe,
  ISME J, Nature Microbiology) AND strong preprints
- Papers that explicitly describe what questions remain open

**Do not summarize papers verbatim.** Extract the *question being asked* and
the *approach used*, not the narrative. You are mining for hypothesis space,
not writing a review.

### Step 4: Extract hypothesis seeds

For each paper, identify one or more "hypothesis seeds" — a gap, finding,
or open question that could be tested in the current dataset.

Hypothesis seed format:
```
[PAPER]: {short citation}
[QUESTION]: What {testable question}?
[RELEVANCE]: Why this applies to {project_name} data
[REQUIRES]: What analyses/data are needed to test this
[FEASIBILITY]: high | medium | low  (given current project state)
```

**Example seeds:**

```
[PAPER]: Lavelle et al. 2022, Cell Host Microbe
[QUESTION]: Is reduced Faecalibacterium prausnitzii abundance associated with
  mucosal inflammation markers in this cohort?
[RELEVANCE]: F. prausnitzii is a key butyrate producer consistently depleted
  in IBD; cohort has disease activity metadata
[REQUIRES]: Taxonomic profiles (available) + clinical metadata (check)
[FEASIBILITY]: high

[PAPER]: Nayfach et al. 2024, Nature
[QUESTION]: Do any MAGs from this cohort represent novel uncultured species
  associated with disease phenotype?
[REQUIRES]: Assembly + binning (not yet run) + taxonomy profiling
[FEASIBILITY]: low (needs assembly stage first)
```

### Step 5: Organize and rank hypotheses

Group seeds into thematic clusters. Standard clusters for gut metagenomics:

**A. Composition & Diversity**
- Alpha/beta diversity differences between groups
- Known keystone species (Faecalibacterium, Akkermansia, Prevotella, etc.)
- Enterotype or community state types

**B. Functional Potential**
- Metabolic pathway enrichment/depletion
- Butyrate / SCFA production capacity
- Bile acid metabolism, tryptophan metabolism, LPS biosynthesis
- Antibiotic resistance gene burden

**C. Microbial Ecology**
- Co-occurrence networks and hub species
- Ecological stability / resilience
- Strain-level variation within species

**D. Host-Microbe Interface** *(if relevant data)*
- Correlation with host metadata (BMI, age, diet, medication)
- Biomarker potential (predictive of disease state or outcome)
- Longitudinal trajectory (if multiple timepoints)

**E. Novel / Emerging**
- Understudied taxa flagged in recent literature
- Phage / virome interactions *(if applicable)*
- Recently described MAGs or pangenomes

For each cluster, list hypotheses ordered by:
1. Feasibility with current data (high → low)
2. Novelty (well-established → cutting-edge)

### Step 6: Write output

Write `{project_dir}/results/hypotheses.md` with the following structure:

```markdown
# Hypotheses — {project_name}
Generated: {ISO timestamp}
Direction: {user_direction or "broad survey"}
Literature surveyed: {N} papers ({date range})

## Study Context
{brief summary of what the project is}

## Top Questions to Explore

### 1. {Highest priority hypothesis}
**Question:** {one sentence}
**Why now:** {why this is timely / what recent paper motivates it}
**What you need:** {analyses required — already done or planned}
**Key reference:** {citation}

### 2. ...

---

## Thematic Clusters

### A. Composition & Diversity
...

### B. Functional Potential
...

[etc.]

---

## Papers Surveyed
| Title | Authors | Year | Journal | Relevance |
|-------|---------|------|---------|-----------|
...

---

## Hypotheses Requiring More Data
{hypotheses that are low feasibility now but worth planning for}
```

### Step 7: Report to user

Summarize the output interactively:

```
Hypothesis generation complete — {project_name}
────────────────────────────────────────────────────
Literature surveyed : {N} papers (focus: {date range})
Hypotheses generated: {N} ({N_high} high feasibility, {N_med} medium, {N_low} needs more data)

Top 3 questions to explore now:
  1. {question}  [{key ref}]
  2. {question}  [{key ref}]
  3. {question}  [{key ref}]

Full hypothesis sheet: {project_dir}/results/hypotheses.md

To begin exploring one of these, run:
  /plan-bfx {project_name}  — and reference a hypothesis by number
```

---

## Refinement loop

The user may run hypothesize-bfx multiple times:
- With a more specific direction: "focus only on butyrate metabolism"
- After a new stage completes: more data → more feasible hypotheses
- To refresh with newer literature

Each run appends a dated section to `hypotheses.md` rather than overwriting,
so the evolution of thinking is preserved.

---

## Domain priors (gut microbiome)

Always check for these well-established associations regardless of direction —
they are common reviewer expectations and low-effort to test once taxonomy is
available:

| Feature | Association | Key reference |
|---------|-------------|---------------|
| Faecalibacterium prausnitzii | Anti-inflammatory; depleted in IBD | Sokol et al. 2008 |
| Akkermansia muciniphila | Gut barrier; metabolic health | Plovier et al. 2017 |
| Prevotella copri | Arthritis risk; diet-associated | Scher et al. 2013 |
| Ruminococcus gnavus | IBD flare; mucus degradation | Henke et al. 2019 |
| Bifidobacterium spp. | Probiotic; infant microbiome | Various |
| Bacteroidetes:Firmicutes ratio | Obesity (controversial; use carefully) | Turnbaugh et al. 2006 |
| Diversity (Shannon) | Lower in IBD, antibiotic-exposed | Multiple |

Flag if any of these are notably present, absent, or anomalous in the current
dataset — even before the user asks.

---

## Limitations to communicate

Always note in the output:
- Literature search is not exhaustive — PubMed MeSH search via librarian is more thorough
- Hypotheses are ranked by feasibility and recency, not by biological importance
- Association ≠ causation; all hypotheses are exploratory
- Dataset size (N samples) constrains statistical power — note which hypotheses
  require larger N than available
