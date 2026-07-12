# Trace

> **Understand any GitHub repository in minutes.**

Trace is an AI Software Intelligence platform that transforms public GitHub repositories into interactive **Software Atlases**.

A Software Atlas organizes repository knowledge into architecture, subsystems, dependencies, design decisions, project evolution, contributor expertise, and evidence-backed explanations.

Trace does not try to replace GitHub, Claude Code, Cursor, or other coding agents.

GitHub stores software.  
Coding agents help modify software.  
Trace helps people understand software.

---

## Status

Trace is under active development.

Current foundation:

- React + TypeScript frontend
- FastAPI backend
- PostgreSQL
- Redis
- Docker Compose
- GitHub Actions CI

Current product scope:

- public GitHub repositories
- Python repositories
- TypeScript/JavaScript repositories
- one repository per generated Atlas
- no authentication in MVP
- no private repositories in MVP

See [`docs/prd.md`](docs/prd.md) for locked product scope.

---

## Product Promise

Given a public GitHub repository URL, Trace should help a person who has never contributed to that repository understand:

- what the project does
- how the system is structured
- which subsystems matter
- how modules depend on each other
- why major changes were introduced
- how the project evolved
- who has worked most on each subsystem
- where to begin learning
- which evidence supports each conclusion

Target outcome:

> A new user should build a useful mental model of an unfamiliar repository in under 10 minutes.

---

## What Is a Software Atlas?

A Software Atlas is an AI-generated, evidence-backed representation of a software system.

Each Atlas contains eight product surfaces.

### Overview

Answers:

> What is this project?

Includes:

- repository summary
- languages
- frameworks and dependencies
- repository statistics
- major subsystems
- recent releases
- major decisions
- suggested exploration order

### Architecture

Answers:

> How is this system built?

Includes:

- high-level subsystem map
- dependency relationships
- key entry points
- central modules
- important files
- external dependencies
- evidence for inferred structure

### Subsystems

Answers:

> What are the major functional areas?

Includes:

- subsystem purpose
- source files and directories
- internal dependencies
- external dependencies
- related issues and pull requests
- contributor activity
- linked decisions
- confidence and evidence

### Timeline

Answers:

> How did this project evolve?

Includes:

- issues
- pull requests
- commits
- releases
- decisions
- subsystem milestones
- filters by date, artifact type, and subsystem

### Decisions

Answers:

> Why was this built or changed?

Includes:

- decision summary
- original context
- alternatives when evidence exists
- related issue or discussion
- implementing pull request
- commits
- affected files and subsystems
- resulting release
- confidence and evidence

### Contributors

Answers:

> Who appears to know this subsystem best?

Includes:

- authored pull requests
- reviewed pull requests when available
- commits
- files modified
- subsystem activity
- recency
- contribution distribution
- explainable expertise ranking

Trace does not claim contribution volume equals absolute expertise. It presents repository-backed evidence.

### Explore

Answers:

> How are repository artifacts connected?

Includes:

- searchable repository entities
- relationship filters
- expandable neighbors
- evidence inspection
- direct GitHub links

### Ask

Answers:

> What else do I need to understand?

The AI assistant uses the Atlas rather than searching blindly.

Responses include:

- direct explanation
- confidence
- citations
- graph path
- timeline context
- related files
- related decisions
- relevant evidence

---

## Why Trace Is Different

### GitHub

GitHub exposes files, issues, pull requests, commits, releases, and discussions.

It does not automatically turn them into a coherent model of the software system.

### GitHub Search

GitHub Search answers:

> Where does this text appear?

Trace aims to answer:

> How does this system work, why did it evolve this way, and what evidence supports that explanation?

### Claude Code and Cursor

Coding agents are optimized to:

- inspect code
- edit files
- run commands
- fix bugs
- generate tests
- implement features

Trace is optimized to:

- generate persistent repository knowledge
- reveal architecture before coding begins
- connect code with history
- explain subsystem evolution
- surface evidence visually
- guide unfamiliar users through a repository

Coding agents help during implementation.

Trace helps before and during understanding.

---

## Core Principle

> **Evidence before inference.**

Trace separates two knowledge layers.

### Deterministic Layer

Built from repository facts:

- directories
- files
- imports
- commits
- issues
- pull requests
- releases
- contributors
- GitHub references
- files modified by commits

These relationships are reproducible.

### Inferred Layer

Generated using graph algorithms, embeddings, and language models:

- subsystem labels
- topics
- design decisions
- architecture summaries
- learning order
- related concepts

Every inferred output stores:

- confidence
- supporting evidence
- generation method
- model or extractor version
- generation timestamp

Trace must not present unsupported relationships as facts.

When evidence is insufficient, Trace still returns useful nearby material:

```text
I could not conclude this with high confidence.

Related evidence:
- matching pull requests
- relevant issues
- connected files
- nearby subsystem
- possible interpretation, clearly labeled as inference
```

---

## System Flow

```text
Public GitHub Repository
          |
          v
Repository Validation
          |
          v
GitHub Metadata + Source Ingestion
          |
          v
Repository Ontology
          |
          v
Deterministic Structural Graph
          |
          v
Code Dependency Analysis
          |
          v
Graph Algorithms + Embeddings
          |
          v
Subsystem + Decision Extraction
          |
          v
Software Atlas Generation
          |
          v
Hybrid Retrieval + Reasoning
          |
          v
Interactive Evidence-Backed UI
```

---

## Repository Ontology

Trace models software using a repository ontology rather than treating all content as flat text.

Primary entity types:

```text
Repository
Directory
File
Symbol
Issue
PullRequest
Commit
Release
Discussion
Person
Label
Subsystem
Topic
Decision
LearningStep
```

Primary deterministic relationships:

```text
CONTAINS
AUTHORED
REVIEWED
RESOLVES
REFERENCES
INCLUDES_COMMIT
MODIFIES
IMPORTS
DEPENDS_ON
LABELED
RELEASE_INCLUDES
```

Primary inferred relationships:

```text
PART_OF_SUBSYSTEM
ABOUT
DERIVED_FROM
RELATED_TO
RECOMMENDED_BEFORE
```

The ontology is documented separately in [`docs/ontology.md`](docs/ontology.md).

---

## AI Architecture

Trace is not a single prompt over a repository.

The AI system combines:

- deterministic metadata extraction
- source parsing
- graph construction
- graph algorithms
- vector embeddings
- clustering
- adaptive retrieval
- structured LLM extraction
- evidence verification
- citation generation

### Subsystem Discovery

Subsystems are not generated by asking an LLM to summarize the whole repository.

Trace combines:

```text
directory structure
+ import graph
+ dependency graph
+ file embeddings
+ naming patterns
+ labels and topics
        |
        v
candidate clusters
        |
        v
graph community detection
        |
        v
LLM naming and explanation
        |
        v
evidence-backed subsystem
```

### Decision Extraction

```text
issues + discussions + pull requests + commits
        |
        v
deterministic artifact links
        |
        v
semantic clustering
        |
        v
candidate decision groups
        |
        v
structured LLM extraction
        |
        v
evidence verification
        |
        v
Decision node
```

No supporting evidence means no confirmed decision.

### Query Reasoning

```text
classify question
        |
        v
choose retrieval strategy
        |
        v
retrieve seed evidence
        |
        v
expand graph neighborhood
        |
        v
rank evidence
        |
        v
generate answer
        |
        v
verify citations
        |
        v
return structured response
```

Retrieval modes:

- vector-first
- graph-first
- metadata-first
- adaptive hybrid

---

## Research and Evaluation

Trace is both a product and an evaluated AI system.

Research question:

> Does an adaptive graph-augmented Software Atlas improve repository-understanding answers compared with vector-only retrieval?

Planned systems:

1. keyword or metadata retrieval
2. vector-only RAG
3. graph-augmented retrieval
4. adaptive hybrid retrieval

Evaluation categories:

- architecture understanding
- subsystem identification
- decision traceability
- historical evolution
- contributor expertise
- semantic repository search

Metrics:

- faithfulness
- answer relevance
- context precision
- context recall
- citation correctness
- evidence coverage
- latency
- token cost
- graph-edge precision
- subsystem quality through manual review

A hand-labeled QA set will contain gold answers and gold evidence references.

Trace will also compare task completion using:

```text
GitHub + README
vs.
Trace Software Atlas
```

Measured outcomes:

- time to answer
- answer correctness
- evidence quality
- perceived usefulness

---

## Tech Stack

### Frontend

- React
- TypeScript
- Vite
- TanStack Query
- React Router
- Tailwind CSS
- `react-chartjs-2`
- Chart.js
- Cytoscape.js
- Vitest
- React Testing Library
- Playwright later in MVP

### Backend

- Python 3.13
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- HTTPX
- LangGraph
- NetworkX
- pytest
- Ruff
- mypy

### Data

- PostgreSQL
- pgvector
- Redis

### Infrastructure

- Docker Compose
- GitHub Actions
- `uv`
- npm

### Provider Strategy

LLM and embedding providers use abstractions.

Goals:

- allow free/local providers when practical
- avoid hard dependency on one commercial API
- compare provider quality and cost
- keep extraction and reasoning pipelines provider-independent

---

## Visualization Strategy

Trace uses different tools for different visual tasks.

### `react-chartjs-2`

Used for:

- language distribution
- repository activity
- contributor activity
- timeline trends
- release frequency
- evaluation results
- latency and cost metrics

### Cytoscape.js

Used for:

- architecture maps
- subsystem relationships
- repository entity exploration
- evidence paths
- dependency networks

Chart.js is not used as a replacement for graph visualization.

---

## MVP Scope

### Included

- public GitHub repositories
- one repository per Atlas
- Python source analysis
- TypeScript source analysis
- JavaScript source analysis
- repository metadata ingestion
- issues
- pull requests
- commits
- releases
- discussions when available
- contributors
- source tree
- deterministic graph construction
- embeddings
- subsystem discovery
- decision extraction
- architecture view
- timeline
- contributor explorer
- graph exploration
- evidence-backed AI answers
- evaluation harness
- Docker Compose
- CI

### Excluded

- authentication
- user accounts
- private repositories
- GitHub OAuth
- organizations
- billing
- team workspaces
- real-time webhooks
- multi-repository reasoning
- IDE extension
- automatic code editing
- arbitrary Git providers
- production-scale crawling
- complete AST support for every language
- perfect runtime call-graph analysis

### Future

- private repositories
- organizations
- continuous synchronization
- multi-repository Atlases
- Neo4j graph-storage implementation
- IDE integration
- repository comparison
- learning mode
- impact analysis
- repository health intelligence

MVP uses PostgreSQL for graph storage.

A graph repository abstraction will allow a future Neo4j implementation without redesigning product logic.

---

## Supported Repository Profile

Best MVP results require:

- public repository
- default branch
- approximately 500–5,000 GitHub artifacts
- approximately 100–5,000 relevant source files
- active issue and pull-request history
- releases
- multiple contributors
- identifiable subsystems
- Python, TypeScript, or JavaScript as primary language

Other languages may be ingested with reduced code-structure analysis.

---

## API Direction

Core endpoints:

```http
POST /api/repositories
GET  /api/repositories/{repository_id}
GET  /api/repositories/{repository_id}/ingestion
GET  /api/repositories/{repository_id}/overview
GET  /api/repositories/{repository_id}/architecture
GET  /api/repositories/{repository_id}/subsystems
GET  /api/repositories/{repository_id}/decisions
GET  /api/repositories/{repository_id}/timeline
GET  /api/repositories/{repository_id}/contributors
GET  /api/repositories/{repository_id}/graph
POST /api/repositories/{repository_id}/query
```

Detailed contracts live in [`docs/api.md`](docs/api.md).

---

## Local Development

### Requirements

- Docker Desktop
- Node.js 24
- Python 3.13
- `uv`
- npm
- GitHub personal access token with read-only public-repository access

### Environment

Create root `.env` from `.env.example`.

Expected services:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/trace
REDIS_URL=redis://redis:6379/0
GITHUB_TOKEN=your_read_only_token
```

Provider-specific LLM and embedding variables will be documented when those integrations land.

Never commit secrets.

### Start Full Stack

```bash
docker compose up --build
```

Expected local services:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
Docs:     http://localhost:8000/docs
Postgres: internal Docker network
Redis:    internal Docker network
```

### Backend Checks

```bash
cd backend
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest
```

### Frontend Checks

```bash
cd frontend
npm ci
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run build
```

---

## Repository Structure

```text
trace/
├── README.md
├── compose.yaml
├── .env.example
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   ├── ontology.md
│   ├── api.md
│   ├── database.md
│   ├── ai-pipeline.md
│   ├── evaluation.md
│   └── roadmap.md
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── alembic/
│   ├── src/
│   │   ├── api/
│   │   ├── db/
│   │   ├── ingestion/
│   │   ├── ontology/
│   │   ├── graph/
│   │   ├── semantic/
│   │   ├── atlas/
│   │   ├── retrieval/
│   │   ├── reasoning/
│   │   └── providers/
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── Dockerfile
│   └── src/
│       ├── api/
│       ├── components/
│       ├── features/
│       ├── pages/
│       ├── routes/
│       └── types/
└── eval/
    ├── qa-set.jsonl
    ├── run-eval.py
    └── results/
```

Structure may evolve internally while product scope remains locked.

---

## Delivery Milestones

### P0 — Foundation

- Docker Compose
- Postgres
- Redis
- FastAPI
- React
- CI
- health checks

### P1 — Repository Submission

- GitHub URL validation
- repository persistence
- ingestion-job persistence
- repository status API
- ingestion status API
- landing page

### P2 — GitHub Ingestion

- repository metadata
- source tree
- issues
- pull requests
- commits
- releases
- contributors
- raw payload persistence
- pagination
- rate-limit handling
- retry and resume

### P3 — Deterministic Graph

- ontology entities
- structural edges
- issue/PR references
- commit/file relationships
- Python imports
- TypeScript/JavaScript imports
- graph integrity tests

### P4 — Atlas Core

- embeddings
- graph metrics
- subsystem discovery
- overview generation
- subsystem pages
- architecture view

### P5 — History Intelligence

- timeline
- decision candidates
- decision extraction
- evidence chains
- contributor expertise

### P6 — Reasoning

- query classifier
- retrieval router
- graph retrieval
- vector retrieval
- adaptive hybrid retrieval
- LangGraph workflow
- citation verification
- Ask interface

### P7 — Evaluation

- hand-labeled QA set
- vector baseline
- graph baseline
- adaptive hybrid system
- metric reporting
- user-study workflow

### P8 — Portfolio Polish

- polished UX
- demo repository
- deployed demo when feasible
- demo video
- final technical report
- evaluation results
- architecture documentation

---

## Quality Standards

### UX

- repository value visible before user asks AI
- no graph shown without clear meaning
- evidence accessible from every inferred output
- loading stages understandable
- empty states useful
- errors actionable
- keyboard and responsive behavior considered

### Engineering

- typed API boundaries
- database migrations
- idempotent ingestion
- resumable jobs
- structured logging
- tests for core graph construction
- CI required
- provider abstractions
- no secrets in repository

### AI

- structured outputs
- evidence validation
- confidence
- reproducible extractor versions
- baseline comparison
- failure analysis
- no unsupported certainty

---

## Security

MVP accepts only public GitHub repository URLs.

Rules:

- validate GitHub host and path
- do not execute arbitrary user-provided shell commands
- do not expose GitHub token to frontend
- use read-only token scopes
- store secrets only in environment variables
- sanitize rendered repository content
- enforce request and ingestion limits
- protect against prompt injection from repository text
- treat repository content as untrusted data, not system instruction

---

## Contributing

Trace is currently a solo portfolio project.

Contributions may open after MVP architecture stabilizes.

Before contributing:

1. read `docs/prd.md`
2. read `docs/architecture.md`
3. run all local checks
4. keep deterministic and inferred knowledge separate
5. add evidence handling for new AI-derived outputs
6. avoid adding features outside locked MVP scope

---

## License

License will be selected before public release.

Until then, source availability does not imply permission for redistribution or commercial reuse.

---

## Final Pitch

> Trace is an AI Software Intelligence platform that converts public GitHub repositories into interactive Software Atlases. It combines repository ontologies, deterministic knowledge graphs, graph algorithms, semantic retrieval, and evidence-backed LLM reasoning to help people understand software architecture, decisions, evolution, and ownership in minutes.
