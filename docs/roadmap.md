# Trace — Build Roadmap

> Delivery plan for building Trace from repository skeleton to a portfolio-ready, research-evaluable AI Software Intelligence platform.

This roadmap prioritizes:

1. working product
2. reliable engineering
3. explainable AI
4. measurable research
5. polished portfolio delivery

Related documents:

- `[overview.md](overview.md)` — product context
- `[product.md](product.md)` — functional requirements
- `[architecture.md](architecture.md)` — system architecture
- `[ontology.md](ontology.md)` — repository knowledge model
- `[ai-system.md](ai-system.md)` — AI pipeline
- `[database.md](database.md)` — persistence design
- `[api.md](api.md)` — API contracts
- `[evaluation.md](evaluation.md)` — research plan
- `[ux.md](ux.md)` — interaction design

---



## 1. Roadmap Goal

Build a complete MVP that can:

```text
Accept public GitHub repository
    ↓
Ingest repository artifacts
    ↓
Build deterministic repository graph
    ↓
Generate embeddings
    ↓
Discover subsystems
    ↓
Extract evidence-backed decisions
    ↓
Generate Software Atlas
    ↓
Answer cited repository questions
    ↓
Compare hybrid retrieval against baselines
```

Final output must be:

- runnable locally
- testable
- documented
- visually polished
- evidence-backed
- evaluation-ready
- suitable for portfolio and MSc discussion

---



## 2. Delivery Constraints

Primary constraint:

```text
Approximately 6 weeks
```

The roadmap assumes:

- one main developer
- part-time weekday work
- longer weekend build sessions
- existing React experience
- intermediate Python/FastAPI/PostgreSQL knowledge
- beginner-to-intermediate AI/ML knowledge
- public repositories only
- no authentication in MVP
- no billing
- no private repositories
- no Neo4j in MVP

---



## 3. Priority Order

When trade-offs appear, use:

```text
UX
    ↓
Engineering reliability
    ↓
AI quality
    ↓
Product polish
    ↓
Advanced scale
```

Do not sacrifice evidence quality for impressive AI output.

Do not add V2 features before core Atlas works.

---



## 4. Milestone Overview


| Milestone | Name                    | Main Output                                      |
| --------- | ----------------------- | ------------------------------------------------ |
| P0        | Foundation              | Stable local stack, CI, project structure        |
| P1        | Repository Submission   | URL validation, repository records, job progress |
| P2        | GitHub Ingestion        | Metadata, files, issues, PRs, commits, releases  |
| P3        | Structural Intelligence | Parsers, ontology, deterministic graph           |
| P4        | Software Atlas Core     | Overview, Architecture, Subsystems, Timeline     |
| P5        | Historical Intelligence | Decisions, contributors, evidence chains         |
| P6        | AI Reasoning            | Embeddings, adaptive retrieval, cited Ask        |
| P7        | Evaluation              | Baselines, QA dataset, metrics, experiments      |
| P8        | Portfolio Release       | UX polish, demo, docs, deployment, case study    |


---



## 5. Current Baseline

Expected existing baseline:

```text
trace/
├── backend/
├── frontend/
├── docs/
├── eval/
├── compose.yaml
└── README.md
```

Infrastructure already expected:

- FastAPI backend
- React/Vite frontend
- PostgreSQL
- Redis
- Docker Compose
- Ruff
- mypy
- pytest
- frontend lint/format/type checks
- GitHub Actions CI
- environment configuration

Before starting new product features, confirm baseline is green.

Checklist:

- [ ] `docker compose up --build` works
- [ ] backend health endpoint responds
- [ ] frontend loads
- [ ] PostgreSQL connection works
- [ ] Redis connection works
- [ ] backend CI passes
- [ ] frontend CI passes
- [ ] Alembic initialized
- [ ] local `.env.example` exists
- [ ] no secrets committed

---



# 6. Week 1 — Foundation and Repository Submission



## Goal

Create stable product skeleton and asynchronous ingestion workflow.

## Learning Focus

- FastAPI service layering
- SQLAlchemy 2.x async patterns
- Alembic migrations
- Redis basics
- background-job architecture
- typed API contracts
- frontend server-state management

---



## Day 1 — Domain and Project Boundaries



### Build

Create backend modules:

```text
src/
├── api/
├── core/
├── db/
├── domain/
├── repositories/
├── services/
├── workers/
├── integrations/
├── graph/
├── parsers/
└── ai/
```

Create initial domain enums:

- RepositoryStatus
- AnalysisMode
- JobStatus
- StageStatus

Create repository domain model.

### Learn

- domain model vs Pydantic API schema
- repository pattern
- dependency injection in FastAPI
- why routes should not contain SQL



### Tests

- enum validation
- repository model validation
- settings tests



### Deliverable

Backend structure matches `architecture.md`.

---



## Day 2 — Database Foundation



### Build

Create Alembic migrations for:

- `repositories`
- `repository_snapshots`
- `ingestion_jobs`
- `ingestion_stages`

Create async SQLAlchemy session.

Create repository persistence layer.

### Learn

- SQLAlchemy declarative models
- async sessions
- transactions
- foreign keys
- unique constraints
- partial unique indexes



### Tests

- create repository
- prevent duplicate GitHub ID
- create active job
- prevent multiple active jobs
- cascade delete behavior



### Deliverable

Repository and job state persist across backend restart.

---



## Day 3 — Repository URL Validation



### Build

Implement:

```http
POST /api/repositories
```

Support:

- normalize GitHub URL
- reject nested GitHub URLs
- validate owner/repository
- check public repository
- detect existing Atlas
- create repository and job

Create GitHub client abstraction.

### Learn

- `httpx.AsyncClient`
- API timeouts
- retries
- external API error mapping
- provider-neutral adapters



### Tests

- valid repository
- invalid URL
- missing repository
- private repository
- duplicate repository
- GitHub timeout



### Frontend

Build landing page:

- URL input
- Generate Atlas button
- validation errors
- loading state



### Deliverable

User can submit public GitHub repository.

---



## Day 4 — Background Job Skeleton



### Build

Implement worker process.

Minimum queue flow:

```text
API
→ Redis queue
→ Worker
→ PostgreSQL progress
```

Create stage runner abstraction.

Example:

```python
class PipelineStage(Protocol):
    name: str

    async def run(self, context: PipelineContext) -> StageResult:
        ...
```



### Learn

- queue semantics
- worker lifecycle
- idempotency
- retries
- source of truth vs cache



### Tests

- enqueue job
- worker consumes job
- stage updates
- worker failure persists error
- retry does not duplicate job output



### Deliverable

Job moves:

```text
queued → running → completed
```

---



## Day 5 — Progress UI



### Build

Implement:

```http
GET /api/repositories/{repository_id}/ingestion
```

Frontend progress page:

- overall progress
- current stage
- stage list
- failed stage
- retry state
- Open Atlas action

Use polling.

### Learn

- TanStack Query polling
- UI state machines
- partial/failed states
- polling cleanup



### Tests

- progress updates
- refresh persists state
- error page
- completed redirect



### Deliverable

User sees live ingestion progress.

---



## Week 1 Exit Gate

Must pass:

- [ ] repository URL submission works
- [ ] repository state persists
- [ ] job runs asynchronously
- [ ] progress page works
- [ ] duplicate active jobs prevented
- [ ] errors are typed
- [ ] CI green
- [ ] Docker Compose green

Do not start AI work before this gate passes.

---



# 7. Week 2 — GitHub Ingestion



## Goal

Collect and normalize repository facts.

## Learning Focus

- GitHub REST/GraphQL concepts
- pagination
- API rate limits
- data normalization
- bulk inserts
- resumable ingestion
- provider fixtures

---



## Day 1 — Repository Metadata and Snapshot



### Build

Fetch:

- repository metadata
- default branch
- HEAD commit SHA
- language distribution

Create `repository_snapshots`.

Persist snapshot version.

### Tests

- metadata normalization
- snapshot uniqueness
- unchanged HEAD reuses snapshot
- provider failure



### Deliverable

Repository has reproducible snapshot.

---



## Day 2 — Source Tree and Files



### Build

Create:

- `source_files`
- optional `source_file_contents`

Fetch source tree.

Classify files:

- source
- test
- documentation
- generated
- binary
- ignored



### Learn

- Git trees
- blob SHAs
- content hashing
- file filtering
- batched writes



### Tests

- path normalization
- file classification
- binary skip
- generated-file skip
- content hash



### Deliverable

Source tree visible in DB.

---



## Day 3 — Issues and Pull Requests



### Build

Create:

- `people`
- `issues`
- `pull_requests`
- `labels`
- join tables

Fetch with pagination.

Normalize authors and timestamps.

### Learn

- provider pagination
- upserts
- external ID identity
- rate-limit handling



### Tests

- duplicate artifact update
- labels
- author resolution
- closed/merged states
- pagination



### Deliverable

Issues and PRs persist.

---



## Day 4 — Commits, Files, Releases



### Build

Create:

- `commits`
- `commit_parents`
- `commit_files`
- `releases`
- `pull_request_commits`

Fetch bounded commit history.

Map commits to changed files.

### Tests

- commit uniqueness
- parent links
- changed file status
- release uniqueness
- PR-commit link



### Deliverable

Repository history graph facts exist.

---



## Day 5 — Contributors and Reviews



### Build

Fetch:

- contributors
- pull-request reviews when available
- contribution activity

Create review records.

Mark bots.

### Tests

- bot detection
- reviewer mapping
- missing GitHub user
- Git author vs GitHub identity not merged incorrectly



### Deliverable

Contributor evidence exists.

---



## Weekend — Ingestion Hardening



### Build

- stage-specific retries
- rate-limit state
- batched DB writes
- stage output summaries
- partial failure behavior
- fixture-based GitHub tests



### Test Repositories

Use 2–3 known repositories:

- small Python repo
- medium TypeScript repo
- medium JavaScript repo



### Week 2 Exit Gate

- [ ] metadata ingested
- [ ] snapshot stored
- [ ] source tree stored
- [ ] issues stored
- [ ] PRs stored
- [ ] commits stored
- [ ] releases stored
- [ ] contributors stored
- [ ] retries idempotent
- [ ] provider tests use fixtures
- [ ] rate-limit error handled

---



# 8. Week 3 — Structural Intelligence and Ontology



## Goal

Convert raw repository artifacts into deterministic knowledge graph.

## Learning Focus

- AST basics
- import graphs
- graph theory
- NetworkX
- ontology design
- recursive SQL
- graph provenance

---



## Day 1 — Ontology Persistence



### Build

Create:

- `graph_nodes`
- `graph_edges`
- `evidence`
- `graph_metrics`

Implement:

```text
GraphRepository
```

Methods:

- upsert node
- upsert edge
- neighbors
- subgraph
- bounded traversal



### Tests

- canonical keys
- edge uniqueness
- no invalid self-loop
- repository/snapshot scoping
- inferred confidence requirement



### Deliverable

Graph persistence works.

---



## Day 2 — Filesystem and Artifact Graph



### Build

Generate deterministic nodes:

- Repository
- RepositorySnapshot
- Directory
- File
- Issue
- PullRequest
- Commit
- Release
- Person
- Label

Generate deterministic edges:

- CONTAINS
- AUTHORED
- REVIEWED
- MODIFIES
- REFERENCES
- RESOLVES
- RELEASE_INCLUDES
- LABELED_WITH
- PARENT_OF



### Tests

- expected node count
- expected edge count
- evidence attached
- repeated run unchanged



### Deliverable

Historical and filesystem graph exists.

---



## Day 3 — Python Parser



### Build

Extract:

- imports
- classes
- functions
- methods
- routes when detectable
- inheritance
- calls where reliable

Create Symbol nodes.

Create edges:

- DECLARES
- IMPORTS
- EXTENDS
- CALLS



### Learn

- Python `ast`
- qualified names
- line spans
- import resolution



### Tests

Use parser fixtures.

Cover:

- relative imports
- aliased imports
- nested functions
- class methods
- syntax error
- unresolved import



### Deliverable

Python structural graph works.

---



## Day 4 — TypeScript and JavaScript Parser



### Build

Choose parser route:

- tree-sitter
- TypeScript compiler API through helper service/script
- maintained Python parsing library

Extract:

- imports
- exports
- functions
- classes
- interfaces
- React components
- hooks
- routes where detectable



### Learn

- AST differences
- ES modules
- CommonJS
- JSX/TSX



### Tests

- default import
- named import
- dynamic import
- component
- hook
- parse failure



### Deliverable

TS/JS structural graph works.

---



## Day 5 — Graph Analysis



### Build

Use NetworkX for:

- connected components
- PageRank
- degree centrality
- betweenness centrality
- community detection
- dependency cycles

Persist graph metrics.

### Learn

- graph direction
- centrality meaning
- community detection limitations
- why centrality is not business importance



### Tests

- known small graph
- cycle detection
- deterministic metric results
- disconnected graph



### Deliverable

Repository graph has analytical signals.

---



## Weekend — Architecture Graph API and UI



### Backend

Implement:

```http
GET /api/repositories/{id}/architecture
GET /api/repositories/{id}/graph
GET /api/repositories/{id}/graph/nodes/{node_id}/neighbors
```



### Frontend

Build Cytoscape.js base:

- nodes
- edges
- pan
- zoom
- selection
- detail panel
- legend
- evidence drawer



### Week 3 Exit Gate

- [ ] ontology tables exist
- [ ] graph builder idempotent
- [ ] artifact graph exists
- [ ] Python parser works
- [ ] TS/JS parser works
- [ ] NetworkX metrics stored
- [ ] graph API works
- [ ] graph UI renders
- [ ] deterministic/inferred styles prepared

---



# 9. Week 4 — Software Atlas Core



## Goal

Generate useful product experience before advanced question answering.

## Learning Focus

- embeddings
- clustering
- semantic similarity
- graph communities
- structured LLM output
- evidence verification
- data visualization

---



## Day 1 — Embedding Infrastructure



### Build

Create:

- `documents`
- `embedding_spaces`
- `embeddings`

Implement provider interface.

Support:

- one hosted embedding provider
- one local/free option if practical

Implement:

- chunking
- content hashing
- batch embeddings
- pgvector search



### Tests

- chunk metadata
- cache unchanged content
- dimension validation
- similarity ordering
- repository filter



### Deliverable

Semantic retrieval works.

---



## Day 2 — Subsystem Discovery



### Build

Combine:

- import community
- directory structure
- semantic cohesion
- file naming
- historical co-change signals

Create candidate clusters.

Use LLM only for:

- naming
- summarizing
- rationale

Persist:

- Subsystem node
- confidence
- discovery signals
- PART_OF_SUBSYSTEM edges
- evidence



### Tests

- known fixture clusters
- low-confidence candidate
- no subsystem case
- repeated run stability



### Deliverable

Subsystems generated.

---



## Day 3 — Architecture Synthesis



### Build

Generate:

- architecture summary
- entry points
- major components
- external dependencies
- subsystem dependency graph

Rules:

- no runtime claim from import only
- no microservice claim from folder only
- every component links to graph evidence



### Deliverable

Architecture Atlas payload ready.

---



## Day 4 — Overview API and UI



### Backend

Implement:

```http
GET /api/repositories/{id}/overview
```



### Frontend

Build:

- summary
- stats
- language chart
- major subsystems
- architecture summary
- suggested learning order
- recent releases
- important decisions placeholder

Use `react-chartjs-2`.

### Deliverable

Overview provides value without chat.

---



## Day 5 — Subsystems UI



### Build

- subsystem list
- confidence/status filters
- subsystem detail
- discovery explanation
- key files
- dependencies
- evidence panel
- related timeline



### Deliverable

Subsystem exploration complete.

---



## Weekend — Timeline



### Backend

Implement timeline aggregation.

### Frontend

Build:

- activity chart
- release frequency
- event stream
- filters
- event drawer



### Week 4 Exit Gate

- [ ] embeddings work
- [ ] pgvector search works
- [ ] subsystem discovery works
- [ ] architecture summary works
- [ ] Overview complete
- [ ] Architecture graph usable
- [ ] Subsystems complete
- [ ] Timeline complete
- [ ] every inference shows confidence/evidence

At this point Trace must already feel like a product.

---



# 10. Week 5 — Decisions, Contributors, and Ask



## Goal

Add historical reasoning, ownership intelligence, and cited question answering.

## Learning Focus

- RAG
- graph retrieval
- hybrid retrieval
- LangGraph
- structured reasoning
- citation verification
- confidence scoring

---



## Day 1 — Decision Candidate Generation



### Build

Find candidates from:

- issues
- PRs
- discussions
- releases
- dependency changes
- broad co-change events
- decision language

Build evidence clusters.

### Tests

- explicit decision
- weak candidate
- irrelevant PR
- contradictory artifacts



### Deliverable

Decision candidates exist.

---



## Day 2 — Decision Extraction and Verification



### Build

Extract:

- context
- decision
- alternatives
- outcome
- date
- affected subsystem
- evidence chain

States:

- candidate
- confirmed
- insufficient_evidence
- rejected

Confirmation requires non-model evidence.

### Frontend

Build decision list and detail.

### Deliverable

Evidence-backed Decisions page complete.

---



## Day 3 — Contributor Intelligence



### Build

Calculate:

- authored PR score
- reviewed PR score
- commit score
- subsystem file score
- recency score
- total expertise score

Use cautious language.

### Frontend

Build:

- contributor list
- score breakdown
- subsystem activity
- timeline
- GitHub profile links



### Deliverable

Contributors page complete.

---



## Day 4 — Retrieval Layer



### Build

Implement:

- metadata retriever
- vector retriever
- graph retriever
- entity resolver
- reranker

Create retrieval result schema.

### Tests

- exact metadata query
- semantic query
- graph dependency query
- mixed query
- filters
- no evidence



### Deliverable

All retrieval modes work independently.

---



## Day 5 — Adaptive Ask Workflow



### Build

Use LangGraph:

```text
classify intent
→ resolve entities
→ plan retrieval
→ metadata retrieval
→ vector retrieval
→ graph expansion
→ rerank
→ assemble context
→ generate answer
→ verify citations
→ calculate confidence
```

Implement:

```http
POST /api/repositories/{id}/query
```



### Response

- answer
- confidence
- evidence
- citations
- graph path
- related files
- related decisions
- timeline context
- limitations
- possible interpretations
- suggested follow-up



### Deliverable

Cited Ask API works.

---



## Weekend — Ask UI and Evidence UX



### Build

- suggested questions
- question input
- loading stages
- structured answer
- citation interaction
- evidence drawer
- confidence
- limitations
- possible interpretations
- related entities



### Week 5 Exit Gate

- [ ] decisions confirmed only with evidence
- [ ] contributor scoring explainable
- [ ] metadata retrieval works
- [ ] vector retrieval works
- [ ] graph retrieval works
- [ ] adaptive router works
- [ ] Ask returns citations
- [ ] citation verification works
- [ ] insufficient evidence behavior works
- [ ] no private chain-of-thought exposed

---



# 11. Week 6 — Evaluation and Portfolio Release



## Goal

Prove quality, polish product, and create credible release.

## Learning Focus

- experiment design
- retrieval metrics
- statistical comparison
- Playwright
- accessibility
- deployment
- technical writing

---



## Day 1 — Evaluation Dataset



### Build

Create:

```text
eval/
├── datasets/
├── configs/
├── runners/
├── metrics/
├── reports/
└── fixtures/
```

Select 3–5 repositories for MVP evaluation.

Write:

- 30–50 QA cases
- expected answers
- gold evidence
- categories
- difficulty



### Deliverable

Versioned QA dataset exists.

---



## Day 2 — Baselines



### Build

Implement:

- keyword retrieval
- vector-only RAG
- graph-only retrieval
- adaptive hybrid retrieval

Keep:

- same generator model
- same token budget
- same questions
- same snapshots



### Deliverable

Four systems runnable through same harness.

---



## Day 3 — Metrics and Reports



### Calculate

- Precision@k
- Recall@k
- Hit Rate@k
- MRR
- faithfulness
- citation correctness
- unsupported claim rate
- latency
- token usage
- cost

Generate:

- JSON report
- CSV report
- Markdown report
- charts



### Deliverable

Evaluation report exists.

---



## Day 4 — End-to-End Testing



### Playwright

Test:

- submit repository
- progress
- Overview
- Architecture
- Subsystems
- Timeline
- Decisions
- Contributors
- Explore
- Ask
- evidence drawer
- partial failure



### Backend

Run:

- unit tests
- integration tests
- migration tests
- provider fixture tests



### Deliverable

Critical paths automated.

---



## Day 5 — Accessibility and Responsive Pass



### Check

- keyboard navigation
- focus state
- semantic headings
- chart summaries
- graph non-visual path
- contrast
- reduced motion
- mobile Overview
- mobile Ask
- mobile Timeline



### Deliverable

Core UI meets practical accessibility bar.

---



## Weekend — Release Package



### Product Polish

- fix empty states
- fix loading states
- fix error states
- reduce graph clutter
- tune copy
- improve evidence UI
- add sample Atlas



### Documentation

Finalize:

- README
- docs index
- architecture diagrams
- setup instructions
- evaluation summary
- known limitations
- roadmap status



### Demo

Create:

- 2–4 minute demo video
- screenshots
- architecture image
- sample questions
- benchmark chart



### Deployment

Deploy:

- frontend
- backend
- worker
- PostgreSQL
- Redis

Or provide reproducible local demo if hosted deployment cost is unsuitable.

### Week 6 Exit Gate

- [ ] one-command local start
- [ ] all core pages work
- [ ] Ask cited
- [ ] evidence inspectable
- [ ] evaluation report complete
- [ ] E2E tests pass
- [ ] docs accurate
- [ ] demo ready
- [ ] limitations honest
- [ ] release tagged

---



# 12. Detailed Milestone Acceptance Criteria



## P0 — Foundation

Complete when:

- backend/frontend run
- Docker Compose works
- CI works
- config safe
- migrations work
- health checks exist



## P1 — Repository Submission

Complete when:

- public URL validates
- repository persists
- async job created
- progress visible
- duplicate jobs prevented



## P2 — GitHub Ingestion

Complete when:

- artifacts normalize
- pagination works
- rate limits handled
- snapshot fixed
- retry idempotent



## P3 — Structural Intelligence

Complete when:

- parsers extract symbols/imports
- graph nodes/edges persist
- evidence links exist
- NetworkX metrics stored
- graph API bounded



## P4 — Software Atlas Core

Complete when:

- Overview useful without Ask
- Architecture graph usable
- subsystems explainable
- timeline filterable
- partial states handled



## P5 — Historical Intelligence

Complete when:

- decisions require evidence
- contributor score explainable
- evidence chain navigable
- candidate/confirmed distinction visible



## P6 — AI Reasoning

Complete when:

- adaptive retrieval works
- answers cited
- unsupported claims filtered
- confidence visible
- weak evidence returns useful fallback



## P7 — Evaluation

Complete when:

- dataset versioned
- baselines runnable
- metrics stored
- experiments reproducible
- results reported honestly



## P8 — Portfolio Release

Complete when:

- visual quality strong
- docs coherent
- demo clear
- setup reproducible
- project limitations explicit

---



# 13. Learning Outcomes by Area



## Backend

By completion:

- FastAPI architecture
- async SQLAlchemy
- Alembic
- PostgreSQL constraints
- Redis queue
- background workers
- retries
- structured logging
- API design
- testing



## Frontend

By completion:

- product-level React architecture
- TanStack Query
- complex async states
- Cytoscape.js
- Chart.js
- accessible dense UI
- Playwright
- responsive technical interfaces



## AI/ML

By completion:

- embeddings
- vector search
- chunking
- RAG
- Graph RAG
- hybrid retrieval
- reranking
- LangGraph
- structured outputs
- citation verification
- evaluation metrics



## Graphs

By completion:

- graph modeling
- ontologies
- centrality
- communities
- graph traversal
- graph visualization
- graph persistence abstraction



## Research

By completion:

- research questions
- hypotheses
- baselines
- datasets
- gold evidence
- metrics
- human study design
- limitations
- reproducibility

---



# 14. Scope Control

Do not add during MVP:

- authentication
- private repositories
- billing
- teams
- organizations
- GitLab
- Bitbucket
- IDE extension
- code generation
- automatic code edits
- Neo4j
- Kubernetes
- real-time webhooks
- multi-repository Atlas
- complex permissions

When tempted to add feature, ask:

```text
Does this improve unfamiliar-repository understanding?
Is it required for current milestone?
Can it be measured?
Does it block core Atlas?
```

If no:

```text
move to future roadmap
```

---



# 15. Risk Register



## Risk — GitHub Rate Limits

Mitigation:

- token
- caching
- pagination
- bounded history
- retries
- rate-limit visibility



## Risk — Large Repositories

Mitigation:

- file limits
- artifact limits
- exclusions
- batching
- reduced-analysis mode



## Risk — Parser Complexity

Mitigation:

- support only Python/TS/JS
- generic fallback
- parser failure isolation
- fixture tests



## Risk — LLM Cost

Mitigation:

- structured small prompts
- content hashing
- cache
- batch embeddings
- task-specific model
- local embeddings



## Risk — Hallucinations

Mitigation:

- deterministic first
- evidence requirement
- structured output
- citation verification
- confidence
- insufficient-evidence state



## Risk — Graph Overload

Mitigation:

- limited default nodes
- user-driven expansion
- filters
- node cap
- architecture-focused view



## Risk — Timeline Slip

Mitigation:

- weekly gates
- scope freeze
- P0/P1 first
- no auth
- no Neo4j
- one repository at a time
- partial Atlas accepted

---



# 16. Weekly Review Template

At end of each week, record:

```text
Completed
Blocked
Deferred
Tests added
Docs updated
Demo available
Main lesson
Next week's first task
```

Also answer:

- Does product still match docs?
- Does every inference have evidence?
- Is CI green?
- Can current milestone be demonstrated?
- Did scope expand without reason?

---



# 17. Branch and Commit Strategy

Suggested branches:

```text
feat/repository-ingestion
feat/source-parser
feat/knowledge-graph
feat/subsystem-discovery
feat/ask-workflow
```

Commit style:

```text
feat: add repository URL validation
feat: persist ingestion stages
test: cover GitHub pagination
docs: add ontology relationship rules
fix: make graph ingestion idempotent
```

Keep commits small and explainable.

---



# 18. Definition of Done

A task is done only when:

- code works
- tests exist
- errors handled
- types pass
- lint passes
- docs updated
- UI state exists where relevant
- acceptance criteria met
- demo path works

Not done:

```text
works on happy path only
```

---



# 19. Portfolio Story

Final project story:

```text
Problem:
Developers struggle to understand unfamiliar repositories.

Product:
Trace generates evidence-backed Software Atlases.

Engineering:
FastAPI, React, PostgreSQL, Redis, Docker, async workers.

AI:
Ontology, graph analysis, embeddings, Graph RAG, LangGraph.

Research:
Adaptive hybrid retrieval compared against keyword, vector, and graph baselines.

Trust:
Every inference exposes confidence and evidence.

Outcome:
Users understand repositories faster and with stronger source traceability.
```

---



# 20. Final Release Checklist



## Product

- [ ] Landing
- [ ] Progress
- [ ] Overview
- [ ] Architecture
- [ ] Subsystems
- [ ] Timeline
- [ ] Decisions
- [ ] Contributors
- [ ] Explore
- [ ] Ask
- [ ] Evidence drawer



## Engineering

- [ ] migrations
- [ ] async jobs
- [ ] idempotency
- [ ] typed API
- [ ] structured logs
- [ ] health checks
- [ ] CI
- [ ] Docker Compose
- [ ] tests



## AI

- [ ] graph construction
- [ ] embeddings
- [ ] subsystem discovery
- [ ] decision extraction
- [ ] adaptive retrieval
- [ ] citation verification
- [ ] confidence
- [ ] failure fallback



## Evaluation

- [ ] repositories fixed by SHA
- [ ] QA dataset
- [ ] gold evidence
- [ ] baselines
- [ ] metrics
- [ ] results
- [ ] error analysis
- [ ] cost analysis



## Portfolio

- [ ] README
- [ ] docs
- [ ] screenshots
- [ ] demo video
- [ ] architecture diagram
- [ ] evaluation chart
- [ ] known limitations
- [ ] future roadmap
- [ ] release tag

---



## Final Roadmap Rule

> Build reliable repository facts first, useful Atlas second, advanced AI third, evaluation fourth, polish last.

