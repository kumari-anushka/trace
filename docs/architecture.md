# Trace — Architecture

## Approach

MVP uses a modular monolith plus background worker.

```text
React Frontend
    ↓
FastAPI API
    ↓
PostgreSQL + pgvector
    ↕
Redis Queue
    ↓
Worker
    ↓
GitHub + Model Providers
```

## Goals

- asynchronous ingestion
- stage-level retries
- deterministic-first analysis
- evidence-backed inference
- provider abstraction
- partial availability
- simple local setup

## Services

### Frontend

- React
- TypeScript
- Vite
- TanStack Query
- Tailwind CSS
- Cytoscape.js
- react-chartjs-2

### Backend API

Responsibilities:

- validation
- typed HTTP contracts
- repository reads
- Atlas reads
- search
- Ask queries
- job status

Must not contain:

- raw SQL in routes
- GitHub pagination logic
- graph algorithms
- prompts

### Worker

Responsibilities:

- GitHub ingestion
- source parsing
- graph construction
- graph analysis
- embeddings
- subsystem discovery
- decision extraction
- Atlas generation

### PostgreSQL

Source of truth for:

- repositories
- snapshots
- jobs
- artifacts
- source files
- graph
- evidence
- vectors
- Atlas data

### Redis

Used for:

- job queue
- progress events
- locks
- short-lived cache

Redis is not source of truth.

## Backend Modules

```text
src/
├── api/
├── core/
├── db/
├── domain/
├── repositories/
├── services/
├── integrations/
├── parsers/
├── graph/
├── ai/
├── workers/
└── main.py
```

## Main Pipeline

```text
validate
fetch_metadata
fetch_source_tree
fetch_artifacts
normalize
parse_source
build_graph
analyze_graph
generate_embeddings
discover_subsystems
extract_decisions
generate_atlas
verify_outputs
finalize
```

Each stage stores:

- status
- progress
- attempts
- start/end time
- error
- output summary

## Idempotency

Use:

- repository upsert by GitHub ID
- artifact upsert by provider ID
- file upsert by snapshot + path
- node upsert by canonical key
- edge upsert by relation identity
- embedding reuse by content hash + model

Retries must not duplicate data.

## Graph Storage

Application depends on:

```python
class GraphRepository(Protocol):
    async def upsert_node(self, node): ...
    async def upsert_edge(self, edge): ...
    async def neighbors(self, node_id, filters): ...
    async def subgraph(self, query): ...
```

MVP:

```text
PostgresGraphRepository
```

Future:

```text
Neo4jGraphRepository
```

## Graph Analysis

Use NetworkX for:

- connected components
- PageRank
- degree centrality
- betweenness centrality
- community detection
- dependency cycles

Persist results as metrics.

## Model Providers

Interfaces:

```python
class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts): ...
    async def embed_query(self, text): ...

class LLMProvider(Protocol):
    async def generate_structured(self, *, messages, schema): ...
```

Provider-specific SDKs stay in adapters.

## Main Runtime Flows

### Submit Repository

```text
Frontend
→ POST /repositories
→ validate GitHub repo
→ persist repository/job
→ enqueue Redis
→ return 202
```

### Build Atlas

```text
Worker
→ fetch GitHub data
→ persist artifacts
→ parse source
→ build graph
→ generate embeddings
→ infer subsystems/decisions
→ verify evidence
→ publish Atlas
```

### Ask

```text
Question
→ classify intent
→ metadata/vector/graph retrieval
→ rerank evidence
→ generate structured answer
→ verify citations
→ return response
```

## Failure Handling

- GitHub failure: retry stage
- parser failure: reduced analysis
- embedding failure: semantic features unavailable
- LLM failure: deterministic Atlas remains
- DB failure: rollback current transaction
- partial success: Atlas status = `partial`

## Security

- public repositories only
- read-only GitHub token
- secrets via env vars
- repository content treated as untrusted
- structured prompt boundaries
- output schema validation
- SQL parameterization
- no secret logging

## Local Deployment

```text
postgres
redis
backend
worker
frontend
```

Start:

```bash
docker compose up --build
```

## Testing

- unit: parsing, graph, validation, scoring
- integration: PostgreSQL, pgvector, Redis, GitHub fixtures
- contract: API schemas
- E2E: Playwright
- evaluation: retrieval and citation quality

## Architecture Constraints

MVP must not require:

- Neo4j
- Kubernetes
- auth
- microservices
- event streaming platform
- blocking HTTP ingestion
