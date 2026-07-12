# Trace — Repository Ontology

## Purpose

Trace models repositories as structured knowledge, not unrelated text chunks.

## Knowledge Kinds

```text
deterministic
derived
inferred
```

- **deterministic**: direct provider/parser fact
- **derived**: computed graph metric or score
- **inferred**: subsystem, decision, topic, learning step

## Core Entities

### Deterministic

- Repository
- RepositorySnapshot
- Directory
- File
- Symbol
- ExternalDependency
- Issue
- PullRequest
- Commit
- Release
- Discussion
- Person
- Label

### Derived

- GraphMetric
- ContributorMetric

### Inferred

- Subsystem
- Topic
- Decision
- LearningStep
- ArchitectureSummary

## Core Relationships

### Structural

- `CONTAINS`
- `DECLARES`
- `IMPORTS`
- `CALLS`
- `EXTENDS`
- `IMPLEMENTS`
- `DEPENDS_ON`
- `MODIFIES`

### Historical

- `REFERENCES`
- `RESOLVES`
- `RELEASE_INCLUDES`
- `PARENT_OF`

### Contributor

- `AUTHORED`
- `REVIEWED`

### Semantic

- `PART_OF_SUBSYSTEM`
- `ABOUT`
- `DERIVED_FROM`
- `IMPLEMENTED_BY`
- `AFFECTS`
- `RECOMMENDED_BEFORE`
- `RELATED_TO`

Use specific relationships before `RELATED_TO`.

## Base Entity Fields

```text
id
repository_id
snapshot_id
entity_type
canonical_key
name
description
knowledge_kind
confidence
provenance
metadata
created_at
updated_at
```

## Base Edge Fields

```text
id
repository_id
snapshot_id
source_node_id
target_node_id
relationship_type
knowledge_kind
confidence
provenance
metadata
created_at
updated_at
```

## Canonical Keys

Examples:

```text
github:repository:{github_id}
repo:{repository_id}:snapshot:{snapshot_id}:file:{path}
repo:{repository_id}:snapshot:{snapshot_id}:symbol:{path}:{qualified_name}
github:issue:{repository_id}:{number}
github:pull_request:{repository_id}:{number}
github:commit:{repository_id}:{sha}
```

Canonical keys must be reproducible and support idempotent upsert.

## Evidence

Evidence stores:

```text
source entity
target entity or edge
evidence type
relationship
content/excerpt
source URL
line range
confidence
provenance
```

Evidence types:

- artifact
- source span
- graph path
- metric
- provider relation
- model inference

Rules:

- inferred entities require evidence
- model output alone cannot confirm a decision
- graph paths must reference persisted edges
- exact source spans preferred

## Confidence

Scale:

```text
0.00–1.00
```

Suggested bands:

```text
high   >= 0.80
medium >= 0.55
low    < 0.55
```

Confidence is an operational score, not guaranteed probability.

## Subsystem Rules

A subsystem should use at least two agreeing signals:

- directory structure
- import community
- semantic similarity
- documentation
- labels
- co-change history

Low-confidence clusters remain candidates.

## Decision Rules

Confirmed decision requires:

- identifiable context
- identifiable chosen action
- evidence source
- confidence above threshold
- no stronger contradiction

Preferred chain:

```text
Issue / Discussion
→ Pull Request
→ Commit
→ File
```

## Contributor Rules

Contributor activity may use:

- authored PRs
- reviewed PRs
- commits
- subsystem files
- recency

Allowed wording:

```text
Repository evidence suggests strong activity in routing.
```

Not allowed:

```text
This person is the routing expert.
```

## Snapshot Semantics

Snapshot-scoped:

- Directory
- File
- Symbol
- import relationships
- Subsystem
- ArchitectureSummary
- GraphMetric

Repository-scoped:

- Repository
- Person
- Issue
- PullRequest
- Commit
- Release

## Validation

Reject:

- unknown entity/edge types
- invalid source-target pair
- inferred item without confidence
- inferred item without provenance
- edge to missing node
- unsupported self-loop
- confirmed decision without evidence

## Example

```text
Decision
    ├── DERIVED_FROM → Issue
    ├── IMPLEMENTED_BY → PullRequest
    ├── IMPLEMENTED_BY → Commit
    └── AFFECTS → Subsystem
```

## Versioning

Store ontology version on:

- snapshot
- node
- edge
- Atlas section

Current initial version:

```text
1.0.0
```
