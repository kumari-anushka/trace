# Trace

> Understand any GitHub repository in minutes.

Trace is an AI Software Intelligence platform that converts public GitHub repositories into interactive **Software Atlases**.

A Software Atlas helps users understand:

- architecture
- subsystems
- dependencies
- decisions
- project history
- contributor activity
- evidence-backed answers

## Core Flow

```text
GitHub Repository
    ↓
Ingestion
    ↓
Source Parsing
    ↓
Repository Ontology
    ↓
Knowledge Graph
    ↓
Embeddings + AI Analysis
    ↓
Software Atlas
```

## Atlas Sections

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

Every inferred result must include:

- confidence
- supporting evidence
- provenance

## Tech Stack

**Frontend**

- React
- TypeScript
- Vite
- Tailwind CSS
- Cytoscape.js
- react-chartjs-2

**Backend**

- Python 3.13
- FastAPI
- SQLAlchemy
- Alembic
- NetworkX
- LangGraph

**Data and Infra**

- PostgreSQL
- pgvector
- Redis
- Docker Compose
- GitHub Actions

## Current Scope

MVP includes:

- public GitHub repositories
- Python, TypeScript, and JavaScript analysis
- deterministic repository graph
- subsystem discovery
- decision extraction
- contributor intelligence
- adaptive Graph RAG
- cited AI answers
- evaluation against retrieval baselines

MVP excludes:

- authentication
- private repositories
- billing
- code generation
- automatic code edits
- Neo4j

## Local Development

Prerequisites:

- Docker with Compose
- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- Node.js 24

Create the local configuration files, then install dependencies:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
make setup
```

For the fastest development loop, run PostgreSQL and Redis in Docker:

```bash
make infra
```

Then run the applications in separate terminals:

```bash
make backend-dev
make frontend-dev
```

To run the complete stack in Docker instead:

```bash
make dev
```

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
API Docs: http://localhost:8000/docs
```

Common checks:

```bash
make test
make lint
```

Stop the Docker stack:

```bash
make down
```

## Documentation

- [`docs/overview.md`](docs/overview.md)
- [`docs/product.md`](docs/product.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/ontology.md`](docs/ontology.md)
- [`docs/ai-system.md`](docs/ai-system.md)
- [`docs/database.md`](docs/database.md)
- [`docs/api.md`](docs/api.md)
- [`docs/evaluation.md`](docs/evaluation.md)
- [`docs/ux.md`](docs/ux.md)
- [`docs/roadmap.md`](docs/roadmap.md)

## Research Question

> Does an adaptive graph-augmented Software Atlas improve unfamiliar-repository understanding compared with vector-only retrieval?

## Status

Under active development.
