# Trace — Product Requirements

## Objective

Help users understand an unfamiliar repository in approximately ten minutes.

## Primary Flow

```text
Landing
→ Submit GitHub URL
→ Validate
→ Ingest
→ Generate Atlas
→ Open Overview
→ Explore
→ Inspect Evidence
→ Ask
```

## Repository States

```text
pending
validating
queued
ingesting
analyzing
generating
ready
partial
failed
```

## Feature Priorities

| Priority | Meaning |
|---|---|
| P0 | Required for working MVP |
| P1 | Required for complete portfolio MVP |
| P2 | Valuable later |

## P0 Features

### 1. Repository Submission

User can submit:

```text
https://github.com/{owner}/{repository}
```

Requirements:

- normalize supported GitHub URLs
- reject malformed or nested URLs
- reject private repositories
- reuse existing Atlas
- create ingestion job

Acceptance:

- valid URL starts ingestion
- invalid URL shows specific error
- duplicate active jobs are prevented
- no login required

### 2. Ingestion Progress

Show:

- current stage
- completed stages
- progress
- failure reason
- retry state
- partial completion

Acceptance:

- progress survives refresh
- failed stage is visible
- completed work is preserved
- partial Atlas can open

### 3. Repository Shell

Navigation:

```text
Overview
Architecture
Subsystems
Timeline
Decisions
Contributors
Explore
Ask
```

Acceptance:

- active page visible
- repository identity persistent
- partial/unavailable sections labeled

### 4. Overview

Show:

- repository summary
- languages
- stats
- architecture summary
- major subsystems
- recent releases
- important decisions
- suggested learning order

Acceptance:

- useful before chat
- every inference exposes confidence/evidence
- empty states are meaningful

### 5. Evidence

Every inferred output must link to structured evidence.

Evidence includes:

- source type
- source title
- source URL
- excerpt or line span
- relationship
- provenance
- confidence

## P1 Features

### Architecture

- Cytoscape.js graph
- subsystem dependencies
- entry points
- external dependencies
- central files
- evidence panel

Rules:

- deterministic and inferred edges look different
- import does not imply runtime call
- graph is bounded

### Subsystems

Each subsystem shows:

- summary
- confidence
- key files
- symbols
- dependencies
- related PRs/issues
- decisions
- contributors
- discovery signals

Low-confidence clusters stay labeled as candidates.

### Timeline

Events:

- issues
- pull requests
- commits
- releases
- decisions
- inferred milestones

Filters:

- date
- event type
- subsystem
- contributor

### Decisions

Each confirmed decision requires:

- context
- chosen action
- confidence
- evidence chain
- affected subsystem/files

States:

```text
candidate
confirmed
insufficient_evidence
rejected
```

No evidence means no confirmed decision.

### Contributors

Show:

- authored PRs
- reviewed PRs
- commits
- active subsystems
- recency
- explainable activity score

Use cautious wording:

```text
Repository evidence suggests strong activity in authentication.
```

### Explore

Support:

- search
- filters
- bounded neighbor expansion
- edge inspection
- evidence
- GitHub links

### Ask

Supported question types:

- architecture
- subsystem
- decision
- history
- contributor
- file
- symbol
- mixed

Response must include:

- answer
- confidence
- citations
- evidence
- graph path
- related files
- limitations
- labeled interpretations when evidence is weak

## Empty-State Rules

Examples:

**No decisions**

```text
No confirmed decisions found.
Explore related issues and pull requests in Timeline.
```

**No subsystems**

```text
Reliable subsystem boundaries could not be derived.
Architecture falls back to directories and imports.
```

## Error Rules

Errors must show:

- what failed
- why when known
- whether retry is available
- what data remains usable
- next action

## Non-Goals

MVP does not include:

- authentication
- private repositories
- billing
- teams
- GitLab/Bitbucket
- code generation
- code editing
- webhooks
- Neo4j
- IDE integration

## Release Criteria

MVP is ready when:

- submission works
- ingestion is async
- progress persists
- Overview works
- Architecture works
- Subsystems works
- Timeline works
- Decisions are evidence-backed
- Contributors are explainable
- Ask returns cited answers
- partial failures work
- CI passes
- Docker Compose starts full stack
