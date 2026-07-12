# Trace — Database

## Stack

```text
PostgreSQL 17
pgvector
SQLAlchemy 2.x
Alembic
psycopg
Redis 8
```

PostgreSQL is source of truth.

Redis stores queue, locks, progress events, and short-lived cache.

## Core Tables

### Repository

```text
repositories
repository_snapshots
```

### Jobs

```text
ingestion_jobs
ingestion_stages
```

### GitHub Artifacts

```text
people
issues
pull_requests
pull_request_reviews
commits
commit_parents
releases
discussions
labels
artifact join tables
```

### Source

```text
source_files
source_file_contents
symbols
commit_files
external_dependencies
```

### Graph

```text
graph_nodes
graph_edges
graph_metrics
evidence
evidence_paths
```

### Semantic

```text
documents
embedding_spaces
embeddings
```

### Inferred Knowledge

```text
subsystems
decisions
learning_steps
contributor_metrics
atlas_sections
atlas_section_evidence
```

### Evaluation

```text
evaluation_datasets
evaluation_cases
evaluation_runs
evaluation_results
```

## Key Rules

### Repository Identity

Use GitHub repository ID.

```text
repositories.github_id UNIQUE
```

### Snapshot Identity

Use:

```text
repository_id + head_commit_sha
```

### File Identity

Use:

```text
snapshot_id + normalized path
```

### Artifact Identity

Use provider ID or repository + provider number/SHA.

### Graph Node Identity

Use:

```text
repository_id + canonical_key
```

### Graph Edge Identity

Use:

```text
repository_id + source + target + relationship type
```

### Embedding Identity

Use:

```text
document_id + embedding_space_id
```

## Important Constraints

- one active ingestion job per repository
- confidence between 0 and 1
- inferred nodes/edges require confidence
- graph edge source and target must exist
- self-loop rejected unless explicitly supported
- confirmed decision requires evidence in service layer
- Atlas section unique per snapshot + section type

## Graph Tables

`graph_nodes` stores:

- type
- canonical key
- name
- knowledge kind
- confidence
- provenance
- metadata
- ontology version

`graph_edges` stores:

- source
- target
- relationship type
- knowledge kind
- confidence
- provenance
- metadata

## Evidence

Evidence links source material to:

- inferred node
- inferred edge
- Atlas section
- query claim

Fields:

- source node
- target node/edge
- evidence type
- excerpt
- URL
- line range
- provenance
- confidence

## pgvector

`documents` stores chunks.

`embedding_spaces` stores provider, model, dimensions, metric.

`embeddings` stores vector.

MVP should use one active embedding space.

Vector index:

- HNSW
- cosine distance
- repository/snapshot filters

## Search

Hybrid search combines:

- exact match
- PostgreSQL full-text search
- vector similarity
- graph proximity

Optional:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

## Transactions

Use one transaction per coherent stage batch.

Do not hold DB transactions open during GitHub/model calls.

Pattern:

```text
read state
commit
call provider
begin transaction
persist output
commit
```

## Upserts

Use:

```sql
INSERT ... ON CONFLICT ... DO UPDATE
```

for repositories, artifacts, files, nodes, edges, embeddings.

## Migrations

Commands:

```bash
cd backend
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
uv run alembic downgrade -1
```

Rules:

- never edit applied migration
- test fresh upgrade
- keep destructive changes explicit
- separate large backfills

## Redis Keys

Examples:

```text
trace:queue:ingestion
trace:job:{job_id}:progress
trace:lock:repository:{repository_id}
trace:cache:atlas:{snapshot_id}:{section}
```

Redis loss must not destroy persistent job state.

## Testing

Use real PostgreSQL + pgvector for integration tests.

Test:

- migrations
- upserts
- active-job uniqueness
- graph constraints
- evidence integrity
- vector search
- cascade behavior
- retry idempotency

## Future Neo4j

PostgreSQL remains source of truth for artifacts, evidence, vectors, and Atlas.

Neo4j may later store graph nodes/edges if measured graph needs justify it.
