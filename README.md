# Trace

> **Trace any decision back to its evidence.** A GitHub-grounded organizational memory that answers *"why does this exist?"* with citations — not keyword search, not a plain RAG chatbot.

[CI](#)
[Live demo](#)

**Live demo:** *add URL* · **Writeup:** *add link*

---

## The problem

Why a feature exists, which PR implemented a requirement, who understands a subsystem — this knowledge is scattered across issues, PRs, commits and releases, and decays as people and context move on. Flat keyword and vector search retrieve *documents* but lose the *connections* between them, so they can't answer relational, "why" and "how-did-this-evolve" questions.

Trace turns a repository's full GitHub history into a **knowledge graph** and answers questions with **evidence-backed reasoning** that traces real relationships across artifacts.

## What makes it different

Relationships are not guessed by an LLM. They come from **two layers**:

- **Deterministic graph** — edges extracted directly from GitHub metadata (`PR resolves issue`, `commit modifies file`, `release includes PR`, authorship, cross-references). High precision, real citations, zero hallucination.
- **Semantic overlay** — the LLM adds *only* topic clustering and "why" reasoning on top, with every LLM-derived edge flagged with a confidence score and its source spans.

Deterministic edges are treated as ground-truth citations; LLM edges are always shown as such. That split is the system's integrity guarantee — and the reason its answers survive scrutiny.

## Results

Graph-augmented retrieval vs. baseline vector RAG on a hand-labeled QA set (RAGAS):


| Metric            | Baseline RAG | Trace (graph-augmented) |
| ----------------- | ------------ | ----------------------- |
| Faithfulness      | *tbd*        | *tbd*                   |
| Answer relevancy  | *tbd*        | *tbd*                   |
| Context precision | *tbd*        | *tbd*                   |
| Context recall    | *tbd*        | *tbd*                   |


> *Fill in after running `eval/run_eval.py`. This table is the headline of the project — keep it at the top.*

## How it works

```
GitHub API ──▶ Ingestion ──▶ Deterministic graph ──▶ Semantic overlay (LLM)
                                       │                        │
                                       ▼                        ▼
                              PostgreSQL + pgvector  (nodes | edges | embeddings)
                                       │
              Query ──▶ Hybrid retrieval (vector + graph traversal)
                     ──▶ LangGraph reasoning ──▶ cited answer + evidence subgraph
```

Everything runs on a **single PostgreSQL + pgvector** instance — graph traversal via recursive CTEs, semantic recall via pgvector. No separate graph or vector database.

## Flagship queries

- **Decision traceability** — "Why was X built?" walks the decision → issue/PR/discussion evidence chain.
- **Semantic + graph search** — "What discusses authentication?" combines vector recall with topic-graph expansion.
- **Expert discovery** — "Who knows subsystem Y?" ranks people by authorship/review/file activity on related artifacts.

## Tech stack


| Layer     | Tech                                                 |
| --------- | ---------------------------------------------------- |
| Frontend  | React + TypeScript + Vite, D3.js (graph + timeline)  |
| Backend   | FastAPI (Python 3.11+), LangGraph                    |
| Datastore | PostgreSQL 16 + pgvector                             |
| AI        | Configurable LLM + embedding provider                |
| Eval      | RAGAS                                                |
| Infra     | Docker Compose, GitHub Actions (lint · test · build) |


## Project structure

```
trace/
├── backend/        FastAPI: ingestion, graph, semantic, retrieval, reasoning, api
├── frontend/       React + Vite: query panel, D3 graph view, timeline, evidence panel
├── eval/           hand-labeled QA set + RAGAS harness (baseline vs graph)
├── docs/           PRD
└── docker-compose.yml
```

## Getting started

**Prerequisites:** Docker + Docker Compose, a GitHub personal access token (read-only), an LLM/embedding API key.

```bash
git clone https://github.com/<you>/trace.git
cd trace
cp .env.example .env          # add GITHUB_TOKEN, LLM_API_KEY, DATABASE_URL, etc.
docker compose up --build     # starts postgres + backend + frontend
```

Ingest a repository into the graph:

```bash
docker compose exec backend python scripts/ingest.py --repo owner/name
```

Then open the frontend (default `http://localhost:5173`) and ask a question.

## Evaluation

```bash
docker compose exec backend python eval/run_eval.py
```

Runs the QA set through both baseline vector RAG and the graph-augmented pipeline and writes the comparison table to `eval/results/`.

## Roadmap

- Multi-source ingestion (Google Docs, PDFs, meeting notes)
- Incremental / webhook-driven ingestion
- Multi-repo organization model
- LightRAG-style dual-level retrieval as a comparison arm

## License

MIT