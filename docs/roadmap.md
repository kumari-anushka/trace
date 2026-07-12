# Trace — Roadmap

## Goal

Build a portfolio-ready MVP in approximately six weeks.

## Priority

```text
UX
→ engineering reliability
→ AI quality
→ polish
→ scale
```

## Milestones

| Milestone | Output |
|---|---|
| P0 | Stable local stack and CI |
| P1 | Repository submission and progress |
| P2 | GitHub ingestion |
| P3 | Deterministic graph |
| P4 | Core Software Atlas |
| P5 | Decisions and contributors |
| P6 | Adaptive cited Ask |
| P7 | Evaluation |
| P8 | Portfolio release |

## Week 1 — Foundation

Build:

- backend module boundaries
- repository/job domain models
- SQLAlchemy + Alembic
- URL validation
- GitHub client abstraction
- Redis worker
- progress API/UI

Exit gate:

- submission works
- async job runs
- progress persists
- duplicate active jobs prevented
- CI green

## Week 2 — GitHub Ingestion

Build:

- repository metadata
- snapshots
- source tree
- issues
- pull requests
- commits
- releases
- contributors
- reviews
- rate-limit handling
- fixture tests

Exit gate:

- all artifacts persist
- retries are idempotent
- fixed snapshot SHA exists

## Week 3 — Structural Intelligence

Build:

- graph tables
- GraphRepository
- filesystem/artifact graph
- Python parser
- TypeScript/JavaScript parser
- NetworkX metrics
- graph API
- base Cytoscape UI

Exit gate:

- deterministic nodes/edges exist
- parsers tested
- graph renders
- evidence attached

## Week 4 — Core Atlas

Build:

- documents/embeddings
- pgvector search
- subsystem discovery
- architecture synthesis
- Overview
- Architecture
- Subsystems
- Timeline

Exit gate:

- product useful before Ask
- every inference shows confidence/evidence

## Week 5 — Historical Intelligence and Ask

Build:

- decision candidate generation
- decision verification
- contributor scoring
- metadata retriever
- vector retriever
- graph retriever
- adaptive router
- LangGraph Ask workflow
- citation verification
- Ask UI

Exit gate:

- decisions require evidence
- contributors are explainable
- Ask returns cited answers
- weak evidence handled safely

## Week 6 — Evaluation and Release

Build:

- QA dataset
- keyword/vector/graph/hybrid baselines
- metrics
- Playwright tests
- accessibility pass
- responsive pass
- demo
- docs
- deployment or reproducible local demo

Exit gate:

- one-command start
- core pages work
- evaluation report exists
- demo ready
- limitations documented

## Scope Freeze

Do not add during MVP:

- auth
- private repositories
- billing
- teams
- GitLab/Bitbucket
- code generation
- IDE extension
- Neo4j
- Kubernetes
- webhooks
- multi-repository analysis

## Definition of Done

A task is done when:

- code works
- tests exist
- errors handled
- types/lint pass
- docs updated
- acceptance criteria met
- demo path works

## Final Release Checklist

### Product

- Landing
- Progress
- Overview
- Architecture
- Subsystems
- Timeline
- Decisions
- Contributors
- Explore
- Ask
- Evidence drawer

### Engineering

- migrations
- async jobs
- idempotency
- typed API
- logs
- health checks
- CI
- Docker Compose
- tests

### AI

- graph
- embeddings
- subsystem discovery
- decision extraction
- adaptive retrieval
- citation verification
- confidence
- safe fallback

### Evaluation

- fixed SHAs
- QA set
- baselines
- metrics
- report
- error analysis
- cost analysis

### Portfolio

- README
- docs
- screenshots
- demo video
- architecture diagram
- evaluation chart
- limitations
- release tag
