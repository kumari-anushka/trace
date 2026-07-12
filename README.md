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

## Why Trace?

Repository knowledge is scattered across code, issues, pull requests, commits, releases, and discussions.

Trace connects these artifacts into one explorable system instead of forcing users to rebuild the mental model manually.

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

## Software Atlas

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

Every inferred result includes:

- confidence
- supporting evidence
- provenance

## Tech Stack

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Cytoscape.js
- react-chartjs-2

### Backend

- Python 3.13
- FastAPI
- SQLAlchemy
- Alembic
- NetworkX
- LangGraph

### Data and Infrastructure

- PostgreSQL
- pgvector
- Redis
- Docker Compose
- GitHub Actions

## Current Status

Under active development.

Current foundation:

- frontend and backend setup
- PostgreSQL and Redis
- Docker Compose
- CI
- linting, typing, and tests
- product and architecture documentation

Planned MVP:

- public GitHub repository ingestion
- deterministic repository graph
- source parsing for Python, TypeScript, and JavaScript
- subsystem discovery
- decision extraction
- contributor intelligence
- adaptive Graph RAG
- cited AI answers
- evaluation against retrieval baselines

## Run Locally

```bash
docker compose up --build
```

Services:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
API Docs: http://localhost:8000/docs
```

Stop:

```bash
docker compose down
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

## Research Direction

Trace compares:

- keyword retrieval
- vector-only RAG
- graph-only retrieval
- adaptive hybrid retrieval

Main research question:

> Does a graph-augmented Software Atlas improve unfamiliar-repository understanding compared with vector-only retrieval?

## License

License not selected yet.
