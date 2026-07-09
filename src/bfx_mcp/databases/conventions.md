# Reference database conventions

Reference databases (host genome indices, Kraken2/MetaPhlAn/HUMAnN
databases, custom BLAST/marker-gene DBs, ...) are usually a directory of
files, not a single artifact, and are expensive to build or download — so
they belong in one shared, discoverable location rather than being
re-downloaded per project.

## Shared location

Configured via `databases.root` in `~/.bfx_mcp/config.yaml`, defaulting to
`~/.bfx_mcp/databases/`. Convention: one subdirectory per database, named to
match its registry entry, e.g. `<databases.root>/hg38-host/`,
`<databases.root>/kraken2-standard-20240605/`.

## Before downloading or building anything

Call `find_databases()` first. Reference databases can be tens to hundreds
of GB and take hours to build — check whether one already exists (and what
version it is) before starting from scratch.

## Registering a database

`register_database(name, kind, location, version, source_url=None, version_check=None, tags=None)`

- `kind`: a free-text category, e.g. `host_genome`, `kraken2_db`,
  `humann_db`, `metaphlan_db`, `custom` — used for filtering, not enforced
  against a fixed list, since reference databases in this space are
  heterogeneous.
- `location`: the directory (or file, for a single-file index) where it
  actually lives.
- `version`: whatever version identifier the source uses — a release tag,
  a build date, a checksum, whatever is meaningful for that source. Free
  text; there's no universal versioning scheme across genome/taxonomy DBs.
- `version_check` (optional): how to check whether a newer version exists
  later, as `{"type": "url", "spec": "<url that returns/contains a current
  version string>"}` or `{"type": "command", "spec": "<shell command whose
  stdout is the current version string>"}`. Generic and pluggable on
  purpose — there's no built-in knowledge of NCBI/Kraken2/HUMAnN release
  pages baked into this tool; whoever registers the database supplies the
  check.

## Checking for updates

`check_for_updates(name)` fetches the URL or runs the command from the
registered `version_check` spec and hands back both the recorded version and
the freshly fetched value for comparison — it does not attempt version
string parsing (semver, date comparison, etc.), since formats vary too much
across sources to do that reliably. Interpret the diff yourself.

If no `version_check` was registered, the tool says so rather than guessing.
