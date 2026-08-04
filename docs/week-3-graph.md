# Week 3 — Repository Ontology and Deterministic Graph

Week 3 starts with a versioned persistence boundary for deterministic and
derived repository knowledge. The initial slice stores graph nodes, edges,
evidence, and metrics in PostgreSQL and builds the filesystem graph from the
fixed source inventory produced in Week 2.

## Persistence

The graph schema contains:

- `graph_nodes`
- `graph_edges`
- `evidence`
- `graph_metrics`

Every record is repository-scoped. Snapshot facts also reference a
`repository_version`, whose `ontology_version` is currently `1.0.0`.
Canonical node keys and relation identities drive PostgreSQL conflict updates,
so rebuilding the same snapshot updates existing facts instead of duplicating
them.

Application and database constraints enforce confidence bounds, reject edge
self-loops, require exactly one evidence target, and ensure referenced graph
records exist. The `GraphRepository` protocol keeps graph construction
independent of PostgreSQL; `PostgresGraphRepository` is the MVP adapter.

## Filesystem Graph

`FilesystemGraphBuilder` reads persisted `source_files` and creates:

```text
RepositorySnapshot
  └── CONTAINS → Directory
        ├── CONTAINS → Directory
        └── CONTAINS → File
```

Nodes carry normalized paths, file classifications, language, blob identity,
and snapshot provenance. Every `CONTAINS` edge has both inline provenance and
a persisted provider-relation evidence record. Unsafe absolute or parent
traversal paths fail before graph writes.

## Query Bounds

The repository boundary includes snapshot subgraphs and recursive neighbor
reads scoped to a repository and immutable repository version. HTTP requests
may return at most 500 nodes, 2,000 edges, and 5,000 metrics. Neighbor depth is
limited to 1–3. Responses carry separate truncation flags for each collection
instead of silently implying completeness.

Both endpoints accept repeatable entity-type, relationship-type,
knowledge-kind, and metric-name filters. A neighbor response always retains
the requested root node even when an entity filter excludes its type.

```http
GET /api/repositories/{repository_id}/versions/{repository_version_id}/graph
GET /api/repositories/{repository_id}/versions/{repository_version_id}/graph/nodes/{node_id}/neighbors
```

## Python AST Graph

The Python parser uses the standard-library AST and extracts:

- classes, functions, async functions, methods, and qualified nested names;
- `import` and `from ... import ...` statements, including aliases and scope;
- decorator-aware declaration ranges and exact import source spans.

Python graph construction creates `Symbol` nodes, `DECLARES` edges from files,
and `IMPORTS` edges to internal files or Python external dependencies. Imports
under nested source roots such as `backend/src` resolve through deterministic
module aliases. Ambiguous or unresolved relative imports remain unresolved
rather than being mislabeled as external packages. Syntax failures are
returned per file and do not stop other files from being parsed.

`IMPORTS` records syntactic dependency only. The parser does not create
`CALLS` edges or imply runtime execution.

## TypeScript and JavaScript Graph

The TypeScript/JavaScript parser uses the official Tree-sitter runtime and
language grammars for `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, and `.cjs` files.
It extracts:

- ESM imports, re-exports, CommonJS `require`, and dynamic imports;
- functions, classes, methods, interfaces, type aliases, enums, and module
  variables;
- named and default exports, including type-only exports;
- JSX/TSX and `React.createElement` function components;
- React component classes and conventionally named custom hooks.

Graph construction creates `DECLARES` and `IMPORTS` relations with exact
source-span evidence. Export facts are stored as source evidence on the
exported symbol or file rather than inventing a relationship outside the
ontology. Relative imports and modules below nested `src` or `lib` roots are
resolved to repository files. Ambiguous aliases and unresolved relative paths
remain unresolved instead of being mislabeled as npm packages.

As with Python, `IMPORTS` is a syntactic dependency and never implies a runtime
call.

## Historical Graph

The historical builder maps persisted GitHub facts into repository-scoped
`Person`, `Issue`, `PullRequest`, `Commit`, and `Release` nodes. Snapshot files
remain version-scoped. It creates deterministic:

- `AUTHORED` and `REVIEWED` contributor relations;
- `MODIFIES` relations from pull requests and commits to files present in the
  fixed snapshot;
- `REFERENCES` and closing-keyword `RESOLVES` relations for local `#number`
  references;
- `PARENT_OF` relations between ingested commits;
- `RELEASE_INCLUDES` when a release target is an exact ingested commit SHA.

Every relation has provider or artifact evidence. Git commit identities remain
separate from GitHub people: an `AUTHORED` edge is created only when GitHub
supplies an account link. Cross-repository references, missing historical
parents, and paths absent from the fixed snapshot are not guessed; builders
report them as unresolved counts. Snapshot graph reads include applicable
repository-scoped history while retaining their node cap.

## Ingestion Stages

Graph construction is part of the normal worker flow after all provider
artifacts are persisted. Filesystem, Python, JavaScript/TypeScript, and history
each run as a separate ingestion stage. A completed stage is skipped when a
worker resumes the job, while writes from a failed in-progress stage are
rolled back together. Each stage stores its builder summary on the ingestion
stage for operational visibility, including parser failures and unresolved
relationship counts.

## NetworkX Analysis

The final graph ingestion stage loads the complete deterministic snapshot graph
within explicit safety limits and replaces one versioned metric set atomically.
Analysis produces:

- degree centrality and connected-component membership over the full
  undirected topology;
- seeded Louvain community membership over internal file-to-file `IMPORTS`;
- structural bridges over the full topology;
- dependency-cycle groups from strongly connected internal import components,
  including a representative directed cycle.

Global counts and per-node memberships are stored in `graph_metrics`. Bridge
and cycle records use bounded hash-based scope keys with the affected canonical
keys and node IDs in metadata. Metric writes are chunked for large graphs and
rebuilding the same algorithm version removes stale results before inserting
the replacement set. Analysis refuses graphs above 25,000 deterministic nodes
or 100,000 deterministic edges instead of exhausting worker memory.

## Graph Explorer

The repository detail page links to a lazy-loaded architecture explorer for
the latest immutable snapshot. Its bounded API request includes filesystem and
external-dependency nodes, `CONTAINS` and `IMPORTS` relations, degree
centrality, and community membership.

The Cytoscape view provides node sizing from centrality, distinct entity
styles, directed import edges, relationship filters, search, zoom, fit, and
layout controls. Selecting a node opens its path, language, confidence,
knowledge kind, provenance, ontology version, centrality, and community.

Because the canvas is not an accessible representation by itself, the same
visible relationships are exposed in a keyboard-operable table. The page also
handles missing snapshots, empty graphs, API failures, and bounded-response
warnings explicitly.

## Next Slice

Week 3 is complete. Week 4 begins with document and embedding persistence,
followed by evidence-preserving chunking and subsystem discovery.

## Verification

Unit and PostgreSQL integration tests cover invariants, path safety,
idempotency, evidence attachment, and bounded reads.

```bash
cd backend
uv run alembic upgrade head
uv run alembic check
uv run pytest
```
